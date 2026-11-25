"""The EQ reader must hand the card catalog readings it can match.

Before 2026-11-24 nearly every message came back with an unclear subject and a
flat 0.5 intensity, so the catalog fell back to one listening card every time.
"""
import pytest

from companion_support.eq_disambiguation_engine import ContextDisambiguator
from modules.wired.eq_card_selector import ContextAwareCardSelector

CASES = [
    ("I got the part!", "achievement", "celebrate_achievement"),
    ("we nailed it", "achievement", "celebrate_achievement"),
    ("I hit the target", "achievement", "celebrate_achievement"),
    ("I took a shot and scored", "achievement", "celebrate_achievement"),
    ("my dog died", "loss", "loss_validation"),
    ("I lost my mother", "loss", "loss_validation"),
    ("my best friend lied to me", "betrayal", "betrayal_"),
    ("I am so burned out", "fatigue", "fatigue_"),
    ("I feel trapped", "autonomy", "autonomy_reflection"),
    ("I feel so guilty", "identity", "identity_exploration"),
    ("he hit me", "violence", "trauma_"),
    ("I was shot", "violence", "trauma_"),
]


@pytest.mark.parametrize("message,context,card_prefix", CASES)
def test_reader_reaches_the_right_cards(message, context, card_prefix):
    result = ContextDisambiguator().analyze(message, "t", include_history=False)
    assert result.primary_context.value == context
    picks = [c.id for c, _ in ContextAwareCardSelector().select_response(result, 3)]
    assert picks and picks[0].startswith(card_prefix), picks


def test_lost_keys_is_not_grief():
    result = ContextDisambiguator().analyze("I lost my keys", "t", include_history=False)
    assert result.primary_context.value != "loss"


def test_it_inside_hit_is_not_a_subject():
    result = ContextDisambiguator().analyze("he hit me", "t", include_history=False)
    assert result.subject_role.value == "self"
