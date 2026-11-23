"""Adapter between the runtime spine and the PubCast avatar skeleton module."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("pubcast.runtime.spine.skeleton")


def create_avatar_skeleton() -> Optional[Any]:
    """Create the standard PubCast skeleton when the avatar module is available."""

    try:
        from modules.avatar_skeleton_system import create_standard_skeleton
    except ImportError as exc:
        logger.warning("PubCast skeleton module is unavailable: %s", exc)
        return None
    return create_standard_skeleton()


def serialize_avatar_skeleton(skeleton: Any) -> Optional[Dict[str, Any]]:
    """Serialize a PubCastSkeleton-like object without mutating it."""

    if skeleton is None:
        return None
    joints = getattr(skeleton, "joints", None)
    bind_pose = getattr(skeleton, "bind_pose", None)
    if isinstance(joints, dict):
        data = {
            "skeleton_type": type(skeleton).__name__,
            "joint_count": len(joints),
            "bind_pose": copy.deepcopy(bind_pose or {}),
            "joints": {
                name: joint.to_dict() if hasattr(joint, "to_dict") else copy.deepcopy(joint)
                for name, joint in joints.items()
            },
        }
        if hasattr(skeleton, "get_retargeting_map"):
            data["retargeting_map"] = skeleton.get_retargeting_map()
        return data
    if hasattr(skeleton, "to_dict"):
        return skeleton.to_dict()
    if hasattr(skeleton, "export_data"):
        return skeleton.export_data()
    return {"skeleton_type": type(skeleton).__name__}


def get_bind_pose(skeleton: Any) -> Dict[str, Any]:
    """Return a copy of the skeleton bind pose as a runtime pose."""

    bind_pose = getattr(skeleton, "bind_pose", None)
    if not isinstance(bind_pose, dict):
        return {}
    return copy.deepcopy(bind_pose)

