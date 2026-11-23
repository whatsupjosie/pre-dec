"""Diagnostics for mocap joint names crossing into the PubCast skeleton."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


MOCAP_TO_PUBCAST_JOINTS: Dict[str, str] = {
    "hips": "hips",
    "spine": "spine_01",
    "chest": "chest",
    "neck": "neck",
    "head": "head",
    "left_shoulder": "upperarm_l",
    "left_elbow": "lowerarm_l",
    "left_wrist": "hand_l",
    "left_hand": "hand_l",
    "right_shoulder": "upperarm_r",
    "right_elbow": "lowerarm_r",
    "right_wrist": "hand_r",
    "right_hand": "hand_r",
    "left_hip": "thigh_l",
    "left_knee": "calf_l",
    "left_ankle": "foot_l",
    "left_foot": "foot_l",
    "right_hip": "thigh_r",
    "right_knee": "calf_r",
    "right_ankle": "foot_r",
    "right_foot": "foot_r",
}


def diagnose_mocap_skeleton_boundary(
    skeleton: Any,
    incoming_joint_names: Optional[Iterable[str]] = None,
    mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, List[str]]:
    """Return missing or unknown joint-name boundary problems."""

    mapping = mapping or MOCAP_TO_PUBCAST_JOINTS
    incoming = set(incoming_joint_names or mapping.keys())
    skeleton_joints = set(getattr(skeleton, "joints", {}).keys())
    missing_skeleton_targets = sorted({
        target for source, target in mapping.items()
        if source in incoming and skeleton_joints and target not in skeleton_joints
    })
    unmapped_incoming = sorted(joint for joint in incoming if joint not in mapping)
    mapped = sorted(joint for joint in incoming if joint in mapping and mapping[joint] not in missing_skeleton_targets)
    return {
        "mapped": mapped,
        "missing_skeleton_targets": missing_skeleton_targets,
        "unmapped_incoming": unmapped_incoming,
    }

