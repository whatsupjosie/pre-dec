from __future__ import annotations

from typing import List
import re

from .config import DetectorConfig
from .models import DetectorFinding, InterventionLevel, SessionState, Severity, new_id


class ContextHealthAnalyzer:
    """Deterministic context-health checks for long Co-Labs.

    This is intentionally tokenizer-light so it runs in local/unit-test mode. It
    uses documented approximations and session structure, not magic. A provider
    tokenizer can replace the estimator later without changing the policy API.
    """

    lost_context_patterns = [
        re.compile(r"\b(as i said earlier|we already decided|you forgot|lost context|wrong version)\b", re.I),
        re.compile(r"\bnot the current version\b", re.I),
        re.compile(r"\bthat was already answered\b", re.I),
    ]

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()

    def analyze(self, session: SessionState) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        token_estimate = session.approx_recent_tokens(limit=80)
        recent = session.recent_turns(80)

        if token_estimate >= self.config.context_token_critical_threshold:
            findings.append(self._finding(
                session=session,
                severity=Severity.HIGH,
                confidence=0.82,
                level=InterventionLevel.CLARIFY,
                issue_class="context_overload_high_risk",
                turn_ids=[t.turn_id for t in recent[-3:]],
                snippets=[f"Approx recent context estimate: {token_estimate} tokens."],
                rules=["recent context exceeds high-risk threshold"],
                recommendation="Pause expansion, ask Jeremy to refresh the Co-Lab brief, and pin active goals before continuing.",
            ))
        elif token_estimate >= self.config.context_token_warning_threshold:
            findings.append(self._finding(
                session=session,
                severity=Severity.MEDIUM,
                confidence=0.70,
                level=InterventionLevel.NUDGE,
                issue_class="context_overload_warning",
                turn_ids=[t.turn_id for t in recent[-3:]],
                snippets=[f"Approx recent context estimate: {token_estimate} tokens."],
                rules=["recent context exceeds warning threshold"],
                recommendation="Ask Jeremy to refresh the Co-Lab brief soon and keep active constraints near the front of the session.",
            ))

        if len(session.turns) >= self.config.long_session_goal_refresh_turns and not session.active_goals:
            findings.append(self._finding(
                session=session,
                severity=Severity.MEDIUM,
                confidence=0.76,
                level=InterventionLevel.NUDGE,
                issue_class="missing_active_goal_in_long_session",
                turn_ids=[t.turn_id for t in recent[-3:]],
                snippets=["Long session has no active_goals pinned in SessionState."],
                rules=["long Co-Labs require active goal pins"],
                recommendation="Ask Jeremy to pin the active goal, current decision, and next required output.",
            ))

        lost_context_turns = [
            turn for turn in session.recent_turns(12)
            if any(pattern.search(turn.text) for pattern in self.lost_context_patterns)
        ]
        if lost_context_turns:
            findings.append(self._finding(
                session=session,
                severity=Severity.HIGH,
                confidence=0.81,
                level=InterventionLevel.CLARIFY,
                issue_class="explicit_context_loss_report",
                turn_ids=[t.turn_id for t in lost_context_turns],
                snippets=[t.text[:220] for t in lost_context_turns[:3]],
                rules=["participant reported context/version loss"],
                recommendation="Stop new branches, locate the current version, and refresh the Co-Lab brief before answering.",
            ))

        return findings

    def _finding(
        self,
        session: SessionState,
        severity: Severity,
        confidence: float,
        level: InterventionLevel,
        issue_class: str,
        turn_ids: List[str],
        snippets: List[str],
        rules: List[str],
        recommendation: str,
    ) -> DetectorFinding:
        return DetectorFinding(
            finding_id=new_id("finding"),
            detector="context_health",
            issue_class=issue_class,
            severity=severity,
            confidence=confidence,
            intervention_level=level,
            evidence_turn_ids=turn_ids,
            evidence_snippets=snippets,
            rules_fired=rules,
            recommendation=recommendation,
            metadata={"session_mode": session.mode, "context": session.context.value},
        )
