"""
modules/capture.py  —  PubCast AI FFmpeg Capture Engine
=========================================================
Sits alongside RecordingService. When a session is ACTIVE,
FFmpegCaptureEngine spawns one FFmpeg process per source,
writes real media files into the session directory, and
registers them as RecordingArtifacts when stopped.

Transport → FFmpeg input mapping
---------------------------------
  virtual      → lavfi testsrc (safe fallback, always works)
  file         → -i <endpoint>
  rtmp         → -i rtmp://...
  srt          → -i srt://...
  ndi          → -i 'device_name()=<endpoint>' via libndi_newtek (if available)
  voxel_3d     → -i <endpoint> (TCP stream from Rust renderer)

Environment:
  PUBCAST_FFMPEG   path to ffmpeg binary  (default: ffmpeg on PATH)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# ── FFmpeg resolution ──────────────────────────────────────────────────────────
def _ffmpeg_bin() -> str:
    env = os.environ.get("PUBCAST_FFMPEG", "")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise EnvironmentError(
        "ffmpeg not found. Install ffmpeg and ensure it is on PATH, "
        "or set the PUBCAST_FFMPEG environment variable to the binary path."
    )


# ── Transport → FFmpeg input builder ─────────────────────────────────────────
_LISTEN_HOSTS = {"0.0.0.0", "::", "[::]"}
# FFmpeg's default 5 s look at a live stream before it starts encoding is time during which the take is already
# running; 2 s is enough to see the picture and sound of a phone or camera and halves the delay.
_LIVE_PROBE = ["-analyzeduration", "2000000", "-probesize", "2000000"]


def _is_listener(endpoint: str) -> bool:
    """True when the endpoint names this machine's own address, i.e. the camera connects to us."""
    try:
        return (urlsplit(endpoint).hostname or "") in {h.strip("[]") for h in _LISTEN_HOSTS}
    except ValueError:
        return False


def _srt_endpoint(endpoint: str) -> str:
    """SRT defaults to calling out; an endpoint on 0.0.0.0 means "wait for the camera", so say so."""
    if not _is_listener(endpoint):
        return endpoint
    parts = urlsplit(endpoint)
    if "mode=" in parts.query:
        return endpoint
    query = (parts.query + "&" if parts.query else "") + "mode=listener"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _webcam_input(endpoint: str) -> List[str]:
    """A camera attached to this machine. ``/dev/videoN`` is Linux, ``avfoundation:N`` macOS, anything else DirectShow."""
    if endpoint.startswith("/dev/"):
        return ["-f", "v4l2", "-i", endpoint]
    if endpoint.lower().startswith("avfoundation:"):
        return ["-f", "avfoundation", "-framerate", "30", "-i", endpoint.split(":", 1)[1]]
    device = endpoint if endpoint.lower().startswith("video=") else f"video={endpoint}"
    return ["-f", "dshow", "-i", device]


def _build_ffmpeg_input(transport: str, endpoint: str) -> List[str]:
    """Return the FFmpeg input argument list for a given camera source."""
    t = transport.lower()

    if t == "virtual":
        # Lavfi test pattern — reliable fallback that always works
        return ["-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30"]

    if t == "file":
        return ["-re", "-i", endpoint]          # -re = real-time read-back

    if t == "rtmp":
        # A phone app or camera that PUSHES to us: an endpoint on 0.0.0.0 makes FFmpeg the server and wait for it.
        return (["-listen", "1"] if _is_listener(endpoint) else []) + _LIVE_PROBE + ["-i", endpoint]

    if t == "srt":
        return _LIVE_PROBE + ["-i", _srt_endpoint(endpoint)]

    if t == "rtsp":
        # IP cameras. TCP avoids the dropped-packet corruption UDP gives over Wi-Fi.
        return ["-rtsp_transport", "tcp"] + _LIVE_PROBE + ["-i", endpoint]

    if t == "webcam":
        return _webcam_input(endpoint)

    if t == "ndi":
        # Requires FFmpeg built with libndi_newtek
        return ["-f", "libndi_newtek", "-i", endpoint]

    if t == "voxel_3d":
        if endpoint.startswith("rust://"):
            raise ValueError("Native voxel camera is registered for pose control only")
        return ["-i", endpoint]

    # Unknown — try as raw input and hope for the best
    logger.warning("Unknown transport '%s' for endpoint '%s' — using raw -i", t, endpoint)
    return ["-i", endpoint]


