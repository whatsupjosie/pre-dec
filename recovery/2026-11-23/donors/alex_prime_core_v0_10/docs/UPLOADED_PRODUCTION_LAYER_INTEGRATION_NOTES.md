# Uploaded Production Layer Integration Notes

## Files interpreted

The new uploaded modules describe the PubCast production side:

- camera management
- distributed engine / camera nodes
- E-Pete routing and system governance
- EVO orchestration
- facial performance and audience analysis
- Pete character layer
- prosody engine
- Switchblade semantic scheduler
- VDI engine
- voice character profiles

## Integration decision

Do not merge these modules into Alex Prime.

Alex Prime is not a camera manager, renderer, voice synthesizer, character performer, or engine scheduler. Alex receives normalized events from those systems and applies consent, continuity, memory, identity-boundary, and Co-Lab stability policy.

## Boundaries

### Pete

Pete is a character. Pete speaks. Pete translates system facts into character voice.

Alex must not overwrite Pete's voice layer or speak as Pete.

### E-Pete

E-Pete is silent governance/routing. E-Pete does not roleplay or speak to the user.

Alex may recommend a system alert, but E-Pete/Pete handle the production-layer delivery path.

### EVO / VDI / Prosody

VDI/prosody states are delivery signals. They do not prove inner emotional truth.

Alex maps them into safe voice guidance and uncertainty warnings.

### Facial and voice analysis

Facial analysis, emotion inference, voice analysis, voiceprint storage, voice cloning, recording, and transcription require explicit consent states before activation.

### Audio protection

The production files repeat the principle that audio is never sacrificed. Alex now enforces this as a policy signal: if audio quality drops, reduce visual load or route an E-Pete alert before compromising audio.

## v0.5 bridge shape

Production system emits:

```python
ProductionEvent(
    subsystem=ProductionSubsystem.FACIAL_PERFORMANCE,
    event_type="audience_analysis_requested",
    metadata={"facial_analysis": True, "emotion_inference": True},
)
```

Alex evaluates:

```python
audit = runtime.inspect_production_event(session, event)
```

If consent is missing, Alex returns an audit bundle with `L3_GATE` and `alex.require_consent`.

## Why this is safer

The production modules are ambitious and identity-rich. Direct merge would blur layers. The bridge keeps each system in its lane:

- E-Pete governs.
- Pete speaks.
- EVO orchestrates.
- Switchblade schedules compute.
- VDI/prosody shape delivery.
- Alex protects consent, continuity, emotional/system stability, and memory integrity.
