# PubCast AI — reconstruction.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Turn a recorded take's show data back into pictures, from any camera.

A take's show data (modules/recording_modes.py) holds every camera cut, with its dissolve, and
every performer frame (modules/performance_capture.py): where each performer stood, how they
moved, their mouth weight, their gestures, the graphics on screen and the set. This module replays
it, frame by frame on a fixed time step, through the live 2.5D studio's own drawing code
(static/production25d_core.js, static/production25d_renderer.js, static/world_walk_glb.js),
loaded unchanged into a headless browser (modules/render_host/), and encodes what it draws with
FFmpeg, together with the take's recorded sound.

Cameras:
  "program"                follow the switcher, cuts and dissolves as they happened;
  a 2.5D source id          one camera for the whole take, e.g. "p25d_late_night_guest";
  {"center": [x, y], "zoom": z}   a camera that never existed live: any framing of the stage.

Nothing is invented. A stretch where Program was on a camera this renderer cannot draw (a real
camera, a phone) is black and named in the manifest; so is time before the first performer frame.
The output file is checked with ffprobe and a full decode before it is added to the take.

The browser is only needed here, never at startup. It is found, not installed: set
PUBCAST_RENDER_BROWSER to a Chrome/Chromium/Edge executable, or let Playwright use Microsoft Edge
on Windows, Google Chrome, or its own Chromium.
"""
from __future__ import annotations

import asyncio
import base64
import bisect
import hashlib
import json
import logging
import math
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from modules.recording_modes import MODE_RECORD_FILE, SHOW_DATA_FILE, iter_show_data

logger = logging.getLogger("pubcast.reconstruction")

REPO = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO / "static"
HOST_DIR = Path(__file__).resolve().parent / "render_host"
ORIGIN = "http://pubcast-render.invalid"
RENDERER_FILES = ("static/production25d_core.js", "static/production25d_renderer.js", "static/world_walk_glb.js",
                  "modules/render_host/reconstruct.html", "modules/render_host/reconstruct.js")
STUDIO25D_PREFIX = "p25d_"
FPS_CHOICES = (24, 25, 30)
BATCH = 12
QUALITY = {"standard": {"format": "jpeg", "quality": 0.95, "preset": "veryfast", "crf": 18},
           "master": {"format": "png", "quality": 1.0, "preset": "medium", "crf": 14}}
BROWSER_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
                "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]
SCHEMA = "pubcast.reconstruction/1"

CameraSpec = Union[str, Dict[str, Any]]


class ReconstructionError(RuntimeError):
    """A reconstruction that cannot be done, with the reason in words."""


# ---------------------------------------------------------------------------------------------------------
# Reading the take
# ---------------------------------------------------------------------------------------------------------
@dataclass
class Cut:
    t: float                                  # show time (seconds from the show data header)
    source_id: Optional[str]
    dissolve_s: float = 0.0
    previous: Optional[str] = None


@dataclass
class ShowTimeline:
    """Everything reconstruction needs from show_data.jsonl.gz, on the show data's own clock."""
    header: Dict[str, Any]
    end_t: float
    pauses: List[Tuple[float, float]]
    cuts: List[Cut]
    stage_t: List[float]
    stages: List[Dict[str, Any]]
    gestures: List[Tuple[float, Dict[str, Any]]]
    complete: bool
    notes: List[str] = field(default_factory=list)
    mixes: List[Tuple[float, Dict[str, Any]]] = field(default_factory=list)   # (show time, Program mix)

    @classmethod
    def read(cls, path: Path) -> "ShowTimeline":
        header: Optional[Dict[str, Any]] = None
        footer: Optional[Dict[str, Any]] = None
        pauses: List[Tuple[float, Optional[float]]] = []
        cuts: List[Cut] = []
        stage_t: List[float] = []
        stages: List[Dict[str, Any]] = []
        gestures: List[Tuple[float, Dict[str, Any]]] = []
        mixes: List[Tuple[float, Dict[str, Any]]] = []
        last_t = 0.0
        for entry in iter_show_data(path):
            if entry.get("header"):
                header = entry
                continue
            if entry.get("footer"):
                footer = entry
                continue
            t = float(entry.get("t", 0.0))
            last_t = max(last_t, t)
            kind, data = entry.get("kind"), entry.get("data") or {}
            if kind == "camera.switch" and data.get("destination") == "program":
                how = data.get("transition") or {}
                dissolve = how.get("duration_ms", 0) / 1000.0 if how.get("type") == "dissolve" else 0.0
                cuts.append(Cut(t, data.get("source_id"), dissolve, data.get("previous_source_id")))
            elif kind == "performance.frame":
                stage = data.get("stage")
                if isinstance(stage, dict):
                    stage_t.append(t)
                    stages.append(stage)
                for g in data.get("gestures") or []:
                    gestures.append((t, g))
            elif kind == "audio.mix" and isinstance(data.get("channels"), dict):
                mixes.append((t, data))
            elif kind == "take.paused":
                pauses.append((t, None))
            elif kind == "take.resumed" and pauses and pauses[-1][1] is None:
                pauses[-1] = (pauses[-1][0], t)
        if header is None:
            raise ReconstructionError("The show data has no header; it is not a PubCast take")
        notes: List[str] = []
        if footer and isinstance(footer.get("closed_utc"), (int, float)):
            end_t = max(last_t, float(footer["closed_utc"]) - float(header.get("utc_origin", 0.0)))
        else:
            end_t = last_t
            notes.append("The show data was not closed (the take ended abruptly); it is replayed up to its last event")
        closed = [(a, b if b is not None else end_t) for a, b in pauses]
        # Events are written in the order they arrive; a batch or a back-dated stamp can arrive late. Time decides.
        cuts.sort(key=lambda c: c.t)
        order = sorted(range(len(stage_t)), key=lambda i: (stage_t[i], i))
        stage_t, stages = [stage_t[i] for i in order], [stages[i] for i in order]
        gestures.sort(key=lambda g: g[0])
        mixes.sort(key=lambda m: m[0])
        closed.sort()
        cuts.insert(0, Cut(0.0, header.get("program"), 0.0, None))
        return cls(header, end_t, closed, cuts, stage_t, stages, gestures, footer is not None, notes, mixes)

    @property
    def paused_seconds(self) -> float:
        return sum(b - a for a, b in self.pauses)

    @property
    def duration(self) -> float:
        """Take time: the show with its pauses taken out, the same clock as the take's sound files."""
        return max(0.0, self.end_t - self.paused_seconds)

    def show_time(self, take_t: float) -> float:
        """Take time to show-data time (pauses put back in)."""
        t = take_t
        for a, b in self.pauses:
            if t >= a:
                t += b - a
            else:
                break
        return t

    def take_time(self, show_t: float) -> float:
        """Show-data time to take time (pauses taken out; a moment inside a pause is the pause's start)."""
        return show_t - sum(min(b, show_t) - a for a, b in self.pauses if a < show_t)

    def gain_steps(self, source_id: Optional[str]) -> Optional[List[Tuple[float, float]]]:
        """[(take time, effective gain)] for the channel that carries ``source_id``, from the recorded mixes;
        None when no channel names that source (its sound is then kept at full level)."""
        if not source_id or not self.mixes:
            return None
        steps: List[Tuple[float, float]] = []
        claimed = False
        for t, mix in self.mixes:
            gain = 0.0 if any(c.get("source_id") == source_id for c in mix["channels"].values()) else None
            for channel in mix["channels"].values():
                if channel.get("source_id") == source_id:
                    claimed = True
                    gain = max(gain or 0.0, float(channel.get("effective_gain", 0.0)))
            steps.append((self.take_time(t), 1.0 if gain is None else gain))
        return steps if claimed else None

    def stage_at(self, t: float) -> Optional[Dict[str, Any]]:
        i = bisect.bisect_right(self.stage_t, t) - 1
        return self.stages[i] if i >= 0 else None

    def program_at(self, t: float) -> Tuple[Optional[str], Optional[str], float]:
        """(camera now, camera dissolving away from or None, how far the dissolve is 0..1)."""
        i = max(0, bisect.bisect_right([c.t for c in self.cuts], t) - 1)
        cut = self.cuts[i]
        if cut.dissolve_s > 0 and t < cut.t + cut.dissolve_s and cut.previous:
            return cut.source_id, cut.previous, (t - cut.t) / cut.dissolve_s
        return cut.source_id, None, 1.0


