"""
PubCast Expanded Animation Presets
==================================
Adds a second-wave behavior vocabulary on top of animation_presets_complete.py.

This file intentionally imports the original library and appends new presets instead
of replacing the base file. That keeps integration safer: existing imports keep
working, while new systems can import this expanded module for richer behavior.

Total target after expansion: 70+ body-language tokens.
"""
from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

try:
    from animation_presets_complete import (  # type: ignore
        AnimationCategory,
        AnimationPreset,
        BoneKeyframe,
        ANIMATION_LIBRARY as BASE_ANIMATION_LIBRARY,
    )
except Exception:  # pragma: no cover
    from .animation_presets_complete import (  # type: ignore
        AnimationCategory,
        AnimationPreset,
        BoneKeyframe,
        ANIMATION_LIBRARY as BASE_ANIMATION_LIBRARY,
    )


def k(bone: str, frame: int, ms: int, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)) -> BoneKeyframe:
    return BoneKeyframe(bone, frame, ms, position=pos, rotation=rot, scale=scale)


def preset(
    animation_id: str,
    category: AnimationCategory,
    name: str,
    duration: int,
    frames,
    *,
    loop: bool = False,
    blocking: bool = False,
    tags: Set[str] | None = None,
    blendable_with: Set[str] | None = None,
    description: str = "",
) -> AnimationPreset:
    return AnimationPreset(
        animation_id=animation_id,
        category=category,
        display_name=name,
        duration_ms=duration,
        is_loopable=loop,
        is_blocking=blocking,
        frames=list(frames),
        blendable_with=blendable_with or set(),
        tags=tags or set(),
        description=description,
    )


EXPANDED_ANIMATIONS: Dict[str, AnimationPreset] = {}


def add(anim: AnimationPreset) -> None:
    EXPANDED_ANIMATIONS[anim.animation_id] = anim


# ---------------------------------------------------------------------------
# Listening / conversational presence additions
# ---------------------------------------------------------------------------
add(preset("micro_nod", AnimationCategory.LISTENING, "Micro Nod", 520, [
    k("head", 0, 0), k("head", 8, 170, rot=(0, 1.1, 0)), k("head", 16, 180), k("head", 24, 170, rot=(0, -0.4, 0)),
], loop=False, tags={"listening", "agreement", "subtle", "presence", "natural"}, description="Tiny acknowledgment nod; useful when full nodding would overplay the moment."))

add(preset("delayed_nod", AnimationCategory.LISTENING, "Delayed Nod", 1800, [
    k("head", 0, 0), k("head", 18, 650), k("head", 28, 420, rot=(0, 2.2, 0)), k("head", 40, 420), k("head", 48, 310, rot=(0, -0.7, 0)),
], loop=False, tags={"listening", "agreement", "thoughtful", "delayed", "natural"}, description="Agreement after processing; good for serious or reflective dialogue."))

add(preset("double_take_subtle", AnimationCategory.LISTENING, "Subtle Double Take", 900, [
    k("head", 0, 0), k("head", 8, 220, rot=(0, 0, 4)), k("head", 16, 180), k("head", 24, 250, rot=(0, 0, -5)), k("head", 32, 250),
], tags={"surprise", "curiosity", "listening", "reaction", "subtle"}, description="Small surprise/check reaction without cartoon exaggeration."))

add(preset("listen_breath_settle", AnimationCategory.LISTENING, "Listening Breath Settle", 1600, [
    k("spine", 0, 0), k("chest", 0, 0), k("spine", 20, 800, rot=(0, 0, 1.2)), k("chest", 20, 800, pos=(0, 0.25, 0)), k("spine", 40, 800), k("chest", 40, 800),
], loop=True, tags={"listening", "breath", "presence", "subtle", "natural"}, description="Quiet breathing/settling loop for moments where stillness is right."))

add(preset("attentive_turn_left", AnimationCategory.LISTENING, "Attentive Turn Left", 760, [
    k("head", 0, 0), k("spine", 0, 0), k("head", 16, 380, rot=(-5, 0, -2)), k("spine", 16, 380, rot=(-2, 0, 0)), k("head", 32, 380, rot=(-3, 0, -1)),
], tags={"listening", "attention", "turn", "left", "engagement"}, description="Turns attention toward a speaker or sound source on the left."))

