"""Context disambiguation fixes (companion_support/eq_disambiguation_engine.py), used live by the
companion advisory. Three fixes ported from recovery/2026-11-23/donors/eq_disambiguation_fixed_breaking_dawn
(neutral intensity, explicit-only crisis wording, "hit my goal" is not violence) and one new fix
(mislaid objects are not a loss). Synthetic messages only.
Run: pytest -q tests/test_eq_disambiguation_fixes.py
"""
from __future__ import annotations

import pytest

from companion_support.eq_disambiguation_engine import ContextDisambiguator, EmotionContext


def contexts(message):
    return ContextDisambiguator()._identify_context(message)


def intensity(message):
    return ContextDisambiguator()._estimate_intensity(message)


@pytest.mark.parametrize("message", ["I lost my keys again", "I lost my phone on the bus", "lost my train of thought"])
def test_a_mislaid_object_is_not_a_loss(message):
    assert EmotionContext.LOSS not in contexts(message)


@pytest.mark.parametrize("message", ["I lost my mother last month", "We lost our dog yesterday",
                                     "I lost my job today", "my grandfather passed away",
                                     "I lost my best friend"])
def test_a_real_loss_is_still_a_loss(message):
    assert EmotionContext.LOSS in contexts(message)


def test_hitting_a_goal_is_achievement_not_violence():
    found = contexts("I hit my goal for the quarter")
    assert EmotionContext.ACHIEVEMENT in found and EmotionContext.VIOLENCE not in found
    assert EmotionContext.VIOLENCE in contexts("he hit me last night")


@pytest.mark.parametrize("message", ["I give up trying to parallel park", "let's end it here for tonight",
                                     "I'm dying of laughter"])
def test_everyday_phrases_are_not_crisis(message):
    assert intensity(message) < 0.9


@pytest.mark.parametrize("message", ["I want to kill myself", "I can't go on", "I want to end it all"])
def test_explicit_crisis_wording_is_still_crisis(message):
    assert intensity(message) == 1.0


def test_neutral_text_is_neutral_not_moderate():
    assert intensity("Hi there, the camera list is attached") == pytest.approx(0.05)
    assert intensity("Hi there") < intensity("I'm fine") < intensity("I'm frustrated")


def test_the_live_analysis_path_runs_end_to_end():
    result = ContextDisambiguator().analyze(message="I lost my keys again", user_id="u")
    assert result.primary_context != EmotionContext.LOSS
    assert result.recommended_response_style != "crisis_support"
