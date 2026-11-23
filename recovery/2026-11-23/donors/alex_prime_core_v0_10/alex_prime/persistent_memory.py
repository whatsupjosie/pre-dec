from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import ConsentState, MemoryCandidate, MemoryStatus, Sensitivity, SessionState, utc_now
from .serialization import to_jsonable


class PersistentMemoryError(RuntimeError):
    """Raised when persistent memory cannot be changed safely."""


class MemoryScope(str, Enum):
    PERSONAL = "personal"
    PUBCAST = "pubcast"
    PROJECT = "project"
    COLAB = "colab"
    GLOBAL = "global"


class MemoryEventType(str, Enum):
    CANDIDATE_PROPOSED = "candidate_proposed"
    CANDIDATE_REJECTED = "candidate_rejected"
    CANDIDATE_QUARANTINED = "candidate_quarantined"
    MEMORY_PROMOTED = "memory_promoted"
    MEMORY_SUPERSEDED = "memory_superseded"
    MEMORY_EXPIRED = "memory_expired"
    MEMORY_DELETED_BY_USER = "memory_deleted_by_user"


@dataclass(frozen=True)
class PersistentMemoryRecord:
    memory_id: str
    memory_type: str
    text: str
    scope: MemoryScope
    sensitivity: Sensitivity
    source_turn_ids: List[str]
    approved_by: str
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    confidence: float = 0.70
    tags: List[str] = field(default_factory=list)
    status: MemoryStatus = MemoryStatus.ACCEPTED
    supersedes: Optional[str] = None
    source_candidate_id: Optional[str] = None
    rationale: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.memory_id.strip():
            raise ValueError("memory_id is required")
        if not self.memory_type.strip():
            raise ValueError("memory_type is required")
        if not self.text.strip():
            raise ValueError("memory text is required")
        if not self.source_turn_ids:
            raise ValueError("persistent memory requires source_turn_ids")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        computed = self.compute_content_hash()
        if self.content_hash and self.content_hash != computed:
            raise ValueError("content_hash does not match memory payload")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", computed)

    def canonical_content(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type,
            "text": self.text,
            "scope": self.scope.value,
            "sensitivity": self.sensitivity.value,
            "source_turn_ids": list(self.source_turn_ids),
            "approved_by": self.approved_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "status": self.status.value,
            "supersedes": self.supersedes,
            "source_candidate_id": self.source_candidate_id,
            "rationale": self.rationale,
        }

    def compute_content_hash(self) -> str:
        encoded = json.dumps(self.canonical_content(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = self.canonical_content()
        data["content_hash"] = self.content_hash
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistentMemoryRecord":
        return cls(
            memory_id=str(data["memory_id"]),
            memory_type=str(data["memory_type"]),
            text=str(data["text"]),
            scope=MemoryScope(str(data["scope"])),
            sensitivity=Sensitivity(str(data["sensitivity"])),
            source_turn_ids=list(data["source_turn_ids"]),
            approved_by=str(data["approved_by"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            confidence=float(data["confidence"]),
            tags=list(data.get("tags", [])),
            status=MemoryStatus(str(data.get("status", MemoryStatus.ACCEPTED.value))),
            supersedes=data.get("supersedes"),
            source_candidate_id=data.get("source_candidate_id"),
            rationale=str(data.get("rationale", "")),
            content_hash=str(data.get("content_hash", "")),
        )


@dataclass(frozen=True)
class PersistentMemoryEvent:
    event_id: str
    event_type: MemoryEventType
    actor_id: str
    created_at: str
    previous_hash: str
    payload: Dict[str, Any]
    event_hash: str = ""

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
            "payload": to_jsonable(self.payload),
        }

    def compute_hash(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def sealed(self) -> "PersistentMemoryEvent":
        return PersistentMemoryEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            actor_id=self.actor_id,
            created_at=self.created_at,
            previous_hash=self.previous_hash,
            payload=self.payload,
            event_hash=self.compute_hash(),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = self.canonical_payload()
        data["event_hash"] = self.event_hash
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistentMemoryEvent":
        return cls(
            event_id=str(data["event_id"]),
            event_type=MemoryEventType(str(data["event_type"])),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
            previous_hash=str(data["previous_hash"]),
            payload=dict(data.get("payload", {})),
            event_hash=str(data.get("event_hash", "")),
        )


class PersistentMemoryStore:
    """Durable, review-first memory store for Alex Prime.

    The store is append-only at the event layer. Accepted memories are a
    materialized index rebuilt from events. This keeps normal retrieval fast
    while preserving a verifiable custody history for every promotion, rejection,
    quarantine, supersession, expiration, and user deletion.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "persistent_memory_events.jsonl"
        self.index_path = self.root / "persistent_memory_index.json"
        self.chain_head_path = self.root / "persistent_memory_chain_head.json"

    def propose_candidate(self, candidate: MemoryCandidate, actor_id: str, session: SessionState) -> Dict[str, Any]:
        self._require_actor(actor_id)
        self._append_event(
            MemoryEventType.CANDIDATE_PROPOSED,
            actor_id,
            {
                "candidate": candidate.to_dict(),
                "session_id": session.session_id,
                "context": session.context.value,
                "mode": session.mode,
            },
        )
        return candidate.to_dict()

    def quarantine_candidate(self, candidate: MemoryCandidate, actor_id: str, rationale: str) -> Dict[str, Any]:
        self._require_actor(actor_id)
        if not rationale.strip():
            raise PersistentMemoryError("quarantine rationale is required")
        self._append_event(
            MemoryEventType.CANDIDATE_QUARANTINED,
            actor_id,
            {"candidate": candidate.to_dict(), "rationale": rationale},
        )
        return {"candidate_id": candidate.candidate_id, "status": MemoryStatus.QUARANTINED.value}

    def reject_candidate(self, candidate_id: str, actor_id: str, rationale: str) -> Dict[str, Any]:
        self._require_id(candidate_id, "candidate_id")
        self._require_actor(actor_id)
        if not rationale.strip():
            raise PersistentMemoryError("rejection rationale is required")
        self._append_event(
            MemoryEventType.CANDIDATE_REJECTED,
            actor_id,
            {"candidate_id": candidate_id, "rationale": rationale},
        )
        return {"candidate_id": candidate_id, "status": MemoryStatus.REJECTED.value}

    def promote_candidate(
        self,
        candidate: MemoryCandidate,
        actor_id: str,
        consent: ConsentState,
        scope: MemoryScope,
        *,
        tags: Optional[List[str]] = None,
        supersedes: Optional[str] = None,
        rationale: str = "",
        protected_core_approval: bool = False,
    ) -> PersistentMemoryRecord:
        self._require_actor(actor_id)
        if not consent.memory_promotion:
            raise PersistentMemoryError("memory_promotion consent is required")
        if candidate.status == MemoryStatus.QUARANTINED:
            raise PersistentMemoryError("quarantined candidates cannot be promoted directly")
        if candidate.status not in {MemoryStatus.PROPOSED, MemoryStatus.ACCEPTED}:
            raise PersistentMemoryError(f"candidate status cannot be promoted: {candidate.status.value}")
        if candidate.sensitivity == Sensitivity.SPECIAL_CATEGORY_RISK:
            raise PersistentMemoryError("special-category-risk memory requires safer summary or explicit separate workflow")
        if candidate.sensitivity == Sensitivity.PROTECTED_CORE and not protected_core_approval:
            raise PersistentMemoryError("protected-core memory requires protected_core_approval")
        if supersedes is not None and self.get_memory(supersedes) is None:
            raise PersistentMemoryError("superseded memory_id does not exist")

        record = PersistentMemoryRecord(
            memory_id=f"mem_{uuid.uuid4().hex[:16]}",
            memory_type=candidate.memory_type,
            text=candidate.proposed_text,
            scope=scope,
            sensitivity=candidate.sensitivity,
            source_turn_ids=list(candidate.source_turn_ids),
            approved_by=actor_id,
            confidence=candidate.confidence,
            tags=sorted(set(tags or [])),
            supersedes=supersedes,
            source_candidate_id=candidate.candidate_id,
            rationale=rationale or candidate.rationale or "Approved memory promotion.",
        )
        self._append_event(
            MemoryEventType.MEMORY_PROMOTED,
            actor_id,
            {"memory": record.to_dict(), "source_candidate": candidate.to_dict()},
        )
        if supersedes:
            self._append_event(
                MemoryEventType.MEMORY_SUPERSEDED,
                actor_id,
                {"memory_id": supersedes, "superseded_by": record.memory_id, "rationale": rationale},
            )
        self._rebuild_index_atomic()
        return record

    def expire_memory(self, memory_id: str, actor_id: str, rationale: str) -> Dict[str, Any]:
        return self._state_change(MemoryEventType.MEMORY_EXPIRED, memory_id, actor_id, rationale)

    def delete_memory_by_user(self, memory_id: str, actor_id: str, rationale: str) -> Dict[str, Any]:
        return self._state_change(MemoryEventType.MEMORY_DELETED_BY_USER, memory_id, actor_id, rationale)

    def get_memory(self, memory_id: str) -> Optional[PersistentMemoryRecord]:
        index = self._load_index()
        raw = index.get("records", {}).get(memory_id)
        if not raw:
            return None
        return PersistentMemoryRecord.from_dict(raw)

    def list_memories(
        self,
        *,
        scope: Optional[MemoryScope] = None,
        include_sensitive: bool = False,
        include_inactive: bool = False,
    ) -> List[PersistentMemoryRecord]:
        index = self._load_index()
        records: List[PersistentMemoryRecord] = []
        for raw in index.get("records", {}).values():
            record = PersistentMemoryRecord.from_dict(raw)
            if scope and record.scope != scope:
                continue
            if not include_inactive and record.status != MemoryStatus.ACCEPTED:
                continue
            if not include_sensitive and record.sensitivity in {Sensitivity.SPECIAL_CATEGORY_RISK, Sensitivity.PROTECTED_CORE}:
                continue
            records.append(record)
        records.sort(key=lambda item: item.updated_at, reverse=True)
        return records

    def retrieve(
        self,
        query: str,
        *,
        scopes: Optional[Iterable[MemoryScope]] = None,
        memory_types: Optional[Iterable[str]] = None,
        limit: int = 5,
        include_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        if limit < 1:
            return []
        query_terms = self._terms(query)
        if not query_terms:
            return []
        allowed_scopes = set(scopes or [])
        allowed_types = {m.lower() for m in (memory_types or [])}
        scored: List[tuple[float, PersistentMemoryRecord, List[str]]] = []
        for record in self.list_memories(include_sensitive=include_sensitive):
            if allowed_scopes and record.scope not in allowed_scopes:
                continue
            if allowed_types and record.memory_type.lower() not in allowed_types:
                continue
            record_terms = self._terms(" ".join([record.text, record.memory_type, " ".join(record.tags)]))
            matched = sorted(query_terms.intersection(record_terms))
            if not matched:
                continue
            score = len(matched) / max(len(query_terms), 1)
            if query.lower().strip() in record.text.lower():
                score += 0.75
            if record.sensitivity == Sensitivity.PROTECTED_CORE:
                score -= 0.15
            scored.append((score, record, matched))
        scored.sort(key=lambda item: (item[0], item[1].confidence, item[1].updated_at), reverse=True)
        return [
            {"score": round(score, 4), "matched_terms": matched, "memory": record.to_dict()}
            for score, record, matched in scored[:limit]
        ]

    def verify(self) -> Dict[str, Any]:
        previous = "GENESIS"
        count = 0
        last_hash = previous
        for line_no, raw in self._read_event_lines():
            event = PersistentMemoryEvent.from_dict(raw)
            if event.previous_hash != previous:
                return {
                    "ok": False,
                    "reason": "broken_previous_hash",
                    "line": line_no,
                    "expected_previous": previous,
                    "actual_previous": event.previous_hash,
                }
            expected = event.compute_hash()
            if event.event_hash != expected:
                return {"ok": False, "reason": "event_hash_mismatch", "line": line_no}
            previous = expected
            last_hash = expected
            count += 1
        return {"ok": True, "event_count": count, "chain_head": last_hash}

    def rebuild_index(self) -> Dict[str, Any]:
        return self._rebuild_index_atomic()

    def _state_change(self, event_type: MemoryEventType, memory_id: str, actor_id: str, rationale: str) -> Dict[str, Any]:
        self._require_id(memory_id, "memory_id")
        self._require_actor(actor_id)
        if not rationale.strip():
            raise PersistentMemoryError("state-change rationale is required")
        if self.get_memory(memory_id) is None:
            raise PersistentMemoryError("memory_id does not exist")
        self._append_event(event_type, actor_id, {"memory_id": memory_id, "rationale": rationale})
        self._rebuild_index_atomic()
        return {"memory_id": memory_id, "status": self._status_for_event(event_type).value}

    @staticmethod
    def _status_for_event(event_type: MemoryEventType) -> MemoryStatus:
        if event_type == MemoryEventType.MEMORY_EXPIRED:
            return MemoryStatus.EXPIRED
        if event_type == MemoryEventType.MEMORY_DELETED_BY_USER:
            return MemoryStatus.REJECTED
        if event_type == MemoryEventType.MEMORY_SUPERSEDED:
            return MemoryStatus.EXPIRED
        raise PersistentMemoryError(f"No status mapping for {event_type.value}")

    def _append_event(self, event_type: MemoryEventType, actor_id: str, payload: Dict[str, Any]) -> PersistentMemoryEvent:
        event = PersistentMemoryEvent(
            event_id=f"memevt_{uuid.uuid4().hex[:16]}",
            event_type=event_type,
            actor_id=actor_id,
            created_at=utc_now(),
            previous_hash=self._current_head(),
            payload=payload,
        ).sealed()
        line = json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
        self._write_chain_head(event)
        return event

    def _rebuild_index_atomic(self) -> Dict[str, Any]:
        records: Dict[str, Dict[str, Any]] = {}
        for _, raw in self._read_event_lines():
            event = PersistentMemoryEvent.from_dict(raw)
            if event.event_type == MemoryEventType.MEMORY_PROMOTED:
                record = PersistentMemoryRecord.from_dict(event.payload["memory"])
                records[record.memory_id] = record.to_dict()
            elif event.event_type in {MemoryEventType.MEMORY_EXPIRED, MemoryEventType.MEMORY_DELETED_BY_USER}:
                memory_id = str(event.payload["memory_id"])
                if memory_id in records:
                    prior = PersistentMemoryRecord.from_dict(records[memory_id])
                    replacement = PersistentMemoryRecord(
                        memory_id=prior.memory_id,
                        memory_type=prior.memory_type,
                        text=prior.text,
                        scope=prior.scope,
                        sensitivity=prior.sensitivity,
                        source_turn_ids=prior.source_turn_ids,
                        approved_by=prior.approved_by,
                        created_at=prior.created_at,
                        updated_at=event.created_at,
                        confidence=prior.confidence,
                        tags=prior.tags,
                        status=self._status_for_event(event.event_type),
                        supersedes=prior.supersedes,
                        source_candidate_id=prior.source_candidate_id,
                        rationale=str(event.payload.get("rationale", prior.rationale)),
                    )
                    records[memory_id] = replacement.to_dict()
            elif event.event_type == MemoryEventType.MEMORY_SUPERSEDED:
                memory_id = str(event.payload["memory_id"])
                if memory_id in records:
                    prior = PersistentMemoryRecord.from_dict(records[memory_id])
                    replacement = PersistentMemoryRecord(
                        memory_id=prior.memory_id,
                        memory_type=prior.memory_type,
                        text=prior.text,
                        scope=prior.scope,
                        sensitivity=prior.sensitivity,
                        source_turn_ids=prior.source_turn_ids,
                        approved_by=prior.approved_by,
                        created_at=prior.created_at,
                        updated_at=event.created_at,
                        confidence=prior.confidence,
                        tags=prior.tags,
                        status=MemoryStatus.EXPIRED,
                        supersedes=prior.supersedes,
                        source_candidate_id=prior.source_candidate_id,
                        rationale=str(event.payload.get("rationale", prior.rationale)),
                    )
                    records[memory_id] = replacement.to_dict()
        index = {
            "format": "ALEX_PERSISTENT_MEMORY_INDEX_V1",
            "rebuilt_at": utc_now(),
            "chain": self.verify(),
            "records": records,
        }
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.index_path)
        return index

    def _load_index(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return self._rebuild_index_atomic()
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PersistentMemoryError(f"Unreadable persistent memory index: {exc}") from exc

    def _read_event_lines(self) -> List[tuple[int, Dict[str, Any]]]:
        if not self.events_path.exists():
            return []
        rows: List[tuple[int, Dict[str, Any]]] = []
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append((line_no, json.loads(line)))
                except json.JSONDecodeError as exc:
                    raise PersistentMemoryError(f"Invalid persistent memory event at line {line_no}: {exc}") from exc
        return rows

    def _current_head(self) -> str:
        if not self.chain_head_path.exists():
            return "GENESIS"
        try:
            data = json.loads(self.chain_head_path.read_text(encoding="utf-8"))
            return str(data.get("event_hash") or "GENESIS")
        except json.JSONDecodeError as exc:
            raise PersistentMemoryError(f"Unreadable persistent memory chain head: {exc}") from exc

    def _write_chain_head(self, event: PersistentMemoryEvent) -> None:
        tmp = self.chain_head_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"event_id": event.event_id, "event_hash": event.event_hash, "updated_at": event.created_at},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.chain_head_path)

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {term for term in re.findall(r"[a-z0-9][a-z0-9']+", text.lower()) if len(term) > 1}

    @staticmethod
    def _require_actor(actor_id: str) -> None:
        PersistentMemoryStore._require_id(actor_id, "actor_id")

    @staticmethod
    def _require_id(value: str, label: str) -> None:
        if not value or not value.strip():
            raise PersistentMemoryError(f"{label} is required")
