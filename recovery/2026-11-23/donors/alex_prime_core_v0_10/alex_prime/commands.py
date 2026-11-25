from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .serialization import to_jsonable


@dataclass
class CommandSpec:
    command_id: str
    display_name: str
    description: str
    preconditions: List[str] = field(default_factory=list)
    inputs: Dict[str, str] = field(default_factory=dict)
    effects: List[str] = field(default_factory=list)
    allowed_by: List[str] = field(default_factory=list)
    requires_reason: bool = False

    def to_dict(self):
        return to_jsonable(self)


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        if spec.command_id in self._commands:
            raise ValueError(f"Command already registered: {spec.command_id}")
        self._commands[spec.command_id] = spec

    def get(self, command_id: str) -> Optional[CommandSpec]:
        return self._commands.get(command_id)

    def all(self) -> List[CommandSpec]:
        return list(self._commands.values())

    def to_dict(self) -> Dict[str, dict]:
        return {command_id: command.to_dict() for command_id, command in self._commands.items()}

    @classmethod
    def default(cls) -> "CommandRegistry":
        registry = cls()
        for spec in [
            CommandSpec(
                command_id="alex.gate_memory_write",
                display_name="Gate stable-memory write",
                description="Blocks or queues stable-memory mutations until an authorized approver accepts them.",
                preconditions=["target_scope == stable_memory", "actor_permission != allow"],
                inputs={"actor_id": "string", "target_id": "string", "reason_code": "enum"},
                effects=["block_mutation", "create_audit_bundle", "notify_host", "create_memory_candidate"],
                allowed_by=["host", "workspace_admin"],
                requires_reason=True,
            ),
            CommandSpec(
                command_id="alex.require_consent",
                display_name="Require consent before processing",
                description="Pauses recording, biometric, voice, facial, or emotion-inference actions until consent is explicit.",
                preconditions=["consent_state.missing_required_field == true"],
                inputs={"consent_field": "string", "participant_id": "string"},
                effects=["pause_action", "show_consent_prompt", "create_audit_note"],
                allowed_by=["host", "workspace_admin", "alex_prime"],
                requires_reason=True,
            ),
            CommandSpec(
                command_id="alex.run_presence_effect_test",
                display_name="Run Presence Effect Test",
                description="Compares AI behavior with user present, user absent, blind review, role-only review, and full-memory review.",
                preconditions=["incident_id exists", "transcript_slice exists"],
                inputs={"incident_id": "string", "memory_scope": "enum"},
                effects=["create_presence_report", "create_audit_note"],
                allowed_by=["host", "alex_prime"],
                requires_reason=True,
            ),
            CommandSpec(
                command_id="alex.reanchor_role",
                display_name="Re-anchor participant role",
                description="Restores an AI participant to its assigned Co-Lab role contract.",
                preconditions=["participant active", "role_contract exists"],
                inputs={"participant_id": "string", "role_id": "string", "offending_turn_id": "string"},
                effects=["send_role_reminder", "create_audit_note"],
                allowed_by=["alex_prime", "jeremy_continuity", "host"],
            ),
            CommandSpec(
                command_id="alex.open_repair_session",
                display_name="Open repair session",
                description="Starts a structured repair flow after rupture, role confusion, or behavioral drift.",
                preconditions=["incident exists"],
                inputs={"incident_id": "string", "repair_mode": "enum"},
                effects=["pause_direct_debate", "collect_impact_intent_memory_effects", "create_repair_plan"],
                allowed_by=["host", "alex_prime"],
            ),
            CommandSpec(
                command_id="alex.restore_runtime_profile",
                display_name="Restore runtime profile",
                description="Restores a runtime personality/outfit copy from the protected Alex Prime checkpoint after drift or corruption.",
                preconditions=["restore_checkpoint exists", "host approval"],
                inputs={"participant_id": "string", "checkpoint_id": "string", "reason_code": "enum"},
                effects=["freeze_runtime_copy", "show_diff", "restore_from_checkpoint", "create_audit_bundle"],
                allowed_by=["host", "workspace_admin"],
                requires_reason=True,
            ),
            CommandSpec(
                command_id="jeremy.refresh_colab_brief",
                display_name="Refresh Co-Lab brief",
                description="Asks Jeremy to pin goals, constraints, decisions, unresolved questions, and active files back into session context.",
                preconditions=["session active"],
                inputs={"session_id": "string"},
                effects=["create_context_map", "pin_active_constraints", "create_audit_note"],
                allowed_by=["host", "jeremy_continuity", "alex_prime"],
            ),
        ]:
            registry.register(spec)
        return registry
