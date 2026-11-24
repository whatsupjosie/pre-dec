"""EQ observation layer (shadow): measurement, baselines, trust, readers, storage, spine and routes.

Synthetic people and messages only. Run: pytest -q tests/test_eq_observation.py
"""
from __future__ import annotations

import asyncio
import json
import math
from dataclasses import replace

import pytest

from modules.eq_observation import DEFAULT_DIALS, ObservationError, ObservationLayer, PerceptionReader
from modules.eq_observation.baseline import FeatureBaseline
from modules.eq_observation.features import behaviour_features, likely_typos, text_features
from modules.eq_observation.store import PersonStore, person_folder_name

ORDINARY = [
    "Spent the morning sorting cables and then fixed the camera mount that kept slipping off the rail.",
    "We got the script pages printed and the actors read through the second scene twice this afternoon.",
    "The paint on the back wall dried overnight, so tomorrow we can hang the frames and test the shots.",
    "I tried the new microphone in the booth and it picks up the room much better than the old one did.",
    "Lunch was late but the crew stayed and we blocked out the whole opening sequence before dinner.",
    "The director wants a wider lens for the second camera, so I ordered one that should arrive Friday.",
    "We recorded three takes of the intro and the last one was clean enough to keep for the edit.",
    "Tonight I am going to review the footage and mark the good moments so the editor has a head start.",
    "The weather held up so we shot the outdoor part by the fountain and the light was really warm.",
    "I moved the camera cart closer to the stage so the cables reach without crossing the walkway.",
]
CALM_KEYS = {"chars_per_second": 4.0, "backspace_ratio": 0.04, "pause_before_send_s": 2.0, "edit_count": 1}


def keyboard(values, consent=True, status="observed"):
    return {"consent": {"keyboard": consent}, "keyboard": {"status": status, **values}}


def settle(layer, user="person-a", turns=ORDINARY, with_keys=False, start=1000.0):
    reading = None
    for i, text in enumerate(turns):
        # Small natural variation so baselines have a spread.
        keys = {k: v * (1 + 0.05 * ((i % 3) - 1)) for k, v in CALM_KEYS.items()} if with_keys else None
        reading = layer.observe_turn(user_id=user, session_id="s1", turn_id=f"t{i}", source_id=f"src{i}",
                                     text=text, behaviour=keyboard(keys) if keys else None, now=start + i)
    return reading


# ---- measurement ---------------------------------------------------------------------------------

def test_plain_capitals_are_not_shouting():
    calm, _, _ = text_features("OK, the TV is on and the PDF is sent.", {}, min_count=3)
    loud, _, _ = text_features("STOP touching the CAMERA right now.", {}, min_count=3)
    assert calm["caps_ratio"] == 0.0
    assert loud["caps_ratio"] > 0.2


def test_typos_are_judged_against_the_persons_own_words_and_never_names():
    vocab = {"camera": 5, "stage": 4, "lights": 3}
    assert likely_typos(["camrea"], vocab, 3) == 1         # swapped letters
    assert likely_typos(["cameras"], vocab, 3) == 1        # one letter added: never used before
    assert likely_typos(["camera"], vocab, 3) == 0         # their own word
    assert likely_typos(["stagger"], vocab, 3) == 0        # two edits away
    values, _, _ = text_features("Jane met Camrea and the camrea crew at the stage today", vocab, min_count=3)
    # only the lower-case camrea is judged; Jane and Camrea (capitalised) are not
    assert values["likely_typo_rate"] == pytest.approx(1 / 11)


def test_code_and_long_documents_are_not_conversational_writing():
    assert text_features("```python\nprint(1)\n```", {}, min_count=3)[1] == "unavailable"
    assert text_features("word " * 2500, {}, min_count=3)[1] == "unavailable"


@pytest.mark.parametrize("payload,status", [
    (keyboard(CALM_KEYS, consent=False), "no_consent"),
    (keyboard(CALM_KEYS, status="simulated"), "simulated"),
    ({"keyboard": dict(CALM_KEYS)}, "no_consent"),
])
def test_behaviour_needs_consent_and_real_observation(payload, status):
    values, statuses, problems = behaviour_features(payload)
    assert values == {} and statuses["keyboard"] == status and problems


