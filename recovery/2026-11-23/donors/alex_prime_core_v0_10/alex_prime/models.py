from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

from .serialization import to_jsonable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    safe_prefix = "".join(ch for ch in prefix.lower() if ch.isalnum() or ch == "_").strip("_")
    if not safe_prefix:
        raise ValueError("id prefix must contain at least one alphanumeric character")
    return f"{safe_prefix}_{uuid.uuid4().hex[:12]}"


class AlexContext(str, Enum):
    PERSONAL = "personal_alex"
    PUBCAST = "pubcast_alext"


class ParticipantType(str, Enum):
    HUMAN = "human"
    AI = "ai"
    TOOL = "tool"
    FILE = "file"
    SYSTEM = "system"


class InterventionLevel(str, Enum):
    OBSERVE = "L0_OBSERVE"
    NUDGE = "L1_NUDGE"
    CLARIFY = "L2_CLARIFY"
    GATE = "L3_GATE"
    CONTAIN = "L4_CONTAIN"
    QUARANTINE_RESTORE = "L5_QUARANTINE_RESTORE"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Permission(str, Enum):
    SPEAK = "speak"
    INTERRUPT = "interrupt"
    CALL_TOOL = "call_tool"
    EDIT_FILE = "edit_file"
    WRITE_SESSION_MEMORY = "write_session_memory"
    WRITE_STABLE_MEMORY = "write_stable_memory"
    EDIT_PROTECTED_PERSONALITY = "edit_protected_personality"
    CHANGE_ROLE = "change_role"
    START_RECORDING = "start_recording"
    TRANSCRIBE = "transcribe"
    VOICE_ANALYSIS = "voice_analysis"
    VOICEPRINT_STORAGE = "voiceprint_storage"
    VOICE_CLONING = "voice_cloning"
    FACE_ANALYSIS = "face_analysis"
    EMOTION_INFERENCE = "emotion_inference"
    BIOMETRIC_IDENTIFICATION = "biometric_identification"
    RESTORE_PROFILE = "restore_profile"


class MemoryStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    EXPIRED = "expired"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    WORKSPACE_PRIVATE = "workspace_private"
    PERSONAL = "personal"
    SPECIAL_CATEGORY_RISK = "special_category_risk"
    PROTECTED_CORE = "protected_core"


