# PubCast AI — alex_routes.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rear View Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart

"""
Alex Core API Routes
Provides endpoints for interacting with Alex AI companion
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from .route_security import auth_enforced, current_identity

router = APIRouter(prefix="/api/alex", tags=["alex"], dependencies=[Depends(current_identity)])


def _scoped_user_id(
    *,
    request: Request,
    identity: Dict[str, Any],
    explicit_value: Any = None,
) -> str:
    """Resolve the user_id these routes should act on to the actual caller.

    SECURITY: every route below reads/writes a specific user's Alex companion
    state (messages, memory, grounding, reset) keyed by `user_id`. Previously
    that value was taken directly from an unauthenticated client-supplied
    query/body field with no check against who was actually calling -- any
    caller could read or wipe any other user's Alex by passing their id. This
    mirrors the same fix already applied to pubpartner_routes.py's
    `_scoped_user_id()`: in enforced-auth mode the caller's authenticated
    identity always wins, and a mismatched explicit value is rejected rather
    than silently trusted.
    """
    explicit = str(explicit_value or "").strip()[:128]
    header_user = str(request.headers.get("X-Client-Id") or "").strip()[:128]
    auth_user = str(identity.get("user_id") or header_user or explicit or "default").strip()[:128] or "default"
    if auth_enforced():
        if explicit and explicit != auth_user:
            raise HTTPException(status_code=403, detail="user_id does not match authenticated caller")
        if header_user and header_user != auth_user:
            raise HTTPException(status_code=403, detail="X-Client-Id does not match authenticated caller")
        return auth_user
    if header_user and explicit and header_user != explicit:
        raise HTTPException(status_code=403, detail="user_id must match X-Client-Id")
    return explicit or header_user or auth_user


class MessageRequest(BaseModel):
    """Request to send message to Alex."""
    message: str = Field(..., min_length=1, max_length=10000)
    user_id: Optional[str] = Field(None, min_length=1, max_length=128)
    context: Optional[Dict[str, Any]] = None
    typing_speed: Optional[float] = Field(60.0, ge=0.0, le=1000.0)


class StateResponse(BaseModel):
    """Alex's current state."""
    state: str
    battery: str
    engagement_score: float


def _normalize_recent_memories(memories: Any) -> List[Dict[str, Any]]:
    """Normalize Alex memory payloads for API responses across implementations."""
    normalized: List[Dict[str, Any]] = []
    for memory in memories or []:
        if isinstance(memory, dict):
            normalized.append(memory)
            continue
        normalized.append({
            "id": getattr(memory, "id", ""),
            "content": getattr(memory, "content", ""),
            "memory_type": getattr(getattr(memory, "memory_type", None), "value", str(getattr(memory, "memory_type", ""))),
            "timestamp": getattr(getattr(memory, "timestamp", None), "isoformat", lambda: "")(),
            "emotional_tags": getattr(memory, "emotional_tags", getattr(memory, "tags", [])),
        })
    return normalized


# Global alex instance/provider - will be set by main.py
_alex_core = None
_alex_provider = None


def set_alex_instance(alex_instance):
    """Set the fallback Alex instance (called from main.py)."""
    global _alex_core
    _alex_core = alex_instance


def set_alex_provider(provider):
    """Set a user-aware Alex provider, e.g. AlexJeremyBridge.alex_for."""
    global _alex_provider
    _alex_provider = provider


def _resolve_alex(user_id: Optional[str] = None):
    if _alex_provider is not None:
        return _alex_provider(user_id or "default")
    return _alex_core


@router.post("/message")
async def send_message(
    request: MessageRequest,
    http_request: Request,
    identity: Dict[str, Any] = Depends(current_identity),
):
    """Send a message to Alex and get response."""
    scoped_user = _scoped_user_id(request=http_request, identity=identity, explicit_value=request.user_id)
    alex = _resolve_alex(scoped_user)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        metadata = dict(request.context or {})
        response = await alex.process_message(
            request.message,
            typing_speed=float(request.typing_speed or 60.0),
            metadata=metadata,
            user_id=scoped_user,
        )
        return {"response": response, "status": "ok"}
    except Exception as e:
        raise HTTPException(500, f"Alex processing error: {e}")


@router.get("/state")
async def get_state(
    http_request: Request,
    user_id: Optional[str] = Query(None, min_length=1, max_length=128),
    identity: Dict[str, Any] = Depends(current_identity),
):
    """Get Alex's current state."""
    scoped_user = _scoped_user_id(request=http_request, identity=identity, explicit_value=user_id)
    alex = _resolve_alex(scoped_user)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        state = alex.get_state()
        return state
    except Exception as e:
        raise HTTPException(500, f"State retrieval error: {e}")


@router.post("/grounding")
async def trigger_grounding(
    http_request: Request,
    user_id: Optional[str] = Query(None, min_length=1, max_length=128),
    identity: Dict[str, Any] = Depends(current_identity),
):
    """Trigger a grounding exercise."""
    scoped_user = _scoped_user_id(request=http_request, identity=identity, explicit_value=user_id)
    alex = _resolve_alex(scoped_user)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        result = await alex.grounding_check()
        return {"grounding": result, "status": "ok"}
    except Exception as e:
        raise HTTPException(500, f"Grounding error: {e}")


@router.get("/memory/recent")
async def get_recent_memory(
    http_request: Request,
    limit: int = Query(10, ge=1, le=200),
    user_id: Optional[str] = Query(None, min_length=1, max_length=128),
    identity: Dict[str, Any] = Depends(current_identity),
):
    """Get recent conversation memory."""
    scoped_user = _scoped_user_id(request=http_request, identity=identity, explicit_value=user_id)
    alex = _resolve_alex(scoped_user)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        memories = alex.get_recent_memories(limit)
        normalized = _normalize_recent_memories(memories)
        return {"memories": normalized, "count": len(normalized)}
    except Exception as e:
        raise HTTPException(500, f"Memory retrieval error: {e}")


@router.post("/reset")
async def reset_alex(
    http_request: Request,
    user_id: Optional[str] = Query(None, min_length=1, max_length=128),
    identity: Dict[str, Any] = Depends(current_identity),
):
    """Reset Alex to initial state."""
    scoped_user = _scoped_user_id(request=http_request, identity=identity, explicit_value=user_id)
    alex = _resolve_alex(scoped_user)
    if not alex:
        raise HTTPException(503, "Alex Core not initialized")
    
    try:
        alex.reset()
        return {"status": "reset", "message": "Alex has been reset"}
    except Exception as e:
        raise HTTPException(500, f"Reset error: {e}")
