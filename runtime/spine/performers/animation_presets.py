"""Canonical animation preset metadata and validation."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


ANIMATION_PRESETS: Dict[str, Dict[str, Any]] = {
    "walk": {
        "duration": 2.0,
        "loop": True,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0, 0]}, {"time": 2, "value": [0, 0, -2]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0.4, 0, 0]}, {"time": 1, "value": [-0.4, 0, 0]}, {"time": 2, "value": [0.4, 0, 0]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [-0.4, 0, 0]}, {"time": 1, "value": [0.4, 0, 0]}, {"time": 2, "value": [-0.4, 0, 0]}]},
            "upperarm_l": {"rotation": [{"time": 0, "value": [-0.3, 0, 0]}, {"time": 1, "value": [0.3, 0, 0]}, {"time": 2, "value": [-0.3, 0, 0]}]},
            "upperarm_r": {"rotation": [{"time": 0, "value": [0.3, 0, 0]}, {"time": 1, "value": [-0.3, 0, 0]}, {"time": 2, "value": [0.3, 0, 0]}]},
        },
    },
    "sit": {
        "duration": 3.0,
        "loop": False,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0, 0]}, {"time": 3, "value": [0, -0.6, 0]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 3, "value": [1.57, 0, 0]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 3, "value": [1.57, 0, 0]}]},
            "calf_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 3, "value": [-1.57, 0, 0]}]},
            "calf_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 3, "value": [-1.57, 0, 0]}]},
        },
    },
    "wave": {
        "duration": 2.0,
        "loop": False,
        "tracks": {
            "upperarm_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 0.5, "value": [0, 0, -1.57]}]},
            "lowerarm_r": {"rotation": [{"time": 0.5, "value": [0, 0, 0]}, {"time": 0.7, "value": [0, 0.6, 0]}, {"time": 0.9, "value": [0, -0.6, 0]}, {"time": 1.1, "value": [0, 0.6, 0]}]},
        },
    },
    "type": {
        "duration": 4.0,
        "loop": True,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, -0.6, 0]}]},
            "upperarm_l": {"rotation": [{"time": 0, "value": [-0.5, 0, 0.3]}]},
            "upperarm_r": {"rotation": [{"time": 0, "value": [-0.5, 0, -0.3]}]},
            "lowerarm_l": {"rotation": [{"time": 0, "value": [-0.8, 0, 0]}]},
            "lowerarm_r": {"rotation": [{"time": 0, "value": [-0.8, 0, 0]}]},
        },
    },
    "idle": {
        "duration": 4.0,
        "loop": True,
        "tracks": {
            "chest": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 2, "value": [0.03, 0, 0]}, {"time": 4, "value": [0, 0, 0]}]},
        },
    },
    "stand": {
        "duration": 1.0,
        "loop": False,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
            "hips": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
            "chest": {"rotation": [{"time": 0, "value": [0.03, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
            "calf_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
            "calf_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0, 0]}]},
        },
    },
    "sit_to_stand": {
        "duration": 2.2,
        "loop": False,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, -0.6, 0]}, {"time": 1.1, "value": [0, -0.18, 0.04]}, {"time": 2.2, "value": [0, 0, 0]}]},
            "hips": {"rotation": [{"time": 0, "value": [-0.15, 0, 0]}, {"time": 1.1, "value": [0.28, 0, 0]}, {"time": 2.2, "value": [0, 0, 0]}]},
            "chest": {"rotation": [{"time": 0, "value": [0.12, 0, 0]}, {"time": 1.1, "value": [-0.2, 0, 0]}, {"time": 2.2, "value": [0, 0, 0]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [1.57, 0, 0]}, {"time": 1.1, "value": [0.72, 0, 0]}, {"time": 2.2, "value": [0, 0, 0]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [1.57, 0, 0]}, {"time": 1.1, "value": [0.72, 0, 0]}, {"time": 2.2, "value": [0, 0, 0]}]},
            "calf_l": {"rotation": [{"time": 0, "value": [-1.57, 0, 0]}, {"time": 1.1, "value": [-0.55, 0, 0]}, {"time": 2.2, "value": [0, 0, 0]}]},
            "calf_r": {"rotation": [{"time": 0, "value": [-1.57, 0, 0]}, {"time": 1.1, "value": [-0.55, 0, 0]}, {"time": 2.2, "value": [0, 0, 0]}]},
        },
    },
    "fall_down": {
        "duration": 2.4,
        "loop": False,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0, 0]}, {"time": 0.8, "value": [0, -0.25, 0.18]}, {"time": 2.4, "value": [0, -0.88, 0.62]}]},
            "hips": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 0.8, "value": [0.5, 0, 0.12]}, {"time": 2.4, "value": [1.35, 0, 0.25]}]},
            "chest": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 0.8, "value": [0.35, 0, -0.12]}, {"time": 2.4, "value": [1.15, 0, -0.25]}]},
            "head": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 2.4, "value": [-0.35, 0, 0.08]}]},
            "upperarm_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1.2, "value": [-0.7, 0, 0.35]}, {"time": 2.4, "value": [-0.35, 0, 0.9]}]},
            "upperarm_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 1.2, "value": [-0.7, 0, -0.35]}, {"time": 2.4, "value": [-0.35, 0, -0.9]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 2.4, "value": [0.9, 0, 0.2]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 2.4, "value": [0.65, 0, -0.25]}]},
            "calf_l": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 2.4, "value": [-0.8, 0, 0]}]},
            "calf_r": {"rotation": [{"time": 0, "value": [0, 0, 0]}, {"time": 2.4, "value": [-0.45, 0, 0]}]},
        },
    },
    "get_back_up": {
        "duration": 3.2,
        "loop": False,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, -0.88, 0.62]}, {"time": 1.4, "value": [0, -0.44, 0.25]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "hips": {"rotation": [{"time": 0, "value": [1.35, 0, 0.25]}, {"time": 1.4, "value": [0.72, 0, 0.05]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "chest": {"rotation": [{"time": 0, "value": [1.15, 0, -0.25]}, {"time": 1.4, "value": [-0.25, 0, 0]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "head": {"rotation": [{"time": 0, "value": [-0.35, 0, 0.08]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "upperarm_l": {"rotation": [{"time": 0, "value": [-0.35, 0, 0.9]}, {"time": 1.4, "value": [-0.9, 0, 0.45]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "upperarm_r": {"rotation": [{"time": 0, "value": [-0.35, 0, -0.9]}, {"time": 1.4, "value": [-0.9, 0, -0.45]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0.9, 0, 0.2]}, {"time": 1.4, "value": [1.1, 0, 0]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [0.65, 0, -0.25]}, {"time": 1.4, "value": [0.9, 0, 0]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "calf_l": {"rotation": [{"time": 0, "value": [-0.8, 0, 0]}, {"time": 3.2, "value": [0, 0, 0]}]},
            "calf_r": {"rotation": [{"time": 0, "value": [-0.45, 0, 0]}, {"time": 3.2, "value": [0, 0, 0]}]},
        },
    },
    "feminine_high_heel_walk": {
        "duration": 2.0,
        "loop": True,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0.045, 0]}, {"time": 1, "value": [0.035, 0.06, -0.95]}, {"time": 2, "value": [0, 0.045, -1.9]}]},
            "hips": {"rotation": [{"time": 0, "value": [0, 0, 0.11]}, {"time": 0.5, "value": [0, 0, -0.11]}, {"time": 1, "value": [0, 0, 0.11]}, {"time": 1.5, "value": [0, 0, -0.11]}, {"time": 2, "value": [0, 0, 0.11]}]},
            "chest": {"rotation": [{"time": 0, "value": [0.03, 0, -0.055]}, {"time": 1, "value": [0.03, 0, 0.055]}, {"time": 2, "value": [0.03, 0, -0.055]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0.33, 0, 0.04]}, {"time": 1, "value": [-0.28, 0, -0.02]}, {"time": 2, "value": [0.33, 0, 0.04]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [-0.28, 0, 0.02]}, {"time": 1, "value": [0.33, 0, -0.04]}, {"time": 2, "value": [-0.28, 0, 0.02]}]},
            "calf_l": {"rotation": [{"time": 0, "value": [-0.2, 0, 0]}, {"time": 1, "value": [0.12, 0, 0]}, {"time": 2, "value": [-0.2, 0, 0]}]},
            "calf_r": {"rotation": [{"time": 0, "value": [0.12, 0, 0]}, {"time": 1, "value": [-0.2, 0, 0]}, {"time": 2, "value": [0.12, 0, 0]}]},
            "foot_l": {"rotation": [{"time": 0, "value": [-0.28, 0, 0.03]}, {"time": 1, "value": [-0.42, 0, 0]}, {"time": 2, "value": [-0.28, 0, 0.03]}]},
            "foot_r": {"rotation": [{"time": 0, "value": [-0.42, 0, 0]}, {"time": 1, "value": [-0.28, 0, -0.03]}, {"time": 2, "value": [-0.42, 0, 0]}]},
        },
    },
    "waltz_box_step_male": {
        "duration": 3.0,
        "loop": True,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0, 0]}, {"time": 1, "value": [0, 0.02, -0.42]}, {"time": 2, "value": [-0.32, 0.03, -0.42]}, {"time": 3, "value": [0, 0, 0]}]},
            "hips": {"rotation": [{"time": 0, "value": [0, 0, 0.04]}, {"time": 1, "value": [0, 0, -0.04]}, {"time": 2, "value": [0, 0, 0.04]}, {"time": 3, "value": [0, 0, 0.04]}]},
            "chest": {"rotation": [{"time": 0, "value": [0.03, 0, -0.03]}, {"time": 1.5, "value": [0.04, 0, 0.03]}, {"time": 3, "value": [0.03, 0, -0.03]}]},
            "upperarm_l": {"rotation": [{"time": 0, "value": [-0.2, 0, 0.65]}, {"time": 3, "value": [-0.2, 0, 0.65]}]},
            "upperarm_r": {"rotation": [{"time": 0, "value": [-0.18, 0, -0.42]}, {"time": 3, "value": [-0.18, 0, -0.42]}]},
            "lowerarm_l": {"rotation": [{"time": 0, "value": [-0.12, 0, 0.35]}, {"time": 3, "value": [-0.12, 0, 0.35]}]},
            "lowerarm_r": {"rotation": [{"time": 0, "value": [-0.22, 0, -0.2]}, {"time": 3, "value": [-0.22, 0, -0.2]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [0.22, 0, 0]}, {"time": 1.5, "value": [-0.18, 0, 0]}, {"time": 3, "value": [0.22, 0, 0]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [-0.18, 0, 0]}, {"time": 1.5, "value": [0.22, 0, 0]}, {"time": 3, "value": [-0.18, 0, 0]}]},
        },
    },
    "waltz_box_step_female": {
        "duration": 3.0,
        "loop": True,
        "tracks": {
            "root": {"position": [{"time": 0, "value": [0, 0.035, 0]}, {"time": 1, "value": [0, 0.055, 0.42]}, {"time": 2, "value": [0.32, 0.055, 0.42]}, {"time": 3, "value": [0, 0.035, 0]}]},
            "hips": {"rotation": [{"time": 0, "value": [0, 0, -0.08]}, {"time": 1, "value": [0, 0, 0.08]}, {"time": 2, "value": [0, 0, -0.08]}, {"time": 3, "value": [0, 0, -0.08]}]},
            "chest": {"rotation": [{"time": 0, "value": [0.02, 0, 0.055]}, {"time": 1.5, "value": [0.02, 0, -0.055]}, {"time": 3, "value": [0.02, 0, 0.055]}]},
            "upperarm_l": {"rotation": [{"time": 0, "value": [-0.18, 0, 0.42]}, {"time": 3, "value": [-0.18, 0, 0.42]}]},
            "upperarm_r": {"rotation": [{"time": 0, "value": [-0.18, 0, -0.65]}, {"time": 3, "value": [-0.18, 0, -0.65]}]},
            "lowerarm_l": {"rotation": [{"time": 0, "value": [-0.22, 0, 0.2]}, {"time": 3, "value": [-0.22, 0, 0.2]}]},
            "lowerarm_r": {"rotation": [{"time": 0, "value": [-0.12, 0, -0.35]}, {"time": 3, "value": [-0.12, 0, -0.35]}]},
            "thigh_l": {"rotation": [{"time": 0, "value": [-0.17, 0, 0.02]}, {"time": 1.5, "value": [0.24, 0, -0.03]}, {"time": 3, "value": [-0.17, 0, 0.02]}]},
            "thigh_r": {"rotation": [{"time": 0, "value": [0.24, 0, -0.02]}, {"time": 1.5, "value": [-0.17, 0, 0.03]}, {"time": 3, "value": [0.24, 0, -0.02]}]},
            "foot_l": {"rotation": [{"time": 0, "value": [-0.32, 0, 0]}, {"time": 1.5, "value": [-0.2, 0, 0.03]}, {"time": 3, "value": [-0.32, 0, 0]}]},
            "foot_r": {"rotation": [{"time": 0, "value": [-0.2, 0, -0.03]}, {"time": 1.5, "value": [-0.32, 0, 0]}, {"time": 3, "value": [-0.2, 0, -0.03]}]},
        },
    },
}


ANIMATION_ALIASES = {
    "sit down and watch tv on couch": "sit",
    "sit": "sit",
    "couch": "sit",
    "chair": "sit",
    "typing": "type",
    "typewriter": "type",
    "type": "type",
    "walk": "walk",
    "walking": "walk",
    "high heel walk": "feminine_high_heel_walk",
    "high_heel_walk": "feminine_high_heel_walk",
    "feminine_high_heel_walk": "feminine_high_heel_walk",
    "feminine walk": "feminine_high_heel_walk",
    "sheila walk": "feminine_high_heel_walk",
    "sheila high heel walk": "feminine_high_heel_walk",
    "stand": "stand",
    "standing": "stand",
    "sit to stand": "sit_to_stand",
    "sit_to_stand": "sit_to_stand",
    "fall": "fall_down",
    "fall down": "fall_down",
    "fall_down": "fall_down",
    "get up": "get_back_up",
    "get back up": "get_back_up",
    "get_back_up": "get_back_up",
    "recover": "get_back_up",
    "waltz": "waltz_box_step_male",
    "waltz male": "waltz_box_step_male",
    "male waltz": "waltz_box_step_male",
    "waltz_box_step_male": "waltz_box_step_male",
    "waltz female": "waltz_box_step_female",
    "female waltz": "waltz_box_step_female",
    "sheila waltz": "waltz_box_step_female",
    "shela waltz": "waltz_box_step_female",
    "waltz_box_step_female": "waltz_box_step_female",
    "wave": "wave",
    "idle": "idle",
}


@dataclass(frozen=True)
class AnimationPresetIssue:
    severity: str
    preset: str
    message: str


def normalize_animation_name(raw_name: str, default: str = "idle") -> str:
    text = " ".join(str(raw_name or "").lower().split())
    if not text:
        return default
    if text in ANIMATION_ALIASES:
        return ANIMATION_ALIASES[text]
    for key, preset in sorted(ANIMATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if key in text:
            return preset
    return text if text in ANIMATION_PRESETS else default


def validate_animation_presets(skeleton: Any, presets: Optional[Dict[str, Dict[str, Any]]] = None) -> List[AnimationPresetIssue]:
    presets = presets or ANIMATION_PRESETS
    joints = set(getattr(skeleton, "joints", {}).keys())
    issues: List[AnimationPresetIssue] = []
    for preset_name, preset in presets.items():
        duration = preset.get("duration")
        if not isinstance(duration, (int, float)) or duration <= 0:
            issues.append(AnimationPresetIssue("error", preset_name, "duration must be a positive number"))
        tracks = preset.get("tracks", {})
        if not isinstance(tracks, dict) or not tracks:
            issues.append(AnimationPresetIssue("error", preset_name, "tracks must be a non-empty object"))
            continue
        for joint_name, track in tracks.items():
            if joints and joint_name not in joints:
                issues.append(AnimationPresetIssue("error", preset_name, f"track references unknown skeleton joint {joint_name!r}"))
            for channel, keyframes in track.items():
                expected = 3 if channel in {"position", "rotation"} else None
                if not isinstance(keyframes, list) or not keyframes:
                    issues.append(AnimationPresetIssue("error", preset_name, f"{joint_name}.{channel} has no keyframes"))
                    continue
                _validate_keyframes(issues, preset_name, joint_name, channel, keyframes, duration, expected)
    return issues


def sample_preset_pose(preset_name: str, elapsed: float, presets: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, List[float]]]:
    presets = presets or ANIMATION_PRESETS
    preset = presets[normalize_animation_name(preset_name)]
    duration = float(preset["duration"])
    t = float(elapsed)
    if preset.get("loop"):
        t = t % duration
    else:
        t = min(max(0.0, t), duration)
    pose: Dict[str, Dict[str, List[float]]] = {}
    for joint_name, track in preset["tracks"].items():
        pose[joint_name] = {}
        for channel, keyframes in track.items():
            pose[joint_name][channel] = _sample_keyframes(keyframes, t)
    return pose


def get_animation_presets() -> Dict[str, Dict[str, Any]]:
    return copy.deepcopy(ANIMATION_PRESETS)


def _validate_keyframes(
    issues: List[AnimationPresetIssue],
    preset_name: str,
    joint_name: str,
    channel: str,
    keyframes: Iterable[Dict[str, Any]],
    duration: float,
    expected_len: Optional[int],
):
    previous_time = -1.0
    for frame in keyframes:
        frame_time = frame.get("time")
        value = frame.get("value")
        if not isinstance(frame_time, (int, float)):
            issues.append(AnimationPresetIssue("error", preset_name, f"{joint_name}.{channel} keyframe missing numeric time"))
            continue
        if frame_time < previous_time:
            issues.append(AnimationPresetIssue("error", preset_name, f"{joint_name}.{channel} keyframes are not sorted"))
        if frame_time < 0 or frame_time > duration:
            issues.append(AnimationPresetIssue("warning", preset_name, f"{joint_name}.{channel} keyframe time is outside duration"))
        previous_time = frame_time
        if expected_len is not None and (not isinstance(value, list) or len(value) != expected_len):
            issues.append(AnimationPresetIssue("error", preset_name, f"{joint_name}.{channel} value must be length {expected_len}"))


def _sample_keyframes(keyframes: List[Dict[str, Any]], t: float) -> List[float]:
    if len(keyframes) == 1 or t <= keyframes[0]["time"]:
        return list(keyframes[0]["value"])
    for index in range(1, len(keyframes)):
        before = keyframes[index - 1]
        after = keyframes[index]
        if t <= after["time"]:
            span = max(float(after["time"] - before["time"]), 1e-9)
            alpha = (t - float(before["time"])) / span
            return [
                float(before["value"][axis]) + (float(after["value"][axis]) - float(before["value"][axis])) * alpha
                for axis in range(len(before["value"]))
            ]
    return list(keyframes[-1]["value"])