add(preset("attentive_turn_right", AnimationCategory.LISTENING, "Attentive Turn Right", 760, [
    k("head", 0, 0), k("spine", 0, 0), k("head", 16, 380, rot=(5, 0, 2)), k("spine", 16, 380, rot=(2, 0, 0)), k("head", 32, 380, rot=(3, 0, 1)),
], tags={"listening", "attention", "turn", "right", "engagement"}, description="Turns attention toward a speaker or sound source on the right."))

add(preset("soft_disagree", AnimationCategory.LISTENING, "Soft Disagreement", 950, [
    k("head", 0, 0), k("head", 10, 240, rot=(0, 0, -3.5)), k("head", 20, 240, rot=(0, 0, 3.5)), k("head", 30, 240, rot=(0, 0, -2)), k("head", 38, 230),
], tags={"disagreement", "skepticism", "listening", "subtle", "natural"}, description="A softer no than head_shake; good when the avatar is polite or uncertain."))

add(preset("processing_pause", AnimationCategory.LISTENING, "Processing Pause", 1400, [
    k("head", 0, 0), k("spine", 0, 0), k("head", 20, 700, rot=(2.5, 0, 0)), k("spine", 20, 700, rot=(0, 0, -1)), k("head", 40, 700), k("spine", 40, 700),
], tags={"thinking", "listening", "processing", "stillness", "subtle"}, description="The avatar takes a beat before reacting; helps avoid twitchy instant responses."))

# ---------------------------------------------------------------------------
# Speaking / hand gesture additions
# ---------------------------------------------------------------------------
add(preset("small_beat_left", AnimationCategory.GESTURE, "Small Beat Left", 520, [
    k("hand_left", 0, 0), k("arm_left", 0, 0), k("hand_left", 10, 220, pos=(0.6, 0.8, 0), rot=(0, 0, 12)), k("arm_left", 10, 220, rot=(0, 0, 12)), k("hand_left", 24, 300), k("arm_left", 24, 300),
], tags={"gesture", "emphasis", "speech", "beat", "subtle"}, description="Small speech beat with the left hand."))

add(preset("small_beat_right", AnimationCategory.GESTURE, "Small Beat Right", 520, [
    k("hand_right", 0, 0), k("arm_right", 0, 0), k("hand_right", 10, 220, pos=(-0.6, 0.8, 0), rot=(0, 0, -12)), k("arm_right", 10, 220, rot=(0, 0, -12)), k("hand_right", 24, 300), k("arm_right", 24, 300),
], tags={"gesture", "emphasis", "speech", "beat", "subtle"}, description="Small speech beat with the right hand."))

add(preset("count_on_fingers", AnimationCategory.GESTURE, "Count on Fingers", 1500, [
    k("hand_right", 0, 0), k("arm_right", 0, 0), k("hand_right", 10, 300, pos=(-1.2, 1.1, 0), rot=(0, 0, -20)), k("hand_right", 25, 400, pos=(-1.1, 1.15, 0), rot=(0, 0, -10)), k("hand_right", 40, 400, pos=(-1.0, 1.2, 0), rot=(0, 0, -4)), k("hand_right", 55, 400), k("arm_right", 55, 400),
], tags={"gesture", "explain", "counting", "speech", "emphasis"}, description="Enumeration gesture for explaining multiple points."))

add(preset("frame_the_idea", AnimationCategory.GESTURE, "Frame the Idea", 1100, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("arm_left", 0, 0), k("arm_right", 0, 0),
    k("hand_left", 20, 500, pos=(1.3, 1.1, 0), rot=(0, 0, 25)), k("hand_right", 20, 500, pos=(-1.3, 1.1, 0), rot=(0, 0, -25)),
    k("hand_left", 40, 600, pos=(1.4, 1.1, 0), rot=(0, 0, 20)), k("hand_right", 40, 600, pos=(-1.4, 1.1, 0), rot=(0, 0, -20)),
], tags={"gesture", "presentation", "explain", "idea", "speech"}, description="Two-hand gesture that frames an idea in space."))

