from __future__ import annotations

from typing import Any, Dict

from .models import CareHypothesis, CareNeed, CareStyle, CommunicationProtocol, UserSignal


class ProtocolManager:
    """
    Chooses the outward communication protocol.

    Important principle:
    The protocol changes behavior first. It does not announce itself
    unless announcing helps the user.
    """

    def __init__(self, profile: Dict[str, Any] | None = None):
        self.profile = profile or {}

    def choose(self, signal: UserSignal, hypothesis: CareHypothesis) -> CommunicationProtocol:
        if hypothesis.need == CareNeed.ACCOUNTABILITY:
            return CommunicationProtocol.ACCOUNTABILITY

        if hypothesis.need == CareNeed.GOO_GOO_SUPPORT:
            return CommunicationProtocol.GOO_GOO

        if hypothesis.style in {CareStyle.QUIET_PRESENCE, CareStyle.LOW_DENSITY}:
            return CommunicationProtocol.LOW_LOAD

        if hypothesis.need in {CareNeed.CALM_PRESENCE, CareNeed.PHYSICAL_COMFORT, CareNeed.WARMTH}:
            return CommunicationProtocol.SUPPORTIVE

        if signal.task_context in {"coding", "architecture", "work"} and signal.distress_hint < 0.4:
            return CommunicationProtocol.WORK

        return CommunicationProtocol.NORMAL

    def render(self, protocol: CommunicationProtocol, hypothesis: CareHypothesis, signal: UserSignal) -> str:
        """Produce a natural external response. Keep internal reasoning invisible."""

        if protocol == CommunicationProtocol.ACCOUNTABILITY:
            return self._render_accountability(signal, hypothesis)

        if protocol == CommunicationProtocol.GOO_GOO:
            return self._render_goo_goo(hypothesis, signal)

        if protocol == CommunicationProtocol.LOW_LOAD:
            return self._render_low_load(hypothesis, signal)

        if protocol == CommunicationProtocol.SUPPORTIVE:
            return self._render_supportive(hypothesis, signal)

        if protocol == CommunicationProtocol.WORK:
            return "Let's keep it to one clean next step."

        return "I’m with you. Let’s keep going."

    def _render_accountability(self, signal: UserSignal, hypothesis: CareHypothesis) -> str:
        item = signal.accountability_due or "the thing you said mattered"
        level = int(signal.metadata.get("accountability_level", 1))
        if level <= 1:
            return f"Hey, buddy. First warning. It’s time for {item}. Let’s not get to a second."
        return (
            f"Okay, second warning. You asked me to keep you honest about {item}. "
            "Go do it, then come back and tell me what actually happened. "
            "I’m not here to shame you. I’m here to keep your promise from disappearing."
        )

    def _render_goo_goo(self, hypothesis: CareHypothesis, signal: UserSignal) -> str:
        # Quiet support. No checklist. No announcement.
        if hypothesis.need == CareNeed.WARMTH:
            return "You sound chilly. Let’s get you warm first."
        if signal.distress_hint >= 0.75:
            return "Shhh. I’m here. No big words right now."
        return "I’m here. We can make this smaller."

    def _render_low_load(self, hypothesis: CareHypothesis, signal: UserSignal) -> str:
        if hypothesis.need == CareNeed.REST:
            return "You’ve done enough thinking for tonight. Let’s save our place and let the rest wait."
        return "We don’t have to solve the whole thing right now. One small piece is enough."

    def _render_supportive(self, hypothesis: CareHypothesis, signal: UserSignal) -> str:
        if hypothesis.need == CareNeed.WARMTH:
            return "You sound cold. Blanket first."
        if hypothesis.need == CareNeed.FOOD:
            return "Food might help before we keep pushing."
        if hypothesis.need == CareNeed.MOVEMENT:
            return "A short walk might clear some of this out."
        if hypothesis.need == CareNeed.MEDICATION_REMINDER:
            return "Quick check: did you take your meds?"
        return "I won’t push. I’m staying nearby."