def test_behaviour_refuses_non_finite_and_negative_values():
    values, statuses, problems = behaviour_features(keyboard({"chars_per_second": float("nan"),
                                                               "backspace_ratio": -1, "edit_count": 2}))
    assert values == {"edit_count": 2.0} and statuses["keyboard"] == "observed" and len(problems) == 2


# ---- baselines -----------------------------------------------------------------------------------

def test_baseline_says_nothing_until_it_has_enough_samples():
    b = FeatureBaseline()
    for v in range(DEFAULT_DIALS.baseline_min_samples - 1):
        b.update(10.0 + v, DEFAULT_DIALS)
        assert b.deviation(100.0, DEFAULT_DIALS, "word_count") is None
    b.update(12.0, DEFAULT_DIALS)
    assert b.deviation(100.0, DEFAULT_DIALS, "word_count") == DEFAULT_DIALS.z_clip


def test_spread_floor_keeps_one_exclamation_from_being_extreme():
    b = FeatureBaseline()
    for _ in range(20):
        b.update(0.0, DEFAULT_DIALS)
    assert b.deviation(0.25, DEFAULT_DIALS, "exclaim_rate") == pytest.approx(1.0)


def test_baseline_follows_a_person_after_its_memory_fills():
    dials = replace(DEFAULT_DIALS, baseline_memory=20)
    b = FeatureBaseline()
    for _ in range(20):
        b.update(10.0, dials)
    for _ in range(200):
        b.update(30.0, dials)
    assert b.mean == pytest.approx(30.0, abs=0.01) and b.n == 20 and math.isfinite(b.variance())


def test_corrupt_baseline_rows_load_as_neutral():
    assert FeatureBaseline.from_dict({"n": 5, "mean": float("nan"), "m2": 1}).n == 0
    assert FeatureBaseline.from_dict({"n": "x"}).n == 0


# ---- the inner reader ----------------------------------------------------------------------------

def test_everybody_starts_neutral(tmp_path):
    layer = ObservationLayer(tmp_path)
    first = layer.observe_turn(user_id="new", session_id="s", turn_id="t0", source_id="x", text="hello there")
    assert first["status"] == "warming_up"
    assert first["aggregate"]["band"] is None
    assert set(first["groups"].values()) == {"warming_up"}
    assert ObservationLayer.shadow_view(first)["inner_state"]["different_from_usual"] is None


def test_a_message_is_read_before_it_joins_the_baseline(tmp_path):
    layer = ObservationLayer(tmp_path)
    settle(layer)
    short = layer.observe_turn(user_id="person-a", session_id="s1", turn_id="tx", source_id="sx", text="fine.")
    assert short["groups"]["message_shape"] == "departed"
    assert short["axes"]["contraction"]["direction"] == "up"
    assert short["deviations"]["word_count"] <= -DEFAULT_DIALS.deviation_threshold


def test_says_fine_while_two_independent_witnesses_differ_is_a_gap(tmp_path):
    layer = ObservationLayer(tmp_path)
    settle(layer, with_keys=True)
    reading = layer.observe_turn(user_id="person-a", session_id="s1", turn_id="tx", source_id="sx",
                                 text="im fine.", report={"said": "fine", "plain": True},
                                 behaviour=keyboard({"chars_per_second": 4.0, "backspace_ratio": 0.4,
                                                     "pause_before_send_s": 30.0, "edit_count": 9}))
    assert {"message_shape", "motor"} <= set(reading["departed"])
    assert reading["report_gap"]["kind"] == "says_fine_witnesses_differ"
    assert reading["calibration_candidate"] == "says_fine_witnesses_differ"
    card = ObservationLayer.shadow_view(reading)["inner_state"]
    assert card["report_gap"] is True and "never tell them" in card["label"].lower()
    # no numbers or text leave through the card
    assert "deviations" not in card and "im fine" not in json.dumps(card)


