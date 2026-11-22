"""Runtime animation player and sequence helpers for PubCast performers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

from ..event_bus import EventBus
from .animation_authority import AnimationAuthority
from .animation_presets import ANIMATION_PRESETS, normalize_animation_name, sample_preset_pose
from .motion_retargeting import MotionRetargeter, RETARGET_MODE_TARGET_EQUIVALENT

if TYPE_CHECKING:
    from ..performer_registry import PerformerRegistry


@dataclass(frozen=True)
class AnimationClip:
    performer_id: str
    animation: str
    start_time: float
    duration: float
    layer: str = "scripted"
    priority: Optional[int] = None

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    def to_dict(self):
        return asdict(self)


@dataclass
class AnimationSequence:
    sequence_id: str
    clips: List[AnimationClip] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max((clip.end_time for clip in self.clips), default=0.0)

    def active_clips(self, elapsed: float) -> List[AnimationClip]:
        return [clip for clip in self.clips if clip.start_time <= elapsed <= clip.end_time]

    def to_dict(self):
        return {"sequence_id": self.sequence_id, "duration": self.duration, "clips": [clip.to_dict() for clip in self.clips]}


class AnimationRuntime:
    """Apply named animation presets through the spine registries."""

    def __init__(
        self,
        registry: "PerformerRegistry",
        authority: AnimationAuthority,
        event_bus: Optional[EventBus] = None,
        retargeter: Optional[MotionRetargeter] = None,
        retarget_mode: str = RETARGET_MODE_TARGET_EQUIVALENT,
    ):
        self.registry = registry
        self.authority = authority
        self.event_bus = event_bus
        self.retargeter = retargeter or MotionRetargeter()
        self.retarget_mode = retarget_mode

    def apply_animation(
        self,
        performer_id: str,
        animation_name: str,
        elapsed: float,
        layer: str = "scripted",
        priority: Optional[int] = None,
        retarget_mode: Optional[str] = None,
    ) -> Dict:
        animation = normalize_animation_name(animation_name)
        pose = sample_preset_pose(animation, elapsed)
        performer = self.registry.get_performer(performer_id)
        retarget_report = None
        if performer is not None:
            pose, retarget_report = self.retargeter.retarget_pose_with_report(
                pose,
                performer.avatar_skeleton,
                motion_intent=animation,
                retarget_mode=retarget_mode or self.retarget_mode,
            )
        self.authority.register_animation(performer_id, layer, pose, priority=priority)
        resolved = self.authority.resolve(performer_id)
        self.registry.apply_animation_frame(performer_id, resolved)
        if self.event_bus is not None:
            payload = {"performer_id": performer_id, "animation": animation, "layer": layer, "elapsed": elapsed}
            if retarget_report is not None:
                payload["retarget_report"] = retarget_report.to_dict()
            self.event_bus.emit(
                "performer:animated",
                payload,
                source="animation_runtime",
            )
        return resolved

    def apply_sequence(self, sequence: AnimationSequence, elapsed: float) -> Dict[str, Dict]:
        applied: Dict[str, Dict] = {}
        for clip in sequence.active_clips(elapsed):
            applied[clip.performer_id] = self.apply_animation(
                clip.performer_id,
                clip.animation,
                elapsed - clip.start_time,
                layer=clip.layer,
                priority=clip.priority,
            )
        return applied


def preset_duration(animation_name: str) -> float:
    animation = normalize_animation_name(animation_name)
    return float(ANIMATION_PRESETS[animation]["duration"])


def build_basic_recovery_sequence(performer_id: str = "male_part_1") -> AnimationSequence:
    """Sit, stand, walk, fall, recover, sit, stand."""

    timeline = [
        ("sit", 0.0),
        ("sit_to_stand", 3.0),
        ("walk", 5.4),
        ("fall_down", 8.0),
        ("get_back_up", 10.8),
        ("sit", 14.4),
        ("sit_to_stand", 17.8),
        ("stand", 20.2),
    ]
    return _sequence_from_timeline("basic_recovery_sequence", performer_id, timeline)


def build_waltz_duet_sequence(male_id: str = "male_part_1", female_id: str = "sheila") -> AnimationSequence:
    """Create synchronized male and Sheila waltz parts."""

    clips = [
        AnimationClip(male_id, "waltz_box_step_male", 0.0, 12.0, layer="scripted", priority=100),
        AnimationClip(female_id, "waltz_box_step_female", 0.0, 12.0, layer="scripted", priority=100),
    ]
    return AnimationSequence("sheila_waltz_duet", clips)


def build_full_animation_rehearsal_sequence(male_id: str = "male_part_1", female_id: str = "sheila") -> AnimationSequence:
    basic = build_basic_recovery_sequence(male_id)
    clips = list(basic.clips)
    sheila_start = basic.duration + 0.5
    clips.extend([
        AnimationClip(female_id, "feminine_high_heel_walk", sheila_start, 6.0, layer="scripted", priority=100),
        AnimationClip(male_id, "waltz_box_step_male", sheila_start + 6.5, 12.0, layer="scripted", priority=100),
        AnimationClip(female_id, "waltz_box_step_female", sheila_start + 6.5, 12.0, layer="scripted", priority=100),
    ])
    return AnimationSequence("full_animation_rehearsal_male_and_sheila", clips)


def export_sequences(sequences: Iterable[AnimationSequence]) -> Dict:
    return {"sequences": [sequence.to_dict() for sequence in sequences], "presets": sorted(ANIMATION_PRESETS.keys())}


def _sequence_from_timeline(sequence_id: str, performer_id: str, timeline: List[tuple]) -> AnimationSequence:
    clips = [
        AnimationClip(performer_id, animation, start, preset_duration(animation), layer="scripted", priority=100)
        for animation, start in timeline
    ]
    return AnimationSequence(sequence_id, clips)
