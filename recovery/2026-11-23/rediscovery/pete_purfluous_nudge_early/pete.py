#!/usr/bin/env python3
"""
pete.py — Pete, PubCast AI Production Engine
════════════════════════════════════════════════════════════════════════════════
Rear View Foresight LLC · Feic Mo Chroí™

Pete sits at the engine level. He sees what is actually loaded, actually
costing, and actually running. He does not infer — he reads live metrics.
"""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("pubcast.pete")

BUDGET_TARGETS: Dict[str, float] = {
    "triangles": 400_000, "draw_calls": 150, "texture_mb": 256,
    "physics_objects": 50, "particle_systems": 5, "materials": 40,
}
BUDGET_CEILINGS: Dict[str, float] = {
    "triangles": 600_000, "draw_calls": 250, "texture_mb": 512,
    "physics_objects": 100, "particle_systems": 10, "materials": 80,
}
QUALITY_TIER_1_THRESHOLD = 1.30
QUALITY_TIER_2_THRESHOLD = 1.60
QUALITY_REFUSE_THRESHOLD = 1.80
FRAME_DROP_NOISE_THRESHOLD   = 1
FRAME_DROP_PATTERN_THRESHOLD = 3
FRAME_DROP_WINDOW_SECONDS    = 8.0
PLANNED_SKIP_RATE            = 2
WARN_PCT    = 0.80
CAUTION_PCT = 0.90

class QualityTier(str, Enum):
    STANDARD  = "standard"
    REDUCED_1 = "reduced_1"
    REDUCED_2 = "reduced_2"
    REFUSED   = "refused"

class CueType(str, Enum):
    TIMECODE        = "timecode"
    POSITION_CROSS  = "position_cross"
    AUDIO_EVENT     = "audio_event"
    SOUND_COMPLETE  = "sound_complete"
    PHYSICS_SETTLED = "physics_settled"
    CHAIN           = "chain"

class CueAction(str, Enum):
    CUT            = "cut"
    AUTO_CUT       = "auto_cut"
    ACTION         = "action"
    DETONATE       = "detonate"
    CAMERA_SWITCH  = "camera_switch"
    CHUNK_BOUNDARY = "chunk_boundary"
    CUSTOM         = "custom"

class CueState(str, Enum):
    ARMED     = "armed"
    TRIGGERED = "triggered"
    FIRED     = "fired"
    CANCELLED = "cancelled"

class TakeState(str, Enum):
    IDLE    = "idle"
    ARMED   = "armed"
    ROLLING = "rolling"
    CUT     = "cut"

@dataclass
class SceneMarker:
    marker_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:      str = "marker"
    position:  Tuple[float, float, float] = (0.0, 0.0, 0.0)
    tolerance: float = 0.5
    normal:    Optional[Tuple[float, float, float]] = None
    def to_dict(self) -> Dict[str, Any]:
        return {"marker_id": self.marker_id, "name": self.name,
                "position": list(self.position), "tolerance": self.tolerance,
                "normal": list(self.normal) if self.normal else None}
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SceneMarker":
        return cls(marker_id=d.get("marker_id", str(uuid.uuid4())[:8]),
                   name=d.get("name","marker"), position=tuple(d["position"]),
                   tolerance=d.get("tolerance",0.5),
                   normal=tuple(d["normal"]) if d.get("normal") else None)

@dataclass
class AutoCutCue:
    cue_id:         str       = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:           str       = "cue"
    cue_type:       CueType   = CueType.TIMECODE
    action:         CueAction = CueAction.AUTO_CUT
    scene_time_s:   Optional[float] = None
    character_id:   Optional[str]   = None
    marker_id:      Optional[str]   = None
    sound_name:     Optional[str]   = None
    count:          int             = 1
    chain_cue_id:   Optional[str]   = None
    delay_s:        float           = 0.0
    guard_after_s:  float           = 0.0
    camera_id:      Optional[str]   = None
    instance_id:    Optional[str]   = None
    custom_payload: Optional[Dict[str, Any]] = None
    state:          CueState        = CueState.ARMED
    triggered_at_s: Optional[float] = None
    fired_at_s:     Optional[float] = None
    _event_count:   int             = field(default=0, repr=False)
    def to_dict(self) -> Dict[str, Any]:
        return {"cue_id": self.cue_id, "name": self.name,
                "cue_type": self.cue_type.value, "action": self.action.value,
                "scene_time_s": self.scene_time_s, "character_id": self.character_id,
                "marker_id": self.marker_id, "sound_name": self.sound_name,
                "count": self.count, "chain_cue_id": self.chain_cue_id,
                "delay_s": self.delay_s, "guard_after_s": self.guard_after_s,
                "state": self.state.value,
                "triggered_at_s": self.triggered_at_s, "fired_at_s": self.fired_at_s}
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AutoCutCue":
        return cls(cue_id=d.get("cue_id", str(uuid.uuid4())[:8]),
                   name=d.get("name","cue"), cue_type=CueType(d.get("cue_type","timecode")),
                   action=CueAction(d.get("action","auto_cut")),
                   scene_time_s=d.get("scene_time_s"), character_id=d.get("character_id"),
                   marker_id=d.get("marker_id"), sound_name=d.get("sound_name"),
                   count=d.get("count",1), chain_cue_id=d.get("chain_cue_id"),
                   delay_s=d.get("delay_s",0.0), guard_after_s=d.get("guard_after_s",0.0),
                   camera_id=d.get("camera_id"), instance_id=d.get("instance_id"),
                   custom_payload=d.get("custom_payload"),
                   state=CueState(d.get("state","armed")))