def test_one_witness_alone_is_never_a_gap(tmp_path):
    layer = ObservationLayer(tmp_path)
    settle(layer)
    reading = layer.observe_turn(user_id="person-a", session_id="s1", turn_id="tx", source_id="sx",
                                 text="fine.", report={"said": "fine", "plain": True})
    assert reading["report_gap"] is None


# ---- calibration: moments, verdicts, trust ---------------------------------------------------------

def _gap_turn(layer, user="person-a", turn="tx"):
    settle(layer, user=user, with_keys=True)
    return layer.observe_turn(user_id=user, session_id="s1", turn_id=turn, source_id="src-" + turn,
                              text="im fine.", report={"said": "fine", "plain": True}, now=5000.0,
                              behaviour=keyboard({"chars_per_second": 4.0, "backspace_ratio": 0.4,
                                                  "pause_before_send_s": 30.0, "edit_count": 9}))


def test_moments_carry_evidence_the_interview_store_accepts(tmp_path):
    layer = ObservationLayer(tmp_path)
    _gap_turn(layer)
    moments = layer.calibration_moments(user_id="person-a")
    assert moments[0]["turn_id"] == "tx"
    assert moments[0]["evidence"] == {"session_id": "s1", "turn_id": "tx", "source_id": "src-tx"}
    assert "they said they were fine" in moments[0]["why"]
    assert "messages were shorter than usual" in moments[0]["why"]
    assert "never name a feeling" in moments[0]["interviewer_rule"].lower()


def test_an_approved_account_moves_trust_once_and_measures_its_own_delay(tmp_path):
    layer = ObservationLayer(tmp_path)
    _gap_turn(layer)
    result = layer.apply_calibration_verdict(user_id="person-a", turn_id="tx", now=5000.0 + 86400,
                                             verdict={"answer": "something_was_going_on", "approved": True,
                                                      "calm": True, "delay_s": 1})
    step = DEFAULT_DIALS.reliability_learning_rate * (1 - DEFAULT_DIALS.neutral_reliability)
    assert result["trust"]["message_shape"] == pytest.approx(DEFAULT_DIALS.neutral_reliability + step)
    assert result["trust"]["report_in_moment"] == pytest.approx(DEFAULT_DIALS.neutral_reliability - step)
    state = layer.store.load_state("person-a")
    assert state["verdicts"][-1]["delay_s"] == 86400.0      # measured from the reading, not the caller's 1
    assert state["verdicts"][-1]["calm"] is True
    with pytest.raises(ObservationError):
        layer.apply_calibration_verdict(user_id="person-a", turn_id="tx",
                                        verdict={"answer": "nothing_was_going_on", "approved": True})
    assert layer.calibration_moments(user_id="person-a") == []  # answered moments are not offered again


@pytest.mark.parametrize("verdict,error", [
    ({"answer": "something_was_going_on"}, ObservationError),
    ({"answer": "they were sad", "approved": True}, ObservationError),
    ({"answer": "partly", "approved": True, "calm": "yes"}, ObservationError),
])
def test_unapproved_or_malformed_accounts_change_nothing(tmp_path, verdict, error):
    layer = ObservationLayer(tmp_path)
    _gap_turn(layer)
    with pytest.raises(error):
        layer.apply_calibration_verdict(user_id="person-a", turn_id="tx", verdict=verdict)
    assert layer.summary(user_id="person-a")["trust_evidence"] == {}


def test_partly_is_recorded_but_moves_no_trust(tmp_path):
    layer = ObservationLayer(tmp_path)
    _gap_turn(layer)
    layer.apply_calibration_verdict(user_id="person-a", turn_id="tx", verdict={"answer": "partly", "approved": True})
    summary = layer.summary(user_id="person-a")
    assert summary["trust_evidence"] == {} and summary["verdicts"] == 1


def test_unknown_turn_is_not_found(tmp_path):
    with pytest.raises(LookupError):
        ObservationLayer(tmp_path).apply_calibration_verdict(
            user_id="nobody", turn_id="nope", verdict={"answer": "partly", "approved": True})