# ---------------------------------------------------------------------------------------------------------
# The headless browser
# ---------------------------------------------------------------------------------------------------------
def find_browser() -> Dict[str, Any]:
    """How to start a browser for rendering, or why none can be used. Never installs anything."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return {"available": False, "reason": "Playwright is not installed (pip install playwright); "
                                              "reconstruction needs it to drive a browser"}
    explicit = os.environ.get("PUBCAST_RENDER_BROWSER")
    if explicit:
        if Path(explicit).is_file():
            return {"available": True, "executable_path": explicit, "source": "PUBCAST_RENDER_BROWSER"}
        return {"available": False, "reason": f"PUBCAST_RENDER_BROWSER does not name a file: {explicit}"}
    found = _bundled_headless_shell()
    if found:
        return {"available": True, "executable_path": str(found), "source": "PLAYWRIGHT_BROWSERS_PATH"}
    if sys.platform.startswith("win"):
        return {"available": True, "channel": "msedge", "source": "Microsoft Edge (installed with Windows)"}
    return {"available": True, "channel": None, "source": "Playwright's own Chromium"}


def _bundled_headless_shell() -> Optional[Path]:
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not root or not Path(root).is_dir():
        return None
    names = ("chrome-headless-shell.exe", "chrome-headless-shell") if sys.platform.startswith("win") else ("chrome-headless-shell",)
    for directory in sorted(Path(root).glob("chromium_headless_shell-*"), reverse=True):
        for name in names:
            for candidate in directory.rglob(name):
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return candidate
    return None


def _content_type(path: Path) -> str:
    return {".js": "text/javascript", ".mjs": "text/javascript", ".glb": "model/gltf-binary",
            ".html": "text/html", ".json": "application/json"}.get(path.suffix.lower()) \
        or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _serve_path(url_path: str) -> Optional[Path]:
    """The repository file for a render-host URL, never anything outside static/ or render_host/."""
    if url_path.startswith("/static/"):
        root, rel = STATIC_DIR, url_path[len("/static/"):]
    elif url_path.startswith("/__render__/"):
        root, rel = HOST_DIR, url_path[len("/__render__/"):]
    else:
        return None
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


class RenderHost:
    """One headless browser page running the studio's renderer. Use with ``async with``."""

    def __init__(self, browser: Optional[Dict[str, Any]] = None):
        self.browser_info = browser or find_browser()
        self._pw = None
        self._browser = None
        self.page = None
        self.version = None
        self.console: List[str] = []
        self.packages: Dict[str, Any] = {}
        self._prepared: Optional[str] = None

    async def __aenter__(self) -> "RenderHost":
        if not self.browser_info.get("available"):
            raise ReconstructionError(self.browser_info.get("reason") or "No browser for rendering")
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        try:
            options: Dict[str, Any] = {"headless": True, "args": BROWSER_ARGS}
            if self.browser_info.get("executable_path"):
                options["executable_path"] = self.browser_info["executable_path"]
            elif self.browser_info.get("channel"):
                options["channel"] = self.browser_info["channel"]
            try:
                self._browser = await self._pw.chromium.launch(**options)
            except Exception as exc:
                raise ReconstructionError(f"The rendering browser could not start ({self.browser_info.get('source')}): "
                                          f"{str(exc).splitlines()[0][:300]}") from exc
            self.version = self._browser.version
            context = await self._browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
            # No request leaves this machine: every URL is answered from the repository or refused.
            await context.route("**/*", self._answer)
            self.page = await context.new_page()
            self.page.on("console", lambda m: self.console.append(m.text)
                         if m.type in ("error", "warning") and "GL Driver Message" not in m.text else None)
            self.page.on("pageerror", lambda e: self.console.append(f"page error: {e}"))
            await self.page.goto(f"{ORIGIN}/__render__/reconstruct.html")
            await self.page.wait_for_function("document.documentElement.dataset.reconstruct==='ready'", timeout=30000)
            self.packages = await self.page.evaluate("PubCastReconstruct.packages()")
            return self
        except BaseException:
            await self.close()
            raise

    async def _answer(self, route) -> None:
        url = route.request.url
        if not url.startswith(ORIGIN + "/"):
            await route.abort()
            return
        path = _serve_path(url[len(ORIGIN):].split("?", 1)[0].split("#", 1)[0])
        if path is None:
            await route.fulfill(status=404, body="")
            return
        await route.fulfill(status=200, body=path.read_bytes(), headers={"content-type": _content_type(path)})

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        for closer in (getattr(self._browser, "close", None), getattr(self._pw, "stop", None)):
            if closer is None:
                continue
            try:
                await closer()
            except Exception:
                pass
        self._browser = self._pw = self.page = None

    async def prepare(self, stage: Dict[str, Any]) -> Dict[str, Any]:
        spec = {"package": stage.get("package"), "hologram": bool(stage.get("hologram")),
                "assets": stage.get("assets") or {},
                "performers": [{k: p[k] for k in ("id", "slot", "avatar", "avatar_url") if p.get(k) is not None}
                               for p in stage.get("performers") or []]}
        signature = json.dumps(spec, sort_keys=True)
        if signature == self._prepared:
            return {}
        report = await self.page.evaluate("s=>PubCastReconstruct.prepare(s)", spec)
        self._prepared = signature
        return report

    async def render(self, frames: List[Dict[str, Any]], *, fmt: str, quality: float) -> List[Dict[str, Any]]:
        return await self.page.evaluate("([f,o])=>PubCastReconstruct.renderFrames(f,o)",
                                        [frames, {"format": fmt, "quality": quality}])