add(preset("offer_object_space", AnimationCategory.GESTURE, "Offer Object Space", 950, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("hand_left", 20, 460, pos=(0.9, 0.6, 0.3), rot=(0, 0, 28)), k("hand_right", 20, 460, pos=(-0.9, 0.6, 0.3), rot=(0, 0, -28)), k("hand_left", 38, 490, pos=(0.7, 0.6, 0.3)), k("hand_right", 38, 490, pos=(-0.7, 0.6, 0.3)),
], tags={"gesture", "presentation", "offering", "space", "speech"}, description="Offers an invisible object/option to the audience."))

add(preset("precision_pinch", AnimationCategory.GESTURE, "Precision Pinch", 700, [
    k("hand_right", 0, 0), k("arm_right", 0, 0), k("hand_right", 16, 350, pos=(-1.0, 1.1, 0), rot=(0, 0, -8)), k("arm_right", 16, 350, rot=(0, 0, -18)), k("hand_right", 32, 350), k("arm_right", 32, 350),
], tags={"gesture", "precision", "small", "emphasis", "speech"}, description="Tiny 'exactly this' gesture for precise statements."))

add(preset("palms_down_calm", AnimationCategory.GESTURE, "Palms Down Calm", 900, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("hand_left", 20, 450, pos=(0.8, -0.4, 0), rot=(0, 0, -8)), k("hand_right", 20, 450, pos=(-0.8, -0.4, 0), rot=(0, 0, 8)), k("hand_left", 40, 450), k("hand_right", 40, 450),
], tags={"gesture", "calm", "deescalate", "speech", "control"}, description="Calming downward gesture; good for moderation or slowing the room."))

add(preset("not_me_gesture", AnimationCategory.GESTURE, "Not Me Gesture", 850, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("shoulder_left", 0, 0), k("shoulder_right", 0, 0),
    k("hand_left", 18, 380, pos=(1.1, 0.7, 0), rot=(0, 0, 18)), k("hand_right", 18, 380, pos=(-1.1, 0.7, 0), rot=(0, 0, -18)),
    k("shoulder_left", 18, 380, pos=(0, 0.5, 0)), k("shoulder_right", 18, 380, pos=(0, 0.5, 0)),
    k("hand_left", 36, 470), k("hand_right", 36, 470), k("shoulder_left", 36, 470), k("shoulder_right", 36, 470),
], tags={"gesture", "uncertainty", "deflect", "humor", "speech"}, description="Light disclaiming gesture; useful for jokes and self-aware remarks."))

# ---------------------------------------------------------------------------
# Fidgets and grounding motions
# ---------------------------------------------------------------------------
add(preset("adjust_sleeve_left", AnimationCategory.FIDGET, "Adjust Left Sleeve", 1050, [
    k("hand_right", 0, 0), k("arm_right", 0, 0), k("hand_right", 12, 350, pos=(0.9, 0.2, 0), rot=(0, 0, -18)), k("hand_right", 24, 350, pos=(0.8, 0.1, 0), rot=(0, 0, -12)), k("hand_right", 36, 350), k("arm_right", 36, 350),
], tags={"fidget", "grooming", "natural", "subtle", "hands"}, description="Small sleeve adjustment; fills a pause without stealing focus."))

add(preset("adjust_sleeve_right", AnimationCategory.FIDGET, "Adjust Right Sleeve", 1050, [
    k("hand_left", 0, 0), k("arm_left", 0, 0), k("hand_left", 12, 350, pos=(-0.9, 0.2, 0), rot=(0, 0, 18)), k("hand_left", 24, 350, pos=(-0.8, 0.1, 0), rot=(0, 0, 12)), k("hand_left", 36, 350), k("arm_left", 36, 350),
], tags={"fidget", "grooming", "natural", "subtle", "hands"}, description="Small sleeve adjustment on the other side."))