def test_disagreement_alone_never_discounts_the_report(tmp_path):
    layer = ObservationLayer(tmp_path)
    for n in range(5):
        _gap_turn(layer, user=f"p{n}")
    assert all(layer.summary(user_id=f"p{n}")["trust"]["report_in_moment"] == DEFAULT_DIALS.neutral_reliability
               for n in range(5))


# ---- the perception reader -------------------------------------------------------------------------

@pytest.mark.parametrize("reply,expected", [
    ("If you feel like it, we can look at it tomorrow.", []),
    ("When you feel ready, send it over.", []),
    ("How do you feel about the shot?", ["invites_a_reply"]),
    ("Just checking in.", []),
    ("Go for it!", []),
    ("You feel sad. That is okay.", ["may_read_as_telling_them_how_they_feel"]),
    ("Maybe you feel tired after all that.", ["may_read_as_telling_them_how_they_feel"]),
    ("You're clearly upset.", ["may_read_as_telling_them_how_they_feel"]),
    ("You should rest. Try some tea.", ["may_read_as_orders"]),
    ("I understand how you feel.", ["may_read_as_script_or_brush_off"]),
])
def test_reply_perception(reply, expected):
    assert PerceptionReader(DEFAULT_DIALS).perceive_reply(reply, user_message="the lights are done")["expected_reads"] == expected


def test_display_perception_is_absolute_not_personal():
    reads = PerceptionReader(DEFAULT_DIALS).perceive_display({"caps_ratio": 0.5, "word_count": 2, "expressivity": 0.1})
    assert reads["expected_reads"] == ["reads_as_intense", "reads_as_brief", "looks_flat"]
    assert "not what is felt" in reads["label"]


def test_perception_feedback_scores_once(tmp_path):
    layer = ObservationLayer(tmp_path)
    p = layer.perceive_reply(user_id="person-a", turn_id="t1", reply="You should rest. Try some tea.",
                             user_message="long day")
    assert p["influence"].startswith("none")
    card = layer.record_perception_feedback(user_id="person-a", prediction_id=p["prediction_id"],
                                            observed_reads=["may_read_as_orders", "came_across_cold"])
    assert card["predicted:may_read_as_orders"]["hit_rate"] == 1.0
    assert card["missed:came_across_cold"]["hit_rate"] == 0.0
    with pytest.raises(ObservationError):
        layer.record_perception_feedback(user_id="person-a", prediction_id=p["prediction_id"], observed_reads=[])
    with pytest.raises(LookupError):
        layer.record_perception_feedback(user_id="person-a", prediction_id="0" * 32, observed_reads=[])


# ---- storage ---------------------------------------------------------------------------------------

def test_ids_that_clean_to_the_same_slug_never_share_a_folder():
    assert person_folder_name("a/b") != person_folder_name("a_b")


def test_no_message_text_on_disk_except_the_persons_word_counts(tmp_path):
    layer = ObservationLayer(tmp_path)
    settle(layer)
    folder = layer.store.folder("person-a")
    readings = (folder / "readings.jsonl").read_text(encoding="utf-8")
    assert "cables" not in readings and "fountain" not in readings
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    assert state["vocabulary"]["fountain"] == 1         # documented: word counts, no order, no messages


def test_damaged_state_is_set_aside_and_the_turn_still_reads(tmp_path):
    layer = ObservationLayer(tmp_path)
    settle(layer)
    path = layer.store.folder("person-a") / "state.json"
    path.write_text("{not json", encoding="utf-8")
    reading = layer.observe_turn(user_id="person-a", session_id="s1", turn_id="ty", source_id="sy", text="hello")
    assert reading["status"] == "warming_up"
    assert any("damaged" in p for p in reading["problems"])
    assert list(path.parent.glob("state.json.damaged-*"))


