from __future__ import annotations

from typing import List
import re

from .models import MemoryCandidate, MemoryStatus, Sensitivity, SessionTurn, new_id


class MemoryGate:
    """Creates reviewable memory candidates instead of writing stable memory."""

    harm_terms = {"hate", "useless", "stupid", "liar", "destroy", "attack", "sabotage", "worthless"}
    protected_identity_terms = {"always", "never", "identity", "personality", "prime", "core"}
    stable_lesson_markers = {"wants", "prefers", "rule", "priority", "must", "should", "needs", "build", "workflow"}

    def propose_from_turns(
        self,
        turns: List[SessionTurn],
        memory_type: str,
        proposed_text: str,
        confidence: float = 0.70,
        sensitivity: Sensitivity = Sensitivity.PERSONAL,
    ) -> MemoryCandidate:
        if not turns:
            raise ValueError("Cannot create memory candidate without source turns")
        if not memory_type.strip():
            raise ValueError("memory_type is required")

        status = MemoryStatus.PROPOSED
        decay_policy = "review_in_30d"
        rationale = "Candidate created for user approval."
        proposed_lower = proposed_text.lower()
        source_text = " ".join(t.text.lower() for t in turns)
        combined_words = set(re.findall(r"[a-z']+", f"{proposed_lower} {source_text}"))

        redactions: list[str] = []
        if self.harm_terms.intersection(combined_words):
            status = MemoryStatus.QUARANTINED
            sensitivity = Sensitivity.SPECIAL_CATEGORY_RISK
            decay_policy = "session_only_until_reviewed"
            rationale = "Contains intense or harmful language; quarantine raw event and extract a safer lesson."
            redactions.append("intense_language")

        if self.protected_identity_terms.intersection(set(re.findall(r"[a-z']+", proposed_lower))) and memory_type in {"identity", "personality", "care_rule"}:
            sensitivity = Sensitivity.PROTECTED_CORE
            decay_policy = "requires_prime_review"
            rationale = "Affects protected identity/care rules; Prime review required before promotion."

        return MemoryCandidate(
            candidate_id=new_id("memcand"),
            source_turn_ids=[t.turn_id for t in turns],
            memory_type=memory_type,
            proposed_text=proposed_text,
            confidence=max(0.0, min(1.0, confidence)),
            sensitivity=sensitivity,
            approval_required=True,
            decay_policy=decay_policy,
            legal_basis_or_consent="pending_user_approval",
            status=status,
            redactions=redactions,
            rationale=rationale,
        )

    def safer_summary_candidate(self, turns: List[SessionTurn], raw_event_summary: str) -> MemoryCandidate:
        """Distill intense events into a safer pattern memory."""
        cleaned = re.sub(
            r"\b(hate|useless|stupid|worthless|liar|destroy|attack|sabotage)\b",
            "[redacted_intense_language]",
            raw_event_summary,
            flags=re.I,
        )
        proposed = (
            "During high-intensity exchanges, preserve boundaries, avoid absorbing insults as identity, "
            f"and review the underlying practical lesson: {cleaned}"
        )
        return self.propose_from_turns(
            turns=turns,
            memory_type="care_rule",
            proposed_text=proposed,
            confidence=0.62,
            sensitivity=Sensitivity.SPECIAL_CATEGORY_RISK,
        )
