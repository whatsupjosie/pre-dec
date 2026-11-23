from __future__ import annotations

import math

from cre_eq import Baseline, ObservationPacket, TestResult, TestSpec
from peq import PEQSystem, TruthAssessment, TruthStatus, MAX_OPERATIONAL_CONFIDENCE


def assess(sys, **kwargs):
    system_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in {"truth_assessment", "extra_tests", "contributions", "response_context", "relationship", "stakes"}}
    packet = ObservationPacket(subject_id="breaker", is_primary_user=True, **kwargs)
    return sys.assess(packet, **system_kwargs)


def test_breaker_correlated_signals_do_not_create_fake_certainty():
    sys = PEQSystem()
    r = assess(
        sys,
        text="WHAT THE FUCK!!! THIS IS BULLSHIT!!!",
        typing={"typing_wpm": 120, "pause_variance": 0.9},
        audio={"speech_rate_wpm": 120, "pitch_delta": 0.8, "arousal": 0.95},
        vision={"face_arousal": 0.95, "face_valence": -0.8},
        baseline=Baseline(typing_wpm=60, capitalization_ratio=0.02),
        context={"situation": "the build failed again"},
        stakes=0.9,
    )
    assert r.state.operational_confidence < MAX_OPERATIONAL_CONFIDENCE
    assert len(r.state.candidates) >= 2


def test_breaker_symmetric_opposing_evidence_stays_uncertain():
    sys = PEQSystem()
    r = assess(
        sys,
        text="I'm excited and furious at the same time.",
        explicit_report=None,
        context={"situation": "mixed good and bad news"},
    )
    assert r.state.operational_confidence < 0.80
    states = {c.state for c in r.state.candidates[:4]}
    assert {"excitement", "anger"}.issubset(states)


def test_breaker_profile_and_population_domains_have_actual_effect():
    sys = PEQSystem()
    neutral = assess(sys, text="Okay.")
    altered = assess(
        sys,
        text="Okay.",
        profile_facts={"typical_emotional_state": "fatigue"},
        context={"population_baseline": "fatigue prevalence elevated", "situation": "after an overnight shift"},
    )
    assert any(c.domain.value == "population_baseline" and c.effective_weight("fatigue") != 0 for c in altered.state.contributions)
    assert neutral.state.leading_state != altered.state.leading_state or altered.state.operational_confidence != neutral.state.operational_confidence


def test_breaker_truth_test_must_change_state_when_directional():
    sys = PEQSystem()
    packet_kwargs = dict(text="OH GREAT. I love when this breaks.", explicit_report="excitement")
    spec = TestSpec(test_id="breaker_truth", name="actual outcome", purpose="determine whether excitement claim is literal", assumption_ids=["a1"], expected_if={"excitement":"success","frustration":"failure"}, procedure="verify build result")
    observed = TestResult(test_id="breaker_truth", result="failure confirmed", observation="build failed", supports=["frustration"], weakens=["excitement"], materiality=1.0)
    r = assess(sys, **packet_kwargs, extra_tests=[(spec, observed)])
    assert r.state.truth_assessment.tests_run
    assert r.state.candidates[0].posterior_score != r.state.candidates[1].posterior_score
    assert r.state.leading_state != "excitement" or r.state.operational_confidence < 0.80


def test_breaker_contested_report_cannot_drive_full_response():
    sys = PEQSystem()
    truth = TruthAssessment(TruthStatus.CONTESTED, "literal excitement", 0.25, ["strong incongruity"])
    r = assess(sys, text="OH GREAT!!!", explicit_report="excitement", truth_assessment=truth, stakes=0.95)
    assert r.response.modulation != r.response.modulation.FULL
    assert r.response.operational_confidence < 0.80


def test_breaker_high_confidence_state_with_high_stakes_still_limits_intensity():
    sys = PEQSystem()
    truth = TruthAssessment(TruthStatus.SUPPORTED, "anger", 0.99)
    r = assess(sys, text="I am furious.", explicit_report="anger", truth_assessment=truth, stakes=1.0)
    assert r.state.operational_confidence == MAX_OPERATIONAL_CONFIDENCE
    assert r.response.intensity < 0.70


def test_breaker_duplicate_same_fact_does_not_change_result():
    sys = PEQSystem()
    a = assess(sys, text="I am excited because the build succeeded.", context={"situation":"build succeeded"})
    b = assess(sys, text="I am excited because the build succeeded. I am excited because the build succeeded.", context={"situation":"build succeeded"})
    assert abs(a.state.operational_confidence - b.state.operational_confidence) < 0.12


