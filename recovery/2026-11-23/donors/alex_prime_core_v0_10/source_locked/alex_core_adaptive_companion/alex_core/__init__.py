"""
Alex Core — Adaptive Companion Orchestrator.

Alex is the private continuity and care orchestrator.
She does not replace PubCast, Jeremy, BlackBox, or the LLM.
She decides what kind of support is needed, which system should handle it,
and how densely/gently to communicate.
"""

from .models import (
    UserSignal,
    CareHypothesis,
    CareNeed,
    CareStyle,
    CommunicationProtocol,
    CompanionDecision,
    DebriefRecord,
)
from .state_detector import StateDetector
from .care_model import CareModel
from .protocol_manager import ProtocolManager
from .orchestrator import AlexOrchestrator
from .debrief import DebriefEngine
from .memory_adapter import MemoryAdapter

__all__ = [
    "UserSignal",
    "CareHypothesis",
    "CareNeed",
    "CareStyle",
    "CommunicationProtocol",
    "CompanionDecision",
    "DebriefRecord",
    "StateDetector",
    "CareModel",
    "ProtocolManager",
    "AlexOrchestrator",
    "DebriefEngine",
    "MemoryAdapter",
]
