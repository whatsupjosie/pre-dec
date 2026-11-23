# PubCast AI — recording_modes.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""The three ways a take records picture.

Josie, 2026-11-22: "I want to be able to record all three ways." In her words:

* **camcorder** — "record traditionally, same way you would with a camcorder. You hit record, you tape it, and you
  record everything that just goes on in front of the camera. And you hear everything that goes on in front of the
  camera or wherever the mics are laid up." Every camera chosen for the take records picture and sound for the whole
  take. This is what ``modules/capture.py`` already did; the mode only adds the show-data record.
* **data_only** — "the data only option". No picture is recorded. The take keeps the show data (every camera move and
  cut, every motion and choreography frame, every studio action and audio cue the stage receives) and the sound of
  every chosen source and the microphone, for the whole take. Turning that data back into pictures later needs a
  renderer that can replay it; that is engine work and is not part of this module.
* **main_camera** — "the only render, you know, what's actually recorded option": "when we cut to camera 2, camera 2
  is now being recorded. But when we cut back to camera 1, now we're recording camera 1." Only the camera on the live
  screen (the switcher's program) records picture. At each cut the new camera starts and the old one stops once the
  new one is delivering frames, so nothing is missing between them. When the take stops, the pieces are joined into
  one program file. Sound of every chosen source and the microphone records for the whole take.

Under all three, unless a take turns it off, the **show-data record** runs: a compressed JSON Lines file
(``show_data.jsonl.gz``) written as the take happens and flushed every second, so a crash loses at most the last
second. Its footer holds the event count and a SHA-256 of every line before it.

Privacy follows the rules the recorder already enforces for cameras (``RecordingService.room_policy``): a camera in a
place where recording is "never" (the dressing room) or "with_permission" (the green room) is not recorded without the
host override, whether it is cut to or chosen at the start. Room messages enter the show data only from rooms the
privacy table names and allows; private message rooms and presence lists never do.

What each take did is kept in ``recording_mode.json`` beside it: the mode, every cut as asked for and as it took
effect (how late, in milliseconds), every piece of picture and why any stretch has none, the sound tracks, the
show-data summary, and the program join. Both files travel with the take on export and import.

Choosing between the cameras' own sound and a separate microphone is already handled by the recorder: in camcorder
mode the microphone goes with the first camera (``FFmpegCaptureEngine.start``); in the other two it is its own track.
"""
from __future__ import annotations

import asyncio
import dataclasses
import gzip
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .persistence import write_json

logger = logging.getLogger("pubcast.recording_modes")

MODES: Dict[str, str] = {
    "camcorder": "Every chosen camera records picture and sound for the whole take.",
    "data_only": "No picture. The show data and every sound source record for the whole take.",
    "main_camera": "Only the camera on the live screen records picture; each cut switches which camera records. "
                   "Every sound source records for the whole take. The pieces are joined into one program file.",
}
SHOW_DATA_FILE = "show_data.jsonl.gz"
SHOW_DATA_SCHEMA = "pubcast-show-data/1"
MODE_RECORD_FILE = "recording_mode.json"
MODE_RECORD_SCHEMA = "pubcast-recording-mode/1"
PROGRAM_STEM = "program"
SOUND_PROFILE_ID = "audio_only"
FLUSH_SECONDS = 1.0
FIRST_FRAME_WAIT_SECONDS = 15.0      # how long a camera that was cut to may take to deliver its first frame
_PRIVATE_ROOM_PREFIXES = ("dm____", "dmv2_")
_NO_SOUND_TRANSPORTS = {"virtual", "webcam", "voxel_3d"}
_NO_AUDIO_STREAM = re.compile(r"does not contain any stream|matches no streams|Output file #0 does not contain", re.I)


class ModeRequestError(ValueError):
    """A recording request asks for something its mode cannot do."""


# ── Request validation ─────────────────────────────────────────────────────────────────────────────────────────
def _is_listener(camera) -> bool:
    try:
        from .capture import _is_listener as capture_is_listener
    except Exception:  # pragma: no cover - capture.py always ships with this module
        return False
    return camera.transport.value in ("rtmp", "srt") and capture_is_listener(str(camera.endpoint))


def validate_mode_request(recording, mode: Any, sources: List[str], profile_id: str, *,
                          record_data: Any = True, host_override: bool = False) -> str:
    """Return the normalised mode, or raise ``ModeRequestError`` saying plainly why the request cannot run."""
    name = str(mode if mode is not None else "camcorder").strip().lower()
    if name not in MODES:
        raise ModeRequestError(f"Unknown recording mode {mode!r}; use one of: {', '.join(MODES)}")
    if not isinstance(record_data, bool):
        raise ModeRequestError("record_data must be true or false")
    if name == "data_only" and not record_data:
        raise ModeRequestError("Data only records the show data; it cannot run with record_data false")
    cameras = recording.cameras
    if name == "main_camera":
        program = cameras.get_program_source()
        if program is None:
            raise ModeRequestError("Main camera only records the camera on the live screen, and no program camera is set")
        if program.source_id not in sources:
            raise ModeRequestError(f"The camera on the live screen ({program.source_id}) is not one of this take's cameras")
        profile = recording.get_profile(profile_id)     # an unknown profile is a KeyError, as before
        if profile.is_audio_only or not profile.video_codec:
            raise ModeRequestError(f"Main camera only records picture; profile '{profile_id}' has none")
        for source_id in sources:
            camera = cameras.get(source_id)
            if camera is not None and _is_listener(camera):
                raise ModeRequestError(
                    f"Camera '{source_id}' waits for its sender to connect, so it cannot be switched in and out of a "
                    "take. Record it in camcorder mode.")
    if name in ("data_only", "main_camera") and sources:
        try:
            recording.get_profile(SOUND_PROFILE_ID)
        except KeyError:
            raise ModeRequestError(f"Recording sound on its own needs the '{SOUND_PROFILE_ID}' profile, which is not registered")
    return name


def default_sources(recording, mode: str) -> List[str]:
    """Cameras a take uses when none were named. Main camera only may cut to any camera the rules allow."""
    cameras = recording.cameras
    program = cameras.get_program_source()
    if mode != "main_camera":
        return [program.source_id] if program is not None else []
    chosen: List[str] = []
    for camera in cameras.list_sources():
        try:
            recording._validate_sources([camera.source_id], host_override=False)
        except (PermissionError, ValueError):
            continue
        if _is_listener(camera):
            continue
        chosen.append(camera.source_id)
    if program is not None and program.source_id in chosen:
        chosen.remove(program.source_id)
        chosen.insert(0, program.source_id)
    return chosen


# ── Show data ──────────────────────────────────────────────────────────────────────────────────────────────────
def _json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float)):
        return value.value
    return str(value)


def _line(obj: Dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=_json_default) + "\n").encode("utf-8")


class ShowDataRecorder:
    """Append-only, crash-tolerant record of everything the stage received during a take."""

    def __init__(self, path: Path, header: Dict[str, Any], *, flush_seconds: float = FLUSH_SECONDS):
        self.path = Path(path)
        self._header = header
        self._flush_seconds = flush_seconds
        self._lock = threading.Lock()
        self._raw = None
        self._gz: Optional[gzip.GzipFile] = None
        self._digest = hashlib.sha256()
        self._t0 = 0.0
        self._last_flush = 0.0
        self.events = 0
        self.raw_bytes = 0
        self.error: Optional[str] = None
        self.closed = False
        self.summary: Dict[str, Any] = {}

    def open(self) -> None:
        raw = open(self.path, "xb")       # a take never overwrites another take's data
        self._raw = raw
        self._gz = gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0)
        self._t0 = time.monotonic()
        header = {"schema": SHOW_DATA_SCHEMA, "header": True, "utc_origin": time.time(), **self._header}
        with self._lock:
            self._write(header)
            self._flush()

    def record(self, kind: str, data: Any, *, room: Optional[str] = None) -> None:
        with self._lock:
            if self.closed or self.error or self._gz is None:
                return
            entry: Dict[str, Any] = {"seq": self.events, "t": round(time.monotonic() - self._t0, 6),
                                     "utc": time.time(), "kind": kind}
            if room is not None:
                entry["room"] = room
            entry["data"] = data
            if self._write(entry):
                self.events += 1
                if time.monotonic() - self._last_flush >= self._flush_seconds:
                    self._flush()

    def _write(self, obj: Dict[str, Any]) -> bool:
        try:
            data = _line(obj)
            self._gz.write(data)
        except (OSError, ValueError, TypeError) as exc:
            self.error = f"show data could not be written: {exc}"
            logger.error("%s (%s)", self.error, self.path)
            return False
        self._digest.update(data)
        self.raw_bytes += len(data)
        return True

    def _flush(self) -> None:
        try:
            self._gz.flush()          # a sync flush: everything so far can be decompressed after a crash
            self._raw.flush()
        except (OSError, ValueError) as exc:
            self.error = f"show data could not be flushed: {exc}"
            logger.error("%s (%s)", self.error, self.path)
        self._last_flush = time.monotonic()

    def close(self) -> Dict[str, Any]:
        with self._lock:
            if self.closed:
                return self.summary
            self.closed = True
            sha = self._digest.hexdigest()
            if self._gz is not None and not self.error:
                footer = {"footer": True, "events": self.events, "sha256": sha, "closed_utc": time.time()}
                try:
                    self._gz.write(_line(footer))
                except (OSError, ValueError) as exc:
                    self.error = f"show data footer could not be written: {exc}"
            for closer in (getattr(self._gz, "close", None), getattr(self._raw, "flush", None)):
                try:
                    if closer:
                        closer()
                except (OSError, ValueError) as exc:
                    self.error = self.error or f"show data could not be closed: {exc}"
            if self._raw is not None:
                try:
                    os.fsync(self._raw.fileno())
                except (OSError, ValueError):
                    pass
                try:
                    self._raw.close()
                except OSError:
                    pass
            size = self.path.stat().st_size if self.path.exists() else 0
            self.summary = {"file": self.path.name, "events": self.events, "uncompressed_bytes": self.raw_bytes,
                            "bytes": size, "sha256": sha, "complete": not self.error, "error": self.error}
            return self.summary


def iter_show_data(path: Path) -> Iterator[Dict[str, Any]]:
    """Every whole line of a show-data file, header first, footer last if the take closed it.

    A file cut short by a crash yields every line up to the last one it holds in full; it never raises for a
    truncated tail, only for lines that are not JSON.
    """
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    pending = b""
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            try:
                pending += decoder.decompress(block)
            except zlib.error:
                break
            *lines, pending = pending.split(b"\n")
            for raw in lines:
                if raw:
                    yield json.loads(raw)
    # A trailing partial line (no newline) is the unfinished write a crash cut off: it is not a record.


def verify_show_data(path: Path) -> Dict[str, Any]:
    """Count the events, and check the footer's hash against the lines actually in the file."""
    digest = hashlib.sha256()
    header: Optional[Dict[str, Any]] = None
    footer: Optional[Dict[str, Any]] = None
    events = 0
    kinds: Dict[str, int] = {}
    for obj in iter_show_data(path):
        if obj.get("footer"):
            footer = obj
            break
        digest.update(_line(obj))
        if obj.get("header"):
            header = obj
            continue
        events += 1
        kinds[obj.get("kind", "?")] = kinds.get(obj.get("kind", "?"), 0) + 1
    result = {"header": header, "events": events, "kinds": kinds, "closed": footer is not None}
    if footer is not None:
        result["verified"] = footer.get("sha256") == digest.hexdigest() and footer.get("events") == events
    else:
        result["verified"] = False
    return result


def room_is_recordable(recording, room: Optional[str], *, host_override: bool) -> bool:
    """Room messages enter the show data only from rooms the privacy table names and allows."""
    if not room or room.startswith(_PRIVATE_ROOM_PREFIXES):
        return False
    policy = recording.privacy_matrix().get(room)
    if not isinstance(policy, dict):
        return False
    rule = str(policy.get("recording") or "allowed")
    if rule in ("never", "with_permission"):
        return bool(host_override)
    return True


# ── Program (main camera only) ─────────────────────────────────────────────────────────────────────────────────
@dataclass
class Segment:
    """One stretch of one camera's picture, in its own file."""
    index: int
    source_id: str
    key: str
    file: Path
    synthetic: bool
    spawned_at: float
    state: str = "starting"              # starting / running / failed / stopped
    stop_requested_at: Optional[float] = None
    duration: Optional[float] = None
    has_audio: bool = False
    # Wall time that the file's own time zero stands for: the stop request minus the file's length. A file camera
    # reads its first half-second at once (FFmpeg's -re burst), so this can fall just before the segment started.
    media_offset: Optional[float] = None
    # When this camera's picture was there to be shown: never before the segment was started.
    first_frame_at: Optional[float] = None
    report: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    roles: List[Tuple[str, float]] = field(default_factory=list)

    def to_dict(self, t0: float) -> Dict[str, Any]:
        rel = lambda value: None if value is None else round(value - t0, 4)
        return {"index": self.index, "source_id": self.source_id, "file": self.file.name, "synthetic": self.synthetic,
                "state": self.state, "spawned_at": rel(self.spawned_at), "stopped_at": rel(self.stop_requested_at),
                "media_offset": rel(self.media_offset), "first_frame_at": rel(self.first_frame_at),
                "duration": self.duration, "has_audio": self.has_audio,
                "roles": [{"role": role, "at": rel(at)} for role, at in self.roles], "error": self.error,
                "report": self.report}


@dataclass
class Interval:
    """What was on the live screen for a stretch of the take: a camera's segment, or nothing and why."""
    source_id: Optional[str]
    segment: Optional[int]
    reason: str                          # program / private / not_in_take / failed_to_start / no_capture_engine
    start: Optional[float] = None        # wall time, or None: the first frame of ``start_ref``
    start_ref: Optional[int] = None
    end: Optional[float] = None
    end_ref: Optional[int] = None


def plan_program(intervals: List[Interval], segments: Dict[int, Segment], *, frame: float) -> Tuple[float, List[Dict[str, Any]]]:
    """Turn what was on the live screen into pieces of files: ``(origin, pieces)``.

    Each piece is ``{"kind": "segment", "segment": i, "in": s, "out": e}`` (seconds into that segment's file) or
    ``{"kind": "black", "duration": d}``. ``origin`` is the wall time at which the program starts. A stretch the file
    does not cover (it started late or ended early) becomes black of exactly that length, so the program keeps real
    time and stays in step with the sound tracks. Pieces shorter than one frame are dropped.
    """
    def resolve(value: Optional[float], ref: Optional[int]) -> Optional[float]:
        if value is not None:
            return value
        seg = segments.get(ref) if ref is not None else None
        return seg.first_frame_at if seg is not None else None

    resolved: List[Tuple[Interval, float, float]] = []
    for interval in intervals:
        start = resolve(interval.start, interval.start_ref)
        end = resolve(interval.end, interval.end_ref)
        if start is None or end is None:
            continue
        if resolved and start < resolved[-1][2]:
            start = resolved[-1][2]           # never overlap the stretch before
        if end - start >= frame:
            resolved.append((interval, start, end))
    if not resolved:
        return 0.0, []
    origin = resolved[0][1]
    pieces: List[Dict[str, Any]] = []

    def black(duration: float) -> None:
        if duration >= frame:
            pieces.append({"kind": "black", "duration": round(duration, 6)})

    cursor = origin
    for interval, start, end in resolved:
        black(start - cursor)                 # a hole between stretches is shown as black, not skipped
        seg = segments.get(interval.segment) if interval.segment is not None else None
        offset = None if seg is None else (seg.media_offset if seg.media_offset is not None else seg.first_frame_at)
        if seg is None or offset is None or not seg.duration:
            black(end - start)
        else:
            media_in = start - offset
            media_out = end - offset
            if media_in < 0:
                black(-media_in)
                media_in = 0.0
            tail = 0.0
            if media_out > seg.duration:
                tail = media_out - seg.duration
                media_out = seg.duration
            if media_out - media_in >= frame:
                pieces.append({"kind": "segment", "segment": seg.index, "in": round(media_in, 6), "out": round(media_out, 6)})
            black(tail)
        cursor = end
    return origin, pieces


def _piece_duration(piece: Dict[str, Any]) -> float:
    return piece["duration"] if piece["kind"] == "black" else piece["out"] - piece["in"]


def _ffprobe_bin() -> Optional[str]:
    return shutil.which(os.environ.get("PUBCAST_FFPROBE", "") or "ffprobe")


def probe_media(path: Path) -> Dict[str, Any]:
    """Duration and streams of a file, from ffprobe. Empty when it cannot be read."""
    probe = _ffprobe_bin()
    if not probe or not path.is_file() or path.stat().st_size == 0:
        return {}
    try:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json",
                              str(path)], capture_output=True, timeout=60, check=True).stdout
        data = json.loads(out)
    except (subprocess.SubprocessError, OSError, ValueError):
        return {}
    kinds = [s.get("codec_type") for s in data.get("streams", [])]
    try:
        duration = float(data.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        duration = None
    return {"duration": duration, "video": "video" in kinds, "audio": "audio" in kinds}


# ── One take's recording mode ──────────────────────────────────────────────────────────────────────────────────
class ModeTake:
    """Runs one take's mode from the moment it goes live until it stops."""

    def __init__(self, controller: "RecordingModeController", session, *, audio_input=None, arm_preview: bool = False,
                 sources_named: bool = True):
        self.controller = controller
        self.session = session
        self.session_id = session.session_id
        self.mode = session.mode
        self.arm_preview = bool(arm_preview) and self.mode == "main_camera"
        self.audio_input = audio_input
        # False when the take was given every eligible camera by default: a camera nobody named that cannot be opened
        # for sound is then a note, not an error at the start of the take.
        self.sources_named = bool(sources_named)
        self.dir = controller.recording._session_dir(self.session_id)
        self.t0 = time.time()
        self.stopped_at: Optional[float] = None
        self.data: Optional[ShowDataRecorder] = None
        self.segments: Dict[int, Segment] = {}
        self.intervals: List[Interval] = []
        self.cuts: List[Dict[str, Any]] = []
        self.sound: List[Dict[str, Any]] = []
        self.microphone: Optional[Dict[str, Any]] = None
        self.assembly: Dict[str, Any] = {"state": "not_applicable" if self.mode != "main_camera" else "waiting"}
        self.state = "recording"
        self.notes: List[str] = []
        self.rooms_recorded: set = set()
        self.rooms_excluded: set = set()
        self._program: Optional[int] = None      # index of the segment on the live screen
        self._preview: Optional[int] = None      # index of the armed preview segment
        self._queue: "asyncio.Queue" = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        self._worker: Optional[asyncio.Task] = None
        self._next_index = 1

    # -- start ---------------------------------------------------------------------------------------------
    async def begin(self) -> List[str]:
        paths: List[str] = []
        self._write_record()
        self.controller.recording.attach_data_file(self.session_id, self.dir / MODE_RECORD_FILE)
        if self.session.record_data:
            self._open_data()
        # Picture and every sound track start together: each FFmpeg start waits a moment to see that it is
        # running, and one after another they would leave the first seconds of the take unrecorded.
        jobs = []
        if self.mode == "main_camera":
            jobs.append(self._start_program())
        if self.mode in ("data_only", "main_camera"):
            jobs.append(self._start_sound())
        for result in await asyncio.gather(*jobs):
            paths += result
        if self.mode == "main_camera":
            self._worker = asyncio.create_task(self._work(), name=f"recording-mode-{self.session_id}")
            self._worker.add_done_callback(_report_task_failure)
        self._write_record()
        return paths

    def _open_data(self) -> None:
        cameras = self.controller.cameras
        program = cameras.get_program_source()
        preview = cameras.get_preview_source()
        header = {
            "session_id": self.session_id, "mode": self.mode, "take_started_utc": self.t0,
            "profile_id": self.session.profile_id, "sources": list(self.session.sources),
            "program": program.source_id if program else None, "preview": preview.source_id if preview else None,
            # Where every camera stood when the take began. Endpoints are left out: they can hold stream keys.
            "cameras": [{"source_id": c.source_id, "name": c.name, "location": c.location, "transport": c.transport.value,
                         "position": list(c.position), "rotation": list(c.rotation), "fov": c.fov,
                         "focus": getattr(c, "focus", None), "tags": list(c.tags)} for c in cameras.list_sources()],
            "privacy": self.controller.recording.privacy_matrix(),
            "clock": "t is seconds on a monotonic clock from the header; utc is wall time",
        }
        recorder = ShowDataRecorder(self.dir / SHOW_DATA_FILE, header)
        try:
            recorder.open()
        except OSError as exc:
            self.notes.append(f"Show data could not be started: {exc}")
            logger.error("Show data for %s could not be started: %s", self.session_id, exc)
            return
        self.data = recorder
        self.controller.recording.attach_data_file(self.session_id, recorder.path)

    async def _start_sound(self) -> List[str]:
        """Sound of every chosen source, and the microphone, for the whole take."""
        engine = self.controller.capture_engine
        paths: List[str] = []
        if engine is None or not getattr(engine, "available", False):
            if self.session.sources or self.audio_input is not None:
                self.notes.append("FFmpeg is not available: no sound is being recorded")
            return paths
        profile = self.controller.recording.get_profile(SOUND_PROFILE_ID)
        cameras = self.controller.cameras

        async def one(source_id: str) -> Optional[str]:
            camera = cameras.get(source_id)
            entry: Dict[str, Any] = {"source_id": source_id, "file": None, "state": "skipped", "note": None}
            self.sound.append(entry)
            if camera is None:
                entry["note"] = "camera is no longer registered"
                return None
            if camera.transport.value in _NO_SOUND_TRANSPORTS:
                entry["note"] = f"a {camera.transport.value} camera carries no sound"
                return None
            if not camera.audio_enabled:
                entry["note"] = "sound is turned off for this camera"
                return None
            if camera.transport.value == "file":
                info = await asyncio.to_thread(probe_media, Path(str(camera.endpoint)))
                if info and not info.get("audio"):
                    entry["note"] = "this file has no sound"
                    return None
            key = f"{self.session_id}~sound~{source_id}"
            source = dataclasses.replace(camera, source_id="sound_" + re.sub(r"[^A-Za-z0-9._-]", "_", source_id))
            out = await engine.start(key, [source], profile, self.dir)
            failures = engine.startup_failures(key) if hasattr(engine, "startup_failures") else []
            if failures:
                text = " ".join(str(f.get("error", "")) for f in failures)
                silent = bool(_NO_AUDIO_STREAM.search(text))
                entry.update(state="none" if silent else ("failed" if self.sources_named else "unavailable"),
                             note="this source has no sound" if silent else text[:400])
                await engine.stop(key)
                if not silent and not self.sources_named:
                    self.notes.append(f"Sound of {source_id} could not be opened, so it is not recorded: {text[:200]}")
                return None
            if out:
                entry.update(state="recording", file=Path(out[0]).name, key=key)
                return str(out[0])
            return None

        async def microphone() -> Optional[str]:
            key = f"{self.session_id}~microphone"
            out = await engine.start_audio_input(key, self.audio_input, profile, self.dir, name="microphone")
            failures = engine.startup_failures(key)
            self.microphone = {"input": self.audio_input.describe(), "key": key,
                               "file": Path(out[0]).name if out else None,
                               "state": "failed" if failures or not out else "recording",
                               "note": " ".join(str(f.get("error", "")) for f in failures)[:400] or None}
            if failures:
                await engine.stop(key)
                return None
            return str(out[0]) if out else None

        jobs = [one(source_id) for source_id in self.session.sources]
        if self.audio_input is not None:
            jobs.append(microphone())
        paths += [path for path in await asyncio.gather(*jobs) if path]
        return paths

    async def _start_program(self) -> List[str]:
        cameras = self.controller.cameras
        program = cameras.get_program_source()
        now = time.time()
        self.cuts.append({"requested_at": now, "from": None, "to": program.source_id, "kind": "start"})
        seg = await self._open_segment(program.source_id, role="program")
        if seg is None or seg.state == "failed":
            reason = "no_capture_engine" if seg is None else "failed_to_start"
            self.intervals.append(Interval(program.source_id, None, reason, start=now))
            self._program = None
        else:
            self.intervals.append(Interval(program.source_id, seg.index, "program", start_ref=seg.index))
            self._program = seg.index
            self.cuts[-1].update(segment=seg.index, handled="started")
        if self.arm_preview:
            preview = cameras.get_preview_source()
            if preview is not None and preview.source_id != program.source_id:
                await self._arm(preview.source_id)
        return [str(seg.file)] if seg is not None and seg.state != "failed" else []

    # -- segments ------------------------------------------------------------------------------------------
    async def _open_segment(self, source_id: str, *, role: str) -> Optional[Segment]:
        engine = self.controller.capture_engine
        if engine is None or not getattr(engine, "available", False):
            if "FFmpeg is not available: no picture is being recorded" not in self.notes:
                self.notes.append("FFmpeg is not available: no picture is being recorded")
            return None
        camera = self.controller.cameras.get(source_id)
        if camera is None:
            return None
        index = self._next_index
        self._next_index += 1
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", source_id)
        key = f"{self.session_id}~pgm{index:04d}"
        source = dataclasses.replace(camera, source_id=f"{PROGRAM_STEM}_{index:04d}_{safe}")
        profile = self.controller.recording.get_profile(self.session.profile_id)
        spawned = time.time()
        out = await engine.start(key, [source], profile, self.dir)
        seg = Segment(index=index, source_id=source_id, key=key,
                      file=Path(out[0]) if out else self.dir / f"{source.source_id}.{profile.container.value}",
                      synthetic=camera.transport.value == "virtual", spawned_at=spawned, roles=[(role, spawned)])
        failures = engine.startup_failures(key) if hasattr(engine, "startup_failures") else []
        if not out or failures:
            seg.state = "failed"
            seg.error = " ".join(str(f.get("error", "")) for f in failures)[:400] or "FFmpeg could not be started"
            await engine.stop(key)
        else:
            seg.state = "running"
        self.segments[index] = seg
        self.controller._witness(self.session, "segment_started" if seg.state == "running" else "segment_failed",
                                 source_id=source_id, segment=index, role=role)
        return seg

    async def _first_frame(self, seg: Segment) -> bool:
        """Wait until the segment's encoder reports picture, so the camera before it can stop without a gap."""
        engine = self.controller.capture_engine
        deadline = time.monotonic() + FIRST_FRAME_WAIT_SECONDS
        while time.monotonic() < deadline:
            if not engine.running(seg.key):
                return False
            report = engine.live_report(seg.key)
            if report and (report[0].get("encoded_seconds") or 0) > 0:
                return True
            await asyncio.sleep(0.05)
        return engine.running(seg.key)

    async def _close_segment(self, index: Optional[int]) -> None:
        if index is None:
            return
        seg = self.segments.get(index)
        if seg is None or seg.state != "running":
            return
        engine = self.controller.capture_engine
        seg.stop_requested_at = time.time()
        await engine.stop(seg.key)
        report = engine.report(seg.key) if hasattr(engine, "report") else []
        seg.report = report[0] if report else {}
        seg.state = "stopped"
        info = await asyncio.to_thread(probe_media, seg.file)
        seg.duration = info.get("duration") or seg.report.get("encoded_seconds")
        seg.has_audio = bool(info.get("audio"))
        speed = seg.report.get("speed")
        wall = seg.stop_requested_at - seg.spawned_at
        if seg.duration and seg.duration - wall > 0.75:
            seg.error = (f"the file holds {seg.duration:.2f} s for {wall:.2f} s of take: the source was not paced to "
                         "the clock (a test pattern does this), so this piece's timing is not the take's")
        elif speed is not None and speed < 0.97 and wall >= 3.0:
            seg.error = f"the encoder fell behind real time ({speed:.2f}x), so this piece is shorter than its stretch"
        if seg.duration:
            # FFmpeg writes every frame it read before it was told to stop, so the file ends at the stop request.
            seg.media_offset = seg.stop_requested_at - seg.duration
            seg.first_frame_at = max(seg.spawned_at, seg.media_offset)
        else:
            seg.error = seg.error or "no picture was written"
        self.controller._witness(self.session, "segment_stopped", source_id=seg.source_id, segment=index,
                                 duration=seg.duration)

    async def _arm(self, source_id: str) -> None:
        if not self._eligible(source_id)[0]:
            return
        seg = await self._open_segment(source_id, role="preview")
        if seg is not None and seg.state == "running":
            self._preview = seg.index

    # -- cuts ----------------------------------------------------------------------------------------------
    def _eligible(self, source_id: str) -> Tuple[bool, str]:
        # Privacy first, so a cut to the dressing room is recorded as private whether or not it was in the take.
        try:
            self.controller.recording._validate_sources([source_id], host_override=self.session.host_override)
        except PermissionError:
            return False, "private"
        except ValueError:
            return False, "not_recordable"
        if source_id not in self.session.sources:
            return False, "not_in_take"
        return True, "program"

    def camera_event(self, event) -> None:
        """Called by the camera manager for every change; records it and queues the cut (event loop thread)."""
        if self.data is not None:
            kind = "camera.switch" if hasattr(event, "destination") else "camera.pose"
            self.data.record(kind, event)
        if self.mode == "main_camera" and hasattr(event, "destination") and self.state == "recording":
            # The camera manager may be driven from another thread; the queue belongs to the event loop.
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    async def _work(self) -> None:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            try:
                if event.destination == "program":
                    await self._cut(event)
                elif event.destination == "preview" and self.arm_preview:
                    await self._preview_changed(event)
            except Exception as exc:     # a cut must never take the whole recording down
                logger.exception("Recording mode %s could not follow a cut", self.session_id)
                self.notes.append(f"A cut to {getattr(event, 'source_id', '?')} could not be followed: {exc}")
            self._write_record()

    def _end_current(self, *, at: Optional[float] = None, at_ref: Optional[int] = None) -> None:
        if self.intervals and self.intervals[-1].end is None and self.intervals[-1].end_ref is None:
            self.intervals[-1].end = at
            self.intervals[-1].end_ref = at_ref

    async def _cut(self, event) -> None:
        target = event.source_id
        requested = float(event.timestamp or time.time())
        current = self.intervals[-1].source_id if self.intervals else None
        if target == current:
            return
        cut = {"requested_at": requested, "from": current, "to": target, "kind": "cut"}
        self.cuts.append(cut)
        previous = self._program
        keep_previous = False
        if self.arm_preview and previous is not None:
            preview = self.controller.cameras.get_preview_source()
            seg = self.segments.get(previous)
            keep_previous = bool(seg and preview and preview.source_id == seg.source_id)
        ok, reason = self._eligible(target)
        if not ok:
            self._end_current(at=requested)
            self.intervals.append(Interval(target, None, reason, start=requested))
            cut.update(handled=reason, effective_at=requested)
            self._program = None
            if not keep_previous:
                await self._close_segment(previous)
            elif previous is not None:
                await self._set_preview(previous)
            self.controller._witness(self.session, "program_gap", source_id=target, reason=reason)
            return
        if self._preview is not None and self.segments[self._preview].source_id == target \
                and self.segments[self._preview].state == "running":
            # Armed on preview and already recording: the cut is exact.
            index = self._preview
            self._preview = None
            self.segments[index].roles.append(("program", requested))
            self._end_current(at=requested)
            self.intervals.append(Interval(target, index, "program", start=requested))
            self._program = index
            cut.update(handled="armed", segment=index, effective_at=requested)
        else:
            seg = await self._open_segment(target, role="program")
            if seg is None or seg.state == "failed" or not await self._first_frame(seg):
                if seg is not None and seg.state == "running":
                    await self._close_segment(seg.index)
                    seg.state, seg.error = "failed", seg.error or "the camera delivered no picture"
                self._end_current(at=requested)
                why = "no_capture_engine" if seg is None else "failed_to_start"
                self.intervals.append(Interval(target, None, why, start=requested))
                cut.update(handled=why, effective_at=requested, error=getattr(seg, "error", None))
                self._program = None
            else:
                # The camera before keeps going until this one has picture: the join happens at its first frame.
                self._end_current(at_ref=seg.index)
                self.intervals.append(Interval(target, seg.index, "program", start_ref=seg.index))
                self._program = seg.index
                cut.update(handled="started", segment=seg.index)
        if keep_previous:
            await self._set_preview(previous)
            self.segments[previous].roles.append(("preview", requested))
        elif previous is not None and previous != self._program:
            await self._close_segment(previous)

    async def _set_preview(self, index: Optional[int]) -> None:
        """Make ``index`` the one armed preview; any other camera armed until now stops recording."""
        if self._preview is not None and self._preview != index and self._preview != self._program:
            await self._close_segment(self._preview)
        self._preview = index

    async def _preview_changed(self, event) -> None:
        target = event.source_id
        current = self.segments.get(self._preview) if self._preview is not None else None
        if current is not None and current.source_id == target:
            return
        await self._set_preview(None)
        program = self.segments.get(self._program) if self._program is not None else None
        if program is not None and program.source_id == target:
            return          # that camera is already recording, as the one on the live screen
        await self._arm(target)

    # -- stop ----------------------------------------------------------------------------------------------
    async def end(self) -> List[Dict[str, Any]]:
        """Stop everything this mode started; returns the media files to register."""
        self.state = "stopping"
        self.stopped_at = time.time()
        if self._worker is not None:
            self._queue.put_nowait(None)
            try:
                await asyncio.wait_for(self._worker, timeout=60)
            except asyncio.TimeoutError:
                self._worker.cancel()
                self.notes.append("A cut was still being followed when the take stopped")
        self._end_current(at=self.stopped_at)
        engine = self.controller.capture_engine
        media: List[Dict[str, Any]] = []
        for index in list(self.segments):
            await self._close_segment(index)
        for seg in self.segments.values():
            if seg.state == "stopped" and seg.file.is_file() and seg.file.stat().st_size > 0:
                media.append({"path": seg.file, "synthetic": seg.synthetic})
        for entry in self.sound:
            key = entry.pop("key", None)
            if key and engine is not None:
                await engine.stop(key)
                report = engine.report(key)
                entry["report"] = report[0] if report else {}
                path = self.dir / entry["file"] if entry.get("file") else None
                if path is not None and path.is_file() and path.stat().st_size > 0:
                    entry["state"] = "recorded"
                    media.append({"path": path, "synthetic": False})
                else:
                    entry["state"] = "empty"
        if self.microphone and self.microphone.get("state") == "recording":
            stop_at = time.time()
            await engine.stop(self.microphone["key"])
            report = engine.report(self.microphone["key"])
            self.microphone["report"] = report[0] if report else {}
            path = self.dir / self.microphone["file"]
            if path.is_file() and path.stat().st_size > 0:
                self.microphone["state"] = "recorded"
                self.microphone["_stop_at"] = stop_at
                info = await asyncio.to_thread(probe_media, path)
                self.microphone["duration"] = info.get("duration")
                media.append({"path": path, "synthetic": False})
            else:
                self.microphone["state"] = "empty"
        if self.data is not None:
            self.data.close()
        self.state = "stopped"
        if self.mode == "main_camera":
            self.assembly = {"state": "pending"}
        self._write_record()
        return media

    # -- the program file ----------------------------------------------------------------------------------
    async def assemble(self) -> Dict[str, Any]:
        """Join the program pieces into one file at the take's own picture and sound settings."""
        recording = self.controller.recording
        profile = recording.get_profile(self.session.profile_id)
        self.assembly = {"state": "running", "started_utc": time.time()}
        self._write_record()
        try:
            result = await asyncio.to_thread(self._render_program, profile)
        except Exception as exc:
            logger.exception("Program for %s could not be joined", self.session_id)
            result = {"state": "failed", "error": str(exc)[:500]}
        if result.get("state") == "complete":
            try:
                recording.register_artifact(self.session_id, self.dir / result["file"])
            except Exception as exc:
                result = {**result, "state": "failed", "error": f"joined, but could not be registered: {exc}"}
        result["finished_utc"] = time.time()
        self.assembly = result
        self._write_record()
        self.controller._witness(self.session, "program_assembled", result=result.get("state"), file=result.get("file"))
        return result

    def _render_program(self, profile) -> Dict[str, Any]:
        from .capture import _build_ffmpeg_output, _ffmpeg_bin
        try:
            ffmpeg = _ffmpeg_bin()
        except EnvironmentError as exc:
            return {"state": "unavailable", "error": str(exc)}
        width, height = (profile.resolution or "1920x1080").lower().split("x")
        rate = profile.frame_rate or "30"
        frame = 1.0 / float(rate)
        origin, pieces = plan_program(self.intervals, self.segments, frame=frame)
        if not pieces:
            return {"state": "empty", "error": "nothing was on the live screen long enough to join"}
        total = sum(_piece_duration(p) for p in pieces)
        inputs: List[str] = []
        input_index: Dict[str, int] = {}

        def input_of(path: Path) -> int:
            if path.name not in input_index:
                input_index[path.name] = len(inputs) // 2
                inputs.extend(["-i", path.name])
            return input_index[path.name]

        mic_path = None
        mic = self.microphone or {}
        if mic.get("state") == "recorded" and mic.get("duration") and mic.get("_stop_at"):
            mic_path = self.dir / mic["file"]
        fmt = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
        chains: List[str] = []
        labels: List[str] = []
        for i, piece in enumerate(pieces):
            duration = _piece_duration(piece)
            if piece["kind"] == "segment":
                seg = self.segments[piece["segment"]]
                k = input_of(seg.file)
                chains.append(f"[{k}:v:0]trim=start={piece['in']}:end={piece['out']},setpts=PTS-STARTPTS,fps={rate},"
                              f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                              f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v{i}]")
                if mic_path is None:
                    if seg.has_audio:
                        chains.append(f"[{k}:a:0]atrim=start={piece['in']}:end={piece['out']},asetpts=PTS-STARTPTS,"
                                      f"{fmt},apad,atrim=duration={duration:.6f}[a{i}]")
                    else:
                        chains.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration:.6f}[a{i}]")
            else:
                chains.append(f"color=c=black:s={width}x{height}:r={rate}:d={duration:.6f},format=yuv420p,setsar=1[v{i}]")
                if mic_path is None:
                    chains.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration:.6f}[a{i}]")
            labels.append(f"[v{i}]" + ("" if mic_path is not None else f"[a{i}]"))
        audio_note = "follows the picture: each camera's own sound"
        if mic_path is not None:
            chains.append("".join(labels) + f"concat=n={len(pieces)}:v=1:a=0[vout]")
            m = input_of(mic_path)
            mic_first = mic["_stop_at"] - mic["duration"]
            offset = origin - mic_first
            lead = f"atrim=start={offset:.6f}," if offset > 0 else ""
            delay = f"adelay={int(round(-offset * 1000))}:all=1," if offset < 0 else ""
            chains.append(f"[{m}:a:0]{lead}asetpts=PTS-STARTPTS,{delay}{fmt},apad,atrim=duration={total:.6f}[aout]")
            audio_note = "the microphone, for the whole program"
        else:
            chains.append("".join(labels) + f"concat=n={len(pieces)}:v=1:a=1[vout][aout]")
        out_path = self.dir / f"{PROGRAM_STEM}.{profile.container.value}"
        if out_path.exists():
            return {"state": "failed", "error": f"{out_path.name} already exists; it is never overwritten"}
        script = self.dir / f"{out_path.name}.ffmpeg.filter"
        script.write_text(";\n".join(chains), encoding="utf-8")
        tmp = self.dir / f".{out_path.stem}.joining.{profile.container.value}"
        args = _build_ffmpeg_output(profile, tmp)
        cmd = [ffmpeg, "-y", "-hide_banner", "-nostdin", *inputs, "-filter_complex_script", script.name,
               "-map", "[vout]", "-map", "[aout]", *args[:-1], tmp.name]
        log_path = self.dir / f"{out_path.name}.ffmpeg.log"
        started = time.time()
        with open(log_path, "wb") as log:
            done = subprocess.run(cmd, cwd=str(self.dir), stdout=subprocess.DEVNULL, stderr=log, timeout=24 * 3600)
        tail = " | ".join(log_path.read_text(errors="replace").strip().splitlines()[-4:])
        if done.returncode != 0 or not tmp.is_file():
            return {"state": "failed", "error": f"FFmpeg exited with status {done.returncode}: {tail}"[:600],
                    "log": log_path.name, "filter": script.name}
        info = probe_media(tmp)
        tolerance = max(0.25, 2 * frame)
        warnings: List[str] = []
        if not info.get("duration") or abs(info["duration"] - total) > tolerance:
            warnings.append(f"joined program lasts {info.get('duration')} s; the pieces add up to {total:.3f} s")
        os.replace(tmp, out_path)
        late = [c.get("late_by_ms") for c in self.cuts if c.get("late_by_ms") is not None]
        return {"state": "complete", "file": out_path.name, "duration": info.get("duration"), "expected_duration": round(total, 4),
                "origin": round(origin - self.t0, 4), "pieces": pieces, "audio": audio_note, "warnings": warnings,
                "render_seconds": round(time.time() - started, 2), "log": log_path.name, "filter": script.name,
                "largest_cut_delay_ms": max(late) if late else None}

    @classmethod
    async def from_record(cls, controller: "RecordingModeController", session, record: Dict[str, Any]) -> "ModeTake":
        """Rebuild a stopped take from its mode record, so its program can be joined after a restart."""
        take = cls(controller, session)
        take.t0 = float(record.get("take_started_utc") or session.started_at)
        absolute = lambda value: None if value is None else take.t0 + float(value)
        program = record.get("program") or {}
        for item in program.get("segments", []):
            seg = Segment(index=int(item["index"]), source_id=str(item["source_id"]), key="",
                          file=take.dir / Path(str(item["file"])).name, synthetic=bool(item.get("synthetic")),
                          spawned_at=absolute(item.get("spawned_at")) or take.t0, state=str(item.get("state")),
                          stop_requested_at=absolute(item.get("stopped_at")), duration=item.get("duration"),
                          has_audio=bool(item.get("has_audio")), media_offset=absolute(item.get("media_offset")),
                          first_frame_at=absolute(item.get("first_frame_at")),
                          report=item.get("report") or {}, error=item.get("error"))
            if seg.first_frame_at is None and seg.file.is_file():
                # The server stopped before this piece was closed: its start is the best estimate there is.
                info = await asyncio.to_thread(probe_media, seg.file)
                seg.duration, seg.has_audio = info.get("duration"), bool(info.get("audio"))
                if seg.duration:
                    seg.first_frame_at = seg.media_offset = seg.spawned_at
                    seg.stop_requested_at = seg.spawned_at + seg.duration
                    seg.error = "timing estimated: the server stopped before this piece was closed"
            take.segments[seg.index] = seg
        for item in program.get("intervals", []):
            take.intervals.append(Interval(item.get("source_id"), item.get("segment"), str(item.get("reason")),
                                           start=absolute(item.get("start")), start_ref=item.get("start_at_first_frame_of"),
                                           end=absolute(item.get("end")), end_ref=item.get("end_at_first_frame_of")))
        if take.intervals and take.intervals[-1].end is None and take.intervals[-1].end_ref is None:
            seg = take.segments.get(take.intervals[-1].segment) if take.intervals[-1].segment is not None else None
            take.intervals[-1].end = absolute(record.get("stopped_at")) or (
                seg.stop_requested_at if seg is not None else None)
        take.cuts = [{**c, "requested_at": absolute(c.get("requested_at")), "effective_at": absolute(c.get("effective_at"))}
                     for c in program.get("cuts", [])]
        mic = record.get("microphone")
        if mic and mic.get("state") == "recorded":
            take.microphone = {**mic, "_stop_at": absolute(mic.get("stopped_at"))}
        take.sound = list(record.get("sound") or [])
        take.state = "stopped"
        take.stopped_at = absolute(record.get("stopped_at"))
        take.notes = list(record.get("notes") or [])
        return take

    # -- the mode record -----------------------------------------------------------------------------------
    def _effective_cuts(self) -> None:
        for cut in self.cuts:
            index = cut.get("segment")
            seg = self.segments.get(index) if index is not None else None
            if cut.get("handled") in ("started",) and seg is not None and seg.first_frame_at is not None:
                cut["effective_at"] = seg.first_frame_at
            if cut.get("effective_at") is not None and cut["kind"] == "cut":
                cut["late_by_ms"] = max(0, int(round((cut["effective_at"] - cut["requested_at"]) * 1000)))

    def record(self) -> Dict[str, Any]:
        self._effective_cuts()
        rel = lambda value: None if value is None else round(value - self.t0, 4)
        data = None
        if self.data is not None:
            data = self.data.summary or {"file": self.data.path.name, "events": self.data.events, "complete": False,
                                         "error": self.data.error}
            data = {**data, "rooms_recorded": sorted(self.rooms_recorded), "rooms_excluded": sorted(self.rooms_excluded)}
        return {
            "schema": MODE_RECORD_SCHEMA, "session_id": self.session_id, "mode": self.mode,
            "description": MODES[self.mode], "record_data": bool(self.session.record_data),
            "arm_preview": self.arm_preview, "state": self.state, "take_started_utc": self.t0,
            "stopped_at": rel(self.stopped_at),
            "times": "seconds from take_started_utc, wall clock",
            "program": None if self.mode != "main_camera" else {
                "cuts": [{**c, "requested_at": rel(c.get("requested_at")), "effective_at": rel(c.get("effective_at"))}
                         for c in self.cuts],
                "intervals": [{"source_id": i.source_id, "segment": i.segment, "reason": i.reason,
                               "start": rel(i.start), "start_at_first_frame_of": i.start_ref,
                               "end": rel(i.end), "end_at_first_frame_of": i.end_ref} for i in self.intervals],
                "segments": [s.to_dict(self.t0) for s in self.segments.values()],
            },
            "sound": [{k: v for k, v in entry.items() if k != "key"} for entry in self.sound],
            "microphone": None if not self.microphone else {
                **{k: v for k, v in self.microphone.items() if k != "key" and not k.startswith("_")},
                "stopped_at": rel(self.microphone.get("_stop_at"))},
            "show_data": data,
            "assembly": self.assembly,
            "notes": self.notes,
        }

    def _write_record(self) -> None:
        try:
            write_json(self.dir / MODE_RECORD_FILE, self.record())
        except Exception:
            logger.exception("Recording mode record for %s could not be written", self.session_id)


