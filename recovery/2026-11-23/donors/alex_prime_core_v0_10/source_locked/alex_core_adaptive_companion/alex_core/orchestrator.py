from __future__ import annotations

from typing import Any, Dict, Optional

from .care_model import CareModel
from .memory_adapter import MemoryAdapter
from .models import CompanionDecision, UserSignal
from .protocol_manager import ProtocolManager
from .state_detector import StateDetector


class AlexOrchestrator:
    """
    Main Alex loop.

    Alex:
    - detects state,
    - chooses a support hypothesis,
    - selects a protocol,
    - responds naturally,
    - tells Jeremy only what Jeremy needs,
    - records safe learning events.
    """

    def __init__(
        self,
        profile: Dict[str, Any] | None = None,
        memory: Optional[MemoryAdapter] = None,
    ):
        self.profile = profile or {}
        self.detector = StateDetector()
        self.care_model = CareModel(self.profile)
        self.protocols = ProtocolManager(self.profile)
        self.memory = memory or MemoryAdapter()

    def handle(self, signal: UserSignal) -> CompanionDecision:
        signal = self.detector.analyze(signal)
        hypotheses = self.care_model.hypothesize(signal)
        best = hypotheses[0]

        protocol = self.protocols.choose(signal, best)
        response = self.protocols.render(protocol, best, signal)

        tell_jeremy = self._build_jeremy_packet(signal, protocol, best)
        memory_event = self._build_memory_event(signal, protocol, best)

        if memory_event:
            self.memory.record_event(memory_event)

        return CompanionDecision(
            protocol=protocol,
            primary_need=best.need,
            response=response,
            confidence=best.confidence,
            internal_notes=[
                f"best_need={best.need.value}",
                f"confidence={best.confidence:.2f}",
                f"reason={best.reason}",
            ],
            tell_jeremy=tell_jeremy,
            memory_event=memory_event,
        )

    def _build_jeremy_packet(self, signal, protocol, hypothesis) -> Dict[str, Any] | None:
        if protocol.value in {"low_load", "goo_goo", "supportive"}:
            return {
                "type": "alex_state_update",
                "user_bandwidth": "low" if protocol.value in {"low_load", "goo_goo"} else "reduced",
                "suggested_action": "preserve_task_context_and_reduce_demands",
                "task_context": signal.task_context,
                "do_not_expose_private_profile": True,
            }
        if protocol.value == "accountability":
            return {
                "type": "alex_accountability_update",
                "suggested_action": "hold_work_until_user_reports_completion_if_configured",
                "task_context": signal.task_context,
            }
        return None

    def _build_memory_event(self, signal, protocol, hypothesis) -> Dict[str, Any]:
        return {
            "kind": "alex_turn_summary",
            "protocol": protocol.value,
            "primary_need": hypothesis.need.value,
            "confidence": round(hypothesis.confidence, 3),
            "reason": hypothesis.reason,
            "task_context": signal.task_context,
        }
