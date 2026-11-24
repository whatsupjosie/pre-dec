"""Sir Purfluous's cue cards: one deck for both modes (offline lines, online cues)."""
import json
from pathlib import Path

from modules import purfluous_cue_cards as cc
from modules.sir_purfluous_runtime import respond

DECK = json.loads(Path("data/characters/sir_purfluous.json").read_text(encoding="utf-8"))["cue_cards"]


def test_deck_lives_in_his_character_file_and_is_marked_draft():
    assert DECK["status"] == "draft_for_josie_to_edit"
    ids = [c["id"] for c in DECK["cards"]]
    assert len(ids) == len(set(ids)) and len(ids) > 80


def test_josie_lines_are_verbatim():
    texts = [c["text"] for c in DECK["cards"]]
    assert "You'll never know just when or where, but it shall strike. The tiny chair." in texts


def test_composes_from_topic_cards():
    out = respond("is that chair safe to sit in?")
    chair_lines = [cc._fill(c["text"], DECK["slots"], sancho=False) for c in DECK["cards"] if "chair" in c["topics"]]
    assert any(line in out for line in chair_lines), out


def test_scottish_play_ritual():
    assert "scottish play" in respond("Break a leg in Macbeth tonight").lower() or "spit" in respond("Break a leg in Macbeth tonight").lower()


def test_deterministic_but_varies_with_history():
    a = cc.compose("tell me about the ghost")
    assert a == cc.compose("tell me about the ghost")
    seen = {a}
    hist = []
    for _ in range(5):
        line = cc.compose("tell me about the ghost", hist)
        seen.add(line)
        hist.append({"speaker": "Sir Purfluous", "text": line})
    assert len(seen) >= 3


def test_hurt_gets_one_plain_card_no_jokes_no_services():
    topics, mood = cc.read("my dog died last week and I can't stop crying")
    assert mood == "hurt"
    picked = cc.select("my dog died last week and I can't stop crying")
    assert len(picked["cards"]) == 1 and picked["cards"][0]["kind"] == "plain"
    out = respond("my dog died last week and I can't stop crying").lower()
    for banned in ("hotline", "therapist", "counsel", "services", "are you safe"):
        assert banned not in out


def test_unknown_still_honest():
    assert "will not invent" in respond("what is the capital of Mongolia").lower()
    assert cc.compose("what is the capital of Mongolia") is None


def test_online_cue_is_private_note():
    cue = cc.cues_for("nice suit")
    assert cue.startswith("Cue cards (private")
    assert cc.cues_for("what is the capital of Mongolia") is None


def test_no_card_slots_left_unfilled():
    for c in DECK["cards"]:
        assert "{" not in cc._fill(c["text"], DECK["slots"])


def test_he_draws_on_the_eq_card_catalog():
    from modules.wired.eq_card_selector import CardLibrary
    catalog_texts = {c.text for c in CardLibrary().cards.values()}
    assert cc.compose("I am so burned out") in catalog_texts
    assert cc.compose("my best friend lied to me") in catalog_texts


def test_crisis_resource_cards_are_never_his():
    for msg in ("he hit me", "I was shot", "my dad died", "I can't do this anymore", "I lost my mother"):
        _ctx, cards = cc._catalog_read(msg)
        assert all("crisis" not in c["id"] and "trauma_safety" not in c["id"] and "resources" not in c["id"] for c in cards)
        out = respond(msg)
        for banned in ("988", "RAINN", "safe right now", "Lifeline"):
            assert banned not in out, (msg, out)


def test_sancho_is_rationed():
    hist, said = [], []
    for msg in ["hello", "nice suit", "what are you drinking", "is Horace around?", "tell me about the ghost",
                "where's Pints?", "we nailed the take!", "I love old movies", "how do I act for camera?", "goodnight"]:
        out = respond(msg, hist)
        said.append("Sancho" in out)
        hist += [{"speaker": "You", "text": msg}, {"speaker": "Sir Purfluous", "text": out}]
    assert sum(said) <= 2, said
    assert all(out.count("Sancho") <= 1 for out in (h["text"] for h in hist if h["speaker"] == "Sir Purfluous"))


def test_grief_comes_before_studio_pets():
    out = respond("my dog died last week")
    assert "Pints" not in out and "Stage Door Joe" not in out


def test_macbeth_with_an_exclamation_is_still_the_scottish_play():
    out = respond("Break a leg in Macbeth tonight!").lower()
    assert "scottish play" in out or "spit" in out


