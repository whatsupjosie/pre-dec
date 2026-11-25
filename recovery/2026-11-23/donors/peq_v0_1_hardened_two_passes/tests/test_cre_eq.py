from dataclasses import replace

from cre_eq import Baseline, CREStateStore, CriticalReasoningEngine, ObservationPacket, TestResult, TestSpec


def test_observations_are_not_emotions():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="I am VERY excited!!!",
        typing={"typing_wpm": 82.0},
        baseline=Baseline(typing_wpm=50.0, capitalization_ratio=0.02),
    )
    result = engine.assess(packet)
    labels = {e.label for e in result.trace.observations}
    assert "capitalization_ratio" in labels
    assert result.leading_state in {"excitement", "frustration", "anxiety", "neutral"}
    assert result.trace.observations



def test_sparse_affect_evidence_does_not_force_emotion():
    engine = CriticalReasoningEngine()
    result = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I am fine."))
    assert result.leading_state == "neutral"
    assert result.status.value == "inconclusive"

def test_direct_self_report_has_high_weight():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="I am fine.",
        explicit_report="sadness",
    )
    result = engine.assess(packet)
    assert result.leading_state == "sadness"
    assert result.confidence > 0.60


def test_sarcasm_is_an_alternative_explanation_not_fact():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="OH GREAT!!! I absolutely love when the build breaks.",
        context={"interaction_goal": "debugging"},
    )
    result = engine.assess(packet)
    assert result.leading_state in {"frustration", "excitement"}
    assert any("sarcastic" in a.statement.lower() for a in result.trace.assumptions)
    assert result.response_appraisal.expressive_emotion == "neutral warmth + curiosity"


def test_best_of_three_stops_on_majority():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(subject_id="user", is_primary_user=True, text="I'm thrilled")
    results = [engine.assess(packet), engine.assess(packet)]
    summary = engine.best_of_three(results)
    assert summary["status"] == "majority_but_not_independent"
    assert summary["winner"] is None
    assert summary["provisional_winner"] == "excitement"


def test_best_of_three_forces_divergence_analysis():
    engine = CriticalReasoningEngine()
    a = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm thrilled"))
    b = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm furious"))
    c = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm furious"))
    summary = engine.best_of_three([a, b, c])
    assert summary["status"] == "majority_but_not_independent"
    assert summary["winner"] is None
    assert summary["provisional_winner"] == "anger"
    assert summary["root_cause_required"] is True
    assert summary["disagreements"]
    assert summary["independence_warning"] is True


def test_executed_discrimination_test_appears_in_trace():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="I can't believe we finally did this!",
        typing={"typing_wpm": 85},
    )
    spec = TestSpec(
        test_id="manual_1",
        name="context check",
        purpose="distinguish excitement from frustration",
        assumption_ids=["A1"],
        expected_if={"excitement": "celebration", "frustration": "blocked goal"},
        procedure="Ask for the outcome context.",
    )
    observed = TestResult(
        test_id="manual_1",
        result="positive outcome confirmed",
        observation="User confirms the project succeeded.",
        supports=["excitement"],
        weakens=["frustration"],
        materiality=0.8,
    )
    result = engine.assess(packet, extra_tests=[(spec, observed)])
    assert result.trace.test_results[0].test_id == "manual_1"
    assert result.leading_state == "excitement"


def test_response_appraisal_does_not_equal_user_emotion():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(
        subject_id="user",
        is_primary_user=True,
        text="This is bullshit. I'm pissed.",
    )
    result = engine.assess(packet)
    assert result.leading_state == "frustration"
    assert result.response_appraisal.expressive_emotion != "anger"
    assert result.response_appraisal.expressive_emotion != "anger"
    assert "steady" in result.response_appraisal.desired_posture or result.response_appraisal.confidence < 0.65


def test_direct_anger_is_supported_as_anger():
    engine = CriticalReasoningEngine()
    result = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm angry.", explicit_report="anger"))
    assert result.leading_state == "anger"
    assert result.confidence > 0.60
    assert result.confidence < 0.90


def test_two_same_engine_runs_are_not_validated_independent_replication():
    engine = CriticalReasoningEngine()
    packet = ObservationPacket(subject_id="user", is_primary_user=True, text="I'm thrilled")
    a = engine.assess(packet)
    b = engine.assess(packet)
    summary = engine.best_of_three([a, b])
    assert summary["status"] == "majority_but_not_independent"
    assert summary["winner"] is None
    assert summary["provisional_winner"] == "excitement"


def test_neutral_low_signal_does_not_schedule_a_fake_discrimination_test():
    engine = CriticalReasoningEngine()
    result = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="hello there"))
    assert not result.trace.tests


def test_state_store_persists_to_disk(tmp_path):
    path = tmp_path / "cre_state.json"
    first = CREStateStore(path)
    first.save("session", {"leading_state": "sadness", "confidence": 0.71})
    second = CREStateStore(path)
    assert second.load("session") == {"leading_state": "sadness", "confidence": 0.71}


def test_word_matching_does_not_false_match_substrings():
    engine = CriticalReasoningEngine()
    result = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I am on a wonderful website."))
    assert result.leading_state != "sadness"


def test_explicit_report_can_override_ambiguous_text_without_certainty_claim():
    engine = CriticalReasoningEngine()
    result = engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I can't believe it.", explicit_report="happiness"))
    assert result.leading_state == "excitement"
    assert result.confidence_type == "uncalibrated_assessed_confidence"


def test_three_way_disagreement_is_not_resolved_by_vote():
    engine = CriticalReasoningEngine()
    assessments = [
        engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm thrilled"), method_id="A"),
        engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm furious"), method_id="B"),
        engine.assess(ObservationPacket(subject_id="user", is_primary_user=True, text="I'm exhausted"), method_id="C"),
    ]
    summary = engine.best_of_three(assessments)
    assert summary["status"] == "three_way_disagreement"
    assert summary["winner"] is None
    assert summary["root_cause_required"] is True