@dataclass
class AssetBudgetRecord:
    instance_id:   str
    asset_name:    str
    asset_tier:    str
    triangles:     float = 0
    draw_calls:    float = 0
    texture_mb:    float = 0
    physics_count: float = 0
    materials:     float = 0

@dataclass
class BudgetReport:
    totals:           Dict[str, float]
    targets:          Dict[str, float]
    ceilings:         Dict[str, float]
    pct_of_target:    Dict[str, float]
    pct_of_ceiling:   Dict[str, float]
    quality_tier:     QualityTier
    overloaded_pools: List[str]
    heaviest_assets:  List[Tuple[str, str, float]]
    timestamp:        float = field(default_factory=time.time)
    def summary_line(self) -> str:
        pct = max(self.pct_of_target.values()) * 100
        h = self.heaviest_assets[0] if self.heaviest_assets else None
        h_str = f" Heaviest: {h[0]} at {h[2]:,.0f} {h[1]}." if h else ""
        return f"Scene at {pct:.0f}% of target budget (quality: {self.quality_tier.value}).{h_str}"

class BudgetTracker:
    def __init__(self) -> None:
        self._assets: Dict[str, AssetBudgetRecord] = {}
    def register(self, r: AssetBudgetRecord) -> None:
        self._assets[r.instance_id] = r
    def unregister(self, instance_id: str) -> None:
        self._assets.pop(instance_id, None)
    def add_fragments(self, instance_id: str, count: int) -> None:
        if instance_id in self._assets:
            self._assets[instance_id].physics_count += count
    def clear_fragments(self, instance_id: str) -> None:
        if instance_id in self._assets:
            self._assets[instance_id].physics_count = 0
    def totals(self) -> Dict[str, float]:
        t: Dict[str, float] = {k: 0.0 for k in BUDGET_TARGETS}
        for r in self._assets.values():
            t["triangles"]        += r.triangles
            t["draw_calls"]       += r.draw_calls
            t["texture_mb"]       += r.texture_mb
            t["physics_objects"]  += r.physics_count
            t["materials"]        += r.materials
        return t
    def quality_tier(self, totals: Optional[Dict[str, float]] = None) -> QualityTier:
        tt = totals or self.totals()
        max_ratio = max(tt.get(k,0)/max(BUDGET_TARGETS[k],1) for k in BUDGET_TARGETS)
        if max_ratio >= QUALITY_REFUSE_THRESHOLD: return QualityTier.REFUSED
        if max_ratio >= QUALITY_TIER_2_THRESHOLD: return QualityTier.REDUCED_2
        if max_ratio >= QUALITY_TIER_1_THRESHOLD: return QualityTier.REDUCED_1
        return QualityTier.STANDARD
    def report(self) -> BudgetReport:
        tt  = self.totals()
        pt  = {k: tt.get(k,0)/max(BUDGET_TARGETS[k],1)  for k in BUDGET_TARGETS}
        pc  = {k: tt.get(k,0)/max(BUDGET_CEILINGS[k],1) for k in BUDGET_CEILINGS}
        ov  = [k for k,v in pt.items() if v >= WARN_PCT]
        qt  = self.quality_tier(tt)
        fmap = {"triangles":"triangles","draw_calls":"draw_calls",
                "texture_mb":"texture_mb","physics_objects":"physics_count","materials":"materials"}
        heavy: List[Tuple[str,str,float]] = []
        for pool in ov:
            attr = fmap.get(pool, pool)
            top = max(self._assets.values(), key=lambda r: getattr(r,attr,0), default=None)
            if top: heavy.append((top.asset_name, pool, getattr(top,attr,0)))
        return BudgetReport(totals=tt, targets=dict(BUDGET_TARGETS), ceilings=dict(BUDGET_CEILINGS),
                            pct_of_target=pt, pct_of_ceiling=pc, quality_tier=qt,
                            overloaded_pools=ov, heaviest_assets=heavy)
    def check_asset(self, record: AssetBudgetRecord) -> List[str]:
        tier_limits = {
            "hero":{"triangles":8_000,"materials":2}, "standard":{"triangles":2_000,"materials":1},
            "background":{"triangles":500,"materials":1}, "default":{"triangles":30_000,"materials":2},
            "featured":{"triangles":60_000,"materials":3}, "crowd":{"triangles":12_000,"materials":1},
        }
        lim = tier_limits.get(record.asset_tier.lower(), {})
        viols = []
        if record.triangles > lim.get("triangles", float("inf")):
            viols.append(f"{record.asset_name}: {record.triangles:,.0f} tris exceeds {record.asset_tier} limit of {lim['triangles']:,}")
        if record.materials > lim.get("materials", float("inf")):
            viols.append(f"{record.asset_name}: {record.materials} materials exceeds {record.asset_tier} limit of {lim['materials']}")
        return viols

@dataclass
class DropEvent:
    scene_time_s: float
    wall_time:    float = field(default_factory=time.time)

