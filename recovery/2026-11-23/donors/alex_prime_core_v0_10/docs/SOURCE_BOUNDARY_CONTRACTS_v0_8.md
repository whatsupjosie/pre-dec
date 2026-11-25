# Source Boundary Contracts v0.8

These contracts keep uploaded source modules in their proper lanes.

## blackbox
- source files: blackbox_4.py
- owns: append-only evidence, hash-chain verification, BBX1 event records, human-intent receipts
- boundary rules:
  - warning: `blackbox_must_not_interpret` — BlackBox records facts and custody events; it must not decide Alex identity or emotional truth.
- integration notes: Use as evidence spine for audit bundles and protected actions.

## camera_manager
- source files: camera_manager_1.py
- owns: camera transports, camera status, program/preview/standby roles, capture lifecycle
- boundary rules:
  - block: `camera_manager_must_not_infer_emotion` — CameraManager may report camera state; it must not infer emotion or consent.

## distributed_engine
- source files: distributed_engine.py
- owns: engine node role, system load, work distribution, audio quality metrics
- boundary rules:
  - block: `audio_never_sacrificed` — Distributed engine policy must not sacrifice audio quality to preserve visual fidelity.

## epete
- source files: epete_2.py
- owns: inference routing, flow control, system awareness, fact-only escalation, delegation
- boundary rules:
  - block: `epete_must_not_speak` — E-Pete does not speak to the user directly.
  - block: `epete_must_not_roleplay` — E-Pete does not roleplay and has no personality surface.

## pete
- source files: pete.py
- owns: character speech, floor-director persona, system-alert expression
- boundary rules:
  - block: `pete_must_not_govern` — Pete does not route, govern, schedule, or expose raw engine decisions.

## vdi_prosody
- source files: vdi_engine.py, prosody_engine.py, voice_characters.py
- owns: voice mode, delivery register, synthesis parameters, character voice identity
- boundary rules:
  - block: `no_emotion_certainty` — VDI/prosody signals guide delivery; they must not be presented as certain emotion, intent, deception, or attraction detection.

## facial_performance
- source files: facial_performance_1.py
- owns: performer facial signals, audience facial signals, VDI signal generation
- boundary rules:
  - block: `requires_media_consent` — Face/emotion processing requires explicit consent and visible session state.
  - block: `no_emotion_certainty` — Facial analysis must not be sold or displayed as direct mind-reading.

## switchblade
- source files: switchblade_governor_2.py
- owns: semantic render priority, resource priority vector, LOD decisions
- boundary rules:
  - block: `switchblade_must_not_speak` — Switchblade emits compact priority vectors; it does not create user-facing language.

## alex_adaptive_companion
- source files: source_locked/alex_core_adaptive_companion/alex_core/*.py
- owns: state detection, care hypothesis, protocol selection, private support decision, Jeremy packet
- boundary rules:
  - block: `personal_support_not_clinical_therapy` — Adaptive companion support is not clinical therapy or diagnosis.
