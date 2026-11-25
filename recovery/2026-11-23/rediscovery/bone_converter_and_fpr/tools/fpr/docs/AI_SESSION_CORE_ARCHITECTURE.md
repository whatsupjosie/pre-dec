# AI Session Core

Independent system discussed in conversation:
- boot process
- active mode selection
- end-of-session detection
- idle checkpointing
- session logging
- current state tracking
- Git checkpoint support

Core directories discussed:
- memory/
- session_logs/
- modes/
- agents/
- state/
- scripts/
- adapters/

Important files discussed:
- BOOT.md
- ACTIVE_MODE.md
- ACTIVE_AGENTS.md
- SESSION_PROTOCOL.md
- AGENT_PROTOCOL.md
- memory/current_state.md
- memory/decisions.md
- memory/long_term.md

Core rule:
Read BOOT.md first. Load state, load latest session log, resolve mode, load agents, align, then begin work.

End session:
summarize work, record decisions, record open issues, update current_state, write session log, checkpoint.
