# Codex Handoff — Alex Prime Core v0.4

## Mission

Wire Alex Prime Core into PubPartner without weakening the guardrail spine.

## Non-negotiable boundaries

- No direct writes to stable memory.
- No direct edits to protected personality or Prime continuity.
- No recording, transcription, voice, face, emotion, biometric, or voice-clone processing without explicit consent state.
- No UI path may hide an Alex intervention from the host.
- No Co-Lab participant may act outside its role contract without a visible gate.
- Every serious intervention must produce an audit bundle and evidence event.

## Primary integration points

1. Convert PubPartner chat/call/Co-Lab messages into `SessionTurn` records.
2. Create `SessionState` with participants, roles, goals, constraints, consent, and restore checkpoints.
3. Call `AlexRuntime.inspect_and_record(session)` after each turn and before each state-changing action.
4. Route returned `AuditBundle` to Live Status Pill, Why Panel, Intervention Queue, and Audit Drawer.
5. Persist evidence with `BlackBoxEvidenceRecorder` when Iteration Wallet BlackBox is available.
6. Use `TamperEvidentJsonlRecorder` as the local fallback evidence recorder.
7. Use `CoLabBriefBuilder` when Jeremy needs to refresh the active brief.
8. Use `PersonalSupportEngine` only in Personal Alex context.

## Files to read first

- `alex_prime/models.py`
- `alex_prime/runtime.py`
- `alex_prime/evidence.py`
- `alex_prime/detectors.py`
- `alex_prime/policy.py`
- `alex_prime/memory.py`
- `alex_prime/personal_support.py`
- `alex_prime/colab.py`
- `tests/test_alex_core.py`

## Verification command

```bash
python -m unittest discover -s tests -v
```
