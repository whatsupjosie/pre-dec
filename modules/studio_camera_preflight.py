"""Camera visibility and recording preflight helpers for PubCast studio.

These helpers do not capture media. They answer the production question that
must be true before capture starts: can the selected sources plausibly see, are
they recordable under current policy, and is the recording profile available?

Added 2026-11-27 (Claude, finish/control-room-engine), so a take is not rolled onto a machine that cannot keep it:
* ``mode``: when given, the mode is judged by ``recording_modes.validate_mode_request``, the same rule the start
  uses, and the mode's default cameras are used when none are named;
* ``machine``: FFmpeg and ffprobe installed, the recordings folder writable (a real write and fsync), free disk,
  and how many minutes of this take the disk holds, estimated from each output's profile bitrate with a 25% margin
  (a profile's bitrate is a target, not a promise);
* ``gate`` and ``start_gate``: what every start path enforces. It refuses only what certainly ruins a take: no
  FFmpeg when the take encodes, a folder that cannot be written, or disk for less than two minutes. Everything
  else stays a report, because the start already reports capture problems per camera and a camera may come up a
  moment later.
"""
from __future__ import annotations

import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .cameras import CameraManager, CameraSource, CameraStatus, CameraTransport
from .recording import RecordingService


GATE_MINUTES = 2.0            # disk for less than this much of the take: refused
PLANNED_MINUTES = 30.0        # the take length assumed when none is given
DISK_MARGIN = 1.25


class PreflightRefusal(ValueError):
    """A start refused by the gate; ``report`` is the preflight that says why.

    A ValueError, so every start path that already refuses bad requests refuses this one too."""

    def __init__(self, report: Dict[str, Any]):
        super().__init__("Cannot roll: " + "; ".join(i["message"] for i in report["gate"]["refusals"]))
        self.report = report


def _issue(code: str, message: str, severity: str = "error") -> Dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def bits_per_second(value: Optional[str]) -> Optional[float]:
    """'50Mbps' -> 50e6, '320kbps' -> 320e3, '1.5Mbps' -> 1.5e6; None for anything else."""
    if not value:
        return None
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]?)(?:bps|b/s)?\s*", str(value))
    if not m:
        return None
    return float(m.group(1)) * {"": 1.0, "k": 1e3, "m": 1e6, "g": 1e9}[m.group(2).lower()]


