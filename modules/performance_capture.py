# PubCast AI — performance_capture.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Performer data: the one server record of what the 2.5D stage is showing.

The 2.5D studio draws its performers, set and graphics in the director's browser. Until now the
server only knew which camera was live, so a data-only take could not be turned back into a
picture: nobody had kept where each performer stood, how they moved, their mouth shapes, or
what graphics were on screen.

The director's studio sends a performance frame whenever any of that changes (and the mouth
weights while someone talks). This module checks each frame, keeps the latest one for pages that
ask, tells subscribed pages when the stage changes, and writes each frame into every take that is
recording, through the same show data as camera cuts and pauses (modules/recording_modes.py).
modules/reconstruction.py reads those frames back to draw the take from any camera.

The frame shape is the camera pool's director scene (modules/camera_pool.py, ``Scene``), widened
with what a reconstruction also needs: mouth weight, gestures, the set images, the voxel prop.
A pool scene is a valid performance frame.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from modules.route_security import require_role

logger = logging.getLogger("pubcast.performance_capture")

STATIC_PATH = r"^/static/[A-Za-z0-9_\-./]+$"
MAX_PERFORMERS = 8
MAX_VOXEL_BLOCKS = 4096
MAX_BATCH = 120
BROADCAST_MIN_INTERVAL = 0.1        # pages hear about stage changes at most ten times a second


def _finite(value: float, name: str, limit: float) -> float:
    if not math.isfinite(value) or abs(value) > limit:
        raise ValueError(f"{name} must be a finite number within ±{limit:g}")
    return value


class PerformerFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_.:\-]+$")
    slot: str = Field(default="", max_length=32)
    avatar: Optional[Literal["female", "male"]] = None
    avatar_url: Optional[str] = Field(default=None, max_length=200, pattern=STATIC_PATH)
    position: List[float] = Field(min_length=2, max_length=2)     # stage picture, 0..1 each
    vx: float = 0.0
    vy: float = 0.0
    moving: bool = False
    jaw: Optional[float] = Field(default=None, ge=0.0, le=1.0)    # mouth open, for speech
    viseme: Optional[str] = Field(default=None, max_length=16, pattern=r"^[A-Za-z_]+$")

    @field_validator("position")
    @classmethod
    def _position(cls, value: List[float]) -> List[float]:
        if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in value):
            raise ValueError("position must be two numbers between 0 and 1")
        return value

    @field_validator("vx", "vy")
    @classmethod
    def _velocity(cls, value: float) -> float:
        return _finite(value, "velocity", 10.0)

    @field_validator("avatar_url")
    @classmethod
    def _no_escape(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and ".." in value:
            raise ValueError("avatar_url must stay inside /static/")
        return value

    @model_validator(mode="after")
    def _has_body(self) -> "PerformerFrame":
        if self.avatar is None and self.avatar_url is None:
            raise ValueError("each performer needs avatar (female or male) or avatar_url")
        return self


class Gesture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    performer: str = Field(min_length=1, max_length=96)
    clip: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_ .\-|()]+$")