def test_josies_speech_keeps_its_sancho():
    from modules.sir_purfluous_character_profile import MONOLOGUE_POOL
    speech = next(m.text for m in MONOLOGUE_POOL if m.monologue_id == "m60_imagination")
    assert speech.startswith("But you see, Sancho")


def test_pubcast_cards_are_marked_for_josie_to_check():
    pc = [c for c in DECK["cards"] if "pubcast_how" in c["topics"]]
    assert pc and all(c.get("verify") for c in pc)


def test_unclothed_years_answer_when_raised():
    from modules.purfluous_cue_cards import reload
    reload()
    texts = {cc._fill(c["text"], DECK["slots"], sancho=False) for c in DECK["cards"] if "the_unclothed_years" in c["topics"]}
    for msg in ("so you used to make porn?", "what was it like directing adult movies?", "were the x-rated films hard to light?"):
        out = respond(msg)
        assert any(t in out for t in texts), (msg, out)


def test_unclothed_years_never_come_up_unasked():
    for msg in ("tell me about the old days", "I love old movies", "how should I light this scene", "hello"):
        out = respond(msg)
        assert "tea break" not in out and "unclothed" not in out.lower()


def test_josies_bosom_line_is_verbatim_and_stands_alone():
    card = next(c for c in DECK["cards"] if c.get("author") == "Josie" and "the_unclothed_years" in c["topics"])
    assert card["text"] == ("So I said, madam, if you can't get your bosom out of the way, then I don't know how "
                            "I'm ever going to be able to shoot your face. Well, she didn't take kindly to that.")
    assert card.get("solo") is True


def test_pete_always_shuts_him_down_before_a_story_is_told():
    from modules.purfluous_cue_cards import reload
    reload()
    data = json.loads(Path("data/characters/sir_purfluous.json").read_text(encoding="utf-8"))["cue_cards"]
    shush = [c for c in data["cards"] if c["id"].startswith("pete_shush_")]
    assert len(shush) >= 6
    for c in shush:
        assert c.get("solo") is True and "(Pete" in c["text"]
        assert "movie" not in c["text"].lower()   # she never jokes about the movie, and neither does he


def test_every_frame_and_filler_makes_a_whole_sentence():
    import itertools
    kit = json.loads(Path("data/characters/sir_purfluous.json").read_text(encoding="utf-8"))["cue_cards"]["phrase_kit"]
    lines = set()
    for topic, g in kit["fillers"].items():
        assert not any(" my " in f" {x} " for x in g["doing"]), topic   # "doing" must fit any frame
        for f in kit["frames"]:
            for th, q, do in itertools.product(g["thing"], g["quality"], g["doing"]):
                t = (f["text"].replace("{Thing}", th[:1].upper() + th[1:]).replace("{thing}", th)
                     .replace("{quality}", q).replace("{doing}", do))
                assert "{" not in t and t[:1].isupper() and t.rstrip()[-1] in ".?!", t
                lines.add(t)
    assert len(lines) > 1400   # 1,491 distinct sentences at the time of writing


def test_frames_add_new_lines_to_a_topic_he_has_covered():
    from modules.purfluous_cue_cards import reload
    reload()
    hist, seen = [], set()
    for _ in range(12):
        out = respond("I love old movies", hist)
        seen.add(out)
        hist += [{"speaker": "You", "text": "I love old movies"}, {"speaker": "Sir Purfluous", "text": out}]
    assert len(seen) >= 10


def test_people_carry_their_own_grammar():
    import hashlib
    from modules.purfluous_cue_cards import reload, _story_line, _load
    reload()
    kit = _load()["kit"]
    for i in range(400):
        line = _story_line(kit, hashlib.sha256(str(i).encode()).digest(), "", continuing=True)["text"]
        assert "{" not in line
        assert "they was" not in line.lower() and "crew was" not in line.lower()
        assert "he were" not in line.lower() and "she were" not in line.lower()


def test_a_fresh_story_never_starts_with_a_bare_pronoun():
    import hashlib
    from modules.purfluous_cue_cards import _story_line, _load
    kit = _load()["kit"]
    for i in range(300):
        line = _story_line(kit, hashlib.sha256(str(i).encode()).digest(), "")["text"]
        names = [p["who"].lower() for p in kit["people"] if p["who"] not in ("he", "she", "they")]
        assert any(n in line.lower() for n in names), line          # the subject is named
        assert line.split()[0].lower() not in ("he", "she", "they"), line
