from cre_eq import Baseline, ObservationPacket
from peq import MAX_OPERATIONAL_CONFIDENCE, PEQSystem, ResponseModulation, TruthAssessment, TruthStatus


def test_peq_separates_state_from_response():
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="I'm pissed that the build broke again.",
        context={"interaction_goal": "help solve the build problem"},
    )
    result = system.assess(packet)
    assert result.state.leading_state in {"frustration", "anger"}
    assert result.response.recommended_response != result.state.leading_state
    assert result.response.modulation in {
        ResponseModulation.FULL,
        ResponseModulation.RESTRAINED,
        ResponseModulation.CONSERVATIVE,
    }


def test_peq_uses_individual_baseline_as_modifier_not_emotion():
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="OKAY!!!",
        typing={"typing_wpm": 90.0},
        baseline=Baseline(typing_wpm=45.0, capitalization_ratio=0.01),
    )
    result = system.assess(packet)
    assert any(c.domain.value == "individual_baseline" for c in result.state.contributions)
    assert any(c.domain.value == "population_baseline" for c in result.state.contributions)
    assert any(c.domain.value == "individual_baseline" for c in result.state.contributions)


def test_peq_honors_high_quality_direct_report_without_reaching_100_percent():
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="I'm angry.",
        explicit_report="anger",
    )
    truth = TruthAssessment(
        status=TruthStatus.SUPPORTED,
        proposition="The user reports anger.",
        reliability=0.99,
        source_summary="Direct current self-report with no material contradiction.",
    )
    result = system.assess(packet, truth_assessment=truth)
    assert result.state.leading_state == "anger"
    assert result.state.operational_confidence <= MAX_OPERATIONAL_CONFIDENCE
    assert result.state.operational_confidence < 1.0


def test_contested_truth_reduces_state_commitment():
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="I'm thrilled.",
        explicit_report="excitement",
    )
    truth = TruthAssessment(
        status=TruthStatus.CONTESTED,
        proposition="The statement is literal excitement.",
        reliability=0.45,
        reasons_for_review=["Tone/content incongruity."],
        unresolved_questions=["Is the statement sarcastic?"],
    )
    result = system.assess(packet, truth_assessment=truth)
    assert result.state.truth_assessment.status == TruthStatus.CONTESTED
    assert result.response.modulation != ResponseModulation.FULL


def test_response_intensity_tracks_confidence():
    system = PEQSystem()
    low = TruthAssessment(TruthStatus.INCONCLUSIVE, "uncertain", 0.45, ["incongruity"], unresolved_questions=["clarify"])
    packet = ObservationPacket(subject_id="u", is_primary_user=True, text="I don't know what I feel.")
    low_result = system.assess(packet, truth_assessment=low)
    high_truth = TruthAssessment(TruthStatus.SUPPORTED, "direct report", 0.99)
    high_packet = ObservationPacket(subject_id="u", is_primary_user=True, text="I'm furious.", explicit_report="anger")
    high_result = system.assess(high_packet, truth_assessment=high_truth)
    assert high_result.response.intensity > low_result.response.intensity


def test_peq_audit_has_two_explicit_questions():
    result = PEQSystem().assess(ObservationPacket(subject_id="u", is_primary_user=True, text="hello"))
    assert set(result.audit["questions"]) == {"state", "response"}
    assert result.audit["blackbox_access"] is False


def test_situation_and_individual_baseline_are_directional_evidence_domains():
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="u",
        is_primary_user=True,
        text="OH YES!!! It finally worked!",
        typing={"typing_wpm": 90.0},
        baseline=Baseline(typing_wpm=45.0, capitalization_ratio=0.01),
        context={"situation": "the build succeeded after repeated failures"},
    )
    result = system.assess(packet)
    weighted = [c for c in result.state.contributions if c.effective_weight("excitement") != 0 or c.effective_weight("frustration") != 0]
    assert any(c.domain.value == "individual_baseline" for c in weighted)
    assert any(c.domain.value == "situation" for c in weighted)
    assert result.state.leading_state == "excitement"


def test_high_quality_supported_report_reaches_but_does_not_exceed_ceiling():
    system = PEQSystem()
    packet = ObservationPacket(subject_id="u", is_primary_user=True, text="I am furious.", explicit_report="anger")
    truth = TruthAssessment(TruthStatus.SUPPORTED, "anger report", 0.99)
    result = system.assess(packet, truth_assessment=truth, stakes=0.1)
    assert result.state.leading_state == "anger"
    assert result.state.operational_confidence == MAX_OPERATIONAL_CONFIDENCE
    assert result.response.modulation == ResponseModulation.FULL