class FrameMonitor:
    def __init__(self) -> None:
        self._drops: List[DropEvent] = []
        self._using_frame_skip = False
        self._skip_rate = PLANNED_SKIP_RATE
        self._target_fps = 60
    def record_drop(self, scene_time_s: float) -> None:
        self._drops.append(DropEvent(scene_time_s=scene_time_s))
    def enable_planned_skip(self, skip_rate: int = PLANNED_SKIP_RATE) -> None:
        self._using_frame_skip = True
        self._skip_rate = skip_rate
        logger.info("Pete: planned frame skip armed — %d/sec at %dfps", skip_rate, self._target_fps)
    def disable_planned_skip(self) -> None:
        self._using_frame_skip = False
    def recent_drops(self, window_s: float = FRAME_DROP_WINDOW_SECONDS) -> List[DropEvent]:
        cutoff = time.time() - window_s
        return [d for d in self._drops if d.wall_time >= cutoff]
    def drop_pattern_detected(self) -> bool:
        return len(self.recent_drops()) >= FRAME_DROP_PATTERN_THRESHOLD
    def drop_summary(self) -> Dict[str, Any]:
        recent = self.recent_drops()
        return {"total_drops": len(self._drops), "recent_drops": len(recent),
                "pattern_detected": len(recent) >= FRAME_DROP_PATTERN_THRESHOLD,
                "planned_skip_active": self._using_frame_skip,
                "planned_skip_rate": self._skip_rate if self._using_frame_skip else 0,
                "drop_timestamps": [d.scene_time_s for d in self._drops[-20:]]}
    def reset(self) -> None:
        self._drops.clear()

class WindowCalculator:
    SAMPLE_WINDOW = 10
    def __init__(self) -> None:
        self._samples: List[Tuple[float, Dict[str, float]]] = []
        self._critical_pct = 0.95

    # Number of samples to keep for trend calculation
    # Each sample is a (timestamp, totals_dict) pair

    def __init__(self) -> None:
        self._samples: List[Tuple[float, Dict[str, float]]] = []
        self._critical_pct = 0.95  # 95% of ceiling = critical

    def record_sample(self, scene_time_s: float, totals: Dict[str, float]) -> None:
        self._samples.append((scene_time_s, dict(totals)))
        # Keep only the last SAMPLE_WINDOW samples
        if len(self._samples) > self.SAMPLE_WINDOW:
            self._samples.pop(0)

    def seconds_to_critical(self) -> Optional[float]:
        """
        Extrapolate the resource consumption curve.
        Returns seconds remaining before any pool hits critical (95% of ceiling).
        Returns None if trajectory is flat or improving.
        """
        if len(self._samples) < 2:
            return None

        now_s, now_totals = self._samples[-1]
        first_s, first_totals = self._samples[0]
        elapsed = now_s - first_s
        if elapsed < 0.1:
            return None

        worst_remaining = None

        for pool in BUDGET_CEILINGS:
            ceiling  = BUDGET_CEILINGS[pool]
            critical = ceiling * self._critical_pct
            current  = now_totals.get(pool, 0)
            initial  = first_totals.get(pool, 0)

            rate_per_s = (current - initial) / elapsed  # units per second
            if rate_per_s <= 0:
                continue  # pool is flat or shrinking

            headroom = critical - current
            if headroom <= 0:
                return 0.0  # already at critical

            secs = headroom / rate_per_s
            if worst_remaining is None or secs < worst_remaining:
                worst_remaining = secs

        return worst_remaining

    def window_report(self, scene_time_s: float, totals: Dict[str, float]) -> Dict[str, Any]:
        self.record_sample(scene_time_s, totals)
        remaining = self.seconds_to_critical()
        return {
            "scene_time_s":      scene_time_s,
            "seconds_to_critical": remaining,
            "has_window":        remaining is not None,
            "window_message":    (
                f"I can give you {remaining:.0f} seconds before this scene hits critical."
                if remaining is not None and remaining > 0
                else "Scene is already at or past critical resource threshold."
            ),
        }

    def reset(self) -> None:
        self._samples.clear()


# ══════════════════════════════════════════════════════════════════════════════
# ACTION READINESS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReadinessCheck:
    name:    str
    passed:  bool
    message: str
    severity:str = "info"  # "info", "warn", "critical"


@dataclass
class ActionReadinessReport:
    """
    Pete's assessment of whether the scene can survive the frame-1 spike.
    """
    survivable:         bool
    checks:             List[ReadinessCheck]
    quality_tier:       QualityTier
    recommended_actions:List[str]
    chunk_recommended:  bool
    chunk_size_s:       Optional[float]
    frame_skip_recommended: bool
    message:            str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "survivable":              self.survivable,
            "quality_tier":            self.quality_tier.value,
            "checks":                  [{"name":c.name,"passed":c.passed,"message":c.message,"severity":c.severity} for c in self.checks],
            "recommended_actions":     self.recommended_actions,
            "chunk_recommended":       self.chunk_recommended,
            "chunk_size_s":            self.chunk_size_s,
            "frame_skip_recommended":  self.frame_skip_recommended,
            "message":                 self.message,
        }


# ══════════════════════════════════════════════════════════════════════════════
# PETE
# ══════════════════════════════════════════════════════════════════════════════

