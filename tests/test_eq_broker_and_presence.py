"""Emotional broker fixes (ported from the 2026-10-02 empathy pass) and the crisis presence rules.

Owner rules tested here, 2026-11-23: "unless the person asks, no referring to services. No brushing
them off." and, on safety-check questions, "Don't ask them that. It makes it worse."
Run: pytest -q tests/test_eq_broker_and_presence.py
"""
from __future__ import annotations

import pytest

from companion_support.conversation_pacing import GriefWeight, MomentGuard, PacingDecision, PacingReport, PresenceMode
from modules.emotional_orchestrator import EmotionalOrchestrator, EmotionSignal


def signal(**over):
    base = dict(source="eq", subject_id="u", session_id="s", observed_at=1000.0, confidence=0.5,
                dimensions={"load": 0.4}, provenance="test")
    base.update(over)
    return EmotionSignal(**base)


@pytest.mark.parametrize("field,value", [
    ("confidence", float("nan")), ("confidence", float("inf")), ("observed_at", float("nan")),
    ("confidence", "high"),
])
def test_non_finite_or_non_numeric_evidence_is_refused(field, value):
    with pytest.raises(ValueError):
        signal(**{field: value})


def test_non_finite_dimension_is_refused():
    with pytest.raises(ValueError):
        signal(dimensions={"load": float("nan")})


def test_clinical_floor_holds_at_the_broker_boundary():
    broker = EmotionalOrchestrator(clock=lambda: 1000.0)
    broker.publish(signal(source="peq", clinical_hypothesis=False))
    broker.publish_secondary(source="cre_eq", subject_id="u", session_id="s", dimensions={"load": 0.9},
                             confidence=0.9, provenance="test", clinical_hypothesis=False)
    bundle = broker.evidence_bundle(subject_id="u", session_id="s")
    assert all(s.clinical_hypothesis for s in bundle.signals)
    assert "load" not in broker.adjudicate(subject_id="u", session_id="s").dimensions


def test_one_noisy_source_cannot_evict_the_others():
    broker = EmotionalOrchestrator(clock=lambda: 1000.0, max_signals=16)
    broker.publish(signal(source="alex_affect", event_id="keep"))
    for i in range(200):
        broker.publish(signal(source="conversation", event_id=f"n{i}"))
    sources = [s.source for s in broker.evidence_bundle(subject_id="u", session_id="s").signals]
    assert "alex_affect" in sources and sources.count("conversation") == 8


def test_existing_selection_order_is_unchanged():
    # The empathy pass's "self-report always wins" rule was deliberately NOT ported: trust is earned
    # per person. Higher credibility still wins, as before.
    broker = EmotionalOrchestrator(clock=lambda: 1000.0)
    broker.publish(signal(source="participant_self_report", confidence=0.4, dimensions={"load": 0.1}))
    broker.publish(signal(source="alex_affect", confidence=0.9, dimensions={"load": 0.8}))
    assert broker.adjudicate(subject_id="u", session_id="s").selected_source["load"] == "alex_affect"


def test_crisis_presence_asks_nothing_and_refers_nowhere():
    line = PresenceMode().crisis_response()
    assert "?" not in line
    for word in ("988", "741741", "hotline", "safe", "therapist"):
        assert word not in line.lower()


ACUTE = PacingReport(decision=PacingDecision.STAY, grief_weight=GriefWeight.ACUTE,
                     allowed_contributions=["crisis_acknowledgment"])


@pytest.mark.parametrize("reply", [
    "Are you safe right now?",
    "Is anyone with you?",
    "Please call 988.",
    "You should talk to a therapist.",
    "There is a crisis line you can text.",
])
def test_acute_gate_blocks_hand_offs_and_safety_scripts(reply):
    approved, reason = MomentGuard().check(reply, ACUTE, "crisis_acknowledgment")
    assert approved is False and "stay with them" in reason


def test_acute_gate_lets_presence_through():
    approved, _ = MomentGuard().check("I'm right here with you. Tell me what happened.", ACUTE,
                                      "crisis_acknowledgment")
    assert approved is True
