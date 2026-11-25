from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .models import ParticipantType, SessionState, utc_now
from .serialization import to_jsonable


@dataclass(frozen=True)
class CoLabBrief:
    brief_id: str
    session_id: str
    created_at: str
    mode: str
    host_id: str
    goals: List[str]
    constraints: List[str]
    participants: Dict[str, Dict[str, Any]]
    recent_decisions: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    memory_scope: str = "session_and_approved_project_memory"
    privacy_scope: str = "session_participants_only"

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


class CoLabBriefBuilder:
    """Builds scoped Co-Lab briefs for Jeremy, Alex, and linked AI engines."""

    def build(self, session: SessionState) -> CoLabBrief:
        participants = {
            pid: {
                "display_name": participant.display_name,
                "type": participant.participant_type.value,
                "role_id": participant.role.role_id,
                "role_name": participant.role.display_name,
                "may_make_final_decisions": participant.role.may_make_final_decisions,
                "may_write_stable_memory": participant.role.may_write_stable_memory,
                "active": participant.active,
                "model_name": participant.model_name,
            }
            for pid, participant in session.participants.items()
        }
        recent_decisions = self._extract_marked_items(session, marker="decision")
        unresolved_questions = self._extract_marked_items(session, marker="question")
        return CoLabBrief(
            brief_id=f"brief_{session.session_id}",
            session_id=session.session_id,
            created_at=utc_now(),
            mode=session.mode,
            host_id=session.host_id,
            goals=list(session.active_goals),
            constraints=list(session.active_constraints),
            participants=participants,
            recent_decisions=recent_decisions,
            unresolved_questions=unresolved_questions,
            memory_scope=str(session.metadata.get("memory_scope", "session_and_approved_project_memory")),
            privacy_scope=str(session.metadata.get("privacy_scope", "session_participants_only")),
        )

    def scoped_for_participant(self, brief: CoLabBrief, participant_id: str) -> Dict[str, Any]:
        if participant_id not in brief.participants:
            raise ValueError(f"Unknown participant for brief scope: {participant_id}")
        participant = brief.participants[participant_id]
        allowed_participants = {
            pid: info
            for pid, info in brief.participants.items()
            if info.get("active") and info.get("type") in {ParticipantType.HUMAN.value, ParticipantType.AI.value}
        }
        scoped = brief.to_dict()
        scoped["participants"] = allowed_participants
        scoped["recipient"] = {
            "participant_id": participant_id,
            "role_id": participant.get("role_id"),
            "role_name": participant.get("role_name"),
        }
        if participant.get("role_id") not in {"host", "jeremy_continuity", "alex_prime"}:
            scoped["privacy_scope"] = "scoped_context_packet"
            scoped["memory_scope"] = "role_relevant_session_context_only"
        return scoped

    @staticmethod
    def _extract_marked_items(session: SessionState, marker: str) -> List[str]:
        items: List[str] = []
        key = f"{marker}:"
        for turn in session.recent_turns(40):
            text = turn.text.strip()
            lower = text.lower()
            if lower.startswith(key):
                items.append(text[len(key):].strip())
        return items[-8:]