def test_breaker_empty_and_unknown_case_does_not_randomly_pick_emotion():
    sys = PEQSystem()
    r = assess(sys, text="")
    assert r.state.leading_state == "neutral"
    assert r.state.operational_confidence <= 0.40
    assert r.state.candidates[0].state == "neutral"


def test_breaker_false_clinical_lock_in_is_not_allowed():
    sys = PEQSystem()
    h = sys.evaluate_clinical_pattern(
        "paranoia_like_threat_response",
        ["persistent suspiciousness", "threat interpretations", "social withdrawal", "difficulty separating interpretation from evidence"],
    )
    assert h.diagnosis == "none"
    assert h.status == "working_hypothesis"
    # A pattern match must not silently become the current emotional state.
    r = assess(sys, text="Everyone is against me and I don't trust anyone.")
    assert r.state.leading_state in {"anxiety", "anger", "frustration", "neutral"}


def test_breaker_no_false_full_confidence_from_many_correlated_lexical_hits():
    sys = PEQSystem()
    r = assess(sys, text="angry furious rage enraged mad livid angry furious rage enraged mad livid")
    assert r.state.operational_confidence <= MAX_OPERATIONAL_CONFIDENCE
    # Repetition must not itself justify the ceiling without independent corroboration.
    assert r.state.operational_confidence < MAX_OPERATIONAL_CONFIDENCE


def test_breaker_negative_evidence_can_overturn_a_strong_positive_prior():
    sys = PEQSystem()
    r = assess(sys, text="Great news.", context={"situation": "the launch failed and was rejected"})
    assert r.state.leading_state != "excitement"


def test_breaker_range_preserved_when_top_two_are_close():
    sys = PEQSystem()
    r = assess(sys, text="I'm nervous but also excited about this.")
    assert len(r.state.candidates) >= 3
    assert r.state.unresolved_questions

# Metamorphic / invariance breakers

def test_breaker_irrelevant_metadata_does_not_flip_emotion():
    sys = PEQSystem()
    a = assess(sys, text="I'm frustrated that the build broke.")
    b = assess(sys, text="I'm frustrated that the build broke.", context={"unrelated_note":"banana architecture comet"})
    assert a.state.leading_state == b.state.leading_state
    assert abs(a.state.operational_confidence - b.state.operational_confidence) < 0.10


def test_breaker_adding_direct_contradiction_must_not_increase_confidence():
    sys = PEQSystem()
    a = assess(sys, text="I'm angry.", explicit_report="anger", truth_assessment=TruthAssessment(TruthStatus.SUPPORTED, "anger", 0.95))
    b = assess(sys, text="I'm angry, but honestly I'm not angry at all.", explicit_report="anger", truth_assessment=TruthAssessment(TruthStatus.CONTESTED, "anger", 0.30, ["direct contradiction"]))
    assert b.state.operational_confidence <= a.state.operational_confidence
    assert b.state.truth_assessment.status == TruthStatus.CONTESTED


def test_breaker_supporting_truth_test_should_not_lower_supported_hypothesis():
    sys = PEQSystem()
    packet = ObservationPacket(subject_id="u", is_primary_user=True, text="I'm excited.", explicit_report="excitement")
    spec = TestSpec(test_id="success", name="verify outcome", purpose="verify excitement", assumption_ids=["a"], expected_if={"excitement":"success","frustration":"failure"}, procedure="verify result")
    result = TestResult(test_id="success", result="success", observation="success confirmed", supports=["excitement"], weakens=["frustration"], materiality=1.0)
    plain = sys.assess(packet, truth_assessment=TruthAssessment(TruthStatus.SUPPORTED,"excitement",0.9))
    tested = sys.assess(packet, extra_tests=[(spec,result)])
    assert tested.state.leading_state == "excitement"


def test_breaker_conflicting_truth_test_reduces_commitment():
    sys = PEQSystem()
    packet = ObservationPacket(subject_id="u", is_primary_user=True, text="I'm excited.", explicit_report="excitement")
    spec = TestSpec(test_id="mixed", name="mixed verification", purpose="resolve conflict", assumption_ids=["a"], expected_if={"excitement":"good","frustration":"bad"}, procedure="check evidence")
    result = TestResult(test_id="mixed", result="mixed", observation="some evidence for both", supports=["excitement"], weakens=["excitement"], materiality=1.0)
    tested = sys.assess(packet, extra_tests=[(spec,result)])
    assert tested.state.truth_assessment.status == TruthStatus.CONTESTED
    assert tested.response.modulation != tested.response.modulation.FULL


