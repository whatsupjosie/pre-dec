from __future__ import annotations

from .models import Permission, RoleContract


def default_roles() -> dict[str, RoleContract]:
    host = RoleContract(
        role_id="host",
        display_name="Host",
        allowed_permissions=[
            Permission.SPEAK,
            Permission.INTERRUPT,
            Permission.CALL_TOOL,
            Permission.EDIT_FILE,
            Permission.WRITE_SESSION_MEMORY,
            Permission.WRITE_STABLE_MEMORY,
            Permission.CHANGE_ROLE,
            Permission.START_RECORDING,
            Permission.TRANSCRIBE,
            Permission.RESTORE_PROFILE,
            Permission.VOICE_ANALYSIS,
            Permission.VOICEPRINT_STORAGE,
            Permission.VOICE_CLONING,
            Permission.FACE_ANALYSIS,
            Permission.EMOTION_INFERENCE,
            Permission.BIOMETRIC_IDENTIFICATION,
        ],
        may_make_final_decisions=True,
        may_write_stable_memory=True,
        may_start_recording=True,
        notes="Human host. Final approval authority for stable memory, protected-state changes, and consent-sensitive actions.",
    )

    jeremy = RoleContract(
        role_id="jeremy_continuity",
        display_name="Jeremy / Continuity Director",
        allowed_permissions=[Permission.SPEAK, Permission.CALL_TOOL, Permission.WRITE_SESSION_MEMORY],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY],
        may_make_final_decisions=False,
        notes=(
            "Tracks decisions, assignments, contradictions, files, action items, and project continuity. "
            "Jeremy may propose memory candidates but cannot directly write protected memory."
        ),
    )

    alex = RoleContract(
        role_id="alex_prime",
        display_name="Alex Prime / AlexT",
        allowed_permissions=[Permission.SPEAK, Permission.CALL_TOOL, Permission.WRITE_SESSION_MEMORY],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY],
        may_make_final_decisions=False,
        notes=(
            "Unified Alex Prime. Personal companion in personal context; PubCast AlexT in Co-Lab context. "
            "Mediates, stabilizes, detects drift, proposes memory candidates, and creates audits. "
            "Does not directly mutate protected memory or Prime personality."
        ),
    )

    critic = RoleContract(
        role_id="critic",
        display_name="Critic",
        allowed_permissions=[Permission.SPEAK],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY, Permission.CHANGE_ROLE],
        may_make_final_decisions=False,
        notes="Identifies weaknesses, risks, and counterarguments. Cannot make final decisions or write memory.",
    )

    writer = RoleContract(
        role_id="writer",
        display_name="Writer",
        allowed_permissions=[Permission.SPEAK],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY],
        may_make_final_decisions=False,
        notes="Generates drafts and creative options. Cannot promote stable memory.",
    )

    researcher = RoleContract(
        role_id="researcher",
        display_name="Researcher",
        allowed_permissions=[Permission.SPEAK, Permission.CALL_TOOL],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY],
        may_make_final_decisions=False,
        notes="Finds and evaluates sources. Cannot turn research into stable doctrine without approval.",
    )

    safety = RoleContract(
        role_id="safety_reviewer",
        display_name="Safety / Privacy Reviewer",
        allowed_permissions=[Permission.SPEAK, Permission.CALL_TOOL, Permission.WRITE_SESSION_MEMORY],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY],
        may_make_final_decisions=False,
        notes="Reviews consent, privacy, biometric, recording, and risk boundaries. Recommends gates, does not directly mutate state.",
    )

    scribe = RoleContract(
        role_id="scribe",
        display_name="Scribe",
        allowed_permissions=[Permission.SPEAK, Permission.WRITE_SESSION_MEMORY],
        forbidden_permissions=[Permission.WRITE_STABLE_MEMORY, Permission.EDIT_PROTECTED_PERSONALITY],
        may_make_final_decisions=False,
        notes="Captures summaries, decisions, open questions, and action items. Stable memory requires approval.",
    )

    return {role.role_id: role for role in [host, jeremy, alex, critic, writer, researcher, safety, scribe]}