# Profiles name codecs the way the container does ("vp9", "opus"); FFmpeg's encoders have other names.
# Without this translation FFmpeg exits at once ("Unknown encoder 'vp9'") and nothing is recorded.
_ENCODER_ALIASES = {
    "h264": "libx264", "avc": "libx264", "h265": "libx265", "hevc": "libx265",
    "vp8": "libvpx", "vp9": "libvpx-vp9", "opus": "libopus", "mp3": "libmp3lame",
}


def _encoder(name: str) -> str:
    return _ENCODER_ALIASES.get(str(name).lower(), name)


def _live_encoder_args(video_codec: str) -> List[str]:
    """Settings that let a software encoder keep up with a live source.

    x264's default preset ("medium") encodes the 1080p/59.94 broadcast profile at roughly half real time on a
    two-core machine, so a stopped recording was silently much shorter than the take. "veryfast" keeps up at a
    small cost in compression. Set PUBCAST_CAPTURE_X264_PRESET (any x264 preset name) to change it.
    """
    if video_codec == "libx264":
        return ["-preset", os.environ.get("PUBCAST_CAPTURE_X264_PRESET", "veryfast")]
    if video_codec == "libvpx-vp9":
        return ["-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1"]
    return []


def _ffmpeg_bitrate(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    clean = str(value).strip()
    lower = clean.lower()
    if lower.endswith("mbps"):
        return clean[:-4] + "M"
    if lower.endswith("kbps"):
        return clean[:-4] + "k"
    return clean


# ── Encoding profile → FFmpeg output args ─────────────────────────────────────
def _file_stem(name: str) -> str:
    """A source or input name as a plain file name: no folder separators in either style, no drive colon."""
    return str(name).replace("/", "_").replace("\\", "_").replace(":", "_")


def _reserve_output_path(session_dir: Path, stem: str, ext: str, reserved: set) -> Path:
    """The file this source records to, different from every file already given out in this take.

    Two different source ids can clean to the same stem ("cam/a" and "cam_a"), and Windows and macOS
    folders treat names that differ only in case as one file; either would make two cameras overwrite
    each other's recording. The second and later ones get -2, -3 ... so every source keeps its own file.
    """
    candidate, number = session_dir / f"{stem}.{ext}", 2
    while candidate.name.casefold() in reserved:
        candidate = session_dir / f"{stem}-{number}.{ext}"
        number += 1
    reserved.add(candidate.name.casefold())
    return candidate


def _build_ffmpeg_output(profile, output_path: Path) -> List[str]:
    """Return FFmpeg codec/output arguments from an EncodingProfile."""
    args: List[str] = []

    if profile.video_codec and not profile.is_audio_only:
        video_codec = _encoder(profile.video_codec)
        args += ["-c:v", video_codec] + _live_encoder_args(video_codec)
        video_bitrate = _ffmpeg_bitrate(profile.video_bitrate)
        if video_bitrate:
            args += ["-b:v", video_bitrate]
        if profile.resolution:
            w, h = profile.resolution.split("x")
            args += ["-s", f"{w}x{h}"]
        if profile.frame_rate:
            args += ["-r", profile.frame_rate]
        if video_codec == "libx264":
            args += ["-pix_fmt", "yuv420p"]
    else:
        args += ["-vn"]   # no video

    if profile.audio_codec:
        args += ["-c:a", _encoder(profile.audio_codec)]
        audio_bitrate = _ffmpeg_bitrate(profile.audio_bitrate)
        if audio_bitrate:
            args += ["-b:a", audio_bitrate]
    else:
        args += ["-an"]

    args.append(str(output_path))
    return args


_STARTUP_CHECK_SECONDS = 0.6   # how long to wait before asking whether FFmpeg is still running
_LAG_SPEED = 0.97              # encode speed (x real time) below which the take is reported as short


# ── Per-source process handle ─────────────────────────────────────────────────
@dataclass
class _CaptureProcess:
    source_id: str
    output_path: Path
    proc: asyncio.subprocess.Process
    started_at: float = field(default_factory=time.time)
    log_path: Optional[Path] = None
    stopped_at: Optional[float] = None

    async def terminate(self) -> None:
        self.stopped_at = time.time()
        if self.proc.returncode is None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(b"q")
                    await self.proc.stdin.drain()
                await asyncio.wait_for(self.proc.wait(), timeout=8.0)
            except asyncio.TimeoutError:
                try:
                    self.proc.terminate()
                    await asyncio.wait_for(self.proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.proc.kill()
                    await self.proc.wait()
            except (BrokenPipeError, ConnectionResetError):
                await self.proc.wait()
        logger.info("Capture process for %s finished (rc=%s)", self.source_id, self.proc.returncode)


# ── Capture Engine ────────────────────────────────────────────────────────────
class FFmpegCaptureEngine:
    """
    Manages FFmpeg processes for active recording sessions.
    One engine instance lives for the lifetime of the server.
    """

    def __init__(self) -> None:
        self._active: Dict[str, List[_CaptureProcess]] = {}   # session_id → [processes]
        # Outputs recorded from the lavfi test pattern, kept after stop() so the
        # artifact list can say which files are not real camera video.
        self._synthetic: Dict[str, List[Path]] = {}
        # What FFmpeg actually did, per session: failed starts and encoders that fell behind real time.
        self._reports: Dict[str, List[dict]] = {}
        self._startup_failures: Dict[str, List[dict]] = {}
        try:
            self._bin = _ffmpeg_bin()
            logger.info("FFmpegCaptureEngine ready: %s", self._bin)
        except EnvironmentError as e:
            self._bin = None
            logger.warning("FFmpegCaptureEngine: %s  —  capture disabled.", e)

    @property
    def available(self) -> bool:
        return self._bin is not None

    # ── Public API ─────────────────────────────────────────────────────────────
    async def start(
        self,
        session_id: str,
        sources,          # list of CameraSource objects
        profile,          # EncodingProfile object
        session_dir: Path,
        audio_input=None,  # optional AudioInput (a microphone): recorded with the FIRST source, replacing its own sound
    ) -> List[Path]:
        """
        Spawn one FFmpeg process per source.
        Returns list of output file paths (one per source).
        """
        if not self.available:
            logger.warning("FFmpeg not available — session %s will have no media.", session_id)
            return []

        if session_id in self._active:
            logger.warning("Session %s already capturing — ignoring duplicate start.", session_id)
            return [cp.output_path for cp in self._active[session_id]]

        self._reports.pop(session_id, None)
        self._startup_failures.pop(session_id, None)
        mic_pending = audio_input is not None
        procs: List[_CaptureProcess] = []
        output_paths: List[Path] = []
        synthetic_paths: List[Path] = []
        reserved_names: set = set()

        for src in sources:
            ext = profile.container.value          # mp4 / webm / wav / mov
            out_path = _reserve_output_path(session_dir, _file_stem(src.source_id), ext, reserved_names)

            input_args  = _build_ffmpeg_input(src.transport.value, src.endpoint)
            if mic_pending:
                mic_pending = False
                # Two sources cannot both open one microphone, so it goes to the first. Picture from input 0,
                # sound from the microphone (input 1); an audio-only profile takes the microphone alone.
                input_args = input_args + audio_input.ffmpeg_args()
                input_args += ["-map", "1:a:0"] if profile.is_audio_only else ["-map", "0:v:0", "-map", "1:a:0"]
            output_args = _build_ffmpeg_output(profile, out_path)

            cmd = [self._bin, "-y", "-hide_banner"] + input_args + output_args
            cp = await self._spawn(cmd, src.source_id, out_path)
            if cp is not None:
                procs.append(cp)
                output_paths.append(out_path)
                if src.transport.value.lower() == "virtual":
                    synthetic_paths.append(out_path)
                    logger.warning(
                        "Source %s is a virtual camera: %s will contain an FFmpeg test pattern, not rendered PubWorld video.",
                        src.source_id, out_path,
                    )

        await self._register_started(session_id, procs)
        if synthetic_paths:
            self._synthetic[session_id] = synthetic_paths
            while len(self._synthetic) > 50:   # bounded: drop the oldest session's record
                self._synthetic.pop(next(iter(self._synthetic)))

        return output_paths

    async def start_audio_input(self, session_id: str, audio_input, profile, session_dir: Path,
                                *, name: str = "microphone") -> List[Path]:
        """Record a microphone on its own, for the whole of ``session_id``.

        ``audio_input`` is an ``AudioInput`` (modules/audio_input_spec.py); nothing else is opened, so a camera
        that is also being recorded is never opened twice. ``profile`` should be audio-only; any picture settings
        in it are ignored. The file is ``<name>.<container>`` in ``session_dir``.
        """
        if not self.available:
            logger.warning("FFmpeg not available — microphone for %s will not be recorded.", session_id)
            return []
        if session_id in self._active:
            logger.warning("Session %s already capturing — ignoring duplicate start.", session_id)
            return [cp.output_path for cp in self._active[session_id]]
        self._reports.pop(session_id, None)
        self._startup_failures.pop(session_id, None)
        safe_name = _file_stem(name)
        out_path = session_dir / f"{safe_name}.{profile.container.value}"
        args = _build_ffmpeg_output(profile, out_path)
        if "-vn" not in args:
            args = ["-vn"] + args
        cmd = [self._bin, "-y", "-hide_banner"] + audio_input.ffmpeg_args() + args
        cp = await self._spawn(cmd, safe_name, out_path)
        await self._register_started(session_id, [cp] if cp is not None else [])
        return [out_path] if cp is not None else []

    async def _spawn(self, cmd: List[str], source_id: str, out_path: Path) -> Optional["_CaptureProcess"]:
        """Start one FFmpeg process writing ``out_path``, with its log kept beside it."""
        logger.info("FFmpeg cmd for %s: %s", source_id, " ".join(cmd))
        log_path = out_path.with_name(out_path.name + ".ffmpeg.log")
        try:
            # FFmpeg's own output is kept next to the take: it is the only record of why an encode failed or lagged.
            with open(log_path, "wb") as log_file:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=log_file,
                )
        except Exception as e:
            logger.error("Failed to start FFmpeg for %s: %s", source_id, e)
            return None
        logger.info("Capture started for %s → %s (pid=%d)", source_id, out_path, proc.pid)
        return _CaptureProcess(source_id=source_id, output_path=out_path, proc=proc, log_path=log_path)

    async def _register_started(self, session_id: str, procs: List["_CaptureProcess"]) -> None:
        if not procs:
            return
        self._active[session_id] = procs
        # An encoder that cannot start (unknown codec, bad input) exits within moments. Say so now
        # instead of letting the operator record to nothing.
        await asyncio.sleep(_STARTUP_CHECK_SECONDS)
        failed = [self._describe(cp) for cp in procs if cp.proc.returncode is not None]
        if failed:
            self._startup_failures[session_id] = failed
            self._bound(self._startup_failures)
            for item in failed:
                logger.error("Capture for %s failed to start: %s", item["source_id"], item["error"])

    def live_report(self, session_id: str) -> List[dict]:
        """The same account as ``report()``, for processes that are still running (empty when none are)."""
        return [self._report_for(cp) for cp in self._active.get(session_id, [])]

    def running(self, session_id: str) -> bool:
        """True while every process of ``session_id`` is still alive."""
        procs = self._active.get(session_id, [])
        return bool(procs) and all(cp.proc.returncode is None for cp in procs)

    def synthetic_outputs(self, session_id: str) -> List[Path]:
        """Outputs of this session recorded from the test pattern (``virtual`` transport).

        Still available after ``stop()`` so callers can mark the registered artifacts.
        """
        return list(self._synthetic.get(session_id, []))

    @staticmethod
    def _bound(store: Dict[str, list]) -> None:
        while len(store) > 50:
            store.pop(next(iter(store)))

    @staticmethod
    def _log_tail(path: Optional[Path], lines: int = 4) -> str:
        try:
            text = path.read_text(errors="replace") if path else ""
        except OSError:
            return ""
        parts = [p.strip() for p in re.split(r"[\r\n]+", text) if p.strip() and not p.lstrip().startswith(("frame=", "size=", "Lsize="))]
        return " | ".join(parts[-lines:])

    def _describe(self, cp: "_CaptureProcess") -> dict:
        return {"source_id": cp.source_id, "returncode": cp.proc.returncode,
                "error": self._log_tail(cp.log_path) or f"FFmpeg exited with status {cp.proc.returncode}"}

    def _report_for(self, cp: "_CaptureProcess") -> dict:
        """What this encode did, read from FFmpeg's own progress lines."""
        try:
            text = cp.log_path.read_text(errors="replace") if cp.log_path else ""
        except OSError:
            text = ""
        speeds = re.findall(r"speed=\s*([0-9.]+)x", text)
        times = re.findall(r"time=(\d+):(\d+):([0-9.]+)", text)
        speed = float(speeds[-1]) if speeds else None
        encoded = None
        if times:
            h, m, sec = times[-1]
            encoded = int(h) * 3600 + int(m) * 60 + float(sec)
        wall = ((cp.stopped_at or time.time()) - cp.started_at)
        size = cp.output_path.stat().st_size if cp.output_path.exists() else 0
        warnings: List[str] = []
        rc = cp.proc.returncode
        if rc not in (0, 255, -15, None):
            warnings.append(f"FFmpeg exited with status {rc}: {self._log_tail(cp.log_path)}")
        if text and "Input #0" not in text:
            warnings.append("FFmpeg never opened the input: nothing connected to this listener, or the device or address could not be opened")
        if size == 0:
            warnings.append("No media was written for this source")
        if speed is not None and speed < _LAG_SPEED and wall >= 3.0:
            warnings.append(f"Encoder ran at {speed:.2f}x real time: this recording is shorter than the take "
                            "and the missing footage is not recoverable. Use a lighter profile or a faster preset "
                            "(PUBCAST_CAPTURE_X264_PRESET).")
        return {"source_id": cp.source_id, "returncode": rc, "output_bytes": size,
                "wall_seconds": round(wall, 2), "encoded_seconds": encoded, "speed": speed,
                "warnings": warnings, "log": cp.log_path.as_posix() if cp.log_path else None}

    def startup_failures(self, session_id: str) -> List[dict]:
        """Sources whose FFmpeg exited within moments of starting (empty when all are running)."""
        return list(self._startup_failures.get(session_id, []))

    def report(self, session_id: str) -> List[dict]:
        """Per-source account of a stopped session's capture: exit status, speed, and anything the operator must know."""
        return list(self._reports.get(session_id, []))

    async def stop(self, session_id: str) -> List[Path]:
        """
        Terminate all FFmpeg processes for a session.
        Returns list of completed output file paths.
        """
        procs = self._active.pop(session_id, [])
        output_paths: List[Path] = []

        for cp in procs:
            await cp.terminate()
            self._reports.setdefault(session_id, []).append(self._report_for(cp))
            self._bound(self._reports)
            if cp.output_path.exists() and cp.output_path.stat().st_size > 0:
                output_paths.append(cp.output_path)
                logger.info("Artifact ready: %s (%d bytes)", cp.output_path, cp.output_path.stat().st_size)
            else:
                logger.warning("No media written for %s — file missing or empty.", cp.source_id)

        return output_paths

    async def pause(self, session_id: str) -> None:
        """Send SIGSTOP to all processes (Unix) or no-op on Windows."""
        for cp in self._active.get(session_id, []):
            if cp.proc.returncode is None:
                try:
                    import signal
                    cp.proc.send_signal(signal.SIGSTOP)
                except (AttributeError, ProcessLookupError, OSError):
                    pass   # Windows: SIGSTOP not available — silently skip

    async def resume(self, session_id: str) -> None:
        """Send SIGCONT to all processes (Unix) or no-op on Windows."""
        for cp in self._active.get(session_id, []):
            if cp.proc.returncode is None:
                try:
                    import signal
                    cp.proc.send_signal(signal.SIGCONT)
                except (AttributeError, ProcessLookupError, OSError):
                    pass

    def is_capturing(self, session_id: str) -> bool:
        return session_id in self._active

    def active_sessions(self) -> List[str]:
        return list(self._active.keys())

    async def shutdown(self) -> None:
        """Graceful shutdown — stop all active captures."""
        for sid in list(self._active.keys()):
            await self.stop(sid)
        logger.info("FFmpegCaptureEngine shut down.")