# ---------------------------------------------------------------------------------------------------------
# Planning frames
# ---------------------------------------------------------------------------------------------------------
def shot_for(source_id: Optional[str], package: str, packages: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The 2.5D framing a switcher source id stands for in this package, or None if it is not one."""
    prefix = f"{STUDIO25D_PREFIX}{package}_"
    if not source_id or not source_id.startswith(prefix):
        return None
    shot_id = source_id[len(prefix):]
    for camera in packages.get(package, {}).get("cameras", []):
        if camera["id"] == shot_id:
            return {"center": list(camera["center"]), "zoom": camera["zoom"]}
    return None


def check_camera(camera: CameraSpec) -> CameraSpec:
    if camera == "program":
        return camera
    if isinstance(camera, str):
        if not camera.startswith(STUDIO25D_PREFIX) or len(camera) > 160:
            raise ReconstructionError("camera must be \"program\", a 2.5D camera id (p25d_<package>_<shot>) "
                                      "or a framing {\"center\": [x, y], \"zoom\": z}")
        return camera
    if isinstance(camera, dict) and set(camera) <= {"center", "zoom"}:
        center, zoom = camera.get("center"), camera.get("zoom")
        if (isinstance(center, list) and len(center) == 2
                and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1 for v in center)
                and isinstance(zoom, (int, float)) and not isinstance(zoom, bool) and 1 <= zoom <= 4):
            return {"center": [float(v) for v in center], "zoom": float(zoom)}
    raise ReconstructionError("a framing needs center [x, y] between 0 and 1 and zoom between 1 and 4")


@dataclass
class FramePlan:
    frames: int
    stretches: List[Dict[str, Any]]          # what each run of frames shows, for the manifest


def plan_frame(timeline: ShowTimeline, camera: CameraSpec, take_t: float, packages: Dict[str, Any]
               ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], str]:
    """(stage to draw or None, shot description, what it shows) for one moment of take time."""
    t = timeline.show_time(take_t)
    stage = timeline.stage_at(t)
    if stage is None:
        return None, {}, "black: no performer data yet"
    package = stage.get("package", "")
    if package not in packages:
        return None, {}, f"black: unknown production package {package}"
    if camera == "program":
        now, before, progress = timeline.program_at(t)
        shot = shot_for(now, package, packages)
        if shot is None:
            return None, {}, f"black: Program was on {now or 'no camera'}, which is not a 2.5D camera of {package}"
        frame_shot: Dict[str, Any] = {"shot": shot}
        if before is not None:
            from_shot = shot_for(before, package, packages)
            if from_shot is not None:
                # The outgoing camera stays underneath while the incoming one fades in over it.
                frame_shot = {"shot": from_shot, "mix_to": shot, "mix": round(progress, 4)}
                return stage, frame_shot, f"dissolve {before} -> {now}"
        return stage, frame_shot, f"camera {now}"
    if isinstance(camera, str):
        shot = shot_for(camera, package, packages)
        if shot is None:
            return None, {}, f"black: {camera} is not a camera of {package}"
        return stage, {"shot": shot}, f"camera {camera}"
    return stage, {"shot": dict(camera)}, f"framing center={camera['center']} zoom={camera['zoom']}"


# ---------------------------------------------------------------------------------------------------------
# Media checks
# ---------------------------------------------------------------------------------------------------------
def _ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def _ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")


def probe(path: Path) -> Dict[str, Any]:
    tool = _ffprobe()
    if not tool:
        return {"ok": False, "error": "ffprobe is not installed"}
    run = subprocess.run([tool, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        return {"ok": False, "error": run.stderr.strip()[:500]}
    info = json.loads(run.stdout or "{}")
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {"ok": True, "duration": float(info.get("format", {}).get("duration") or 0.0),
            "video": None if not video else {"codec": video.get("codec_name"), "width": video.get("width"),
                                             "height": video.get("height"), "frame_rate": video.get("avg_frame_rate"),
                                             "frames": int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else None},
            "audio": None if not audio else {"codec": audio.get("codec_name"), "sample_rate": audio.get("sample_rate"),
                                             "channels": audio.get("channels"),
                                             "duration": float(audio.get("duration") or 0.0)}}


def decode_check(path: Path) -> Dict[str, Any]:
    """Decode every frame and sample; any decoder error fails the file."""
    tool = _ffmpeg()
    if not tool:
        return {"ok": False, "error": "ffmpeg is not installed"}
    run = subprocess.run([tool, "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"],
                         capture_output=True, text=True, timeout=3600)
    errors = run.stderr.strip()
    return {"ok": run.returncode == 0 and not errors, "errors": errors[:1000]}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class SoundTrack:
    path: Path
    timing: List[Dict[str, Any]]          # the capture engine's pieces, wall clock; empty for older takes
    source_id: Optional[str] = None       # the camera or input it came from ("microphone" for the take's mic)


def take_sound(take_dir: Path) -> List[SoundTrack]:
    """The take's own sound files, as its mode record lists them (microphone first), with each one's timing."""
    record_path = take_dir / MODE_RECORD_FILE
    if not record_path.is_file():
        return []
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = [{**(record.get("microphone") or {}), "source_id": "microphone"}] + list(record.get("sound") or [])
    out: List[SoundTrack] = []
    for entry in entries:
        name = entry.get("file")
        if not name:
            continue
        path = take_dir / Path(name).name
        if path.is_file() and path.stat().st_size > 44 and all(t.path != path for t in out):
            out.append(SoundTrack(path, list((entry.get("report") or {}).get("timing") or []), entry.get("source_id")))
    return out


def sound_placement(track: SoundTrack, timeline: ShowTimeline) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Where each piece of a joined sound file goes on take time: [{"from", "length", "at"}], and a note.

    The joined file is the pieces end to end; each piece is cut back out by its measured length and placed at
    the moment its first sample was recorded, with the pauses taken out. Silence fills any gap (the moment a
    microphone takes to start, or to come back after a pause), so the sound stays with the picture.
    """
    origin = float(timeline.header.get("utc_origin") or 0.0)
    pieces = [t for t in track.timing if t.get("media_seconds")]
    if not origin or not pieces or len(pieces) != len(track.timing):
        return [{"from": 0.0, "length": None, "at": 0.0}], \
            f"{track.path.name}: no piece timing in the take record (an older take), so it is placed at the take start"
    placed, offset = [], 0.0
    for piece in pieces:
        show_t = float(piece["start"]) - origin
        take_t = show_t - sum(min(b, show_t) - a for a, b in timeline.pauses if a < show_t)
        placed.append({"from": round(offset, 6), "length": float(piece["media_seconds"]), "at": round(max(0.0, take_t), 6),
                       "ended_early": bool(piece.get("ended_early"))})
        offset += float(piece["media_seconds"])
    return placed, None


# ---------------------------------------------------------------------------------------------------------
# One reconstruction
# ---------------------------------------------------------------------------------------------------------
@dataclass
class Request:
    camera: CameraSpec = "program"
    fps: int = 30
    quality: str = "standard"
    audio: str = "take"                 # "take" (its microphone and camera sound, mixed) or "none"
    label: str = ""

    def checked(self) -> "Request":
        camera = check_camera(self.camera)
        if self.fps not in FPS_CHOICES:
            raise ReconstructionError(f"fps must be one of {FPS_CHOICES}")
        if self.quality not in QUALITY:
            raise ReconstructionError(f"quality must be one of {tuple(QUALITY)}")
        if self.audio not in ("take", "none"):
            raise ReconstructionError("audio must be \"take\" or \"none\"")
        label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(self.label or ""))[:40]
        return Request(camera, self.fps, self.quality, self.audio, label)

    def slug(self) -> str:
        if self.label:
            return self.label
        if self.camera == "program":
            return "program"
        if isinstance(self.camera, str):
            return self.camera
        return "framing"