add(preset("rub_palms_once", AnimationCategory.FIDGET, "Rub Palms Once", 950, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("hand_left", 12, 300, pos=(0.35, -0.2, 0)), k("hand_right", 12, 300, pos=(-0.35, -0.2, 0)), k("hand_left", 24, 300, pos=(0.15, -0.2, 0)), k("hand_right", 24, 300, pos=(-0.15, -0.2, 0)), k("hand_left", 36, 350), k("hand_right", 36, 350),
], tags={"fidget", "anticipation", "thinking", "hands", "subtle"}, description="One contained palm rub; anticipation without villain-camp."))

add(preset("ankle_shift_seated", AnimationCategory.SEATED, "Ankle Shift Seated", 800, [
    k("foot_left", 0, 0), k("foot_right", 0, 0), k("pelvis", 0, 0), k("foot_left", 16, 400, pos=(0.2, 0, 0), rot=(0, 0, 3)), k("pelvis", 16, 400, pos=(0.15, 0, 0)), k("foot_left", 32, 400), k("pelvis", 32, 400),
], tags={"seated", "fidget", "body", "subtle", "natural"}, description="Subtle seated ankle/weight adjustment."))

add(preset("table_hand_settle", AnimationCategory.SEATED, "Table Hand Settle", 700, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("hand_left", 14, 350, pos=(0.5, -0.8, 0.4)), k("hand_right", 14, 350, pos=(-0.5, -0.8, 0.4)), k("hand_left", 28, 350, pos=(0.45, -0.85, 0.4)), k("hand_right", 28, 350, pos=(-0.45, -0.85, 0.4)),
], tags={"seated", "hands", "settle", "podcast", "natural"}, description="Hands settle onto table/mic area for seated podcast work."))

add(preset("mic_check_lean", AnimationCategory.SEATED, "Mic Check Lean", 850, [
    k("spine", 0, 0), k("head", 0, 0), k("hand_right", 0, 0), k("spine", 18, 420, pos=(1.0, 0, 0), rot=(0, 0, 4)), k("head", 18, 420, rot=(0, 1.0, 0)), k("hand_right", 18, 420, pos=(-0.5, -0.3, 0.6)), k("spine", 34, 430), k("head", 34, 430), k("hand_right", 34, 430),
], tags={"seated", "podcast", "mic", "lean", "technical", "fidget"}, description="Subtle lean toward mic/console."))

add(preset("chair_recenter", AnimationCategory.SEATED, "Chair Recenter", 1000, [
    k("pelvis", 0, 0), k("spine", 0, 0), k("pelvis", 12, 300, pos=(0.35, 0, 0)), k("spine", 12, 300, rot=(0, 0, -1.5)), k("pelvis", 24, 300, pos=(-0.2, 0, 0)), k("spine", 24, 300, rot=(0, 0, 1.0)), k("pelvis", 40, 400), k("spine", 40, 400),
], tags={"seated", "body", "adjust", "fidget", "natural"}, description="Re-centers in chair after a long hold."))

# ---------------------------------------------------------------------------
# Emotional / attitude overlays
# ---------------------------------------------------------------------------
add(preset("guarded_idle", AnimationCategory.EMOTIONAL, "Guarded Idle", 1800, [
    k("spine", 0, 0), k("shoulder_left", 0, 0), k("shoulder_right", 0, 0), k("head", 0, 0), k("spine", 30, 900, rot=(0, 0, -1.5)), k("shoulder_left", 30, 900, pos=(0, 0.25, 0)), k("shoulder_right", 30, 900, pos=(0, 0.25, 0)), k("head", 30, 900, rot=(0, -0.5, 0)), k("spine", 60, 900), k("shoulder_left", 60, 900), k("shoulder_right", 60, 900),
], loop=True, tags={"guarded", "defensive", "skepticism", "emotional", "subtle"}, description="Protective, guarded baseline posture."))

add(preset("curious_idle", AnimationCategory.EMOTIONAL, "Curious Idle", 1700, [
    k("head", 0, 0), k("spine", 0, 0), k("head", 28, 850, rot=(-1.5, 0.5, -2.5)), k("spine", 28, 850, rot=(0.8, 0, 1.0)), k("head", 56, 850), k("spine", 56, 850),
], loop=True, tags={"curious", "engagement", "listening", "emotional", "presence"}, description="Curious attentiveness overlay."))

