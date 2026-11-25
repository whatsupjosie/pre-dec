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
import signal
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


_LOG_SUFFIX = ".ffmpeg.log"


def _names_in_use(session_dir: Path) -> set:
    """Every media name already present in ``session_dir``, folded for case-insensitive folders.

    A file left by an earlier recording (or another take's file in the same folder) is never a
    fresh name: FFmpeg runs with ``-n`` and would refuse to start on it, and before that change it
    overwrote it. A log whose media is gone still holds the name, so its log is not replaced either.
    """
    try:
        entries = [entry.name for entry in session_dir.iterdir()]
    except FileNotFoundError:
        return set()
    names = set()
    for name in entries:
        folded = name.casefold()
        names.add(folded)
        if folded.endswith(_LOG_SUFFIX):
            names.add(folded[: -len(_LOG_SUFFIX)])
    return names


def _reserve_output_path(session_dir: Path, stem: str, ext: str, reserved: set) -> Path:
    """The file this source records to, different from every file already given out in this take.

    Two different source ids can clean to the same stem ("cam/a" and "cam_a"), and Windows and macOS
    folders treat names that differ only in case as one file; either would make two cameras overwrite
    each other's recording. The second and later ones get -2, -3 ... so every source keeps its own file.
    ``reserved`` starts with the names already in the folder (``_names_in_use``), so a file from
    earlier is skipped the same way.
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
# Exit codes of an FFmpeg that was stopped on purpose: 0 after "q", 255 after it handled a stop
# signal, -15 when the stop signal ended it. Anything else means the encoder failed.
_STOPPED_CLEANLY = (0, 255, -15)


class PauseUnsupported(RuntimeError):
    """This machine has no way to suspend a running FFmpeg, so a pause would not stop the recording."""


def _windows_suspend(pid: int, paused: bool) -> None:
    """Suspend or resume every thread of process ``pid`` (Windows has no SIGSTOP).

    Uses the same system calls as Task Manager and Process Explorer (NtSuspendProcess and
    NtResumeProcess in ntdll), so nothing has to be installed.
    """
    import ctypes
    from ctypes import wintypes

    process_suspend_resume = 0x0800
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    call = ntdll.NtSuspendProcess if paused else ntdll.NtResumeProcess
    call.argtypes = (wintypes.HANDLE,)
    call.restype = ctypes.c_long
    handle = kernel32.OpenProcess(process_suspend_resume, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), f"Windows would not let PubCast {'pause' if paused else 'resume'} FFmpeg")
    try:
        status = call(handle)
    finally:
        kernel32.CloseHandle(handle)
    if status < 0:
        raise OSError(f"Windows refused to {'pause' if paused else 'resume'} FFmpeg (status 0x{status & 0xFFFFFFFF:08X})")


def _suspend(proc: "asyncio.subprocess.Process", paused: bool) -> None:
    """Stop or restart an encoder's clock: SIGSTOP/SIGCONT where they exist, the Windows calls on Windows."""
    if os.name == "nt":
        _windows_suspend(proc.pid, paused)
        return
    sig = getattr(signal, "SIGSTOP" if paused else "SIGCONT", None)
    if sig is None:
        raise PauseUnsupported("This machine cannot suspend a running FFmpeg capture, so the take cannot be paused")
    proc.send_signal(sig)