def test_peq_can_consume_a_discriminating_truth_test():
    from cre_eq import TestResult, TestSpec

    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="u",
        is_primary_user=True,
        text="OH GREAT. I love when the build breaks.",
        explicit_report="excitement",
    )
    spec = TestSpec(
        test_id="outcome_check",
        name="outcome check",
        purpose="distinguish genuine excitement from sarcastic frustration",
        assumption_ids=["A1"],
        expected_if={"excitement": "positive outcome", "frustration": "blocked outcome"},
        procedure="Verify whether the build actually succeeded.",
    )
    observed = TestResult(
        test_id="outcome_check",
        result="positive outcome confirmed",
        observation="The build succeeded.",
        supports=["excitement"],
        weakens=["frustration"],
        materiality=0.9,
    )
    result = system.assess(packet, extra_tests=[(spec, observed)])
    assert result.audit["state"]["truth_assessment"]["tests_run"]
    assert result.audit["state"]["truth_assessment"]["tests_run"][0]["test_id"] == "outcome_check"


def test_clinical_evidence_registry_is_explicitly_non_diagnostic():
    from peq import evaluate_pattern, list_patterns

    patterns = {item["pattern_id"]: item for item in list_patterns()}
    assert "ptsd_like_trauma_response" in patterns
    assert "paranoia_like_threat_response" in patterns
    for pattern in patterns.values():
        assert pattern["diagnostic_status"] == "non_diagnostic_working_model"

    hypothesis = evaluate_pattern(
        "ptsd_like_trauma_response",
        [
            "re-experiencing or intrusive memories/dreams/flashback-like episodes",
            "avoidance of trauma reminders",
            "marked startle or hyperarousal",
        ],
    )
    assert hypothesis.status == "working_hypothesis"
    assert hypothesis.diagnosis == "none"
    assert hypothesis.match_ratio > 0.0
    assert hypothesis.predicted_response_principles


def test_clinical_evidence_sources_have_provenance_and_limits():
    from peq import list_sources

    sources = {item["source_id"]: item for item in list_sources()}
    assert "nimh_ptsd" in sources
    assert "va_dod_ptsd_2023" in sources
    assert "samhsa_trauma_informed" in sources
    assert "nimh_psychosis" in sources
    assert "apa_schizophrenia_2020" in sources
    for source in sources.values():
        assert source["url"].startswith("https://")
        assert source["limitations"]
        assert source["evidentiary_role"]


def test_peq_system_exposes_non_diagnostic_clinical_registry():
    system = PEQSystem()
    assert system.available_clinical_sources()
    assert system.available_clinical_patterns()
    hypothesis = system.evaluate_clinical_pattern(
        "paranoia_like_threat_response",
        ["persistent suspiciousness toward other people"],
    )
    assert hypothesis.status == "working_hypothesis"
    assert hypothesis.diagnosis == "none"
    assert hypothesis.predicted_response_principles


def test_expanded_scientific_registry_has_population_measurement_and_intervention_layers():
    system = PEQSystem()
    datasets = system.available_population_datasets()
    evidence = system.available_evidence_items()
    interventions = system.available_intervention_evidence()
    assert {x["source_id"] for x in datasets} >= {"cdc_brfss", "cdc_nhanes", "uk_biobank", "nih_all_of_us", "pew_american_trends_panel"}
    assert {x["evidence_id"] for x in evidence} >= {"phq9_validity", "gad7_validation", "pcl5_psychometrics", "caps5_psychometrics", "panss_measurement", "ampd_review"}
    assert {x["intervention_id"] for x in interventions} >= {"ptsd_trauma_focused_cbt", "ptsd_emdr", "psychosis_cbt_family", "depression_cb_approaches", "gad_cbt", "panic_cbt", "emotion_regulation"}
    for item in evidence:
        assert item["automation_status"] == "reference_only"
        assert item["limits"]


def test_expanded_patterns_remain_non_diagnostic():
    patterns = {x["pattern_id"]: x for x in PEQSystem().available_clinical_patterns()}
    for key in ("depressive_like_pattern", "anxiety_like_pattern", "panic_like_pattern", "emotion_dysregulation_pattern"):
        assert key in patterns
        assert patterns[key]["diagnostic_status"] == "non_diagnostic_working_model"