class Pete:
    """
    PubCast AI Production Engine.

    One instance per application. Manages budget, frame performance,
    action readiness, chunking, window calculation, and the auto-cut
    cue system.

    Communication discipline:
        Pete NEVER surfaces mid-take unless it is an auto-cut firing.
        All reports delivered between takes, after cut, or on request.
        Every observation goes to the black box regardless of surfacing.

    Handle / tail discipline:
        Every cut — manual, auto, cue-fired, chunk boundary — is followed
        by a 5-second recording tail before capture actually stops.
        Every exported clip carries 5-second handles on both sides.
        Pete accounts for the 5-second tail in all window calculations.
    """

    TAIL_SECONDS     = 5.0   # recording tail after any cut
    HANDLE_SECONDS   = 5.0   # handle on each side of exported clip

    def __init__(
        self,
        hub:    Any,                    # modules.hub.Hub
        irm:    Optional[Any] = None,   # modules.irm.IRMController
        rec:    Optional[Any] = None,   # modules.recording.RecordingService
        on_cut: Optional[Callable] = None,  # async callback when Pete fires a cut
        on_action: Optional[Callable] = None,  # async callback when Pete fires action
    ) -> None:
        self.hub          = hub
        self.irm          = irm
        self.rec          = rec
        self._on_cut      = on_cut
        self._on_action   = on_action

        self.budget       = BudgetTracker()
        self.frames       = FrameMonitor()
        self.window       = WindowCalculator()

        self._state       = TakeState.IDLE
        self._action_time: Optional[float] = None  # wall-clock
        self._cues:       List[AutoCutCue]  = []
        self._markers:    Dict[str, SceneMarker] = {}
        self._cue_task:   Optional[asyncio.Task] = None
        self._chunk_size_s: Optional[float] = None
        self._next_chunk_at_s: Optional[float] = None

        # Black box — every event logged here regardless of surfacing
        self._black_box:  List[Dict[str, Any]] = []

        # Deferred report — built during take, delivered after cut
        self._deferred_report: List[str] = []

        logger.info("Pete initialised")

    # ── Black box ──────────────────────────────────────────────────────────

    def _log(self, event_type: str, surface: bool = False, **payload: Any) -> None:
        """
        Write to the black box. Always. Surfacing is separate and optional.
        Nothing is ever silently dismissed.
        """
        entry = {
            "ts":           time.time(),
            "scene_s":      self._scene_time(),
            "event_type":   event_type,
            "surface":      surface,
            **payload,
        }
        self._black_box.append(entry)
        if surface:
            self._deferred_report.append(
                f"[{entry['scene_s']:.1f}s] {event_type}: "
                + ", ".join(f"{k}={v}" for k, v in payload.items())
            )

    def _scene_time(self) -> float:
        if self._action_time is None:
            return 0.0
        return time.time() - self._action_time

    # ── Asset registration ─────────────────────────────────────────────────

    def register_asset(
        self,
        instance_id: str,
        asset_name:  str,
        asset_tier:  str,
        triangles:   float = 0,
        draw_calls:  float = 0,
        texture_mb:  float = 0,
        physics_count:float= 0,
        materials:   float = 0,
    ) -> List[str]:
        """
        Register a placed asset. Returns list of tier violations (empty = clean).
        Violations are always surfaced immediately — placement time, not take time.
        """
        record = AssetBudgetRecord(
            instance_id  = instance_id,
            asset_name   = asset_name,
            asset_tier   = asset_tier,
            triangles    = triangles,
            draw_calls   = draw_calls,
            texture_mb   = texture_mb,
            physics_count= physics_count,
            materials    = materials,
        )
        violations = self.budget.check_asset(record)
        self.budget.register(record)

        for v in violations:
            self._log("asset_tier_violation", surface=True, violation=v)
            logger.warning("Pete: %s", v)

        report = self.budget.report()
        self._check_budget_thresholds(report, placement=True)

        return violations

    def unregister_asset(self, instance_id: str) -> None:
        self.budget.unregister(instance_id)

    # ── Markers ────────────────────────────────────────────────────────────

    def place_marker(self, marker: SceneMarker) -> None:
        """Place a scene marker. Markers are part of the SLATE."""
        self._markers[marker.marker_id] = marker
        logger.debug("Pete: marker placed '%s' at %s", marker.name, marker.position)

    def remove_marker(self, marker_id: str) -> None:
        self._markers.pop(marker_id, None)

    def list_markers(self) -> List[SceneMarker]:
        return list(self._markers.values())

    # ── Cue sheet ──────────────────────────────────────────────────────────

    def add_cue(self, cue: AutoCutCue) -> None:
        """Add a cue to the cue sheet. Part of the SLATE."""
        self._cues.append(cue)
        logger.debug("Pete: cue added '%s' (%s → %s)", cue.name, cue.cue_type.value, cue.action.value)

    def remove_cue(self, cue_id: str) -> None:
        self._cues = [c for c in self._cues if c.cue_id != cue_id]

    def list_cues(self) -> List[AutoCutCue]:
        return list(self._cues)

    def clear_cues(self) -> None:
        self._cues.clear()

    def arm_cues(self) -> None:
        """Reset all cues to ARMED state for a fresh take."""
        for cue in self._cues:
            cue.state          = CueState.ARMED
            cue.triggered_at_s = None
            cue.fired_at_s     = None
            cue._event_count   = 0

    # ── Chunking ───────────────────────────────────────────────────────────

    def set_chunk_size(self, seconds: Optional[float]) -> None:
        """
        Configure Pete to auto-cut every N seconds for chunk-based takes.
        None disables chunking. SLATE clock is never reset between chunks.
        """
        self._chunk_size_s = seconds
        if seconds:
            logger.info("Pete: chunking armed at %.1f second intervals", seconds)
        else:
            logger.info("Pete: chunking disabled")

    # ── Action readiness ───────────────────────────────────────────────────

    async def action_readiness(
        self,
        avatar_count:     int = 0,
        destructibles:    int = 0,
        particle_systems: int = 0,
        partial_textures: int = 0,
    ) -> ActionReadinessReport:
        """
        Simulate the frame-1 spike. Assess survivability before Action is called.
        Does NOT simulate the entire take — only the concurrency burst at start.
        """
        checks:   List[ReadinessCheck] = []
        recs:     List[str]            = []
        critical  = False

        report = self.budget.report()

        # ── Budget state ──────────────────────────────────────────────────
        if report.quality_tier == QualityTier.REFUSED:
            checks.append(ReadinessCheck(
                "Budget", False,
                "Scene exceeds 180% of target budget. Pete cannot compensate.",
                "critical"
            ))
            critical = True
        elif report.quality_tier == QualityTier.REDUCED_2:
            checks.append(ReadinessCheck(
                "Budget", True,
                "Scene at 130-160% of target. Recording at reduced quality tier 2.",
                "warn"
            ))
            recs.append("Consider removing one heavy asset before recording a final take.")
        elif report.quality_tier == QualityTier.REDUCED_1:
            checks.append(ReadinessCheck(
                "Budget", True,
                "Scene at 100-130% of target. Recording at reduced quality tier 1.",
                "warn"
            ))
        else:
            checks.append(ReadinessCheck("Budget", True, "Scene within standard budget.", "info"))

        # ── Physics init spike ─────────────────────────────────────────────
        if destructibles > 0:
            physics_at_frame1 = report.totals.get("physics_objects", 0) + (destructibles * 10)
            if physics_at_frame1 > BUDGET_CEILINGS["physics_objects"]:
                checks.append(ReadinessCheck(
                    "Physics Init", False,
                    f"{destructibles} destruction profiles arming simultaneously will push "
                    f"physics objects to ~{physics_at_frame1:.0f} at frame 1 (ceiling: {BUDGET_CEILINGS['physics_objects']:.0f}).",
                    "critical"
                ))
                recs.append("Stagger destruction arm timing by 2 frames each to spread physics load.")
                critical = True
            else:
                checks.append(ReadinessCheck(
                    "Physics Init", True,
                    f"{destructibles} destructibles arming. Estimated frame-1 physics: {physics_at_frame1:.0f}.",
                    "info"
                ))

        # ── Avatar activation spike ────────────────────────────────────────
        if avatar_count > 4:
            checks.append(ReadinessCheck(
                "Avatar Activation", True,
                f"{avatar_count} avatars activating simultaneously. "
                "Animation blend trees initialising at frame 1. Watching.",
                "warn"
            ))
            recs.append("Consider staggering avatar activation by 1 frame each.")
        else:
            checks.append(ReadinessCheck(
                "Avatar Activation", True,
                f"{avatar_count} avatars — activation spike manageable.",
                "info"
            ))

        # ── Texture streaming ──────────────────────────────────────────────
        if partial_textures > 0:
            checks.append(ReadinessCheck(
                "Texture Streaming", True,
                f"{partial_textures} asset(s) at partial texture load. "
                f"Will spike streaming budget at frame 1.",
                "warn"
            ))
            recs.append(
                f"Give Pete {partial_textures * 2} seconds to fully load textures before calling Action."
            )

        # ── Particle systems ───────────────────────────────────────────────
        if particle_systems > BUDGET_TARGETS["particle_systems"]:
            checks.append(ReadinessCheck(
                "Particle Systems", False,
                f"{particle_systems} particle systems exceeds target of {BUDGET_TARGETS['particle_systems']:.0f}.",
                "warn"
            ))
        else:
            checks.append(ReadinessCheck(
                "Particle Systems", True,
                f"{particle_systems} particle system(s) — within budget.",
                "info"
            ))

        # ── IRM health check ───────────────────────────────────────────────
        if self.irm is not None:
            try:
                health = self.irm.get_health()
                if health.status.value in ("critical", "failed"):
                    checks.append(ReadinessCheck(
                        "System Health", False,
                        f"IRM reports {health.status.value}: "
                        f"CPU {health.cpu_pct:.0f}% / MEM {health.memory_pct:.0f}%.",
                        "critical"
                    ))
                    critical = True
                else:
                    checks.append(ReadinessCheck(
                        "System Health", True,
                        f"IRM: {health.status.value}. "
                        f"CPU {health.cpu_pct:.0f}% / MEM {health.memory_pct:.0f}%.",
                        "info"
                    ))
            except Exception as exc:
                checks.append(ReadinessCheck(
                    "System Health", True,
                    f"IRM check unavailable: {exc}", "warn"
                ))

        # ── Chunking recommendation ────────────────────────────────────────
        chunk_recommended = report.quality_tier in (QualityTier.REDUCED_1, QualityTier.REDUCED_2)
        chunk_size: Optional[float] = self._chunk_size_s
        if chunk_recommended and chunk_size is None:
            chunk_size = 5.0
            recs.append(
                "Pete recommends 5-second chunks for this scene. "
                "SLATE clock stays continuous. Recording is seamless. Call set_chunk_size(5.0)."
            )

        # ── Frame skip recommendation ──────────────────────────────────────
        frame_skip = report.quality_tier != QualityTier.STANDARD

        survivable = not critical
        tier = report.quality_tier

        if critical:
            msg = (
                "Scene is NOT ready for Action. "
                + " ".join(r for c in checks if not c.passed for r in [c.message])
            )
        elif tier == QualityTier.REDUCED_2:
            msg = (
                "I can run this scene at reduced quality tier 2. "
                "Good for previz and rehearsal. Not ideal for a final take. "
                + (f"Chunking at {chunk_size:.0f}s recommended. " if chunk_recommended else "")
                + "Your call."
            )
        elif tier == QualityTier.REDUCED_1:
            msg = (
                "I can run this scene at reduced quality tier 1. "
                "1080p with simplified shadows. Acceptable for most takes. "
                + ("Chunking recommended. " if chunk_recommended else "")
                + "Your call."
            )
        else:
            msg = "Scene is ready for Action. Standard quality. All checks nominal."

        result = ActionReadinessReport(
            survivable            = survivable,
            checks                = checks,
            quality_tier          = tier,
            recommended_actions   = recs,
            chunk_recommended     = chunk_recommended,
            chunk_size_s          = chunk_size,
            frame_skip_recommended= frame_skip,
            message               = msg,
        )

        self._log("action_readiness", surface=False,
                  survivable=survivable, tier=tier.value, message=msg)
        return result

    # ── Take lifecycle ─────────────────────────────────────────────────────

    async def on_action(self) -> None:
        """Called when Action is called. Arms monitoring and cue evaluation."""
        self._state       = TakeState.ROLLING
        self._action_time = time.time()
        self._deferred_report.clear()
        self.frames.reset()
        self.window.reset()
        self.arm_cues()

        if self._chunk_size_s:
            self._next_chunk_at_s = self._chunk_size_s

        if self.frames._using_frame_skip:
            logger.info("Pete: planned frame skip active (%d/sec)", self.frames._skip_rate)

        self._cue_task = asyncio.create_task(self._cue_loop())
        self._log("action", surface=False)
        logger.info("Pete: Action — monitoring armed")

    async def on_cut(self) -> Dict[str, Any]:
        """
        Called when Cut is called (manually or by Pete).
        Recording tail: 5 seconds before capture actually stops.
        Delivers deferred report.
        """
        if self._cue_task:
            self._cue_task.cancel()
            try:
                await self._cue_task
            except asyncio.CancelledError:
                pass
            self._cue_task = None

        self._state = TakeState.CUT
        scene_time  = self._scene_time()

        # 5-second recording tail — capture runs 5 more seconds
        logger.info(
            "Pete: Cut at %.1fs — recording tail %.1fs", scene_time, self.TAIL_SECONDS
        )
        await asyncio.sleep(self.TAIL_SECONDS)

        # Build final report
        budget_report = self.budget.report()
        frame_summary = self.frames.drop_summary()
        window_info   = self.window.window_report(scene_time, budget_report.totals)

        report = {
            "scene_duration_s":   scene_time,
            "tail_s":             self.TAIL_SECONDS,
            "handle_s":           self.HANDLE_SECONDS,
            "budget":             {
                "totals":         budget_report.totals,
                "pct_of_target":  budget_report.pct_of_target,
                "quality_tier":   budget_report.quality_tier.value,
                "overloaded":     budget_report.overloaded_pools,
            },
            "frames":             frame_summary,
            "window":             window_info,
            "cues_fired":         [c.to_dict() for c in self._cues if c.state == CueState.FIRED],
            "deferred_report":    list(self._deferred_report),
            "black_box_entries":  len(self._black_box),
        }

        # Surface deferred report
        if self.deferred_report_has_items():
            await self._surface_report()

        self._log("cut", surface=False,
                  duration_s=scene_time, quality_tier=budget_report.quality_tier.value)
        logger.info("Pete: Cut complete. Report ready.")
        return report

    def deferred_report_has_items(self) -> bool:
        return len(self._deferred_report) > 0

    async def _surface_report(self) -> None:
        """Deliver the deferred report via hub after cut."""
        if not self._deferred_report:
            return
        msg = {
            "type":    "pete_report",
            "payload": {
                "items":   list(self._deferred_report),
                "scene_s": self._scene_time(),
            }
        }
        if self.hub:
            await self.hub.broadcast_system_event(msg)
        self._deferred_report.clear()

    # ── Budget threshold checks ────────────────────────────────────────────

    def _check_budget_thresholds(
        self,
        report: BudgetReport,
        placement: bool = False,
    ) -> None:
        """
        Check if any pool has crossed a warning threshold.
        Placement-time violations surface immediately.
        Take-time violations are deferred until cut.
        """
        for pool, pct in report.pct_of_target.items():
            if pct >= CAUTION_PCT:
                msg = (
                    f"Scene at {pct*100:.0f}% of {pool} target. "
                    f"{report.summary_line()}"
                )
                surface = placement  # immediate only at placement time
                self._log(
                    "budget_threshold_90pct", surface=surface,
                    pool=pool, pct=round(pct, 3), message=msg
                )
                if placement:
                    logger.warning("Pete: %s", msg)

            elif pct >= WARN_PCT:
                msg = f"Scene at {pct*100:.0f}% of {pool} target."
                self._log(
                    "budget_threshold_80pct", surface=placement,
                    pool=pool, pct=round(pct, 3), message=msg
                )

    # ── Frame drop recording ───────────────────────────────────────────────

    def record_frame_drop(self) -> None:
        """
        Call this whenever the renderer reports a dropped frame.
        Pete logs it, checks for patterns, defers any report to post-cut.
        """
        scene_s = self._scene_time()
        self.frames.record_drop(scene_s)
        self._log("frame_drop", surface=False, scene_s=scene_s)

        if self.frames.drop_pattern_detected():
            report = self.budget.report()
            msg = (
                f"Consistent frame drops — {len(self.frames.recent_drops())} "
                f"in the last {FRAME_DROP_WINDOW_SECONDS:.0f}s. "
                f"{report.summary_line()}"
            )
            self._log("frame_drop_pattern", surface=True, message=msg)

    # ── Window monitoring ──────────────────────────────────────────────────

    def tick(self) -> Optional[str]:
        """
        Call periodically during a take (e.g. every second).
        Updates window calculation. Returns a message if Pete needs to
        fire an auto-cut due to window expiry.
        Returns None if everything is nominal.
        """
        if self._state != TakeState.ROLLING:
            return None

        scene_s = self._scene_time()
        report  = self.budget.report()
        win     = self.window.window_report(scene_s, report.totals)

        # Check for imminent window expiry
        remaining = win.get("seconds_to_critical")
        if remaining is not None:
            # Account for 5-second recording tail
            effective_remaining = remaining - self.TAIL_SECONDS
            if effective_remaining <= 0:
                msg = (
                    f"Window expired at {scene_s:.1f}s. "
                    "Firing auto-cut to protect recording integrity."
                )
                self._log("window_auto_cut", surface=True, scene_s=scene_s, message=msg)
                logger.warning("Pete: %s", msg)
                return msg  # Caller should fire the cut

            elif effective_remaining <= 5.0:
                msg = f"Critical in {effective_remaining:.0f}s. Auto-cut imminent."
                self._log("window_warning", surface=True, scene_s=scene_s,
                          effective_remaining=effective_remaining)
                logger.warning("Pete: %s", msg)

        return None

    # ── Cue evaluation loop ────────────────────────────────────────────────

    async def _cue_loop(self) -> None:
        """
        Main cue evaluation loop. Runs every frame-ish (16ms) during a take.
        Evaluates all armed cues. Fires actions when conditions are met.
        Handles delays. Handles chunk boundaries.
        Never raises — logs and continues on any error.
        """
        while self._state == TakeState.ROLLING:
            try:
                scene_s = self._scene_time()

                # ── Chunk boundary ────────────────────────────────────────
                if (self._chunk_size_s is not None and
                        self._next_chunk_at_s is not None and
                        scene_s >= self._next_chunk_at_s):
                    await self._fire_chunk_boundary(scene_s)
                    self._next_chunk_at_s += self._chunk_size_s

                # ── Cue evaluation ────────────────────────────────────────
                for cue in self._cues:
                    if cue.state != CueState.ARMED:
                        continue
                    if scene_s < cue.guard_after_s:
                        continue

                    condition_met = self._evaluate_cue_condition(cue, scene_s)

                    if condition_met and cue.triggered_at_s is None:
                        cue.triggered_at_s = scene_s
                        cue.state = CueState.TRIGGERED

                    if (cue.state == CueState.TRIGGERED and
                            cue.triggered_at_s is not None and
                            scene_s >= cue.triggered_at_s + cue.delay_s):
                        await self._fire_cue(cue, scene_s)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log("cue_loop_error", surface=False, error=str(exc))
                logger.error("Pete cue loop error: %s", exc)

            await asyncio.sleep(0.016)  # ~60fps evaluation

    def _evaluate_cue_condition(self, cue: AutoCutCue, scene_s: float) -> bool:
        """
        Evaluate whether a cue's condition is currently met.
        Position and audio events are fed externally via notify_* methods.
        Timecode is evaluated here directly.
        """
        if cue.cue_type == CueType.TIMECODE:
            return (
                cue.scene_time_s is not None and
                scene_s >= cue.scene_time_s
            )

        elif cue.cue_type == CueType.CHAIN:
            # True when the referenced cue has fired
            if cue.chain_cue_id is None:
                return False
            ref = next((c for c in self._cues if c.cue_id == cue.chain_cue_id), None)
            return ref is not None and ref.state == CueState.FIRED

        elif cue.cue_type == CueType.PHYSICS_SETTLED:
            # True when there are no active physics objects
            totals = self.budget.totals()
            return totals.get("physics_objects", 0) == 0

        # POSITION_CROSS, AUDIO_EVENT, SOUND_COMPLETE are triggered externally
        return False

    # ── External event notifications ───────────────────────────────────────

    def notify_position(
        self,
        character_id: str,
        position:     Tuple[float, float, float],
    ) -> None:
        """
        Feed character position from Purfluous/mocap every frame.
        Pete checks against armed POSITION_CROSS cues.
        """
        if self._state != TakeState.ROLLING:
            return

        for cue in self._cues:
            if cue.state != CueState.ARMED:
                continue
            if cue.cue_type != CueType.POSITION_CROSS:
                continue
            if cue.character_id != character_id:
                continue
            if cue.marker_id is None:
                continue

            marker = self._markers.get(cue.marker_id)
            if marker is None:
                continue

            # Distance from marker
            dx = position[0] - marker.position[0]
            dy = position[1] - marker.position[1]
            dz = position[2] - marker.position[2]
            dist = (dx*dx + dy*dy + dz*dz) ** 0.5

            if dist <= marker.tolerance:
                if cue.triggered_at_s is None:
                    scene_s = self._scene_time()
                    cue.triggered_at_s = scene_s
                    cue.state = CueState.TRIGGERED
                    self._log(
                        "cue_position_cross", surface=False,
                        cue_name=cue.name, character_id=character_id,
                        marker=marker.name, scene_s=scene_s
                    )

    def notify_audio_event(self, sound_name: str) -> None:
        """
        Feed named audio events from the audio system.
        Pete increments counters for AUDIO_EVENT cues.
        """
        if self._state != TakeState.ROLLING:
            return

        for cue in self._cues:
            if cue.state != CueState.ARMED:
                continue
            if cue.cue_type != CueType.AUDIO_EVENT:
                continue
            if cue.sound_name != sound_name:
                continue

            cue._event_count += 1
            self._log(
                "cue_audio_event", surface=False,
                cue_name=cue.name, sound=sound_name,
                count=cue._event_count, target=cue.count
            )

            if cue._event_count >= cue.count:
                if cue.triggered_at_s is None:
                    scene_s = self._scene_time()
                    cue.triggered_at_s = scene_s
                    cue.state = CueState.TRIGGERED

    def notify_sound_complete(self, sound_name: str) -> None:
        """
        Feed sound completion events.
        Pete triggers SOUND_COMPLETE cues.
        """
        if self._state != TakeState.ROLLING:
            return

        for cue in self._cues:
            if cue.state != CueState.ARMED:
                continue
            if cue.cue_type != CueType.SOUND_COMPLETE:
                continue
            if cue.sound_name != sound_name:
                continue

            if cue.triggered_at_s is None:
                scene_s = self._scene_time()
                cue.triggered_at_s = scene_s
                cue.state = CueState.TRIGGERED
                self._log(
                    "cue_sound_complete", surface=False,
                    cue_name=cue.name, sound=sound_name, scene_s=scene_s
                )

    # ── Cue firing ─────────────────────────────────────────────────────────

    async def _fire_cue(self, cue: AutoCutCue, scene_s: float) -> None:
        """Fire a cue action. Logs to black box. Calls registered callbacks."""
        cue.state      = CueState.FIRED
        cue.fired_at_s = scene_s

        self._log(
            "cue_fired", surface=False,
            cue_name=cue.name, cue_type=cue.cue_type.value,
            action=cue.action.value, scene_s=scene_s
        )
        logger.info(
            "Pete: cue '%s' fired at %.2fs — action: %s",
            cue.name, scene_s, cue.action.value
        )

        if cue.action == CueAction.CUT or cue.action == CueAction.AUTO_CUT:
            if self._on_cut:
                await self._on_cut(
                    reason=f"auto_cut_cue:{cue.name}",
                    scene_s=scene_s
                )

        elif cue.action == CueAction.ACTION:
            if self._on_action:
                await self._on_action(reason=f"cue:{cue.name}")

        elif cue.action == CueAction.CAMERA_SWITCH:
            await self.hub.broadcast_system_event({
                "type":    "camera_switch",
                "payload": {"camera_id": cue.camera_id, "scene_s": scene_s},
            })

        elif cue.action == CueAction.DETONATE:
            await self.hub.broadcast_system_event({
                "type":    "detonate",
                "payload": {"instance_id": cue.instance_id, "scene_s": scene_s},
            })

        elif cue.action == CueAction.CUSTOM:
            await self.hub.broadcast_system_event({
                "type":    "pete_custom_cue",
                "payload": {
                    "cue_name": cue.name,
                    "scene_s":  scene_s,
                    **(cue.custom_payload or {}),
                },
            })

    async def _fire_chunk_boundary(self, scene_s: float) -> None:
        """
        Fire a chunk boundary — internal micro-flush.
        SLATE clock continues. Recording tail NOT applied here.
        Chunk boundaries are silent infrastructure.
        """
        self._log(
            "chunk_boundary", surface=False,
            scene_s=scene_s, chunk_size_s=self._chunk_size_s
        )
        logger.debug("Pete: chunk boundary at %.1fs", scene_s)

        # Broadcast chunk boundary to clients for renderer flush
        if self.hub:
            await self.hub.broadcast_system_event({
                "type":    "pete_chunk_boundary",
                "payload": {
                    "scene_s":    scene_s,
                    "chunk_size": self._chunk_size_s,
                },
            })

        # Reset Pete's internal performance accumulators
        self.window.reset()
        # Note: frame monitor intentionally NOT reset — drops are cumulative
        # Note: budget tracker intentionally NOT reset — scene budget is cumulative

    # ── Direct query ───────────────────────────────────────────────────────

    async def status(self) -> Dict[str, Any]:
        """Full status snapshot. Safe to call any time including mid-take."""
        report = self.budget.report()
        return {
            "state":          self._state.value,
            "scene_s":        self._scene_time(),
            "quality_tier":   report.quality_tier.value,
            "budget":         {
                "totals":         report.totals,
                "pct_of_target":  report.pct_of_target,
                "overloaded":     report.overloaded_pools,
                "summary":        report.summary_line(),
            },
            "frames":         self.frames.drop_summary(),
            "window":         self.window.window_report(
                self._scene_time(), report.totals
            ) if self._state == TakeState.ROLLING else None,
            "cues":           [c.to_dict() for c in self._cues],
            "markers":        [m.to_dict() for m in self._markers.values()],
            "chunk_size_s":   self._chunk_size_s,
            "black_box_size": len(self._black_box),
            "handle_s":       self.HANDLE_SECONDS,
            "tail_s":         self.TAIL_SECONDS,
        }

    def get_black_box(
        self,
        last_n: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve black box entries. Everything. Always.
        Optionally filter by type or limit to last N entries.
        """
        entries = self._black_box
        if event_type:
            entries = [e for e in entries if e["event_type"] == event_type]
        if last_n:
            entries = entries[-last_n:]
        return entries