add(preset("nervous_idle", AnimationCategory.EMOTIONAL, "Nervous Idle", 1300, [
    k("spine", 0, 0), k("hand_left", 0, 0), k("hand_right", 0, 0), k("spine", 16, 420, rot=(0, 0, -0.8)), k("hand_left", 16, 420, pos=(0.1, -0.2, 0)), k("hand_right", 16, 420, pos=(-0.1, -0.2, 0)), k("spine", 32, 420, rot=(0, 0, 0.8)), k("hand_left", 32, 420, pos=(0.15, -0.15, 0)), k("hand_right", 32, 420, pos=(-0.15, -0.15, 0)), k("spine", 48, 460),
], loop=True, tags={"nervous", "fidget", "emotional", "uncertain", "subtle"}, description="Low-level nervous energy baseline."))

add(preset("warm_host_idle", AnimationCategory.EMOTIONAL, "Warm Host Idle", 1900, [
    k("spine", 0, 0), k("head", 0, 0), k("shoulder_left", 0, 0), k("shoulder_right", 0, 0), k("spine", 30, 950, rot=(0, 0, 1.5)), k("head", 30, 950, rot=(0, 1.0, 1.0)), k("shoulder_left", 30, 950, pos=(0, -0.15, 0)), k("shoulder_right", 30, 950, pos=(0, -0.15, 0)), k("spine", 60, 950), k("head", 60, 950),
], loop=True, tags={"warm", "friendly", "host", "emotional", "presence"}, description="Open, welcoming host posture."))

add(preset("focused_operator_idle", AnimationCategory.EMOTIONAL, "Focused Operator Idle", 1600, [
    k("head", 0, 0), k("spine", 0, 0), k("hand_right", 0, 0), k("head", 24, 800, rot=(1.0, 0, 0)), k("spine", 24, 800, rot=(0, 0, 2.0)), k("hand_right", 24, 800, pos=(-0.2, -0.4, 0.2)), k("head", 48, 800), k("spine", 48, 800), k("hand_right", 48, 800),
], loop=True, tags={"focused", "operator", "technical", "emotional", "thinking"}, description="Concentrated control-room posture."))

add(preset("triumphant_recover", AnimationCategory.EMOTIONAL, "Triumphant Recover", 1500, [
    k("spine", 0, 0), k("head", 0, 0), k("hand_left", 0, 0), k("hand_right", 0, 0), k("spine", 18, 500, rot=(0, 0, 5)), k("head", 18, 500, rot=(0, -2, 0)), k("hand_left", 18, 500, pos=(0.8, 0.6, 0)), k("hand_right", 18, 500, pos=(-0.8, 0.6, 0)), k("spine", 48, 1000), k("head", 48, 1000), k("hand_left", 48, 1000), k("hand_right", 48, 1000),
], tags={"relief", "success", "confidence", "emotional", "recovery"}, description="Contained success/relief motion after a win."))

# ---------------------------------------------------------------------------
# Direction / staging tokens
# ---------------------------------------------------------------------------
add(preset("look_to_camera", AnimationCategory.SCRIPTED, "Look to Camera", 500, [
    k("head", 0, 0), k("spine", 0, 0), k("head", 16, 350, rot=(0, 0, 0)), k("spine", 16, 350), k("head", 24, 150),
], tags={"camera", "attention", "scripted", "host", "focus"}, description="Clean attention snap to camera without a big motion."))

add(preset("look_to_guest", AnimationCategory.SCRIPTED, "Look to Guest", 620, [
    k("head", 0, 0), k("spine", 0, 0), k("head", 16, 360, rot=(4, 0, 1)), k("spine", 16, 360, rot=(1.5, 0, 0)), k("head", 28, 260, rot=(3, 0, 0.5)),
], tags={"guest", "attention", "scripted", "listening", "focus"}, description="Shifts attention from audience/camera to conversation partner."))