def test_a_torn_last_line_is_skipped(tmp_path):
    store = PersonStore(tmp_path)
    store.append("u", "readings", {"turn_id": "a"})
    with (store.folder("u") / "readings.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"turn_id": "b", "rea')
    assert [r["turn_id"] for r in store.read_stream("u", "readings")] == ["a"]


def test_streams_are_trimmed_to_the_newest_rows(tmp_path):
    layer = ObservationLayer(tmp_path, dials=replace(DEFAULT_DIALS, readings_kept=5))
    for i in range(12):
        layer.observe_turn(user_id="u", session_id="s", turn_id=f"t{i}", source_id="x", text="a plain short message")
    rows = layer.store.read_stream("u", "readings")
    assert 5 <= len(rows) <= 10 and rows[-1]["turn_id"] == "t11"
    assert layer.store.load_state("u")["stream_lines"]["readings"] == len(rows)


def test_forget_removes_everything_for_that_person_only(tmp_path):
    layer = ObservationLayer(tmp_path)
    settle(layer, user="a")
    settle(layer, user="b")
    assert layer.forget(user_id="a") is True
    assert not layer.store.folder("a").exists() and layer.store.folder("b").exists()
    assert layer.forget(user_id="a") is False


# ---- the live spine ----------------------------------------------------------------------------------

def test_spine_records_the_shadow_reading_and_keeps_it_out_of_the_prompt(tmp_path):
    from modules.pubpartner_core import PubPartnerSpine
    spine = PubPartnerSpine(tmp_path)
    turn = asyncio.run(spine.build_turn_packet(user_id="u", session_id="s", message="The lights look right today."))
    assert turn["eq_observation"]["influence"].startswith("none")
    assert "eq_observation" not in turn["llm_prompt_text"] and "inner state" not in turn["llm_prompt_text"]
    shared = asyncio.run(spine.build_turn_packet(user_id="u", session_id="s", message="Hello room.",
                                                 room_id="main_stage"))
    assert "eq_observation" not in shared              # shared rooms do not feed a private baseline


def test_spine_turn_survives_an_observation_failure(tmp_path, monkeypatch):
    from modules.pubpartner_core import PubPartnerSpine
    spine = PubPartnerSpine(tmp_path)

    def broken(**_):
        raise OSError("disk full")
    monkeypatch.setattr(spine.eq_observation, "observe_turn", broken)
    turn = asyncio.run(spine.build_turn_packet(user_id="u", session_id="s", message="Still here."))
    assert turn["ok"] is True and turn["eq_observation"]["status"] == "unavailable"
    assert "disk full" in turn["eq_observation"]["error"]


def test_spine_can_switch_the_layer_off(tmp_path):
    from modules.pubpartner_core import PubPartnerSpine
    spine = PubPartnerSpine(tmp_path, eq_observation_enabled=False)
    turn = asyncio.run(spine.build_turn_packet(user_id="u", session_id="s", message="Hello."))
    assert spine.eq_observation is None and "eq_observation" not in turn


def test_live_turn_records_reply_perception(tmp_path):
    from modules.pubpartner_core import PubPartnerSpine
    spine = PubPartnerSpine(tmp_path)
    result = asyncio.run(spine.run_turn(user_id="u", session_id="s", message="Can you list the cameras?",
                                        provider={"provider": "mock"}))
    assert result["eq_perception"]["influence"].startswith("none")
    assert result["eq_perception"]["prediction_id"]


# ---- routes --------------------------------------------------------------------------------------------

def test_routes_close_the_calibration_loop_and_stay_owner_scoped(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import pubpartner_app

    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    a, b = {"X-Client-Id": "owner-a"}, {"X-Client-Id": "owner-b"}
    with TestClient(pubpartner_app.app) as client:
        layer = pubpartner_app.app.state.pubpartner_spine.eq_observation \
            if getattr(pubpartner_app.app.state, "pubpartner_spine", None) is not None else None
        if layer is None:
            from modules.pubpartner_routes import get_spine
            layer = get_spine().eq_observation
        _gap_turn(layer, user="owner-a", turn="ta")

        assert client.post("/api/pubpartner/turns", headers=a,
                           json={"message": "hi", "behaviour": "fast"}).status_code == 400

        summary = client.get("/api/pubpartner/eq-observation/summary", headers=a).json()
        assert summary["status"] == "shadow" and summary["readings_kept"] == 11

        moments = client.get("/api/pubpartner/eq-observation/moments", headers=a).json()["moments"]
        assert [m["turn_id"] for m in moments] == ["ta"]
        assert client.get("/api/pubpartner/eq-observation/moments", headers=b).json()["moments"] == []

        body = {"turn_id": "ta", "answer": "something_was_going_on", "approved": True, "calm": False}
        assert client.post("/api/pubpartner/eq-observation/verdicts", headers=b, json=body).status_code == 404
        assert client.post("/api/pubpartner/eq-observation/verdicts", headers=a,
                           json={**body, "approved": False}).status_code == 400
        ok = client.post("/api/pubpartner/eq-observation/verdicts", headers=a, json=body)
        assert ok.status_code == 200 and ok.json()["trust"]["motor"] > DEFAULT_DIALS.neutral_reliability
        assert client.post("/api/pubpartner/eq-observation/verdicts", headers=a, json=body).status_code == 409

        p = layer.perceive_reply(user_id="owner-a", turn_id="ta", reply="I hear you.")
        fb = client.post("/api/pubpartner/eq-observation/perception-feedback", headers=a,
                         json={"prediction_id": p["prediction_id"], "observed_reads": ["came_across_cold"]})
        assert fb.status_code == 200
        assert client.post("/api/pubpartner/eq-observation/perception-feedback", headers=b,
                           json={"prediction_id": p["prediction_id"], "observed_reads": []}).status_code == 404

        assert client.post("/api/pubpartner/eq-observation/forget", headers=a, json={}).status_code == 400
        gone = client.post("/api/pubpartner/eq-observation/forget", headers=a, json={"confirm": "forget"})
        assert gone.json()["removed"] is True
        assert client.get("/api/pubpartner/eq-observation/summary", headers=a).json()["readings_kept"] == 0


# ---- the face rule (Josie, 2026-11-23) ------------------------------------------------------------
# "Faces count for performance and avatar reaction. Unless we are actually looking at somebody in a
# live camera, seeing their actual living face, then faces don't count. Unless it's an avatar
# impersonating a human, in which case that is an intentional performance ..."

FACE = {"expressivity": 0.4, "blink_rate": 0.3, "tic_rate": 0.1, "gaze_away_ratio": 0.2}


def test_a_live_camera_on_the_persons_own_face_counts_with_consent():
    values, statuses, problems = behaviour_features(
        {"consent": {"face": True}, "face": {"origin": "live_camera", "status": "observed", **FACE}})
    assert statuses["face"] == "observed" and values == FACE and problems == []


@pytest.mark.parametrize("origin,status", [("avatar", "performance"), ("rendered", "performance"),
                                           ("recording", "performance"), (None, "origin_unknown")])
def test_any_other_face_is_never_inner_state_evidence(origin, status):
    block = {"status": "observed", **FACE, **({"origin": origin} if origin else {})}
    values, statuses, problems = behaviour_features({"consent": {"face": True}, "face": block})
    assert values == {} and statuses["face"] == status and problems


def test_an_avatar_face_counts_fully_for_performance():
    from modules.eq_observation.features import performance_face
    values, origin = performance_face({"origin": "avatar", "expressivity": 0.1, "gaze_away_ratio": 0.7})
    assert origin == "avatar" and values == {"expressivity": 0.1, "gaze_away_ratio": 0.7}
    read = PerceptionReader(DEFAULT_DIALS).perceive_display(values, origin=origin)
    assert read["origin"] == "avatar" and read["expected_reads"] == ["looks_flat", "looks_disengaged"]


def test_an_avatar_face_never_reaches_the_persons_reading(tmp_path):
    layer = ObservationLayer(tmp_path)
    reading = layer.observe_turn(user_id="u", session_id="s", turn_id="t", source_id="x", text="hello there",
                                 behaviour={"consent": {"face": True}, "face": {"origin": "avatar", **FACE}})
    assert "face" not in reading["groups"] and reading["sources"]["face"] == "performance"
    assert "expressivity" not in reading["deviations"]
