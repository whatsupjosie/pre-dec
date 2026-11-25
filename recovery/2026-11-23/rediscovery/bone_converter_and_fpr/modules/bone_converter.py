"""
bone_converter.py — Bone Name Format Converter
═══════════════════════════════════════════════════════════════════════
Converts bone names from Mixamo, Rigify, and Rokoko rig formats into
PubCast's canonical 89-bone UE5-compatible internal naming convention.

Canonical names are derived directly from rust_crate/src/skeleton.rs.
Mapping tables are module-level dicts: source_name → pubcast_name.

Rear View Foresight LLC — Feic Mo Chroí™
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Canonical PubCast bone names (from skeleton.rs add_unchecked calls) ───────

PUBCAST_BONES: frozenset = frozenset({
    # Core
    "Root", "Pelvis",
    # Spine
    "Spine_01", "Spine_02", "Spine_03",
    # Head/neck
    "Neck_01", "Head", "Jaw",
    # Arms — Left
    "Clavicle_L", "UpperArm_L", "UpperArm_Twist_L",
    "LowerArm_L", "LowerArm_Twist_L", "Hand_L",
    # Arms — Right
    "Clavicle_R", "UpperArm_R", "UpperArm_Twist_R",
    "LowerArm_R", "LowerArm_Twist_R", "Hand_R",
    # Fingers — Left
    "Thumb_01_L", "Thumb_02_L", "Thumb_03_L",
    "Index_01_L", "Index_02_L", "Index_03_L",
    "Middle_01_L", "Middle_02_L", "Middle_03_L",
    "Ring_01_L",   "Ring_02_L",   "Ring_03_L",
    "Pinky_01_L",  "Pinky_02_L",  "Pinky_03_L",
    # Fingers — Right
    "Thumb_01_R", "Thumb_02_R", "Thumb_03_R",
    "Index_01_R", "Index_02_R", "Index_03_R",
    "Middle_01_R", "Middle_02_R", "Middle_03_R",
    "Ring_01_R",   "Ring_02_R",   "Ring_03_R",
    "Pinky_01_R",  "Pinky_02_R",  "Pinky_03_R",
    # Blade arrays (fused finger proxy)
    "Blade_Array_L", "Blade_Array_R",
    # Legs — Left
    "Thigh_L", "Thigh_Twist_L", "Calf_L", "Foot_L", "Ball_L", "Toe_L",
    # Legs — Right
    "Thigh_R", "Thigh_Twist_R", "Calf_R", "Foot_R", "Ball_R", "Toe_R",
    # Tail chain
    "Tail_01", "Tail_02", "Tail_03", "Tail_04", "Tail_05",
    # Attachment sockets
    "Socket_Hand_R", "Socket_Hip_L",
})


class BoneNameFormat(str, Enum):
    MIXAMO  = "mixamo"
    RIGIFY  = "rigify"
    ROKOKO  = "rokoko"
    PUBCAST = "pubcast"   # passthrough — already native


# ── Mixamo → PubCast ──────────────────────────────────────────────────────────
# Mixamo uses "mixamorig:" prefix in FBX; strip it or pass without prefix.
# Table covers names both with and without the prefix.

_MIXAMO_TO_PUBCAST: Dict[str, str] = {
    # Core
    "Hips":                  "Pelvis",
    "mixamorig:Hips":        "Pelvis",
    # Spine
    "Spine":                 "Spine_01",
    "Spine1":                "Spine_02",
    "Spine2":                "Spine_03",
    "mixamorig:Spine":       "Spine_01",
    "mixamorig:Spine1":      "Spine_02",
    "mixamorig:Spine2":      "Spine_03",
    # Head / neck
    "Neck":                  "Neck_01",
    "Head":                  "Head",
    "mixamorig:Neck":        "Neck_01",
    "mixamorig:Head":        "Head",
    # Jaw
    "Jaw":                   "Jaw",
    "mixamorig:Jaw":         "Jaw",
    # Left arm
    "LeftShoulder":          "Clavicle_L",
    "LeftArm":               "UpperArm_L",
    "LeftForeArm":           "LowerArm_L",
    "LeftHand":              "Hand_L",
    "mixamorig:LeftShoulder": "Clavicle_L",
    "mixamorig:LeftArm":      "UpperArm_L",
    "mixamorig:LeftForeArm":  "LowerArm_L",
    "mixamorig:LeftHand":     "Hand_L",
    # Right arm
    "RightShoulder":         "Clavicle_R",
    "RightArm":              "UpperArm_R",
    "RightForeArm":          "LowerArm_R",
    "RightHand":             "Hand_R",
    "mixamorig:RightShoulder": "Clavicle_R",
    "mixamorig:RightArm":      "UpperArm_R",
    "mixamorig:RightForeArm":  "LowerArm_R",
    "mixamorig:RightHand":     "Hand_R",
    # Left fingers
    "LeftHandThumb1":        "Thumb_01_L",
    "LeftHandThumb2":        "Thumb_02_L",
    "LeftHandThumb3":        "Thumb_03_L",
    "LeftHandIndex1":        "Index_01_L",
    "LeftHandIndex2":        "Index_02_L",
    "LeftHandIndex3":        "Index_03_L",
    "LeftHandMiddle1":       "Middle_01_L",
    "LeftHandMiddle2":       "Middle_02_L",
    "LeftHandMiddle3":       "Middle_03_L",
    "LeftHandRing1":         "Ring_01_L",
    "LeftHandRing2":         "Ring_02_L",
    "LeftHandRing3":         "Ring_03_L",
    "LeftHandPinky1":        "Pinky_01_L",
    "LeftHandPinky2":        "Pinky_02_L",
    "LeftHandPinky3":        "Pinky_03_L",
    # Right fingers
    "RightHandThumb1":       "Thumb_01_R",
    "RightHandThumb2":       "Thumb_02_R",
    "RightHandThumb3":       "Thumb_03_R",
    "RightHandIndex1":       "Index_01_R",
    "RightHandIndex2":       "Index_02_R",
    "RightHandIndex3":       "Index_03_R",
    "RightHandMiddle1":      "Middle_01_R",
    "RightHandMiddle2":      "Middle_02_R",
    "RightHandMiddle3":      "Middle_03_R",
    "RightHandRing1":        "Ring_01_R",
    "RightHandRing2":        "Ring_02_R",
    "RightHandRing3":        "Ring_03_R",
    "RightHandPinky1":       "Pinky_01_R",
    "RightHandPinky2":       "Pinky_02_R",
    "RightHandPinky3":       "Pinky_03_R",
    # Left leg
    "LeftUpLeg":             "Thigh_L",
    "LeftLeg":               "Calf_L",
    "LeftFoot":              "Foot_L",
    "LeftToeBase":           "Ball_L",
    "mixamorig:LeftUpLeg":   "Thigh_L",
    "mixamorig:LeftLeg":     "Calf_L",
    "mixamorig:LeftFoot":    "Foot_L",
    "mixamorig:LeftToeBase": "Ball_L",
    # Right leg
    "RightUpLeg":            "Thigh_R",
    "RightLeg":              "Calf_R",
    "RightFoot":             "Foot_R",
    "RightToeBase":          "Ball_R",
    "mixamorig:RightUpLeg":  "Thigh_R",
    "mixamorig:RightLeg":    "Calf_R",
    "mixamorig:RightFoot":   "Foot_R",
    "mixamorig:RightToeBase":"Ball_R",
}


# ── Rigify → PubCast ──────────────────────────────────────────────────────────
# Rigify uses DEF- (deform) and ORG- (original) prefixes.
# Table covers the DEF- bones that drive skinning.

_RIGIFY_TO_PUBCAST: Dict[str, str] = {
    # Core
    "DEF-spine":             "Pelvis",
    "ORG-spine":             "Pelvis",
    # Spine
    "DEF-spine.001":         "Spine_01",
    "DEF-spine.002":         "Spine_02",
    "DEF-spine.003":         "Spine_03",
    "DEF-chest":             "Spine_03",
    # Head / neck
    "DEF-neck":              "Neck_01",
    "DEF-head":              "Head",
    "ORG-neck":              "Neck_01",
    "ORG-head":              "Head",
    # Left arm
    "DEF-shoulder.L":        "Clavicle_L",
    "DEF-upper_arm.L":       "UpperArm_L",
    "DEF-forearm.L":         "LowerArm_L",
    "DEF-hand.L":            "Hand_L",
    "ORG-shoulder.L":        "Clavicle_L",
    "ORG-upper_arm.L":       "UpperArm_L",
    "ORG-forearm.L":         "LowerArm_L",
    "ORG-hand.L":            "Hand_L",
    # Right arm
    "DEF-shoulder.R":        "Clavicle_R",
    "DEF-upper_arm.R":       "UpperArm_R",
    "DEF-forearm.R":         "LowerArm_R",
    "DEF-hand.R":            "Hand_R",
    "ORG-shoulder.R":        "Clavicle_R",
    "ORG-upper_arm.R":       "UpperArm_R",
    "ORG-forearm.R":         "LowerArm_R",
    "ORG-hand.R":            "Hand_R",
    # Left fingers
    "DEF-thumb.01.L":        "Thumb_01_L",
    "DEF-thumb.02.L":        "Thumb_02_L",
    "DEF-thumb.03.L":        "Thumb_03_L",
    "DEF-f_index.01.L":      "Index_01_L",
    "DEF-f_index.02.L":      "Index_02_L",
    "DEF-f_index.03.L":      "Index_03_L",
    "DEF-f_middle.01.L":     "Middle_01_L",
    "DEF-f_middle.02.L":     "Middle_02_L",
    "DEF-f_middle.03.L":     "Middle_03_L",
    "DEF-f_ring.01.L":       "Ring_01_L",
    "DEF-f_ring.02.L":       "Ring_02_L",
    "DEF-f_ring.03.L":       "Ring_03_L",
    "DEF-f_pinky.01.L":      "Pinky_01_L",
    "DEF-f_pinky.02.L":      "Pinky_02_L",
    "DEF-f_pinky.03.L":      "Pinky_03_L",
    # Right fingers
    "DEF-thumb.01.R":        "Thumb_01_R",
    "DEF-thumb.02.R":        "Thumb_02_R",
    "DEF-thumb.03.R":        "Thumb_03_R",
    "DEF-f_index.01.R":      "Index_01_R",
    "DEF-f_index.02.R":      "Index_02_R",
    "DEF-f_index.03.R":      "Index_03_R",
    "DEF-f_middle.01.R":     "Middle_01_R",
    "DEF-f_middle.02.R":     "Middle_02_R",
    "DEF-f_middle.03.R":     "Middle_03_R",
    "DEF-f_ring.01.R":       "Ring_01_R",
    "DEF-f_ring.02.R":       "Ring_02_R",
    "DEF-f_ring.03.R":       "Ring_03_R",
    "DEF-f_pinky.01.R":      "Pinky_01_R",
    "DEF-f_pinky.02.R":      "Pinky_02_R",
    "DEF-f_pinky.03.R":      "Pinky_03_R",
    # Left leg
    "DEF-thigh.L":           "Thigh_L",
    "DEF-shin.L":            "Calf_L",
    "DEF-foot.L":            "Foot_L",
    "DEF-toe.L":             "Ball_L",
    "ORG-thigh.L":           "Thigh_L",
    "ORG-shin.L":            "Calf_L",
    "ORG-foot.L":            "Foot_L",
    "ORG-toe.L":             "Ball_L",
    # Right leg
    "DEF-thigh.R":           "Thigh_R",
    "DEF-shin.R":            "Calf_R",
    "DEF-foot.R":            "Foot_R",
    "DEF-toe.R":             "Ball_R",
    "ORG-thigh.R":           "Thigh_R",
    "ORG-shin.R":            "Calf_R",
    "ORG-foot.R":            "Foot_R",
    "ORG-toe.R":             "Ball_R",
}


# ── Rokoko → PubCast ──────────────────────────────────────────────────────────
# Rokoko Smartsuit Pro exports in its own naming convention.

_ROKOKO_TO_PUBCAST: Dict[str, str] = {
    # Core
    "Hip":                   "Pelvis",
    "Stomach":               "Spine_01",
    "Chest":                 "Spine_02",
    "Neck":                  "Neck_01",
    "Head":                  "Head",
    # Left arm
    "LeftShoulderBlade":     "Clavicle_L",
    "LeftShoulder":          "UpperArm_L",
    "LeftElbow":             "LowerArm_L",
    "LeftWrist":             "Hand_L",
    # Right arm
    "RightShoulderBlade":    "Clavicle_R",
    "RightShoulder":         "UpperArm_R",
    "RightElbow":            "LowerArm_R",
    "RightWrist":            "Hand_R",
    # Left fingers
    "LeftHandThumb1":        "Thumb_01_L",
    "LeftHandThumb2":        "Thumb_02_L",
    "LeftHandThumb3":        "Thumb_03_L",
    "LeftHandIndex1":        "Index_01_L",
    "LeftHandIndex2":        "Index_02_L",
    "LeftHandIndex3":        "Index_03_L",
    "LeftHandMiddle1":       "Middle_01_L",
    "LeftHandMiddle2":       "Middle_02_L",
    "LeftHandMiddle3":       "Middle_03_L",
    "LeftHandRing1":         "Ring_01_L",
    "LeftHandRing2":         "Ring_02_L",
    "LeftHandRing3":         "Ring_03_L",
    "LeftHandPinky1":        "Pinky_01_L",
    "LeftHandPinky2":        "Pinky_02_L",
    "LeftHandPinky3":        "Pinky_03_L",
    # Right fingers
    "RightHandThumb1":       "Thumb_01_R",
    "RightHandThumb2":       "Thumb_02_R",
    "RightHandThumb3":       "Thumb_03_R",
    "RightHandIndex1":       "Index_01_R",
    "RightHandIndex2":       "Index_02_R",
    "RightHandIndex3":       "Index_03_R",
    "RightHandMiddle1":      "Middle_01_R",
    "RightHandMiddle2":      "Middle_02_R",
    "RightHandMiddle3":      "Middle_03_R",
    "RightHandRing1":        "Ring_01_R",
    "RightHandRing2":        "Ring_02_R",
    "RightHandRing3":        "Ring_03_R",
    "RightHandPinky1":       "Pinky_01_R",
    "RightHandPinky2":       "Pinky_02_R",
    "RightHandPinky3":       "Pinky_03_R",
    # Left leg
    "LeftHip":               "Thigh_L",
    "LeftKnee":              "Calf_L",
    "LeftAnkle":             "Foot_L",
    "LeftToe":               "Ball_L",
    # Right leg
    "RightHip":              "Thigh_R",
    "RightKnee":             "Calf_R",
    "RightAnkle":            "Foot_R",
    "RightToe":              "Ball_R",
}

_FORMAT_TO_TABLE: Dict[BoneNameFormat, Dict[str, str]] = {
    BoneNameFormat.MIXAMO:  _MIXAMO_TO_PUBCAST,
    BoneNameFormat.RIGIFY:  _RIGIFY_TO_PUBCAST,
    BoneNameFormat.ROKOKO:  _ROKOKO_TO_PUBCAST,
    BoneNameFormat.PUBCAST: {},   # passthrough — handled in convert_bone_name
}


# ── Public API ────────────────────────────────────────────────────────────────

def convert_bone_name(
    name: str,
    source_format: BoneNameFormat,
) -> Optional[str]:
    """
    Convert one bone name from source_format to PubCast internal naming.

    Returns None if no mapping exists for this name.
    Never raises — unknown names always return None silently.

    PUBCAST passthrough: returns the name unchanged if it is a valid
    PubCast bone, else returns None.
    """
    try:
        if source_format is BoneNameFormat.PUBCAST:
            return name if name in PUBCAST_BONES else None
        table = _FORMAT_TO_TABLE.get(source_format)
        if table is None:
            return None
        return table.get(name)
    except Exception as exc:
        logger.debug("convert_bone_name(%r, %s) failed: %s", name, source_format, exc)
        return None


def convert_pose(
    pose: Dict[str, Any],
    source_format: BoneNameFormat,
) -> Dict[str, Any]:
    """
    Convert a {bone_name: transform_data} dict from source_format to
    PubCast internal naming.

    Bones with no mapping are dropped silently.
    Unknown source_format returns the pose unchanged.
    Never raises.
    """
    try:
        if source_format is BoneNameFormat.PUBCAST:
            # Passthrough: keep only valid PubCast bones
            return {k: v for k, v in pose.items() if k in PUBCAST_BONES}
        table = _FORMAT_TO_TABLE.get(source_format)
        if table is None:
            return dict(pose)
        result: Dict[str, Any] = {}
        for src_name, transform in pose.items():
            pubcast_name = table.get(src_name)
            if pubcast_name is not None:
                result[pubcast_name] = transform
        return result
    except Exception as exc:
        logger.debug("convert_pose(%s) failed: %s", source_format, exc)
        return {}


def list_supported_bones(source_format: BoneNameFormat) -> List[str]:
    """Return the source bone names this converter knows about."""
    if source_format is BoneNameFormat.PUBCAST:
        return sorted(PUBCAST_BONES)
    table = _FORMAT_TO_TABLE.get(source_format, {})
    return sorted(table.keys())
