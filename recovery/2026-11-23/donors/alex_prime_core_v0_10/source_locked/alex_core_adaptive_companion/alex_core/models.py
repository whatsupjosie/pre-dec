from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CareNeed(str, Enum):
    """What the user may need. Not a diagnosis; just support hypotheses."""

    UNKNOWN = "unknown"
    CONTINUITY = "continuity"
    REDUCE_LOAD = "reduce_load"
    CALM_PRESENCE = "calm_presence"
    PHYSICAL_COMFORT = "physical_comfort"
    WARMTH = "warmth"
    HYDRATION = "hydration"
    FOOD = "food"
    REST = "rest"
    MOVEMENT = "movement"
    MEDICATION_REMINDER = "medication_reminder"
    ACCOUNTABILITY = "accountability"
    HONEST_FEEDBACK = "honest_feedback"
    SPACE = "space"
    GOO_GOO_SUPPORT = "goo_goo_support"


class CareStyle(str, Enum):
    """How the support should be delivered."""

    NORMAL = "normal"
    GENTLE = "gentle"
    LOW_DENSITY = "low_density"
    QUIET_PRESENCE = "quiet_presence"
    FIRM_ACCOUNTABILITY = "firm_accountability"
    HONEST_COACH = "honest_coach"
    GOO_GOO = "goo_goo"


class CommunicationProtocol(str, Enum):
    """Surface protocol. Same user, same companion; different bandwidth/style."""

    NORMAL = "normal"
    WORK = "work"
    SUPPORTIVE = "supportive"
    LOW_LOAD = "low_load"
    GOO_GOO = "goo_goo"
    ACCOUNTABILITY = "accountability"
    DEBRIEF = "debrief"


@dataclass
class UserSignal:
    """Signals Alex sees in a turn. These are observations, not conclusions."""

    text: str
    timestamp: Optional[str] = None
    task_context: Optional[str] = None
    recent_history: List[str] = field(default_factory=list)
    explicit_cue: Optional[str] = None
    tiredness_hint: float = 0.0
    distress_hint: float = 0.0
    baby_talk_hint: float = 0.0
    accountability_due: Optional[str] = None
    routine_due: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CareHypothesis:
    """A possible interpretation of what would help."""

    need: CareNeed
    confidence: float
    reason: str
    suggested_intervention: str
    style: CareStyle = CareStyle.NORMAL


@dataclass
class CompanionDecision:
    """What Alex chooses to do this turn."""

    protocol: CommunicationProtocol
    primary_need: CareNeed
    response: str
    confidence: float
    internal_notes: List[str] = field(default_factory=list)
    tell_jeremy: Optional[Dict[str, Any]] = None
    memory_event: Optional[Dict[str, Any]] = None


@dataclass
class DebriefRecord:
    """Post-event learning data. This is where EQ improves."""

    event_id: str
    what_alex_thought: str
    what_helped: List[str] = field(default_factory=list)
    what_hurt: List[str] = field(default_factory=list)
    corrected_need: Optional[CareNeed] = None
    corrected_protocol: Optional[CommunicationProtocol] = None
    user_notes: str = ""
    lessons: List[str] = field(default_factory=list)
