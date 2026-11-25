"""
PubCast GLB Motion Retargeter
=============================
Server-side schema helper for the visible motion link. This does not render; it
standardizes pipeline commands into a GLB skeleton contract consumed by
static/avatar_glb_motion_consumer.js.

Why this exists:
- BehaviorMotionPipeline already emits semantic/mocap commands.
- The renderer needs stable bone names, layer names, and conservative rotations.
- This module provides validation and a tiny retarget contract for tests/tools.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Mapping, Optional
import math

CANONICAL_BONES = {
    "hips", "spine", "chest", "neck", "head",
    "shoulder_left", "arm_left", "forearm_left", "hand_left",
    "shoulder_right", "arm_right", "forearm_right", "hand_right",
    "leg_left", "leg_right",
}

BONE_ALIASES: Dict[str, List[str]] = {
    "hips": ["hips", "pelvis", "mixamorigHips"],
    "spine": ["spine", "spine_01", "mixamorigSpine"],
    "chest": ["chest", "spine_02", "upper_chest", "mixamorigSpine1"],
    "neck": ["neck", "mixamorigNeck"],
    "head": ["head", "mixamorigHead"],
    "shoulder_left": ["shoulder_left", "left_shoulder", "mixamorigLeftShoulder"],
    "arm_left": ["arm_left", "left_upper_arm", "mixamorigLeftArm"],
    "forearm_left": ["forearm_left", "left_forearm", "mixamorigLeftForeArm"],
    "hand_left": ["hand_left", "left_hand", "mixamorigLeftHand"],
    "shoulder_right": ["shoulder_right", "right_shoulder", "mixamorigRightShoulder"],
    "arm_right": ["arm_right", "right_upper_arm", "mixamorigRightArm"],
    "forearm_right": ["forearm_right", "right_forearm", "mixamorigRightForeArm"],
    "hand_right": ["hand_right", "right_hand", "mixamorigRightHand"],
    "leg_left": ["leg_left", "left_upper_leg", "mixamorigLeftUpLeg"],
    "leg_right": ["leg_right", "right_upper_leg", "mixamorigRightUpLeg"],
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def clamp_rotation(rot: Iterable[float], limit: float = 65.0) -> List[float]:
    values = list(rot)
    while len(values) < 3:
        values.append(0.0)
    return [round(clamp(values[0], -limit, limit), 4), round(clamp(values[1], -limit, limit), 4), round(clamp(values[2], -limit, limit), 4)]


@dataclass
class GLBBoneTransform:
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    position: Optional[List[float]] = None
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        data = {"rotation": clamp_rotation(self.rotation), "weight": clamp(self.weight, 0.0, 1.0)}
        if self.position is not None:
            p = list(self.position)
            while len(p) < 3:
                p.append(0.0)
            data["position"] = [round(float(v), 4) for v in p[:3]]
        return data


@dataclass
class GLBRetargetPacket:
    avatar_id: str
    timestamp_ms: int
    source: str = "glb_motion_retargeter"
    bones: Dict[str, GLBBoneTransform] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_pose(self) -> Dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "source": self.source,
            "bones": {bone: transform.to_dict() for bone, transform in sorted(self.bones.items()) if bone in CANONICAL_BONES},
            "metadata": dict(self.metadata),
        }

    def to_motion_command(self, weight: float = 1.0, duration_ms: int = 120) -> Dict[str, Any]:
        return {
            "avatar_id": self.avatar_id,
            "kind": "mocap_pose",
            "layer": "MOCAP_BASE",
            "weight": clamp(weight, 0.0, 1.0),
            "duration_ms": int(duration_ms),
            "blend_in_ms": 50,
            "blend_out_ms": 80,
            "priority": 70,
            "source": self.source,
            "reason": "retargeted GLB skeleton packet",
            "pose": self.to_pose(),
            "metadata": self.metadata,
        }


def normalize_pose_command(command: Mapping[str, Any], avatar_id: Optional[str] = None) -> Dict[str, Any]:
    """Return a renderer-safe mocap_pose command with canonical bones only."""
    cmd = dict(command or {})
    pose = dict(cmd.get("pose") or {})
    bones_raw = pose.get("bones") or {}
    bones: Dict[str, Any] = {}
    for name, transform in bones_raw.items():
        if name not in CANONICAL_BONES or not isinstance(transform, Mapping):
            continue
        out: Dict[str, Any] = {}
        if "rotation" in transform:
            out["rotation"] = clamp_rotation(transform["rotation"])
        if "position" in transform:
            pos = list(transform["position"])
            while len(pos) < 3:
                pos.append(0.0)
            out["position"] = [round(float(v), 4) for v in pos[:3]]
        if out:
            bones[name] = out
    cmd["avatar_id"] = str(avatar_id or cmd.get("avatar_id") or "manny")
    cmd["kind"] = "mocap_pose"
    cmd["pose"] = dict(pose, bones=bones)
    cmd.setdefault("layer", "MOCAP_BASE")
    cmd.setdefault("priority", 70)
    cmd.setdefault("duration_ms", 120)
    return cmd


def retarget_from_runtime_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize all mocap_pose commands inside an avatar_motion_commands event."""
    evt = dict(event or {})
    payload = dict(evt.get("payload") or evt)
    avatar_id = payload.get("avatar_id") or payload.get("avatarId") or "manny"
    commands = []
    for cmd in payload.get("commands") or []:
        if isinstance(cmd, Mapping) and cmd.get("kind") == "mocap_pose":
            commands.append(normalize_pose_command(cmd, avatar_id=str(avatar_id)))
        else:
            commands.append(dict(cmd))
    payload["commands"] = commands
    if "payload" in evt:
        evt["payload"] = payload
        return evt
    return payload
