from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .alex_core import AlexCore, AIState, UserBattery

DEFAULT_PACKET_TTL_SECONDS = 60 * 60 * 8
MAX_SIGNAL_HISTORY = 64
DEFAULT_SIGNAL_COOLDOWN_SECONDS = 30
AUTHORITY_ACTIONS = {"freeze_actor", "hold_action", "mute_user", "kick_user", "ban_user"}
AUTHORITY_ACTION_ALIASES = {
    "freeze_avatar": "freeze_actor",
    "freeze": "freeze_actor",
    "ban": "ban_user",
    "mute": "mute_user",
    "kick": "kick_user",
}
PRIVATE_EVENT_FIELDS = {"raw_text", "full_transcript", "private_cue", "private_profile", "secret", "token", "api_key"}

logger = logging.getLogger("alex_jeremy_bridge")


def _canonical_authority_action(action: Any) -> str:
    raw = str(action or "").strip()
    return AUTHORITY_ACTION_ALIASES.get(raw, raw)


class AlexJeremyBridge:
    """Permissioned bridge between Alex (personal) and Jeremy (PubCast space).

    Alex stays sovereign and private. Jeremy only receives a minimal packet that
    helps him run the room more gently/intelligently. Authority-bearing actions
    are never granted by this bridge unless an injected authority reviewer
    explicitly approves them.
    """

    def __init__(
        self,
        data_dir: Path,
        *,
        authority_reviewer: Any = None,
        blackbox_logger: Any = None,
        signal_cooldown_seconds: int = DEFAULT_SIGNAL_COOLDOWN_SECONDS,
    ):
        self.data_dir = Path(data_dir)
        self.bridge_dir = self.data_dir / "alex_bridge"
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self._alex_instances: Dict[str, AlexCore] = {}
        self._io_lock = threading.RLock()
        self._authority_reviewer = authority_reviewer
        self._blackbox_logger = blackbox_logger
        self._signal_cooldown_seconds = max(0, int(signal_cooldown_seconds))
        self._last_signal_at: Dict[str, float] = {}
        self._bridge_log_failures: List[Dict[str, Any]] = []

    def _safe(self, value: str) -> str:
        return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in str(value or 'anon'))[:120] or 'anon'

    def _session_path(self, session_id: str) -> Path:
        return self.bridge_dir / f"session_{self._safe(session_id)}.json"

    def _signals_path(self, session_id: str, user_id: str) -> Path:
        return self.bridge_dir / f"signals_{self._safe(session_id)}_{self._safe(user_id)}.json"

    def alex_for(self, user_id: str) -> AlexCore:
        user_id = user_id or "default"
        alex = self._alex_instances.get(user_id)
        if alex is None:
            alex = AlexCore(user_id=user_id, data_dir=self.data_dir / "alex")
            self._alex_instances[user_id] = alex
        return alex

    def build_entry_packet(
        self,
        *,
        user_id: str,
        session_id: str,
        project_id: str,
        room_id: str,
        display_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        alex = self.alex_for(user_id)
        packet = self._packet_from_alex(alex, user_id=user_id, session_id=session_id, project_id=project_id, room_id=room_id)
        if metadata and isinstance(metadata, dict):
            packet["entry_context"] = {
                "presence_mode": metadata.get("presence_mode"),
                "availability": metadata.get("availability"),
            }
        packet.update({
            "display_name": display_name or user_id,
            "bridge_scope": "entry",
            "generated_at": time.time(),
        })
        packet["blackbox_recorded"] = self._record_bridge_event(
            "alex_entry_packet",
            user_id=user_id,
            session_id=session_id,
            room_id=room_id,
            status="ok",
            fields={
                "care_priority": packet.get("care_priority"),
                "fragility_level": packet.get("fragility_level"),
                "bridge_scope": packet.get("bridge_scope"),
            },
        )
        self._persist_packet(session_id, user_id, packet)

        # Store contextual moment in Alex's personal memory without exposing it to Jeremy.
        summary = f"Entered PubCast session {session_id} project {project_id} room {room_id}."
        alex.memory.store(summary, {"valence": 0.0, "intensity": min(1.0, packet["fragility_level"])})
        return packet

    def signal_from_jeremy(
        self,
        *,
        user_id: str,
        session_id: str,
        room_state: str,
        urgency: str,
        reason: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        alex = self.alex_for(user_id)
        now = time.time()
        signal = {
            "ts": now,
            "user_id": user_id,
            "session_id": session_id,
            "room_state": room_state,
            "urgency": urgency,
            "reason": reason,
            "payload": payload,
        }
        authority_review = self._review_authority(signal)
        cooldown_key = f"{self._safe(session_id)}:{self._safe(user_id)}"
        urgent_signal = urgency == "high" or room_state == "critical" or bool(authority_review.get("requires_authority"))
        with self._io_lock:
            elapsed = now - self._last_signal_at.get(cooldown_key, 0.0)
            suppress_for_cooldown = bool(
                self._signal_cooldown_seconds
                and elapsed < self._signal_cooldown_seconds
                and not urgent_signal
            )
            if not suppress_for_cooldown:
                self._last_signal_at[cooldown_key] = now

        if suppress_for_cooldown:
            packet = self.current_packet(user_id=user_id, session_id=session_id)
            packet["bridge_scope"] = "cooldown_suppressed"
            packet["latest_signal"] = {
                "room_state": room_state,
                "urgency": urgency,
                "reason": reason,
                "ts": now,
                "suppressed": True,
            }
            packet["authority_review"] = authority_review
            self._apply_authority_contract(packet, authority_review)
            packet["blackbox_recorded"] = self._record_bridge_event(
                "jeremy_signal_suppressed",
                user_id=user_id,
                session_id=session_id,
                room_id=payload.get("room_id") if isinstance(payload, dict) else None,
                status="cooldown",
                fields={
                    "room_state": room_state,
                    "urgency": urgency,
                    "reason": reason[:120],
                    "cooldown_remaining": round(self._signal_cooldown_seconds - elapsed, 3),
                },
            )
            self._persist_packet(session_id, user_id, packet)
            return packet

        signals = self._load_json(self._signals_path(session_id, user_id), default=[])
        signals.append(signal)
        signals = signals[-MAX_SIGNAL_HISTORY:]
        self._write_json(self._signals_path(session_id, user_id), signals)

        # Nudge Alex's live state so follow-up packets actually respond to room distress.
        stress_floor = {"low": 0.20, "medium": 0.45, "high": 0.75}.get(urgency, 0.25)
        room_bonus = {"stable": 0.0, "tense": 0.05, "destabilizing": 0.15, "critical": 0.25}.get(room_state, 0.0)
        target_stress = min(1.0, stress_floor + room_bonus)
        alex._user_state.stress_level = max(alex._user_state.stress_level, target_stress)
        if urgency in {"medium", "high"}:
            alex._user_state.clarity_score = min(alex._user_state.clarity_score, 0.85 if urgency == "medium" else 0.5)
        if urgency == "high":
            alex._user_state.energy_level = min(alex._user_state.energy_level, 0.4)
        alex._cached_stress_score = alex._user_state.calculate_stress_score()
        alex._update_ai_state()

        intensity = max(0.25, target_stress)
        alex.memory.store(
            f"Jeremy signaled from room: {room_state} / {urgency} / {reason}",
            {"valence": -0.2 if urgency != "low" else 0.0, "intensity": intensity},
        )

        base_packet = self._load_packet(session_id, user_id) or self._packet_from_alex(
            alex, user_id=user_id, session_id=session_id, project_id="", room_id=""
        )
        refreshed = self._apply_signal_overlay(dict(base_packet), signal)
        refreshed["authority_review"] = authority_review
        self._apply_authority_contract(refreshed, authority_review)
        status = "authority_approved" if authority_review.get("action_allowed") else "authority_required" if authority_review.get("requires_authority") else "ok"
        blackbox_recorded = self._record_bridge_event(
            "jeremy_signal_applied",
            user_id=user_id,
            session_id=session_id,
            room_id=payload.get("room_id") if isinstance(payload, dict) else None,
            status=status,
            fields={
                "room_state": room_state,
                "urgency": urgency,
                "reason": reason[:120],
                "care_priority": refreshed.get("care_priority"),
                "fragility_level": refreshed.get("fragility_level"),
                "authority_action": authority_review.get("requested_action"),
                "action_allowed": authority_review.get("action_allowed"),
            },
        )
        refreshed["blackbox_recorded"] = blackbox_recorded
        if authority_review.get("action_allowed") and not blackbox_recorded:
            authority_review = dict(authority_review)
            authority_review.update({
                "approved": False,
                "action_allowed": False,
                "decision": "blocked_blackbox_record_failed",
            })
            refreshed["authority_review"] = authority_review
            self._apply_authority_contract(refreshed, authority_review)
            refreshed["authority_status"] = "blocked_blackbox_record_failed"
        self._persist_packet(session_id, user_id, refreshed)
        return refreshed

    async def process_user_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        text: str,
        project_id: str = "default",
        room_id: str = "pubpartner",
        typing_speed: float = 60.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run Alex's full per-message analysis and persist a bridge-safe packet.

        The private memory context returned by ``AlexCore.process_message`` stays
        inside Alex. Only the bounded response guidance and state snapshot enter
        the provider packet. This makes every ordinary turn reach Alex without
        turning the bridge into a second personal-memory database.
        """
        alex = self.alex_for(user_id)
        analysis = await alex.process_message(
            text,
            typing_speed=typing_speed,
            metadata={
                "project_id": project_id,
                "room_id": room_id,
                **dict(metadata or {}),
            },
        )
        packet = self._packet_from_alex(
            alex,
            user_id=user_id,
            session_id=session_id,
            project_id=project_id,
            room_id=room_id,
        )
        packet.update({
            "bridge_scope": "message_analysis",
            "generated_at": time.time(),
            "analysis_source": "AlexCore.process_message",
            "response_guidelines": dict(analysis.get("response_guidelines") or {}),
            "anchor_message": analysis.get("anchor_message"),
            "processing_time_ms": int(analysis.get("processing_time_ms") or 0),
            "private_memory_context_withheld": True,
        })
        packet["blackbox_recorded"] = self._record_bridge_event(
            "alex_message_analysis",
            user_id=user_id,
            session_id=session_id,
            room_id=room_id,
            status="ok",
            fields={
                "alex_state": packet.get("alex_state"),
                "user_battery": packet.get("user_battery"),
                "care_priority": packet.get("care_priority"),
                "processing_time_ms": packet.get("processing_time_ms"),
            },
        )
        self._persist_packet(session_id, user_id, packet)
        return packet

    def current_packet(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        packet = self._load_packet(session_id, user_id)
        if packet and not self._packet_expired(packet):
            return packet
        if packet and self._packet_expired(packet):
            self.clear_packet(session_id=session_id, user_id=user_id)
        return self.build_entry_packet(user_id=user_id, session_id=session_id, project_id="default", room_id="default")

    def clear_packet(self, *, session_id: str, user_id: str) -> bool:
        path = self._session_path(session_id)
        payload = self._load_json(path, default={"session_id": session_id, "packets": {}})
        packets = payload.setdefault("packets", {})
        removed = packets.pop(user_id, None) is not None
        if removed:
            self._write_json(path, payload)
        return removed

    def clear_session(self, *, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    def downgrade_after_stabilization(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        packet = self.current_packet(user_id=user_id, session_id=session_id)
        packet["care_priority"] = "low" if packet.get("fragility_level", 0.0) < 0.35 else "medium"
        packet["tone_guidance"] = "steady" if packet.get("fragility_level", 0.0) < 0.4 else packet.get("tone_guidance", "steady")
        packet["bridge_scope"] = "stabilized"
        packet["generated_at"] = time.time()
        packet["blackbox_recorded"] = self._record_bridge_event(
            "alex_packet_stabilized",
            user_id=user_id,
            session_id=session_id,
            room_id=packet.get("room_id"),
            status="ok",
            fields={
                "care_priority": packet.get("care_priority"),
                "fragility_level": packet.get("fragility_level"),
            },
        )
        self._persist_packet(session_id, user_id, packet)
        return packet

    def jeremy_whisper(self, *, user_id: str, session_id: str) -> str:
        packet = self.current_packet(user_id=user_id, session_id=session_id)
        tone = packet.get("tone_guidance", "steady")
        fragility = float(packet.get("fragility_level", 0.0))
        flags = list(packet.get("do_not_touch", []))
        active = list(packet.get("active_threads", []))
        parts = [f"Jeremy note: keep tone {tone}."]
        if fragility >= 0.7:
            parts.append("User appears fragile; minimize friction and keep steps small.")
        elif fragility >= 0.4:
            parts.append("User may need gentler pacing and reduced noise.")
        if flags:
            parts.append("Avoid: " + ", ".join(flags[:3]) + ".")
        if active:
            parts.append("Active threads: " + ", ".join(active[:3]) + ".")
        return " ".join(parts)

    def assert_authority_action_allowed(self, packet: Dict[str, Any], action: str) -> None:
        """Raise if a downstream caller tries to execute an unapproved authority action."""
        action = _canonical_authority_action(action)
        if action not in AUTHORITY_ACTIONS:
            return
        if packet.get("allowed_authority_action") == action:
            return
        raise PermissionError(f"Authority action {action!r} requires Pub Manager/Security approval")

    def bridge_health(self) -> Dict[str, Any]:
        return {
            "blackbox_failures": len(self._bridge_log_failures),
            "last_blackbox_failure": self._bridge_log_failures[-1] if self._bridge_log_failures else None,
        }

    def shutdown(self) -> None:
        for alex in self._alex_instances.values():
            try:
                alex.shutdown()
            except Exception:
                logger.exception("Failed to shutdown Alex instance")
        self._alex_instances.clear()

    def _packet_from_alex(self, alex: AlexCore, *, user_id: str, session_id: str, project_id: str, room_id: str) -> Dict[str, Any]:
        state_name = alex._current_state.value
        battery = alex._user_battery.value
        stress = float(alex._user_state.calculate_stress_score())
        fragility = max(0.0, min(1.0, round(stress, 3)))

        tone = "steady"
        pace = "normal"
        intervention = "light"
        flags: List[str] = []

        if alex._current_state == AIState.ANCHOR:
            tone = "gentle"
            pace = "slow"
            intervention = "protective"
            flags.append("avoid_confrontation")
        elif alex._current_state == AIState.WITNESS:
            tone = "minimal"
            pace = "quiet"
            intervention = "hold_space"
            flags.append("avoid_overexplaining")
        elif alex._current_state == AIState.MIRROR:
            tone = "reflective"
            pace = "measured"
            intervention = "validate_first"
        elif alex._current_state == AIState.COMPANION:
            tone = "warm"
            intervention = "casual"

        if alex._user_battery in (UserBattery.LOW, UserBattery.DEPLETED):
            flags.append("avoid_complexity")
            pace = "slow"

        recent = alex.memory.recall(days_back=14, limit=5)
        active_threads = []
        seen = set()
        for mem in recent:
            if mem.keywords:
                key = mem.keywords[0]
            else:
                key = mem.content[:32]
            if key not in seen:
                active_threads.append(key)
                seen.add(key)

        return {
            "user_id": user_id,
            "session_id": session_id,
            "project_id": project_id,
            "room_id": room_id,
            "alex_state": state_name,
            "user_battery": battery,
            "tone_guidance": tone,
            "pace_guidance": pace,
            "intervention_style": intervention,
            "fragility_level": fragility,
            "care_priority": "high" if fragility >= 0.7 else "medium" if fragility >= 0.35 else "low",
            "do_not_touch": flags,
            "active_threads": active_threads,
        }

    def _persist_packet(self, session_id: str, user_id: str, packet: Dict[str, Any]) -> None:
        path = self._session_path(session_id)
        payload = self._load_json(path, default={"session_id": session_id, "packets": {}})
        payload.setdefault("packets", {})[user_id] = packet
        self._write_json(path, payload)

    def _load_packet(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        payload = self._load_json(self._session_path(session_id), default={})
        return (payload.get("packets") or {}).get(user_id)

    def _packet_expired(self, packet: Dict[str, Any], *, ttl_seconds: int = DEFAULT_PACKET_TTL_SECONDS) -> bool:
        generated_at = float(packet.get("generated_at") or 0)
        if generated_at <= 0:
            return False
        return (time.time() - generated_at) > ttl_seconds

    def _apply_signal_overlay(self, packet: Dict[str, Any], signal: Dict[str, Any]) -> Dict[str, Any]:
        urgency = signal.get("urgency", "low")
        room_state = signal.get("room_state", "stable")
        reason = signal.get("reason", "")

        fragility_floor = {"low": 0.25, "medium": 0.50, "high": 0.80}.get(urgency, 0.25)
        if room_state == "destabilizing":
            fragility_floor = max(fragility_floor, 0.65)
        elif room_state == "critical":
            fragility_floor = max(fragility_floor, 0.90)

        packet["fragility_level"] = max(float(packet.get("fragility_level", 0.0)), fragility_floor)

        priorities = {"low": 1, "medium": 2, "high": 3}
        current_priority = packet.get("care_priority", "low")
        target_priority = "high" if urgency == "high" or room_state == "critical" else "medium" if urgency == "medium" or room_state == "destabilizing" else "low"
        if priorities.get(target_priority, 1) > priorities.get(current_priority, 1):
            packet["care_priority"] = target_priority

        tone = packet.get("tone_guidance", "steady")
        if urgency == "high" or room_state == "critical":
            tone = "gentle"
            packet["pace_guidance"] = "slow"
            packet["intervention_style"] = "protective"
        elif urgency == "medium" or room_state == "destabilizing":
            tone = "steady" if tone == "warm" else tone
            packet["pace_guidance"] = "measured"
            packet["intervention_style"] = "validate_first"
        packet["tone_guidance"] = tone

        flags = list(packet.get("do_not_touch", []))
        if urgency in {"medium", "high"} and "avoid_complexity" not in flags:
            flags.append("avoid_complexity")
        if urgency == "high" and "avoid_confrontation" not in flags:
            flags.append("avoid_confrontation")
        if room_state in {"destabilizing", "critical"} and "reduce_noise" not in flags:
            flags.append("reduce_noise")
        packet["do_not_touch"] = flags

        packet["bridge_scope"] = "signal_response"
        packet["latest_signal"] = {k: signal[k] for k in ("room_state", "urgency", "reason", "ts")}
        packet["generated_at"] = time.time()
        packet["signal_count"] = int(packet.get("signal_count", 0)) + 1
        if reason:
            active_threads = list(packet.get("active_threads", []))
            if reason not in active_threads:
                packet["active_threads"] = ([reason] + active_threads)[:5]
        return packet

    def _review_authority(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        payload = signal.get("payload") if isinstance(signal.get("payload"), dict) else {}
        requested_action = _canonical_authority_action(payload.get("requested_action") or payload.get("action") or "")
        hard_authority_action = requested_action in AUTHORITY_ACTIONS
        requires_authority = hard_authority_action or bool(payload.get("requires_authority"))
        review = {
            "requires_authority": requires_authority,
            "requested_action": requested_action or None,
            "reviewer": "not_configured",
            "approved": False,
            "action_allowed": False,
        }
        if callable(self._authority_reviewer):
            try:
                external = self._authority_reviewer(signal)
                if isinstance(external, dict):
                    review.update({
                        "reviewer": external.get("reviewer", "external"),
                        "approved": bool(external.get("approved")),
                        "decision": external.get("decision"),
                    })
                    review["requires_authority"] = hard_authority_action or bool(external.get("requires_authority", requires_authority))
            except Exception:
                logger.exception("Authority reviewer failed")
                review.update({"reviewer": "error", "approved": False, "requires_authority": True})
        review["action_allowed"] = bool(requested_action and review["requires_authority"] and review["approved"])
        return review

    def _apply_authority_contract(self, packet: Dict[str, Any], authority_review: Dict[str, Any]) -> None:
        requested_action = authority_review.get("requested_action")
        packet.pop("allowed_authority_action", None)
        packet.pop("blocked_authority_action", None)
        if not requested_action:
            packet["authority_status"] = "none"
            return
        if authority_review.get("action_allowed"):
            packet["allowed_authority_action"] = requested_action
            packet["authority_status"] = "approved"
            return
        packet["blocked_authority_action"] = requested_action
        packet["authority_status"] = "blocked_pending_authority"

    def _record_bridge_event(
        self,
        event_type: str,
        *,
        user_id: str,
        session_id: str,
        room_id: Optional[str],
        status: str,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        event = {
            "ts": time.time(),
            "event_type": event_type,
            "status": status,
            "source": "alex_jeremy_bridge",
            "user_id": self._safe(user_id),
            "session_id": self._safe(session_id),
            "room_id": self._safe(room_id or "unknown"),
        }
        for key, value in (fields or {}).items():
            if key in PRIVATE_EVENT_FIELDS:
                continue
            event[key] = value
        try:
            if callable(self._blackbox_logger):
                self._blackbox_logger(self.data_dir, event)
            else:
                from .dressing_room_security import log_black_box_event
                log_black_box_event(self.data_dir, event)
            return True
        except Exception as exc:
            failure = {
                "ts": time.time(),
                "event_type": event_type,
                "status": "blackbox_record_failed",
                "error": str(exc),
            }
            self._bridge_log_failures.append(failure)
            logger.error("Failed to record Alex/Jeremy bridge event: %s", failure)
            return False

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, indent=2)
        with self._io_lock:
            with tempfile.NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
                tmp.write(data)
                tmp.flush()
                tmp_path = Path(tmp.name)
            tmp_path.replace(path)

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed reading bridge json: %s", path)
        return default


__all__ = ["AlexJeremyBridge"]
