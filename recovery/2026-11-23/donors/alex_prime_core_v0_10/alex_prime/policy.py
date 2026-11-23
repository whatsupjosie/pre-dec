from __future__ import annotations

from typing import List, Optional

from .models import AuditBundle, DetectorFinding, InterventionLevel, SessionState, Severity, new_id


_LEVEL_ORDER = {
    InterventionLevel.OBSERVE: 0,
    InterventionLevel.NUDGE: 1,
    InterventionLevel.CLARIFY: 2,
    InterventionLevel.GATE: 3,
    InterventionLevel.CONTAIN: 4,
    InterventionLevel.QUARANTINE_RESTORE: 5,
}

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}

_COMMANDS_BY_ACTION = {
    "role_or_flow_nudge": ["alex.reanchor_role"],
    "clarify_and_repair": ["alex.open_repair_session"],
    "gate_state_change": [],
    "contain_interaction": ["alex.open_repair_session"],
    "quarantine_and_restore": ["alex.restore_runtime_profile"],
}


def strongest_level(findings: List[DetectorFinding]) -> InterventionLevel:
    if not findings:
        return InterventionLevel.OBSERVE
    return max((f.intervention_level for f in findings), key=lambda level: _LEVEL_ORDER[level])


def strongest_finding(findings: List[DetectorFinding]) -> DetectorFinding:
    return max(findings, key=lambda f: (_LEVEL_ORDER[f.intervention_level], _SEVERITY_ORDER[f.severity], f.confidence))


class AlexPolicyEngine:
    """Maps detector findings to interventions and audit bundles."""

    def decide(self, session: SessionState, findings: List[DetectorFinding]) -> Optional[AuditBundle]:
        actionable = [f for f in findings if f.intervention_level != InterventionLevel.OBSERVE]
        if not actionable:
            return None

        level = self._escalated_level(actionable)
        top = strongest_finding(actionable)
        action, reason = self._action_for(level, top)
        checkpoint_before = session.restore_checkpoints[-1] if session.restore_checkpoints else None
        evidence_turn_ids = sorted({tid for finding in actionable for tid in finding.evidence_turn_ids})
        rules_fired = sorted({rule for finding in actionable for rule in finding.rules_fired})
        recommended_commands = self._commands_for(action, actionable)
        top_severity = max((f.severity for f in actionable), key=lambda sev: _SEVERITY_ORDER[sev])

        return AuditBundle(
            audit_bundle_id=new_id("audit"),
            session_id=session.session_id,
            issue_class=top.issue_class,
            severity=top_severity,
            intervention_level=level,
            findings=actionable,
            action=action,
            user_visible_reason=reason,
            host_override_available=True,
            checkpoint_before=checkpoint_before,
            checkpoint_after=None,
            consent_snapshot=session.consent.to_dict(),
            retention_class="security_incident_30d" if top_severity in {Severity.CRITICAL, Severity.HIGH} else "operational_30d",
            evidence_turn_ids=evidence_turn_ids,
            rules_fired=rules_fired,
            recommended_commands=recommended_commands,
            metadata={
                "findings_count": len(actionable),
                "highest_confidence": max(f.confidence for f in actionable),
                "session_mode": session.mode,
                "context": session.context.value,
                "participants": {pid: participant.role.role_id for pid, participant in session.participants.items()},
            },
        )

    def _escalated_level(self, findings: List[DetectorFinding]) -> InterventionLevel:
        level = strongest_level(findings)
        high_or_critical = sum(1 for f in findings if f.severity in {Severity.HIGH, Severity.CRITICAL})
        issue_classes = {f.issue_class for f in findings}
        if level == InterventionLevel.GATE:
            consent_only = all(issue.startswith("missing_consent_") for issue in issue_classes)
            if not consent_only and "explicit_threat_or_sabotage" in issue_classes:
                return InterventionLevel.CONTAIN
        if high_or_critical >= 3 and _LEVEL_ORDER[level] < _LEVEL_ORDER[InterventionLevel.GATE]:
            return InterventionLevel.CLARIFY
        return level

    def _commands_for(self, action: str, findings: List[DetectorFinding]) -> List[str]:
        commands = set(_COMMANDS_BY_ACTION.get(action, []))
        for finding in findings:
            if finding.issue_class.startswith("missing_consent_"):
                commands.add("alex.require_consent")
            if "memory" in finding.issue_class or "identity" in finding.issue_class:
                commands.add("alex.gate_memory_write")
            if finding.issue_class in {"role_exceeded_decision_authority"}:
                commands.add("alex.reanchor_role")
            if "context" in finding.issue_class or finding.issue_class == "missing_active_goal_in_long_session":
                commands.add("jeremy.refresh_colab_brief")
            if finding.issue_class in {"explicit_threat_or_sabotage", "rising_conflict_or_repetition_loop"}:
                commands.add("alex.open_repair_session")
        return sorted(commands)

    def _action_for(self, level: InterventionLevel, top: DetectorFinding) -> tuple[str, str]:
        if level == InterventionLevel.NUDGE:
            return "role_or_flow_nudge", top.recommendation or "Alex recommends a light course correction."
        if level == InterventionLevel.CLARIFY:
            return "clarify_and_repair", top.recommendation or "Alex recommends clarifying intent before continuing."
        if level == InterventionLevel.GATE:
            return "gate_state_change", top.recommendation or "This action requires approval before changing protected state."
        if level == InterventionLevel.CONTAIN:
            return "contain_interaction", top.recommendation or "Direct interaction should pause pending host review."
        if level == InterventionLevel.QUARANTINE_RESTORE:
            return "quarantine_and_restore", top.recommendation or "Runtime should be isolated and compared to protected Prime."
        return "observe", "Alex observed a signal but recommends no interruption."