def test_scientific_registry_includes_dsm_pid5_personality_and_who_anchors():
    system = PEQSystem()
    sources = {x["source_id"] for x in system.all_scientific_sources()}
    evidence = {x["evidence_id"] for x in system.available_evidence_items()}
    assert {"apa_dsm5tr", "apa_pid5", "big5_emotion_regulation_review", "who_mhgap_v2"} <= sources
    assert {"dsm5tr_framework", "pid5_trait_model", "who_mhgap"} <= evidence


def test_evidence_retrieval_returns_multiple_sources_and_alternatives():
    system = PEQSystem()
    bundle = system.retrieve_evidence(
        "trauma intrusive memories hypervigilance grounding",
        top_k=8,
        alternatives_k=4,
    )
    assert bundle.primary
    assert bundle.alternatives
    assert len(bundle.source_families) >= 1
    assert all(item.limitations for item in bundle.primary)
    assert all(item.automation_status for item in bundle.primary)


def test_evidence_retrieval_does_not_collapse_to_one_answer():
    system = PEQSystem()
    bundle = system.retrieve_evidence(
        "suspiciousness paranoia anxiety threat",
        top_k=8,
        alternatives_k=5,
    )
    titles = {item.title for item in bundle.primary}
    assert len(titles) >= 2
    assert bundle.alternatives


def test_evidence_retrieval_preserves_uncovered_terms_as_uncertainty():
    system = PEQSystem()
    bundle = system.retrieve_evidence("completely_unseen_token zebrafish emotion", top_k=5)
    assert "completely_unseen_token" in bundle.uncovered_terms or "zebrafish" in bundle.uncovered_terms
    assert bundle.warnings


def test_packet_assessment_includes_retrieval_without_using_it_as_diagnosis():
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="u",
        is_primary_user=True,
        text="I can't stop checking the locks; I keep thinking someone is coming in.",
        context={"situation": "at home at night"},
    )
    result = system.assess(packet)
    retrieval = result.audit["evidence_retrieval"]
    assert retrieval["primary"]
    assert "diagnosis" not in retrieval["primary"][0]


def test_working_pattern_ranker_returns_range_not_diagnosis():
    system = PEQSystem()
    rows = system.rank_working_patterns(
        [
            "persistent suspiciousness toward other people",
            "marked uneasiness around others",
        ],
        top_k=4,
    )
    assert rows
    assert rows[0]["score"] > 0.0
    assert all(row["score"] > 0.0 for row in rows)
    assert all(row["status"] == "working_hypothesis" for row in rows)
    assert all(row["diagnosis"] == "none" for row in rows)


def test_evidence_operational_value_has_all_six_dimensions():
    bundle = PEQSystem().retrieve_evidence(
        "anxiety communication assessment response prediction risk differential uncertainty"
    )
    utility = bundle.operational_value.to_dict()
    assert set(utility) == {
        "interaction", "assessment", "response", "prediction", "risk_management", "test_selection"
    }
    assert max(utility.values()) > 0.0


def test_retrieval_exposes_operational_value_on_each_result():
    bundle = PEQSystem().retrieve_evidence("trauma grounding therapy assessment", top_k=6)
    assert bundle.primary
    for item in bundle.primary:
        values = item.operational_value.to_dict()
        assert set(values) == {
            "interaction", "assessment", "response", "prediction", "risk_management", "test_selection"
        }


def test_packet_audit_exposes_operational_value_separately_from_diagnosis():
    packet = ObservationPacket(
        subject_id="u", is_primary_user=True,
        text="I keep checking the locks because I think someone may come in.",
        context={"situation": "at home at night"},
    )
    result = PEQSystem().assess(packet)
    utility = result.audit["operational_value"]
    assert "assessment" in utility and "response" in utility
    assert "diagnosis" not in utility


def test_direct_report_only_supports_reported_state_not_all_states():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    result = PEQSystem().assess(ObservationPacket(subject_id="u", is_primary_user=True, text="I am angry.", explicit_report="anger"))
    direct = [c for c in result.state.contributions if c.source_id.startswith("direct_")]
    assert direct
    contribution = direct[0]
    assert contribution.effective_weight("anger") > 0
    assert contribution.effective_weight("excitement") < 0