add(preset("invite_response", AnimationCategory.INTERACTION, "Invite Response", 1200, [
    k("hand_left", 0, 0), k("hand_right", 0, 0), k("head", 0, 0), k("hand_left", 20, 520, pos=(0.9, 0.7, 0), rot=(0, 0, 20)), k("hand_right", 20, 520, pos=(-0.9, 0.7, 0), rot=(0, 0, -20)), k("head", 20, 520, rot=(0, 1, 0)), k("hand_left", 44, 680), k("hand_right", 44, 680), k("head", 44, 680),
], tags={"interaction", "invite", "handoff", "gesture", "friendly"}, description="Invites another avatar/person to answer."))

add(preset("yield_floor", AnimationCategory.INTERACTION, "Yield the Floor", 1050, [
    k("hand_right", 0, 0), k("head", 0, 0), k("spine", 0, 0), k("hand_right", 16, 440, pos=(-1.1, 0.5, 0.2), rot=(0, 0, -25)), k("head", 16, 440, rot=(3, 0, 1)), k("spine", 16, 440, rot=(1.5, 0, 0)), k("hand_right", 38, 610), k("head", 38, 610), k("spine", 38, 610),
], tags={"interaction", "handoff", "listening", "gesture", "floor"}, description="Finishes a thought and gives conversational floor to someone else."))

add(preset("interrupt_start", AnimationCategory.INTERACTION, "Interrupt Start", 650, [
    k("hand_left", 0, 0), k("head", 0, 0), k("spine", 0, 0), k("hand_left", 12, 260, pos=(0.7, 0.8, 0), rot=(0, 0, 18)), k("head", 12, 260, rot=(-2, 0, -1)), k("spine", 12, 260, rot=(0, 0, 2)), k("hand_left", 26, 390, pos=(0.5, 0.65, 0)),
], tags={"interaction", "interrupt", "speech", "attention", "gesture"}, description="Starts to interject; should be suppressed if politeness/turn-taking says no."))

ANIMATION_LIBRARY: Dict[str, AnimationPreset] = dict(BASE_ANIMATION_LIBRARY)
ANIMATION_LIBRARY.update(EXPANDED_ANIMATIONS)


def get_animation(animation_id: str) -> Optional[AnimationPreset]:
    return ANIMATION_LIBRARY.get(animation_id)


def get_animations_by_category(category: AnimationCategory) -> Dict[str, AnimationPreset]:
    return {k: v for k, v in ANIMATION_LIBRARY.items() if v.category == category}


def get_animations_by_tag(tag: str) -> Dict[str, AnimationPreset]:
    return {k: v for k, v in ANIMATION_LIBRARY.items() if tag in v.tags}


def get_loopable_animations() -> Dict[str, AnimationPreset]:
    return {k: v for k, v in ANIMATION_LIBRARY.items() if v.is_loopable}


def get_animations_for_context(context: str) -> Dict[str, AnimationPreset]:
    context_tags = {
        "seated": {"seated", "podcast", "fidget", "body", "hands"},
        "standing": {"gesture", "listening", "presence", "host", "attention"},
        "listening": {"listening", "agreement", "engagement", "attention", "processing"},
        "speaking": {"gesture", "presentation", "emphasis", "speech", "explain", "handoff"},
        "thinking": {"thinking", "contemplative", "processing", "fidget", "focused"},
        "camera": {"camera", "host", "focus"},
        "interaction": {"interaction", "handoff", "invite", "floor", "interrupt"},
        "technical": {"technical", "operator", "mic", "focused"},
    }
    tags = context_tags.get(context, set())
    return {k: v for k, v in ANIMATION_LIBRARY.items() if any(t in v.tags for t in tags)}


def list_all_animations() -> Dict[str, Dict]:
    return {k: v.to_dict() for k, v in ANIMATION_LIBRARY.items()}


if __name__ == "__main__":
    print(f"Loaded {len(ANIMATION_LIBRARY)} animations ({len(EXPANDED_ANIMATIONS)} expanded)")
    for ctx in ["seated", "standing", "listening", "speaking", "thinking", "interaction", "camera"]:
        print(f"{ctx:12s}: {len(get_animations_for_context(ctx)):2d}")
