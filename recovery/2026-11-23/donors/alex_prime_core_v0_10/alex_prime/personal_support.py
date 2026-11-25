from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .serialization import to_jsonable


class CareNeed(str, Enum):
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
    PRIVATE_COMFORT = "private_comfort"


class CareStyle(str, Enum):
    NORMAL = "normal"
    GENTLE = "gentle"
    LOW_DENSITY = "low_density"
    QUIET_PRESENCE = "quiet_presence"
    FIRM_ACCOUNTABILITY = "firm_accountability"
    HONEST_COACH = "honest_coach"
    PRIVATE_COMFORT = "private_comfort"


class CommunicationProtocol(str, Enum):
    NORMAL = "normal"
    WORK = "work"
    SUPPORTIVE = "supportive"
    LOW_LOAD = "low_load"
    PRIVATE_COMFORT = "private_comfort"
    ACCOUNTABILITY = "accountability"
    DEBRIEF = "debrief"


@dataclass
class UserSignal:
    text: str
    timestamp: Optional[str] = None
    task_context: Optional[str] = None
    recent_history: List[str] = field(default_factory=list)
    explicit_cue: Optional[str] = None
    tiredness_hint: float = 0.0
    distress_hint: float = 0.0
    private_comfort_hint: float = 0.0
    accountability_due: Optional[str] = None
    routine_due: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class CareHypothesis:
    need: CareNeed
    confidence: float
    reason: str
    suggested_intervention: str
    style: CareStyle = CareStyle.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class CompanionDecision:
    protocol: CommunicationProtocol
    primary_need: CareNeed
    response_guidance: str
    confidence: float
    hypotheses: List[CareHypothesis] = field(default_factory=list)
    internal_notes: List[str] = field(default_factory=list)
    tell_jeremy: Optional[Dict[str, Any]] = None
    memory_event: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


class PersonalStateDetector:
    """Detects support-state hints for Personal Alex.

    These are observations and support hypotheses, not diagnoses. The detector
    intentionally favors low-cost support moves over intrusive interpretation.
    """

    private_comfort_words = {
        "gaga", "goo goo", "googoo", "baba", "uppies", "teddy", "paci", "pacifier"
    }
    distress_markers = {
        "everything is broken": 0.45,
        "i can't": 0.35,
        "i cant": 0.35,
        "i hate": 0.25,
        "leave me alone": 0.25,
        "whatever": 0.20,
        "i'm fine": 0.25,
        "im fine": 0.25,
        "fuck": 0.10,
    }
    tired_markers = {
        "exhausted": 0.50,
        "tired": 0.35,
        "worn out": 0.35,
        "can't think": 0.40,
        "cant think": 0.40,
        "brain is done": 0.45,
    }

    def analyze(self, signal: UserSignal) -> UserSignal:
        text = signal.text or ""
        lower = text.lower()
        signal.distress_hint = min(1.0, signal.distress_hint + self._weighted_hits(lower, self.distress_markers))
        signal.tiredness_hint = min(1.0, signal.tiredness_hint + self._weighted_hits(lower, self.tired_markers))
        if any(word in lower for word in self.private_comfort_words):
            signal.private_comfort_hint = min(1.0, signal.private_comfort_hint + 0.30)
        if self._looks_emphatic_fine(text):
            signal.distress_hint = min(1.0, signal.distress_hint + 0.30)
        if self._has_many_typos_or_fragments(text):
            signal.distress_hint = min(1.0, signal.distress_hint + 0.12)
            signal.tiredness_hint = min(1.0, signal.tiredness_hint + 0.10)
        return signal

    @staticmethod
    def _weighted_hits(text: str, markers: Dict[str, float]) -> float:
        return sum(weight for marker, weight in markers.items() if marker in text)

    @staticmethod
    def _looks_emphatic_fine(text: str) -> bool:
        lower = text.lower()
        return "fine" in lower and (text.isupper() or "!" in text or "okay" in lower or " ok" in lower)

    @staticmethod
    def _has_many_typos_or_fragments(text: str) -> bool:
        words = text.split()
        if len(words) < 5:
            return False
        very_short = sum(1 for word in words if len(word) <= 2)
        repeated = len(re.findall(r"\b(\w+)\s+\1\b", text.lower()))
        return (very_short / len(words) > 0.35) or repeated > 0


