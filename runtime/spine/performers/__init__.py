"""Performer authority systems for the PubCast runtime spine."""

from .animation_authority import AnimationAuthority
from .animation_presets import get_animation_presets, normalize_animation_name, validate_animation_presets
from .animation_runtime import (
    AnimationClip,
    AnimationRuntime,
    AnimationSequence,
    build_basic_recovery_sequence,
    build_full_animation_rehearsal_sequence,
    build_waltz_duet_sequence,
    export_sequences,
)
from .contact import ContactObject, ContactResolution, ContactResolver
from .interaction_fit import InteractionFitCoordinator, InteractionFitReport
from .locomotion import LocomotionSystem
from .mocap_diagnostics import diagnose_mocap_skeleton_boundary
from .motion_feedback import MotionFeedbackCoordinator, MotionFeedbackSignal
from .motion_retargeting import (
    MotionRetargeter,
    RETARGET_MODE_LITERAL_SOURCE,
    RETARGET_MODE_TARGET_EQUIVALENT,
    RetargetReport,
    SkeletonMetrics,
    measure_skeleton_metrics,
)
from .performer_state import PerformerState
from .replication import build_replication_snapshot
from .skeleton_binding import create_avatar_skeleton, get_bind_pose, serialize_avatar_skeleton
from .visual_patch import VoxelPatchSpec, VisualPatchCoordinator, parse_visual_patch_request

__all__ = [
    "AnimationAuthority",
    "AnimationClip",
    "AnimationRuntime",
    "AnimationSequence",
    "ContactObject",
    "ContactResolution",
    "ContactResolver",
    "InteractionFitCoordinator",
    "InteractionFitReport",
    "LocomotionSystem",
    "MotionFeedbackCoordinator",
    "MotionFeedbackSignal",
    "MotionRetargeter",
    "PerformerState",
    "RETARGET_MODE_LITERAL_SOURCE",
    "RETARGET_MODE_TARGET_EQUIVALENT",
    "RetargetReport",
    "SkeletonMetrics",
    "VisualPatchCoordinator",
    "VoxelPatchSpec",
    "build_basic_recovery_sequence",
    "build_full_animation_rehearsal_sequence",
    "build_replication_snapshot",
    "build_waltz_duet_sequence",
    "create_avatar_skeleton",
    "diagnose_mocap_skeleton_boundary",
    "export_sequences",
    "get_animation_presets",
    "get_bind_pose",
    "measure_skeleton_metrics",
    "normalize_animation_name",
    "parse_visual_patch_request",
    "serialize_avatar_skeleton",
    "validate_animation_presets",
]
