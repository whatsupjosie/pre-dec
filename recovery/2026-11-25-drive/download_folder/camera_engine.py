"""
modules/camera_engine.py  —  PubCast Unified Camera Engine  v2
════════════════════════════════════════════════════════════════════════════════

One engine.  Two internal layers.  One registry.  No seam.

Architecture:
  CameraEngine
    ├── SceneGraph          world truth — cameras query, never rebuild
    ├── ShotResolver        translates intent → concrete transform (the smart part)
    ├── CameraNode          per-camera: role, intent, transform, fallback
    │     └── TargetTracker smooth interpolation only, no intelligence
    ├── TickLoop            30fps asyncio background task (starts on boot)
    └── StudioEventBus      all cross-system communication goes here

Design rules enforced structurally:
  - A return shot is a VIEW EVENT, not a rebuild event.
  - Cameras are queries against a known world, not engines of reconstruction.
  - The tick loop runs; routes serve its last-known state. Nothing computes on request.
  - Fallback is PROACTIVE: ShotResolver flags degradation before the cut.
  - EVO subscribes to the bus. EVO never calls engine methods directly.

Coordinate convention:
  +X right, +Y up, camera at +Z looks toward -Z.
  Forward vector at yaw=0: (sin(0), 0, -cos(0)) = (0, 0, -1).

Rear View Foresight LLC — Feic Mo Chroí — 2026
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("pubcast.camera")


# ══════════════════════════════════════════════════════════════════════════════
# Math  (maps 1:1 to glam in Rust)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s: float) -> "Vec3":
        return Vec3(self.x * s, self.y * s, self.z * s)

    def length(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalized(self) -> "Vec3":
        l = self.length()
        return Vec3(self.x / l, self.y / l, self.z / l) if l > 1e-9 else Vec3(0, 0, -1)

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def lerp(self, o: "Vec3", t: float) -> "Vec3":
        t = max(0.0, min(1.0, t))
        return Vec3(self.x + (o.x - self.x) * t,
                    self.y + (o.y - self.y) * t,
                    self.z + (o.z - self.z) * t)

    def to_dict(self) -> dict:
        return {"x": round(self.x, 4), "y": round(self.y, 4), "z": round(self.z, 4)}


@dataclass
class Euler:
    pitch: float = 0.0
    yaw:   float = 0.0
    roll:  float = 0.0

    def lerp(self, o: "Euler", t: float) -> "Euler":
        t = max(0.0, min(1.0, t))
        def _la(a: float, b: float) -> float:
            d = ((b - a) + 180) % 360 - 180
            return a + d * t
        return Euler(_la(self.pitch, o.pitch), _la(self.yaw, o.yaw), _la(self.roll, o.roll))

    def to_dict(self) -> dict:
        return {"pitch": round(self.pitch, 3),
                "yaw":   round(self.yaw,   3),
                "roll":  round(self.roll,  3)}


@dataclass
class CameraTransform:
    position: Vec3  = field(default_factory=lambda: Vec3(0, 1.7, 5))
    rotation: Euler = field(default_factory=Euler)
    fov:      float = 60.0

    def lerp_to(self, o: "CameraTransform", t: float) -> "CameraTransform":
        return CameraTransform(
            self.position.lerp(o.position, t),
            self.rotation.lerp(o.rotation, t),
            self.fov + (o.fov - self.fov) * t,
        )

    @property
    def yaw(self) -> float:
        return self.rotation.yaw

    @property
    def pitch(self) -> float:
        return self.rotation.pitch

    def to_dict(self) -> dict:
        return {"position": self.position.to_dict(),
                "rotation": self.rotation.to_dict(),
                "fov":      round(self.fov, 2)}


# ══════════════════════════════════════════════════════════════════════════════
# Scene graph
# ══════════════════════════════════════════════════════════════════════════════

class ObjectClass(str, Enum):
    STATIC          = "static"
    LAZY_UPDATE     = "lazy_update"
    DYNAMIC         = "dynamic"
    DESTRUCTIBLE    = "destructible"
    SAFETY_CRITICAL = "safety_critical"


@dataclass
class SceneObject:
    object_id:    str
    name:         str
    position:     Vec3
    bounds:       Vec3
    object_class: ObjectClass = ObjectClass.STATIC
    is_dirty:     bool = False
    cue_armed:    bool = False
    occupied:     bool = False
    priority:     int  = 5

    def to_dict(self) -> dict:
        return {"object_id": self.object_id, "name": self.name,
                "class": self.object_class.value, "position": self.position.to_dict(),
                "dirty": self.is_dirty, "cue_armed": self.cue_armed,
                "occupied": self.occupied, "priority": self.priority}


class SceneGraph:
    """
    The virtual world's source of truth.
    Cameras QUERY this. They do not UPDATE it.
    A return shot to the table is a VIEW EVENT, not a table reconstruction.
    """

    def __init__(self) -> None:
        self._objects: Dict[str, SceneObject] = {}

    def register(self, obj: SceneObject) -> None:
        self._objects[obj.object_id] = obj

    def update(self, object_id: str, **kwargs: Any) -> bool:
        obj = self._objects.get(object_id)
        if not obj:
            return False
        for k, v in kwargs.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return True

    def get(self, object_id: str) -> Optional[SceneObject]:
        return self._objects.get(object_id)

    def all_objects(self) -> List[SceneObject]:
        return list(self._objects.values())

    def query_frustum(self, transform: CameraTransform,
                      max_distance: float = 20.0) -> List[SceneObject]:
        """
        Objects visible from this transform.
        Convention: yaw=0 → forward = (0, 0, -1).
        """
        visible: List[SceneObject] = []
        half_fov = math.radians(transform.fov * 0.5) * 1.15
        yr       = math.radians(transform.yaw)
        fw       = Vec3(math.sin(yr), 0.0, -math.cos(yr))

        for obj in self._objects.values():
            to_obj = obj.position - transform.position
            dist   = to_obj.length()
            if dist < 0.01 or dist > max_distance:
                continue
            dot   = fw.dot(to_obj.normalized())
            angle = math.acos(max(-1.0, min(1.0, dot)))
            if angle <= half_fov:
                visible.append(obj)

        visible.sort(key=lambda o: o.priority)
        return visible

    def to_dict(self) -> dict:
        return {oid: obj.to_dict() for oid, obj in self._objects.items()}


# ══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ══════════════════════════════════════════════════════════════════════════════

class CameraRole(str, Enum):
    PROGRAM        = "program"
    PREVIEW        = "preview"
    STANDBY        = "standby"
    ANALYSIS       = "analysis"
    RECORDING_ONLY = "recording_only"


class CameraType(str, Enum):
    VIRTUAL_SCENE = "virtual_scene"
    EXTERNAL_FEED = "external_feed"


class CameraTransport(str, Enum):
    VIRTUAL = "virtual"
    NDI     = "ndi"
    RTMP    = "rtmp"
    SRT     = "srt"
    WEBCAM  = "webcam"
    FILE    = "file"


class OperatorMode(str, Enum):
    MANUAL_HUMAN    = "manual_human"
    AI_OPERATOR     = "ai_operator"
    BOT_OPERATOR    = "bot_operator"
    SCRIPTED        = "scripted"
    LOCKED_OFF      = "locked_off"
    AUTONOMOUS_SAFE = "autonomous_safe"


class IntentMode(str, Enum):
    FOLLOW_SUBJECT    = "follow_subject"
    HOLD_COMPOSITION  = "hold_composition"
    WATCH_CUE_OBJECT  = "watch_cue_object"
    PREPARE_NEXT_SHOT = "prepare_next_shot"
    HOLD_WIDE         = "hold_wide"
    REACTION_COVERAGE = "reaction_coverage"


class FollowBehavior(str, Enum):
    LOCKED      = "locked"
    SOFT_FOLLOW = "soft_follow"
    ANTICIPATE  = "anticipate"
    DRIFT       = "drift"


class ShotStatus(str, Enum):
    QUEUED     = "queued"
    PREHEATING = "preheating"
    READY      = "ready"
    LIVE       = "live"
    COMPLETED  = "completed"
    BLOCKED    = "blocked"
    FALLBACK   = "fallback"


_FALLBACK_ORDER = ["none", "preserve_intent", "simplified_continuation",
                   "coverage_preservation", "neutral_hold"]


class FallbackLevel(str, Enum):
    NONE                    = "none"
    PRESERVE_INTENT         = "preserve_intent"
    SIMPLIFIED_CONTINUATION = "simplified_continuation"
    COVERAGE_PRESERVATION   = "coverage_preservation"
    NEUTRAL_HOLD            = "neutral_hold"

    def worse_than(self, other: "FallbackLevel") -> bool:
        return _FALLBACK_ORDER.index(self.value) > _FALLBACK_ORDER.index(other.value)


# ══════════════════════════════════════════════════════════════════════════════
# Shot spec & queue
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TargetSpec:
    target_id:         str
    framing_goal:      str            = "medium_shot"
    follow_behavior:   FollowBehavior = FollowBehavior.SOFT_FOLLOW
    maintain_headroom: bool           = True
    preserve_eyeline:  bool           = True
    priority:          int            = 1


@dataclass
class ShotSpec:
    shot_id:           str
    scene_id:          str
    priority:          int              = 10
    targets:           List[TargetSpec] = field(default_factory=list)
    framing_type:      str              = "medium_shot"
    fov_override:      Optional[float]  = None
    cue_conditions:    List[str]        = field(default_factory=list)
    fallback_shot_ids: List[str]        = field(default_factory=list)
    status:            ShotStatus       = ShotStatus.QUEUED


class ShotQueue:
    def __init__(self) -> None:
        self._shots: List[ShotSpec] = []

    def load(self, shots: List[ShotSpec]) -> None:
        self._shots = sorted(shots, key=lambda s: s.priority)

    def current(self) -> Optional[ShotSpec]:
        for s in self._shots:
            if s.status in (ShotStatus.QUEUED, ShotStatus.PREHEATING,
                            ShotStatus.READY, ShotStatus.LIVE):
                return s
        return None

    def peek_next(self) -> Optional[ShotSpec]:
        found = False
        for s in self._shots:
            if found and s.status == ShotStatus.QUEUED:
                return s
            if s.status in (ShotStatus.LIVE, ShotStatus.PREHEATING, ShotStatus.READY):
                found = True
        return None

    def clear(self) -> None:
        self._shots.clear()

    def __len__(self) -> int:
        return len(self._shots)


# ══════════════════════════════════════════════════════════════════════════════
# Shot evaluation
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ShotEvaluation:
    composition_score: float = 1.0
    visibility_score:  float = 1.0
    continuity_score:  float = 1.0
    stability_score:   float = 1.0
    overall:           float = 1.0
    quality:           str   = "excellent"
    notes:             List[str] = field(default_factory=list)

    def compute(self) -> None:
        self.overall = (self.composition_score * 0.35 +
                        self.visibility_score  * 0.35 +
                        self.continuity_score  * 0.15 +
                        self.stability_score   * 0.15)
        if   self.overall >= 0.85: self.quality = "excellent"
        elif self.overall >= 0.70: self.quality = "good"
        elif self.overall >= 0.50: self.quality = "acceptable"
        elif self.overall >= 0.30: self.quality = "degraded"
        else:                      self.quality = "unusable"

    def to_dict(self) -> dict:
        return {"composition": round(self.composition_score, 3),
                "visibility":  round(self.visibility_score,  3),
                "continuity":  round(self.continuity_score,  3),
                "stability":   round(self.stability_score,   3),
                "overall":     round(self.overall,           3),
                "quality":     self.quality,
                "notes":       self.notes}


# ══════════════════════════════════════════════════════════════════════════════
# Shot resolver  —  THE intelligence layer
# Cameras are not smart. The resolver is smart.
# ══════════════════════════════════════════════════════════════════════════════

class ShotResolver:
    """
    Given a camera's current intent and the scene graph, produce:
      - A desired CameraTransform to interpolate toward
      - A ShotEvaluation scoring achievability
      - A recommended FallbackLevel if the shot is compromised

    This is the correct place for:
      - Headroom calculation
      - Anticipation leading
      - Pre-shot feasibility detection
      - 180-degree line checking (stub for next sprint)

    Bots and AI operators set intent on the camera.
    The resolver translates that intent into transform every tick.
    The camera applies it. Intelligence and motion are decoupled.
    """

    HEADROOM_OFFSET    = 0.28
    ANTICIPATION_LEAD  = 0.35
    RECOVERY_THRESHOLD = 0.82

    def __init__(self) -> None:
        self._velocity_cache: Dict[str, Vec3] = {}
        self._last_positions: Dict[str, Vec3] = {}

    def resolve(
        self,
        current: CameraTransform,
        target:  Optional[TargetSpec],
        intent:  IntentMode,
        scene:   SceneGraph,
        dt:      float,
    ) -> Tuple[CameraTransform, ShotEvaluation, FallbackLevel]:
        eval_    = ShotEvaluation()
        fallback = FallbackLevel.NONE

        if target is None or intent == IntentMode.HOLD_COMPOSITION:
            eval_.compute()
            return current, eval_, fallback

        obj = scene.get(target.target_id)
        if obj is None:
            eval_.visibility_score = 0.0
            eval_.notes.append("target_not_in_scene")
            eval_.compute()
            return current, eval_, FallbackLevel.PRESERVE_INTENT

        # Target position with headroom
        look_at = Vec3(
            obj.position.x,
            obj.position.y + (self.HEADROOM_OFFSET if target.maintain_headroom else 0.0),
            obj.position.z,
        )

        # Velocity estimate for anticipation
        last = self._last_positions.get(target.target_id)
        vel  = self._velocity_cache.get(target.target_id, Vec3())
        if last is not None and dt > 0:
            raw = (obj.position - last) * (1.0 / dt)
            vel = vel.lerp(raw, 0.25)
        self._velocity_cache[target.target_id] = vel
        self._last_positions[target.target_id] = Vec3(
            obj.position.x, obj.position.y, obj.position.z)

        if target.follow_behavior == FollowBehavior.ANTICIPATE:
            look_at = look_at + vel * self.ANTICIPATION_LEAD

        # Desired yaw and pitch
        dx   = look_at.x - current.position.x
        dy   = look_at.y - current.position.y
        dz   = look_at.z - current.position.z
        dist = math.sqrt(dx**2 + dy**2 + dz**2)

        desired_yaw   = math.degrees(math.atan2(dx, -dz))
        horiz         = math.sqrt(dx**2 + dz**2)
        desired_pitch = (-math.degrees(math.atan2(dy, horiz))
                         if horiz > 0.001 else 0.0)

        desired_tf = CameraTransform(
            position=current.position,
            rotation=Euler(pitch=desired_pitch, yaw=desired_yaw),
            fov=current.fov,
        )

        # Evaluation
        yaw_err = abs(((desired_yaw - current.yaw) + 180) % 360 - 180)
        eval_.visibility_score  = (1.0 if dist < 10.0
                                   else max(0.0, 1.0 - (dist - 10.0) / 8.0))
        eval_.composition_score = max(0.0, 1.0 - yaw_err / 45.0)
        eval_.continuity_score  = 1.0
        eval_.stability_score   = 0.8 if target.follow_behavior == FollowBehavior.DRIFT else 1.0
        eval_.compute()

        if   eval_.quality == "unusable": fallback = FallbackLevel.COVERAGE_PRESERVATION
        elif eval_.quality == "degraded": fallback = FallbackLevel.PRESERVE_INTENT

        return desired_tf, eval_, fallback

    def can_recover(self, confidence: float) -> bool:
        return confidence >= self.RECOVERY_THRESHOLD


# ══════════════════════════════════════════════════════════════════════════════
# Target tracker  —  smooth interpolation only, no intelligence
# ══════════════════════════════════════════════════════════════════════════════

class TargetTracker:
    _SPEEDS: Dict[str, float] = {
        "locked":      0.25,
        "soft_follow": 0.055,
        "anticipate":  0.07,
        "drift":       0.018,
    }

    def step(self, current: CameraTransform, desired: CameraTransform,
             behavior: FollowBehavior) -> CameraTransform:
        speed = self._SPEEDS.get(behavior.value, 0.055)
        return current.lerp_to(desired, speed)


# ══════════════════════════════════════════════════════════════════════════════
# Camera frame  —  one tick of output
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CameraFrame:
    camera_id:       str
    role:            CameraRole
    transform:       CameraTransform
    visible_objects: List[str]
    cue_flags:       List[str]
    evaluation:      ShotEvaluation
    fallback_level:  FallbackLevel
    intent_mode:     IntentMode
    operator_mode:   OperatorMode
    parallax:        dict
    timestamp:       float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "camera_id":       self.camera_id,
            "role":            self.role.value,
            "transform":       self.transform.to_dict(),
            "visible_objects": self.visible_objects,
            "cue_flags":       self.cue_flags,
            "evaluation":      self.evaluation.to_dict(),
            "fallback_level":  self.fallback_level.value,
            "intent_mode":     self.intent_mode.value,
            "operator_mode":   self.operator_mode.value,
            "parallax":        self.parallax,
            "timestamp":       round(self.timestamp, 3),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Camera node
# ══════════════════════════════════════════════════════════════════════════════

class CameraNode:
    """
    One camera in the PubCast studio.

    State lives here. Intelligence lives in ShotResolver.
    The camera applies the resolver's output through the tracker.
    """

    COVERAGE_FOV = 68.0

    def __init__(
        self,
        camera_id:     str,
        name:          str,
        camera_type:   CameraType    = CameraType.VIRTUAL_SCENE,
        role:          CameraRole    = CameraRole.STANDBY,
        operator_mode: OperatorMode  = OperatorMode.AUTONOMOUS_SAFE,
        intent_mode:   IntentMode    = IntentMode.HOLD_WIDE,
        transform:     Optional[CameraTransform] = None,
        transport:     CameraTransport = CameraTransport.VIRTUAL,
        endpoint:      str           = "",
    ) -> None:
        self.camera_id     = camera_id
        self.name          = name
        self.camera_type   = camera_type
        self.role          = role
        self.operator_mode = operator_mode
        self.intent_mode   = intent_mode
        self.transport     = transport
        self.endpoint      = endpoint

        self.transform:    CameraTransform = transform or CameraTransform()
        self._coverage_tf: CameraTransform = CameraTransform(
            Vec3(0, 2.2, 5.5), Euler(pitch=-5), self.COVERAGE_FOV)

        self.shot_queue:  ShotQueue       = ShotQueue()
        self.targets:     List[TargetSpec] = []
        self.fallback:    FallbackLevel    = FallbackLevel.NONE

        self._resolver:  ShotResolver   = ShotResolver()
        self._tracker:   TargetTracker  = TargetTracker()
        self._last_tick: float          = time.time()
        self._eval:      ShotEvaluation = ShotEvaluation()
        self._visible:   List[str]      = []
        self._cue_flags: List[str]      = []
        self._online:    bool           = True

    def assign_role(self, role: CameraRole) -> None:
        self.role = role
        if role == CameraRole.PREVIEW and self.intent_mode == IntentMode.HOLD_WIDE:
            self.intent_mode = IntentMode.PREPARE_NEXT_SHOT

    def set_target(self, object_id: Optional[str],
                   behavior: FollowBehavior = FollowBehavior.SOFT_FOLLOW,
                   framing: str = "medium_shot") -> None:
        if object_id is None:
            self.targets = []
            return
        self.targets    = [TargetSpec(object_id, framing, behavior)]
        self.intent_mode = IntentMode.FOLLOW_SUBJECT

    def load_shot_queue(self, shots: List[ShotSpec]) -> None:
        self.shot_queue.load(shots)

    def prepare_next_shot(self) -> None:
        shot = self.shot_queue.current()
        if shot and shot.status == ShotStatus.QUEUED:
            shot.status = ShotStatus.PREHEATING
            if shot.targets:
                t = shot.targets[0]
                self.set_target(t.target_id, t.follow_behavior, t.framing_goal)

    def mark_shot_ready(self) -> None:
        shot = self.shot_queue.current()
        if shot and shot.status == ShotStatus.PREHEATING:
            shot.status = ShotStatus.READY

    def go_live(self) -> None:
        shot = self.shot_queue.current()
        if shot:
            shot.status = ShotStatus.LIVE

    def complete_shot(self) -> None:
        shot = self.shot_queue.current()
        if shot and shot.status == ShotStatus.LIVE:
            shot.status = ShotStatus.COMPLETED

    # ── Tick — called by TickLoop at 30fps ────────────────────────────────────

    def tick(self, scene: SceneGraph) -> CameraFrame:
        now = time.time()
        dt  = min(now - self._last_tick, 0.1)
        self._last_tick = now

        primary = self.targets[0] if self.targets else None

        if self.fallback == FallbackLevel.NEUTRAL_HOLD:
            self.transform = self._tracker.step(
                self.transform, self._coverage_tf, FollowBehavior.SOFT_FOLLOW)
        else:
            desired, self._eval, recommended = self._resolver.resolve(
                self.transform, primary, self.intent_mode, scene, dt)
            behavior = primary.follow_behavior if primary else FollowBehavior.SOFT_FOLLOW
            self.transform = self._tracker.step(self.transform, desired, behavior)
            self._update_fallback(recommended)

        self._visible   = [o.object_id for o in scene.query_frustum(self.transform)]
        self._cue_flags = [oid for oid in self._visible
                           if (scene.get(oid) and scene.get(oid).cue_armed)]

        return CameraFrame(
            camera_id      = self.camera_id,
            role           = self.role,
            transform      = CameraTransform(
                Vec3(self.transform.position.x,
                     self.transform.position.y,
                     self.transform.position.z),
                Euler(self.transform.pitch, self.transform.yaw),
                self.transform.fov,
            ),
            visible_objects = list(self._visible),
            cue_flags       = list(self._cue_flags),
            evaluation      = self._eval,
            fallback_level  = self.fallback,
            intent_mode     = self.intent_mode,
            operator_mode   = self.operator_mode,
            parallax        = self._parallax(),
        )

    def _update_fallback(self, recommended: FallbackLevel) -> None:
        if recommended == FallbackLevel.NONE:
            if (self.fallback != FallbackLevel.NONE and
                    self._resolver.can_recover(self._eval.overall)):
                self.fallback    = FallbackLevel.NONE
                if self.intent_mode == IntentMode.HOLD_WIDE:
                    self.intent_mode = IntentMode.FOLLOW_SUBJECT
        elif recommended.worse_than(self.fallback):
            self.fallback = recommended
            if recommended == FallbackLevel.COVERAGE_PRESERVATION:
                self.intent_mode  = IntentMode.HOLD_WIDE
                self.transform.fov = max(self.transform.fov, self.COVERAGE_FOV)

    def _parallax(self) -> dict:
        return {
            "ox":    round(-self.transform.yaw   / 45.0 * 0.2, 4),
            "oy":    round( self.transform.pitch / 30.0 * 0.1, 4),
            "scale": round(60.0 / max(self.transform.fov, 20.0), 4),
            "yaw":   round(self.transform.yaw,   2),
            "pitch": round(self.transform.pitch, 2),
            "fov":   round(self.transform.fov,   2),
        }

    @property
    def location(self) -> str:
        if self.camera_type == CameraType.VIRTUAL_SCENE:
            return "studio"
        proto = self.endpoint.split("://")[0].lower() if "://" in self.endpoint else ""
        return "studio" if proto in ("ndi", "virtual") else "remote"

    @property
    def source_id(self) -> str:
        """Legacy alias used by older recording/camera callers."""
        return self.camera_id

    def is_online(self) -> bool:
        return self._online

    def to_dict(self) -> dict:
        shot = self.shot_queue.current()
        return {
            "camera_id":    self.camera_id,
            "name":         self.name,
            "type":         self.camera_type.value,
            "role":         self.role.value,
            "operator":     self.operator_mode.value,
            "intent":       self.intent_mode.value,
            "fallback":     self.fallback.value,
            "online":       self._online,
            "current_shot": shot.shot_id if shot else None,
            "shot_count":   len(self.shot_queue),
            "targets":      [t.target_id for t in self.targets],
            "evaluation":   self._eval.to_dict(),
            "transform":    self.transform.to_dict(),
            "parallax":     self._parallax(),
            "transport":    self.transport.value,
            "endpoint":     self.endpoint,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Studio event bus
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StudioEvent:
    event_type:  str
    timestamp:   float = field(default_factory=time.time)
    scene_id:    Optional[str] = None
    take_number: Optional[int] = None
    camera_id:   Optional[str] = None
    payload:     Dict[str, Any] = field(default_factory=dict)


class StudioEventBus:
    """
    Async pub/sub. All inter-system communication goes here.
    No module calls another module's methods directly at runtime.
    """

    def __init__(self) -> None:
        self._subs: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subs.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: Callable) -> None:
        self.subscribe("*", handler)

    async def publish(self, event: StudioEvent) -> None:
        handlers = self._subs.get(event.event_type, []) + self._subs.get("*", [])
        for h in handlers:
            try:
                r = h(event)
                if asyncio.iscoroutine(r):
                    await r
            except Exception as exc:
                logger.error("Bus handler error (%s): %s", event.event_type, exc)


# ══════════════════════════════════════════════════════════════════════════════
# Tick loop  —  30fps heartbeat.  Starts on boot.  Routes read its output.
# ══════════════════════════════════════════════════════════════════════════════

class TickLoop:
    """
    asyncio background task at 30fps.
    Calls tick() on every camera. Writes to shared frame buffer.
    Routes and WebSocket handlers read from that buffer.
    Nothing computes on request. This is the correct architecture.
    """

    TARGET_FPS = 30.0

    def __init__(self, cameras: Dict[str, CameraNode],
                 scene: SceneGraph, bus: StudioEventBus) -> None:
        self._cameras     = cameras
        self._scene       = scene
        self._bus         = bus
        self._running     = False
        self._task:       Optional[asyncio.Task] = None
        self._frame_count = 0
        self._last_frames: Dict[str, CameraFrame] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task    = asyncio.create_task(self._run(), name="camera_tick_loop")
        logger.info("TickLoop started at %dfps", self.TARGET_FPS)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TickLoop stopped after %d frames", self._frame_count)

    async def _run(self) -> None:
        interval = 1.0 / self.TARGET_FPS
        while self._running:
            t0 = time.perf_counter()
            self._tick()
            elapsed = time.perf_counter() - t0
            await asyncio.sleep(max(0.0, interval - elapsed))

    def _tick(self) -> None:
        self._frame_count += 1
        frames: Dict[str, CameraFrame] = {}
        for cam_id, cam in self._cameras.items():
            if not cam.is_online():
                continue
            try:
                frames[cam_id] = cam.tick(self._scene)
            except Exception as exc:
                logger.error("TickLoop camera %s: %s", cam_id, exc)
        self._last_frames = frames

        # Publish bus event every 10 frames (3fps for downstream consumers)
        if self._frame_count % 10 == 0:
            pgm_id = next(
                (cid for cid, c in self._cameras.items()
                 if c.role == CameraRole.PROGRAM), None)
            asyncio.create_task(self._bus.publish(StudioEvent(
                event_type = "tick:cameras",
                payload    = {
                    "frame":   self._frame_count,
                    "program": pgm_id,
                    "cameras": {cid: f.parallax for cid, f in frames.items()},
                },
            )))

    def last_frame(self, camera_id: str) -> Optional[CameraFrame]:
        return self._last_frames.get(camera_id)

    def all_frames(self) -> Dict[str, CameraFrame]:
        return dict(self._last_frames)

    def program_frame(self) -> Optional[CameraFrame]:
        pgm = next((c for c in self._cameras.values()
                    if c.role == CameraRole.PROGRAM), None)
        return self._last_frames.get(pgm.camera_id) if pgm else None

    def parallax_state(self) -> dict:
        return {cid: f.parallax for cid, f in self._last_frames.items()}

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def running(self) -> bool:
        return self._running


# ══════════════════════════════════════════════════════════════════════════════
# Camera Engine  —  the single public interface
# ══════════════════════════════════════════════════════════════════════════════

class CameraEngine:
    """
    The unified camera system. One engine. One registry. One tick loop.
    Call await engine.start() after registering all cameras.
    Call await engine.stop() on shutdown.
    """

    def __init__(self, scene: Optional[SceneGraph] = None) -> None:
        self.scene        = scene or SceneGraph()
        self.bus          = StudioEventBus()
        self._cameras:    Dict[str, CameraNode] = {}
        self._program_id: Optional[str]         = None
        self._preview_id: Optional[str]         = None
        self.tick_loop    = TickLoop(self._cameras, self.scene, self.bus)

    async def start(self) -> None:
        await self.tick_loop.start()

    async def stop(self) -> None:
        await self.tick_loop.stop()

    def register(self, camera: CameraNode) -> None:
        self._cameras[camera.camera_id] = camera

    def deregister(self, camera_id: str) -> None:
        self._cameras.pop(camera_id, None)

    def get(self, camera_id: str) -> Optional[CameraNode]:
        return self._cameras.get(camera_id)

    def all_cameras(self) -> List[CameraNode]:
        return list(self._cameras.values())

    def set_program(self, camera_id: str) -> bool:
        if camera_id not in self._cameras:
            return False
        if self._program_id and self._program_id in self._cameras:
            self._cameras[self._program_id].assign_role(CameraRole.STANDBY)
        self._cameras[camera_id].assign_role(CameraRole.PROGRAM)
        self._program_id = camera_id
        return True

    def set_preview(self, camera_id: str) -> bool:
        if camera_id not in self._cameras:
            return False
        if (self._preview_id and self._preview_id in self._cameras
                and self._preview_id != camera_id):
            cam = self._cameras[self._preview_id]
            if cam.role == CameraRole.PREVIEW:
                cam.assign_role(CameraRole.STANDBY)
        self._cameras[camera_id].assign_role(CameraRole.PREVIEW)
        self._preview_id = camera_id
        return True

    def take(self) -> bool:
        if not self._preview_id:
            return False
        if self._program_id and self._program_id in self._cameras:
            self._cameras[self._program_id].assign_role(CameraRole.STANDBY)
            self._cameras[self._program_id].complete_shot()
        self._cameras[self._preview_id].assign_role(CameraRole.PROGRAM)
        self._cameras[self._preview_id].go_live()
        self._program_id = self._preview_id
        self._preview_id = None
        return True

    def program_camera(self) -> Optional[CameraNode]:
        return self._cameras.get(self._program_id) if self._program_id else None

    def preview_camera(self) -> Optional[CameraNode]:
        return self._cameras.get(self._preview_id) if self._preview_id else None

    def assign_scene(self, scene_id: str, take_number: int,
                     assignments: Dict[str, List[ShotSpec]]) -> List[str]:
        assigned: List[str] = []
        for cam_id, shots in assignments.items():
            cam = self._cameras.get(cam_id)
            if cam:
                cam.load_shot_queue(shots)
                assigned.append(cam_id)
        return assigned

    def update_scene_object(self, object_id: str, **kwargs: Any) -> bool:
        return self.scene.update(object_id, **kwargs)

    def status_dict(self) -> dict:
        pgm = self.program_camera()
        pvw = self.preview_camera()
        return {
            "program":      pgm.camera_id if pgm else None,
            "preview":      pvw.camera_id if pvw else None,
            "tick_count":   self.tick_loop.frame_count,
            "tick_running": self.tick_loop.running,
            "cameras":      {cid: cam.to_dict() for cid, cam in self._cameras.items()},
        }

    # ── Legacy shims ───────────────────────────────────────────────────────────
    def list_sources(self) -> List[dict]:
        return [c.to_dict() for c in self._cameras.values()]

    def list_status(self) -> List[dict]:
        return [{"camera_id": c.camera_id, "online": c.is_online(),
                 "role": c.role.value, "evaluation": c._eval.to_dict()}
                for c in self._cameras.values()]

    def get_program_source(self) -> Optional[dict]:
        c = self.program_camera(); return c.to_dict() if c else None

    def get_preview_source(self) -> Optional[dict]:
        c = self.preview_camera(); return c.to_dict() if c else None

    def set_program_source(self, camera_id: str) -> bool:
        return self.set_program(camera_id)

    def set_preview_source(self, camera_id: str) -> bool:
        return self.set_preview(camera_id)

    def register_source(self, **kwargs: Any) -> None:
        cam_id = kwargs.get("camera_id") or kwargs.get("source_id", "unknown")
        pos    = kwargs.get("position", [0.0, 1.7, 5.0])
        self.register(CameraNode(
            camera_id   = cam_id,
            name        = kwargs.get("name", cam_id),
            camera_type = (CameraType.VIRTUAL_SCENE
                           if kwargs.get("transport", "virtual") in ("virtual", "voxel_3d")
                           else CameraType.EXTERNAL_FEED),
            transport   = CameraTransport(kwargs.get("transport", "virtual")),
            endpoint    = kwargs.get("endpoint", ""),
            transform   = CameraTransform(
                Vec3(pos[0], pos[1], pos[2]), fov=kwargs.get("fov", 60.0)),
        ))


# ══════════════════════════════════════════════════════════════════════════════
# Default scene
# ══════════════════════════════════════════════════════════════════════════════

def _build_default_scene() -> SceneGraph:
    scene = SceneGraph()
    scene.register(SceneObject("studio_floor",   "Studio Floor",
                               Vec3(0,0,0),      Vec3(8,.1,8),   ObjectClass.STATIC))
    scene.register(SceneObject("broadcast_desk", "Broadcast Desk",
                               Vec3(0,.8,-1),    Vec3(2,.5,.6),  ObjectClass.LAZY_UPDATE, priority=4))
    scene.register(SceneObject("back_wall",      "Back Wall",
                               Vec3(0,2,-4),     Vec3(6,2.5,.2), ObjectClass.STATIC, priority=9))
    scene.register(SceneObject("slot_pete",      "Pete",
                               Vec3(-1.8,1.5,.5),Vec3(.4,.9,.3), ObjectClass.DYNAMIC, priority=1))
    scene.register(SceneObject("slot_host",      "Host",
                               Vec3(0,1.5,.2),   Vec3(.4,.9,.3), ObjectClass.DYNAMIC, priority=1))
    scene.register(SceneObject("slot_purfluous", "Sir Purfluous",
                               Vec3(1.8,1.5,.5), Vec3(.5,.95,.3),ObjectClass.DYNAMIC, priority=1))
    return scene


# ══════════════════════════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════════════════════════

def create_camera_engine() -> CameraEngine:
    """
    Build the default PubCast camera engine.
    Remember: await engine.start() after this.
    """
    engine = CameraEngine(scene=_build_default_scene())

    engine.register(CameraNode("wide_shot",    "Wide Shot",
        CameraType.VIRTUAL_SCENE, CameraRole.PROGRAM, OperatorMode.AI_OPERATOR,
        IntentMode.HOLD_WIDE,
        CameraTransform(Vec3(0,2,6),    Euler(-8,0),   72), CameraTransport.VIRTUAL, "virtual://wide_shot"))
    engine.register(CameraNode("medium_shot",  "Medium Shot",
        CameraType.VIRTUAL_SCENE, CameraRole.PREVIEW, OperatorMode.AI_OPERATOR,
        IntentMode.FOLLOW_SUBJECT,
        CameraTransform(Vec3(1.8,1.6,3.2), Euler(-3,-18), 50), CameraTransport.VIRTUAL, "virtual://medium_shot"))
    engine.register(CameraNode("close_up",     "Close Up",
        CameraType.VIRTUAL_SCENE, CameraRole.STANDBY, OperatorMode.AI_OPERATOR,
        IntentMode.FOLLOW_SUBJECT,
        CameraTransform(Vec3(.8,1.5,1.8), Euler(-2,-8),  34), CameraTransport.VIRTUAL, "virtual://close_up"))
    engine.register(CameraNode("overhead",     "Overhead",
        CameraType.VIRTUAL_SCENE, CameraRole.STANDBY, OperatorMode.AI_OPERATOR,
        IntentMode.HOLD_COMPOSITION,
        CameraTransform(Vec3(0,5.5,1),  Euler(-75,0),  85), CameraTransport.VIRTUAL, "virtual://overhead"))
    engine.register(CameraNode("reaction_shot","Reaction Shot",
        CameraType.VIRTUAL_SCENE, CameraRole.STANDBY, OperatorMode.AI_OPERATOR,
        IntentMode.REACTION_COVERAGE,
        CameraTransform(Vec3(-2.2,1.6,3), Euler(-3,20), 50), CameraTransport.VIRTUAL, "virtual://reaction_shot"))
    engine.register(CameraNode("cam1_ndi",  "Camera 1 NDI",
        CameraType.EXTERNAL_FEED, CameraRole.STANDBY, OperatorMode.MANUAL_HUMAN,
        transport=CameraTransport.NDI, endpoint="ndi://camera-1"))
    engine.register(CameraNode("cam2_rtmp", "Camera 2 RTMP",
        CameraType.EXTERNAL_FEED, CameraRole.STANDBY, OperatorMode.MANUAL_HUMAN,
        transport=CameraTransport.RTMP, endpoint="rtmp://streaming-server/cam2"))

    engine.set_program("wide_shot")
    engine.set_preview("medium_shot")

    engine.get("medium_shot").set_target("slot_pete",       FollowBehavior.SOFT_FOLLOW)
    engine.get("close_up").set_target(   "slot_pete",       FollowBehavior.SOFT_FOLLOW)
    engine.get("reaction_shot").set_target("slot_purfluous", FollowBehavior.SOFT_FOLLOW)
    engine.get("wide_shot").set_target(  "broadcast_desk",  FollowBehavior.LOCKED)

    return engine


# Legacy aliases
StudioCameraEngine     = CameraEngine
create_studio_cameras  = create_camera_engine
create_default_cameras = create_camera_engine