def test_truth_test_supports_and_weakens_flow_into_peq_state_evidence():
    from cre_eq import TestResult, TestSpec
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    packet = ObservationPacket(subject_id="u", is_primary_user=True, text="OH GREAT. I love when the build breaks.", explicit_report="excitement")
    spec = TestSpec(test_id="t1", name="outcome", purpose="distinguish literal excitement from sarcasm", assumption_ids=["A1"], expected_if={"excitement":"success", "frustration":"failure"}, procedure="Check build outcome")
    observed = TestResult(test_id="t1", result="success", observation="Build succeeded", supports=["excitement"], weakens=["frustration"], materiality=0.9)
    result = PEQSystem().assess(packet, extra_tests=[(spec, observed)])
    ids = {c.source_id for c in result.state.contributions}
    assert "truth_test:t1" in ids
    test_contrib = next(c for c in result.state.contributions if c.source_id == "truth_test:t1")
    assert test_contrib.effective_weight("excitement") > 0
    assert test_contrib.effective_weight("frustration") < 0


def test_response_confidence_is_distinct_from_state_confidence():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    result = PEQSystem().assess(
        ObservationPacket(subject_id="u", is_primary_user=True, text="I am angry.", explicit_report="anger"),
        response_context={"interaction_goal": "clarify what happened"},
        relationship={"relationship": "new_person"},
        stakes=0.9,
    )
    assert result.response.operational_confidence <= result.state.operational_confidence
    assert len(result.response.candidates) >= 2


def test_lexical_negation_does_not_count_as_affirmative_emotion():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    result = PEQSystem().assess(ObservationPacket(subject_id="u", is_primary_user=True, text="I am not angry."))
    anger = next(c for c in result.state.candidates if c.state == "anger")
    assert not any("Current lexical signal associated with anger" in x for x in anger.supporting)


def test_lexical_negation_allows_positive_counterclaim():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    result = PEQSystem().assess(ObservationPacket(subject_id="u", is_primary_user=True, text="I am not sad. I am happy."))
    excitement = next(c for c in result.state.candidates if c.state == "excitement")
    assert any("excitement" in x for x in excitement.supporting)
    assert not any(
        c.source_id == "lexical:sadness" and c.effective_weight("sadness") > 0
        for c in result.state.contributions
    )


def test_structured_direct_report_is_not_double_counted_as_lexical_evidence():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    result = PEQSystem().assess(ObservationPacket(
        subject_id="u", is_primary_user=True, text="I am angry.", explicit_report="anger"
    ))
    sources = [c.source_id for c in result.state.contributions]
    assert any(s.startswith("direct_") for s in sources)
    assert "lexical:anger" not in sources


def test_hardening_malformed_runtime_measurements_fail_closed():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    packet = ObservationPacket(
        subject_id="u", is_primary_user=True,
        text="I am okay.",
        typing={"typing_wpm": "not-a-number", "typo_rate": float("nan")},
        audio={"pitch_mean_hz": float("inf")},
        vision={"face_arousal": object()},
    )
    result = PEQSystem().assess(packet)
    assert 0.0 <= result.state.operational_confidence <= 0.985


def test_hardening_evidence_weight_rejects_nonfinite_values():
    from peq.models import EvidenceContribution, EvidenceDomain
    c = EvidenceContribution("x", EvidenceDomain.CURRENT, "bad", float("nan"), float("inf"), float("-inf"))
    assert c.effective_weight() == 0.0
    assert c.effective_weight("anger") == 0.0


def test_hardening_retrieval_request_bounds():
    from peq.retrieval import RetrievalRequest
    try:
        RetrievalRequest("x", top_k=51)
    except ValueError:
        pass
    else:
        raise AssertionError("top_k > 50 should fail closed")
    try:
        RetrievalRequest("x" * 4097)
    except ValueError:
        pass
    else:
        raise AssertionError("oversized retrieval query should fail closed")


def test_hardening_nonfinite_stakes_do_not_corrupt_response():
    from peq import PEQSystem
    from cre_eq.models import ObservationPacket
    result = PEQSystem().assess(ObservationPacket(subject_id="u", is_primary_user=True, text="I am angry."), stakes=float("nan"))
    assert 0.0 <= result.response.operational_confidence <= 0.985
    assert 0.0 <= result.response.intensity <= 1.0

