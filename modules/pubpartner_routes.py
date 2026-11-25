"""FastAPI routes for the PubPartner friend-preservation spine."""
from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile
from yaml import YAMLError
import os
from contextvars import ContextVar
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from . import pubpartner_chatgpt_link as chatgpt_link
from .pubpartner_rate_limit import RateLimiter
from fastapi.responses import FileResponse, PlainTextResponse

from .pubpartner_core import PubPartnerSpine
from .pubpartner_work_notes import WorkNoteNotFound, WorkNotesError
from .pubpartner_vessel import VesselConflictError
from .pubpartner_preflight import run_preflight
from .pubpartner_backup import create_friend_backup, verify_friend_backup
from .route_security import auth_enforced, current_identity, require_role
from .provider_capabilities import canonical_provider
from .local_model_config import default_provider

_request_spine = ContextVar("pubpartner_request_spine", default=None)


async def _bind_host_spine(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    # Each host owns its runtime; standalone tests may still configure _spine.
    # A second TestClient must never redirect a running host into its test store.
    token = _request_spine.set(getattr(request.app.state, "pubpartner_spine", None))
    account = chatgpt_link.current_session.set(chatgpt_link.session_id(identity))
    try:
        yield
    finally:
        chatgpt_link.current_session.reset(account)
        _request_spine.reset(token)


router = APIRouter(prefix="/api/pubpartner", tags=["pubpartner"], dependencies=[Depends(current_identity), Depends(_bind_host_spine)])
_limiter = RateLimiter()


def _limit_or_429(identity: str) -> None:
    allowed, retry_after = _limiter.allow(identity)
    if not allowed:
        raise HTTPException(status_code=429, detail={"error": "rate_limited", "retry_after": retry_after})
_spine: Optional[PubPartnerSpine] = None


def configure_pubpartner_spine(
    *,
    data_dir: Path,
    alex_bridge: Any = None,
    cricket_keeper: Any = None,
    vessel_runtime: Any = None,
    scoped_memory: bool = False,
) -> PubPartnerSpine:
    global _spine
    _spine = PubPartnerSpine(
        data_dir,
        alex_bridge=alex_bridge,
        cricket_keeper=cricket_keeper,
        vessel_runtime=vessel_runtime,
        scoped_memory=scoped_memory,
    )
    return _spine


def configure_pubpartner_byok(byok_manager: Any) -> None:
    """Attach the encrypted BYOK manager to the already-created spine."""
    get_spine().set_byok_manager(byok_manager)


def get_spine() -> PubPartnerSpine:
    if _request_spine.get() is not None:
        return _request_spine.get()
    if _spine is None:
        raise HTTPException(status_code=503, detail="PubPartner spine not initialized")
    return _spine


async def _json_dict(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    if not _is_utf8_encodable(body):
        # A lone surrogate (e.g. "\ud800") parses as JSON but cannot be stored as
        # UTF-8 verbatim. Refuse it plainly rather than failing deep in a store.
        raise HTTPException(status_code=400, detail="text contains invalid Unicode (unpaired surrogate)")
    return body


def _is_utf8_encodable(value: Any) -> bool:
    """True when every string (and key) nested in a decoded JSON value encodes as UTF-8."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                return False
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return True


def _body_id(body: Dict[str, Any], request: Request, key: str, default: str) -> str:
    return str(body.get(key) or request.headers.get("X-Client-Id") or default)[:120]




def _scoped_user_id(
    *,
    request: Request,
    identity: Dict[str, Any],
    explicit_value: Any = None,
) -> str:
    """Resolve PubPartner-owned credentials to the actual caller.

    In the normal secured launcher, a request may only operate on the
    authenticated user's knowledge credentials.  Relaxed local/test mode keeps
    the existing explicit ``user_id`` behavior, while still rejecting a body
    identity that contradicts an explicit ``X-Client-Id`` header.
    """
    explicit = str(explicit_value or "").strip()[:120]
    header_user = str(request.headers.get("X-Client-Id") or "").strip()[:120]
    auth_user = str(identity.get("user_id") or header_user or explicit or "anon").strip()[:120] or "anon"
    if auth_enforced():
        if explicit and explicit != auth_user:
            raise HTTPException(status_code=403, detail="user_id does not match authenticated caller")
        if header_user and header_user != auth_user:
            raise HTTPException(status_code=403, detail="X-Client-Id does not match authenticated caller")
        return auth_user
    if header_user and explicit and header_user != explicit:
        raise HTTPException(status_code=403, detail="user_id must match X-Client-Id")
    return explicit or header_user or auth_user


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, field: str) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field} must be an integer")
    return max(minimum, min(maximum, parsed))


@router.get("/status")
async def status() -> Dict[str, Any]:
    spine = get_spine()
    return {
        "ok": True,
        "spine": "ready",
        "verbatim_vault": str(spine.vault.root),
        "alex_bridge": spine.alex_bridge is not None,
        "jeremy_cricket": spine.cricket_keeper is not None,
        "protocols": ["FCP1-T", "FCP1-J", "FCP1-NL-fallback"],
        "providers": spine.provider_dispatcher.configured_providers(),
        "knowledge_sources": ["opencode_zen/big-pickle"],
        "knowledge_default_mode": "off",
        "live_loop": True,
        "vessel": spine.vessel_runtime.status() if spine.vessel_runtime is not None else None,
    }


@router.get("/vessel")
async def vessel_status() -> Dict[str, Any]:
    vessel = get_spine().vessel_runtime
    if vessel is None:
        raise HTTPException(status_code=503, detail="PubPartner vessel is not mounted")
    return {"ok": True, "vessel": vessel.status(), "friend": vessel.friend_profile()}


@router.get("/vessel/memory/claims")
async def vessel_claims(
    request: Request,
    status: str = "all",
    limit: int = 200,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    vessel = get_spine().vessel_runtime
    if vessel is None:
        raise HTTPException(status_code=503, detail="PubPartner vessel is not mounted")
    user_id = _scoped_user_id(request=request, identity=identity)
    allowed = {"all", "tentative", "corroborated", "confirmed", "rejected", "superseded"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="unsupported claim status")
    rows = vessel.memory.list_claims(
        subject_id=user_id,
        status=status,
        limit=_bounded_int(
            limit, default=200, minimum=1, maximum=2_000, field="limit"
        ),
    )
    return {"ok": True, "user_id": user_id, "claims": [row.to_dict() for row in rows]}


@router.post("/vessel/memory/claims/{claim_id}/corrections")
async def correct_vessel_claim(
    claim_id: str,
    request: Request,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    vessel = get_spine().vessel_runtime
    if vessel is None:
        raise HTTPException(status_code=503, detail="PubPartner vessel is not mounted")
    body = await _json_dict(request)
    user_id = _scoped_user_id(request=request, identity=identity)
    try:
        existing = vessel.memory.claim(claim_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="memory claim not found")
    if existing.subject_id != user_id:
        raise HTTPException(status_code=404, detail="memory claim not found")
    try:
        corrected = vessel.memory.correct_claim(
            claim_id,
            action=str(body.get("action") or ""),
            reason=str(body.get("reason") or ""),
            replacement_text=str(body.get("replacement_text") or ""),
            event_id=str(body.get("event_id") or "") or None,
        )
    except VesselConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "claim": corrected.to_dict()}


@router.post("/sessions")
async def create_session(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    spine = get_spine()
    return await spine.create_session(
        user_id=_scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id")),
        session_id=body.get("session_id"),
        project_id=str(body.get("project_id") or "default")[:120],
        room_id=str(body.get("room_id") or "pubpartner")[:120],
        friend=body.get("friend") if isinstance(body.get("friend"), (dict, str)) else None,
        user_primer=body.get("user") if isinstance(body.get("user"), dict) else None,
        provider=_public_provider(body.get("provider")),
    )


@router.get("/sessions/{session_id}")
async def read_session(session_id: str, request: Request, user_id: Optional[str] = None, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    state = get_spine()._read_session_state(scoped_user, session_id)
    if not state:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "session": state}


def _public_provider(value):
    if isinstance(value, dict):
        clean = dict(value)
        for key in ("allow_inline_key", "api_key", "api_key_env", "extra_headers"):
            clean.pop(key, None)
        return clean
    return value if isinstance(value, str) else None


def _turn_kwargs(body: Dict[str, Any], request: Request, identity: Dict[str, Any]) -> Dict[str, Any]:
    body = dict(body)
    if not body.get("provider") and getattr(request.app.state, "pubpartner_spine", None) is not None:
        try:
            body["provider"] = default_provider()
        except ValueError:
            raise HTTPException(409, "Repair the local launcher or select a provider in Connections.") from None
    if "allow_fallback" in body and not isinstance(body["allow_fallback"], bool):
        raise HTTPException(400, "allow_fallback must be a boolean")
    # v20/2i uses messages[]; the vessel client uses message + history. Both
    # contracts terminate here, with one live route and one runtime authority.
    if "messages" in body:
        messages = body["messages"]
        if not isinstance(messages, list) or not messages or len(messages) > 100:
            raise HTTPException(400, "messages must contain 1–100 conversation turns")
        for row in messages:
            if not isinstance(row, dict) or row.get("role") not in {"user", "assistant", "system"} or not isinstance(row.get("content"), str):
                raise HTTPException(400, "each message requires a role and string content")
        if messages[-1]["role"] != "user":
            raise HTTPException(400, "messages must end with the current user turn")
        if "message" in body and body["message"] != messages[-1]["content"]:
            raise HTTPException(400, "message and messages disagree")
        body["message"] = messages[-1]["content"]
        body["history"] = messages[:-1]
    message = body.get("message")
    if message is None:
        raise HTTPException(status_code=400, detail="message is required")
    behaviour = body.get("behaviour")
    if behaviour is not None and not isinstance(behaviour, dict):
        raise HTTPException(400, "behaviour must be an object (keyboard, voice and face measurements with consent)")
    if not isinstance(message, str):
        raise HTTPException(status_code=400, detail="message must be a string so exact user text is not silently coerced")
    if not message.strip():
        raise HTTPException(400, "message must not be empty")
    history = body.get("history", [])
    if not isinstance(history, list) or len(history) > 100 or any(
        not isinstance(row, dict) or row.get("role") not in {"user", "assistant", "system"}
        or not isinstance(row.get("content"), str) for row in history
    ):
        raise HTTPException(400, "history must contain at most 100 text turns")
    body["provider"] = _public_provider(body.get("provider"))
    # SECURITY: user_id must be bound to the authenticated caller, not taken
    # verbatim from client-submitted body content. This value flows through
    # build_turn_packet()/run_turn() into the fcp1 packet's "u.id" field,
    # which pubpartner_provider.PubPartnerProviderDispatcher.dispatch() then
    # uses to look up and spend that user's stored BYOK provider credentials.
    # Using the unchecked body value here would let any authenticated caller
    # set user_id to someone else's id and cause the server to use that other
    # user's credentials on their behalf (cross-tenant credential use).
    # _scoped_user_id() (already used by the /knowledge/credentials routes
    # below) is the correct, existing helper for this and is reused here.
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    return {
        "user_id": scoped_user,
        "session_id": str(body.get("session_id") or "default")[:120],
        "message": message,
        "project_id": str(body.get("project_id") or "default")[:120],
        "room_id": str(body.get("room_id") or "pubpartner")[:120],
        "friend": body.get("friend") if isinstance(body.get("friend"), (dict, str)) else None,
        "user_primer": body.get("user") if isinstance(body.get("user"), dict) else None,
        "provider": body.get("provider") if isinstance(body.get("provider"), (dict, str)) else None,
        "knowledge": body.get("knowledge") if isinstance(body.get("knowledge"), dict) else None,
        "task": body.get("task") if isinstance(body.get("task"), dict) else None,
        "output": body.get("output") if isinstance(body.get("output"), dict) else None,
        "safety": body.get("safety") if isinstance(body.get("safety"), list) else None,
        "content_kind": str(body.get("content_kind") or "message")[:80],
        "language": str(body.get("language") or "en-US")[:32],
        "history": body.get("history") if isinstance(body.get("history"), list) else None,
        "max_memories": _bounded_int(body.get("max_memories"), default=6, minimum=0, maximum=24, field="max_memories"),
        "prompt_mode": str(body.get("prompt_mode") or "auto")[:40],
        # Keyboard, voice and face measurements for the EQ observation layer. Each is used only
        # when its consent flag is true; see modules/eq_observation/features.py.
        "behaviour": behaviour,
    }

@router.post("/turns")
async def build_turn(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    spine = get_spine()
    kwargs = _turn_kwargs(body, request, identity)
    if bool(body.get("generate_response") or body.get("live")):
        return await spine.run_turn(
            **kwargs,
            allow_fallback=bool(body.get("allow_fallback", getattr(request.app.state, "pubpartner_spine", None) is None)),
        )
    kwargs.pop("knowledge", None)
    return await spine.build_turn_packet(**kwargs)


@router.post("/turns/live")
async def live_turn(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    spine = get_spine()
    if getattr(request.app.state, "pubpartner_spine", None) is not None:
        # Full Reach never defaults a real user to the deterministic test model.
        body.setdefault("allow_fallback", False)
    kwargs = _turn_kwargs(body, request, identity)
    _limit_or_429(kwargs["user_id"])
    result = await spine.run_turn(
        **kwargs,
        allow_fallback=bool(body.get("allow_fallback", True)),
    )
    # Keep the legacy reply key while retaining vessel/provider receipts.
    result["reply"] = result.get("friend_response", "")
    friend_id = (result.get("fcp1", {}).get("f") or {}).get("id", "friend")
    result["role"] = "pub_partner_" + friend_id
    result["ok"] = bool((result.get("provider_result") or {}).get("ok"))
    eq_recorder = getattr(request.app.state, "eq_monitoring_recorder", None)
    if eq_recorder is not None:
        try:
            session_id = kwargs["session_id"]
            turn_id = str(result.get("turn_id") or result.get("receipt_id") or "") or None
            eq_recorder.record_message({"session_id":session_id,"room":kwargs.get("room_id"),"turn_id":turn_id,"user_id":kwargs["user_id"],"role":"user","text":kwargs["message"]})
            eq_recorder.record_provider(session_id,{"turn_id":turn_id,"user_id":kwargs["user_id"],"provider_request":kwargs.get("provider"),"provider_result":result.get("provider_result"),"provider_fallback":result.get("provider_fallback")})
            eq_recorder.record_message({"session_id":session_id,"room":kwargs.get("room_id"),"turn_id":turn_id,"user_id":"pubpartner:"+str(friend_id),"role":"assistant","text":str(result.get("friend_response") or "" )})
            eq_recorder.record_outcome(session_id,{"turn_id":turn_id,"ok":result["ok"],"role":result["role"],"response_length":len(str(result.get("friend_response") or ""))})
        except Exception:
            pass  # evidence capture must not change the user-facing provider result
    if not result["ok"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(result, status_code=503)
    return result


@router.get("/knowledge/specs")
async def knowledge_specs() -> Dict[str, Any]:
    return get_spine().knowledge.specs()


@router.get("/knowledge/credentials")
async def knowledge_credentials(
    request: Request,
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().knowledge.list_zen_credentials(user_id=scoped_user)


@router.post("/knowledge/credentials")
async def register_knowledge_credential(
    request: Request,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    body = await _json_dict(request)
    user_id = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    _limit_or_429(f"knowledge-key:{user_id}")
    api_key = body.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise HTTPException(status_code=400, detail="api_key must be a non-empty string")
    result = await get_spine().knowledge.register_zen_key(
        user_id=user_id,
        api_key=api_key,
        display_name=str(body.get("display_name") or "OpenCode Zen — Big Pickle")[:120],
    )
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Unable to store Zen key")
    return result


@router.get("/knowledge/status")
async def knowledge_status(
    request: Request,
    user_id: Optional[str] = None,
    credential_model_id: str = "",
    mode: str = "off",
    live: bool = False,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return await get_spine().knowledge.status(
        user_id=scoped_user,
        config={
            "provider": "opencode_zen",
            "model": "big-pickle",
            "credential_model_id": credential_model_id[:180],
            "mode": mode[:20],
        },
        live=bool(live),
    )


@router.post("/knowledge/test")
async def knowledge_test(
    request: Request,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    body = await _json_dict(request)
    user_id = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    _limit_or_429(f"knowledge-test:{user_id}")
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="message must be a non-empty string")
    cfg = body.get("knowledge") if isinstance(body.get("knowledge"), dict) else {}
    cfg = dict(cfg)
    cfg.setdefault("mode", "shadow")
    result = await get_spine().knowledge.query(
        user_id=user_id,
        message=message,
        config=cfg,
        task=body.get("task") if isinstance(body.get("task"), dict) else {"mode": "knowledge_diagnostic"},
    )
    return {"ok": result.ok, "knowledge_result": result.as_dict()}


def _provider_byok_manager() -> Any:
    manager = get_spine().provider_dispatcher.byok_manager
    if manager is None:
        raise HTTPException(status_code=503, detail="Provider credential vault is unavailable")
    return manager


@router.get("/providers/credentials")
async def provider_credentials(
    request: Request,
    user_id: Optional[str] = None,
    provider: str = "",
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    """List redacted user-owned provider configurations.

    API keys never leave the encrypted credential store.  The returned model_id
    is the opaque handle accepted by live-turn provider configuration.
    """
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    requested = canonical_provider(provider) if provider else ""
    rows = _provider_byok_manager().list_user_models(scoped_user)
    if requested:
        rows = [row for row in rows if canonical_provider(str(row.get("provider") or "")) == requested]
    return {"ok": True, "configured": rows}


@router.post("/providers/credentials")
async def register_provider_credential(
    request: Request,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    """Store a cloud-provider key without echoing or live-testing it by default."""
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    _limit_or_429(f"provider-key:{scoped_user}")
    provider = canonical_provider(str(body.get("provider") or ""))
    allowed = {"openai", "anthropic", "gemini", "mistral", "groq", "xai", "opencode_zen"}
    if provider not in allowed:
        raise HTTPException(status_code=400, detail=f"provider must be one of {sorted(allowed)}")
    model = str(body.get("model") or body.get("model_name") or "").strip()[:180]
    api_key = body.get("api_key")
    if not model:
        raise HTTPException(status_code=400, detail="model must be a non-empty provider model ID")
    if not isinstance(api_key, str) or not api_key.strip():
        raise HTTPException(status_code=400, detail="api_key must be a non-empty string")
    manager = _provider_byok_manager()
    try:
        model_id = await manager.register_key(
            user_id=scoped_user,
            provider=provider,
            model_name=model,
            api_key=api_key.strip(),
            display_name=str(body.get("display_name") or f"{provider} / {model}")[:120],
            run_fidelity=bool(body.get("run_fidelity", False)),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to store provider credential: {type(exc).__name__}")
    return {
        "ok": True,
        "credential_model_id": model_id,
        "provider": provider,
        "model": model,
        "api_key_stored": True,
        "api_key": None,
    }


def _owner_connector(request, identity):
    if not identity.get("authenticated") or identity.get("role") != "owner":
        raise HTTPException(403, "Sign in as the host owner to manage its connector.")
    host = getattr(request.app.state, "pubpartner_connector", None)
    if host is None:
        raise HTTPException(503, "The connector launcher is unavailable on this host.")
    return host


@router.get("/connector")
async def connector_status(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    return _owner_connector(request, identity).status()


@router.put("/connector/cartridge")
async def select_connector_cartridge(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    host = _owner_connector(request, identity)
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > 8 * 1024 * 1024:
            raise HTTPException(413, "Choose a cartridge under 8 MiB compressed.")
        payload.extend(chunk)
    try:
        return await host.select(payload)
    except (ValueError, RuntimeError, KeyError, TypeError, AttributeError, OSError,
            BadZipFile, YAMLError):
        raise HTTPException(400, "Stop the connector and choose a valid PubPartner cartridge ZIP.") from None


@router.post("/connector")
async def connector_start(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    host = _owner_connector(request, identity)
    body = await _json_dict(request)
    try:
        return await host.start(body.get("route"), create=body.get("create") is True)
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from None


@router.delete("/connector")
async def connector_stop(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    return await _owner_connector(request, identity).stop()


@router.get("/chatgpt/account")
async def chatgpt_account(identity: Dict[str, Any] = Depends(current_identity)):
    return chatgpt_link.status(chatgpt_link.session_id(identity))


@router.post("/chatgpt/connect")
async def chatgpt_connect(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    try:
        return await chatgpt_link.begin(identity, host_id=request.app.state.guest_admission.host_id,
                                        origin=request.headers.get("origin") or str(request.base_url).rstrip("/"))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "OpenAI sign-in discovery failed.") from None


@router.post("/chatgpt/finish")
async def chatgpt_finish(request: Request, identity: Dict[str, Any] = Depends(current_identity)):
    try:
        return await chatgpt_link.finish(identity, await _json_dict(request))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "OpenAI account verification or model discovery failed. Reconnect to retry.") from None


@router.delete("/chatgpt/account")
async def chatgpt_disconnect(identity: Dict[str, Any] = Depends(current_identity)):
    session = chatgpt_link.require_session(identity)
    chatgpt_link.accounts.pop(session, None)
    chatgpt_link.pending.pop(session, None)
    return {"ok": True}


@router.get("/providers/catalog")
async def provider_catalog() -> Dict[str, Any]:
    dispatcher = get_spine().provider_dispatcher
    return {"ok": True, "providers": dispatcher.catalog()}


@router.get("/providers/status")
async def provider_status(
    request: Request,
    provider: str = "all",
    model: str = "",
    host: str = "",
    base_url: str = "",
    credential_model_id: str = "",
    require_api_key: bool = True,
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    config = {
        "provider": provider,
        "model": model,
        "host": host,
        "base_url": base_url,
        "credential_model_id": credential_model_id[:180],
        "require_api_key": require_api_key,
    }
    return await get_spine().provider_dispatcher.status(provider, config, user_id=scoped_user)


@router.get("/preflight")
async def preflight(host: str = "127.0.0.1", port: int = 8000) -> Dict[str, Any]:
    spine = get_spine()
    return run_preflight(data_dir=spine.data_dir, app_root=Path.cwd(), host=host, port=port)


@router.get("/launch-check")
async def launch_check(identity=Depends(require_role("owner"))) -> Dict[str, Any]:
    return await get_spine().launch_check()


@router.get("/sources")
async def list_sources(request: Request, user_id: str, session_id: str, limit: int = 50, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().session_sources(user_id=scoped_user, session_id=session_id, limit=max(1, min(200, int(limit))))


@router.get("/sources/{source_id}/span")
async def restore_source_span(source_id: str, request: Request, user_id: str, session_id: str, start: int = 0, end: Optional[int] = None, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    try:
        return get_spine().restore_source_span(user_id=scoped_user, session_id=session_id, source_id=source_id, start=start, end=end)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="source not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/sources/{source_id}/verify-quote")
async def verify_quote(source_id: str, request: Request, user_id: str, session_id: str, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    quote = body.get("quote")
    if not isinstance(quote, str):
        raise HTTPException(status_code=400, detail="quote must be a string")
    try:
        return get_spine().verify_quote(
            user_id=scoped_user,
            session_id=session_id,
            source_id=source_id,
            quote=quote,
            normalize_newlines=bool(body.get("normalize_newlines", False)),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="source not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/sources/{source_id}")
async def restore_source(source_id: str, request: Request, user_id: str, session_id: str, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    try:
        return get_spine().restore_source(user_id=scoped_user, session_id=session_id, source_id=source_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="source not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/sessions/{session_id}/turns")
async def read_session_turns(session_id: str, request: Request, user_id: Optional[str] = None, limit: int = 50, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().list_turns(user_id=scoped_user, session_id=session_id, limit=max(1, min(500, int(limit))))


@router.get("/profiles/{kind}")
async def list_profiles(kind: str, request: Request, identity=Depends(current_identity)) -> Dict[str, Any]:
    if kind not in {"friend", "user", "provider"}:
        raise HTTPException(status_code=400, detail="kind must be friend, user, or provider")
    result = get_spine().list_profiles(kind)
    if kind == "user" and auth_enforced():
        owner = _scoped_user_id(request=request, identity=identity)
        result["profiles"] = [profile for profile in result["profiles"] if profile.get("id") == owner]
    return result


@router.get("/profiles/{kind}/{profile_id}")
async def read_profile(kind: str, profile_id: str, request: Request, identity=Depends(current_identity)) -> Dict[str, Any]:
    if kind not in {"friend", "user", "provider"}:
        raise HTTPException(status_code=400, detail="kind must be friend, user, or provider")
    if kind == "user" and auth_enforced() and profile_id != _scoped_user_id(request=request, identity=identity):
        raise HTTPException(404, "profile not found")
    return get_spine().load_profile(kind, profile_id)


@router.post("/profiles/{kind}/{profile_id}")
async def save_profile(kind: str, profile_id: str, request: Request, identity=Depends(require_role("mod"))) -> Dict[str, Any]:
    if kind not in {"friend", "user", "provider"}:
        raise HTTPException(status_code=400, detail="kind must be friend, user, or provider")
    body = await _json_dict(request)
    return get_spine().save_profile(kind, profile_id, body)


@router.post("/guidance")
async def add_guidance(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    try:
        return get_spine().add_guidance(
            user_id=_scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id")),
            friend_id=str(body.get("friend_id") or body.get("friend") or "*")[:120],
            project_id=str(body.get("project_id") or "*")[:120],
            kind=str(body.get("kind") or "preference")[:60],
            text=text,
            priority=_bounded_int(body.get("priority"), default=5, minimum=1, maximum=10, field="priority"),
            applies_to=[str(v)[:80] for v in body.get("applies_to", [])] if isinstance(body.get("applies_to", []), list) else [],
            metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/guidance")
async def list_guidance(request: Request, user_id: Optional[str] = None, friend_id: str = "*", project_id: str = "*", limit: int = 100, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().list_guidance(user_id=scoped_user, friend_id=friend_id, project_id=project_id, limit=max(1, min(500, int(limit))))


@router.get("/receipts")
async def list_receipts(request: Request, user_id: str, session_id: str, limit: int = 50, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().list_receipts(user_id=scoped_user, session_id=session_id, limit=max(1, min(500, int(limit))))


@router.get("/receipts/verify")
async def verify_receipts(request: Request, user_id: str, session_id: str, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().verify_receipts(user_id=scoped_user, session_id=session_id)


@router.get("/relationship/summary")
async def relationship_summary(
    request: Request,
    user_id: Optional[str] = None,
    friend_id: str = "alex",
    project_id: str = "*",
    session_id: str = "*",
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().relationship_summary(
        user_id=scoped_user[:120], friend_id=friend_id[:120],
        project_id=project_id[:120], session_id=session_id[:120],
    )


@router.get("/relationship/lessons")
async def relationship_lessons(
    request: Request,
    user_id: Optional[str] = None,
    friend_id: str = "alex",
    status: str = "all",
    project_id: str = "*",
    session_id: str = "*",
    limit: int = 200,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().list_relationship_lessons(
        user_id=scoped_user[:120], friend_id=friend_id[:120], status=status[:40],
        project_id=project_id[:120], session_id=session_id[:120],
        limit=max(1, min(1000, int(limit))),
    )


@router.post("/relationship/lessons")
async def add_relationship_lesson(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    try:
        return get_spine().add_relationship_lesson(
            user_id=_scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id")),
            friend_id=str(body.get("friend_id") or "alex")[:120],
            text=text,
            kind=str(body.get("kind") or "preference")[:40],
            scope=str(body.get("scope") or "global")[:40],
            project_id=str(body.get("project_id") or "*")[:120],
            session_id=str(body.get("session_id") or "*")[:120],
            status=str(body.get("status") or "confirmed")[:40],
            confidence=float(body.get("confidence", 1.0)),
            source="manual_user_review",
            evidence_ids=body.get("evidence_ids") if isinstance(body.get("evidence_ids"), list) else [],
            exceptions=body.get("exceptions") if isinstance(body.get("exceptions"), list) else [],
            metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/relationship/lessons/{lesson_id}")
async def update_relationship_lesson(lesson_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    user_id = _scoped_user_id(request=request, identity=identity, explicit_value=body.pop("user_id", None))
    friend_id = str(body.pop("friend_id", "alex"))[:120]
    try:
        return get_spine().update_relationship_lesson(
            user_id=user_id, friend_id=friend_id, lesson_id=lesson_id[:180], patch=body,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="relationship lesson not found")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/relationship/encounters")
async def relationship_encounters(request: Request, user_id: Optional[str] = None, friend_id: str = "alex", limit: int = 100, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return get_spine().list_relationship_encounters(
        user_id=scoped_user[:120], friend_id=friend_id[:120], limit=max(1, min(1000, int(limit))),
    )


@router.post("/backup")
async def create_backup(request: Request, identity: Dict[str, Any] = Depends(require_role("owner"))) -> Dict[str, Any]:
    body = await _json_dict(request)
    user_id = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    friend_id = str(body.get("friend_id") or "alex")[:120]
    return create_friend_backup(get_spine().data_dir, user_id=user_id, friend_id=friend_id)


@router.get("/backups/{filename}")
async def download_backup(filename: str, identity=Depends(require_role("owner"))):
    safe = Path(filename).name
    if safe != filename or not safe.endswith(".zip"):
        raise HTTPException(status_code=400, detail="invalid backup filename")
    path = get_spine().data_dir / "pubpartner" / "backups" / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="backup not found")
    check = verify_friend_backup(path)
    if not check.get("ok"):
        raise HTTPException(status_code=409, detail=f"backup failed verification: {check.get('error')}")
    return FileResponse(path, media_type="application/zip", filename=safe)


@router.get("/backups/{filename}/verify")
async def verify_backup(filename: str, identity=Depends(require_role("owner"))) -> Dict[str, Any]:
    safe = Path(filename).name
    if safe != filename or not safe.endswith(".zip"):
        raise HTTPException(status_code=400, detail="invalid backup filename")
    return verify_friend_backup(get_spine().data_dir / "pubpartner" / "backups" / safe)


@router.get("/living/state")
async def living_state(request: Request, user_id: Optional[str] = None, session_id: str = "pubpartner_live", provider: str = "all", model: str = "", host: str = "", identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """Small live telemetry packet for the cinematic UI.

This is deliberately honest: it reports provider health, vault/receipt status,
recent turn counts, and rate limiter state. It does not claim live Llama/Ollama
works unless the local service actually answers.
    """
    user_id = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    spine = get_spine()
    providers = await spine.provider_dispatcher.status(provider, {"provider": provider, "model": model, "host": host})
    receipts = spine.list_receipts(user_id=user_id, session_id=session_id, limit=12)
    receipt_verify = spine.verify_receipts(user_id=user_id, session_id=session_id)
    turns = spine.list_turns(user_id=user_id, session_id=session_id, limit=12)
    sources = spine.session_sources(user_id=user_id, session_id=session_id, limit=12)
    relationship = spine.relationship_summary(user_id=user_id, friend_id="alex", project_id="pubpartner", session_id=session_id)
    return {
        "ok": True,
        "mode": "living_systems_telemetry",
        "user_id": user_id,
        "session_id": session_id,
        "provider_focus": provider,
        "providers": providers,
        "counts": {
            "turns": len(turns.get("turns", [])),
            "receipts": len(receipts.get("receipts", [])),
            "sources": len(sources.get("sources", [])),
            "relationship_lessons": int((relationship.get("counts") or {}).get("confirmed", 0)),
            "relationship_emerging": int((relationship.get("counts") or {}).get("provisional", 0)),
        },
        "relationship": relationship,
        "receipt_chain": receipt_verify,
        "source_audit": sources.get("audit"),
        "limiter": {"buckets": _limiter.snapshot()},
        "lantern": {
            "pulse": "online" if receipt_verify.get("ok", True) else "check_receipts",
            "caption": "Friend loop breathing; exact source custody active."
        }
    }


@router.post("/tokens/estimate")
async def estimate_tokens(request: Request) -> Dict[str, Any]:
    body = await _json_dict(request)
    text = body.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="text must be a string")
    return get_spine().estimate_prompt_tokens(
        text=text,
        provider=str(body.get("provider") or "generic")[:60],
        model=str(body.get("model") or "unknown")[:120],
    )


@router.post("/providers/test")
async def provider_test(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    _limit_or_429(scoped_user)
    provider = _public_provider(body.get("provider")) or (default_provider() if getattr(request.app.state, "pubpartner_spine", None) is not None else {"provider": "mock"})
    if "allow_fallback" in body and not isinstance(body["allow_fallback"], bool):
        raise HTTPException(400, "allow_fallback must be a boolean")
    # This runs a tiny live loop with the requested provider config. If a live provider
    # is missing, allow_fallback=false lets the caller see the honest failure.
    result = await get_spine().run_turn(
        user_id=scoped_user,
        session_id=str(body.get("session_id") or "provider_test")[:120],
        message=str(body.get("message") or "Provider diagnostic: answer with one short sentence."),
        provider=provider,
        task={"mode": "provider_diagnostic", "goal": "test_provider_availability"},
        allow_fallback=bool(body.get("allow_fallback", False)),
    )
    return {
        "ok": result.get("provider_result", {}).get("ok") is True,
        "provider_result": result.get("provider_result"),
        "provider_fallback": result.get("provider_fallback"),
        "friend_response": result.get("friend_response"),
        "receipt": result.get("receipt"),
    }


@router.get("/providers/local-discovery")
async def discover_local_models():
    from .pubpartner_local_setup import discover
    return await discover()


@router.post("/providers/local-start")
async def start_local_ollama(request: Request, identity=Depends(current_identity)):
    _owner_connector(request, identity)
    try:
        await request.app.state.pubpartner_local_ollama.start()
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from None
    return {"ok": True}


@router.post("/providers/local-starter")
async def install_local_starter(request: Request, identity=Depends(current_identity)):
    import httpx
    _owner_connector(request, identity)
    try:
        await request.app.state.pubpartner_local_ollama.install_starter()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(409, "Ollama could not finish the download. Check the connection and retry.") from None
    return {"ok": True}


@router.get("/connector/brief")
async def preview_cartridge_brief(request: Request, identity=Depends(current_identity)):
    import asyncio
    import tempfile
    from zipfile import ZipFile
    from fastapi.responses import JSONResponse
    from pubpartner.cartridge import load_cartridge
    from pubpartner.prompt_assembler import assemble_prompt
    host = _owner_connector(request, identity)
    def read_brief():
        # Only use the owner-selected, previously validated ZIP.
        with tempfile.TemporaryDirectory() as directory, ZipFile(host.selected) as archive:
            archive.extractall(directory)
            root = Path(directory)
            entries = list(root.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                root = entries[0]
            with load_cartridge(root) as cartridge:
                return assemble_prompt(cartridge).text
    try:
        brief = await asyncio.to_thread(read_brief)
    except FileNotFoundError:
        raise HTTPException(409, "Choose your cartridge ZIP first.") from None
    return JSONResponse({"brief": brief}, headers={"Cache-Control":"no-store"})


@router.get("/connector/claude-desktop.mcpb")
async def claude_desktop_extension():
    from io import BytesIO
    from zipfile import ZipFile
    from fastapi.responses import Response
    folder = Path(__file__).resolve().parents[1] / "pubpartner" / "claude_desktop"
    data = BytesIO()
    with ZipFile(data, "w") as bundle:
        for name in ("server.js", "manifest.json"):
            bundle.write(folder / name, name)
    return Response(data.getvalue(), media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="PubPartner.mcpb"'})


@router.get("/providers/local-config")
async def local_model_defaults():
    try:
        return {"enabled": bool(os.getenv("PUBCAST_LOCAL_MODEL_URL")), "provider": default_provider()}
    except ValueError:
        return {"enabled": False, "provider": None, "error": "Local launcher settings are incomplete."}


# ── Project work notes ──────────────────────────────────────────────────────
# User-owned notes per project: what was decided, worked on, left open, and
# discussed. Detected notes wait as drafts in one autosave per session until
# the user saves them; only saved notes reach a model. Note words are never
# edited: a fix is a new note that replaces the old one.

def _work_notes_call(action):
    try:
        return action()
    except WorkNoteNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except WorkNotesError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/work-notes")
async def list_work_notes(
    request: Request,
    project_id: str = "default",
    status: str = "saved",
    session_id: str = "",
    limit: int = 500,
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    bounded = _bounded_int(limit, default=500, minimum=1, maximum=5000, field="limit")
    return _work_notes_call(lambda: get_spine().work_notes.list_notes(
        user_id=scoped_user, project_id=project_id, status=status[:20],
        session_id=session_id, limit=bounded))


@router.get("/work-notes/drafts")
async def list_work_note_drafts(
    request: Request,
    project_id: str = "default",
    session_id: str = "",
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return _work_notes_call(lambda: get_spine().work_notes.drafts(
        user_id=scoped_user, project_id=project_id, session_id=session_id))


@router.get("/work-notes/export", response_class=PlainTextResponse)
async def export_work_notes(
    request: Request,
    project_id: str = "default",
    include_drafts: bool = False,
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> PlainTextResponse:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    text = _work_notes_call(lambda: get_spine().work_notes.export_text(
        user_id=scoped_user, project_id=project_id, include_drafts=include_drafts))
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")


@router.get("/work-notes/verify")
async def verify_work_notes(
    request: Request,
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    return _work_notes_call(lambda: get_spine().work_notes.verify(user_id=scoped_user))


@router.get("/work-notes/{note_id}/source")
async def work_note_source(
    note_id: str,
    request: Request,
    user_id: Optional[str] = None,
    identity: Dict[str, Any] = Depends(current_identity),
) -> Dict[str, Any]:
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=user_id)
    try:
        return _work_notes_call(lambda: get_spine().work_note_source(user_id=scoped_user, note_id=note_id))
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=f"source for this note could not be restored: {exc}")


@router.post("/work-notes")
async def add_work_note(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    if "save" in body and not isinstance(body["save"], bool):
        raise HTTPException(status_code=400, detail="save must be a boolean")
    return _work_notes_call(lambda: get_spine().work_notes.add_note(
        user_id=scoped_user,
        project_id=str(body.get("project_id") or "default"),
        kind=str(body.get("kind") or ""),
        text=body.get("text"),
        session_id=str(body.get("session_id") or ""),
        save=bool(body.get("save", False)),
    ))


@router.post("/work-notes/save")
async def save_work_notes(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    note_ids = body.get("note_ids")
    if note_ids is not None and (not isinstance(note_ids, list) or not all(isinstance(n, str) for n in note_ids)):
        raise HTTPException(status_code=400, detail="note_ids must be a list of note ids")
    return _work_notes_call(lambda: get_spine().work_notes.save(
        user_id=scoped_user,
        project_id=str(body.get("project_id") or "default"),
        session_id=str(body.get("session_id") or ""),
        note_ids=note_ids,
    ))


@router.post("/work-notes/{note_id}/replace")
async def replace_work_note(note_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    return _work_notes_call(lambda: get_spine().work_notes.replace(
        user_id=scoped_user, note_id=note_id, text=body.get("text"), kind=str(body.get("kind") or "")))


@router.post("/work-notes/{note_id}/drop")
async def drop_work_note(note_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    return _work_notes_call(lambda: get_spine().work_notes.drop(user_id=scoped_user, note_id=note_id))


@router.post("/work-notes/{note_id}/withdraw")
async def withdraw_work_note(note_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    scoped_user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    return _work_notes_call(lambda: get_spine().work_notes.withdraw(user_id=scoped_user, note_id=note_id))


# Calibration is owned by the existing PubPartner host spine, not a second server.
from .pubpartner_calibration import CalibrationStore, CalibrationError


def _calibration_store() -> CalibrationStore:
    return CalibrationStore(get_spine().data_dir)


@router.post("/calibration/interviews")
async def calibration_start(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    try:
        return _calibration_store().start(
            user_id=user,
            partner_id=str(body.get("partner_id") or ""),
            mode=str(body.get("mode") or ""),
        )
    except CalibrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/calibration/interviews")
async def calibration_list(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    user = _scoped_user_id(request=request, identity=identity)
    return {"ok": True, "interviews": _calibration_store().list_interviews(user_id=user)}


@router.get("/calibration/interviews/{interview_id}")
async def calibration_get(interview_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    user = _scoped_user_id(request=request, identity=identity)
    try:
        return _calibration_store().get(user_id=user, interview_id=interview_id)
    except (CalibrationError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="calibration interview not found")


@router.post("/calibration/interviews/{interview_id}/events")
async def calibration_event(interview_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    body = await _json_dict(request)
    user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    try:
        return _calibration_store().record(
            user_id=user, interview_id=interview_id,
            action=str(body.get("action") or ""),
            text=body.get("text") or "",
            question_id=str(body.get("question_id") or ""),
            evidence=body.get("evidence"), modality=str(body.get("modality") or "text"),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="calibration interview not found")
    except CalibrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/calibration/interviews/{interview_id}/finish")
async def calibration_finish(interview_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    user = _scoped_user_id(request=request, identity=identity)
    try:
        return _calibration_store().finish_formal(user_id=user, interview_id=interview_id)
    except (CalibrationError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="calibration interview not found")


@router.post("/calibration/interviews/{interview_id}/close")
async def calibration_close(interview_id: str, request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    user = _scoped_user_id(request=request, identity=identity)
    try:
        return _calibration_store().close(user_id=user, interview_id=interview_id)
    except (CalibrationError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="calibration interview not found")


@router.get("/calibration/moments")
async def calibration_moments(request: Request, session_id: str = "pubpartner_live",
                              friend_id: str = "alex",
                              identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """Actual recent exchanges across sessions, scoped by user and partner.

    Encounter rows are pointers only. Read real replies from the session turn log
    and original user messages from VerbatimVault. Never fabricate EQ findings.
    """
    user_id = _scoped_user_id(request=request, identity=identity)
    spine = get_spine()
    fid = str(friend_id or "alex")[:120]
    preferred = str(session_id or "pubpartner_live")[:120]
    encounters = spine.list_relationship_encounters(
        user_id=user_id, friend_id=fid, limit=120).get("encounters", [])
    encountered_sessions = list(dict.fromkeys(
        [preferred, *[str(row.get("session_id") or "") for row in reversed(encounters)
                     if isinstance(row, dict) and row.get("session_id")]]
    ))[:30]
    moments = []
    seen = set()
    for sid in encountered_sessions:
        try:
            turns = spine.list_turns(user_id=user_id, session_id=sid, limit=60)["turns"]
        except (OSError, ValueError, KeyError, FileNotFoundError):
            continue
        for turn in reversed(turns):
            if not isinstance(turn, dict) or not (turn.get("provider_result") or {}).get("ok"):
                continue
            source = turn.get("source") or {}
            source_id = str(source.get("id") or "")
            if not source_id or (sid, source_id) in seen:
                continue
            turn_friend = str(((turn.get("fcp1") or {}).get("f") or {}).get("id") or fid)
            if turn_friend != fid:
                continue
            try:
                exact = spine.restore_source(user_id=user_id, session_id=sid, source_id=source_id)
            except (OSError, ValueError, KeyError, FileNotFoundError):
                continue
            user_text = str(exact.get("text") or "")
            partner_text = str(turn.get("friend_response") or "")
            if not user_text or not partner_text:
                continue
            seen.add((sid, source_id))
            moments.append({
                "session_id": sid, "source_id": source_id,
                "turn_id": str(turn.get("turn_id") or (turn.get("receipt") or {}).get("receipt_id") or ""),
                "user_excerpt": user_text[:600], "partner_excerpt": partner_text[:600],
                "truncated": len(user_text) > 600 or len(partner_text) > 600,
            })
            if len(moments) >= 30:
                return {"ok": True, "moments": _with_observation_notes(spine, user_id, moments)}
    return {"ok": True, "moments": _with_observation_notes(spine, user_id, moments)}


def _with_observation_notes(spine: PubPartnerSpine, user_id: str, moments: list) -> list:
    """Add what the EQ observation layer noticed about each listed moment, if anything.

    Additive: existing keys and order are unchanged; a flagged moment gains "observation"
    (plain behaviour words and the kind of disagreement). A failure leaves the list as it was."""
    layer = getattr(spine, "eq_observation", None)
    if layer is None or not moments:
        return moments
    try:
        notes = layer.moment_notes(user_id=user_id, turn_ids=[m.get("turn_id") for m in moments])
    except Exception:
        return moments
    return [{**m, "observation": notes[m["turn_id"]]} if m.get("turn_id") in notes else m for m in moments]

@router.post("/calibration/interviews/{interview_id}/audio")
async def calibration_upload_audio(interview_id: str, request: Request,
                                   identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """Authenticated optional recorded audio for future EQ review, not diagnosis."""
    user_id = _scoped_user_id(request=request, identity=identity)
    size = request.headers.get("content-length")
    if size:
        try:
            declared = int(size)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid content length")
        if declared > 4 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="audio sample too large")
    payload = await request.body()
    if len(payload) > 4 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audio sample too large")
    try:
        return _calibration_store().save_audio(
            user_id=user_id, interview_id=interview_id, data=payload,
            content_type=request.headers.get("content-type", ""),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="calibration interview not found")
    except CalibrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/calibration/interviews/{interview_id}/audio/{audio_ref}")
async def calibration_download_audio(interview_id: str, audio_ref: str, request: Request,
                                     identity: Dict[str, Any] = Depends(current_identity)):
    user_id = _scoped_user_id(request=request, identity=identity)
    try:
        path = _calibration_store().audio_path(
            user_id=user_id, interview_id=interview_id, audio_ref=audio_ref)
    except (FileNotFoundError, CalibrationError):
        raise HTTPException(status_code=404, detail="audio sample not found")
    mime = {".webm": "audio/webm", ".ogg": "audio/ogg",
            ".m4a": "audio/mp4", ".wav": "audio/wav"}[path.suffix]
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "no-store"})


# ---- EQ observation layer (shadow): owner-scoped views and the calibration loop ----------------
from .eq_observation import ObservationError, ObservationLayer
from .eq_observation.reliability import VERDICTS as _EQ_VERDICTS


def _eq_layer() -> ObservationLayer:
    layer = getattr(get_spine(), "eq_observation", None)
    if layer is None:
        raise HTTPException(status_code=404, detail="the EQ observation layer is switched off on this host")
    return layer


@router.get("/eq-observation/summary")
async def eq_observation_summary(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """The caller's own baseline maturity, trust per witness and scorecards. Numbers only."""
    user = _scoped_user_id(request=request, identity=identity)
    return {"ok": True, **_eq_layer().summary(user_id=user)}


@router.get("/eq-observation/moments")
async def eq_observation_moments(request: Request, limit: Optional[int] = None,
                                 identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """Moments worth asking about in calibration, with evidence refs the interview store accepts."""
    user = _scoped_user_id(request=request, identity=identity)
    bounded = _bounded_int(limit, default=3, minimum=1, maximum=10, field="limit")
    return {"ok": True, "moments": _eq_layer().calibration_moments(user_id=user, limit=bounded)}


@router.post("/eq-observation/verdicts")
async def eq_observation_verdict(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """Record the person's approved account of one moment. Moves trust; one account per moment."""
    body = await _json_dict(request)
    user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    turn_id = str(body.get("turn_id") or "").strip()[:120]
    if not turn_id:
        raise HTTPException(status_code=400, detail="turn_id is required")
    if body.get("answer") not in _EQ_VERDICTS:
        raise HTTPException(status_code=400, detail="answer must be one of " + ", ".join(_EQ_VERDICTS))
    if body.get("approved") is not True:
        raise HTTPException(status_code=400, detail="approved must be true: only the person's approved account is recorded")
    if body.get("calm") not in (True, False, None):
        raise HTTPException(status_code=400, detail="calm must be true, false or null")
    try:
        result = _eq_layer().apply_calibration_verdict(user_id=user, turn_id=turn_id, verdict={
            "answer": body["answer"], "approved": True, "calm": body.get("calm"),
            "interview_id": str(body.get("interview_id") or "")[:64]})
    except LookupError:
        raise HTTPException(status_code=404, detail="no recorded reading for that turn")
    except ObservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"ok": True, **result}


@router.post("/eq-observation/perception-feedback")
async def eq_observation_perception_feedback(request: Request,
                                             identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """How a reply actually came across, from the person or an observer. Scores the perception reader."""
    body = await _json_dict(request)
    user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    prediction_id = str(body.get("prediction_id") or "").strip()
    observed = body.get("observed_reads")
    if not prediction_id:
        raise HTTPException(status_code=400, detail="prediction_id is required")
    if not isinstance(observed, list) or not all(isinstance(r, str) for r in observed):
        raise HTTPException(status_code=400, detail="observed_reads must be a list of strings")
    try:
        summary = _eq_layer().record_perception_feedback(user_id=user, prediction_id=prediction_id,
                                                         observed_reads=observed)
    except LookupError:
        raise HTTPException(status_code=404, detail="no recorded prediction with that id")
    except ObservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"ok": True, "perception_scorecard": summary}


@router.post("/eq-observation/forget")
async def eq_observation_forget(request: Request, identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
    """Remove everything the observation layer holds about the caller. Their own data, at their request.
    Requires {"confirm": "forget"} so it cannot happen by accident."""
    body = await _json_dict(request)
    user = _scoped_user_id(request=request, identity=identity, explicit_value=body.get("user_id"))
    if body.get("confirm") != "forget":
        raise HTTPException(status_code=400, detail='send {"confirm": "forget"} to remove this data')
    return {"ok": True, "removed": _eq_layer().forget(user_id=user)}