async def reconstruct(take_dir: Path, request: Request, *, progress: Optional[Callable[[Dict[str, Any]], None]] = None,
                      cancelled: Optional[Callable[[], bool]] = None, browser: Optional[Dict[str, Any]] = None
                      ) -> Dict[str, Any]:
    """Render one take from its show data. Returns the manifest (also written beside the video)."""
    request = request.checked()
    show = take_dir / SHOW_DATA_FILE
    if not show.is_file():
        raise ReconstructionError("This take has no show data, so it cannot be reconstructed "
                                  "(it was recorded with record_data off, or before show data existed)")
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise ReconstructionError("FFmpeg is not installed, so nothing can be encoded")
    timeline = ShowTimeline.read(show)
    if not timeline.stages:
        raise ReconstructionError("This take has no performer data (no performance frames were sent while it "
                                  "recorded), so there is nothing to draw")
    duration = timeline.duration
    fps = request.fps
    total = int(math.floor(duration * fps + 1e-6))
    if total < 1:
        raise ReconstructionError("The take is shorter than one frame")
    settings = QUALITY[request.quality]
    sound = take_sound(take_dir) if request.audio == "take" else []

    stem = f"reconstruct_{request.slug()}"
    final = _unique(take_dir, stem, ".mp4")
    partial = take_dir / f".{final.stem}.{uuid.uuid4().hex[:8]}.partial.mp4"
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n",
           "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg" if settings["format"] == "jpeg" else "png",
           "-i", "pipe:0"]
    placements: List[Dict[str, Any]] = []
    sound_notes: List[str] = []
    graph: List[str] = []
    labels: List[str] = []
    for i, track in enumerate(sound):
        cmd += ["-i", str(track.path)]
        placed, note = sound_placement(track, timeline)
        if note:
            sound_notes.append(note)
        placements.append({"file": track.path.name, "pieces": placed})
        steps = timeline.gain_steps(track.source_id)
        volume = ""
        if steps is not None:
            # The intended Program mix: this source's channel level, step by step, on take time (the delayed
            # stream's own clock starts at the take's start). g0 + (g1-g0)*gte(t,t1) + ...
            expr = f"{steps[0][1]:.6f}" + "".join(f"+({g - steps[n][1]:.6f})*gte(t,{t:.6f})"
                                                  for n, (t, g) in enumerate(steps[1:]) if g != steps[n][1])
            volume = f",volume='{expr}':eval=frame"
        placements[-1]["mix"] = None if steps is None else [{"at": round(t, 4), "gain": round(g, 6)} for t, g in steps]
        if steps is None:
            sound_notes.append(f"{track.path.name}: no Program channel names {track.source_id}, so it is at full level")
        for k, piece in enumerate(placed):
            label = f"s{i}_{k}"
            trim = f"atrim=start={piece['from']:.6f}" + (f":duration={piece['length']:.6f}" if piece["length"] else "")
            delay = int(round(piece["at"] * 1000))
            graph.append(f"[{i + 1}:a]{trim},asetpts=PTS-STARTPTS,aresample=48000,adelay={delay}:all=1{volume}[{label}]")
            labels.append(f"[{label}]")
    if labels:
        # The placed pieces are mixed over silence exactly as long as the take, and the mix takes the silence's length:
        # never shorter (a source that stopped early) and never longer. (An open-ended apad after a mix of delayed
        # pieces never ends in FFmpeg 6.1; reproduced 2026-11-26.)
        graph.append(f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={duration:.6f}[bed]")
        graph.append("[bed]" + "".join(labels) +
                     f"amix=inputs={len(labels) + 1}:normalize=0:duration=first:dropout_transition=0[a]")
        cmd += ["-filter_complex", ";".join(graph), "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-c:v", "libx264", "-preset", settings["preset"], "-crf", str(settings["crf"]), "-pix_fmt", "yuv420p",
            "-r", str(fps), "-frames:v", str(total), "-movflags", "+faststart", str(partial)]

    stretches: List[Dict[str, Any]] = []
    frame_notes: Dict[str, int] = {}
    started = time.monotonic()
    encoder = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    host_report: Dict[str, Any] = {}
    gesture_i = 0
    gestures = sorted(timeline.gestures, key=lambda g: g[0])
    try:
        async with RenderHost(browser) as host:
            host_report = {"browser": host.version, "browser_source": host.browser_info.get("source")}
            prepared: List[Dict[str, Any]] = []
            i = 0
            prev_show_t = -1.0
            while i < total:
                if cancelled and cancelled():
                    raise ReconstructionError("Cancelled")
                batch: List[Dict[str, Any]] = []
                batch_stage: Optional[str] = None
                while i < total and len(batch) < BATCH:
                    take_t = i / fps
                    stage, shot, what = plan_frame(timeline, request.camera, take_t, host.packages)
                    show_t = timeline.show_time(take_t)
                    if stage is not None:
                        key = json.dumps({k: stage.get(k) for k in ("package", "assets", "hologram")}, sort_keys=True) + \
                              json.dumps([(p.get("id"), p.get("avatar"), p.get("avatar_url")) for p in stage.get("performers", [])])
                        if batch_stage is not None and key != batch_stage:
                            break        # the cast or set changes: draw what we have, then load the new one
                        if batch_stage is None:
                            batch_stage = key
                            report = await host.prepare(stage)
                            if report:
                                prepared.append({"at": round(take_t, 3), **report})
                    fired = []
                    while gesture_i < len(gestures) and gestures[gesture_i][0] <= show_t:
                        if gestures[gesture_i][0] > prev_show_t or i == 0:
                            fired.append(gestures[gesture_i][1])
                        gesture_i += 1
                    prev_show_t = show_t
                    scene = stage if stage is not None else {"performers": [], "blackout": True}
                    blank_shot = {"shot": {"center": [0.5, 0.5], "zoom": 1}}
                    batch.append({"stamp": i, "dt": 0 if i == 0 else 1 / fps, "scene": scene,
                                  "gestures": fired if stage is not None else [], **(shot or blank_shot)})
                    if not stretches or stretches[-1]["shows"] != what:
                        stretches.append({"from": round(take_t, 4), "to": None, "shows": what})
                    stretches[-1]["to"] = round((i + 1) / fps, 4)
                    i += 1
                if not batch:
                    continue
                if batch_stage is None and host._prepared is None:
                    # Nothing to draw yet and nothing loaded: the renderer still needs a set to paint black over.
                    first = timeline.stages[0]
                    await host.prepare({**first, "performers": []})
                results = await host.render(batch, fmt=settings["format"], quality=settings["quality"])
                for result in results:
                    if result.get("error"):
                        raise ReconstructionError(f"Frame {result.get('stamp')} could not be drawn: {result['error']}")
                    for note in result.get("notes") or []:
                        frame_notes[note] = frame_notes.get(note, 0) + 1
                    encoder.stdin.write(base64.b64decode(result["data"]))
                await encoder.stdin.drain()
                if progress:
                    progress({"frames_done": i, "frames_total": total,
                              "seconds": round(time.monotonic() - started, 1)})
            host_report["console"] = host.console[-20:]
            host_report["prepared"] = prepared
        encoder.stdin.close()
        stderr = (await encoder.stderr.read()).decode("utf-8", "replace")
        code = await encoder.wait()
        if code != 0:
            raise ReconstructionError(f"FFmpeg could not encode the reconstruction: {stderr.strip()[:500]}")
    except BaseException:
        if encoder.returncode is None:
            encoder.kill()
            await encoder.wait()
        partial.unlink(missing_ok=True)
        raise

    info = probe(partial)
    decoded = decode_check(partial)
    expected = total / fps
    problems = []
    if not info.get("ok"):
        problems.append(f"ffprobe could not read the file: {info.get('error')}")
    else:
        if not info.get("video") or info["video"]["codec"] != "h264":
            problems.append("no H.264 picture in the file")
        if abs(info["duration"] - expected) > max(2.0 / fps, 0.1):
            problems.append(f"length {info['duration']:.3f}s, expected {expected:.3f}s")
        if sound and not info.get("audio"):
            problems.append("the take's sound is missing from the file")
    if not decoded["ok"]:
        problems.append(f"the file does not decode cleanly: {decoded['errors'][:300]}")
    if problems:
        bad = take_dir / f".{final.stem}.rejected.mp4"
        os.replace(partial, bad)
        raise ReconstructionError("The reconstruction failed its checks and was not added to the take: " + "; ".join(problems))
    try:
        os.link(partial, final)              # never replaces a file that already exists
        partial.unlink()
    except OSError:
        if final.exists():
            raise ReconstructionError(f"{final.name} appeared while rendering; nothing was overwritten")
        os.replace(partial, final)

    for s in stretches:
        if s["shows"].startswith("black"):
            s["black"] = True
    manifest = {
        "schema": SCHEMA, "file": final.name, "sha256": _sha256(final), "made_utc": time.time(),
        "request": {"camera": request.camera, "fps": fps, "quality": request.quality, "audio": request.audio},
        "take": {"session_id": timeline.header.get("session_id"), "mode": timeline.header.get("mode"),
                 "show_data": show.name, "show_data_sha256": _sha256(show), "show_data_complete": timeline.complete,
                 "duration": round(duration, 4), "paused_seconds": round(timeline.paused_seconds, 4),
                 "performance_frames": len(timeline.stages), "cuts": len(timeline.cuts) - 1,
                 "gestures": len(timeline.gestures)},
        "frames": total, "expected_seconds": round(expected, 4),
        "stretches": stretches, "frame_notes": frame_notes, "notes": timeline.notes,
        "sound": [{"file": t.path.name, "sha256": _sha256(t.path),
                   "source_id": t.source_id,
                   "placement": next((p["pieces"] for p in placements if p["file"] == t.path.name), []),
                   "mix": next((p.get("mix") for p in placements if p["file"] == t.path.name), None)} for t in sound],
        "sound_notes": sound_notes,
        "renderer": {**host_report, "files": {name: _sha256(REPO / name) for name in RENDERER_FILES}},
        "verification": {"ffprobe": info, "decode": decoded},
        "render_seconds": round(time.monotonic() - started, 2),
    }
    manifest_path = take_dir / f"{final.stem}.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, default=str)
    return manifest


def _unique(directory: Path, stem: str, suffix: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in stem)[:80]
    n = 1
    while True:
        candidate = directory / f"{safe}_{n:03d}{suffix}"
        if not candidate.exists() and not (directory / f"{safe}_{n:03d}.json").exists():
            return candidate
        n += 1


__all__ = ["ShowTimeline", "RenderHost", "Request", "ReconstructionError", "reconstruct", "find_browser",
           "check_camera", "plan_frame", "probe", "decode_check", "take_sound", "sound_placement", "SoundTrack"]
