# PubCast AI — recording.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
from __future__ import annotations

import json
import hashlib
import logging
import math
import os
import re
import shutil
import subprocess
import time
import tempfile
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

from .cameras import CameraManager, CameraSource, CameraTransport
from .persistence import write_json

logger = logging.getLogger(__name__)

_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
# A take's non-media files: plain names only, never a path, never hidden.
_DATA_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# The three ways a take can record picture (modules/recording_modes.py has what each does).
RECORDING_MODES = ("camcorder", "data_only", "main_camera")


class ContainerFormat(str, Enum):
    MP4 = "mp4"
    WEBM = "webm"
    WAV = "wav"
    MOV = "mov"


@dataclass
class EncodingProfile:
    profile_id: str
    name: str
    container: ContainerFormat
    video_codec: Optional[str]
    audio_codec: Optional[str]
    video_bitrate: Optional[str]
    audio_bitrate: Optional[str]
    resolution: Optional[str]
    frame_rate: Optional[str]
    description: str = ""
    is_audio_only: bool = False


@dataclass
class RecordingArtifact:
    name: str
    format: ContainerFormat
    file_path: Path
    size_bytes: int = 0
    # True when the file is an FFmpeg test pattern (a ``virtual`` camera), not
    # camera or rendered PubWorld video. Only written to disk when True, so
    # existing session files and exports are unchanged.
    synthetic: bool = False
    # For media copied into the take from another location: a digest of where it came from, so the
    # same source is replaced in place and a different source with the same file name stays distinct.
    source_key: Optional[str] = None


@dataclass
class RecordingMarker:
    timestamp: float
    label: str
    operator: Optional[str] = None


class RecordingState(str, Enum):
    REQUESTED = "requested"
    COUNTDOWN = "countdown"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ARCHIVED = "archived"


@dataclass
class RecordingSession:
    session_id: str
    sources: List[str]
    profile_id: str
    operator: str
    preset: Optional[str] = None
    host_override: bool = False
    countdown_seconds: int = 5
    state: RecordingState = RecordingState.REQUESTED
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    artifacts: List[RecordingArtifact] = field(default_factory=list)
    markers: List[RecordingMarker] = field(default_factory=list)
    recovery: Optional[Dict[str, Any]] = None
    ingest: Optional[Dict[str, Any]] = None
    # How picture is recorded (modules/recording_modes.py): "camcorder", "data_only" or
    # "main_camera". Takes saved before recording modes existed were camcorder takes.
    mode: str = "camcorder"
    # Whether the show-data record ran under this take. Older takes had none.
    record_data: bool = False
    # Non-media files of this take (show data, the mode record), by file name in the
    # session folder. They travel with the media on export and import.
    data_files: List[str] = field(default_factory=list)
    # Sources that did not record properly, each {"source_id", "error", "phase"} with phase "start"
    # or "stop". Kept with the take so a reload still says which camera is missing from it.
    capture_errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "sources": self.sources,
            "profile_id": self.profile_id,
            "operator": self.operator,
            "preset": self.preset,
            "host_override": self.host_override,
            "countdown_seconds": self.countdown_seconds,
            "state": self.state.value,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "ended_at": self.ended_at,
            "recovery": self.recovery,
            "ingest": self.ingest,
            "mode": self.mode,
            "record_data": self.record_data,
            "data_files": list(self.data_files),
            # Only written when something failed, so takes that recorded cleanly keep their files as before.
            **({"capture_errors": [dict(item) for item in self.capture_errors]} if self.capture_errors else {}),
            "artifacts": [
                {
                    "name": art.name,
                    "format": art.format.value,
                    "file_path": art.file_path.as_posix(),
                    "size_bytes": art.size_bytes,
                    **({"synthetic": True} if art.synthetic else {}),
                    **({"source_key": art.source_key} if art.source_key else {}),
                }
                for art in self.artifacts
            ],
            "markers": [
                {
                    "timestamp": marker.timestamp,
                    "label": marker.label,
                    "operator": marker.operator,
                }
                for marker in self.markers
            ],
        }


