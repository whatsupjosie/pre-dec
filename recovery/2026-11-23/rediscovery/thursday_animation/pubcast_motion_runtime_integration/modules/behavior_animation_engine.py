"""
PubCast Behavior Animation Engine
=================================
Turns semantic conversational state into layered, conflict-aware avatar animation.

This module is deliberately NOT a replacement for animation_presets_complete.py.
It sits above the preset library and decides what should play, when it should be
suppressed, and which body layer owns which bones.

Core idea:
    animation presets are vocabulary tokens;
    behavior state is the sentence being performed.

Designed for PubCast avatar presence:
- active listening without twitchy overanimation
- speech gestures that respect cooldowns and repetition memory
- emotional overlays as soft posture color, not canned emotes
- seated/standing context awareness
- layer priority and bone conflict checks
- deterministic testing through injectable random seed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import math
import random
import time

try:  # Drop-in when copied beside animation_presets_complete.py or animation_presets.py
    from animation_presets_complete import (
        ANIMATION_LIBRARY,
        AnimationPreset,
        AnimationCategory,
        get_animation,
        get_animations_for_context,
        get_animations_by_tag,
    )
except Exception:  # pragma: no cover - allows host app to inject library later
    ANIMATION_LIBRARY = {}
    AnimationPreset = Any  # type: ignore
    AnimationCategory = Any  # type: ignore
    get_animation = None  # type: ignore
    get_animations_for_context = None  # type: ignore
    get_animations_by_tag = None  # type: ignore


class BehaviorIntent(str, Enum):
    """Semantic intent from dialogue/camera/host logic."""
    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"
    THINKING = "thinking"
    SKEPTICAL = "skeptical"
    CONFIDENT = "confident"
    RELAXED = "relaxed"
    ENTHUSIASTIC = "enthusiastic"
    GREETING = "greeting"
    DIRECTING_ATTENTION = "directing_attention"


class BodyLayer(IntEnum):
    """Higher number wins unless an active layer is locked."""
    BASE_POSTURE = 10
    EMOTION_OVERLAY = 20
    TORSO = 30
    HEAD = 40
    GAZE = 45
    HANDS = 50
    FIDGET = 55
    SPEECH_GESTURE = 60
    SCRIPTED = 80
    SAFETY_OVERRIDE = 100


# Broad bone ownership groups. This keeps the resolver useful even before the
# final skeleton map is complete. Specific host projects may expand this map.
BONE_GROUPS: Dict[str, Set[str]] = {
    "head": {"head", "neck", "eye_left", "eye_right"},
    "torso": {"spine", "spine_1", "spine_2", "chest", "pelvis"},
    "left_arm": {"shoulder_left", "arm_left", "forearm_left", "hand_left"},
    "right_arm": {"shoulder_right", "arm_right", "forearm_right", "hand_right"},
    "hands": {"hand_left", "hand_right", "arm_left", "arm_right", "forearm_left", "forearm_right"},
    "legs": {"leg_left", "leg_right", "knee_left", "knee_right", "foot_left", "foot_right", "pelvis"},
}

ANIMATION_LAYER_HINTS: Dict[str, BodyLayer] = {
    # emotional/posture overlays
    "confident_stance": BodyLayer.EMOTION_OVERLAY,
    "thoughtful_idle": BodyLayer.EMOTION_OVERLAY,
    "skeptical_expression": BodyLayer.EMOTION_OVERLAY,
    "enthusiasm_bounce": BodyLayer.EMOTION_OVERLAY,
    "relaxed_idle": BodyLayer.EMOTION_OVERLAY,
    # listening/head/torso
    "nod_slow": BodyLayer.HEAD,
    "nod_emphatic": BodyLayer.HEAD,
    "head_shake": BodyLayer.HEAD,
    "head_tilt_left": BodyLayer.HEAD,
    "head_tilt_right": BodyLayer.HEAD,
    "lean_forward": BodyLayer.TORSO,
    "lean_back": BodyLayer.TORSO,
    "weight_shift_left": BodyLayer.TORSO,
    "weight_shift_right": BodyLayer.TORSO,
    # gestures/fidgets
    "open_palm_presentation": BodyLayer.SPEECH_GESTURE,
    "pointing_gesture": BodyLayer.SPEECH_GESTURE,
    "hand_wave": BodyLayer.SPEECH_GESTURE,
    "shoulder_shrug": BodyLayer.SPEECH_GESTURE,
    "hand_to_chin": BodyLayer.HANDS,
    "hands_on_hips": BodyLayer.HANDS,
    "hands_cross_chest": BodyLayer.HANDS,
    "hands_together_chest": BodyLayer.HANDS,
    "adjust_collar": BodyLayer.FIDGET,
    "smooth_hair": BodyLayer.FIDGET,
    "clasp_hands_relax": BodyLayer.FIDGET,
    "finger_tap": BodyLayer.FIDGET,
    "glance_down": BodyLayer.HEAD,
    "touch_face": BodyLayer.FIDGET,
    "adjust_seat": BodyLayer.FIDGET,
}

INTENT_CONTEXTS: Dict[BehaviorIntent, Tuple[str, ...]] = {
    BehaviorIntent.IDLE: ("standing",),
    BehaviorIntent.LISTENING: ("listening",),
    BehaviorIntent.SPEAKING: ("speaking",),
    BehaviorIntent.THINKING: ("thinking",),
    BehaviorIntent.SKEPTICAL: ("listening", "thinking"),
    BehaviorIntent.CONFIDENT: ("speaking", "standing"),
    BehaviorIntent.RELAXED: ("standing", "seated"),
    BehaviorIntent.ENTHUSIASTIC: ("speaking",),
    BehaviorIntent.GREETING: ("speaking",),
    BehaviorIntent.DIRECTING_ATTENTION: ("speaking",),
}

INTENT_TAG_WEIGHTS: Dict[BehaviorIntent, Dict[str, float]] = {
    BehaviorIntent.LISTENING: {"listening": 2.0, "agreement": 1.2, "engagement": 1.1, "natural": 0.7},
    BehaviorIntent.SPEAKING: {"gesture": 2.0, "presentation": 1.6, "emphasis": 1.4, "direction": 1.0},
    BehaviorIntent.THINKING: {"thinking": 2.0, "pondering": 1.7, "fidget": 0.8, "thoughtful": 1.4},
    BehaviorIntent.SKEPTICAL: {"skepticism": 2.2, "disagreement": 1.6, "defensive": 1.1},
    BehaviorIntent.CONFIDENT: {"confident": 2.0, "assertive": 1.3, "presentation": 0.8},
    BehaviorIntent.RELAXED: {"relaxed": 2.0, "calm": 1.0, "natural": 0.8},
    BehaviorIntent.ENTHUSIASTIC: {"enthusiastic": 2.0, "gesture": 1.1, "friendly": 0.8},
    BehaviorIntent.GREETING: {"greeting": 3.0, "friendly": 2.0},
    BehaviorIntent.DIRECTING_ATTENTION: {"direction": 3.0, "reference": 1.5, "emphasis": 1.0},
    BehaviorIntent.IDLE: {"natural": 1.0, "presence": 0.8, "relaxed": 0.7},
}

INTENT_ANIMATION_BONUSES: Dict[BehaviorIntent, Dict[str, float]] = {
    BehaviorIntent.SKEPTICAL: {"head_shake": 1.5, "lean_back": 1.0, "skeptical_expression": 1.3, "hands_cross_chest": 0.9},
    BehaviorIntent.THINKING: {"hand_to_chin": 1.4, "glance_down": 1.1, "thoughtful_idle": 1.5, "touch_face": 0.6},
    BehaviorIntent.CONFIDENT: {"confident_stance": 1.6, "hands_on_hips": 1.2, "open_palm_presentation": 0.6},
    BehaviorIntent.RELAXED: {"relaxed_idle": 1.6, "clasp_hands_relax": 0.8, "lean_back": 0.5},
    BehaviorIntent.ENTHUSIASTIC: {"enthusiasm_bounce": 1.5, "open_palm_presentation": 1.1, "nod_emphatic": 0.8},
    BehaviorIntent.GREETING: {"hand_wave": 4.0},
    BehaviorIntent.DIRECTING_ATTENTION: {"pointing_gesture": 3.0, "open_palm_presentation": 1.2},
}


@dataclass
class ActiveLayer:
    animation_id: str
    layer: BodyLayer
    started_at_ms: int
    until_ms: int
    bones: Set[str]
    locked: bool = False


@dataclass
class AnimationDecision:
    animation_id: Optional[str]
    layer: Optional[BodyLayer]
    reason: str
    score: float = 0.0
    suppressed: bool = False
    alternatives: List[Tuple[str, float]] = field(default_factory=list)

    def should_play(self) -> bool:
        return self.animation_id is not None and not self.suppressed


@dataclass
class BehaviorState:
    """Per-avatar rolling state. Persist this between frames/ticks."""
    avatar_id: str
    is_seated: bool = False
    intent: BehaviorIntent = BehaviorIntent.IDLE
    energy_level: float = 0.45
    social_confidence: float = 0.50
    attention_focus: Optional[str] = None
    engagement: float = 0.50
    dominance: float = 0.35
    interruption_pressure: float = 0.0
    fatigue: float = 0.10
    stillness_bias: float = 0.35
    last_animation_id: Optional[str] = None
    last_animation_at_ms: int = -10_000
    last_intent: BehaviorIntent = BehaviorIntent.IDLE
    repeated_family_count: int = 0
    rhythm_memory: Dict[str, float] = field(default_factory=dict)
    cooldowns: Dict[str, int] = field(default_factory=dict)  # animation_id -> next allowed ms
    active_layers: Dict[BodyLayer, ActiveLayer] = field(default_factory=dict)
    recent_tags: List[str] = field(default_factory=list)
    held_pose_until_ms: int = 0

    def clamp(self) -> None:
        for name in ("energy_level", "social_confidence", "engagement", "dominance", "interruption_pressure", "fatigue", "stillness_bias"):
            value = getattr(self, name)
            setattr(self, name, max(0.0, min(1.0, float(value))))

    def update_intent(self, intent: BehaviorIntent) -> None:
        if intent != self.intent:
            self.last_intent = self.intent
            self.intent = intent
            self.repeated_family_count = 0

    def decay(self, elapsed_ms: int) -> None:
        """Slowly settle volatile behavior values."""
        if elapsed_ms <= 0:
            return
        factor = min(1.0, elapsed_ms / 10_000.0)
        self.interruption_pressure *= (1.0 - 0.5 * factor)
        self.fatigue = min(1.0, self.fatigue + 0.015 * factor)
        self.energy_level = max(0.0, min(1.0, self.energy_level - 0.01 * factor + self.engagement * 0.005 * factor))
        self.clamp()


class AnimationConflictResolver:
    """Resolves layer/bone ownership conflicts before an animation is emitted."""

    def __init__(self, layer_hints: Optional[Mapping[str, BodyLayer]] = None) -> None:
        self.layer_hints = dict(ANIMATION_LAYER_HINTS)
        if layer_hints:
            self.layer_hints.update(layer_hints)

    def infer_layer(self, preset: AnimationPreset) -> BodyLayer:
        anim_id = getattr(preset, "animation_id", "")
        if anim_id in self.layer_hints:
            return self.layer_hints[anim_id]
        tags = set(getattr(preset, "tags", set()) or set())
        category = getattr(getattr(preset, "category", None), "value", getattr(preset, "category", ""))
        if "fidget" in tags or category == "fidget":
            return BodyLayer.FIDGET
        if "gesture" in tags or category == "gesture":
            return BodyLayer.SPEECH_GESTURE
        if "listening" in tags:
            return BodyLayer.HEAD
        if category == "emotional":
            return BodyLayer.EMOTION_OVERLAY
        return BodyLayer.TORSO

    def affected_bones(self, preset: AnimationPreset) -> Set[str]:
        bones: Set[str] = set()
        for frame in getattr(preset, "frames", []) or []:
            bone_id = getattr(frame, "bone_id", None) or getattr(frame, "boneId", None)
            if bone_id:
                bones.add(str(bone_id))
        return bones

    def conflicts(self, preset: AnimationPreset, state: BehaviorState, now_ms: int) -> Tuple[bool, str]:
        new_layer = self.infer_layer(preset)
        new_bones = self.affected_bones(preset)
        expired = [layer for layer, active in state.active_layers.items() if active.until_ms <= now_ms]
        for layer in expired:
            state.active_layers.pop(layer, None)

        for layer, active in state.active_layers.items():
            if active.until_ms <= now_ms:
                continue
            bone_overlap = bool(new_bones & active.bones)
            same_layer = layer == new_layer
            lower_priority = new_layer < active.layer
            if active.locked and (bone_overlap or same_layer):
                return True, f"blocked by locked {active.animation_id} on {active.layer.name}"
            if bone_overlap and lower_priority:
                return True, f"bone conflict with higher-priority {active.animation_id}"
            if same_layer and getattr(preset, "animation_id", "") != active.animation_id:
                if new_layer <= active.layer:
                    return True, f"layer {new_layer.name} already occupied by {active.animation_id}"
        return False, "no conflict"

    def activate(self, preset: AnimationPreset, state: BehaviorState, now_ms: int, locked: bool = False) -> ActiveLayer:
        layer = self.infer_layer(preset)
        bones = self.affected_bones(preset)
        duration = int(getattr(preset, "duration_ms", 800) or 800)
        active = ActiveLayer(
            animation_id=getattr(preset, "animation_id", "unknown"),
            layer=layer,
            started_at_ms=now_ms,
            until_ms=now_ms + max(100, duration),
            bones=bones,
            locked=locked or bool(getattr(preset, "is_blocking", False)),
        )
        state.active_layers[layer] = active
        return active


class AnimationSuppressionGate:
    """Prevents uncanny twitchiness, repeats, and meaningless motion spam."""

    def __init__(self, minimum_gap_ms: int = 450, repeat_gap_ms: int = 2400) -> None:
        self.minimum_gap_ms = minimum_gap_ms
        self.repeat_gap_ms = repeat_gap_ms

    def should_suppress(self, preset: AnimationPreset, state: BehaviorState, now_ms: int) -> Tuple[bool, str]:
        anim_id = getattr(preset, "animation_id", "")
        state.clamp()
        if now_ms < state.held_pose_until_ms:
            return True, "pose hold is intentionally suppressing new motion"
        if now_ms - state.last_animation_at_ms < self.minimum_gap_ms:
            return True, "minimum animation gap not met"
        if anim_id == state.last_animation_id and now_ms - state.last_animation_at_ms < self.repeat_gap_ms:
            return True, "exact repeat suppressed"
        if now_ms < state.cooldowns.get(anim_id, -1):
            return True, f"{anim_id} is cooling down"

        tags = set(getattr(preset, "tags", set()) or set())
        is_fidget = "fidget" in tags or getattr(getattr(preset, "category", None), "value", "") == "fidget"
        is_big_gesture = "gesture" in tags or "presentation" in tags or "direction" in tags

        if state.intent == BehaviorIntent.LISTENING and is_big_gesture and state.energy_level < 0.75:
            return True, "listener should not steal focus with a big gesture"
        if state.fatigue > 0.78 and is_fidget:
            # tired people fidget less in this vocabulary; they settle/hold instead
            return True, "fatigue prefers stillness over fidget"
        if state.stillness_bias > 0.65 and is_fidget and state.energy_level < 0.55:
            return True, "stillness bias suppresses filler fidget"
        return False, "allowed"

    def note_played(self, preset: AnimationPreset, state: BehaviorState, now_ms: int) -> None:
        anim_id = getattr(preset, "animation_id", "")
        duration = int(getattr(preset, "duration_ms", 800) or 800)
        tags = list(getattr(preset, "tags", set()) or [])
        state.last_animation_id = anim_id
        state.last_animation_at_ms = now_ms
        state.recent_tags = (state.recent_tags + tags)[-12:]
        base_cooldown = max(900, int(duration * 1.35))
        if anim_id.startswith("nod"):
            base_cooldown = max(base_cooldown, 1400)
        if "gesture" in tags or "presentation" in tags:
            base_cooldown = max(base_cooldown, 1800)
        if "fidget" in tags:
            base_cooldown = max(base_cooldown, 2600)
        state.cooldowns[anim_id] = now_ms + base_cooldown
        # Introduce intentional quiet after meaningful motion.
        if "gesture" in tags or "emphasis" in tags:
            state.held_pose_until_ms = max(state.held_pose_until_ms, now_ms + min(900, duration))


class BehaviorAnimationSelector:
    """Scores animation candidates from current semantic behavior state."""

    def __init__(
        self,
        library: Optional[Mapping[str, AnimationPreset]] = None,
        rng: Optional[random.Random] = None,
        resolver: Optional[AnimationConflictResolver] = None,
        suppression: Optional[AnimationSuppressionGate] = None,
    ) -> None:
        self.library = dict(library if library is not None else ANIMATION_LIBRARY)
        self.rng = rng or random.Random()
        self.resolver = resolver or AnimationConflictResolver()
        self.suppression = suppression or AnimationSuppressionGate()

    def _context_candidates(self, state: BehaviorState) -> Dict[str, AnimationPreset]:
        candidates: Dict[str, AnimationPreset] = {}
        contexts = list(INTENT_CONTEXTS.get(state.intent, ()))
        if state.is_seated:
            contexts.insert(0, "seated")
        if get_animations_for_context:
            for context in contexts:
                try:
                    candidates.update(get_animations_for_context(context))
                except Exception:
                    pass
        if not candidates:
            candidates.update(self.library)
        # Preserve explicit emotional overlay candidates even if context filters miss them.
        for anim_id in INTENT_ANIMATION_BONUSES.get(state.intent, {}):
            if anim_id in self.library:
                candidates[anim_id] = self.library[anim_id]
        return candidates

    def _score(self, preset: AnimationPreset, state: BehaviorState, now_ms: int) -> float:
        anim_id = getattr(preset, "animation_id", "")
        tags = set(getattr(preset, "tags", set()) or set())
        score = 0.1
        for tag, weight in INTENT_TAG_WEIGHTS.get(state.intent, {}).items():
            if tag in tags:
                score += weight
        score += INTENT_ANIMATION_BONUSES.get(state.intent, {}).get(anim_id, 0.0)

        # Context fit.
        if state.is_seated and "seated" in tags:
            score += 1.1
        if not state.is_seated and "seated" in tags:
            score -= 1.8

        # Human-feeling modulators.
        if "engagement" in tags or "listening" in tags:
            score += 0.8 * state.engagement
        if "confident" in tags or "assertive" in tags:
            score += 0.8 * state.social_confidence + 0.4 * state.dominance
        if "fidget" in tags:
            score += 0.9 * state.interruption_pressure + 0.3 * state.energy_level - 0.9 * state.stillness_bias
        if "gesture" in tags or "presentation" in tags or "emphasis" in tags:
            score += 0.8 * state.energy_level + 0.4 * state.social_confidence
        if "skepticism" in tags or "disagreement" in tags:
            score += 0.7 * (1.0 - state.engagement) + 0.5 * state.dominance

        # Repetition penalty by exact id and recent tag family.
        if anim_id == state.last_animation_id:
            score -= 4.0
        overlap = tags & set(state.recent_tags[-5:])
        score -= min(1.5, 0.25 * len(overlap))

        # Cooldown penalty, not absolute: suppression gate will hard block.
        if now_ms < state.cooldowns.get(anim_id, -1):
            score -= 5.0

        # Slight randomness keeps performance from becoming robotic but not chaotic.
        score += self.rng.uniform(-0.12, 0.12)
        return score

    def decide(self, state: BehaviorState, now_ms: Optional[int] = None, locked: bool = False) -> AnimationDecision:
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        candidates = self._context_candidates(state)
        scored: List[Tuple[str, float, AnimationPreset]] = []
        for anim_id, preset in candidates.items():
            conflict, _ = self.resolver.conflicts(preset, state, now_ms)
            if conflict:
                continue
            score = self._score(preset, state, now_ms)
            if score > 0:
                scored.append((anim_id, score, preset))
        scored.sort(key=lambda row: row[1], reverse=True)
        alternatives = [(anim_id, round(score, 3)) for anim_id, score, _ in scored[:5]]

        if not scored:
            return AnimationDecision(None, None, "no viable animation candidates", suppressed=True)

        # Weighted pick among top candidates. Pick top 4 only; more choices feels mushy.
        top = scored[:4]
        weights = [max(0.01, score) for _, score, _ in top]
        chosen_id, chosen_score, chosen = self.rng.choices(top, weights=weights, k=1)[0]

        suppressed, reason = self.suppression.should_suppress(chosen, state, now_ms)
        layer = self.resolver.infer_layer(chosen)
        if suppressed:
            return AnimationDecision(chosen_id, layer, reason, chosen_score, suppressed=True, alternatives=alternatives)

        self.resolver.activate(chosen, state, now_ms, locked=locked)
        self.suppression.note_played(chosen, state, now_ms)
        return AnimationDecision(chosen_id, layer, "selected from behavior state", chosen_score, False, alternatives)

    def tick(
        self,
        state: BehaviorState,
        elapsed_ms: int,
        intent: Optional[BehaviorIntent] = None,
        now_ms: Optional[int] = None,
    ) -> AnimationDecision:
        if intent is not None:
            state.update_intent(intent)
        state.decay(elapsed_ms)
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        return self.decide(state, now_ms=now_ms)


def build_default_selector(seed: Optional[int] = None) -> BehaviorAnimationSelector:
    """Convenience factory for app integration/tests."""
    return BehaviorAnimationSelector(rng=random.Random(seed))


def demo_sequence(seed: int = 7) -> List[Dict[str, Any]]:
    """Small deterministic smoke demo used by tests and handoff docs."""
    selector = build_default_selector(seed)
    state = BehaviorState("demo_avatar", is_seated=True, engagement=0.72, energy_level=0.52)
    now = 0
    output: List[Dict[str, Any]] = []
    for intent in [
        BehaviorIntent.LISTENING,
        BehaviorIntent.LISTENING,
        BehaviorIntent.THINKING,
        BehaviorIntent.SPEAKING,
        BehaviorIntent.SKEPTICAL,
        BehaviorIntent.RELAXED,
    ]:
        now += 1100
        decision = selector.tick(state, elapsed_ms=1100, intent=intent, now_ms=now)
        output.append({
            "intent": intent.value,
            "animation_id": decision.animation_id,
            "layer": decision.layer.name if decision.layer else None,
            "suppressed": decision.suppressed,
            "reason": decision.reason,
            "alternatives": decision.alternatives,
        })
    return output


if __name__ == "__main__":
    import json
    print(json.dumps(demo_sequence(), indent=2))
