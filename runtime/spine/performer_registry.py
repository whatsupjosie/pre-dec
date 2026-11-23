"""Authoritative performer registry."""

from __future__ import annotations

import copy
import logging
from collections.abc import Mapping
from typing import Dict, Iterable, List, Optional

from .event_bus import EventBus
from .performers.performer_state import PerformerState
from .performers.skeleton_binding import create_avatar_skeleton, get_bind_pose

logger = logging.getLogger("pubcast.runtime.spine.performers")

LOCOMOTION_STATES = {"idle", "walking", "running", "interacting", "falling", "sitting"}
# The name the minimal spine exported; kept so either import keeps working.
VALID_LOCOMOTION_STATES = LOCOMOTION_STATES


class PerformerRegistry:
    """Authoritative registry for all performers."""

    def __init__(self, event_bus: EventBus, bind_default_skeleton: bool = True):
        self.event_bus = event_bus
        self.bind_default_skeleton = bind_default_skeleton
        self._performers: Dict[str, PerformerState] = {}

    def spawn_performer(
        self,
        performer_id: str,
        name: str,
        position: List[float],
        room: str,
        avatar_model_id: str = "default",
        avatar_skeleton=None,
    ) -> PerformerState:
        """Create new performer, emit performer:spawned event."""

        if performer_id in self._performers:
            raise ValueError(f"Performer already exists: {performer_id}")
        if avatar_skeleton is None and self.bind_default_skeleton:
            avatar_skeleton = create_avatar_skeleton()
        performer = PerformerState(
            performer_id=performer_id,
            name=name,
            position=_copy_vector(position, 3, "position"),
            current_room=room,
            avatar_model_id=avatar_model_id,
            avatar_skeleton=avatar_skeleton,
            skeleton_pose=get_bind_pose(avatar_skeleton),
            dirty=True,
        )
        self._performers[performer_id] = performer
        logger.info("spawn performer %s in room %s", performer_id, room)
        self.event_bus.emit("performer:spawned", performer.to_dict(), source="performer_registry")
        return performer

    def get_performer(self, performer_id: str) -> Optional[PerformerState]:
        """Retrieve performer by ID."""

        return self._performers.get(performer_id)

    def all_performers(self) -> Iterable[PerformerState]:
        return tuple(self._performers.values())

    def update_performer_transform(self, performer_id: str, position: List[float], rotation: List[float]):
        """Update position/rotation, emit performer:moved."""

        performer = self._require(performer_id)
        before = {"position": list(performer.position), "rotation": list(performer.rotation)}
        performer.position = _copy_vector(position, 3, "position")
        performer.rotation = _copy_vector(rotation, 4, "rotation")
        performer.touch()
        after = {"position": list(performer.position), "rotation": list(performer.rotation)}
        logger.debug("performer transform %s before=%s after=%s", performer_id, before, after)
        self.event_bus.emit(
            "performer:moved",
            {"performer_id": performer_id, "before": before, "after": after},
            source="performer_registry",
        )

    def set_locomotion_state(self, performer_id: str, state: str):
        """Change movement state, emit performer:state_change."""

        if state not in LOCOMOTION_STATES:
            raise ValueError(f"Unknown locomotion state: {state}")
        performer = self._require(performer_id)
        previous = performer.locomotion_state
        if previous == state:
            return
        performer.locomotion_state = state
        performer.current_animation = state if state != "interacting" else performer.current_animation
        performer.touch()
        logger.debug("performer state %s before=%s after=%s", performer_id, previous, state)
        self.event_bus.emit(
            "performer:state_change",
            {"performer_id": performer_id, "before": previous, "after": state},
            source="performer_registry",
        )

    def apply_animation_frame(self, performer_id: str, skeleton_pose: Dict, animation: Optional[str] = None):
        """Apply mocap/animation data, emit performer:animated.

        A pose is a flat map of bone name to transform. The minimal spine wrapped
        it as {"animation": name, "bones": {...}}; that shape is unwrapped here so
        either caller lands on the same canonical pose. The animation's name is
        kept on the performer as current_animation, never inside the pose.
        """

        performer = self._require(performer_id)
        pose = _plain(skeleton_pose or {})
        if isinstance(pose.get("bones"), dict):
            animation = animation or pose.get("animation")
            pose = pose["bones"]
        performer.skeleton_pose = copy.deepcopy(pose)
        if animation:
            performer.current_animation = str(animation)
        performer.touch()
        self.event_bus.emit(
            "performer:animated",
            {
                "performer_id": performer_id,
                "animation": performer.current_animation,
                "skeleton_pose": copy.deepcopy(performer.skeleton_pose),
            },
            source="performer_registry",
        )

    def activate_station(self, performer_id: str, station_id: str, interaction_data: Optional[Dict] = None):
        """Performer interacts with station, emit station:activated."""

        performer = self._require(performer_id)
        before = performer.active_station
        performer.active_station = station_id
        performer.interaction_data = copy.deepcopy(interaction_data or {})
        performer.touch()
        self.set_locomotion_state(performer_id, "interacting")
        self.event_bus.emit(
            "station:activated",
            {"performer_id": performer_id, "station_id": station_id, "before": before},
            source="performer_registry",
        )

    def deactivate_station(self, performer_id: str):
        """Performer leaves station, emit station:deactivated."""

        performer = self._require(performer_id)
        station_id = performer.active_station
        performer.active_station = None
        performer.interaction_data = {}
        performer.touch()
        self.set_locomotion_state(performer_id, "idle")
        self.event_bus.emit(
            "station:deactivated",
            {"performer_id": performer_id, "station_id": station_id},
            source="performer_registry",
        )

    def set_target_position(self, performer_id: str, target_position: Optional[List[float]]):
        performer = self._require(performer_id)
        performer.target_position = _copy_vector(target_position, 3, "target_position") if target_position is not None else None
        performer.touch()

    def set_velocity(self, performer_id: str, velocity: List[float]):
        performer = self._require(performer_id)
        performer.velocity = _copy_vector(velocity, 3, "velocity")
        performer.touch()

    def _require(self, performer_id: str) -> PerformerState:
        performer = self._performers.get(performer_id)
        if performer is None:
            raise KeyError(f"Unknown performer: {performer_id}")
        return performer


def _plain(value):
    """Thaw an immutable event payload (FrozenDict / tuples) into plain dicts and lists."""

    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _copy_vector(value: List[float], length: int, label: str) -> List[float]:
    if value is None or len(value) != length:
        raise ValueError(f"{label} must have length {length}")
    return [float(item) for item in value]
