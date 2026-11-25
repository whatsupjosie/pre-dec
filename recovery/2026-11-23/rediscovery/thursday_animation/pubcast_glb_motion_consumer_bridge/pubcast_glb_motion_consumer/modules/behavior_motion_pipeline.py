"""
PubCast Behavior + Mocap Motion Pipeline
========================================
System-level layer that wires together:
  1. expanded semantic animation library
  2. behavior/emotion cueing
  3. mocap frame ingestion
  4. procedural filler motion
  5. conflict/suppression/blend-safe animation commands

This is intentionally UI-free. It is the runtime spine that the future user menu,
Codex tools, stage renderer, or avatar performer can call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import math
import random
import time

try:
    from animation_presets_expanded import ANIMATION_LIBRARY, get_animation, get_animations_for_context, get_animations_by_tag
    from behavior_animation_engine import (
        BehaviorAnimationSelector,
        BehaviorIntent,
        BehaviorState,
        BodyLayer,
        AnimationDecision,
        AnimationConflictResolver,
        AnimationSuppressionGate,
        INTENT_ANIMATION_BONUSES,
        INTENT_TAG_WEIGHTS,
    )
except Exception:  # pragma: no cover
    from .animation_presets_expanded import ANIMATION_LIBRARY, get_animation, get_animations_for_context, get_animations_by_tag
    from .behavior_animation_engine import (
        BehaviorAnimationSelector,
        BehaviorIntent,
        BehaviorState,
        BodyLayer,
        AnimationDecision,
        AnimationConflictResolver,
        AnimationSuppressionGate,
        INTENT_ANIMATION_BONUSES,
        INTENT_TAG_WEIGHTS,
    )


class EmotionLabel(str, Enum):
    NEUTRAL = "neutral"
    WARM = "warm"
    CURIOUS = "curious"
    CONFIDENT = "confident"
    THINKING = "thinking"
    SKEPTICAL = "skeptical"
    NERVOUS = "nervous"
    RELAXED = "relaxed"
    ENTHUSIASTIC = "enthusiastic"
    GUARDED = "guarded"
    FOCUSED = "focused"
    RELIEVED = "relieved"


@dataclass
class EmotionCue:
    label: EmotionLabel = EmotionLabel.NEUTRAL
    intensity: float = 0.0
    source: str = "manual"
    confidence: float = 1.0
    expires_at_ms: Optional[int] = None

    def active(self, now_ms: int) -> bool:
        return self.expires_at_ms is None or now_ms < self.expires_at_ms


@dataclass
class MocapJoint:
    x: float
    y: float
    z: float = 0.0
    confidence: float = 1.0


@dataclass
class MocapFrame:
    timestamp_ms: int
    joints: Dict[str, MocapJoint]
    source: str = "unknown"
    body_confidence: float = 1.0
    face_confidence: float = 0.0
    hands_confidence: float = 0.0


@dataclass
class MotionCommand:
    avatar_id: str
    kind: str  # procedural_animation, mocap_pose, overlay, hold
    layer: str
    animation_id: Optional[str] = None
    weight: float = 1.0
    duration_ms: int = 0
    blend_in_ms: int = 120
    blend_out_ms: int = 160
    priority: int = 0
    source: str = "behavior"
    reason: str = ""
    pose: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineOutput:
    avatar_id: str
    commands: List[MotionCommand]
    state_snapshot: Dict[str, Any]
    decision: Optional[AnimationDecision] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class AvatarMotionProfile:
    """Stable tendencies. This is how Manny and Sheila eventually get habits."""
    avatar_id: str
    expressiveness: float = 0.55
    fidget_rate: float = 0.35
    nod_rate: float = 0.50
    gesture_rate: float = 0.45
    stillness_preference: float = 0.35
    politeness: float = 0.65
    camera_awareness: float = 0.50
    preferred_hand: str = "right"
    emotional_inertia: float = 0.70
    random_seed: Optional[int] = None

    def apply_to_state(self, state: BehaviorState) -> None:
        state.stillness_bias = max(0.0, min(1.0, self.stillness_preference))
        state.energy_level = max(0.0, min(1.0, 0.30 + self.expressiveness * 0.45))
        state.social_confidence = max(0.0, min(1.0, 0.35 + self.gesture_rate * 0.45))


EMOTION_TO_INTENT: Dict[EmotionLabel, BehaviorIntent] = {
    EmotionLabel.NEUTRAL: BehaviorIntent.IDLE,
    EmotionLabel.WARM: BehaviorIntent.RELAXED,
    EmotionLabel.CURIOUS: BehaviorIntent.LISTENING,
    EmotionLabel.CONFIDENT: BehaviorIntent.CONFIDENT,
    EmotionLabel.THINKING: BehaviorIntent.THINKING,
    EmotionLabel.SKEPTICAL: BehaviorIntent.SKEPTICAL,
    EmotionLabel.NERVOUS: BehaviorIntent.THINKING,
    EmotionLabel.RELAXED: BehaviorIntent.RELAXED,
    EmotionLabel.ENTHUSIASTIC: BehaviorIntent.ENTHUSIASTIC,
    EmotionLabel.GUARDED: BehaviorIntent.SKEPTICAL,
    EmotionLabel.FOCUSED: BehaviorIntent.THINKING,
    EmotionLabel.RELIEVED: BehaviorIntent.RELAXED,
}

EMOTION_OVERLAY_ANIMS: Dict[EmotionLabel, str] = {
    EmotionLabel.WARM: "warm_host_idle",
    EmotionLabel.CURIOUS: "curious_idle",
    EmotionLabel.CONFIDENT: "confident_stance",
    EmotionLabel.THINKING: "thoughtful_idle",
    EmotionLabel.SKEPTICAL: "skeptical_expression",
    EmotionLabel.NERVOUS: "nervous_idle",
    EmotionLabel.RELAXED: "relaxed_idle",
    EmotionLabel.ENTHUSIASTIC: "enthusiasm_bounce",
    EmotionLabel.GUARDED: "guarded_idle",
    EmotionLabel.FOCUSED: "focused_operator_idle",
    EmotionLabel.RELIEVED: "triumphant_recover",
}

TEXT_CUE_MAP: List[Tuple[Tuple[str, ...], EmotionLabel, float]] = [
    (("thank", "welcome", "glad", "happy", "great to see"), EmotionLabel.WARM, 0.55),
    (("hmm", "interesting", "what if", "why", "how"), EmotionLabel.CURIOUS, 0.45),
    (("exactly", "absolutely", "clearly", "here's the point"), EmotionLabel.CONFIDENT, 0.60),
    (("maybe", "i think", "let me think", "consider"), EmotionLabel.THINKING, 0.55),
    (("no", "but", "however", "i don't buy", "skeptical"), EmotionLabel.SKEPTICAL, 0.60),
    (("sorry", "uh", "um", "not sure", "worried"), EmotionLabel.NERVOUS, 0.50),
    (("we did it", "nice", "perfect", "finally"), EmotionLabel.RELIEVED, 0.65),
    (("wow", "amazing", "huge", "yes!"), EmotionLabel.ENTHUSIASTIC, 0.70),
    (("focus", "check", "route", "debug", "preflight"), EmotionLabel.FOCUSED, 0.55),
]


class EmotionCueMapper:
    """Converts text/host hints into emotional behavior state."""

    def cue_from_text(self, text: str, now_ms: int, ttl_ms: int = 2500) -> EmotionCue:
        lowered = (text or "").lower()
        best = EmotionCue(EmotionLabel.NEUTRAL, 0.0, source="text", expires_at_ms=now_ms + ttl_ms)
        for needles, label, intensity in TEXT_CUE_MAP:
            if any(n in lowered for n in needles):
                if intensity > best.intensity:
                    best = EmotionCue(label, intensity, source="text", confidence=0.75, expires_at_ms=now_ms + ttl_ms)
        if "?" in text and best.intensity < 0.5:
            best = EmotionCue(EmotionLabel.CURIOUS, 0.45, source="punctuation", confidence=0.65, expires_at_ms=now_ms + ttl_ms)
        if "!" in text and best.label == EmotionLabel.NEUTRAL:
            best = EmotionCue(EmotionLabel.ENTHUSIASTIC, 0.45, source="punctuation", confidence=0.55, expires_at_ms=now_ms + ttl_ms)
        return best

    def apply(self, state: BehaviorState, cue: EmotionCue, profile: AvatarMotionProfile, now_ms: int) -> BehaviorIntent:
        if not cue.active(now_ms) or cue.label == EmotionLabel.NEUTRAL:
            return state.intent
        amount = max(0.0, min(1.0, cue.intensity * cue.confidence))
        inertia = max(0.0, min(0.95, profile.emotional_inertia))
        new_weight = 1.0 - inertia

        if cue.label in (EmotionLabel.ENTHUSIASTIC, EmotionLabel.CONFIDENT, EmotionLabel.RELIEVED):
            state.energy_level = state.energy_level * inertia + (0.75 + 0.20 * amount) * new_weight
            state.social_confidence = state.social_confidence * inertia + (0.70 + 0.20 * amount) * new_weight
            state.engagement = max(state.engagement, 0.65 + 0.2 * amount)
        elif cue.label in (EmotionLabel.SKEPTICAL, EmotionLabel.GUARDED):
            state.engagement = state.engagement * inertia + (0.35 + 0.15 * amount) * new_weight
            state.dominance = max(state.dominance, 0.45 + 0.25 * amount)
            state.stillness_bias = max(state.stillness_bias, 0.45)
        elif cue.label in (EmotionLabel.THINKING, EmotionLabel.FOCUSED, EmotionLabel.CURIOUS):
            state.engagement = max(state.engagement, 0.60)
            state.energy_level = state.energy_level * inertia + (0.45 + 0.15 * amount) * new_weight
            state.stillness_bias = max(state.stillness_bias, 0.40)
        elif cue.label == EmotionLabel.NERVOUS:
            state.interruption_pressure = max(state.interruption_pressure, 0.45 + 0.30 * amount)
            state.social_confidence = min(state.social_confidence, 0.45)
        elif cue.label in (EmotionLabel.WARM, EmotionLabel.RELAXED):
            state.engagement = max(state.engagement, 0.55)
            state.stillness_bias = max(0.25, state.stillness_bias - 0.10 * amount)
        state.clamp()
        return EMOTION_TO_INTENT.get(cue.label, state.intent)


class MocapAdapter:
    """Turns raw mocap joints into normalized pose commands and behavior cues."""

    def __init__(self, confidence_threshold: float = 0.55) -> None:
        self.confidence_threshold = confidence_threshold
        self.previous: Dict[str, MocapFrame] = {}

    @staticmethod
    def _angle(a: MocapJoint, b: MocapJoint) -> float:
        return math.degrees(math.atan2(b.y - a.y, b.x - a.x))

    @staticmethod
    def _dist(a: MocapJoint, b: MocapJoint) -> float:
        return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)

    def infer_behavior_from_mocap(self, avatar_id: str, frame: Optional[MocapFrame], state: BehaviorState) -> List[EmotionCue]:
        if frame is None or frame.body_confidence < self.confidence_threshold:
            return []
        cues: List[EmotionCue] = []
        j = frame.joints
        nose = j.get("nose") or j.get("head")
        neck = j.get("neck") or j.get("chest")
        left_sh = j.get("left_shoulder")
        right_sh = j.get("right_shoulder")
        left_wrist = j.get("left_wrist")
        right_wrist = j.get("right_wrist")

        if nose and neck and nose.confidence > .5 and neck.confidence > .5:
            head_drop = neck.y - nose.y
            if head_drop < -0.05:
                cues.append(EmotionCue(EmotionLabel.THINKING, 0.35, source="mocap_head", confidence=frame.body_confidence, expires_at_ms=frame.timestamp_ms+900))

        if left_sh and right_sh and nose:
            shoulder_width = max(0.001, self._dist(left_sh, right_sh))
            center_x = (left_sh.x + right_sh.x) / 2.0
            lean = (nose.x - center_x) / shoulder_width
            if abs(lean) > 0.22:
                cues.append(EmotionCue(EmotionLabel.CURIOUS, min(0.65, abs(lean)), source="mocap_lean", confidence=frame.body_confidence, expires_at_ms=frame.timestamp_ms+1200))

        if nose and (left_wrist or right_wrist):
            raised = False
            for wrist in (left_wrist, right_wrist):
                if wrist and wrist.confidence > .55 and wrist.y > nose.y - 0.05:
                    raised = True
            if raised:
                cues.append(EmotionCue(EmotionLabel.ENTHUSIASTIC, 0.45, source="mocap_hand_raise", confidence=frame.hands_confidence or frame.body_confidence, expires_at_ms=frame.timestamp_ms+1000))
        return cues

    def build_pose_command(self, avatar_id: str, frame: Optional[MocapFrame]) -> Optional[MotionCommand]:
        if frame is None or frame.body_confidence < self.confidence_threshold:
            return None
        pose: Dict[str, Any] = {"timestamp_ms": frame.timestamp_ms, "source": frame.source, "bones": {}}
        j = frame.joints
        if "left_shoulder" in j and "right_shoulder" in j:
            # Basic torso yaw/roll proxy; actual retargeter can replace this.
            angle = self._angle(j["left_shoulder"], j["right_shoulder"])
            pose["bones"]["spine"] = {"rotation": [0.0, 0.0, max(-12.0, min(12.0, angle))]}
        if "nose" in j and "neck" in j:
            dx = j["nose"].x - j["neck"].x
            dy = j["nose"].y - j["neck"].y
            pose["bones"]["head"] = {"rotation": [max(-18.0, min(18.0, dx * 30.0)), max(-15.0, min(15.0, -dy * 20.0)), 0.0]}
        for side in ("left", "right"):
            sh = j.get(f"{side}_shoulder")
            elbow = j.get(f"{side}_elbow")
            wrist = j.get(f"{side}_wrist")
            if sh and elbow:
                pose["bones"][f"arm_{side}"] = {"rotation": [0.0, 0.0, self._angle(sh, elbow)]}
            if elbow and wrist:
                pose["bones"][f"forearm_{side}"] = {"rotation": [0.0, 0.0, self._angle(elbow, wrist)]}
        return MotionCommand(
            avatar_id=avatar_id,
            kind="mocap_pose",
            layer="MOCAP_BASE",
            weight=max(0.0, min(1.0, frame.body_confidence)),
            duration_ms=120,
            blend_in_ms=50,
            blend_out_ms=80,
            priority=70,
            source=frame.source,
            reason="live mocap pose retarget proxy",
            pose=pose,
        )


class BehaviorMotionPipeline:
    """One object per avatar or per scene; call tick from runtime."""

    def __init__(self, profile: AvatarMotionProfile, seed: Optional[int] = None) -> None:
        self.profile = profile
        self.rng = random.Random(seed if seed is not None else profile.random_seed)
        self.selector = BehaviorAnimationSelector(library=ANIMATION_LIBRARY, rng=self.rng)
        # Patch selector context getter by using the expanded library explicitly.
        self.selector.library = dict(ANIMATION_LIBRARY)
        self.mapper = EmotionCueMapper()
        self.mocap = MocapAdapter()
        self.state = BehaviorState(profile.avatar_id)
        profile.apply_to_state(self.state)
        self.active_cues: List[EmotionCue] = []
        self.last_tick_ms: Optional[int] = None

    def push_emotion(self, cue: EmotionCue) -> None:
        self.active_cues.append(cue)

    def push_text(self, text: str, now_ms: Optional[int] = None) -> EmotionCue:
        now = int(time.time() * 1000) if now_ms is None else now_ms
        cue = self.mapper.cue_from_text(text, now)
        self.push_emotion(cue)
        return cue

    def _choose_intent(self, explicit_intent: Optional[BehaviorIntent], now_ms: int) -> BehaviorIntent:
        if explicit_intent is not None:
            return explicit_intent
        live = [cue for cue in self.active_cues if cue.active(now_ms)]
        self.active_cues = live
        if not live:
            return self.state.intent
        strongest = max(live, key=lambda c: c.intensity * c.confidence)
        return self.mapper.apply(self.state, strongest, self.profile, now_ms)

    def _overlay_command(self, cue: Optional[EmotionCue], now_ms: int) -> Optional[MotionCommand]:
        if cue is None or not cue.active(now_ms):
            return None
        anim_id = EMOTION_OVERLAY_ANIMS.get(cue.label)
        if not anim_id or not get_animation(anim_id):
            return None
        weight = max(0.10, min(0.65, cue.intensity * cue.confidence * self.profile.expressiveness))
        return MotionCommand(
            avatar_id=self.profile.avatar_id,
            kind="overlay",
            layer="EMOTION_OVERLAY",
            animation_id=anim_id,
            weight=weight,
            duration_ms=getattr(get_animation(anim_id), "duration_ms", 1000),
            priority=int(BodyLayer.EMOTION_OVERLAY),
            source=cue.source,
            reason=f"emotion overlay for {cue.label.value}",
            metadata={"emotion": cue.label.value, "intensity": cue.intensity},
        )

    def tick(
        self,
        *,
        now_ms: Optional[int] = None,
        elapsed_ms: Optional[int] = None,
        explicit_intent: Optional[BehaviorIntent] = None,
        transcript_text: Optional[str] = None,
        mocap_frame: Optional[MocapFrame] = None,
        is_seated: Optional[bool] = None,
    ) -> PipelineOutput:
        now = int(time.time() * 1000) if now_ms is None else int(now_ms)
        if elapsed_ms is None:
            elapsed_ms = 0 if self.last_tick_ms is None else max(0, now - self.last_tick_ms)
        self.last_tick_ms = now
        if is_seated is not None:
            self.state.is_seated = bool(is_seated)
        if transcript_text:
            self.push_text(transcript_text, now)

        for cue in self.mocap.infer_behavior_from_mocap(self.profile.avatar_id, mocap_frame, self.state):
            self.push_emotion(cue)

        intent = self._choose_intent(explicit_intent, now)
        self.state.update_intent(intent)

        commands: List[MotionCommand] = []
        warnings: List[str] = []

        mocap_cmd = self.mocap.build_pose_command(self.profile.avatar_id, mocap_frame)
        if mocap_cmd:
            commands.append(mocap_cmd)
            # When mocap is strong, keep procedural smaller and less frequent.
            self.state.stillness_bias = max(self.state.stillness_bias, 0.50)

        live_cues = [cue for cue in self.active_cues if cue.active(now)]
        strongest = max(live_cues, key=lambda c: c.intensity * c.confidence) if live_cues else None
        overlay = self._overlay_command(strongest, now)
        if overlay:
            commands.append(overlay)

        decision = self.selector.tick(self.state, elapsed_ms=elapsed_ms, intent=intent, now_ms=now)
        overlay_anim_id = overlay.animation_id if overlay else None
        if decision.should_play() and decision.animation_id and decision.animation_id == overlay_anim_id:
            commands.append(MotionCommand(
                avatar_id=self.profile.avatar_id,
                kind="hold",
                layer="STILLNESS",
                duration_ms=250,
                weight=1.0,
                priority=5,
                source="overlay_dedupe",
                reason="procedural candidate already active as emotional overlay",
                metadata={"candidate": decision.animation_id, "intent": intent.value},
            ))
        elif decision.should_play() and decision.animation_id:
            preset_obj = get_animation(decision.animation_id)
            duration = int(getattr(preset_obj, "duration_ms", 800) or 800) if preset_obj else 800
            commands.append(MotionCommand(
                avatar_id=self.profile.avatar_id,
                kind="procedural_animation",
                layer=decision.layer.name if decision.layer else "UNKNOWN",
                animation_id=decision.animation_id,
                weight=min(1.0, 0.35 + self.profile.expressiveness * 0.65),
                duration_ms=duration,
                priority=int(decision.layer or BodyLayer.TORSO),
                source="behavior_selector",
                reason=decision.reason,
                metadata={"alternatives": decision.alternatives, "score": decision.score, "intent": intent.value},
            ))
        elif decision.suppressed:
            # This is expected, not an error. Runtime can use it for debug HUD/logging.
            commands.append(MotionCommand(
                avatar_id=self.profile.avatar_id,
                kind="hold",
                layer="STILLNESS",
                duration_ms=250,
                weight=1.0,
                priority=5,
                source="suppression_gate",
                reason=decision.reason,
                metadata={"candidate": decision.animation_id, "intent": intent.value},
            ))

        if not commands:
            warnings.append("No motion command emitted; avatar should keep previous pose.")

        snapshot = {
            "avatar_id": self.state.avatar_id,
            "intent": self.state.intent.value,
            "is_seated": self.state.is_seated,
            "energy_level": round(self.state.energy_level, 3),
            "social_confidence": round(self.state.social_confidence, 3),
            "engagement": round(self.state.engagement, 3),
            "dominance": round(self.state.dominance, 3),
            "interruption_pressure": round(self.state.interruption_pressure, 3),
            "stillness_bias": round(self.state.stillness_bias, 3),
            "active_cues": [c.label.value for c in live_cues],
            "last_animation_id": self.state.last_animation_id,
        }
        return PipelineOutput(self.profile.avatar_id, commands, snapshot, decision=decision, warnings=warnings)


def make_test_mocap_frame(ts: int = 1000) -> MocapFrame:
    return MocapFrame(
        timestamp_ms=ts,
        source="test_webcam_proxy",
        body_confidence=0.82,
        hands_confidence=0.66,
        joints={
            "nose": MocapJoint(0.51, 0.82, confidence=0.9),
            "neck": MocapJoint(0.50, 0.70, confidence=0.9),
            "left_shoulder": MocapJoint(0.38, 0.66, confidence=0.9),
            "right_shoulder": MocapJoint(0.62, 0.66, confidence=0.9),
            "left_elbow": MocapJoint(0.34, 0.52, confidence=0.8),
            "right_elbow": MocapJoint(0.66, 0.52, confidence=0.8),
            "left_wrist": MocapJoint(0.32, 0.42, confidence=0.75),
            "right_wrist": MocapJoint(0.69, 0.86, confidence=0.75),
        },
    )


if __name__ == "__main__":
    pipe = BehaviorMotionPipeline(AvatarMotionProfile("demo", expressiveness=0.72), seed=4)
    out = pipe.tick(now_ms=1000, elapsed_ms=1000, transcript_text="Exactly, here's the point.", mocap_frame=make_test_mocap_frame(), is_seated=True)
    import json
    print(json.dumps({"snapshot": out.state_snapshot, "commands": [c.__dict__ for c in out.commands]}, indent=2, default=str))