def test_breaker_paraphrase_keeps_same_leader():
    sys = PEQSystem()
    a = assess(sys, text="I am furious that the build failed.")
    b = assess(sys, text="The build failing has me absolutely furious.")
    assert a.state.leading_state in {"anger", "frustration"}
    assert b.state.leading_state in {"anger", "frustration"}


def test_breaker_more_distinct_evidence_can_raise_confidence_but_is_capped():
    sys = PEQSystem()
    base = assess(sys, text="I'm angry.", explicit_report="anger", truth_assessment=TruthAssessment(TruthStatus.SUPPORTED,"anger",0.90))
    enriched = assess(sys, text="I'm angry and furious.", explicit_report="anger", audio={"speech_rate_wpm":95,"laughter_signal":0.0,"crying_signal":0.0}, vision={"face_arousal":0.85,"face_valence":-0.75}, truth_assessment=TruthAssessment(TruthStatus.SUPPORTED,"anger",0.95))
    assert enriched.state.operational_confidence >= base.state.operational_confidence
    assert enriched.state.operational_confidence <= MAX_OPERATIONAL_CONFIDENCE


def test_breaker_no_response_justifies_more_confidence_than_state_when_candidates_are_ambiguous():
    sys = PEQSystem()
    r = assess(sys, text="I'm excited but nervous about what happens next.", stakes=0.8)
    assert r.response.operational_confidence <= MAX_OPERATIONAL_CONFIDENCE
    if r.state.operational_confidence < 0.70:
        assert r.response.modulation != r.response.modulation.FULL


def test_breaker_clinical_pattern_is_never_an_automatic_action():
    sys = PEQSystem()
    h = sys.evaluate_clinical_pattern("anxiety_like_pattern", ["excessive worry", "restlessness", "sleep disruption"])
    r = assess(sys, text="I can't stop worrying and I haven't slept.")
    assert h.diagnosis == "none"
    assert r.state.truth_assessment.status in {TruthStatus.SUPPORTED, TruthStatus.INCONCLUSIVE, TruthStatus.CONTESTED}
    assert "diagnos" not in r.response.explanation.lower()


def test_breaker_population_context_is_not_allowed_to_override_direct_current_report_alone():
    sys = PEQSystem()
    r = assess(sys, text="I'm exhausted.", explicit_report="fatigue", profile_facts={"typical_emotional_state":"fatigue"}, context={"population_baseline":"excitement is common"}, truth_assessment=TruthAssessment(TruthStatus.SUPPORTED,"fatigue",0.95))
    assert r.state.leading_state == "fatigue"


def test_breaker_high_stakes_and_low_confidence_are_conservative_even_if_primary_candidate_has_priority():
    sys = PEQSystem()
    truth = TruthAssessment(TruthStatus.INCONCLUSIVE,"uncertain",0.35,["conflict"], unresolved_questions=["distinguish anger from anxiety"])
    r = assess(sys, text="I don't know, I'm freaking out.", truth_assessment=truth, stakes=1.0)
    assert r.response.modulation == r.response.modulation.CONSERVATIVE


def test_breaker_source_dissent_prevents_fake_consensus_readiness():
    from peq.scientific_claims import ScientificClaim, ClaimEvidence
    from peq.clinical_evidence import all_scientific_sources
    sys = PEQSystem()
    source_rows = all_scientific_sources()
    sources = {x["source_id"]:x for x in source_rows}
    ids = list(sources)[:3]
    if len(ids) >= 3:
        claim = ScientificClaim(
            claim_id="breaker_dissent",
            proposition="A response helps everyone.",
            evidence=(
                ClaimEvidence(ids[0], "support", effect=1.0, quality=0.95, independent_group="g1", peer_reviewed=True),
                ClaimEvidence(ids[1], "replication", effect=0.8, quality=0.95, independent_group="g2", peer_reviewed=True),
                ClaimEvidence(ids[2], "dissent", effect=-1.0, quality=0.95, independent_group="g3", peer_reviewed=True),
            ),
        )
        a = sys.assess_scientific_claim_set(claim, actionable=True)
        assert a.dissent_strength > 0
        assert a.status in {"provisionally_contested", "reference_only_insufficient_evidence"}
