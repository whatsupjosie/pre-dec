"""Avatar locomotion system."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional

from ..event_bus import EventBus
from .animation_presets import sample_preset_pose

if TYPE_CHECKING:
    from ..performer_registry import PerformerRegistry


WALK_CYCLE_FRAMES = {
    0.0: "idle",
    0.2: "walk_contact_left",
    0.4: "walk_passing",
    0.6: "walk_contact_right",
    0.8: "walk_passing_2",
}


class LocomotionSystem:
    """Movement system for avatars."""

    def __init__(
        self,
        performer_registry: "PerformerRegistry",
        event_bus: EventBus,
        walk_speed: float = 1.4,
        *,
        speed: Optional[float] = None,
    ):
        # ``speed`` is the minimal spine's name for walk_speed; either works.
        self.registry = performer_registry
        self.event_bus = event_bus
        self.update_rate = 60
        self.walk_speed = float(walk_speed if speed is None else speed)
        self._elapsed: Dict[str, float] = {}

    def move_to(self, performer_id: str, target_position: List[float]):
        """Command performer to walk to position."""

        self.registry.set_target_position(performer_id, target_position)
        self.registry.set_locomotion_state(performer_id, "walking")

    def update(self, delta_time: float):
        """Called each frame to advance locomotion."""

        delta_time = max(0.0, float(delta_time))
        for performer in self.registry.all_performers():
            if performer.locomotion_state != "walking" or performer.target_position is None:
                continue
            self._elapsed[performer.performer_id] = self._elapsed.get(performer.performer_id, 0.0) + delta_time
            remaining = _subtract(performer.target_position, performer.position)
            distance = _length(remaining)
            if distance <= 0.02:
                self.registry.update_performer_transform(
                    performer.performer_id,
                    performer.target_position,
                    performer.rotation,
                )
                self.stop(performer.performer_id)
                self.registry.set_target_position(performer.performer_id, None)
                continue
            step = min(self.walk_speed * delta_time, distance)
            direction = [value / distance for value in remaining]
            next_position = [performer.position[index] + direction[index] * step for index in range(3)]
            velocity = [direction[index] * self.walk_speed for index in range(3)]
            self.registry.set_velocity(performer.performer_id, velocity)
            self.registry.update_performer_transform(performer.performer_id, next_position, performer.rotation)
            pose = self.get_walk_animation_frame(performer.performer_id, self._elapsed[performer.performer_id])
            self.registry.apply_animation_frame(performer.performer_id, pose, animation="walk")

    @property
    def speed(self) -> float:
        return self.walk_speed

    @speed.setter
    def speed(self, value: float) -> None:
        self.walk_speed = float(value)

    def stop(self, performer_id: str):
        """Stop movement immediately."""

        self.registry.set_velocity(performer_id, [0.0, 0.0, 0.0])
        self.registry.set_locomotion_state(performer_id, "idle")

    def get_walk_animation_frame(self, performer_id: str, elapsed: float) -> Dict:
        """Get skeleton pose for current walk cycle."""

        performer = self.registry.get_performer(performer_id)
        if performer and str(performer.avatar_model_id).upper() in {"SHELA", "SHEILA"}:
            return sample_preset_pose("feminine_high_heel_walk", elapsed)

        phase = (elapsed * 1.8) % 1.0
        swing = math.sin(phase * math.tau)
        counter = math.sin((phase + 0.5) * math.tau)
        return {
            "hips": {"position": [0.0, 0.9 + 0.015 * abs(swing), 0.0], "rotation": [0.0, 0.0, 0.0, 1.0]},
            "thigh_l": {"rotation": [0.25 * swing, 0.0, 0.0, 1.0]},
            "calf_l": {"rotation": [-0.18 * max(0.0, counter), 0.0, 0.0, 1.0]},
            "thigh_r": {"rotation": [0.25 * counter, 0.0, 0.0, 1.0]},
            "calf_r": {"rotation": [-0.18 * max(0.0, swing), 0.0, 0.0, 1.0]},
            "upperarm_l": {"rotation": [0.12 * counter, 0.0, 0.0, 1.0]},
            "upperarm_r": {"rotation": [0.12 * swing, 0.0, 0.0, 1.0]},
        }


def _subtract(a: List[float], b: List[float]) -> List[float]:
    return [a[index] - b[index] for index in range(3)]


def _length(value: List[float]) -> float:
    return math.sqrt(sum(item * item for item in value))
