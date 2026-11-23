"""Animation arbitration for PubCast performers.

Several systems want to drive the same skeleton at once: scripted cues, a
station interaction, live mocap, the walk cycle. The authority decides, bone by
bone, who wins.

This consolidates the two June 2026 spines. From the June spine: named layers
with fixed priorities, and register_animation() taking a flat pose. From the
minimal spine that shipped in pre-dec: submit() with an explicit priority and
weight, and per-bone resolution, so a higher layer only takes the bones it
actually drives and lower layers keep the rest. An overlay that turns the head
no longer freezes the legs of a performer who is walking.

A pose is always a flat map of bone name to transform. resolve() returns one.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class AnimationCommand:
    layer: str
    priority: int
    bones: Dict[str, Any]
    weight: float = 1.0
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


class AnimationAuthority:
    """Resolves conflicts when multiple systems want to animate the skeleton."""

    LAYERS = {
        "scripted": 100,
        "interaction": 80,
        "mocap": 60,
        "locomotion": 40,
        "default": 0,
    }

    def __init__(self):
        self._commands: Dict[str, Dict[str, AnimationCommand]] = {}
        self._sequence = 0

    def register_animation(self, performer_id: str, layer: str, skeleton_pose: Mapping, priority: Optional[int] = None):
        """Register a flat pose on a named layer.

        A known layer takes its fixed priority unless one is given. An unknown
        layer must be given a priority, so a typo cannot silently rank last.
        """

        if priority is None:
            if layer not in self.LAYERS:
                raise ValueError(f"Unknown animation layer without explicit priority: {layer}")
            priority = self.LAYERS[layer]
        self._store(performer_id, layer, skeleton_pose, int(priority), 1.0)

    def submit(self, performer_id: str, layer: str, pose: Mapping, priority: int = 50, weight: float = 1.0) -> None:
        """Register a pose with an explicit priority and weight, on any layer name.

        Accepts a flat pose or the minimal spine's {"bones": {...}} wrapper.
        Weight is clamped to 0..1 and recorded for reporting; it is not blended.
        """

        weight = max(0.0, min(1.0, float(weight)))
        self._store(performer_id, str(layer), pose, int(priority), weight)

    def resolve(self, performer_id: str) -> Dict[str, Any]:
        """Final pose: for each bone, the transform from the highest-priority
        layer that drives it. Equal priorities go to the most recent layer.
        Returns {} when nothing is registered."""

        bones: Dict[str, Any] = {}
        for command in self._ranked(performer_id):
            for bone, transform in command.bones.items():
                if bone not in bones:
                    bones[bone] = copy.deepcopy(transform)
        return bones

    def resolve_layers(self, performer_id: str) -> List[Dict[str, Any]]:
        """The contributing layers, highest priority first."""

        return [
            {"layer": c.layer, "priority": c.priority, "weight": c.weight, "bones": sorted(c.bones)}
            for c in self._ranked(performer_id)
        ]

    def clear_layer(self, performer_id: str, layer: str):
        """Remove a layer's pose for a performer."""

        layers = self._commands.get(performer_id)
        if not layers:
            return
        layers.pop(layer, None)
        if not layers:
            self._commands.pop(performer_id, None)

    def _store(self, performer_id: str, layer: str, pose: Mapping, priority: int, weight: float) -> None:
        pose = dict(pose or {})
        if isinstance(pose.get("bones"), Mapping):
            pose = dict(pose["bones"])
        self._sequence += 1
        self._commands.setdefault(performer_id, {})[layer] = AnimationCommand(
            layer=layer,
            priority=priority,
            bones=copy.deepcopy(pose),
            weight=weight,
            sequence=self._sequence,
        )

    def _ranked(self, performer_id: str) -> List[AnimationCommand]:
        # sequence, not wall-clock time, breaks ties: two registrations in the
        # same clock tick must still resolve to the later one.
        return sorted(self._commands.get(performer_id, {}).values(),
                      key=lambda c: (c.priority, c.sequence), reverse=True)