class RecordingService:
    """
    Coordinates recording sessions and maintains metadata for import/export.
    The class intentionally separates orchestration from the underlying
    capture pipeline so that future integrations (FFmpeg, cloud encoders,
    etc.) can target the same API surface.
    """

    def __init__(self, base_dir: Path, cameras: CameraManager, blackbox_witness: Optional[Any] = None) -> None:
        self.base_dir = base_dir
        self.cameras = cameras
        self.blackbox_witness = blackbox_witness
        self._profiles: Dict[str, EncodingProfile] = {}
        self._sessions: Dict[str, RecordingSession] = {}
        self._room_privacy: Dict[str, Dict[str, str]] = {}
        
        # NEW: Pipeline sessions for detailed event logging
        self._pipeline_sessions: Dict[str, Any] = {}

        self.recordings_dir = self.base_dir / "recordings"
        self.exports_dir = self.base_dir / "exports"
        self.imports_dir = self.base_dir / "imports"
        for directory in (self.recordings_dir, self.exports_dir, self.imports_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self._storage_cache = {
            "cloud_used_gb": None,
            "backup_status": "not configured",
        }
        self._restore_sessions()

    def _restore_sessions(self) -> None:
        """Restore real persisted takes; never resume an interrupted capture by label."""
        for directory in self.recordings_dir.iterdir():
            if not directory.is_dir() or directory.is_symlink():
                continue
            metadata = directory / f"{directory.name}.json"
            if not metadata.is_file():
                continue
            try:
                if metadata.stat().st_size > 8 * 1024 ** 2:
                    raise ValueError("Recording metadata exceeds the recovery budget")
                payload = json.loads(metadata.read_text(encoding="utf-8"))
                session_id = self._validated_session_id(payload.get("session_id"))
                if session_id != directory.name:
                    raise ValueError("Recording metadata does not match its directory")
                session = self._session_from_dict(payload)
                if session.state not in {RecordingState.STOPPED, RecordingState.ARCHIVED}:
                    session.recovery = {"previous_state": session.state.value, "detected_at": time.time(),
                                        "last_confirmed_at": session.updated_at, "interrupted": True}
                    session.state = RecordingState.STOPPED
                    session.ended_at = session.updated_at
                    self._write_metadata(session)
                self._sessions[session_id] = session
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                logger.exception("Could not restore recording metadata %s; original files retained", metadata)

    def _blackbox_event(self, event_type: str, *, actor: str = "SYS", data: Optional[Dict[str, Any]] = None) -> None:
        if self.blackbox_witness is not None:
            self.blackbox_witness.record_event(event_type, source="recording", actor=actor, data=data or {})

    # ------------------------------------------------------------------
    # Profiles
    def register_profile(self, profile: EncodingProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def list_profiles(self) -> List[EncodingProfile]:
        return list(self._profiles.values())

    def get_profile(self, profile_id: str) -> EncodingProfile:
        if profile_id not in self._profiles:
            raise KeyError(f"Unknown encoding profile '{profile_id}'")
        return self._profiles[profile_id]

    # ------------------------------------------------------------------
    # Sources & privacy
    def list_sources(self) -> List[CameraSource]:
        return self.cameras.list_sources()

    def configure_room_privacy(self, config: Dict[str, Dict[str, str]]) -> None:
        self._room_privacy = config

    def room_policy(self, room: str) -> Dict[str, str]:
        return self._room_privacy.get(room, {"recording": "allowed"})

    def privacy_matrix(self) -> Dict[str, Dict[str, str]]:
        return self._room_privacy

    def _validate_sources(self, sources: Iterable[str], *, host_override: bool) -> None:
        for source_id in sources:
            camera = self.cameras.get(source_id)
            if not camera:
                raise ValueError(f"Unknown source '{source_id}'")
            # A JPEG confidence frame endpoint is not a recordable video transport.
            # Guard the domain boundary across all recording entry points.
            if "studio25d" in camera.tags and str(camera.endpoint).startswith("virtual://"):
                raise ValueError(
                    f"2.5D source '{source_id}' provides confidence images only; "
                    "use the local full-resolution recorder until media ingest is connected"
                )
            if camera.transport == CameraTransport.VOXEL_3D and camera.endpoint.startswith("rust://"):
                raise ValueError(f"Native voxel source '{source_id}' has pose control only and no recordable media.")
            policy = self.room_policy(camera.location)
            rule = policy.get("recording", "allowed")
            if rule == "never" and not host_override:
                raise PermissionError(f"Recording is forbidden in {camera.location}")
            if rule == "with_permission" and not host_override:
                raise PermissionError(f"Recording {camera.location} requires consent")

    # ------------------------------------------------------------------
    # Session lifecycle
    def list_sessions(self) -> List[RecordingSession]:
        return list(self._sessions.values())

    def get_session(self, session_id: str) -> RecordingSession:
        try:
            session = self._sessions.get(session_id)
            if session is None and re.fullmatch(r"enc_[a-f0-9]{40}", session_id):
                metadata = self._session_dir(session_id) / (session_id + ".json")
                try:
                    session = self._session_from_dict(json.loads(metadata.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    raise KeyError(session_id) from None
                if not session.ingest:
                    raise KeyError(session_id)
            if session is None:
                raise KeyError(session_id)
            if session.ingest:
                # Encoded take commits can arrive from another server worker.
                metadata = self._session_dir(session_id) / (session_id + ".json")
                return self._session_from_dict(json.loads(metadata.read_text(encoding="utf-8")))
            return session
        except KeyError as exc:
            raise KeyError(f"Session '{session_id}' not found") from exc

    def _session_dir(self, session_id: str) -> Path:
        return self.recordings_dir / session_id

    @staticmethod
    def _validated_session_id(value: object) -> str:
        session_id = str(value or "").strip()
        if not _SESSION_ID_PATTERN.fullmatch(session_id) or session_id in {".", ".."}:
            raise ValueError(
                "session_id must be 1–128 ASCII letters, digits, dots, "
                "underscores, or hyphens, beginning with a letter or digit"
            )
        return session_id

    def start_session(
        self,
        session_id: Optional[str],
        sources: List[str],
        *,
        profile_id: str,
        operator: str,
        preset: Optional[str] = None,
        host_override: bool = False,
        countdown_seconds: int = 5,
        mode: str = "camcorder",
        record_data: bool = True,
    ) -> RecordingSession:
        from .recording_modes import validate_mode_request  # recording_modes imports this module

        mode = validate_mode_request(self, mode, sources, profile_id, record_data=record_data,
                                     host_override=host_override)
        if not sources and mode != "data_only":
            raise ValueError("At least one source is required")
        if len(set(sources)) != len(sources):
            raise ValueError("Each recording source must be selected only once")
        session_id = self._validated_session_id(
            session_id or f"rec_{uuid.uuid4().hex[:10]}"
        )
        if session_id in self._sessions or self._session_dir(session_id).exists():
            raise ValueError(f"Session '{session_id}' already active")
        self._validate_sources(sources, host_override=host_override)
        profile = self.get_profile(profile_id)
        if profile.profile_id == "browser_original":
            raise ValueError("Original browser takes use the encoded upload path, not camera capture")

        session = RecordingSession(
            session_id=session_id,
            sources=sources,
            profile_id=profile.profile_id,
            operator=operator,
            preset=preset,
            host_override=host_override,
            countdown_seconds=countdown_seconds,
            state=RecordingState.COUNTDOWN if countdown_seconds else RecordingState.ACTIVE,
            mode=mode,
            record_data=bool(record_data),
        )
        session_dir = self._session_dir(session_id)
        try:
            session_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise ValueError(f"Session '{session_id}' already active") from exc
        try:
            self._write_metadata(session)
        except BaseException:
            # A failed first write leaves nothing behind, so the same take can be retried.
            # Only the empty folder this call just reserved is removed.
            try:
                if not any(session_dir.iterdir()):
                    session_dir.rmdir()
            except OSError:
                logger.warning("Could not remove the empty reservation %s", session_dir)
            raise
        self._sessions[session_id] = session

        # NEW: Create pipeline session for detailed event logging
        try:
            from .recording_pipeline import ServerRecordingSession
            pipeline = ServerRecordingSession(session_id, self.recordings_dir)
            self._pipeline_sessions[session_id] = pipeline
            
            # Register with export routes
            try:
                from . import recording_pipeline_routes
                recording_pipeline_routes.register_pipeline_session(session_id, pipeline)
            except ImportError:
                pass  # Routes not loaded yet
            
            logger.info("Recording session %s created with pipeline logging", session_id)
        except ImportError:
            logger.info("Recording session %s created (pipeline logging unavailable)", session_id)

        self._blackbox_event("recording.state", actor=operator, data={"session_id": session.session_id, "state": session.state.value, "sources": ",".join(session.sources), "profile_id": session.profile_id})
        logger.info("Recording session %s created with sources %s", session_id, sources)
        return session

    def note_capture_errors(self, session_id: str, errors: List[Dict[str, Any]]) -> RecordingSession:
        """Record, with the take, which sources failed to record and why.

        ``errors`` are {"source_id", "error", "phase"}; one already noted for the same source and
        phase is replaced by the newer account rather than listed twice."""
        session = self.get_session(session_id)
        merged = {(item.get("source_id"), item.get("phase")): dict(item) for item in session.capture_errors}
        for item in errors:
            source_id = str(item.get("source_id") or "")
            if not source_id:
                continue
            phase = str(item.get("phase") or "start")
            merged[(source_id, phase)] = {"source_id": source_id, "error": str(item.get("error") or "Capture failed"),
                                          "phase": phase}
        updated = list(merged.values())
        if updated != session.capture_errors:
            self._commit_metadata(session, capture_errors=updated, updated_at=time.time())
        return session

    def _commit_metadata(self, session: RecordingSession, **changes) -> None:
        """Change a session only if the change reaches disk.

        The new state is written first, from a copy. Callers that hold the live session see the
        change only once the on-disk replacement has succeeded, so a full disk can never leave
        memory saying a take stopped, paused or was marked when the saved file says otherwise."""
        self._write_metadata(replace(session, **changes))
        for name, value in changes.items():
            setattr(session, name, value)

    def activate_session(self, session_id: str) -> RecordingSession:
        session = self.get_session(session_id)
        if session.state not in {RecordingState.REQUESTED, RecordingState.COUNTDOWN}:
            raise ValueError(f"Cannot activate session in state {session.state}")
        self._commit_metadata(session, state=RecordingState.ACTIVE, updated_at=time.time())
        self._blackbox_event("recording.state", actor=session.operator, data={"session_id": session.session_id, "state": "active"})
        logger.info("Recording session %s is now active", session_id)
        return session

    def create_encoded_take(self, session_id: str, *, source: str, operator: str,
                            ingest: Dict[str, Any]) -> RecordingSession:
        """Reserve a completed browser take, not a virtual-camera capture.

        The dedicated ingest adapter verifies bytes before registering an artifact.
        Keep start_session's confidence-only guard intact for every other caller.
        """
        self._validated_session_id(session_id)
        camera = self.cameras.get(source)
        if not source.startswith("p25d_") or (camera and (camera.location != "studio25d" or "studio25d" not in camera.tags)):
            raise ValueError("A registered 2.5D studio source is required")
        # A saved take can outlive the live camera registry (e.g. after restart).
        # This historical source label never registers or starts a camera feed.
        rule = self.room_policy("studio25d").get("recording", "allowed")
        if rule in {"never", "with_permission"}:
            raise PermissionError("Source policy does not permit this upload")
        directory = self._session_dir(session_id)
        directory.mkdir()  # No reuse or overwrite of another recording.
        session = RecordingSession(session_id, [source], "browser_original", operator,
                                   countdown_seconds=0, state=RecordingState.STOPPED,
                                   ended_at=time.time(), ingest=ingest)
        self._encoded_capture_timing(session)
        try:
            self._write_metadata(session)
        except Exception:
            # Only remove the empty reservation this call just created.
            if not any(directory.iterdir()):
                directory.rmdir()
            raise
        self._sessions[session_id] = session
        self._blackbox_event('recording.upload_started', actor=operator, data={
            'session_id':session_id, 'source':source, 'expected_bytes':ingest['spec']['bytes'],
            'take_id':ingest['spec']['take_id'], 'upload_started_at':ingest['upload_started_at']})
        return session

    def commit_encoded_take(self, session: RecordingSession, path: Path, digest: str, media: Dict[str, Any]) -> None:
        """Publish artifact and validated receipt in one durable metadata write."""
        if not session.ingest or path.parent != self._session_dir(session.session_id):
            raise ValueError("Encoded take does not belong to this recording")
        session.artifacts = [RecordingArtifact(path.name, ContainerFormat(path.suffix[1:]), path, path.stat().st_size)]
        self._encoded_capture_timing(session)
        session.ingest.update(state="complete", sha256=digest, media=media)
        session.updated_at = time.time()
        session.ingest["upload_completed_at"] = session.updated_at
        self._write_metadata(session)
        self._sessions[session.session_id] = session
        self._blackbox_event("recording.artifact", actor=session.operator, data={
            "session_id": session.session_id, "name": path.name,
            "size_bytes": path.stat().st_size, "sha256": digest, "capture_kind":
            "browser_voice_source" if session.ingest['spec']['mime'].startswith('audio/') else "browser_program_proxy"})

    @staticmethod
    def _encoded_capture_timing(session: RecordingSession) -> None:
        """Keep client capture time distinct from server transfer lifecycle time."""
        ingest = session.ingest
        if not ingest:
            return
        ingest.setdefault("upload_started_at", session.started_at)
        spec = ingest["spec"]; manifest = spec["manifest"]
        recordings = [*(manifest.get("recordings", []) if isinstance(manifest.get("recordings", []), list) else []),
                      *(manifest.get("sourceTracks", []) if isinstance(manifest.get("sourceTracks", []), list) else [])]
        selected = next((item for item in recordings if isinstance(item, dict) and item.get("id") == spec["take_id"]), None) if isinstance(recordings, list) else None
        media = manifest.get("media")
        if selected is None and isinstance(media, dict) and (media.get("id") or manifest.get("id")) == spec["take_id"]:
            selected = media
        def epoch(value):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                result = parsed.timestamp() if parsed.tzinfo is not None else None
                return result if result is not None and math.isfinite(result) else None
            except (AttributeError, ValueError, TypeError, OverflowError, OSError):
                return None
        started = epoch(selected.get("startedAt")) if selected else None
        source = "take_metadata" if started is not None else "unknown"
        if started is None and selected:
            base = epoch(manifest.get("startedAt")); offset = selected.get("offsetMs")
            if base is not None and type(offset) in (int, float) and math.isfinite(offset) and offset >= 0:
                candidate = base + offset / 1000
                if math.isfinite(candidate) and -62135596800 <= candidate <= 253402300799:
                    started = candidate; source = "production_offset"
        ingest["capture_timing"] = source
        if started is not None:
            session.started_at = started
            session.ended_at = started + spec["duration_ms"] / 1000

    def stop_session(self, session_id: str) -> RecordingSession:
        session = self.get_session(session_id)
        if session.state == RecordingState.STOPPED:
            return session
        ended_at = time.time()
        self._commit_metadata(session, state=RecordingState.STOPPED, ended_at=ended_at, updated_at=ended_at)
        
        # NEW: Stop pipeline session and log summary
        pipeline = self._pipeline_sessions.pop(session_id, None)
        if pipeline:
            summary = pipeline.stop()
            logger.info("Pipeline session %s stopped: %s", session_id, summary)
            # Preserve a reconstruction contract at the same stop boundary. It is
            # deliberately honest about missing media/avatar/mocap inputs instead
            # of manufacturing a "ready" bundle from event logs alone.
            try:
                from .recreate_bundle import blank_bundle, TimedEvent
                recreate = blank_bundle(
                    session_id=session_id, project_id="pubcast",
                    scene_id=session.preset or "unknown", take_id=session_id,
                )
                recreate.camera_timeline = [TimedEvent(
                    event_type=str(item.get("transition") or "cut"),
                    timestamp=float(item.get("t") or 0.0),
                    payload={"from_camera": item.get("from"), "to_camera": item.get("to"), "source": "director_switcher"},
                ) for item in getattr(pipeline, "_cameras", [])]
                recreate.chat_log = [TimedEvent(
                    event_type="chat.message", timestamp=float(item.get("t") or 0.0),
                    payload={"user":item.get("user"),"user_id":item.get("user_id"),"text":item.get("text")},
                ) for item in getattr(pipeline, "_chat", [])]
                if session.artifacts:
                    recreate.final_program_ref = str(session.artifacts[-1].file_path)
                recreate.export_status = "metadata_written"
                recreate.update_readiness()
                recreate_path = self._session_dir(session_id) / "recreate_bundle.json"
                recreate_path.write_text(recreate.to_json(), encoding="utf-8")
            except Exception:
                logger.exception("Recreate bundle write failed for %s", session_id)
            
            # Unregister from export routes
            try:
                from . import recording_pipeline_routes
                recording_pipeline_routes.unregister_pipeline_session(session_id)
            except ImportError:
                pass
        
        self._blackbox_event("recording.state", actor=session.operator, data={"session_id": session.session_id, "state": "stopped", "duration_sec": round((session.ended_at or time.time()) - session.started_at, 3)})
        logger.info("Recording session %s stopped", session_id)
        return session

    def pause_session(self, session_id: str, paused: bool) -> RecordingSession:
        session = self.get_session(session_id)
        if session.state not in {RecordingState.ACTIVE, RecordingState.PAUSED}:
            raise ValueError("Cannot pause a session that is not active")
        self._commit_metadata(session, state=RecordingState.PAUSED if paused else RecordingState.ACTIVE, updated_at=time.time())
        self._blackbox_event("recording.state", actor=session.operator, data={"session_id": session.session_id, "state": session.state.value, "paused": paused})
        logger.info("Recording session %s %s", session_id, "paused" if paused else "resumed")
        return session

    def archive_session(self, session_id: str) -> RecordingSession:
        session = self.get_session(session_id)
        if session.state != RecordingState.STOPPED:
            raise ValueError("Only stopped sessions can be archived")
        self._commit_metadata(session, state=RecordingState.ARCHIVED, updated_at=time.time())
        logger.info("Recording session %s archived", session_id)
        return session

    def mark_moment(self, session_id: str, label: str, operator: Optional[str] = None) -> RecordingMarker:
        session = self.get_session(session_id)
        marker = RecordingMarker(timestamp=time.time(), label=label, operator=operator)
        self._commit_metadata(session, markers=[*session.markers, marker], updated_at=marker.timestamp)
        self._blackbox_event("recording.state", actor=operator or session.operator, data={"session_id": session.session_id, "state": session.state.value, "marker_label": label})
        logger.info("Session %s :: marker '%s'", session_id, label)
        return marker

    def register_artifact(
        self,
        session_id: str,
        file_path: Path,
        *,
        name: Optional[str] = None,
        format: Optional[ContainerFormat] = None,
        synthetic: bool = False,
    ) -> RecordingArtifact:
        """Register a captured media file on a recording session.

        ``synthetic`` marks a test-pattern recording so it is not mistaken for real video.
        """
        session = self.get_session(session_id)
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)

        artifact_format = format
        if artifact_format is None:
            suffix = path.suffix.lstrip(".").lower()
            try:
                artifact_format = ContainerFormat(suffix)
            except ValueError:
                artifact_format = self.get_profile(session.profile_id).container

        # Media from outside the take (a camera on removable or remote storage) is copied in, so it
        # is still there after a restart and cannot be confused with a same-named file of another source.
        # Capture workers already write inside the take and are registered where they are.
        session_dir = self._session_dir(session_id)
        source = path.resolve()
        source_key = None
        owned_path = None
        previous_copy = None
        if source.parent != session_dir.resolve():
            source_key = hashlib.sha256(os.fsencode(os.path.normcase(str(source)))).hexdigest()
            previous_copy = next((a for a in session.artifacts if a.source_key == source_key), None)
            # The final name appears only after the whole copy is flushed to disk.
            with tempfile.TemporaryDirectory(dir=session_dir, prefix=".source-copy-") as staging:
                pending = Path(staging) / "media"
                with source.open("rb") as stream, pending.open("xb") as output:
                    shutil.copyfileobj(stream, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                owned_path = session_dir / f"source-{uuid.uuid4().hex}{path.suffix}"
                pending.replace(owned_path)

        try:
            artifact_path = owned_path or path
            artifact = RecordingArtifact(
                name=name or path.name,
                format=artifact_format,
                file_path=artifact_path,
                size_bytes=artifact_path.stat().st_size,
                synthetic=bool(synthetic),
                source_key=source_key,
            )
            kept = [a for a in session.artifacts
                    if a is not previous_copy and Path(a.file_path).resolve() != source]
            self._commit_metadata(session, artifacts=[*kept, artifact], updated_at=time.time())
        except BaseException:
            if owned_path is not None:
                owned_path.unlink(missing_ok=True)
            raise
        if (previous_copy is not None and previous_copy.file_path.parent.resolve() == session_dir.resolve()
                and previous_copy.file_path.name.startswith("source-")):
            try:
                previous_copy.file_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Superseded media copy retained at %s", previous_copy.file_path)
        self._blackbox_event(
            "recording.artifact",
            actor=session.operator,
            data={
                "session_id": session.session_id,
                "name": artifact.name,
                "format": artifact.format.value,
                "size_bytes": artifact.size_bytes,
            },
        )
        return artifact

    def attach_data_file(self, session_id: str, file_path: Path) -> str:
        """Record a non-media file of a take (show data, the mode record) so it is kept with the take.

        The file must already be a regular file directly in the session's own folder; only its name is stored,
        the same way media artifacts are relinked after a restart or an import.
        """
        session = self.get_session(session_id)
        path = Path(file_path)
        session_dir = self._session_dir(session_id)
        if path.parent.resolve() != session_dir.resolve() or not path.is_file() or path.is_symlink():
            raise ValueError(f"Data file must be a regular file in the session folder: {path.name}")
        if path.name == f"{session_id}.json" or not _DATA_FILE_NAME.fullmatch(path.name):
            raise ValueError(f"Not a valid data file name: {path.name}")
        if path.name not in session.data_files:
            session.data_files.append(path.name)
        session.updated_at = time.time()
        self._write_metadata(session)
        return path.name

    # ------------------------------------------------------------------
    # Import / export
    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        """Return path to ffmpeg binary, or None if not installed."""
        import shutil as _shutil
        return _shutil.which("ffmpeg")

    @staticmethod
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

    def _opus_export_bitrate(self, source: Path, requested: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Respect libopus' per-channel encoder limit for a derived WebM.

        AAC production profiles may request 320 kb/s, which libopus rejects for
        mono. Probe the actual source so stereo keeps its requested bitrate.
        This affects derived encoding only; the original stays byte-identical.
        """
        normalized = self._ffmpeg_bitrate(requested)
        if not normalized:
            return requested, None
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([kKmM]?)", normalized)
        if not match:
            return requested, None
        try:
            bitrate = int(float(match[1]) * {"": 1, "k": 1000, "m": 1_000_000}[match[2].lower()])
        except (ValueError, OverflowError):
            return requested, None
        if bitrate <= 256_000:
            return requested, None
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return requested, "Opus channel probe unavailable; requested bitrate retained; conversion may fail"
        try:
            probe = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a:0",
                                    "-show_entries", "stream=channels", "-of", "csv=p=0", str(source)],
                                   capture_output=True, text=True, check=True, timeout=10)
            channels = int(probe.stdout.strip())
            if not 1 <= channels <= 255:
                raise ValueError("Unsupported source channel count")
        except (OSError, ValueError, subprocess.SubprocessError):
            return requested, "Opus source channels could not be measured; requested bitrate retained; conversion may fail"
        maximum = 256_000 * channels
        if bitrate <= maximum:
            return requested, None
        return str(maximum), (f"Opus bitrate limited from {normalized} to {maximum} bps for {channels} "
                              "source channel(s); original media bytes preserved")

    def _transcode_artifact(
        self,
        src: Path,
        dst: Path,
        profile: EncodingProfile,
    ) -> bool:
        """
        Transcode a single source file to the target format using FFmpeg.
        Returns True on success, False on failure (src is kept, dst cleaned up).
        Runs synchronously — call from a thread or export_session which is
        already expected to be a blocking operation.
        """
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            logger.warning("ffmpeg not found — conversion unavailable; source media retained")
            return False

        cmd: List[str] = [ffmpeg, "-y", "-i", str(src)]

        if profile.is_audio_only:
            # Strip video, encode audio
            cmd += ["-vn"]
            if profile.audio_codec:
                cmd += ["-acodec", profile.audio_codec]
            audio_bitrate = self._ffmpeg_bitrate(profile.audio_bitrate)
            if audio_bitrate:
                cmd += ["-b:a", audio_bitrate]
        else:
            if profile.video_codec:
                video_codec = "libx264" if profile.video_codec == "h264" else profile.video_codec
                cmd += ["-vcodec", video_codec]
            if profile.audio_codec:
                cmd += ["-acodec", profile.audio_codec]
            video_bitrate = self._ffmpeg_bitrate(profile.video_bitrate)
            if video_bitrate:
                cmd += ["-b:v", video_bitrate]
            audio_bitrate = self._ffmpeg_bitrate(profile.audio_bitrate)
            if audio_bitrate:
                cmd += ["-b:a", audio_bitrate]
            if profile.resolution:
                cmd += ["-s", profile.resolution]
            if profile.frame_rate:
                cmd += ["-r", profile.frame_rate]
            if profile.video_codec == "h264":
                cmd += ["-pix_fmt", "yuv420p"]

        cmd.append(str(dst))

        logger.info("FFmpeg transcode: %s → %s", src.name, dst.name)
        logger.debug("FFmpeg cmd: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10-minute hard limit per file
            )
            if result.returncode != 0:
                logger.error(
                    "FFmpeg failed (rc=%d) for %s:\n%s",
                    result.returncode, src.name, result.stderr[-2000:]
                )
                dst.unlink(missing_ok=True)
                return False
            logger.info(
                "FFmpeg complete: %s → %s (%.1f MB)",
                src.name, dst.name, dst.stat().st_size / (1024 * 1024)
            )
            return True
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out transcoding %s", src.name)
            dst.unlink(missing_ok=True)
            return False
        except Exception as exc:
            logger.error("FFmpeg error transcoding %s: %s", src.name, exc)
            dst.unlink(missing_ok=True)
            return False

    @staticmethod
    def _file_digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()

    def export_session(self, session_id: str, *, container: ContainerFormat) -> Path:
        """Export immutable source bytes, portable metadata and optional derivatives.

        Conversion never replaces the source. Missing media fails the operation;
        unavailable conversion is described in the manifest. Each request has an
        independent staging directory and publishes a completed archive atomically.
        """
        session = self.get_session(session_id)
        if session.state not in {RecordingState.STOPPED, RecordingState.ARCHIVED}:
            raise ValueError("Stop the recording before exporting immutable media")
        if not session.artifacts and not session.data_files:
            raise ValueError("No recorded media is available for export")
        if session.ingest and session.ingest.get("state") != "complete":
            raise ValueError("Encoded take has not completed validation")
        if len({Path(a.file_path).resolve() for a in session.artifacts}) != len(session.artifacts):
            raise ValueError("Distinct recording sources resolve to the same file; relink original media before export")
        for artifact in session.artifacts:
            if not artifact.file_path.is_file():
                raise ValueError(f"Missing recording artifact: {artifact.name}")
        data_paths = [self._session_dir(session_id) / name for name in session.data_files]
        for path in data_paths:
            if not path.is_file():
                raise ValueError(f"Missing recording data file: {path.name}")
        profile = self._profiles.get(session.profile_id)
        archive_path = self.exports_dir / f"{session_id}.{container.value}.{uuid.uuid4().hex[:12]}.zip"
        metadata_name = f"{session_id}.json"
        metadata = session.to_dict()
        metadata["artifacts"] = []
        manifest = {"schema": "pubcast-recording-export/1", "session_id": session_id,
                    "requested_container": container.value, "files": {}, "derived": [], "warnings": []}
        encoder_available = bool(self._find_ffmpeg())
        if profile is None:
            manifest["warnings"].append("Encoding profile unavailable: original media preserved; no conversion performed")
        if not encoder_available:
            manifest["warnings"].append("FFmpeg unavailable: original media preserved; no conversion performed")
        with tempfile.TemporaryDirectory(prefix="recording-export-", dir=self.exports_dir) as staging_name:
            staging = Path(staging_name)
            pending = staging / "bundle.zip"
            with ZipFile(pending, "w", ZIP_DEFLATED) as bundle:
                for index, artifact in enumerate(session.artifacts, 1):
                    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", artifact.file_path.name).rstrip(" .") or "source"
                    source_member = f"media/{index:04d}_{safe_name}"
                    # Hash the exact bytes being archived, including large sources.
                    digest, size = hashlib.sha256(), 0
                    entry = ZipInfo(source_member)
                    entry.compress_type = ZIP_STORED
                    with artifact.file_path.open("rb") as source, bundle.open(entry, "w", force_zip64=True) as target:
                        for block in iter(lambda: source.read(1 << 20), b""):
                            target.write(block); digest.update(block); size += len(block)
                    manifest["files"][source_member] = {"sha256": digest.hexdigest(), "bytes": size}
                    if session.ingest and (digest.hexdigest() != session.ingest.get("sha256") or size != session.ingest["spec"]["bytes"]):
                        raise ValueError("Original encoded take failed its saved integrity check")
                    metadata["artifacts"].append({"name": artifact.name, "format": artifact.format.value,
                                                  "file_path": source_member,
                                                  "size_bytes": size,
                                                  **({"synthetic": True} if artifact.synthetic else {})})
                    if profile and encoder_available and not (session.profile_id == "browser_original" and artifact.format == container):
                        name = f"{index:04d}_{Path(safe_name).stem}.{container.value}"
                        out_path = staging / name
                        # Select codecs compatible with the requested container,
                        # without assigning the source any new quality/provenance.
                        video, audio = {
                            ContainerFormat.MP4: ("h264", "aac"),
                            ContainerFormat.WEBM: ("libvpx-vp9", "libopus"),
                            ContainerFormat.MOV: ("prores_ks", "pcm_s24le"),
                            ContainerFormat.WAV: (None, "pcm_s16le"),
                        }[container]
                        audio_bitrate = profile.audio_bitrate
                        if audio == "libopus":
                            audio_bitrate, adjustment = self._opus_export_bitrate(artifact.file_path, audio_bitrate)
                            if adjustment:
                                manifest["warnings"].append(adjustment)
                        export_profile = EncodingProfile(
                            profile_id=profile.profile_id, name=profile.name, container=container,
                            video_codec=video, audio_codec=audio, video_bitrate=profile.video_bitrate,
                            audio_bitrate=audio_bitrate, resolution=profile.resolution,
                            frame_rate=profile.frame_rate, description=profile.description,
                            is_audio_only=profile.is_audio_only or container == ContainerFormat.WAV)
                        if self._transcode_artifact(artifact.file_path, out_path, export_profile) and out_path.is_file():
                            member = "renders/" + name
                            bundle.write(out_path, arcname=member, compress_type=ZIP_STORED)
                            manifest["files"][member] = {"sha256": self._file_digest(out_path), "bytes": out_path.stat().st_size}
                            manifest["derived"].append({"path": member, "source_member": source_member,
                                                        "container": container.value, "source_master": False,
                                                        "audio_bitrate_setting": self._ffmpeg_bitrate(export_profile.audio_bitrate)})
                        else:
                            manifest["warnings"].append(f"Conversion failed for {artifact.name}; original media preserved")
                # Show data and the mode record are part of the take, byte for byte; they are never converted.
                for path in data_paths:
                    member = "data/" + path.name
                    digest, size = hashlib.sha256(), 0
                    entry = ZipInfo(member)
                    entry.compress_type = ZIP_STORED
                    with path.open("rb") as source, bundle.open(entry, "w", force_zip64=True) as target:
                        for block in iter(lambda: source.read(1 << 20), b""):
                            target.write(block); digest.update(block); size += len(block)
                    manifest["files"][member] = {"sha256": digest.hexdigest(), "bytes": size}
                metadata_bytes = json.dumps(metadata, indent=2).encode("utf-8")
                bundle.writestr(metadata_name, metadata_bytes)
                manifest["files"][metadata_name] = {"sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                                                    "bytes": len(metadata_bytes)}
                bundle.writestr("EXPORT_MANIFEST.json", json.dumps(manifest, indent=2))
            os.replace(pending, archive_path)
        logger.info("Exported original media and portable metadata: %s", archive_path)
        return archive_path

    def import_session(self, bundle_path: Path, *, operator: Optional[str] = None) -> RecordingSession:
        """Validate, stage and relink a bundle without overwriting another take."""
        if not bundle_path.is_file():
            raise FileNotFoundError(bundle_path)
        created_directory = False
        session_dir = None
        try:
            with ZipFile(bundle_path, "r") as bundle:
                members = bundle.infolist()
                names = [item.filename for item in members]
                if len(names) > 4096 or len({name.casefold() for name in names}) != len(names):
                    raise ValueError("Recording bundle contains duplicate or excessive entries")
                limit = int(os.environ.get("PUBCAST_RECORDING_IMPORT_MAX_BYTES", str(64 * 1024 ** 3)))
                total = sum(item.file_size for item in members)
                if total > limit or total + 64 * 1024 ** 2 > shutil.disk_usage(self.recordings_dir).free:
                    raise ValueError("Recording bundle exceeds the available import storage budget")
                metadata_candidates = [name for name in names if "/" not in name and name.endswith(".json")
                                       and name != "EXPORT_MANIFEST.json"]
                if len(metadata_candidates) != 1:
                    raise ValueError("Bundle must contain one recording metadata file")
                metadata_name = metadata_candidates[0]
                if bundle.getinfo(metadata_name).file_size > 8 * 1024 ** 2:
                    raise ValueError("Recording metadata is too large")
                payload = json.loads(bundle.read(metadata_name))
                if not isinstance(payload, dict):
                    raise ValueError("Invalid recording metadata")
                session_id = self._validated_session_id(payload.get("session_id"))
                session_dir = self._session_dir(session_id)
                if session_dir.exists() or session_id in self._sessions:
                    raise ValueError(f"Session directory already exists for {session_id}")
                try:
                    session = self._session_from_dict(payload)
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("Invalid recording metadata") from exc
                if session.ingest and operator is not None:
                    session.ingest.setdefault("original_operator", session.operator)
                    session.operator = operator
                media_members = [name for name in names if name.startswith("media/") and not name.endswith("/")]
                for member in media_members:
                    leaf = member.removeprefix("media/")
                    if not leaf or leaf in {".", ".."} or "/" in leaf or "\\" in leaf or ":" in leaf:
                        raise ValueError("Invalid recording media path")
                media_names = {Path(name).name for name in media_members}
                if len(media_names) != len(media_members):
                    raise ValueError("Duplicate recording media names")
                if any(artifact.file_path.name not in media_names for artifact in session.artifacts):
                    raise ValueError("Missing media referenced by recording metadata")
                data_members = [name for name in names if name.startswith("data/") and not name.endswith("/")]
                data_names = {name.removeprefix("data/") for name in data_members}
                if (len(data_names) != len(data_members)
                        or not all(_DATA_FILE_NAME.fullmatch(leaf) for leaf in data_names)
                        or data_names & media_names or f"{session_id}.json" in data_names):
                    raise ValueError("Invalid recording data path")
                if set(session.data_files) != data_names:
                    raise ValueError("Recording data files do not match the recording metadata")
                media_members = media_members + data_members   # both are extracted and verified the same way
                manifest = None
                if "EXPORT_MANIFEST.json" in names:
                    if bundle.getinfo("EXPORT_MANIFEST.json").file_size > 8 * 1024 ** 2:
                        raise ValueError("Export integrity manifest is too large")
                    manifest = json.loads(bundle.read("EXPORT_MANIFEST.json"))
                    if not isinstance(manifest, dict) or manifest.get("schema") != "pubcast-recording-export/1":
                        raise ValueError("Unsupported export integrity manifest")
                    files = manifest.get("files")
                    if not isinstance(files, dict) or not set(media_members + [metadata_name]).issubset(files):
                        raise ValueError("Incomplete export integrity manifest")
                    if not set(files).issubset(names):
                        raise ValueError("Missing files in export integrity manifest")
                else:
                    logger.warning("Importing legacy recording bundle without an integrity manifest")
                with tempfile.TemporaryDirectory(prefix=".recording-import-", dir=self.recordings_dir) as staging_name:
                    staging = Path(staging_name)
                    for member in (list(manifest["files"]) if manifest else media_members):
                        digest, size = hashlib.sha256(), 0
                        target = staging / Path(member).name if member in media_members else None
                        with bundle.open(member) as source:
                            out = target.open("xb") if target else None
                            try:
                                for block in iter(lambda: source.read(1 << 20), b""):
                                    digest.update(block); size += len(block)
                                    if out is not None:
                                        out.write(block)
                            finally:
                                if out is not None:
                                    out.close()
                        if manifest:
                            spec = manifest["files"][member]
                            if not isinstance(spec, dict) or spec.get("sha256") != digest.hexdigest() or spec.get("bytes") != size:
                                raise ValueError(f"Recording integrity check failed: {member}")
                    # Reserve the destination exclusively after all validation.
                    session_dir.mkdir(exist_ok=False)
                    created_directory = True
                    for child in staging.iterdir():
                        child.rename(session_dir / child.name)
                    for artifact in session.artifacts:
                        artifact.size_bytes = artifact.file_path.stat().st_size
                    self._write_metadata(session)
                self._sessions[session_id] = session
                return session
        except Exception:
            if created_directory and session_dir is not None:
                shutil.rmtree(session_dir)
            raise

    # ------------------------------------------------------------------
    # Storage & diagnostics
    def storage_status(self) -> Dict[str, Any]:
        usage_bytes = sum(
            file.stat().st_size
            for file in self.recordings_dir.glob("**/*")
            if file.is_file()
        )
        self._storage_cache["recorded_gb"] = round(usage_bytes / (1024 ** 3), 2)
        self._storage_cache["local_free_gb"] = round(shutil.disk_usage(self.recordings_dir).free / (1024 ** 3), 2)
        return self._storage_cache

    def set_storage_status(self, **kwargs) -> None:
        self._storage_cache.update(kwargs)

    # ------------------------------------------------------------------
    # NEW: Pipeline event logging methods
    def record_camera_switch(self, session_id: str, from_cam: str, to_cam: str, transition: str = "cut") -> None:
        """Log camera switch to active pipeline session."""
        pipeline = self._pipeline_sessions.get(session_id)
        if pipeline:
            pipeline.record_camera_switch(from_cam, to_cam, transition)

    def record_chat_message(self, session_id: str, user: str, text: str, user_id: str = "") -> None:
        """Log chat message to active pipeline session."""
        pipeline = self._pipeline_sessions.get(session_id)
        if pipeline:
            pipeline.record_chat(user, text, user_id)

    def add_marker(self, session_id: str, label: str, operator: str = "") -> None:
        """Add manual marker to active pipeline session."""
        pipeline = self._pipeline_sessions.get(session_id)
        if pipeline:
            pipeline.record_marker(label, operator)

    def get_pipeline_session(self, session_id: str):
        """Get pipeline session for export operations."""
        return self._pipeline_sessions.get(session_id)

    # ------------------------------------------------------------------
    def _write_metadata(self, session: RecordingSession) -> None:
        metadata_path = self._session_dir(session.session_id) / f"{session.session_id}.json"
        write_json(metadata_path, session.to_dict())

    def _session_from_dict(self, payload: Dict) -> RecordingSession:
        ingest = payload.get("ingest")
        if ingest is not None:
            if not isinstance(ingest, dict) or ingest.get("schema") != "pubcast-encoded-take/1" or ingest.get("state") not in {"uploading", "complete", "abandoned"}:
                raise ValueError("Invalid encoded take metadata")
            if not isinstance(ingest.get("spec"), dict) or not isinstance(ingest.get("received_bytes"), int) or not isinstance(ingest.get("next_index"), int):
                raise ValueError("Invalid encoded take progress")
            spec = ingest["spec"]
            if (type(spec.get("bytes")) is not int or not 0 < spec["bytes"] <= 2 * 1024 ** 3
                    or type(spec.get("duration_ms")) is not int or not 0 < spec["duration_ms"] <= 24 * 3600 * 1000
                    or not isinstance(spec.get("manifest"), dict) or not isinstance(spec.get("take_id"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", str(spec.get("chain", "")))
                    or not 0 <= ingest["received_bytes"] <= spec["bytes"] or ingest["next_index"] < 0):
                raise ValueError("Invalid encoded take specification")
            if not re.fullmatch(r"[a-f0-9]{64}", str(ingest.get("chain", ""))):
                raise ValueError("Invalid encoded take integrity proof")
            if ingest["state"] == "complete" and not re.fullmatch(r"[a-f0-9]{64}", str(ingest.get("sha256", ""))):
                raise ValueError("Invalid completed take checksum")
        session = RecordingSession(
            session_id=payload["session_id"],
            sources=list(payload.get("sources", [])),
            profile_id=payload["profile_id"],
            operator=payload.get("operator", "unknown"),
            preset=payload.get("preset"),
            host_override=payload.get("host_override", False),
            countdown_seconds=payload.get("countdown_seconds", 5),
            state=RecordingState(payload.get("state", RecordingState.STOPPED.value)),
            started_at=payload.get("started_at", time.time()),
            updated_at=payload.get("updated_at", time.time()),
            ended_at=payload.get("ended_at"),
            recovery=payload.get("recovery"),
            ingest=payload.get("ingest"),
            mode=str(payload.get("mode") or "camcorder"),
            record_data=bool(payload.get("record_data", False)),
        )
        if session.mode not in RECORDING_MODES:
            raise ValueError(f"Unknown recording mode {session.mode!r}")
        data_files = payload.get("data_files") or []
        if not isinstance(data_files, list) or not all(
                isinstance(name, str) and _DATA_FILE_NAME.fullmatch(name) and name != f"{session.session_id}.json"
                for name in data_files):
            raise ValueError("Invalid recording data file list")
        session.data_files = list(dict.fromkeys(data_files))
        session.capture_errors = _capture_errors_from(payload.get("capture_errors"))
        session.artifacts = [
            RecordingArtifact(
                name=item["name"],
                format=ContainerFormat(item["format"]),
                file_path=self._session_dir(session.session_id) / Path(str(item["file_path"]).replace("\\", "/")).name,
                size_bytes=item.get("size_bytes", 0),
                synthetic=bool(item.get("synthetic", False)),
                source_key=item.get("source_key") or None,
            )
            for item in payload.get("artifacts", [])
        ]
        session.markers = [
            RecordingMarker(
                timestamp=item["timestamp"],
                label=item["label"],
                operator=item.get("operator"),
            )
            for item in payload.get("markers", [])
        ]
        self._encoded_capture_timing(session)
        return session


def _capture_errors_from(value: Any) -> List[Dict[str, Any]]:
    """Saved capture failures: the list this line writes, or the {source_id: error} map of takes
    saved by the codex/main-debug line, read as start-or-stop failures with no phase."""
    if not value:
        return []
    if isinstance(value, dict):
        return [{"source_id": str(k), "error": str(v), "phase": "unknown"} for k, v in value.items()]
    if not isinstance(value, list) or not all(isinstance(item, dict) and item.get("source_id") for item in value):
        raise ValueError("Invalid capture error list")
    return [{"source_id": str(item["source_id"]), "error": str(item.get("error") or "Capture failed"),
             "phase": str(item.get("phase") or "unknown")} for item in value]


# ----------------------------------------------------------------------
# Factory

def create_recording_service(base_dir: Path, cameras: CameraManager, blackbox_witness: Optional[Any] = None) -> RecordingService:
    service = RecordingService(base_dir=base_dir, cameras=cameras, blackbox_witness=blackbox_witness)
    service.register_profile(EncodingProfile(
        profile_id="browser_original", name="Original browser Program take",
        container=ContainerFormat.WEBM, video_codec=None, audio_codec=None,
        video_bitrate=None, audio_bitrate=None, resolution=None, frame_rate=None,
        description="Original encoded browser bytes; no source-master or 4K claim"))
    service.register_profile(
        EncodingProfile(
            profile_id="prores_hq",
            name="Apple ProRes HQ",
            container=ContainerFormat.MOV,
            video_codec="prores",
            audio_codec="pcm_s24le",
            video_bitrate="880Mbps",
            audio_bitrate="1.5Mbps",
            resolution="3840x2160",
            frame_rate="60",
            description="Mastering quality profile",
        )
    )
    service.register_profile(
        EncodingProfile(
            profile_id="broadcast_mp4",
            name="Broadcast MP4",
            container=ContainerFormat.MP4,
            video_codec="h264",
            audio_codec="aac",
            video_bitrate="50Mbps",
            audio_bitrate="320kbps",
            resolution="1920x1080",
            frame_rate="59.94",
            description="Delivery-ready broadcast encode",
        )
    )
    service.register_profile(
        EncodingProfile(
            profile_id="web_stream",
            name="Web Stream",
            container=ContainerFormat.WEBM,
            video_codec="vp9",
            audio_codec="opus",
            video_bitrate="8Mbps",
            audio_bitrate="192kbps",
            resolution="1280x720",
            frame_rate="30",
            description="Low-latency web playback",
        )
    )
    service.register_profile(
        EncodingProfile(
            profile_id="audio_only",
            name="Audio Only WAV",
            container=ContainerFormat.WAV,
            video_codec=None,
            audio_codec="pcm_s16le",
            video_bitrate=None,
            audio_bitrate="1Mbps",
            resolution=None,
            frame_rate=None,
            description="High fidelity audio capture",
            is_audio_only=True,
        )
    )

    service.configure_room_privacy(
        {
            "pub": {"recording": "allowed", "notice": "This is a public space that may be recorded."},
            "green": {"recording": "with_permission", "notice": "Recording requires explicit consent."},
            "conference": {"recording": "host_policy", "notice": "Recording policy defined by meeting host."},
            "studio": {"recording": "expected", "notice": "Production area"},
            "dressing": {"recording": "never", "notice": "Private space"},
        }
    )
    return service




