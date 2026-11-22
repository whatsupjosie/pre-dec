"""Canonical performer state object."""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .skeleton_binding import serialize_avatar_skeleton


def _vec3() -> List[float]:
    return [0.0, 0.0, 0.0]


def _quat() -> List[float]:
    return [0.0, 0.0, 0.0, 1.0]


def _fit(values: Optional[List[float]], size: int, fill: List[float]) -> List[float]:
    """Coerce to floats and pad or trim to ``size``, padding from ``fill``."""

    out = [float(value) for value in (values or [])[:size]]
    out.extend(fill[len(out):size])
    return out


@dataclass
class PerformerState:
    """Canonical authority object for a performer/avatar."""

    performer_id: str
    name: str
    position: List[float] = field(default_factory=_vec3)
    rotation: List[float] = field(default_factory=_quat)
    velocity: List[float] = field(default_factory=_vec3)
    target_position: Optional[List[float]] = None
    locomotion_state: str = "idle"
    current_animation: str = "idle"
    animation_blend: float = 0.0
    skeleton_pose: Dict[str, Any] = field(default_factory=dict)
    active_station: Optional[str] = None
    interaction_data: Dict[str, Any] = field(default_factory=dict)
    current_room: str = "default"
    current_zone: Optional[str] = None
    last_update_time: float = field(default_factory=time.time)
    replication_tick: int = 0
    dirty: bool = False
    avatar_model_id: str = "default"
    avatar_skeleton: Any = None

    def __post_init__(self):
        # The registry validates lengths strictly on every update. Direct
        # construction is lenient, as it was in the minimal spine, so a state
        # built from partial data is always well-formed.
        self.position = _fit(self.position, 3, _vec3())
        self.rotation = _fit(self.rotation, 4, _quat())
        self.velocity = _fit(self.velocity, 3, _vec3())
        if self.target_position is not None:
            self.target_position = _fit(self.target_position, 3, _vec3())

    def touch(self):
        self.last_update_time = time.time()
        self.replication_tick += 1
        self.dirty = True

    def mark_clean(self):
        self.dirty = False

    # The minimal spine called touch() mark_dirty(); both names stay valid.
    mark_dirty = touch

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "performer_id": self.performer_id,
            "name": self.name,
            "position": list(self.position),
            "rotation": list(self.rotation),
            "velocity": list(self.velocity),
            "target_position": list(self.target_position) if self.target_position is not None else None,
            "locomotion_state": self.locomotion_state,
            "current_animation": self.current_animation,
            "animation_blend": self.animation_blend,
            "skeleton_pose": copy.deepcopy(self.skeleton_pose),
            "active_station": self.active_station,
            "interaction_data": copy.deepcopy(self.interaction_data),
            "current_room": self.current_room,
            "current_zone": self.current_zone,
            "last_update_time": self.last_update_time,
            "replication_tick": self.replication_tick,
            "dirty": self.dirty,
            "avatar_model_id": self.avatar_model_id,
            "avatar_skeleton": self._serialize_skeleton(),
        }
        return data

    def _serialize_skeleton(self):
        return serialize_avatar_skeleton(self.avatar_skeleton)