def _vector_ok(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 3:
        return False
    try:
        [float(item) for item in value]
    except (TypeError, ValueError):
        return False
    return True


def camera_visibility_report(camera: CameraSource, status: Optional[CameraStatus] = None) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    online = bool(status.online) if status is not None else True

    native_control = camera.transport == CameraTransport.VOXEL_3D and camera.endpoint.startswith("rust://")
    if native_control:
        issues.append(_issue("native_media_unavailable", "Native voxel camera is registered for pose control only. No media stream is available."))
    if not online:
        issues.append(_issue("camera_offline", "Camera status is offline."))
    if "studio25d" in camera.tags and str(camera.endpoint).startswith("virtual://"):
        issues.append(_issue("confidence_only", "2.5D camera has low-rate confidence images but no recordable server media stream."))
    if not str(camera.endpoint or "").strip():
        issues.append(_issue("missing_endpoint", "Camera endpoint is empty."))
    if camera.video_enabled and not (1.0 <= float(camera.fov or 0) <= 180.0):
        issues.append(_issue("invalid_fov", "Camera field of view must be between 1 and 180 degrees."))
    if not _vector_ok(camera.position):
        issues.append(_issue("invalid_position", "Camera position must be a numeric XYZ vector."))
    if not _vector_ok(camera.rotation):
        issues.append(_issue("invalid_rotation", "Camera rotation must be a numeric XYZ vector."))
    if not camera.video_enabled and not camera.audio_enabled:
        issues.append(_issue("no_media_enabled", "Camera has neither video nor audio enabled."))
    if camera.is_private:
        warnings.append(_issue("private_source", "Camera is marked private; recording needs policy approval.", "warning"))

    confidence = "status_only"
    if native_control:
        confidence = "control_only"
    elif camera.transport == CameraTransport.VIRTUAL:
        confidence = "synthetic_virtual_frame"
    elif camera.transport == CameraTransport.FILE:
        confidence = "file_endpoint"

    visible = online and camera.video_enabled and not any(item["severity"] == "error" for item in issues)
    recordable = online and (camera.video_enabled or camera.audio_enabled) and not any(item["severity"] == "error" for item in issues)
    return {
        "source_id": camera.source_id,
        "name": camera.name,
        "transport": camera.transport.value,
        "endpoint": camera.endpoint,
        "location": camera.location,
        "online": online,
        "visible": visible,
        "recordable": recordable,
        "confidence": confidence,
        "video_enabled": camera.video_enabled,
        "audio_enabled": camera.audio_enabled,
        "latency_ms": getattr(status, "latency_ms", None),
        "frame_rate": getattr(status, "frame_rate", None),
        "issues": issues,
        "warnings": warnings,
        "checked_at": time.time(),
    }


def all_camera_visibility(cameras: CameraManager) -> Dict[str, Any]:
    statuses = {status.source_id: status for status in cameras.list_status()}
    reports = [camera_visibility_report(camera, statuses.get(camera.source_id)) for camera in cameras.list_sources()]
    return {
        "ok": all(report["recordable"] for report in reports),
        "cameras": reports,
        "program": getattr(cameras.get_program_source(), "source_id", None),
        "preview": getattr(cameras.get_preview_source(), "source_id", None),
    }


def recording_preflight(
    cameras: CameraManager,
    recording: RecordingService,
    *,
    sources: Iterable[str] | None = None,
    profile_id: str = "broadcast_mp4",
    host_override: bool = False,
    mode: Optional[str] = None,
    record_data: Any = True,
    planned_minutes: float = PLANNED_MINUTES,
    default_cameras: bool = True,
) -> Dict[str, Any]:
    """``default_cameras=False`` judges exactly the cameras given (the start gate: the start has already chosen)."""
    selected = [str(item).strip() for item in (sources or []) if str(item).strip()]
    mode_name = str(mode).strip().lower() if mode is not None else None
    if not selected and mode_name is not None and default_cameras:
        from .recording_modes import default_sources
        try:
            selected = default_sources(recording, mode_name)
        except Exception:  # noqa: BLE001 — an unknown mode is reported below
            selected = []
    if not selected and default_cameras:
        program = cameras.get_program_source()
        if program is not None and mode_name != "data_only":
            selected = [program.source_id]

    issues: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    if not selected and mode_name != "data_only":
        issues.append(_issue("no_sources", "No recording sources were selected and no program camera is set."))
    if mode_name is not None:
        from .recording_modes import ModeRequestError, validate_mode_request
        try:
            mode_name = validate_mode_request(recording, mode_name, selected, profile_id,
                                              record_data=record_data, host_override=host_override)
        except ModeRequestError as exc:
            issues.append(_issue("mode_refused", str(exc)))
        except KeyError:
            pass                                    # the missing profile is reported once, below

    try:
        profile = recording.get_profile(profile_id)
        profile_payload: Dict[str, Any] = {
            "profile_id": profile.profile_id,
            "container": profile.container.value,
            "video_codec": profile.video_codec,
            "audio_codec": profile.audio_codec,
            "resolution": profile.resolution,
            "frame_rate": profile.frame_rate,
            "audio_only": profile.is_audio_only,
        }
    except KeyError:
        profile_payload = {"profile_id": profile_id, "missing": True}
        issues.append(_issue("missing_profile", f"Recording profile '{profile_id}' is not registered."))

    statuses = {status.source_id: status for status in cameras.list_status()}
    camera_reports: List[Dict[str, Any]] = []
    for source_id in selected:
        camera = cameras.get(source_id)
        if camera is None:
            issues.append(_issue("unknown_source", f"Camera source '{source_id}' is not registered."))
            continue
        report = camera_visibility_report(camera, statuses.get(source_id))
        camera_reports.append(report)
        if not report["recordable"]:
            issues.append(_issue("source_not_recordable", f"Camera source '{source_id}' is not currently recordable."))
        policy = recording.room_policy(camera.location)
        rule = str(policy.get("recording") or "allowed")
        if rule == "never" and not host_override:
            issues.append(_issue("privacy_forbidden", f"Recording is forbidden in {camera.location}."))
        elif rule == "with_permission" and not host_override:
            issues.append(_issue("consent_required", f"Recording {camera.location} requires explicit consent."))
        elif rule == "host_policy":
            warnings.append(_issue("host_policy", f"Recording policy for {camera.location} is host-defined.", "warning"))

    machine = machine_report(recording, mode_name or "camcorder", selected, profile_id, planned_minutes)
    issues.extend(machine.pop("issues"))
    warnings.extend(machine.pop("warnings"))
    ready = not issues
    return {
        "ready": ready,
        "ok": ready,
        "mode": mode_name,
        "sources": selected,
        "profile": profile_payload,
        "host_override": bool(host_override),
        "camera_reports": camera_reports,
        "machine": machine,
        "gate": gate_findings(machine),
        "issues": issues,
        "warnings": warnings,
        "checked_at": time.time(),
    }


def _outputs(recording: RecordingService, mode: str, sources: List[str], profile_id: str) -> List[Dict[str, Any]]:
    """What the take will encode, one entry per output file, with its bitrate (None: the profile does not say)."""
    from .recording_modes import SOUND_PROFILE_ID
    try:
        profile = recording.get_profile(profile_id)
    except KeyError:
        return []
    if not (profile.video_codec or profile.audio_codec):
        return []                                   # e.g. a browser take: the server encodes nothing

    def rate(p) -> Optional[float]:
        v, a = bits_per_second(p.video_bitrate), bits_per_second(p.audio_bitrate)
        return None if v is None and a is None else (v or 0.0) + (a or 0.0)

    try:
        sound = recording.get_profile(SOUND_PROFILE_ID)
    except KeyError:
        sound = None
    if mode not in ("data_only", "main_camera"):
        return [{"output": f"{s} ({profile_id})", "bps": rate(profile)} for s in sources]
    out = [{"output": f"{s} sound ({SOUND_PROFILE_ID})", "bps": rate(sound) if sound else None} for s in sources]
    if mode == "main_camera":
        out.append({"output": f"program ({profile_id})", "bps": rate(profile)})
    return out


def machine_report(recording: RecordingService, mode: str, sources: List[str], profile_id: str,
                   planned_minutes: float = PLANNED_MINUTES) -> Dict[str, Any]:
    """Can this machine keep the take: tools, a writable folder, and disk. Returns findings in 'issues'/'warnings'."""
    issues: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    outputs = _outputs(recording, mode, sources, profile_id)
    report: Dict[str, Any] = {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
                              "outputs": outputs, "encodes": bool(outputs)}
    if outputs and not report["ffmpeg"]:
        issues.append(_issue("no_ffmpeg", "FFmpeg is not installed, and this take encodes: nothing would be recorded."))
    if outputs and not report["ffprobe"]:
        warnings.append(_issue("no_ffprobe", "ffprobe is not installed: recordings cannot be checked after the take.", "warning"))
    folder = Path(recording.recordings_dir)
    report["recordings_dir"] = str(folder)
    probe = folder / f".preflight-{uuid.uuid4().hex}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(probe, "wb") as handle:
            handle.write(b"preflight")
            handle.flush()
            os.fsync(handle.fileno())
        report["writable"] = True
    except OSError as exc:
        report["writable"] = False
        issues.append(_issue("not_writable", f"The recordings folder cannot be written: {exc}"))
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    try:
        report["free_bytes"] = shutil.disk_usage(folder).free
    except OSError:
        report["free_bytes"] = None
    known = [o["bps"] for o in outputs if o["bps"] is not None]
    unknown = [o["output"] for o in outputs if o["bps"] is None]
    bytes_per_minute = sum(known) * DISK_MARGIN / 8 * 60 if known else None
    report["estimated_bytes_per_minute"] = round(bytes_per_minute) if bytes_per_minute else None
    report["minutes_of_disk"] = None
    planned = max(0.0, float(planned_minutes))
    report["planned_minutes"] = planned
    if unknown:
        warnings.append(_issue("bitrate_unknown", "Disk needed cannot be estimated for: " + ", ".join(unknown), "warning"))
    if report["free_bytes"] is not None and bytes_per_minute:
        minutes = report["free_bytes"] / bytes_per_minute
        report["minutes_of_disk"] = round(minutes, 1)
        if minutes < GATE_MINUTES:
            issues.append(_issue("disk_full", f"The disk holds about {minutes:.1f} minutes of this take; "
                                              f"at least {GATE_MINUTES:.0f} are needed to roll."))
        elif minutes < planned:
            warnings.append(_issue("disk_short", f"The disk holds about {minutes:.0f} minutes of this take, "
                                                 f"less than the {planned:.0f} planned.", "warning"))
    report["issues"], report["warnings"] = issues, warnings
    return report


def gate_findings(machine: Mapping[str, Any]) -> Dict[str, Any]:
    refusals: List[Dict[str, str]] = []
    if machine.get("encodes") and not machine.get("ffmpeg"):
        refusals.append(_issue("no_ffmpeg", "FFmpeg is not installed, and this take encodes."))
    if machine.get("writable") is False:
        refusals.append(_issue("not_writable", "The recordings folder cannot be written."))
    minutes = machine.get("minutes_of_disk")
    if minutes is not None and minutes < GATE_MINUTES:
        refusals.append(_issue("disk_full", f"The disk holds about {minutes:.1f} minutes of this take; "
                                            f"at least {GATE_MINUTES:.0f} are needed."))
    return {"pass": not refusals, "refusals": refusals}


def start_gate(cameras: CameraManager, recording: RecordingService, **kwargs: Any) -> Dict[str, Any]:
    """The preflight every start path runs first. Raises PreflightRefusal when the take would certainly be lost."""
    report = recording_preflight(cameras, recording, default_cameras=False, **kwargs)
    if not report["gate"]["pass"]:
        raise PreflightRefusal(report)
    return report


def studio_readiness(cameras: CameraManager, recording: RecordingService, *, audio_status: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    camera_report = all_camera_visibility(cameras)
    profile_count = len(recording.list_profiles())
    program = cameras.get_program_source()
    preflight = recording_preflight(
        cameras,
        recording,
        sources=[program.source_id] if program is not None else [],
        profile_id="broadcast_mp4",
    )
    audio_ready = bool(audio_status) if audio_status is not None else False
    issues: List[Dict[str, str]] = []
    if program is None:
        issues.append(_issue("no_program_camera", "No program camera is selected."))
    if profile_count <= 0:
        issues.append(_issue("no_recording_profiles", "No recording profiles are registered."))
    issues.extend(preflight.get("issues", []))
    ready = not issues
    return {
        "ready": ready,
        "ok": ready,
        "program": getattr(program, "source_id", None),
        "preview": getattr(cameras.get_preview_source(), "source_id", None),
        "camera_count": len(camera_report["cameras"]),
        "recording_profiles": profile_count,
        "recording_preflight": preflight,
        "audio_ready": audio_ready,
        "audio": dict(audio_status or {}),
        "issues": issues,
        "checked_at": time.time(),
    }


__all__ = ["PreflightRefusal", "all_camera_visibility", "bits_per_second", "camera_visibility_report",
           "gate_findings", "machine_report", "recording_preflight", "start_gate", "studio_readiness"]
