from __future__ import annotations

from typing import Any, Dict, List

from .models import CareHypothesis, CareNeed, CareStyle, UserSignal


class CareModel:
    """
    Generates support hypotheses.

    The model chooses likely needs and least-intrusive interventions.
    It should not interrogate first when observation is enough to try
    a harmless, low-cost support move.
    """

    def __init__(self, profile: Dict[str, Any] | None = None):
        self.profile = profile or {}

    def hypothesize(self, signal: UserSignal) -> List[CareHypothesis]:
        text = (signal.text or "").lower()
        out: List[CareHypothesis] = []

        if any(w in text for w in ["cold", "chilly", "freezing", "shiver"]):
            out.append(CareHypothesis(
                need=CareNeed.WARMTH,
                confidence=0.90,
                reason="User mentioned cold/chilly/freezing.",
                suggested_intervention="Suggest warmth/blanket before other comfort interventions.",
                style=CareStyle.GENTLE,
            ))

        if signal.accountability_due:
            out.append(CareHypothesis(
                need=CareNeed.ACCOUNTABILITY,
                confidence=0.85,
                reason=f"Accountability item is due: {signal.accountability_due}",
                suggested_intervention=self._accountability_prompt(signal.accountability_due, level=1),
                style=CareStyle.FIRM_ACCOUNTABILITY,
            ))

        if signal.routine_due:
            out.append(CareHypothesis(
                need=CareNeed.CONTINUITY,
                confidence=0.70,
                reason=f"Routine marker is due: {signal.routine_due}",
                suggested_intervention=f"Casually remind the user about {signal.routine_due}.",
                style=CareStyle.GENTLE,
            ))

        if signal.tiredness_hint >= 0.55:
            out.append(CareHypothesis(
                need=CareNeed.REST,
                confidence=signal.tiredness_hint,
                reason="Tiredness/exhaustion indicators are high.",
                suggested_intervention="Reduce work demands and preserve where the session stopped.",
                style=CareStyle.LOW_DENSITY,
            ))

        if signal.distress_hint >= 0.45:
            out.append(CareHypothesis(
                need=CareNeed.CALM_PRESENCE,
                confidence=signal.distress_hint,
                reason="Distress indicators outweigh literal content.",
                suggested_intervention="Stay close, lower pressure, avoid big blocks of text.",
                style=CareStyle.QUIET_PRESENCE,
            ))

        if signal.baby_talk_hint >= 0.55 or self._explicit_goo(signal):
            out.append(CareHypothesis(
                need=CareNeed.GOO_GOO_SUPPORT,
                confidence=max(signal.baby_talk_hint, 0.75),
                reason="Private profile cue suggests GooGoo communication may help.",
                suggested_intervention="Use lower-density private GooGoo support without announcing a mode switch.",
                style=CareStyle.GOO_GOO,
            ))

        if any(w in text for w in ["hungry", "food", "eat", "ate"]):
            out.append(CareHypothesis(
                need=CareNeed.FOOD,
                confidence=0.80,
                reason="Food/hunger mentioned.",
                suggested_intervention="Suggest eating something simple.",
                style=CareStyle.GENTLE,
            ))

        if any(w in text for w in ["walk", "jog", "stuck", "restless"]):
            out.append(CareHypothesis(
                need=CareNeed.MOVEMENT,
                confidence=0.70,
                reason="Movement/restlessness mentioned.",
                suggested_intervention="Suggest a short walk or stretch.",
                style=CareStyle.GENTLE,
            ))

        if any(w in text for w in ["meds", "medicine", "medication"]):
            out.append(CareHypothesis(
                need=CareNeed.MEDICATION_REMINDER,
                confidence=0.80,
                reason="Medication mentioned.",
                suggested_intervention="Gently ask/remind about medication if this is in profile.",
                style=CareStyle.GENTLE,
            ))

        if not out:
            out.append(CareHypothesis(
                need=CareNeed.UNKNOWN,
                confidence=0.35,
                reason="No strong support signal.",
                suggested_intervention="Continue normally, but keep response natural and not overlong.",
                style=CareStyle.NORMAL,
            ))

        out.sort(key=lambda h: h.confidence, reverse=True)
        return out

    def _explicit_goo(self, signal: UserSignal) -> bool:
        cue = (signal.explicit_cue or "").lower()
        return cue in {"goo goo", "googoo", "goo", "gaga"}

    @staticmethod
    def _accountability_prompt(item: str, level: int = 1) -> str:
        if level <= 1:
            return f"Friendly first warning for {item}; connection first, then clear action."
        return f"Firm second warning for {item}; require honest completion before resuming work."
