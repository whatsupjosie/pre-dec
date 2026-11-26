"""Program audio runtime routes for studio playback state.

This is the server contract for dialogue, music, SFX, UI clicks, VTR, and room
sound state. It does not play audio by itself; browser/runtime clients consume
validated events and this state gives menus and recovery tools a stable truth.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .program_audio import ProgramAudioState, apply_audio_event, issue_recovery_actions, validate_audio_event
from .route_security import require_role, current_identity
from .auth import role_gte


async def _json_dict(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def create_program_audio_router(state: Optional[ProgramAudioState] = None, *, blackbox: Any = None, hub: Any = None) -> APIRouter:
    audio_state = state or ProgramAudioState()
    router = APIRouter(prefix="/api/program-audio", tags=["Program Audio"])

    def _record(action: str, actor: str, payload: Dict[str, Any]) -> None:
        if blackbox is not None:
            blackbox.record_event("audio.state", source="system", actor=actor, data={"action": action, **payload})

    @router.get('/events')
    async def audio_events(after: int = -1, identity=Depends(current_identity)):
        if not identity.get('authenticated'):
            raise HTTPException(401, 'Sign in to receive program audio commands')
        result = audio_state.events_after(after)
        # An already-running studio's mix must be authoritative for newcomers;
        # the event queue deliberately does not replay past audio on first entry.
        if after < 0 or result.get('gap'):
            result['status'] = audio_state.status()
        from .chat_rooms import role_can_access
        aliases = {'control': 'controlroom', 'waiting_room': 'waitingroom'}
        result['events'] = [event for event in result['events'] if not event.get('room') or
            role_can_access(identity.get('role', 'guest'), aliases.get(event['room'], event['room'])) or
            (role_gte(identity.get('role', 'guest'), 'mod') and not str(event['room']).startswith(('dm____','dmv2_')))]
        return result

    @router.get("/status")
    async def program_audio_status(identity: Dict[str, Any] = Depends(require_role("mod"))):
        status = audio_state.status()
        _record("status", str(identity.get("user_id") or "director"), {"dialogue_active": status["dialogue_active"]})
        return {"ok": True, "status": status, "recovery_actions": issue_recovery_actions()}

    @router.post("/event")
    async def program_audio_event(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        try:
            event = validate_audio_event(body)
            event['authorized_director'] = bool(identity.get('authenticated') and role_gte(identity.get('role', 'guest'), 'mod'))
            if event.get('director_announcement') and not event['authorized_director']:
                raise HTTPException(403, 'Authenticated director required for announcements')
            event['authorized_director'] = bool(event.get('director_announcement') and event['authorized_director'])
            if event.get('room') == 'dressing' and event['action'] == 'play' and not event['authorized_director']:
                raise HTTPException(403, 'Dressing room permits direct director announcements only')
            status = apply_audio_event(audio_state, event)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _record(
            str(event.get("action") or "status"),
            str(identity.get("user_id") or "director"),
            {
                "bus": str(event.get("bus") or ""),
                "volume": event.get("volume", ""),
                "dialogue_active": status["dialogue_active"],
            },
        )
        event = audio_state.publish(event)
        return {"ok": True, "event": event, "status": status, "delivery": "queued_for_players"}

    @router.post("/recovery/{action_id}")
    async def program_audio_recovery(action_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        if action_id == "program_audio.stop_all":
            status = apply_audio_event(audio_state, {"action": "stop_all"})
        elif action_id == "program_audio.clear_dialogue":
            audio_state.dialogue_active = 0
            audio_state.active_sources["dialogue"] = 0
            status = audio_state.status()
        elif action_id == "program_audio.disable_tts_autoplay":
            status = audio_state.status()
        else:
            raise HTTPException(404, f"Unknown audio recovery action: {action_id}")
        recovery_event = {'action': 'stop_all'} if action_id == 'program_audio.stop_all' else (
            {'action': 'stop', 'bus': 'dialogue'} if action_id == 'program_audio.clear_dialogue' else
            {'action': 'disable_tts_autoplay'})
        audio_state.publish(recovery_event)
        _record("recovery", str(identity.get("user_id") or "director"), {"action_id": action_id, "dialogue_active": status["dialogue_active"]})
        return {"ok": True, "action_id": action_id, "status": status}

    # -- independent channels, solo and meters (added 2026-11-26) -------------------------------------------
    def _mix_event(mix: Dict[str, Any], actor: str, what: str) -> Dict[str, Any]:
        event = audio_state.publish({"action": "mix", "mix": mix})
        _record("mix", actor, {"what": what, "mix_sequence": mix["sequence"]})
        return event

    @router.get("/channels")
    async def list_channels(identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"ok": True, "mix": audio_state.mix()}

    @router.post("/channels/{channel_id}")
    async def change_channel(channel_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        try:
            mix = audio_state.set_channel(channel_id, body)
        except KeyError:
            raise HTTPException(404, f"No channel {channel_id}") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        event = _mix_event(mix, str(identity.get("user_id") or "director"), f"channel {channel_id}")
        return {"ok": True, "mix": mix, "event_sequence": event["sequence"]}

    @router.post("/channels")
    async def add_channel(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        try:
            mix = audio_state.add_channel(body)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        event = _mix_event(mix, str(identity.get("user_id") or "director"), f"add {body.get('id')}")
        return {"ok": True, "mix": mix, "event_sequence": event["sequence"]}

    @router.post("/solo/clear")
    async def clear_solo(identity: Dict[str, Any] = Depends(require_role("mod"))):
        mix = audio_state.clear_solo()
        event = _mix_event(mix, str(identity.get("user_id") or "director"), "clear solo")
        return {"ok": True, "mix": mix, "event_sequence": event["sequence"]}

    @router.post("/meters")
    async def report_meters(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _json_dict(request)
        try:
            return audio_state.take_meters(body, measured_by=str(identity.get("user_id") or "director"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.get("/meters")
    async def read_meters(identity: Dict[str, Any] = Depends(require_role("mod"))):
        result = {"ok": True, "program_player": audio_state.meter_status()}
        recording = getattr(router, "recording_levels", None)
        result["recording_inputs"] = recording() if callable(recording) else []
        return result

    router.state = audio_state  # test/introspection convenience; FastAPI ignores this attr.
    return router


__all__ = ["create_program_audio_router"]
