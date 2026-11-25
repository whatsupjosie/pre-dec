# CHANGELOG v0.5

## Added

- `alex_prime/production_bridge.py`
- `ProductionSubsystem`, `ProductionRisk`, `ProductionEvent`, `ProductionAlert`
- `MediaConsentPlanner` for production media consent requirements
- `VoiceRegisterAdapter` for safe VDI/prosody delivery guidance
- `AudioProtectionPolicy` enforcing audio-first production safety
- `AlexProductionBridge` for production event findings
- `AlexRuntime.inspect_production_event()`
- `AlexRuntime.production_alert_for_event()`
- `AlexRuntime.voice_guidance_for_event()`
- `examples/demo_production_bridge.py`
- v0.5 production bridge tests

## Hardened

- Production event consent checks now gate facial analysis, emotion inference, recording, voice analysis, voiceprint storage, voice cloning, transcription, and biometric identification.
- E-Pete identity boundary is enforced: E-Pete may route/govern but not roleplay or speak as character.
- Pete character boundary is enforced: non-character layers cannot directly surface as Pete.
- VDI identity mode is treated as a voice delivery register, not proof of user/audience emotion.
- Audio degradation produces a policy finding recommending visual load reduction before audio compromise.

## Tests

- Expanded from 24 passing tests to 30 passing tests.
- Added production bridge regression tests for consent gating, audio protection, E-Pete/Pete boundaries, fact-only alert packets, and voice-register uncertainty.

## Deferred integration layers

- Live camera capture.
- Live voice synthesis.
- Full EVO runtime execution.
- Real provider/model adapters.
- PubPartner UI panels.
- Iteration Wallet restore execution.

Those belong to integration layers. This package supplies Alex's deterministic control boundary around them.
