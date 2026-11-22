"""Elastic motion retargeting for applying source motion to varied avatar rigs."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


Vector3 = List[float]
Pose = Dict[str, Dict[str, List[float]]]

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

REFERENCE_PROPORTIONS = {
    "height": 1.7,
    "leg": 0.82,
    "arm": 0.53,
    "spine": 0.8,
    "hip_width": 0.2,
}

RETARGET_MODE_TARGET_EQUIVALENT = "target_equivalent"
RETARGET_MODE_LITERAL_SOURCE = "literal_source"
RETARGET_MODES = {RETARGET_MODE_TARGET_EQUIVALENT, RETARGET_MODE_LITERAL_SOURCE}

DEFAULT_ROTATION_LIMITS = {
    "root": [(-math.pi, math.pi), (-math.pi, math.pi), (-math.pi, math.pi)],
    "hips": [(-1.45, 1.45), (-0.75, 0.75), (-0.95, 0.95)],
    "spine": [(-1.15, 1.15), (-0.75, 0.75), (-0.8, 0.8)],
    "head": [(-1.0, 0.85), (-1.0, 1.0), (-0.7, 0.7)],
    "arm": [(-2.25, 2.25), (-1.75, 1.75), (-1.75, 1.75)],
    "hand": [(-1.35, 1.35), (-1.15, 1.15), (-1.15, 1.15)],
    "leg": [(-1.8, 1.8), (-0.65, 0.65), (-0.85, 0.85)],
    "foot": [(-1.0, 0.65), (-0.55, 0.55), (-0.55, 0.55)],
    "finger": [(-1.0, 1.0), (-0.55, 0.55), (-0.55, 0.55)],
    "auxiliary": [(-math.pi, math.pi), (-math.pi, math.pi), (-math.pi, math.pi)],
}

SOURCE_JOINT_ALIASES = {
    "pelvis": "hips",
    "torso": "chest",
    "spine": "spine_02",
    "shoulder_l": "upperarm_l",
    "shoulder_r": "upperarm_r",
    "elbow_l": "lowerarm_l",
    "elbow_r": "lowerarm_r",
    "wrist_l": "hand_l",
    "wrist_r": "hand_r",
    "hip_l": "thigh_l",
    "hip_r": "thigh_r",
    "knee_l": "calf_l",
    "knee_r": "calf_r",
    "ankle_l": "foot_l",
    "ankle_r": "foot_r",
    "front_leg_l": "upperarm_l",
    "front_leg_r": "upperarm_r",
    "front_knee_l": "lowerarm_l",
    "front_knee_r": "lowerarm_r",
    "front_paw_l": "hand_l",
    "front_paw_r": "hand_r",
    "front_foot_l": "hand_l",
    "front_foot_r": "hand_r",
    "hind_leg_l": "thigh_l",
    "hind_leg_r": "thigh_r",
    "hind_knee_l": "calf_l",
    "hind_knee_r": "calf_r",
    "hind_paw_l": "foot_l",
    "hind_paw_r": "foot_r",
    "hind_foot_l": "foot_l",
    "hind_foot_r": "foot_r",
    "paw_l": "hand_l",
    "paw_r": "hand_r",
    "tail": "hips",
    "tail_base": "hips",
    "tail_mid": "spine_03",
    "tail_tip": "chest",
    "ear_l": "head",
    "ear_r": "head",
    "muzzle": "head",
    "snout": "head",
    "beak": "head",
    "wing_l": "upperarm_l",
    "wing_r": "upperarm_r",
    "wing_mid_l": "lowerarm_l",
    "wing_mid_r": "lowerarm_r",
    "wing_tip_l": "hand_l",
    "wing_tip_r": "hand_r",
    "leg_l": "thigh_l",
    "leg_r": "thigh_r",
    "lower_leg_l": "calf_l",
    "lower_leg_r": "calf_r",
    "talon_l": "foot_l",
    "talon_r": "foot_r",
    "claw_l": "foot_l",
    "claw_r": "foot_r",
}

SOURCE_ATTENUATION = {
    "tail": 0.25,
    "tail_base": 0.28,
    "tail_mid": 0.2,
    "tail_tip": 0.15,
    "ear_l": 0.12,
    "ear_r": 0.12,
    "muzzle": 0.18,
    "snout": 0.18,
}

TARGET_JOINT_CANDIDATES = {
    "chest": ["torso", "body"],
    "head": ["skull", "beak", "muzzle"],
    "upperarm_l": ["wing_l", "front_leg_l", "flipper_l"],
    "upperarm_r": ["wing_r", "front_leg_r", "flipper_r"],
    "lowerarm_l": ["wing_mid_l", "wing_l", "front_knee_l", "flipper_mid_l"],
    "lowerarm_r": ["wing_mid_r", "wing_r", "front_knee_r", "flipper_mid_r"],
    "hand_l": ["wing_tip_l", "front_paw_l", "paw_l", "flipper_tip_l"],
    "hand_r": ["wing_tip_r", "front_paw_r", "paw_r", "flipper_tip_r"],
    "thigh_l": ["leg_l", "hind_leg_l", "hip_l"],
    "thigh_r": ["leg_r", "hind_leg_r", "hip_r"],
    "calf_l": ["knee_l", "lower_leg_l", "hind_knee_l"],
    "calf_r": ["knee_r", "lower_leg_r", "hind_knee_r"],
    "foot_l": ["talon_l", "claw_l", "hind_paw_l", "paw_l"],
    "foot_r": ["talon_r", "claw_r", "hind_paw_r", "paw_r"],
    "toe_l": ["talon_tip_l", "claw_tip_l"],
    "toe_r": ["talon_tip_r", "claw_tip_r"],
}


@dataclass(frozen=True)
class SkeletonMetrics:
    height: float
    leg: float
    arm: float
    spine: float
    hip_width: float

    def ratio(self, metric: str) -> float:
        reference = REFERENCE_PROPORTIONS.get(metric, 1.0)
        current = getattr(self, metric, reference)
        if reference <= 0:
            return 1.0
        return _clamp(current / reference, 0.35, 2.75)


@dataclass(frozen=True)
class RetargetReport:
    source_joint_count: int
    applied_joint_count: int
    remapped_joints: Dict[str, str] = field(default_factory=dict)
    dropped_joints: List[str] = field(default_factory=list)
    clamped_channels: List[str] = field(default_factory=list)
    invalid_channels: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    retarget_mode: str = RETARGET_MODE_TARGET_EQUIVALENT
    compatibility_score: float = 1.0
    risk_level: str = "good"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_joint_count": self.source_joint_count,
            "applied_joint_count": self.applied_joint_count,
            "remapped_joints": dict(self.remapped_joints),
            "dropped_joints": list(self.dropped_joints),
            "clamped_channels": list(self.clamped_channels),
            "invalid_channels": list(self.invalid_channels),
            "metrics": dict(self.metrics),
            "retarget_mode": self.retarget_mode,
            "compatibility_score": self.compatibility_score,
            "risk_level": self.risk_level,
            "warnings": list(self.warnings),
        }


class MotionRetargeter:
    """Convert source animation intent into the closest safe target skeleton pose."""

    def __init__(self, aliases: Optional[Dict[str, str]] = None, retarget_mode: str = RETARGET_MODE_TARGET_EQUIVALENT):
        self.aliases = dict(SOURCE_JOINT_ALIASES)
        if aliases:
            self.aliases.update(aliases)
        self.retarget_mode = _normalize_retarget_mode(retarget_mode)
        self.last_report: Optional[RetargetReport] = None

    def retarget_pose(
        self,
        pose: Pose,
        skeleton: Any,
        motion_intent: str = "",
        retarget_mode: Optional[str] = None,
    ) -> Pose:
        retargeted, report = self.retarget_pose_with_report(
            pose,
            skeleton,
            motion_intent=motion_intent,
            retarget_mode=retarget_mode,
        )
        self.last_report = report
        return retargeted

    def retarget_pose_with_report(
        self,
        pose: Pose,
        skeleton: Any,
        motion_intent: str = "",
        retarget_mode: Optional[str] = None,
    ) -> Tuple[Pose, RetargetReport]:
        mode = _normalize_retarget_mode(retarget_mode or self.retarget_mode)
        if not isinstance(pose, dict):
            pose = {}
        joints = _skeleton_joints(skeleton)
        if not joints:
            score, risk, warnings = _score_compatibility(
                source_joint_count=len(pose),
                applied_joint_count=len(pose),
                dropped_count=0,
                clamped_count=0,
                invalid_count=0,
                metrics=dict(REFERENCE_PROPORTIONS),
                no_target_skeleton=True,
            )
            report = RetargetReport(
                source_joint_count=len(pose),
                applied_joint_count=len(pose),
                metrics=dict(REFERENCE_PROPORTIONS),
                retarget_mode=mode,
                compatibility_score=score,
                risk_level=risk,
                warnings=warnings,
            )
            return copy.deepcopy(pose), report

        metrics = measure_skeleton_metrics(skeleton)
        source_traits = _infer_source_traits(pose.keys())
        retargeted: Pose = {}
        remapped: Dict[str, str] = {}
        dropped: List[str] = []
        clamped: List[str] = []
        invalid: List[str] = []

        for source_joint, channels in pose.items():
            if not isinstance(source_joint, str):
                invalid.append(str(source_joint))
                continue
            if not isinstance(channels, dict):
                invalid.append(source_joint)
                dropped.append(source_joint)
                continue
            target_joint = self._target_joint(source_joint, joints)
            if target_joint is None:
                dropped.append(source_joint)
                continue
            if target_joint != source_joint:
                remapped[source_joint] = target_joint

            target_channels = retargeted.setdefault(target_joint, {})
            attenuation = _intent_attenuation(source_joint, motion_intent) * SOURCE_ATTENUATION.get(source_joint, 1.0)
            for channel, value in channels.items():
                if channel == "position":
                    if not _is_vector_like(value):
                        invalid.append(f"{source_joint}.position")
                    target_channels[channel] = _scale_position(target_joint, value, metrics)
                elif channel == "rotation":
                    if not _is_vector_like(value):
                        invalid.append(f"{source_joint}.rotation")
                    constrained, did_clamp = _constrain_rotation(
                        target_joint,
                        source_joint,
                        value,
                        joints,
                        attenuation,
                        source_traits,
                        motion_intent,
                        mode,
                    )
                    target_channels[channel] = constrained
                    if did_clamp:
                        clamped.append(f"{target_joint}.rotation")
                else:
                    target_channels[channel] = copy.deepcopy(value)

        metric_payload = {
            "height": metrics.height,
            "leg": metrics.leg,
            "arm": metrics.arm,
            "spine": metrics.spine,
            "hip_width": metrics.hip_width,
        }
        score, risk, warnings = _score_compatibility(
            source_joint_count=len(pose),
            applied_joint_count=len(retargeted),
            dropped_count=len(dropped),
            clamped_count=len(set(clamped)),
            invalid_count=len(set(invalid)),
            metrics=metric_payload,
        )
        report = RetargetReport(
            source_joint_count=len(pose),
            applied_joint_count=len(retargeted),
            remapped_joints=remapped,
            dropped_joints=dropped,
            clamped_channels=sorted(set(clamped)),
            invalid_channels=sorted(set(invalid)),
            metrics=metric_payload,
            retarget_mode=mode,
            compatibility_score=score,
            risk_level=risk,
            warnings=warnings,
        )
        return retargeted, report

    def _target_joint(self, source_joint: str, joints: Dict[str, Any]) -> Optional[str]:
        if source_joint in joints:
            return source_joint
        alias = self.aliases.get(source_joint)
        if alias in joints:
            return alias
        for candidate in TARGET_JOINT_CANDIDATES.get(source_joint, []):
            if candidate in joints:
                return candidate
        for candidate in TARGET_JOINT_CANDIDATES.get(alias, []):
            if candidate in joints:
                return candidate
        return _nearest_parent_alias(source_joint, joints, self.aliases)


def measure_skeleton_metrics(skeleton: Any) -> SkeletonMetrics:
    joints = _skeleton_joints(skeleton)
    bind_pose = getattr(skeleton, "bind_pose", {}) or {}

    def pos(name: str) -> Optional[Vector3]:
        bind = bind_pose.get(name)
        if isinstance(bind, dict) and isinstance(bind.get("position"), list):
            return _vec3(bind["position"])
        joint = joints.get(name)
        value = getattr(joint, "position", None)
        return _vec3(value) if isinstance(value, list) and len(value) >= 3 else None

    height = _distance(pos("root"), pos("head")) or _axis_span((pos(name) for name in joints), 1) or REFERENCE_PROPORTIONS["height"]
    left_leg = _chain_length(pos("hips"), pos("thigh_l"), pos("calf_l"), pos("foot_l"))
    right_leg = _chain_length(pos("hips"), pos("thigh_r"), pos("calf_r"), pos("foot_r"))
    left_arm = _chain_length(pos("chest"), pos("upperarm_l"), pos("lowerarm_l"), pos("hand_l"))
    right_arm = _chain_length(pos("chest"), pos("upperarm_r"), pos("lowerarm_r"), pos("hand_r"))
    spine = _chain_length(pos("hips"), pos("spine_01"), pos("spine_02"), pos("spine_03"), pos("chest")) or height * 0.45
    hip_width = _distance(pos("thigh_l"), pos("thigh_r")) or REFERENCE_PROPORTIONS["hip_width"]

    return SkeletonMetrics(
        height=max(height, 0.01),
        leg=max(_average_positive(left_leg, right_leg, fallback=height * 0.48), 0.01),
        arm=max(_average_positive(left_arm, right_arm, fallback=height * 0.31), 0.01),
        spine=max(spine, 0.01),
        hip_width=max(hip_width, 0.01),
    )


def _scale_position(joint_name: str, value: Iterable[float], metrics: SkeletonMetrics) -> Vector3:
    vector = _vec3(value)
    if joint_name == "root":
        scale = metrics.ratio("height")
    elif _is_leg_joint(joint_name) or _is_foot_joint(joint_name):
        scale = metrics.ratio("leg")
    elif _is_arm_joint(joint_name) or _is_hand_joint(joint_name):
        scale = metrics.ratio("arm")
    elif _is_spine_joint(joint_name):
        scale = metrics.ratio("spine")
    else:
        scale = metrics.ratio("height")
    return [axis * scale for axis in vector]


def _intent_attenuation(source_joint: str, motion_intent: str) -> float:
    intent = " ".join(str(motion_intent or "").lower().replace("_", " ").split())
    if "sit" in intent and _is_quadruped_front_joint(source_joint):
        return 0.18
    if ("walk" in intent or "run" in intent or "dance" in intent or "waltz" in intent) and _is_quadruped_front_joint(source_joint):
        return 0.62
    if "fall" in intent and _is_quadruped_front_joint(source_joint):
        return 0.45
    return 1.0


def _constrain_rotation(
    target_joint: str,
    source_joint: str,
    value: Iterable[float],
    joints: Dict[str, Any],
    attenuation: float,
    source_traits: str,
    motion_intent: str,
    retarget_mode: str,
) -> Tuple[List[float], bool]:
    vector = _vector(value, 3)
    if len(vector) < 3:
        return copy.deepcopy(vector), False

    limits = _joint_limits(target_joint, joints.get(target_joint))
    locked_axes = set(getattr(joints.get(target_joint), "locked_axes", []) or [])
    adjusted = _target_anatomy_rotation(source_joint, target_joint, vector[:3], source_traits, motion_intent, retarget_mode)
    out = [_finite_float(adjusted[0]) * attenuation, _finite_float(adjusted[1]) * attenuation, _finite_float(adjusted[2]) * attenuation]
    clamped = attenuation != 1.0
    for axis_name, axis_index in AXIS_INDEX.items():
        before = out[axis_index]
        if axis_name in locked_axes:
            out[axis_index] = 0.0
        else:
            low, high = limits[axis_index]
            out[axis_index] = _clamp(before, low, high)
        clamped = clamped or out[axis_index] != before
    return out, clamped


def _target_anatomy_rotation(
    source_joint: str,
    target_joint: str,
    value: List[float],
    source_traits: str,
    motion_intent: str,
    retarget_mode: str,
) -> List[float]:
    out = [_finite_float(value[0]), _finite_float(value[1]), _finite_float(value[2])]
    if retarget_mode == RETARGET_MODE_LITERAL_SOURCE:
        return out
    intent = " ".join(str(motion_intent or "").lower().replace("_", " ").split())
    if source_traits == "bird" and _is_human_leg_target(target_joint):
        if "knee" in source_joint or "lower_leg" in source_joint:
            out[0] = -abs(out[0])
        elif "talon" in source_joint or "claw" in source_joint:
            out[0] = -abs(out[0]) * 0.5
        elif "walk" in intent or "run" in intent:
            out[0] = out[0] * 0.75
    return out


def _joint_limits(joint_name: str, joint: Any) -> List[Tuple[float, float]]:
    custom = getattr(joint, "rotation_limits", None)
    if isinstance(custom, dict):
        limits = []
        for axis in ("x", "y", "z"):
            value = custom.get(axis)
            if isinstance(value, tuple) and len(value) == 2:
                limits.append(_ordered_limit(value[0], value[1], DEFAULT_ROTATION_LIMITS[_joint_group(joint_name)][len(limits)]))
            elif isinstance(value, list) and len(value) == 2:
                limits.append(_ordered_limit(value[0], value[1], DEFAULT_ROTATION_LIMITS[_joint_group(joint_name)][len(limits)]))
            else:
                limits.append(DEFAULT_ROTATION_LIMITS[_joint_group(joint_name)][len(limits)])
        return limits
    return DEFAULT_ROTATION_LIMITS[_joint_group(joint_name)]


def _joint_group(joint_name: str) -> str:
    if joint_name in {"root"}:
        return "root"
    if joint_name == "hips":
        return "hips"
    if _is_spine_joint(joint_name):
        return "spine"
    if joint_name in {"head", "neck", "eye_l", "eye_r", "jaw"}:
        return "head"
    if _is_arm_joint(joint_name):
        return "arm"
    if _is_hand_joint(joint_name):
        return "hand"
    if _is_leg_joint(joint_name):
        return "leg"
    if _is_foot_joint(joint_name):
        return "foot"
    if "thumb" in joint_name or "index" in joint_name or "middle" in joint_name or "ring" in joint_name or "pinky" in joint_name:
        return "finger"
    return "auxiliary"


def _nearest_parent_alias(source_joint: str, joints: Dict[str, Any], aliases: Dict[str, str]) -> Optional[str]:
    parts = source_joint.split("_")
    while len(parts) > 1:
        parts.pop()
        alias = aliases.get("_".join(parts))
        if alias in joints:
            return alias
    return None


def _normalize_retarget_mode(retarget_mode: str) -> str:
    mode = " ".join(str(retarget_mode or "").lower().replace("-", "_").split())
    if mode in {"literal", "literal_source", "source_literal", "creature_literal", "uncanny"}:
        return RETARGET_MODE_LITERAL_SOURCE
    if mode in {"target", "natural", "equivalent", "target_equivalent", "body_equivalent", ""}:
        return RETARGET_MODE_TARGET_EQUIVALENT
    if mode not in RETARGET_MODES:
        raise ValueError(f"Unknown retarget mode: {retarget_mode!r}")
    return mode


def _skeleton_joints(skeleton: Any) -> Dict[str, Any]:
    joints = getattr(skeleton, "joints", None)
    return joints if isinstance(joints, dict) else {}


def _infer_source_traits(source_joints: Iterable[str]) -> str:
    names = {name for name in source_joints if isinstance(name, str)}
    if any("wing" in name or "talon" in name or "claw" in name or "beak" in name for name in names):
        return "bird"
    if any(name.startswith("front_") or name.startswith("hind_") or "paw" in name or "tail" in name for name in names):
        return "quadruped"
    return "generic"


def _vec3(value: Iterable[float]) -> Vector3:
    return _vector(value, 3)


def _distance(a: Optional[Vector3], b: Optional[Vector3]) -> float:
    if a is None or b is None:
        return 0.0
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def _chain_length(*points: Optional[Vector3]) -> float:
    total = 0.0
    previous = None
    for point in points:
        if point is None:
            continue
        if previous is not None:
            total += _distance(previous, point)
        previous = point
    return total


def _axis_span(points: Iterable[Optional[Vector3]], axis: int) -> float:
    values = [point[axis] for point in points if point is not None]
    return max(values) - min(values) if values else 0.0


def _average_positive(left: float, right: float, fallback: float) -> float:
    values = [value for value in (left, right) if value > 0]
    return sum(values) / len(values) if values else fallback


def _score_compatibility(
    source_joint_count: int,
    applied_joint_count: int,
    dropped_count: int,
    clamped_count: int,
    invalid_count: int,
    metrics: Dict[str, float],
    no_target_skeleton: bool = False,
) -> Tuple[float, str, List[str]]:
    if source_joint_count <= 0:
        return 1.0, "good", []

    warnings: List[str] = []
    if no_target_skeleton:
        warnings.append("no_target_skeleton")
        return 0.5, "strained", warnings

    drop_ratio = dropped_count / source_joint_count
    invalid_ratio = invalid_count / max(source_joint_count, 1)
    clamp_ratio = clamped_count / max(applied_joint_count, 1)
    score = 1.0 - (drop_ratio * 0.42) - (invalid_ratio * 0.35) - (clamp_ratio * 0.22)

    for metric, value in metrics.items():
        reference = REFERENCE_PROPORTIONS.get(metric)
        if reference is None or reference <= 0:
            continue
        ratio = _safe_ratio(value, reference)
        if ratio <= 0.4 or ratio >= 2.5:
            score -= 0.12
            warnings.append(f"extreme_{metric}_ratio")
        elif ratio <= 0.6 or ratio >= 1.9:
            score -= 0.05
            warnings.append(f"strained_{metric}_ratio")

    if drop_ratio >= 0.45:
        warnings.append("many_source_joints_dropped")
    if clamp_ratio >= 0.45:
        warnings.append("many_channels_clamped")
    if invalid_ratio > 0:
        warnings.append("invalid_source_channels_sanitized")

    score = round(_clamp(score, 0.0, 1.0), 3)
    if score >= 0.82:
        risk = "good"
    elif score >= 0.64:
        risk = "usable"
    elif score >= 0.42:
        risk = "strained"
    else:
        risk = "likely_bad"
    return score, risk, sorted(set(warnings))


def _is_vector_like(value: Any) -> bool:
    try:
        items = list(value)
    except TypeError:
        return False
    if not items:
        return False
    return all(_is_finite_number(item) for item in items[:3])


def _vector(value: Any, length: int) -> List[float]:
    try:
        items = list(value)
    except TypeError:
        items = []
    return [_finite_float(items[index]) if index < len(items) else 0.0 for index in range(length)]


def _ordered_limit(low: Any, high: Any, fallback: Tuple[float, float]) -> Tuple[float, float]:
    low_value = _finite_float(low, fallback[0])
    high_value = _finite_float(high, fallback[1])
    if low_value > high_value:
        return fallback
    return low_value, high_value


def _safe_ratio(value: Any, reference: float) -> float:
    if reference <= 0:
        return 1.0
    return _finite_float(value, reference) / reference


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _clamp(value: float, low: float, high: float) -> float:
    safe_value = _finite_float(value)
    return max(low, min(high, safe_value))


def _is_spine_joint(joint_name: str) -> bool:
    return joint_name.startswith("spine") or joint_name in {"chest", "neck"}


def _is_arm_joint(joint_name: str) -> bool:
    return "upperarm" in joint_name or "lowerarm" in joint_name or "clavicle" in joint_name or "wing" in joint_name


def _is_hand_joint(joint_name: str) -> bool:
    return joint_name.startswith("hand") or "wing_tip" in joint_name or "flipper_tip" in joint_name


def _is_leg_joint(joint_name: str) -> bool:
    return (
        "thigh" in joint_name
        or "calf" in joint_name
        or joint_name.startswith("leg")
        or "lower_leg" in joint_name
        or "knee" in joint_name
    )


def _is_foot_joint(joint_name: str) -> bool:
    return "foot" in joint_name or "toe" in joint_name or "talon" in joint_name or "claw" in joint_name


def _is_quadruped_front_joint(joint_name: str) -> bool:
    return joint_name.startswith("front_") or joint_name.startswith("paw_")


def _is_human_leg_target(joint_name: str) -> bool:
    return joint_name in {"thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r", "toe_l", "toe_r"}