def _report_task_failure(task: "asyncio.Task") -> None:
    """A background step that fails must say so in the log, not vanish with its task."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Recording mode task %s failed", task.get_name(), exc_info=(type(exc), exc, exc.__traceback__))


# ── Controller: one per server, shared by every route that starts or stops a take ─────────────────────────────
class RecordingModeController:
    def __init__(self, *, cameras, recording, capture_engine=None, hub=None):
        self.cameras = cameras
        self.recording = recording
        self.capture_engine = capture_engine
        self.hub = hub
        self._takes: Dict[str, ModeTake] = {}
        self._finished: Dict[str, ModeTake] = {}
        self._assemblies: Dict[str, asyncio.Task] = {}
        self._camera_token: Optional[int] = None
        self._hub_token: Optional[int] = None

    # -- wiring --------------------------------------------------------------------------------------------
    def _subscribe(self) -> None:
        if self._camera_token is None:
            self._camera_token = self.cameras.subscribe(self._on_camera_event)
        if self._hub_token is None and self.hub is not None and hasattr(self.hub, "add_event_observer"):
            self._hub_token = self.hub.add_event_observer(self._on_hub_message)

    def _unsubscribe_if_idle(self) -> None:
        if self._takes:
            return
        if self._camera_token is not None:
            self.cameras.unsubscribe(self._camera_token)
            self._camera_token = None
        if self._hub_token is not None and self.hub is not None:
            self.hub.remove_event_observer(self._hub_token)
            self._hub_token = None

    def _on_camera_event(self, event) -> None:
        for take in list(self._takes.values()):
            try:
                take.camera_event(event)
            except Exception:
                logger.exception("Recording mode %s could not take a camera event", take.session_id)

    def _on_hub_message(self, kind: str, room: Optional[str], message: Dict[str, Any]) -> None:
        for take in list(self._takes.values()):
            if take.data is None:
                continue
            if kind == "system":
                take.data.record("hub.system", message)
                continue
            if isinstance(message, dict) and message.get("type") == "presence":
                continue
            if room_is_recordable(self.recording, room, host_override=take.session.host_override):
                take.rooms_recorded.add(room)
                take.data.record("hub.room", message, room=room)
            elif room and not room.startswith(_PRIVATE_ROOM_PREFIXES):
                take.rooms_excluded.add(room)

    def _witness(self, session, event: str, /, **data: Any) -> None:
        witness = getattr(self.recording, "blackbox_witness", None)
        if witness is None:
            return
        try:
            witness.record_event("recording.state", source="recording", actor=session.operator,
                                 data={"session_id": session.session_id, "state": event, "mode": session.mode, **data})
        except Exception:
            logger.exception("BlackBox could not witness recording mode %s", event)

    # -- what routes call ----------------------------------------------------------------------------------
    def owns_capture(self, session_id: str) -> bool:
        """True when this mode, not the camcorder path, decides what picture and sound are recorded."""
        take = self._takes.get(session_id) or self._finished.get(session_id)
        if take is not None:
            return take.mode != "camcorder"
        try:
            return self.recording.get_session(session_id).mode != "camcorder"
        except KeyError:
            return False

    async def begin(self, session, *, audio_input=None, arm_preview: bool = False, sources_named: bool = True) -> List[str]:
        """The take has gone live. Starts the show data, and the picture and sound this mode records itself."""
        if session.session_id in self._takes or session.session_id in self._finished:
            return []
        take = ModeTake(self, session, audio_input=audio_input, arm_preview=arm_preview, sources_named=sources_named)
        self._takes[session.session_id] = take
        self._subscribe()
        self._witness(session, "mode_started", record_data=bool(session.record_data), arm_preview=take.arm_preview)
        try:
            return await take.begin()
        except Exception:
            logger.exception("Recording mode %s could not start", session.session_id)
            take.notes.append("The recording mode could not start completely; see the server log")
            take._write_record()
            return []

    async def end(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """The take is stopping. Returns the registered media of a mode that owns capture, else None."""
        take = self._takes.pop(session_id, None)
        if take is None:
            return None
        self._unsubscribe_if_idle()
        try:
            media = await take.end()
        except Exception:
            logger.exception("Recording mode %s could not stop cleanly", session_id)
            take.notes.append("The recording mode did not stop cleanly; see the server log")
            take._write_record()
            media = []
        self._finished[session_id] = take
        while len(self._finished) > 50:
            self._finished.pop(next(iter(self._finished)))
        artifacts: List[Dict[str, Any]] = []
        for item in media:
            try:
                artifact = self.recording.register_artifact(session_id, item["path"], synthetic=item["synthetic"])
            except Exception as exc:
                logger.warning("Could not register %s for %s: %s", item["path"], session_id, exc)
                continue
            artifacts.append({"name": artifact.name, "format": artifact.format.value,
                              "file_path": artifact.file_path.as_posix(), "size_bytes": artifact.size_bytes,
                              "synthetic": bool(item["synthetic"])})
        self._witness(take.session, "mode_stopped", artifacts=len(artifacts))
        if take.mode == "main_camera":
            task = asyncio.create_task(take.assemble(), name=f"program-join-{session_id}")
            task.add_done_callback(_report_task_failure)
            self._assemblies[session_id] = task
            for done in [sid for sid, t in self._assemblies.items() if t.done()][:-50]:
                self._assemblies.pop(done, None)
        return artifacts if take.mode != "camcorder" else None

    def start_problems(self, session_id: str) -> List[Dict[str, Any]]:
        """Anything this mode could not start, in the same shape as the camcorder path's capture errors."""
        take = self._takes.get(session_id)
        if take is None:
            return []
        problems: List[Dict[str, Any]] = []
        for seg in take.segments.values():
            if seg.state == "failed":
                problems.append({"source_id": seg.source_id, "error": seg.error or "picture could not be started"})
        for entry in take.sound:
            if entry.get("state") == "failed":
                problems.append({"source_id": entry["source_id"], "error": f"sound: {entry.get('note')}"})
        if take.microphone and take.microphone.get("state") == "failed":
            problems.append({"source_id": "microphone", "error": take.microphone.get("note") or "could not be opened"})
        for note in take.notes:
            if note.startswith("FFmpeg is not available") or note.startswith("Show data could not"):
                problems.append({"source_id": None, "error": note})
        return problems

    async def assemble(self, session_id: str) -> Dict[str, Any]:
        """Join (again) the program of a stopped main-camera take that has no program file yet."""
        session = self.recording.get_session(session_id)
        if session.mode != "main_camera":
            raise ModeRequestError("Only a main-camera take has a program to join")
        if session_id in self._takes:
            raise ModeRequestError("This take is still recording")
        running = self._assemblies.get(session_id)
        if running is not None and not running.done():
            await asyncio.shield(running)
            return self.status(session_id)["assembly"]
        take = self._finished.get(session_id)
        if take is None:
            path = self.recording._session_dir(session_id) / MODE_RECORD_FILE
            if not path.is_file():
                raise ModeRequestError("This take has no mode record to join from")
            take = await ModeTake.from_record(self, session, json.loads(path.read_text(encoding="utf-8")))
        program = take.dir / f"{PROGRAM_STEM}.{self.recording.get_profile(session.profile_id).container.value}"
        if program.exists():
            raise ModeRequestError(f"{program.name} already exists; it is never overwritten")
        self._finished[session_id] = take
        task = asyncio.create_task(take.assemble(), name=f"program-join-{session_id}")
        task.add_done_callback(_report_task_failure)
        self._assemblies[session_id] = task
        return await asyncio.shield(task)

    def status(self, session_id: str) -> Dict[str, Any]:
        take = self._takes.get(session_id) or self._finished.get(session_id)
        if take is not None:
            return take.record()
        path = self.recording._session_dir(session_id) / MODE_RECORD_FILE
        session = self.recording.get_session(session_id)
        if not path.is_file():
            return {"session_id": session_id, "mode": session.mode, "record_data": session.record_data,
                    "state": "unknown", "notes": ["This take has no mode record"]}
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("state") in ("recording", "stopping") and session.state.value in ("stopped", "archived"):
            record["interrupted"] = True
            record["notes"] = list(record.get("notes") or []) + ["The server stopped before this take finished"]
        return record

    async def wait_for_assembly(self, session_id: str, timeout: float = 600.0) -> Dict[str, Any]:
        task = self._assemblies.get(session_id)
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout)
        return self.status(session_id)

    async def shutdown(self) -> None:
        for session_id in list(self._takes):
            await self.end(session_id)
        pending = [t for t in self._assemblies.values() if not t.done()]
        for task in pending:
            task.cancel()
