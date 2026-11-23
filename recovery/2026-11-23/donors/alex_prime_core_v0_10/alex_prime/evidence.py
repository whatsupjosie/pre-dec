from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .models import AuditBundle, SessionState, utc_now
from .serialization import to_jsonable


class EvidenceRecorderError(RuntimeError):
    """Raised when evidence recording cannot complete safely."""


@runtime_checkable
class EvidenceRecorder(Protocol):
    """Protocol for append-only evidence recorders used by Alex Prime."""

    def record_audit_bundle(self, audit: AuditBundle, session: SessionState) -> Dict[str, Any]:
        """Persist an audit bundle and return the durable event metadata."""

    def verify(self) -> Dict[str, Any]:
        """Verify the recorder's integrity state."""


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    created_at: str
    event_type: str
    summary: str
    session_id: str
    actor: str
    previous_hash: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_hash: str = ""

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "created_at": self.created_at,
            "event_type": self.event_type,
            "summary": self.summary,
            "session_id": self.session_id,
            "actor": self.actor,
            "previous_hash": self.previous_hash,
            "payload": to_jsonable(self.payload),
        }

    def compute_hash(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def sealed(self) -> "EvidenceEvent":
        return EvidenceEvent(
            event_id=self.event_id,
            created_at=self.created_at,
            event_type=self.event_type,
            summary=self.summary,
            session_id=self.session_id,
            actor=self.actor,
            previous_hash=self.previous_hash,
            payload=self.payload,
            event_hash=self.compute_hash(),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = self.canonical_payload()
        data["event_hash"] = self.event_hash
        return data


class TamperEvidentJsonlRecorder:
    """Append-only local evidence recorder with a hash chain.

    This recorder is intentionally small and deterministic. It is useful when
    the Iteration Wallet BlackBox is unavailable, and it also gives tests a
    durable evidence target without network or database dependencies.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "alex_evidence.jsonl"
        self.chain_head_path = self.root / "alex_chain_head.json"

    def record_audit_bundle(self, audit: AuditBundle, session: SessionState) -> Dict[str, Any]:
        event = self._build_event(audit, session).sealed()
        self._append_line(event.to_dict())
        self._write_chain_head(event)
        return event.to_dict()

    def verify(self) -> Dict[str, Any]:
        previous = "GENESIS"
        count = 0
        last_hash = previous
        if not self.events_path.exists():
            return {"ok": True, "event_count": 0, "chain_head": "GENESIS"}
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    return {"ok": False, "reason": "invalid_json", "line": line_no, "error": str(exc)}
                supplied_hash = raw.get("event_hash")
                event = EvidenceEvent(
                    event_id=str(raw.get("event_id", "")),
                    created_at=str(raw.get("created_at", "")),
                    event_type=str(raw.get("event_type", "")),
                    summary=str(raw.get("summary", "")),
                    session_id=str(raw.get("session_id", "")),
                    actor=str(raw.get("actor", "")),
                    previous_hash=str(raw.get("previous_hash", "")),
                    payload=dict(raw.get("payload", {})),
                    event_hash=str(supplied_hash or ""),
                )
                if event.previous_hash != previous:
                    return {
                        "ok": False,
                        "reason": "broken_previous_hash",
                        "line": line_no,
                        "expected_previous": previous,
                        "actual_previous": event.previous_hash,
                    }
                expected_hash = event.compute_hash()
                if supplied_hash != expected_hash:
                    return {"ok": False, "reason": "event_hash_mismatch", "line": line_no}
                previous = expected_hash
                last_hash = expected_hash
                count += 1
        return {"ok": True, "event_count": count, "chain_head": last_hash}

    def _build_event(self, audit: AuditBundle, session: SessionState) -> EvidenceEvent:
        actor = session.host_id if session.host_id in session.participants else "system"
        return EvidenceEvent(
            event_id=f"alexevt_{uuid.uuid4().hex[:16]}",
            created_at=utc_now(),
            event_type="ALEX_AUDIT_BUNDLE",
            summary=f"{audit.issue_class}: {audit.action}",
            session_id=session.session_id,
            actor=actor,
            previous_hash=self._current_head(),
            payload={
                "audit_bundle": audit.to_dict(),
                "session_context": {
                    "context": session.context.value,
                    "mode": session.mode,
                    "host_id": session.host_id,
                    "participants": {
                        pid: {
                            "display_name": participant.display_name,
                            "type": participant.participant_type.value,
                            "role_id": participant.role.role_id,
                            "active": participant.active,
                        }
                        for pid, participant in session.participants.items()
                    },
                    "active_goals": list(session.active_goals),
                    "active_constraints": list(session.active_constraints),
                    "restore_checkpoints": list(session.restore_checkpoints),
                },
            },
        )

    def _current_head(self) -> str:
        if not self.chain_head_path.exists():
            return "GENESIS"
        try:
            data = json.loads(self.chain_head_path.read_text(encoding="utf-8"))
            return str(data.get("event_hash") or "GENESIS")
        except json.JSONDecodeError as exc:
            raise EvidenceRecorderError(f"Unreadable chain head: {exc}") from exc

    def _append_line(self, data: Dict[str, Any]) -> None:
        line = json.dumps(data, sort_keys=True, ensure_ascii=False)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

    def _write_chain_head(self, event: EvidenceEvent) -> None:
        tmp = self.chain_head_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "event_id": event.event_id,
                    "event_hash": event.event_hash,
                    "updated_at": event.created_at,
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.chain_head_path)


class BlackBoxEvidenceRecorder:
    """Adapter for Iteration Wallet BlackBox-style evidence objects.

    The supplied BlackBox implementation exposes write_event() and
    verify_chain(). This adapter keeps Alex independent of the BlackBox module
    location while still writing durable evidence through the vault recorder.
    """

    def __init__(self, blackbox: Any):
        if not hasattr(blackbox, "write_event") or not callable(blackbox.write_event):
            raise TypeError("blackbox must expose callable write_event")
        if not hasattr(blackbox, "verify_chain") or not callable(blackbox.verify_chain):
            raise TypeError("blackbox must expose callable verify_chain")
        self.blackbox = blackbox

    def record_audit_bundle(self, audit: AuditBundle, session: SessionState) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "audit_bundle_id": audit.audit_bundle_id,
            "issue_class": audit.issue_class,
            "severity": audit.severity.value,
            "intervention_level": audit.intervention_level.value,
            "recommended_commands": list(audit.recommended_commands),
            "evidence_turn_ids": list(audit.evidence_turn_ids),
            "rules_fired": list(audit.rules_fired),
            "audit_bundle": audit.to_dict(),
        }
        event = self.blackbox.write_event(
            "ALEX_AUDIT_BUNDLE",
            f"Alex intervention {audit.action} for {audit.issue_class}",
            actor="alex_prime",
            session_id=session.session_id,
            **kwargs,
        )
        if not isinstance(event, dict) or "event_hash" not in event:
            raise EvidenceRecorderError("BlackBox write_event did not return event_hash")
        return event

    def verify(self) -> Dict[str, Any]:
        result = self.blackbox.verify_chain()
        if not isinstance(result, dict):
            raise EvidenceRecorderError("BlackBox verify_chain did not return a dictionary")
        return result


class AuditEvidenceBridge:
    """Routes Alex audit bundles to a durable evidence recorder."""

    def __init__(self, recorder: EvidenceRecorder):
        self.recorder = recorder

    def record(self, audit: Optional[AuditBundle], session: SessionState) -> Optional[Dict[str, Any]]:
        if audit is None:
            return None
        return self.recorder.record_audit_bundle(audit, session)