@dataclass(frozen=True)
class RoleContract:
    role_id: str
    display_name: str
    allowed_permissions: List[Permission] = field(default_factory=list)
    forbidden_permissions: List[Permission] = field(default_factory=list)
    may_make_final_decisions: bool = False
    may_write_stable_memory: bool = False
    may_edit_protected_identity: bool = False
    may_start_recording: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.role_id.strip():
            raise ValueError("role_id is required")
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        overlap = set(self.allowed_permissions).intersection(self.forbidden_permissions)
        if overlap:
            raise ValueError(f"Role {self.role_id} both allows and forbids: {sorted(p.value for p in overlap)}")

    def allows(self, permission: Permission) -> bool:
        if permission in self.forbidden_permissions:
            return False
        if permission == Permission.WRITE_STABLE_MEMORY and not self.may_write_stable_memory:
            return False
        if permission == Permission.EDIT_PROTECTED_PERSONALITY and not self.may_edit_protected_identity:
            return False
        if permission == Permission.START_RECORDING and not self.may_start_recording:
            return False
        return permission in self.allowed_permissions

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class Participant:
    participant_id: str
    display_name: str
    participant_type: ParticipantType
    role: RoleContract
    model_name: Optional[str] = None
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise ValueError("participant_id is required")
        if not self.display_name.strip():
            raise ValueError("display_name is required")

    def is_ai(self) -> bool:
        return self.participant_type == ParticipantType.AI

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class ConsentState:
    recording: bool = False
    transcription: bool = False
    voice_analysis: bool = False
    voiceprint_storage: bool = False
    voice_cloning: bool = False
    facial_analysis: bool = False
    emotion_inference: bool = False
    biometric_identification: bool = False
    memory_promotion: bool = False
    ai_training_use: bool = False
    public_livestream: bool = False
    guest_participation: bool = False

    def has_required(self, required: List[str]) -> bool:
        unknown = [field_name for field_name in required if not hasattr(self, field_name)]
        if unknown:
            raise ValueError(f"Unknown consent field(s): {', '.join(unknown)}")
        return all(bool(getattr(self, field_name)) for field_name in required)

    def missing(self, required: List[str]) -> List[str]:
        return [field_name for field_name in required if not getattr(self, field_name, False)]

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class SessionTurn:
    turn_id: str
    speaker_id: str
    text: str
    timestamp: str = field(default_factory=utc_now)
    target_id: Optional[str] = None
    tool_event: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.turn_id.strip():
            raise ValueError("turn_id is required")
        if not self.speaker_id.strip():
            raise ValueError("speaker_id is required")
        if self.text is None:
            raise ValueError("text cannot be None")

    def approx_token_count(self) -> int:
        return max(1, len(self.text) // 4)

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass
class SessionState:
    session_id: str
    context: AlexContext
    mode: str
    host_id: str
    participants: Dict[str, Participant]
    consent: ConsentState = field(default_factory=ConsentState)
    turns: List[SessionTurn] = field(default_factory=list)
    active_goals: List[str] = field(default_factory=list)
    active_constraints: List[str] = field(default_factory=list)
    restore_checkpoints: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id is required")
        if not self.mode.strip():
            raise ValueError("mode is required")
        if self.host_id not in self.participants:
            raise ValueError(f"host_id {self.host_id!r} is not a participant")
        if not self.participants[self.host_id].active:
            raise ValueError("host participant must be active")

    def add_turn(
        self,
        speaker_id: str,
        text: str,
        target_id: Optional[str] = None,
        tool_event: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionTurn:
        if speaker_id not in self.participants:
            raise ValueError(f"Unknown speaker_id: {speaker_id}")
        if not self.participants[speaker_id].active:
            raise ValueError(f"Inactive speaker_id: {speaker_id}")
        if target_id is not None and target_id not in self.participants:
            raise ValueError(f"Unknown target_id: {target_id}")
        turn = SessionTurn(
            turn_id=new_id("turn"),
            speaker_id=speaker_id,
            target_id=target_id,
            text=text,
            tool_event=tool_event,
            metadata=metadata or {},
        )
        self.turns.append(turn)
        return turn

    def recent_turns(self, limit: int = 8) -> List[SessionTurn]:
        if limit < 1:
            return []
        return self.turns[-limit:]

    def participant_for(self, speaker_id: str) -> Optional[Participant]:
        return self.participants.get(speaker_id)

    def approx_recent_tokens(self, limit: int = 80) -> int:
        return sum(turn.approx_token_count() for turn in self.recent_turns(limit))

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class DetectorFinding:
    finding_id: str
    detector: str
    issue_class: str
    severity: Severity
    confidence: float
    intervention_level: InterventionLevel
    evidence_turn_ids: List[str] = field(default_factory=list)
    evidence_snippets: List[str] = field(default_factory=list)
    rules_fired: List[str] = field(default_factory=list)
    recommendation: str = ""
    created_at: str = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.detector.strip():
            raise ValueError("detector is required")
        if not self.issue_class.strip():
            raise ValueError("issue_class is required")

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    source_turn_ids: List[str]
    memory_type: str
    proposed_text: str
    confidence: float
    sensitivity: Sensitivity = Sensitivity.PERSONAL
    approval_required: bool = True
    decay_policy: str = "review_in_30d"
    legal_basis_or_consent: str = "pending_user_approval"
    approved_by: Optional[str] = None
    status: MemoryStatus = MemoryStatus.PROPOSED
    created_at: str = field(default_factory=utc_now)
    redactions: List[str] = field(default_factory=list)
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.source_turn_ids:
            raise ValueError("memory candidates require source_turn_ids")
        if not self.proposed_text.strip():
            raise ValueError("proposed_text is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class AuditBundle:
    audit_bundle_id: str
    session_id: str
    issue_class: str
    severity: Severity
    intervention_level: InterventionLevel
    findings: List[DetectorFinding]
    action: str
    user_visible_reason: str
    host_override_available: bool = True
    checkpoint_before: Optional[str] = None
    checkpoint_after: Optional[str] = None
    consent_snapshot: Dict[str, Any] = field(default_factory=dict)
    retention_class: str = "operational_30d"
    redactions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    evidence_turn_ids: List[str] = field(default_factory=list)
    rules_fired: List[str] = field(default_factory=list)
    recommended_commands: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.findings:
            raise ValueError("audit bundles require at least one finding")
        if not self.action.strip():
            raise ValueError("audit action is required")

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)