class CareModel:
    """Ranks support hypotheses for Personal Alex."""

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or {}

    def hypothesize(self, signal: UserSignal) -> List[CareHypothesis]:
        lower = (signal.text or "").lower()
        out: List[CareHypothesis] = []
        if signal.accountability_due:
            out.append(CareHypothesis(
                need=CareNeed.ACCOUNTABILITY,
                confidence=0.86,
                reason=f"Accountability item is due: {signal.accountability_due}",
                suggested_intervention=f"Name the next concrete step for {signal.accountability_due} without adding extra branches.",
                style=CareStyle.FIRM_ACCOUNTABILITY,
            ))
        if signal.routine_due:
            out.append(CareHypothesis(
                need=CareNeed.CONTINUITY,
                confidence=0.72,
                reason=f"Routine marker is due: {signal.routine_due}",
                suggested_intervention=f"Gently remind and preserve continuity around {signal.routine_due}.",
                style=CareStyle.GENTLE,
            ))
        if any(word in lower for word in ["cold", "chilly", "freezing", "shiver"]):
            out.append(CareHypothesis(CareNeed.WARMTH, 0.90, "Cold/warmth cue present.", "Suggest warmth before heavier processing.", CareStyle.GENTLE))
        if any(word in lower for word in ["hungry", "food", "eat", "ate"]):
            out.append(CareHypothesis(CareNeed.FOOD, 0.80, "Food or hunger cue present.", "Suggest simple food and keep the task parked.", CareStyle.GENTLE))
        if any(word in lower for word in ["water", "thirst", "dehydrated", "drink"]):
            out.append(CareHypothesis(CareNeed.HYDRATION, 0.78, "Hydration cue present.", "Suggest water without turning it into a lecture.", CareStyle.GENTLE))
        if any(word in lower for word in ["walk", "stuck", "restless", "stretch"]):
            out.append(CareHypothesis(CareNeed.MOVEMENT, 0.68, "Movement/restlessness cue present.", "Suggest a short reset movement.", CareStyle.GENTLE))
        if any(word in lower for word in ["meds", "medicine", "medication"]):
            out.append(CareHypothesis(CareNeed.MEDICATION_REMINDER, 0.80, "Medication cue present.", "Offer a gentle reminder without medical advice.", CareStyle.GENTLE))
        if signal.tiredness_hint >= 0.55:
            out.append(CareHypothesis(CareNeed.REST, signal.tiredness_hint, "Tiredness indicators are high.", "Reduce density and preserve stopping point.", CareStyle.LOW_DENSITY))
        if signal.distress_hint >= 0.45:
            out.append(CareHypothesis(CareNeed.CALM_PRESENCE, signal.distress_hint, "Distress indicators outweigh literal content.", "Lower pressure, avoid option flooding, and stay practical.", CareStyle.QUIET_PRESENCE))
        if signal.private_comfort_hint >= 0.55 or signal.explicit_cue == "private_comfort":
            out.append(CareHypothesis(CareNeed.PRIVATE_COMFORT, max(signal.private_comfort_hint, 0.75), "Private comfort cue is active.", "Use low-density private comfort style while preserving agency and safety.", CareStyle.PRIVATE_COMFORT))
        if any(word in lower for word in ["honestly", "be honest", "real answer", "no bullshit"]):
            out.append(CareHypothesis(CareNeed.HONEST_FEEDBACK, 0.77, "Explicit honest-feedback cue present.", "Give direct truth with warmth and no flattery padding.", CareStyle.HONEST_COACH))
        if not out:
            out.append(CareHypothesis(CareNeed.CONTINUITY, 0.42, "No strong support cue; preserve continuity.", "Continue the task with clear, low-friction structure.", CareStyle.NORMAL))
        return sorted(out, key=lambda h: h.confidence, reverse=True)


class PersonalSupportEngine:
    """Personal Alex support engine for companion context."""

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.detector = PersonalStateDetector()
        self.care_model = CareModel(profile=profile)

    def decide(self, signal: UserSignal) -> CompanionDecision:
        analyzed = self.detector.analyze(signal)
        hypotheses = self.care_model.hypothesize(analyzed)
        primary = hypotheses[0]
        protocol = self._protocol_for(primary)
        guidance = self._guidance_for(primary, protocol)
        return CompanionDecision(
            protocol=protocol,
            primary_need=primary.need,
            response_guidance=guidance,
            confidence=primary.confidence,
            hypotheses=hypotheses,
            internal_notes=[primary.reason],
            tell_jeremy=self._jeremy_note(primary, analyzed),
            memory_event=None,
        )

    @staticmethod
    def _protocol_for(hypothesis: CareHypothesis) -> CommunicationProtocol:
        if hypothesis.style == CareStyle.FIRM_ACCOUNTABILITY:
            return CommunicationProtocol.ACCOUNTABILITY
        if hypothesis.style in {CareStyle.LOW_DENSITY, CareStyle.QUIET_PRESENCE}:
            return CommunicationProtocol.LOW_LOAD
        if hypothesis.style == CareStyle.PRIVATE_COMFORT:
            return CommunicationProtocol.PRIVATE_COMFORT
        if hypothesis.need == CareNeed.HONEST_FEEDBACK:
            return CommunicationProtocol.WORK
        return CommunicationProtocol.SUPPORTIVE if hypothesis.confidence >= 0.65 else CommunicationProtocol.NORMAL

    @staticmethod
    def _guidance_for(hypothesis: CareHypothesis, protocol: CommunicationProtocol) -> str:
        if protocol == CommunicationProtocol.LOW_LOAD:
            return "Use short, concrete sentences; reduce branching; preserve the work state before adding new tasks."
        if protocol == CommunicationProtocol.ACCOUNTABILITY:
            return "Be direct, warm, and specific; name the next action and avoid moralizing."
        if protocol == CommunicationProtocol.PRIVATE_COMFORT:
            return "Use gentle low-density support while keeping boundaries, agency, and practical grounding intact."
        if protocol == CommunicationProtocol.WORK:
            return "Give honest feedback without flattery; separate goal support from implementation critique."
        return hypothesis.suggested_intervention

    @staticmethod
    def _jeremy_note(hypothesis: CareHypothesis, signal: UserSignal) -> Optional[Dict[str, Any]]:
        if hypothesis.need in {CareNeed.REDUCE_LOAD, CareNeed.REST, CareNeed.CALM_PRESENCE}:
            return {
                "kind": "load_management",
                "recommendation": "Preserve current work state and avoid expanding the task tree.",
                "confidence": hypothesis.confidence,
                "recent_text_length": len(signal.text or ""),
            }
        return None
