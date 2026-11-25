import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules"))

from behavior_animation_engine import (  # noqa: E402
    BehaviorAnimationSelector,
    BehaviorState,
    BehaviorIntent,
    AnimationConflictResolver,
    AnimationSuppressionGate,
    BodyLayer,
    demo_sequence,
)
from animation_presets_complete import get_animation  # noqa: E402


def test_demo_sequence_emits_decisions():
    seq = demo_sequence(seed=123)
    assert len(seq) == 6
    assert all("intent" in row for row in seq)
    assert any(row["animation_id"] for row in seq)


def test_exact_repeat_is_suppressed():
    gate = AnimationSuppressionGate(minimum_gap_ms=0, repeat_gap_ms=3000)
    state = BehaviorState("a")
    preset = get_animation("nod_slow")
    gate.note_played(preset, state, now_ms=1000)
    suppressed, reason = gate.should_suppress(preset, state, now_ms=2000)
    assert suppressed
    assert "repeat" in reason


def test_listener_does_not_steal_focus_with_large_gesture():
    gate = AnimationSuppressionGate(minimum_gap_ms=0)
    state = BehaviorState("listener", intent=BehaviorIntent.LISTENING, energy_level=0.3)
    preset = get_animation("open_palm_presentation")
    suppressed, reason = gate.should_suppress(preset, state, now_ms=5000)
    assert suppressed
    assert "listener" in reason


def test_conflict_resolver_blocks_same_layer_overlap():
    resolver = AnimationConflictResolver()
    state = BehaviorState("a")
    first = get_animation("nod_slow")
    second = get_animation("head_shake")
    resolver.activate(first, state, now_ms=0, locked=False)
    conflict, reason = resolver.conflicts(second, state, now_ms=100)
    assert conflict
    assert "layer" in reason or "conflict" in reason


def test_selector_respects_seated_context():
    selector = BehaviorAnimationSelector(rng=__import__("random").Random(4))
    state = BehaviorState("a", is_seated=True, intent=BehaviorIntent.THINKING, engagement=0.6)
    decision = selector.decide(state, now_ms=10_000)
    assert decision.animation_id is not None
    assert decision.layer in set(BodyLayer)


def test_cooldown_after_play():
    selector = BehaviorAnimationSelector(rng=__import__("random").Random(2))
    state = BehaviorState("a", intent=BehaviorIntent.GREETING)
    first = selector.decide(state, now_ms=10_000)
    second = selector.decide(state, now_ms=10_050)
    assert first.animation_id is not None
    assert second.suppressed
