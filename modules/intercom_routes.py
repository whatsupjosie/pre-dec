"""Routes for the director's PA (modules/intercom.py).

The paths and bodies are those of the 2026-08-24 run bundle (NowCurtsey pubcast_run_bundle main.py), so a
client written against it keeps working. Changed: the grant list and the history need mod, as granting
does (the bundle served both to anyone), and every refusal carries the intercom's own reason.

  POST /api/intercom/announce  {text, rooms: [str] | null, audio: bool = true, voice: str = "default"}
  POST /api/intercom/grant     {user_id, rooms: [str] | null, note}          mod+
  POST /api/intercom/revoke    {user_id}                                      mod+
  GET  /api/intercom/grants?include_revoked=false                             mod+
  GET  /api/intercom/history?limit=50                                         mod+
  GET  /api/intercom/status                                                   signed in
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from .intercom import ALL_ROOMS, Intercom, IntercomError
from .route_security import auth_enforced, current_identity, require_role


async def _json_dict(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Body must be JSON")
    if not isinstance(body, dict):
        raise HTTPException(400, "Body must be a JSON object")
    return body


def _rooms(body: Dict[str, Any]):
    rooms = body.get("rooms")
    if rooms is None:
        return None
    if not isinstance(rooms, list) or not all(isinstance(r, str) for r in rooms):
        raise HTTPException(400, "rooms must be a list of room ids, or null for every room")
    return rooms


def create_intercom_router(intercom: Intercom, display_name=lambda user_id: user_id) -> APIRouter:
    router = APIRouter(prefix="/api/intercom", tags=["Intercom"])

    @router.post("/announce")
    async def announce(request: Request, identity=Depends(current_identity)):
        body = await _json_dict(request)
        rooms = _rooms(body)
        audio = body.get("audio", True)
        if not isinstance(audio, bool):
            raise HTTPException(400, "audio must be true or false")
        voice = body.get("voice") or "default"
        if not isinstance(voice, str) or len(voice) > 128:
            raise HTTPException(400, "voice must be a voice id")
        user_id = identity.get("user_id", "anon")
        try:
            # With auth off (local development) every caller passes, exactly as require_role behaves.
            if auth_enforced():
                intercom.check_permission(user_id, identity.get("role", "guest"), rooms)
            ann = await intercom.announce(speaker_id=user_id, speaker_name=display_name(user_id),
                                          text=body.get("text") if isinstance(body.get("text"), str) else "",
                                          rooms=rooms, with_audio=audio, voice_id=voice)
        except IntercomError as exc:
            raise HTTPException(exc.status, str(exc))
        return {"ok": not ann.failed, **ann.to_dict()}

    @router.post("/grant")
    async def grant(request: Request, identity=Depends(require_role("mod"))):
        body = await _json_dict(request)
        target = body.get("user_id")
        if not isinstance(target, str) or not target.strip():
            raise HTTPException(400, "user_id is required")
        try:
            g = intercom.grant(target.strip(), identity.get("user_id", "anon"), rooms=_rooms(body),
                               note=str(body.get("note") or ""))
        except IntercomError as exc:
            raise HTTPException(exc.status, str(exc))
        return {"ok": True, "grant": g.to_dict()}

    @router.post("/revoke")
    async def revoke(request: Request, identity=Depends(require_role("mod"))):
        body = await _json_dict(request)
        target = body.get("user_id")
        if not isinstance(target, str) or not target.strip():
            raise HTTPException(400, "user_id is required")
        if not intercom.revoke(target.strip(), identity.get("user_id", "anon")):
            raise HTTPException(404, f"No active intercom grant for '{target.strip()}'")
        return {"ok": True, "revoked": target.strip()}

    @router.get("/grants")
    async def grants(include_revoked: bool = False, identity=Depends(require_role("mod"))):
        return {"available": True, "grants": intercom.list_grants(include_revoked=include_revoked)}

    @router.get("/history")
    async def history(limit: int = 50, identity=Depends(require_role("mod"))):
        return {"available": True, "announcements": intercom.history(limit)}

    @router.get("/status")
    async def status(identity=Depends(current_identity)):
        if auth_enforced() and not identity.get("authenticated"):
            raise HTTPException(401, "Sign in to see the intercom")
        role, user_id = identity.get("role", "guest"), identity.get("user_id", "anon")
        return {**intercom.status(), "you_may_announce": intercom.may_use(user_id, role, ALL_ROOMS)
                or any(g["user_id"] == user_id for g in intercom.list_grants())}

    router.intercom = intercom
    return router