# ── Per-source process handle ─────────────────────────────────────────────────
@dataclass
class _CaptureProcess:
    source_id: str
    output_path: Path
    proc: asyncio.subprocess.Process
    started_at: float = field(default_factory=time.time)
    log_path: Optional[Path] = None
    stopped_at: Optional[float] = None
    paused: bool = False
    paused_since: Optional[float] = None
    paused_seconds: float = 0.0        # time spent suspended, finished pauses only

    def set_paused(self, paused: bool) -> None:
        """Suspend (True) or resume (False) this encoder. Raises when that did not happen."""
        if self.paused == paused:
            return
        if self.proc.returncode is not None:
            raise RuntimeError(f"The encoder for {self.source_id} has already stopped")
        _suspend(self.proc, paused)
        now = time.time()
        if paused:
            self.paused_since = now
        else:
            self.paused_seconds += now - (self.paused_since or now)
            self.paused_since = None
        self.paused = paused

    def suspended_seconds(self, at: Optional[float] = None) -> float:
        """Seconds this encoder has been suspended, counting a pause still in progress."""
        current = ((at or time.time()) - self.paused_since) if self.paused_since is not None else 0.0
        return self.paused_seconds + max(0.0, current)

    async def terminate(self) -> None:
        self.stopped_at = time.time()
        if self.proc.returncode is None:
            if self.paused:
                # A suspended FFmpeg cannot read the "q" that finishes its file; let it run again first.
                try:
                    self.set_paused(False)
                except (ProcessLookupError, OSError, RuntimeError):
                    logger.warning("Could not resume the paused encoder for %s before stopping it", self.source_id)
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(b"q")
                    await self.proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                # FFmpeg cannot hear "q". Waiting for it to end by itself would hang on a live camera,
                # which never ends, so it gets the same grace time and then the stop signal.
                pass
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=8.0)
            except asyncio.TimeoutError:
                try:
                    self.proc.terminate()
                    await asyncio.wait_for(self.proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.proc.kill()
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
        spawn_failures: List[dict] = []
        reserved_names = self._reserved_names(session_dir)

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

            # -n: FFmpeg refuses to write over a file that is already there, so no recording is ever replaced.
            cmd = [self._bin, "-n", "-hide_banner"] + input_args + output_args
            cp = await self._spawn(cmd, src.source_id, out_path)
            if cp is None:
                spawn_failures.append({"source_id": src.source_id, "returncode": None,
                                       "error": "FFmpeg could not be started for this source; see the server log"})
            else:
                procs.append(cp)
                output_paths.append(out_path)
                if src.transport.value.lower() == "virtual":
                    synthetic_paths.append(out_path)
                    logger.warning(
                        "Source %s is a virtual camera: %s will contain an FFmpeg test pattern, not rendered PubWorld video.",
                        src.source_id, out_path,
                    )

        await self._register_started(session_id, procs, spawn_failures)
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
        out_path = _reserve_output_path(session_dir, safe_name, profile.container.value,
                                        self._reserved_names(session_dir))
        args = _build_ffmpeg_output(profile, out_path)
        if "-vn" not in args:
            args = ["-vn"] + args
        cmd = [self._bin, "-n", "-hide_banner"] + audio_input.ffmpeg_args() + args
        cp = await self._spawn(cmd, safe_name, out_path)
        failures = [] if cp is not None else [{"source_id": safe_name, "returncode": None,
                                               "error": "FFmpeg could not be started for the microphone; see the server log"}]
        await self._register_started(session_id, [cp] if cp is not None else [], failures)
        return [out_path] if cp is not None else []

    def _reserved_names(self, session_dir: Path) -> set:
        """Names nobody may record to in ``session_dir``: files already there, and every file a running
        encoder is writing into that folder (its file may not exist yet in the first moments)."""
        names = _names_in_use(session_dir)
        folder = session_dir.resolve()
        for procs in self._active.values():
            for cp in procs:
                if cp.output_path.parent.resolve() == folder:
                    names.add(cp.output_path.name.casefold())
        return names

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

    async def _register_started(self, session_id: str, procs: List["_CaptureProcess"],
                                spawn_failures: Optional[List[dict]] = None) -> None:
        failed: List[dict] = list(spawn_failures or [])
        if procs:
            self._active[session_id] = procs
            # An encoder that cannot start (unknown codec, bad input, a file already there) exits within
            # moments. Say so now instead of letting the operator record to nothing.
            await asyncio.sleep(_STARTUP_CHECK_SECONDS)
            failed += [self._describe(cp) for cp in procs if cp.proc.returncode is not None]
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
        end = cp.stopped_at or time.time()
        wall = end - cp.started_at
        suspended = cp.suspended_seconds(end)
        if suspended > 0 and encoded is not None and wall - suspended > 0:
            # FFmpeg's own speed counts the paused time as time it fell behind; a pause is not lag.
            speed = round(encoded / (wall - suspended), 3)
        size = cp.output_path.stat().st_size if cp.output_path.exists() else 0
        warnings: List[str] = []
        rc = cp.proc.returncode
        if rc not in _STOPPED_CLEANLY + (None,):
            warnings.append(f"FFmpeg exited with status {rc}: {self._log_tail(cp.log_path)}")
        if text and "Input #0" not in text:
            warnings.append("FFmpeg never opened the input: nothing connected to this listener, or the device or address could not be opened")
        if size == 0:
            warnings.append("No media was written for this source")
        if speed is not None and speed < _LAG_SPEED and wall - suspended >= 3.0:
            warnings.append(f"Encoder ran at {speed:.2f}x real time: this recording is shorter than the take "
                            "and the missing footage is not recoverable. Use a lighter profile or a faster preset "
                            "(PUBCAST_CAPTURE_X264_PRESET).")
        report = {"source_id": cp.source_id, "returncode": rc, "output_bytes": size,
                  "wall_seconds": round(wall, 2), "encoded_seconds": encoded, "speed": speed,
                  "warnings": warnings, "log": cp.log_path.as_posix() if cp.log_path else None}
        if suspended > 0:
            report["paused_seconds"] = round(suspended, 2)
        return report

    @staticmethod
    def _stop_failure(cp: "_CaptureProcess", report: dict, error: Optional[BaseException]) -> Optional[str]:
        """Why this source's recording did not finish properly, or None when it did."""
        if error is not None and cp.proc.returncode is None:
            return f"The encoder could not be stopped ({error}); it may still be running"
        rc = cp.proc.returncode
        has_bytes = report.get("output_bytes", 0) > 0
        if rc in _STOPPED_CLEANLY and has_bytes:
            return None
        detail = (f"FFmpeg exited with status {rc}" if rc not in _STOPPED_CLEANLY
                  else "FFmpeg stopped")
        tail = FFmpegCaptureEngine._log_tail(cp.log_path, 2)
        if tail and rc not in _STOPPED_CLEANLY:
            detail += f": {tail}"
        return detail + ("; the partial recording is kept" if has_bytes else "; no media was recorded")

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
        procs = self._active.get(session_id, [])
        output_paths: List[Path] = []
        # Every camera is told to stop at once: one slow encoder must not hold the others (or a PANIC) back.
        results = await asyncio.gather(*(cp.terminate() for cp in procs), return_exceptions=True)
        reports = self._reports.setdefault(session_id, [])
        for cp, result in zip(procs, results):
            error = result if isinstance(result, BaseException) else None
            report = self._report_for(cp)
            failure = self._stop_failure(cp, report, error)
            if failure:
                report["failed"] = True
                report["error"] = failure
                logger.warning("Capture %s/%s: %s", session_id, cp.source_id, failure)
            reports.append(report)
            if cp.proc.returncode is not None and report["output_bytes"] > 0:
                output_paths.append(cp.output_path)
                logger.info("Artifact ready: %s (%d bytes)", cp.output_path, report["output_bytes"])
            elif cp.proc.returncode is not None:
                logger.warning("No media written for %s — file missing or empty.", cp.source_id)
        self._bound(self._reports)
        still_running = [cp for cp in procs if cp.proc.returncode is None]
        if still_running:
            # Kept so a second stop (or PANIC) tries again instead of forgetting a live encoder.
            self._active[session_id] = still_running
        else:
            self._active.pop(session_id, None)
        return output_paths

    def failures(self, session_id: str) -> List[dict]:
        """Sources of a session that did not record properly: failed to start, or failed when stopped.

        Each is ``{"source_id", "error", "phase"}`` with phase "start" or "stop"."""
        items = [{"source_id": f.get("source_id"), "error": f.get("error"), "phase": "start"}
                 for f in self._startup_failures.get(session_id, [])]
        items += [{"source_id": r.get("source_id"), "error": r.get("error"), "phase": "stop"}
                  for r in self._reports.get(session_id, []) if r.get("failed")]
        return items

    def set_paused(self, session_id: str, paused: bool) -> None:
        """Suspend or resume every encoder of ``session_id``, or none of them.

        Raises (PauseUnsupported, OSError, RuntimeError) when a running encoder could not change; the ones
        that already had are put back, so the take is never half paused. A pause that cannot happen
        is reported, never skipped: a "paused" take that keeps recording is the worse failure.
        """
        changed: List[_CaptureProcess] = []
        try:
            for cp in self._active.get(session_id, []):
                # An encoder that already ended (one that failed to start, say) records nothing to pause.
                if cp.paused != paused and cp.proc.returncode is None:
                    cp.set_paused(paused)
                    changed.append(cp)
        except Exception:
            for cp in reversed(changed):
                try:
                    cp.set_paused(not paused)
                except (RuntimeError, OSError):
                    logger.exception("Could not put the encoder for %s back as it was", cp.source_id)
            raise

    def is_paused(self, session_id: str) -> bool:
        procs = self._active.get(session_id, [])
        return bool(procs) and all(cp.paused for cp in procs if cp.proc.returncode is None)

    async def pause(self, session_id: str) -> None:
        self.set_paused(session_id, True)

    async def resume(self, session_id: str) -> None:
        self.set_paused(session_id, False)

    def is_capturing(self, session_id: str) -> bool:
        return session_id in self._active

    def active_sessions(self) -> List[str]:
        return list(self._active.keys())

    async def shutdown(self) -> None:
        """Graceful shutdown — stop all active captures."""
        for sid in list(self._active.keys()):
            await self.stop(sid)
        logger.info("FFmpegCaptureEngine shut down.")
