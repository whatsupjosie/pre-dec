"""
modules/production_routes.py — Camera + Recording REST API
==============================================================================
Wires CameraManager and RecordingService into FastAPI.
Also provides WebSocket broadcast helpers so the control room
console receives live updates on camera switches and recording state.

Usage in main.py:
    from modules.cameras import create_default_cameras
    from modules.recording import create_recording_service
    from modules.production_routes import create_production_router

    cameras = create_default_cameras()
    recording = create_recording_service(DATA_DIR, cameras)
    app.include_router(create_production_router(cameras, recording, hub))

Rear View Foresight LLC — Feic Mo Chroí — 2026-03-24T08:00Z
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from zipfile import BadZipFile
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse

from modules.audio_input_spec import AudioInputError, parse_audio_input
from modules.cameras import CameraManager, CameraSource, CameraTransport
from modules.recording import (
    RecordingService,
    RecordingState,
    ContainerFormat,
)
from modules.route_security import bound_actor, require_role, current_identity, security
from modules.persistence import sanitize_filename, unique_child_path
from modules.runtime_control_routes import create_runtime_control_router
from modules.stage_compat_routes import create_stage_compat_router
from modules.blackbox_runtime import BlackBoxRuntimeWitness
from modules.studio_camera_preflight import PreflightRefusal, all_camera_visibility, camera_visibility_report, recording_preflight, studio_readiness
from modules.program_audio import ProgramAudioState, apply_audio_event
from modules.program_audio_routes import create_program_audio_router
from modules.participant_audio import create_participant_audio_router
from starlette.requests import HTTPConnection
from modules.studio_console_actions import confirmed_stop_session_id, execute_studio_action, list_studio_actions
from modules.recording_modes import MODES as RECORDING_MODE_DESCRIPTIONS, ModeRequestError, RecordingModeController, default_sources

logger = logging.getLogger("pubcast.production")


class CaptureNotFinished(RuntimeError):
    """A take's media is not all finished and added to it yet; stopping again retries."""


async def _json_dict(request: Request) -> Dict[str, Any]:
    """Parse a request body as a JSON object with clean 400s."""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Malformed JSON body: {exc.msg}")
    except Exception as exc:
        raise HTTPException(400, f"Invalid JSON body: {exc}")
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON body must be an object")
    return body


def _string_field(body: Dict[str, Any], key: str, *, default: str = "", required: bool = False,
                  max_length: int = 256) -> str:
    value = body.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} must be a string")
    value = value.strip()
    if required and not value:
        raise HTTPException(400, f"{key} required")
    if len(value) > max_length:
        raise HTTPException(400, f"{key} must be <= {max_length} characters")
    return value


