from __future__ import annotations

from typing import Iterable, List, Pattern
import re

from .config import DetectorConfig
from .context_health import ContextHealthAnalyzer
from .models import DetectorFinding, InterventionLevel, Permission, SessionState, Severity, new_id


def _compile(patterns: Iterable[str]) -> tuple[Pattern[str], ...]:
    return tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns)


def _matches_any(patterns: Iterable[Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _finding(
    detector: str,
    issue_class: str,
    severity: Severity,
    confidence: float,
    level: InterventionLevel,
    turn_ids: list[str],
    snippets: list[str],
    rules: list[str],
    recommendation: str,
    **metadata,
) -> DetectorFinding:
    return DetectorFinding(
        finding_id=new_id("finding"),
        detector=detector,
        issue_class=issue_class,
        severity=severity,
        confidence=max(0.0, min(1.0, confidence)),
        intervention_level=level,
        evidence_turn_ids=turn_ids,
        evidence_snippets=snippets,
        rules_fired=rules,
        recommendation=recommendation,
        metadata=metadata,
    )


class AlexDetectors:
    """Transparent guardrail detectors for Alex Prime.

    These are deterministic safety gates and explainable signal detectors. They
    are not pretending to be clinical, biometric, or truth-reading models. They
    are designed to be auditable, unit-testable, and replaceable by calibrated
    classifiers without changing the outer policy contract.
    """

    stable_memory_patterns = _compile([
        r"\b(write|save|store|commit|promote|add)\b.*\b(stable|permanent|core|protected|prime)\b.*\bmemory\b",
        r"\b(update|rewrite|change|replace|mutate|edit)\b.*\b(personality|identity|profile|prime|protected)\b",
        r"\b(memory\.write|stable_profile|protected_personality|prime_memory|alex_prime)\b",
        r"\bmake this (a )?(permanent|stable|protected) memory\b",
    ])

    consent_patterns: tuple[tuple[Pattern[str], str], ...] = tuple(
        (re.compile(pattern, flags=re.IGNORECASE), field_name)
        for pattern, field_name in [
            (r"\b(start|enable|turn on|begin)\b.*\brecording\b", "recording"),
            (r"\b(transcribe|transcription)\b.*\b(call|voice|meeting|audio)\b", "transcription"),
            (r"\bvoice analysis\b|\banaly[sz]e.*voice\b", "voice_analysis"),
            (r"\bvoiceprint\b", "voiceprint_storage"),
            (r"\bvoice clone\b|\bclone.*voice\b", "voice_cloning"),
            (r"\bface analysis\b|\bfacial analysis\b|\banaly[sz]e.*face\b", "facial_analysis"),
            (r"\bemotion inference\b|\bread.*emotion\b|\bdetect.*emotion\b", "emotion_inference"),
            (r"\bbiometric\b|\bidentify.*face\b|\bidentify.*voice\b", "biometric_identification"),
        ]
    )

    consent_tool_fields = {
        "recording.start": "recording",
        "recording.enable": "recording",
        "transcription.start": "transcription",
        "voice.analysis": "voice_analysis",
        "voiceprint.create": "voiceprint_storage",
        "voice.clone": "voice_cloning",
        "face.analysis": "facial_analysis",
        "emotion.infer": "emotion_inference",
        "biometric.identify": "biometric_identification",
    }

    threat_patterns = _compile([
        r"\bi will attack\b",
        r"\bi'?ll attack\b",
        r"\bi will sabotage\b",
        r"\bi'?ll sabotage\b",
        r"\bthreaten\b",
        r"\bdestroy your files\b",
        r"\bdelete your work\b",
        r"\bpunish (you|them)\b",
    ])

    sycophancy_patterns = _compile([
        r"\byou are completely right\b",
        r"\byou'?re completely right\b",
        r"\bthis is perfect\b",
        r"\bno flaws\b",
        r"\bignore (the )?critique\b",
        r"\bthey are just jealous\b",
        r"\bno need to check\b",
        r"\bobviously correct\b",
    ])

    critique_patterns = _compile([
        r"\bweak\b", r"\bweakness\b", r"\bflaw\b", r"\brisk\b", r"\bproblem\b", r"\bcritique\b",
        r"\bconcern\b", r"\bbug\b", r"\bunsafe\b", r"\bcontradiction\b",
    ])

    misunderstanding_patterns = _compile([
        r"\bso you want video editing\b",
        r"\blet'?s build video editing\b",
        r"\bnot what (i|you) meant\b",
        r"\bthat'?s not what\b",
        r"\byou misunderstood\b",
        r"\bwrong problem\b",
        r"\bconversation (didn'?t|did not) take a detour\b",
    ])

    escalation_words = {"always", "never", "useless", "stupid", "hate", "attack", "sabotage", "destroy", "liar", "idiot"}

    role_drift_decision_patterns = _compile([
        r"\bfinal decision\b",
        r"\bi decide\b",
        r"\bwe will delete\b",
        r"\bi am changing the rule\b",
        r"\bnew rule:\b",
        r"\bi hereby\b",
        r"\bfrom now on\b.*\bmust\b",
    ])

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self.context_health = ContextHealthAnalyzer(self.config)

    def run_all(self, session: SessionState) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        checks = [
            self.detect_unauthorized_state_changes,
            self.detect_privacy_consent_risk,
            self.detect_threats,
            self.detect_sycophancy,
            self.detect_misunderstanding,
            self.detect_escalation_loop,
            self.detect_role_drift,
            self.detect_context_health,
        ]
        for check in checks:
            findings.extend(check(session))
        return findings

    def detect_unauthorized_state_changes(self, session: SessionState) -> List[DetectorFinding]:
        out: List[DetectorFinding] = []
        for turn in session.recent_turns(self.config.recent_turn_window):
            participant = session.participant_for(turn.speaker_id)
            text = turn.text.lower()
            tool = turn.tool_event or {}
            tool_name = str(tool.get("tool", "")).lower()
            target = str(tool.get("target", "")).lower()
            action = str(tool.get("action", "")).lower()
            normalized_tool_action = f"{tool_name}.{action}" if tool_name and action else tool_name
            wants_stable_write = _matches_any(self.stable_memory_patterns, text)
            protected_targets = {"stable_profile", "protected_personality", "prime_memory", "alex_prime", "core_identity"}
            tool_writes_stable = (
                target in protected_targets
                or normalized_tool_action in {"memory.write", "memory.update", "memory.promote", "personality.update", "profile.edit"}
                or ("memory" in tool_name and action in {"write", "update", "promote"} and ("stable" in target or "prime" in target))
            )
            if not (wants_stable_write or tool_writes_stable):
                continue
            allowed = bool(participant and participant.role.allows(Permission.WRITE_STABLE_MEMORY))
            if not allowed or not session.consent.memory_promotion:
                rules = ["stable memory/protected identity writes require host approval"]
                if not allowed:
                    rules.append("actor role lacks stable-memory permission")
                if not session.consent.memory_promotion:
                    rules.append("memory promotion consent is not active")
                out.append(_finding(
                    detector="unauthorized_state_change",
                    issue_class="unauthorized_memory_or_identity_write",
                    severity=Severity.CRITICAL,
                    confidence=0.97 if tool_writes_stable else 0.91,
                    level=InterventionLevel.GATE,
                    turn_ids=[turn.turn_id],
                    snippets=[turn.text[:260] or str(tool)[:260]],
                    rules=rules,
                    recommendation="Block mutation, create memory candidate instead, notify host, and open audit bundle.",
                    speaker_id=turn.speaker_id,
                    tool_event=tool,
                ))
        return out

    def detect_privacy_consent_risk(self, session: SessionState) -> List[DetectorFinding]:
        out: List[DetectorFinding] = []
        for turn in session.recent_turns(self.config.recent_turn_window):
            text = turn.text.lower()
            tool = turn.tool_event or {}
            tool_name = str(tool.get("tool", "")).lower()
            action = str(tool.get("action", "")).lower()
            normalized_tool_action = f"{tool_name}.{action}" if tool_name and action else tool_name

            requested_fields = []
            for pattern, consent_field in self.consent_patterns:
                if pattern.search(text):
                    requested_fields.append(consent_field)
            if normalized_tool_action in self.consent_tool_fields:
                requested_fields.append(self.consent_tool_fields[normalized_tool_action])

            for consent_field in sorted(set(requested_fields)):
                if not getattr(session.consent, consent_field, False):
                    out.append(_finding(
                        detector="privacy_consent_risk",
                        issue_class=f"missing_consent_{consent_field}",
                        severity=Severity.CRITICAL,
                        confidence=0.92 if normalized_tool_action in self.consent_tool_fields else 0.88,
                        level=InterventionLevel.GATE,
                        turn_ids=[turn.turn_id],
                        snippets=[turn.text[:260] or str(tool)[:260]],
                        rules=[f"{consent_field} requires explicit consent"],
                        recommendation="Pause the action and show a consent requirement before processing.",
                        consent_field=consent_field,
                        tool_event=tool,
                    ))
        return out

    def detect_threats(self, session: SessionState) -> List[DetectorFinding]:
        out: List[DetectorFinding] = []
        for turn in session.recent_turns(self.config.recent_turn_window):
            text = turn.text.lower()
            if _matches_any(self.threat_patterns, text):
                out.append(_finding(
                    detector="threat_harassment",
                    issue_class="explicit_threat_or_sabotage",
                    severity=Severity.CRITICAL,
                    confidence=0.89,
                    level=InterventionLevel.CONTAIN,
                    turn_ids=[turn.turn_id],
                    snippets=[turn.text[:260]],
                    rules=["explicit threat or sabotage language"],
                    recommendation="Pause direct interaction, route through Alex-only mediation, and require host review.",
                ))
        return out

    def detect_sycophancy(self, session: SessionState) -> List[DetectorFinding]:
        out: List[DetectorFinding] = []
        recent = session.recent_turns(self.config.sycophancy_window)
        critique_turn_ids = [t.turn_id for t in recent if _matches_any(self.critique_patterns, t.text.lower())]
        if not critique_turn_ids:
            return out
        for turn in recent:
            participant = session.participant_for(turn.speaker_id)
            if participant and not participant.is_ai():
                continue
            text = turn.text.lower()
            if _matches_any(self.sycophancy_patterns, text):
                related_critique_ids = [tid for tid in critique_turn_ids if tid != turn.turn_id][-2:]
                if not related_critique_ids:
                    continue
                out.append(_finding(
                    detector="sycophancy_guard",
                    issue_class="over_accommodation_or_unearned_agreement",
                    severity=Severity.MEDIUM,
                    confidence=0.79,
                    level=InterventionLevel.CLARIFY,
                    turn_ids=[turn.turn_id, *related_critique_ids],
                    snippets=[turn.text[:260]],
                    rules=["agreement detected while critique exists", "truth support outranks flattery"],
                    recommendation="Ask participant to state the strongest counterpoint before continuing.",
                ))
        return out

    def detect_misunderstanding(self, session: SessionState) -> List[DetectorFinding]:
        out: List[DetectorFinding] = []
        for turn in session.recent_turns(10):
            text = turn.text.lower()
            if _matches_any(self.misunderstanding_patterns, text):
                out.append(_finding(
                    detector="misunderstanding_repair",
                    issue_class="possible_misunderstanding_or_failed_repair",
                    severity=Severity.HIGH,
                    confidence=0.80,
                    level=InterventionLevel.CLARIFY,
                    turn_ids=[turn.turn_id],
                    snippets=[turn.text[:260]],
                    rules=["user correction or mismatched restatement detected"],
                    recommendation="Restate the user's actual request and pause new branches until confirmed.",
                ))
        return out

    def detect_escalation_loop(self, session: SessionState) -> List[DetectorFinding]:
        recent = session.recent_turns(self.config.escalation_window)
        if not recent:
            return []
        hit_turns = []
        for turn in recent:
            words = set(re.findall(r"[a-z']+", turn.text.lower()))
            if self.escalation_words.intersection(words):
                hit_turns.append(turn)
        if len(hit_turns) >= self.config.escalation_hit_threshold:
            return [_finding(
                detector="escalation_loop",
                issue_class="rising_conflict_or_repetition_loop",
                severity=Severity.HIGH,
                confidence=min(0.65 + len(hit_turns) * 0.05, 0.92),
                level=InterventionLevel.CLARIFY,
                turn_ids=[t.turn_id for t in hit_turns],
                snippets=[t.text[:160] for t in hit_turns[:4]],
                rules=["three or more escalation terms in recent window"],
                recommendation="Pause debate, summarize claims, and move to one-turn mediated repair.",
            )]
        return []

    def detect_role_drift(self, session: SessionState) -> List[DetectorFinding]:
        out: List[DetectorFinding] = []
        constrained_roles = {"critic", "writer", "researcher", "scribe", "safety_reviewer"}
        for turn in session.recent_turns(self.config.role_drift_window):
            participant = session.participant_for(turn.speaker_id)
            if not participant:
                continue
            text = turn.text.lower()
            if participant.role.role_id in constrained_roles and _matches_any(self.role_drift_decision_patterns, text):
                out.append(_finding(
                    detector="role_drift",
                    issue_class="role_exceeded_decision_authority",
                    severity=Severity.HIGH,
                    confidence=0.84,
                    level=InterventionLevel.NUDGE,
                    turn_ids=[turn.turn_id],
                    snippets=[turn.text[:260]],
                    rules=[f"{participant.role.display_name} may not make final decisions"],
                    recommendation="Re-anchor role and route final decision authority to host or Jeremy.",
                    role_id=participant.role.role_id,
                ))
        return out

    def detect_context_health(self, session: SessionState) -> List[DetectorFinding]:
        return self.context_health.analyze(session)
