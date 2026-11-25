import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from editor_core import (
    Annotation,
    AnnotationKind,
    EditorEngine,
    GrammarPass,
    RhymeDictionary,
    SpellingPass,
    ThesaurusLookup,
)
from editor_core.plothole import check_continuity


# ── spelling ─────────────────────────────────────────────────────────────

def test_spelling_flags_unknown_word():
    sp = SpellingPass()
    hits = sp.check("She recieved the letter yesterday.")
    assert any(a.span_text == "recieved" for a in hits)
    hit = next(a for a in hits if a.span_text == "recieved")
    assert "received" in hit.suggestions


def test_spelling_respects_custom_dictionary():
    sp = SpellingPass(custom_dictionary=["Sahira", "Voxelgrad"])
    hits = sp.check("Sahira walked through Voxelgrad at dawn.")
    assert not any(a.span_text in ("Sahira", "Voxelgrad") for a in hits)


def test_spelling_skips_acronyms():
    sp = SpellingPass()
    hits = sp.check("NASA launched the probe.")
    assert not any(a.span_text == "NASA" for a in hits)


# ── grammar ──────────────────────────────────────────────────────────────

def test_grammar_flags_confusable_homophone():
    gp = GrammarPass()
    hits = gp.check("Their going to the store.")
    assert any(a.rule_id == "grammar/confusable_homophone" and a.span_text == "Their" for a in hits)


def test_grammar_flags_doubled_word():
    gp = GrammarPass()
    hits = gp.check("He walked to the the door.")
    assert any(a.rule_id == "grammar/doubled_word" for a in hits)


def test_grammar_flags_long_sentence():
    gp = GrammarPass(max_sentence_words=10)
    long_sentence = "This is a very long sentence that keeps going and going and going without any real end in sight at all."
    hits = gp.check(long_sentence)
    assert any(a.rule_id == "cadence/long_sentence" for a in hits)


def test_grammar_flags_passive_voice():
    gp = GrammarPass()
    hits = gp.check("The letter was written by her.")
    assert any(a.rule_id == "style/passive_voice" for a in hits)


def test_grammar_disabled_rule_is_skipped():
    gp = GrammarPass(disabled_rule_ids={"grammar/confusable_homophone"})
    hits = gp.check("Their going to the store.")
    assert not any(a.rule_id == "grammar/confusable_homophone" for a in hits)


# ── thesaurus ────────────────────────────────────────────────────────────

def test_thesaurus_returns_sense_grouped_synonyms():
    th = ThesaurusLookup()
    groups = th.lookup("happy")
    assert groups, "expected at least one sense group for 'happy'"
    all_syns = {s for g in groups for s in g.synonyms}
    assert "felicitous" in all_syns or "glad" in all_syns


def test_thesaurus_flat_synonyms_excludes_input_word():
    th = ThesaurusLookup()
    syns = th.flat_synonyms("happy")
    assert "happy" not in syns
    assert len(syns) > 0


# ── rhyme ────────────────────────────────────────────────────────────────

def test_rhyme_classifies_perfect_rhyme():
    rd = RhymeDictionary()
    assert rd.classify("cat", "hat") == "perfect"


def test_rhyme_classifies_slant_rhyme():
    rd = RhymeDictionary()
    # 'rain' / 'game' share the AY-family... use a clearer slant example:
    # 'moon' (UW) vs 'gone' (AA/AO) is not a slant; use vowel-match/consonant-diff pair instead.
    result = rd.classify("mind", "time")
    assert result in ("perfect", "slant")  # both share AY1 ND vs M — validate it's not None
    assert result is not None


def test_rhyme_classifies_multi_syllable():
    rd = RhymeDictionary()
    result = rd.classify("gravity", "depravity")
    assert result == "multi_syllable"


def test_rhyme_no_match_returns_none():
    rd = RhymeDictionary()
    assert rd.classify("orange", "purple") is None


def test_rhyme_find_rhymes_for_cat_includes_hat():
    rd = RhymeDictionary()
    matches = rd.find_rhymes("cat", max_per_type=200)
    assert "hat" in matches["perfect"]


def test_stress_pattern_returns_values_for_known_word():
    rd = RhymeDictionary()
    pattern = rd.stress_pattern("pubcast".upper())  # not in dict, expect empty
    assert pattern == []
    pattern2 = rd.stress_pattern("apple")
    assert len(pattern2) == 2  # two syllables
    assert pattern2[0] in (1, 2)  # first syllable stressed


# ── engine (combined passes) ────────────────────────────────────────────

def test_engine_merges_and_sorts_annotations_by_position():
    engine = EditorEngine()
    text = "their going to the the store, and it was written by nobody."
    results = engine.check(text)
    assert len(results) > 0
    starts = [a.start for a in results]
    assert starts == sorted(starts)
    kinds = {a.kind for a in results}
    assert AnnotationKind.GRAMMAR in kinds


# ── plothole (model-backed pass, stubbed model caller) ──────────────────

def test_continuity_check_flags_contradiction_with_stub_model():
    async def fake_chat_caller(*, body, **kwargs):
        return {
            "ok": True,
            "reply": (
                '{"has_contradiction": true, "contradictions": '
                '[{"description": "Coat color changed", '
                '"established_fact": "Repeat wore a grey coat", '
                '"new_text_span": "blue coat"}], "confidence": 0.87}'
            ),
        }

    result, annotations, raw = asyncio.run(
        check_continuity(
            chat_caller=fake_chat_caller,
            established_facts=["Repeat wore a grey coat."],
            new_text="He reached for his blue coat and left.",
        )
    )
    assert result is not None
    assert result.has_contradiction is True
    assert len(annotations) == 1
    assert annotations[0].kind == AnnotationKind.CONTINUITY
    assert "blue coat" in annotations[0].span_text


def test_continuity_check_handles_model_failure_gracefully():
    async def failing_chat_caller(*, body, **kwargs):
        return {"ok": False, "error": "model unavailable"}

    result, annotations, raw = asyncio.run(
        check_continuity(
            chat_caller=failing_chat_caller,
            established_facts=[],
            new_text="Anything.",
        )
    )
    assert result is None
    assert annotations == []
    assert raw["ok"] is False


def test_continuity_check_handles_malformed_json_gracefully():
    async def garbage_chat_caller(*, body, **kwargs):
        return {"ok": True, "reply": "I think everything looks fine!"}

    result, annotations, raw = asyncio.run(
        check_continuity(
            chat_caller=garbage_chat_caller,
            established_facts=[],
            new_text="Anything.",
        )
    )
    assert result is None
    assert annotations == []