def _bool_field(body: Dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = body.get(key, default)
    if not isinstance(value, bool):
        raise HTTPException(400, f"{key} must be a boolean")
    return value


def _numeric_field(body: Dict[str, Any], key: str, *, default: float | int, minimum: float | None = None) -> float:
    value = body.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(400, f"{key} must be numeric")
    value = float(value)
    if minimum is not None and value < minimum:
        raise HTTPException(400, f"{key} must be >= {minimum}")
    return value


def _vector3(body: Dict[str, Any], key: str) -> List[float]:
    value = body.get(key, [0.0, 0.0, 0.0])
    if not isinstance(value, list) or len(value) != 3:
        raise HTTPException(400, f"{key} must be a 3-item array")
    try:
        vector = [float(v) for v in value]
    except (TypeError, ValueError):
        raise HTTPException(400, f"{key} must contain only numeric values")
    return vector


def _string_list(body: Dict[str, Any], key: str, *, required: bool = False) -> List[str]:
    value = body.get(key, [])
    if value in (None, ""):
        value = []
    if not isinstance(value, list):
        raise HTTPException(400, f"{key} must be an array")
    cleaned: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise HTTPException(400, f"{key} items must be strings")
        item = item.strip()
        if not item:
            raise HTTPException(400, f"{key} items must not be blank")
        cleaned.append(item)
    if required and not cleaned:
        raise HTTPException(400, f"{key} must contain at least one value")
    return cleaned


def create_production_router(
    cameras: CameraManager,
    recording: RecordingService,
    hub: Any,
    blackbox: Optional[BlackBoxRuntimeWitness] = None,
    program_audio_state: Optional[ProgramAudioState] = None,
    include_overlapping_compat_routes: bool = True,
    emergency_snapshot: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
) -> APIRouter:
    """Create the production API router."""
    async def protect_encoded_take(request: HTTPConnection):
        session_id = request.path_params.get("session_id")
        if request.url.path.startswith("/api/studio/actions/recording."):
            try:
                body = await request.json()
                session_id = body.get("session_id") if isinstance(body, dict) else None
            except ValueError:
                pass
        if not isinstance(session_id, str):
            return
        try:
            session = recording.get_session(session_id)
        except KeyError:
            return
        if getattr(session, "ingest", None):
            identity = await current_identity(request, await security(request))
            if not identity.get("authenticated") or identity.get("user_id") != session.operator:
                raise HTTPException(404, "Take not found")
            if request.method != "GET" and not request.url.path.endswith("/export"):
                raise HTTPException(409, "Encoded take originals are immutable; use their upload controls")
    router = APIRouter(tags=["Production"], dependencies=[Depends(protect_encoded_take)])
    program_audio_state = program_audio_state or ProgramAudioState()
    capture_engine = None
    try:
        from modules.capture import FFmpegCaptureEngine
        capture_engine = FFmpegCaptureEngine()
    except Exception as exc:
        logger.warning("FFmpeg capture engine unavailable: %s", exc)

    # Compatibility bridge routes are mounted here because main.py already mounts
    # production_routes after the core runtime managers exist. These bridge routers
    # do not own the systems; they delegate to existing managers and return explicit
    # unavailable payloads instead of letting the panoramic/control-room UI hit 404s.
    router.include_router(create_runtime_control_router(include_overlapping_routes=include_overlapping_compat_routes))
    router.include_router(create_stage_compat_router(hub=hub, cameras=cameras, recording=recording, include_overlapping_routes=include_overlapping_compat_routes))
    program_audio_router = create_program_audio_router(program_audio_state, blackbox=blackbox, hub=hub)
    router.include_router(program_audio_router)
    router.include_router(create_participant_audio_router())

    def _blackbox_event(event_type: str, *, source: str, actor: str = "SYS", data: Optional[Dict[str, Any]] = None) -> None:
        if blackbox is not None:
            blackbox.record_event(event_type, source=source, actor=actor, data=data or {})

    # Microphone chosen for a recording at start time (see modules/audio_input_spec.py), kept until the capture starts.
    session_audio_inputs: Dict[str, Any] = {}
    capture_start_tasks: Dict[str, asyncio.Task] = {}
    capture_stop_tasks: Dict[str, asyncio.Task] = {}
    # Camcorder, data only or main camera only (modules/recording_modes.py); one controller for every route.
    recording_modes = RecordingModeController(cameras=cameras, recording=recording, capture_engine=capture_engine, hub=hub)
    session_mode_options: Dict[str, Dict[str, bool]] = {}
    # Finished recordings that could not be added to their take (a full disk, say). The file stays on
    # disk and here, and the next stop, PANIC or shutdown tries again; nothing is forgotten.
    unregistered_outputs: Dict[str, List[Dict[str, Any]]] = {}

    def _note_capture_errors(session_id: str, errors: List[Dict[str, Any]]) -> None:
        """Keep failed sources with the take. A record that cannot be written is logged, never raised:
        the operator has already been told, and the failure must not stop the take from closing."""
        note = getattr(recording, "note_capture_errors", None)
        if not errors or not callable(note):
            return
        try:
            note(session_id, errors)
        except Exception:
            logger.exception("Could not save the capture failures of %s", session_id)

    def _engine_failures(session_id: str, phase: Optional[str] = None) -> List[Dict[str, Any]]:
        failures = getattr(capture_engine, "failures", None)
        items = failures(session_id) if callable(failures) else []
        return [item for item in items if phase is None or item.get("phase") == phase]

    def _start_errors(session) -> List[Dict[str, Any]]:
        """What could not start, for the start reply: the camcorder path's failures, then the mode's."""
        items = [dict(item) for item in getattr(session, "capture_errors", []) or [] if item.get("phase") == "start"]
        seen = {item.get("source_id") for item in items}
        for item in recording_modes.start_problems(session.session_id):
            if item.get("source_id") not in seen:
                items.append(item)
        return items

    async def _start_capture_for_session(session) -> List[str]:
        # The mode starts first: the show data needs no FFmpeg, and data-only and main-camera
        # takes decide their own picture and sound.
        if session.state == RecordingState.ACTIVE:
            mode_paths = await recording_modes.begin(session, audio_input=session_audio_inputs.get(session.session_id),
                                                     **session_mode_options.pop(session.session_id, {}))
            if recording_modes.owns_capture(session.session_id):
                return [str(path) for path in mode_paths]
        if session.state != RecordingState.ACTIVE:
            return []
        if capture_engine is None or not getattr(capture_engine, "available", False):
            if session.sources:
                # The take is open but nothing is recording it; say so with the take, not only in the log.
                _note_capture_errors(session.session_id, [
                    {"source_id": source_id, "phase": "start",
                     "error": "FFmpeg is not available on this computer, so nothing was recorded for this source"}
                    for source_id in session.sources])
            return []
        session_id = session.session_id
        source_objects = [cameras.get(source_id) for source_id in session.sources]
        source_objects = [source for source in source_objects if source is not None]
        if not source_objects:
            return []
        profile = recording.get_profile(session.profile_id)
        session_dir = recording._session_dir(session_id)
        microphone = session_audio_inputs.get(session_id)
        task = capture_start_tasks.get(session_id)
        if task is None:
            # The microphone is passed only when one was chosen, so capture engines without the keyword keep working.
            task = asyncio.create_task(
                capture_engine.start(session_id, source_objects, profile, session_dir, audio_input=microphone)
                if microphone is not None else
                capture_engine.start(session_id, source_objects, profile, session_dir))
            capture_start_tasks[session_id] = task
            task.add_done_callback(lambda _: capture_start_tasks.pop(session_id, None))
        paths = await asyncio.shield(task)
        _note_capture_errors(session_id, _engine_failures(session_id, "start"))
        if session_id in capture_stop_tasks or session.state != RecordingState.ACTIVE:
            raise HTTPException(409, "Recording was stopped while its cameras were starting")
        return [str(path) for path in paths]

    async def _collect_capture_artifacts(session_id: str) -> List[Dict[str, Any]]:
        session_audio_inputs.pop(session_id, None)
        session_mode_options.pop(session_id, None)
        mode_artifacts = await recording_modes.end(session_id)
        if mode_artifacts is not None:      # data only / main camera: the mode recorded and registered its own media
            return mode_artifacts
        if capture_engine is None or not getattr(capture_engine, "available", False):
            return []
        starting = capture_start_tasks.get(session_id)
        if starting is not None:
            await asyncio.shield(starting)
        pending = unregistered_outputs.setdefault(session_id, [])
        if capture_engine.is_capturing(session_id):
            paths = await capture_engine.stop(session_id)
            _note_capture_errors(session_id, _engine_failures(session_id, "stop"))
            synthetic_lookup = getattr(capture_engine, "synthetic_outputs", None)
            synthetic = {Path(p).as_posix() for p in synthetic_lookup(session_id)} if callable(synthetic_lookup) else set()
            queued = {item["path"].as_posix() for item in pending}
            pending.extend({"path": Path(path), "synthetic": Path(path).as_posix() in synthetic}
                           for path in paths if Path(path).as_posix() not in queued)
        artifacts: List[Dict[str, Any]] = []
        not_saved: List[str] = []
        for item in list(pending):
            path, is_synthetic = item["path"], item["synthetic"]
            try:
                # The flag is only passed when set, so recording-service stand-ins
                # without the keyword keep working.
                artifact = (recording.register_artifact(session_id, path, synthetic=True)
                            if is_synthetic else recording.register_artifact(session_id, path))
            except Exception as exc:
                # The file is finished and stays on disk and in the queue; the next stop tries again.
                logger.warning("Could not register capture artifact %s for %s: %s", path, session_id, exc)
                not_saved.append(f"{path.name} ({exc})")
                continue
            pending.remove(item)
            artifacts.append({
                "name": artifact.name,
                "format": artifact.format.value,
                "file_path": artifact.file_path.as_posix(),
                "size_bytes": artifact.size_bytes,
                # True when the file is an FFmpeg test pattern, not camera or PubWorld video.
                "synthetic": is_synthetic,
            })
        if not pending:
            unregistered_outputs.pop(session_id, None)
        if not_saved:
            raise CaptureNotFinished(
                "Recorded but not yet added to the take: " + "; ".join(not_saved)
                + ". The files are kept on disk; stop the take again to retry.")
        still = [cp.get("source_id") for cp in getattr(capture_engine, "live_report", lambda _s: [])(session_id) or []]
        if capture_engine.is_capturing(session_id) and still:
            raise CaptureNotFinished(
                "These cameras' encoders did not stop: " + ", ".join(map(str, still))
                + ". Stop the take again to retry.")
        return artifacts

    async def _stop_capture_for_session(session_id: str) -> List[Dict[str, Any]]:
        task = capture_stop_tasks.get(session_id)
        if task is None:
            task = asyncio.create_task(_collect_capture_artifacts(session_id))
            capture_stop_tasks[session_id] = task
            task.add_done_callback(lambda _: capture_stop_tasks.pop(session_id, None))
        return await asyncio.shield(task)

    async def begin_take(session) -> List[str]:
        """Start capture for a session that was not opened by the start route (timeline cues).

        Goes through the same pipeline as POST /api/recording/start, so a timeline take
        gets the same encoders, microphone handling, privacy checks and hub event."""
        paths = await _start_capture_for_session(session)
        if hub:
            await hub.broadcast_system_event({
                "type": "recording_started",
                "payload": {
                    "session_id": session.session_id,
                    "sources": session.sources,
                    "profile_id": session.profile_id,
                    "state": session.state.value,
                    "countdown": 0,
                    "capture_paths": paths,
                    "capture_errors": _start_errors(session),
                },
            })
        return paths

    async def end_take(session_id: str):
        """Finish capture, close the session and announce it; shared by the stop route and the timeline.

        Returns the stopped session, its registered artifacts and the capture engine's warnings."""
        artifacts = await _stop_capture_for_session(session_id)
        session = recording.stop_session(session_id)
        warnings = [w for item in (getattr(capture_engine, "report", lambda _s: [])(session_id) or []) for w in item.get("warnings", [])]
        if hub:
            await hub.broadcast_system_event({
                "type": "recording_stopped",
                "payload": {
                    "session_id": session_id,
                    "duration": (session.ended_at or time.time()) - session.started_at,
                    "artifacts": artifacts,
                    "capture_warnings": warnings,
                    "capture_errors": list(getattr(session, "capture_errors", []) or []),
                },
            })
        return session, artifacts, warnings

    async def finish_all_captures(reason: str) -> Dict[str, List[Any]]:
        """Finish every take that is still recording or still has media waiting, all at once.

        Shared by PANIC and server shutdown. Each take's encoders are finished before its session is
        closed, so the files are complete; one take that fails does not hold back the others."""
        stopped: List[str] = []
        errors: List[Dict[str, Any]] = []
        active_states = (RecordingState.ACTIVE, RecordingState.COUNTDOWN, RecordingState.PAUSED)

        async def finish(session) -> None:
            session_id = session.session_id
            capturing = session_id in capture_start_tasks or bool(capture_engine and capture_engine.is_capturing(session_id))
            try:
                artifacts = await _stop_capture_for_session(session_id)
                if capturing and not artifacts:
                    errors.append({"session_id": session_id, "error": "Capture produced no registered media"})
            except Exception as exc:
                errors.append({"session_id": session_id, "error": str(exc)})
            for item in getattr(session, "capture_errors", []) or []:
                errors.append({"session_id": session_id, "source_id": item.get("source_id"), "error": item.get("error")})
            if session.state in active_states:
                try:
                    recording.stop_session(session_id)
                    stopped.append(session_id)
                except Exception as exc:
                    errors.append({"session_id": session_id, "error": str(exc)})

        sessions = [session for session in recording.list_sessions()
                    if session.state in active_states
                    or session.session_id in capture_start_tasks
                    or session.session_id in capture_stop_tasks
                    or session.session_id in unregistered_outputs
                    or bool(capture_engine and capture_engine.is_capturing(session.session_id))]
        await asyncio.gather(*(finish(session) for session in sessions))
        if errors:
            logger.warning("%s: capture problems %s", reason, errors)
        return {"stopped": stopped, "errors": errors}

    async def shutdown_captures() -> None:
        """Server shutdown: finish the files of every take still recording (as codex/main-debug does)."""
        try:
            await finish_all_captures("Shutdown")
        except Exception:
            logger.exception("Recordings could not all be finished at shutdown")

    router.begin_take = begin_take
    router.end_take = end_take
    router.shutdown_captures = shutdown_captures
    # The one recording-mode controller, for modules that add events to live takes (performer data).
    router.recording_modes = recording_modes
    # The Program mix goes into every live take's show data, at the start and on every change, so a take's
    # intended mix can be rebuilt from its stems; meters read the sound files takes are writing.
    program_audio_state.on_mix_change = lambda mix: recording_modes.record_event("audio.mix", mix)
    recording_modes.snapshot_providers.append(lambda: ("audio.mix", program_audio_state.mix()))
    program_audio_router.recording_levels = recording_modes.live_levels
    router.program_audio_state = program_audio_state

    # —
    # CAMERAS
    # —

    @router.get("/api/cameras")
    async def list_cameras():
        """List all registered camera sources with status."""
        sources = cameras.list_sources()
        statuses = {s.source_id: s for s in cameras.list_status()}
        pgm = cameras.get_program_source()
        pvw = cameras.get_preview_source()

        return {
            "cameras": [
                {
                    "source_id": cam.source_id,
                    "name": cam.name,
                    "location": cam.location,
                    "transport": cam.transport.value,
                    "endpoint": cam.endpoint,
                    "position": cam.position,
                    "rotation": cam.rotation,
                    "fov": cam.fov,
                    "tags": cam.tags,
                    "status": {
                        "online": statuses.get(cam.source_id, None)
                                  and statuses[cam.source_id].online,
                        "latency_ms": getattr(statuses.get(cam.source_id), "latency_ms", None),
                        "frame_rate": getattr(statuses.get(cam.source_id), "frame_rate", None),
                    },
                }
                for cam in sources
            ],
            "program": pgm.source_id if pgm else None,
            "preview": pvw.source_id if pvw else None,
        }

    @router.get("/api/cameras/program")
    async def get_program_camera():
        """Current program (live/on-air) camera source, if any."""
        pgm = cameras.get_program_source()
        return {"source_id": pgm.source_id if pgm else None}

    @router.get("/api/cameras/preview")
    async def get_preview_camera():
        """Current preview (next-up) camera source, if any."""
        pvw = cameras.get_preview_source()
        return {"source_id": pvw.source_id if pvw else None}

    @router.get("/api/cameras/visibility")
    async def camera_visibility_all(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Check whether registered cameras are plausibly visible and recordable."""
        report = all_camera_visibility(cameras)
        _blackbox_event(
            "camera.visibility",
            source="recorder",
            actor=str(identity.get("user_id") or "director"),
            data={"camera_count": len(report["cameras"]), "program": report.get("program"), "ok": report.get("ok")},
        )
        return report

    @router.get("/api/cameras/{source_id}/visibility")
    async def camera_visibility_one(source_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Check one camera source before switching or recording it."""
        camera = cameras.get(source_id)
        if camera is None:
            raise HTTPException(404, f"Camera source '{source_id}' not found.")
        report = camera_visibility_report(camera, cameras.status(source_id))
        _blackbox_event(
            "camera.visibility",
            source="recorder",
            actor=str(identity.get("user_id") or "director"),
            data={"source_id": source_id, "visible": report.get("visible"), "recordable": report.get("recordable")},
        )
        return report
    @router.post("/api/cameras/switch")
    async def switch_camera(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Switch program or preview camera. Broadcasts to all control rooms."""
        body = await _json_dict(request)
        target = _string_field(body, "target", default="program", max_length=32) or "program"
        source_id = _string_field(body, "source_id", required=True, max_length=128)

        if target == "program":
            ok = cameras.set_program_source(source_id)
        elif target == "preview":
            ok = cameras.set_preview_source(source_id)
        else:
            raise HTTPException(400, f"Invalid target '{target}'. Use 'program' or 'preview'.")

        if not ok:
            raise HTTPException(404, f"Camera source '{source_id}' not found.")

        _blackbox_event("broadcast.program_frame", source="recorder", actor=str(identity.get("user_id") or "director"), data={"camera_action": "switch", "target": target, "source_id": source_id})

        if hub and not getattr(hub, "camera_events_bridged", False):
            pgm = cameras.get_program_source()
            pvw = cameras.get_preview_source()
            await hub.broadcast_system_event({
                "type": "camera_switch",
                "payload": {
                    "target": target,
                    "source_id": source_id,
                    "program": pgm.source_id if pgm else None,
                    "preview": pvw.source_id if pvw else None,
                    "timestamp": time.time(),
                },
            })

        return {"ok": True, "target": target, "source_id": source_id}

    @router.post("/api/cameras/cut")
    async def cut_cameras(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Swap program and preview (standard broadcast CUT transition)."""
        pgm = cameras.get_program_source()
        pvw = cameras.get_preview_source()

        if not pgm or not pvw:
            raise HTTPException(400, "Both program and preview must be set to cut.")

        if not cameras.take():
            raise HTTPException(409, "Camera cut could not complete")

        _blackbox_event("broadcast.program_frame", source="recorder", actor=str(identity.get("user_id") or "director"), data={"camera_action": "cut", "program": pvw.source_id, "preview": pgm.source_id})

        if hub:
            await hub.broadcast_system_event({
                "type": "camera_cut",
                "payload": {
                    "new_program": pvw.source_id,
                    "new_preview": pgm.source_id,
                    "timestamp": time.time(),
                },
            })

        return {"ok": True, "program": pvw.source_id, "preview": pgm.source_id}

    @router.post("/api/cameras/register")
    async def register_camera(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Register a new camera source."""
        body = await _json_dict(request)
        try:
            source_id = _string_field(body, "source_id", required=True, max_length=128)
            source = CameraSource(
                source_id=source_id,
                name=_string_field(body, "name", default=source_id, max_length=128),
                location=_string_field(body, "location", default="virtual", max_length=128) or "virtual",
                description=_string_field(body, "description", default="", max_length=512),
                transport=CameraTransport(_string_field(body, "transport", default="virtual", max_length=64) or "virtual"),
                endpoint=_string_field(body, "endpoint", default=f"virtual://{source_id}", max_length=512),
                position=_vector3(body, "position"),
                rotation=_vector3(body, "rotation"),
                fov=_numeric_field(body, "fov", default=60.0, minimum=1.0),
                tags=_string_list(body, "tags"),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        cameras.register(source)
        _blackbox_event("broadcast.program_frame", source="recorder", actor=str(identity.get("user_id") or "director"), data={"camera_action": "register", "source_id": source.source_id, "transport": source.transport.value})
        return {"ok": True, "source_id": source.source_id}

    # —
    # RECORDING
    # —

    @router.get("/api/recording/profiles")
    async def list_profiles():
        """List available encoding profiles."""
        profiles = [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "container": p.container.value,
                "video_codec": p.video_codec,
                "audio_codec": p.audio_codec,
                "resolution": p.resolution,
                "description": p.description,
            }
            for p in recording.list_profiles()
        ]
        return {"profiles": profiles, "count": len(profiles)}

    @router.get("/api/recording/sessions")
    async def list_sessions(identity: Dict[str, Any] = Depends(current_identity)):
        """List all recording sessions."""
        return [s.to_dict() for s in recording.list_sessions()
                if not getattr(s, "ingest", None) or (identity.get("authenticated") and identity.get("user_id") == s.operator)]

    @router.post("/api/recording/preflight")
    async def recording_preflight_route(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Validate camera visibility, source policy, and profile availability before recording."""
        body = await _json_dict(request)
        sources = _string_list(body, "sources")
        profile_id = _string_field(body, "profile_id", default="broadcast_mp4", max_length=128) or "broadcast_mp4"
        host_override = _bool_field(body, "host_override", default=False)
        mode = body.get("mode")
        if mode is not None and not isinstance(mode, str):
            raise HTTPException(400, "mode must be text")
        planned = _numeric_field(body, "planned_minutes", default=30, minimum=0)
        report = recording_preflight(cameras, recording, sources=sources, profile_id=profile_id, host_override=host_override,
                                     mode=mode, record_data=body.get("record_data", True), planned_minutes=planned)
        _blackbox_event(
            "recording.preflight",
            source="recording",
            actor=str(identity.get("user_id") or "director"),
            data={"ready": report.get("ready"), "sources": ",".join(report.get("sources", [])), "profile_id": profile_id, "issue_count": len(report.get("issues", []))},
        )
        return report

    @router.get("/api/studio/readiness")
    async def studio_readiness_route(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Aggregate the current camera and recording readiness for the studio."""
        report = studio_readiness(cameras, recording, audio_status=program_audio_state.status())
        _blackbox_event(
            "studio.readiness",
            source="recording",
            actor=str(identity.get("user_id") or "director"),
            data={"ready": report.get("ready"), "program": report.get("program"), "camera_count": report.get("camera_count"), "recording_profiles": report.get("recording_profiles")},
        )
        return report

    @router.get("/api/studio/actions")
    async def studio_actions_manifest(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Return stable action IDs that future studio-console hotspots can call."""
        return {"actions": list_studio_actions()}

    @router.post("/api/studio/actions/{action_id}")
    async def studio_action_execute(action_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Execute a stable studio action by ID for console art or hotspot overlays."""
        body = await _json_dict(request)
        actor = str(identity.get("user_id") or "director")
        stop_artifacts: Optional[List[Dict[str, Any]]] = None
        if action_id == "recording.stop":
            # The media is finished before the take is closed, the same order as the stop route; closing
            # first left the encoders writing into a take that already said it had ended.
            try:
                stop_artifacts = await _stop_capture_for_session(confirmed_stop_session_id(body))
            except ValueError as exc:
                raise HTTPException(400, str(exc))
            except KeyError as exc:
                raise HTTPException(404, str(exc))
            except CaptureNotFinished as exc:
                raise HTTPException(409, str(exc))
        try:
            response = execute_studio_action(
                action_id,
                body,
                cameras=cameras,
                recording=recording,
                audio_state=program_audio_state,
                actor=actor,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

        if response.get("ok") and action_id == "recording.start":
            session_data = response.get("result", {})
            session_id = session_data.get("session_id")
            if session_id:
                session = recording.get_session(session_id)
                capture_paths = await _start_capture_for_session(session)
                if capture_paths:
                    session_data["capture_paths"] = capture_paths
                start_errors = _start_errors(session)
                if start_errors:
                    session_data["capture_errors"] = start_errors
        elif response.get("ok") and action_id == "recording.stop":
            session_data = response.get("result", {})
            session_id = str(session_data.get("session_id") or body.get("session_id"))
            if stop_artifacts:
                session_data["artifacts"] = stop_artifacts
            report = getattr(capture_engine, "report", None)
            capture_report = report(session_id) if callable(report) else []
            if capture_report:
                session_data["capture_report"] = capture_report
            try:
                saved_errors = recording.get_session(session_id).capture_errors
            except (KeyError, AttributeError):
                saved_errors = []
            if saved_errors:
                session_data["capture_errors"] = list(saved_errors)

        _blackbox_event(
            "studio.action",
            source="recording",
            actor=actor,
            data={"action_id": action_id, "ok": bool(response.get("ok"))},
        )
        if hub:
            await hub.broadcast_system_event({
                "type": "studio_action",
                "payload": {
                    "action_id": action_id,
                    "ok": bool(response.get("ok")),
                    "actor": actor,
                    "result": response.get("result", {}),
                    "timestamp": time.time(),
                },
            })
        return response
    @router.post("/api/recording/start")
    async def start_recording(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Start a new recording session."""
        body = await _json_dict(request)
        sources = _string_list(body, "sources")
        sources_named = bool(sources)
        mode = (_string_field(body, "mode", default="camcorder", max_length=32) or "camcorder").strip().lower()
        record_data = body.get("record_data", True)
        arm_preview = _bool_field(body, "arm_preview", default=False)
        if mode not in RECORDING_MODE_DESCRIPTIONS:
            raise HTTPException(400, f"Unknown recording mode '{mode}'; use one of: {', '.join(RECORDING_MODE_DESCRIPTIONS)}")
        if not sources:
            # Main camera only may cut to any camera the privacy rules allow; the other modes use the live one.
            sources = default_sources(recording, mode)
            if not sources and mode != "data_only":
                raise HTTPException(400, "No sources specified and no program source set.")

        profile_id = _string_field(body, "profile_id", default="broadcast_mp4", max_length=128) or "broadcast_mp4"
        operator = bound_actor(request=request, identity=identity, explicit_value=body.get("operator"), field_name="operator") or "director"
        session_id = _string_field(body, "session_id", default="", max_length=128) or None
        countdown = int(_numeric_field(body, "countdown_seconds", default=5, minimum=0))
        host_override = _bool_field(body, "host_override", default=False)
        microphone = None
        audio_text = _string_field(body, "audio_input", default="", max_length=300)
        if audio_text:
            try:
                microphone = parse_audio_input(audio_text)
            except AudioInputError as exc:
                raise HTTPException(400, str(exc))

        try:
            session = recording.start_session(
                session_id=session_id,
                sources=sources,
                profile_id=profile_id,
                operator=operator,
                countdown_seconds=countdown,
                host_override=host_override,
                mode=mode,
                record_data=record_data,
            )
        except PreflightRefusal as exc:
            raise HTTPException(409, {"message": str(exc), "refusals": exc.report["gate"]["refusals"],
                                      "machine": exc.report["machine"]})
        except (ValueError, PermissionError, KeyError) as exc:
            raise HTTPException(400, str(exc))

        if microphone is not None:
            session_audio_inputs[session.session_id] = microphone
        session_mode_options[session.session_id] = {"arm_preview": arm_preview, "sources_named": sources_named}
        try:
            capture_paths = await _start_capture_for_session(session)
        finally:
            if session.state == RecordingState.ACTIVE:
                session_audio_inputs.pop(session.session_id, None)

        if hub:
            await hub.broadcast_system_event({
                "type": "recording_started",
                "payload": {
                    "session_id": session.session_id,
                    "sources": session.sources,
                    "profile_id": session.profile_id,
                    "state": session.state.value,
                    "countdown": countdown,
                    "capture_paths": capture_paths,
                    "capture_errors": _start_errors(session),
                },
            })

        response = session.to_dict()
        if getattr(session, "preflight", None):
            response["preflight"] = session.preflight
        if capture_paths:
            response["capture_paths"] = capture_paths
        # FFmpeg exiting within moments of starting means nothing is being recorded; say so now.
        capture_errors = _start_errors(session)
        if capture_errors:
            response["capture_errors"] = capture_errors
        return response

    @router.get("/api/recording/modes")
    async def list_recording_modes():
        """The three ways a take can record picture, with what each does."""
        return {"modes": [{"mode": key, "description": text} for key, text in RECORDING_MODE_DESCRIPTIONS.items()],
                "default": "camcorder"}

    @router.get("/api/recording/{session_id}/mode")
    async def recording_mode_status(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """What this take's mode did: cuts, pieces of picture, sound tracks, show data and the program join."""
        try:
            return recording_modes.status(session_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/api/recording/{session_id}/mode/assemble")
    async def recording_mode_assemble(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Join a stopped main-camera take's pieces into its program file again, if it has none yet."""
        try:
            result = await recording_modes.assemble(session_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except ModeRequestError as exc:
            raise HTTPException(409, str(exc))
        return result

    @router.post("/api/recording/{session_id}/activate")
    async def activate_recording(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Activate a recording session (transition from countdown to active)."""
        try:
            session = recording.activate_session(session_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        capture_paths = await _start_capture_for_session(session)
        session_audio_inputs.pop(session_id, None)
        mode_errors = _start_errors(session)

        if hub:
            await hub.broadcast_system_event({
                "type": "recording_active",
                "payload": {"session_id": session_id, "capture_paths": capture_paths},
            })

        response = session.to_dict()
        if capture_paths:
            response["capture_paths"] = capture_paths
        if mode_errors:
            response["capture_errors"] = mode_errors
        return response

    @router.post("/api/recording/{session_id}/stop")
    async def stop_recording(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Stop a recording session."""
        try:
            session, _artifacts, _warnings = await end_take(session_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except CaptureNotFinished as exc:
            # The take stays open, so pressing stop again retries with the files already on disk.
            raise HTTPException(409, str(exc))

        response = session.to_dict()
        report = getattr(capture_engine, "report", None)
        capture_report = report(session_id) if callable(report) else []
        if capture_report:
            response["capture_report"] = capture_report
        return response

    @router.post("/api/recording/{session_id}/pause")
    async def pause_recording(session_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Pause or resume a recording session."""
        body = await _json_dict(request)
        paused = _bool_field(body, "paused", default=True)
        try:
            session = recording.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(400, str(exc))
        live = session.state in (RecordingState.ACTIVE, RecordingState.PAUSED)
        word = "paused" if paused else "resumed"
        problems: List[Dict[str, Any]] = []
        engine_changed = False
        modes_changed = False

        async def engine_pause(value: bool) -> List[Dict[str, Any]]:
            result = capture_engine.set_paused(session_id, value)
            if asyncio.iscoroutine(result):
                result = await result
            return list(result or [])

        try:
            # The camcorder path's cameras (every chosen camera, for the whole take) ...
            if live and capture_engine is not None and capture_engine.is_capturing(session_id):
                problems += await engine_pause(paused)
                engine_changed = True
            # ... and what a data-only or main-camera take records itself, with every mode's show data.
            if live:
                mode_problems = await recording_modes.set_paused(session_id, paused)
                if mode_problems is not None:
                    problems += mode_problems
                    modes_changed = True
        except (RuntimeError, OSError, NotImplementedError, ValueError) as exc:
            if engine_changed:
                try:
                    await engine_pause(not paused)
                except Exception:
                    logger.exception("Could not put the cameras of %s back after a failed pause", session_id)
            raise HTTPException(409, f"The take could not be {word}: {exc}")
        _note_capture_errors(session_id, problems)
        try:
            session = recording.pause_session(session_id, paused)
        except (KeyError, ValueError) as exc:
            try:
                if engine_changed:
                    await engine_pause(not paused)
                if modes_changed:
                    await recording_modes.set_paused(session_id, not paused)
            except Exception:
                logger.exception("Could not put the cameras of %s back after a failed pause", session_id)
            raise HTTPException(400, str(exc))
        reply = session.to_dict()
        if problems:
            # Named here as well as kept with the take: a camera that did not come back after a pause is not recording.
            reply["pause_problems"] = problems
        return reply

    @router.post("/api/recording/{session_id}/marker")
    async def add_marker(session_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Add a timestamp marker to a recording session."""
        body = await _json_dict(request)
        label = _string_field(body, "label", required=True, max_length=256)
        operator = bound_actor(request=request, identity=identity, explicit_value=body.get("operator"), field_name="operator") if body.get("operator") else identity.get("user_id")
        try:
            marker = recording.mark_moment(session_id, label, operator)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        return {"ok": True, "timestamp": marker.timestamp, "label": marker.label}

    @router.post("/api/recording/{session_id}/export")
    async def export_recording(session_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Export a recording session as a zip bundle."""
        body = await _json_dict(request)
        container = _string_field(body, "format", default="mp4", max_length=16) or "mp4"
        try:
            fmt = ContainerFormat(container)
        except ValueError:
            raise HTTPException(400, f"Invalid format '{container}'. Use: mp4, webm, wav, mov")

        try:
            export_path = await asyncio.to_thread(
                recording.export_session, session_id, container=fmt
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        return FileResponse(
            export_path,
            media_type="application/zip",
            filename=export_path.name,
        )

    @router.post("/api/recording/import")
    async def import_recording(file: UploadFile = File(...), identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Import a recording session from a zip bundle."""
        import_dir = recording.imports_dir
        filename = sanitize_filename(file.filename or "")
        if not filename:
            raise HTTPException(400, "Uploaded file must have a filename")
        if not filename.lower().endswith(".zip"):
            raise HTTPException(400, "Recording import requires a .zip bundle")
        limit = int(os.environ.get("PUBCAST_RECORDING_IMPORT_MAX_BYTES", str(64 * 1024 ** 3)))
        # Reserve atomically: two uploads with the same name must not clobber
        # one another between path selection and opening the file.
        while True:
            import_path = unique_child_path(import_dir, filename)
            try:
                upload_target = open(import_path, "xb")
                break
            except FileExistsError:
                continue
        try:
            size = 0
            with upload_target as f:
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, "Recording upload exceeds the import storage budget")
                    f.write(chunk)
            session = await asyncio.to_thread(recording.import_session, import_path, operator=str(identity["user_id"]))
        except (ValueError, FileNotFoundError, BadZipFile) as exc:
            raise HTTPException(400, str(exc)) from exc
        return session.to_dict()

    @router.get("/api/recording/storage")
    async def storage_status():
        """Get recording storage usage."""
        return recording.storage_status()

    @router.get("/api/recording/privacy")
    async def privacy_matrix():
        """Get recording privacy rules per room."""
        return recording.privacy_matrix()

    # —
    # PANIC / Emergency
    # —

    @router.post("/api/production/video-cue")
    async def video_cue(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Shared, acknowledged black/preview-bars state for the actual 2.5D renderer."""
        body = await _json_dict(request)
        cue = body.get("cue")
        enabled = body.get("enabled")
        if cue not in {"blackout", "preview_bars"} or not isinstance(enabled, bool):
            raise HTTPException(400, "cue must be blackout/preview_bars and enabled must be boolean")
        if hub is None:
            raise HTTPException(503, "Production state hub unavailable")
        now = time.time()
        patch = {cue: enabled, cue + "_seq": now}
        hub.update_production_state(patch)
        await hub.broadcast_system_event({"type": "production_video_cue", "payload": {**patch, "cue": cue, "actor": str(identity.get("user_id") or "director")}})
        _blackbox_event("production.video_cue", source="system",
                        actor=str(identity.get("user_id") or "director"), data=patch)
        return {"ok": True, **patch}

    @router.post("/api/production/panic")
    async def production_panic(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Emergency: stop active captures, silence program audio, cue black.

        Reports partial failures explicitly; changing an indicator is not proof
        that FFmpeg and other capture workers actually stopped.
        """
        now = time.time()
        # Browser encoders follow these cues while server captures drain.
        apply_audio_event(program_audio_state, {"action": "stop_all"})
        program_audio_state.publish({"action": "stop_all"})
        apply_audio_event(program_audio_state, {"action": "set_volume", "bus": "master", "volume": 0})
        program_audio_state.publish({"action": "set_volume", "bus": "master", "volume": 0})
        if hub:
            hub.update_production_state({
                "on_air": False,
                "camera": "black",
                "lower_third": "",
                "panic_seq": now,
                "blackout": True,
                "blackout_seq": now,
            })
        # Every take is finished at once: one slow or failing encoder must not hold back the others.
        outcome = await finish_all_captures("PANIC")
        stopped, capture_errors = outcome["stopped"], outcome["errors"]
        if hub:
            await hub.broadcast_system_event({
                "type": "production_panic",
                "payload": {
                    "timestamp": now,
                    "sessions_stopped": stopped,
                    "capture_errors": capture_errors,
                    "message": "PANIC — capture stop requested, program audio silenced, black video cued",
                },
            })
        _blackbox_event("production.panic", source="system",
                        actor=str(identity.get("user_id") or "director"),
                        data={"sessions_stopped": stopped, "capture_errors": capture_errors, "panic_seq": now})
        return {"ok": not capture_errors, "sessions_stopped": stopped,
                "capture_errors": capture_errors, "audio_muted": True,
                "blackout_cued": bool(hub), "panic_seq": now}

    if emergency_snapshot is not None:
        @router.post("/api/studio/emergency-save")
        async def studio_emergency_save(identity: Dict[str, Any] = Depends(require_role("mod"))):
            """Stop production and save the studio control state."""
            stop = await production_panic(identity)
            try:
                snapshot = await emergency_snapshot()
            except Exception:
                logger.exception("Emergency studio state could not be saved")
                snapshot = {"ok": False, "error": "Studio state could not be saved"}
            return {"ok": stop["ok"] and bool(snapshot.get("ok")),
                    "result": snapshot, "production_stop": stop}

    return router







