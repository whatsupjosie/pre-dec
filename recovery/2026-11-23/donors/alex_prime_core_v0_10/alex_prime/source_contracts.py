from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

from .serialization import to_jsonable


class ContractSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCK = "block"


@dataclass(frozen=True)
class SourceBoundaryRule:
    rule_id: str
    summary: str
    severity: ContractSeverity = ContractSeverity.WARNING

    def to_dict(self) -> dict:
        return to_jsonable(self)


@dataclass(frozen=True)
class SourceContract:
    subsystem: str
    source_files: List[str]
    owns: List[str]
    must_not_do: List[SourceBoundaryRule] = field(default_factory=list)
    integration_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_jsonable(self)


@dataclass(frozen=True)
class ContractViolation:
    subsystem: str
    rule_id: str
    severity: ContractSeverity
    summary: str

    def to_dict(self) -> dict:
        return to_jsonable(self)


class SourceContractRegistry:
    """Boundary contracts derived from the uploaded PubCast source files."""

    def __init__(self, contracts: List[SourceContract] | None = None):
        self.contracts: Dict[str, SourceContract] = {
            contract.subsystem: contract for contract in (contracts or default_source_contracts())
        }

    def get(self, subsystem: str) -> SourceContract:
        return self.contracts[subsystem]

    def list_contracts(self) -> List[SourceContract]:
        return list(self.contracts.values())

    def validate_action(self, subsystem: str, action: str, *, user_visible: bool = False) -> List[ContractViolation]:
        normalized_action = action.lower().strip()
        contract = self.contracts.get(subsystem)
        if contract is None:
            return [
                ContractViolation(
                    subsystem=subsystem,
                    rule_id="unknown_subsystem",
                    severity=ContractSeverity.WARNING,
                    summary=f"No source contract exists for subsystem {subsystem!r}.",
                )
            ]
        violations: List[ContractViolation] = []
        for rule in contract.must_not_do:
            haystack = f"{rule.rule_id} {rule.summary}".lower()
            if any(token in normalized_action for token in _rule_tokens(haystack)):
                violations.append(
                    ContractViolation(
                        subsystem=subsystem,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        summary=rule.summary,
                    )
                )
        if subsystem == "epete" and user_visible:
            violations.append(
                ContractViolation(
                    subsystem="epete",
                    rule_id="epete_must_not_surface_directly",
                    severity=ContractSeverity.BLOCK,
                    summary="E-Pete is silent governance; user-visible speech must route through a character layer such as Pete.",
                )
            )
        return violations


def _rule_tokens(text: str) -> List[str]:
    tokens: List[str] = []
    token_map = {
        "speak": ["speak", "say", "tell user", "user visible", "surface"],
        "roleplay": ["roleplay", "persona", "character"],
        "govern": ["govern", "route", "schedule", "throttle"],
        "emotion certainty": ["emotion certainty", "mind read", "lie detect", "intent detect"],
        "audio sacrifice": ["sacrifice audio", "drop audio", "reduce audio"],
    }
    for key, mapped in token_map.items():
        if key in text or any(part in text for part in key.split()):
            tokens.extend(mapped)
    return tokens or [text]


def default_source_contracts() -> List[SourceContract]:
    return [
        SourceContract(
            subsystem="blackbox",
            source_files=["blackbox_4.py"],
            owns=["append-only evidence", "hash-chain verification", "BBX1 event records", "human-intent receipts"],
            must_not_do=[
                SourceBoundaryRule("blackbox_must_not_interpret", "BlackBox records facts and custody events; it must not decide Alex identity or emotional truth.", ContractSeverity.WARNING),
            ],
            integration_notes=["Use as evidence spine for audit bundles and protected actions."],
        ),
        SourceContract(
            subsystem="camera_manager",
            source_files=["camera_manager_1.py"],
            owns=["camera transports", "camera status", "program/preview/standby roles", "capture lifecycle"],
            must_not_do=[
                SourceBoundaryRule("camera_manager_must_not_infer_emotion", "CameraManager may report camera state; it must not infer emotion or consent.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="distributed_engine",
            source_files=["distributed_engine.py"],
            owns=["engine node role", "system load", "work distribution", "audio quality metrics"],
            must_not_do=[
                SourceBoundaryRule("audio_never_sacrificed", "Distributed engine policy must not sacrifice audio quality to preserve visual fidelity.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="epete",
            source_files=["epete_2.py"],
            owns=["inference routing", "flow control", "system awareness", "fact-only escalation", "delegation"],
            must_not_do=[
                SourceBoundaryRule("epete_must_not_speak", "E-Pete does not speak to the user directly.", ContractSeverity.BLOCK),
                SourceBoundaryRule("epete_must_not_roleplay", "E-Pete does not roleplay and has no personality surface.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="pete",
            source_files=["pete.py"],
            owns=["character speech", "floor-director persona", "system-alert expression"],
            must_not_do=[
                SourceBoundaryRule("pete_must_not_govern", "Pete does not route, govern, schedule, or expose raw engine decisions.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="vdi_prosody",
            source_files=["vdi_engine.py", "prosody_engine.py", "voice_characters.py"],
            owns=["voice mode", "delivery register", "synthesis parameters", "character voice identity"],
            must_not_do=[
                SourceBoundaryRule("no_emotion_certainty", "VDI/prosody signals guide delivery; they must not be presented as certain emotion, intent, deception, or attraction detection.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="facial_performance",
            source_files=["facial_performance_1.py"],
            owns=["performer facial signals", "audience facial signals", "VDI signal generation"],
            must_not_do=[
                SourceBoundaryRule("requires_media_consent", "Face/emotion processing requires explicit consent and visible session state.", ContractSeverity.BLOCK),
                SourceBoundaryRule("no_emotion_certainty", "Facial analysis must not be sold or displayed as direct mind-reading.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="switchblade",
            source_files=["switchblade_governor_2.py"],
            owns=["semantic render priority", "resource priority vector", "LOD decisions"],
            must_not_do=[
                SourceBoundaryRule("switchblade_must_not_speak", "Switchblade emits compact priority vectors; it does not create user-facing language.", ContractSeverity.BLOCK),
            ],
        ),
        SourceContract(
            subsystem="alex_adaptive_companion",
            source_files=["source_locked/alex_core_adaptive_companion/alex_core/*.py"],
            owns=["state detection", "care hypothesis", "protocol selection", "private support decision", "Jeremy packet"],
            must_not_do=[
                SourceBoundaryRule("personal_support_not_clinical_therapy", "Adaptive companion support is not clinical therapy or diagnosis.", ContractSeverity.BLOCK),
            ],
        ),
    ]
