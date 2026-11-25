"""
PubCast Avatar Behavior Runtime
===============================

System-level coordinator for avatar motion. This sits between PubCast's HTTP/WS
surface and the behavior/mocap motion pipeline.

It is intentionally UI-free. Control room, stage renderer, Codex tools, mocap
capture clients, and avatar performers can all talk to this runtime through the
same request/event shapes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
import json
import time

try:
    from modules.behavior_motion_pipeline import (
        AvatarMotionProfile,
        BehaviorMotionPipeline,
        EmotionCue,
        EmotionLabel,
        MocapFrame,
        MocapJoint,
    )
except Exception:  # pragma: no cover - direct module testing fallback
    from behavior_motion_pipeline import (
        AvatarMotionProfile,
        BehaviorMotionPipeline,
        EmotionCue,
        EmotionLabel,
        MocapFrame,
        MocapJoint,
    )


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class AvatarRuntimeConfig:
    avatar_id: str
    display_name: str = "Avatar"
    is_seated: bool = False
    room: str = "studio"
    profile: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeTickResult:
    ok: bool
    avatar_id: str
    event: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


class AvatarBehaviorRuntime:
    """
    Owns one BehaviorMotionPipeline per avatar and emits renderer-friendly
    command bundles.

    Event emitted to WebSocket:
        {
          "type": "avatar_motion_commands",
          "payload": {
            "avatar_id": "manny",
            "room": "studio",
            "commands": [...],
            "state": {...},
            "source": "behavior_runtime"
          }
        }
    """

    def __init__(self, data_dir: Path | str, default_room: str = "studio") -> None:
        self.data_dir = Path(data_dir)
        self.default_room = default_room
        self.config_path = self.data_dir / "avatar_behavior_profiles.json"
        self.pipelines: Dict[str, BehaviorMotionPipeline] = {}
        self.configs: Dict[str, AvatarRuntimeConfig] = {}
        self.last_events: Dict[str, Dict[str, Any]] = {}
        self.load_profiles()

    # ------------------------------------------------------------------
    # Profile persistence
    # ------------------------------------------------------------------
    def load_profiles(self) -> None:
        if not self.config_path.exists():
            self._seed_defaults()
            self.save_profiles()
            return
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        avatars = raw.get("avatars", {}) if isinstance(raw, dict) else {}
        if not avatars:
            self._seed_defaults()
            return
        for avatar_id, cfg in avatars.items():
            if isinstance(cfg, dict):
                self.configs[avatar_id] = AvatarRuntimeConfig(
                    avatar_id=avatar_id,
                    display_name=str(cfg.get("display_name", avatar_id.title())),
                    is_seated=bool(cfg.get("is_seated", False)),
                    room=str(cfg.get("room", self.default_room)),
                    profile=dict(cfg.get("profile", {})),
                )

    def save_profiles(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {"avatars": {aid: asdict(cfg) for aid, cfg in sorted(self.configs.items())}}
        self.config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _seed_defaults(self) -> None:
        self.configs = {
            "manny": AvatarRuntimeConfig(
                avatar_id="manny",
                display_name="Manny",
                is_seated=False,
                profile={
                    "expressiveness": 0.50,
                    "fidget_rate": 0.30,
                    "nod_rate": 0.45,
                    "gesture_rate": 0.42,
                    "stillness_preference": 0.42,
                    "politeness": 0.70,
                    "camera_awareness": 0.62,
                    "preferred_hand": "right",
                    "emotional_inertia": 0.76,
                },
            ),
            "sheila": AvatarRuntimeConfig(
                avatar_id="sheila",
                display_name="Sheila",
                is_seated=False,
                profile={
                    "expressiveness": 0.68,
                    "fidget_rate": 0.40,
                    "nod_rate": 0.58,
                    "gesture_rate": 0.55,
                    "stillness_preference": 0.30,
                    "politeness": 0.72,
                    "camera_awareness": 0.72,
                    "preferred_hand": "right",
                    "emotional_inertia": 0.64,
                },
            ),
        }

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------
    def ensure_avatar(self, avatar_id: str, updates: Optional[Mapping[str, Any]] = None) -> BehaviorMotionPipeline:
        avatar_id = str(avatar_id or "default")
        if avatar_id not in self.configs:
            self.configs[avatar_id] = AvatarRuntimeConfig(avatar_id=avatar_id, display_name=avatar_id.title(), room=self.default_room)
        if updates:
            self.update_profile(avatar_id, updates, persist=False)
        if avatar_id not in self.pipelines:
            cfg = self.configs[avatar_id]
            profile_kwargs = dict(cfg.profile)
            profile_kwargs["avatar_id"] = avatar_id
            profile = AvatarMotionProfile(**profile_kwargs)
            pipe = BehaviorMotionPipeline(profile)
            pipe.state.is_seated = cfg.is_seated
            self.pipelines[avatar_id] = pipe
        return self.pipelines[avatar_id]

    def update_profile(self, avatar_id: str, updates: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        cfg = self.configs.get(avatar_id) or AvatarRuntimeConfig(avatar_id=avatar_id)
        if "display_name" in updates:
            cfg.display_name = str(updates["display_name"])
        if "room" in updates:
            cfg.room = str(updates["room"])
        if "is_seated" in updates:
            cfg.is_seated = bool(updates["is_seated"])
        profile_updates = dict(updates.get("profile", {}))
        for key in (
            "expressiveness", "fidget_rate", "nod_rate", "gesture_rate", "stillness_preference",
            "politeness", "camera_awareness", "preferred_hand", "emotional_inertia", "random_seed",
        ):
            if key in updates:
                profile_updates[key] = updates[key]
        cfg.profile.update(profile_updates)
        self.configs[avatar_id] = cfg
        if avatar_id in self.pipelines:
            del self.pipelines[avatar_id]
        if persist:
            self.save_profiles()
        return asdict(cfg)

    def list_avatars(self) -> List[Dict[str, Any]]:
        return [asdict(cfg) for cfg in self.configs.values()]

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "avatars": self.list_avatars(),
            "active_pipelines": sorted(self.pipelines.keys()),
            "last_events": self.last_events,
        }

    # ------------------------------------------------------------------
    # Input normalization
    # ------------------------------------------------------------------
    def parse_mocap_frame(self, raw: Optional[Mapping[str, Any]]) -> Optional[MocapFrame]:
        if not raw:
            return None
        joints_raw = raw.get("joints") or raw.get("landmarks") or raw.get("bones") or {}
        joints: Dict[str, MocapJoint] = {}
        if isinstance(joints_raw, Mapping):
            for name, value in joints_raw.items():
                if isinstance(value, Mapping):
                    joints[str(name)] = MocapJoint(
                        x=float(value.get("x", 0.0)),
                        y=float(value.get("y", 0.0)),
                        z=float(value.get("z", 0.0)),
                        confidence=float(value.get("confidence", value.get("visibility", 1.0))),
                    )
                elif isinstance(value, (list, tuple)) and len(value) >= 2:
                    joints[str(name)] = MocapJoint(
                        x=float(value[0]),
                        y=float(value[1]),
                        z=float(value[2]) if len(value) >= 3 else 0.0,
                        confidence=float(value[3]) if len(value) >= 4 else 1.0,
                    )
        return MocapFrame(
            timestamp_ms=int(raw.get("timestamp_ms", raw.get("timestampMs", now_ms()))),
            joints=joints,
            source=str(raw.get("source", "unknown_mocap")),
            body_confidence=float(raw.get("body_confidence", raw.get("bodyConfidence", 1.0 if joints else 0.0))),
            face_confidence=float(raw.get("face_confidence", raw.get("faceConfidence", 0.0))),
            hands_confidence=float(raw.get("hands_confidence", raw.get("handsConfidence", 0.0))),
        )

    def push_emotion(self, avatar_id: str, label: str, intensity: float = 0.5, ttl_ms: int = 2500, source: str = "manual") -> RuntimeTickResult:
        pipe = self.ensure_avatar(avatar_id)
        ts = now_ms()
        try:
            emotion = EmotionLabel(label)
        except Exception:
            emotion = EmotionLabel.NEUTRAL
        pipe.push_emotion(EmotionCue(label=emotion, intensity=float(intensity), source=source, expires_at_ms=ts + int(ttl_ms)))
        return self.tick(avatar_id, now_ms=ts)

    def tick(
        self,
        avatar_id: str,
        *,
        now_ms: Optional[int] = None,
        elapsed_ms: Optional[int] = None,
        explicit_intent: Optional[str] = None,
        transcript_text: Optional[str] = None,
        mocap_frame: Optional[Mapping[str, Any] | MocapFrame] = None,
        is_seated: Optional[bool] = None,
        room: Optional[str] = None,
    ) -> RuntimeTickResult:
        ts = int(now_ms if now_ms is not None else globals()["now_ms"]())
        pipe = self.ensure_avatar(avatar_id)
        cfg = self.configs[avatar_id]
        if is_seated is None:
            is_seated = cfg.is_seated
        if room is not None:
            cfg.room = str(room)
        frame = mocap_frame if isinstance(mocap_frame, MocapFrame) else self.parse_mocap_frame(mocap_frame)
        output = pipe.tick(
            now_ms=ts,
            elapsed_ms=elapsed_ms,
            explicit_intent=explicit_intent,
            transcript_text=transcript_text,
            mocap_frame=frame,
            is_seated=is_seated,
        )
        commands = [asdict(cmd) if hasattr(cmd, "__dataclass_fields__") else cmd for cmd in output.commands]
        event = {
            "type": "avatar_motion_commands",
            "payload": {
                "avatar_id": avatar_id,
                "room": cfg.room,
                "commands": commands,
                "state": output.state_snapshot,
                "decision": self._decision_dict(output.decision),
                "warnings": output.warnings,
                "source": "avatar_behavior_runtime",
                "timestamp_ms": ts,
            },
        }
        self.last_events[avatar_id] = event["payload"]
        return RuntimeTickResult(ok=True, avatar_id=avatar_id, event=event, warnings=output.warnings)

    @staticmethod
    def _decision_dict(decision: Any) -> Optional[Dict[str, Any]]:
        if decision is None:
            return None
        if hasattr(decision, "__dataclass_fields__"):
            data = asdict(decision)
        elif isinstance(decision, Mapping):
            data = dict(decision)
        else:
            data = {k: getattr(decision, k) for k in dir(decision) if not k.startswith("_") and not callable(getattr(decision, k))}
        return data

    def ingest_payload(self, payload: Mapping[str, Any]) -> RuntimeTickResult:
        avatar_id = str(payload.get("avatar_id", payload.get("avatarId", "manny")))
        return self.tick(
            avatar_id,
            explicit_intent=payload.get("intent"),
            transcript_text=payload.get("text") or payload.get("transcript_text") or payload.get("transcriptText"),
            mocap_frame=payload.get("mocap") or payload.get("frame") or payload.get("mocap_frame"),
            is_seated=payload.get("is_seated", payload.get("isSeated")) if ("is_seated" in payload or "isSeated" in payload) else None,
            room=payload.get("room"),
        )
