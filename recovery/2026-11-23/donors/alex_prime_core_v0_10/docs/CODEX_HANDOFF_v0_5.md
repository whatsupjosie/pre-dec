# Codex Handoff v0.5

## Goal

Wire Alex Prime Core v0.5 into PubPartner/PubCast without collapsing production modules into Alex identity.

## New module

`alex_prime/production_bridge.py`

## Important runtime calls

```python
runtime.inspect_production_event(session, event)
runtime.production_alert_for_event(session, event)
runtime.voice_guidance_for_event(event)
```

## Required integration path

1. Convert real PubCast camera/EVO/VDI/prosody/E-Pete/Pete events into `ProductionEvent`.
2. Run `inspect_production_event()` before enabling recording, transcription, voice analysis, face analysis, emotion inference, voiceprint storage, voice cloning, or biometric identification.
3. Display returned audit bundles in the PubPartner Why Panel / Intervention Queue.
4. Persist serious findings through BlackBox/Iteration Wallet evidence recorder.
5. Route any fact-only `ProductionAlert` through E-Pete/Pete, not directly through Alex as Pete.

## Do not do this

- Do not import live EVO modules directly into Alex core unless dependency boundaries are clean.
- Do not let E-Pete speak or roleplay.
- Do not let Alex speak as Pete.
- Do not let VDI/facial/prosody signals make emotion-certainty claims.
- Do not bundle voice cloning into ordinary recording consent.
- Do not sacrifice audio before reducing visual load.

## Current validation

`python -m unittest discover -s tests -v` passes 30 tests.