class SetImages(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    back: Optional[str] = Field(default=None, max_length=200, pattern=STATIC_PATH)
    mid: Optional[str] = Field(default=None, max_length=200, pattern=STATIC_PATH)
    front: Optional[str] = Field(default=None, max_length=200, pattern=STATIC_PATH)

    @model_validator(mode="after")
    def _inside(self) -> "SetImages":
        for value in (self.back, self.mid, self.front):
            if value and ".." in value:
                raise ValueError("set images must stay inside /static/")
        return self


class VoxelBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x: int = Field(ge=-512, le=512)
    y: int = Field(ge=-512, le=512)
    z: int = Field(ge=-512, le=512)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class VoxelProp(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    prop_id: str = Field(default="", max_length=96)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    size: float = Field(gt=0.0, le=1.0)
    angle: float = Field(ge=-360.0, le=360.0)
    blocks: List[VoxelBlock] = Field(min_length=1, max_length=MAX_VOXEL_BLOCKS)


class PerformanceFrame(BaseModel):
    """Everything the 2.5D stage draws apart from the camera. Camera choice comes from the switcher."""
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    package: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    performers: List[PerformerFrame] = Field(max_length=MAX_PERFORMERS)
    lowerThird: bool = False
    lowerText: str = Field(default="", max_length=160)
    scores: List[int] = Field(default_factory=lambda: [0, 0], min_length=2, max_length=2)
    blackout: bool = False
    hologram: bool = False
    assets: Optional[SetImages] = None
    voxelProp: Optional[VoxelProp] = None
    gestures: List[Gesture] = Field(default_factory=list, max_length=MAX_PERFORMERS)
    # The sender's own monotonic clock in milliseconds. Optional; lets a batch keep its spacing.
    client_ms: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("scores")
    @classmethod
    def _scores(cls, value: List[int]) -> List[int]:
        if not all(-1_000_000 <= v <= 1_000_000 for v in value):
            raise ValueError("scores out of range")
        return value

    @model_validator(mode="after")
    def _unique(self) -> "PerformanceFrame":
        ids = [p.id for p in self.performers]
        if len(set(ids)) != len(ids):
            raise ValueError("performer ids must be unique")
        known = set(ids)
        for gesture in self.gestures:
            if gesture.performer not in known:
                raise ValueError(f"gesture for unknown performer {gesture.performer}")
        return self

    def stage(self) -> Dict[str, Any]:
        """The frame without its one-shot parts (gestures) or sender clock: what stays on screen."""
        return self.model_dump(exclude={"gestures", "client_ms"}, exclude_none=True)


class PerformanceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    frames: List[PerformanceFrame] = Field(min_length=1, max_length=MAX_BATCH)

    @model_validator(mode="after")
    def _clocked(self) -> "PerformanceBatch":
        if len(self.frames) > 1:
            stamps = [f.client_ms for f in self.frames]
            if any(s is None for s in stamps):
                raise ValueError("every frame in a batch needs client_ms")
            if any(b < a for a, b in zip(stamps, stamps[1:])):
                raise ValueError("client_ms must not go backwards within a batch")
        return self


class PerformanceAuthority:
    """Keeps the latest stage, records every change into live takes, and tells pages about it.

    ``record`` is ``RecordingModeController.record_event``: it writes to every take that is
    recording (not paused) and returns how many took it. ``broadcast`` sends a hub system event.
    """

    def __init__(self, *, record: Optional[Callable[..., int]] = None,
                 broadcast: Optional[Callable[[Dict[str, Any]], Any]] = None,
                 clock: Callable[[], float] = time.monotonic):
        self._record = record
        self._broadcast = broadcast
        self._clock = clock
        self._lock = threading.Lock()
        self.sequence = 0
        self.latest: Optional[Dict[str, Any]] = None
        self.latest_at: Optional[float] = None
        self.actor: Optional[str] = None
        self._last_broadcast = 0.0
        self.recorded = 0
        self.unchanged = 0

    def publish(self, frames: List[PerformanceFrame], *, actor: str) -> Dict[str, Any]:
        now = self._clock()
        newest = frames[-1].client_ms
        stage_changed = False
        takes = 0
        with self._lock:
            for frame in frames:
                stage = frame.stage()
                gestures = [g.model_dump() for g in frame.gestures]
                if stage == self.latest and not gestures:
                    self.unchanged += 1
                    continue
                # Frames in a batch keep their spacing: each lands as long before "now" as the
                # sender says it came before the newest one.
                at = now
                if newest is not None and frame.client_ms is not None:
                    at = now - max(0.0, (newest - frame.client_ms) / 1000.0)
                self.sequence += 1
                stage_changed = stage_changed or stage != self.latest
                self.latest, self.latest_at, self.actor = stage, now, actor
                entry = {"sequence": self.sequence, "stage": stage}
                if gestures:
                    entry["gestures"] = gestures
                if self._record is not None:
                    try:
                        takes = max(takes, self._record("performance.frame", entry, at=at))
                    except Exception:
                        logger.exception("Performance frame %s could not be recorded", self.sequence)
                self.recorded += 1
            sequence = self.sequence
            message = None
            if stage_changed and self._broadcast is not None and now - self._last_broadcast >= BROADCAST_MIN_INTERVAL:
                self._last_broadcast = now
                message = {"type": "performance_state", "payload": {"sequence": sequence, "stage": self.latest}}
        if message is not None:
            try:
                self._broadcast(message)
            except Exception:
                logger.exception("Performance state broadcast failed")
        return {"ok": True, "sequence": sequence, "takes_recording": takes}

    def snapshot(self) -> Optional[tuple]:
        """The stage as it is now, for a take that is just beginning (RecordingModeController.snapshot_providers)."""
        with self._lock:
            if self.latest is None:
                return None
            return ("performance.frame", {"sequence": self.sequence, "stage": self.latest, "snapshot": True})

    def state(self) -> Dict[str, Any]:
        with self._lock:
            age = None if self.latest_at is None else round(self._clock() - self.latest_at, 3)
            return {"sequence": self.sequence, "stage": self.latest, "age_seconds": age,
                    "recorded_frames": self.recorded, "unchanged_frames_skipped": self.unchanged}


def create_performance_router(authority: PerformanceAuthority) -> APIRouter:
    router = APIRouter(prefix="/api/performance", tags=["Performer data"])

    def actor_of(identity: Dict[str, Any]) -> str:
        return str(identity.get("user_id") or identity.get("username") or "operator")

    @router.put("/frame")
    async def put_frame(frame: PerformanceFrame, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return authority.publish([frame], actor=actor_of(identity))

    @router.post("/frames")
    async def post_frames(batch: PerformanceBatch, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return authority.publish(batch.frames, actor=actor_of(identity))

    @router.get("/state")
    async def get_state(identity: Dict[str, Any] = Depends(require_role("mod"))):
        return authority.state()

    return router


__all__ = ["PerformanceFrame", "PerformanceBatch", "PerformerFrame", "PerformanceAuthority",
           "create_performance_router"]
