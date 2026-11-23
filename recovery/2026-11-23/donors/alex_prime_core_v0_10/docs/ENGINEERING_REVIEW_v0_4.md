# Engineering Review — Alex Prime Core v0.4

## What improved

v0.4 moves the system from a deterministic intervention core into a more complete integration core:

- Evidence can be persisted and verified.
- BlackBox-style recorders can receive Alex audit bundles.
- Personal Alex support logic is available without contaminating PubCast AlexT policy.
- Jeremy/Alex Co-Lab context packets can be generated and scoped.

## What is production-ready inside this package

- Session validation.
- Role/permission modeling.
- Consent-state modeling.
- Deterministic detector execution.
- Policy mapping to intervention levels.
- Memory candidate gating.
- Audit bundle generation.
- Local evidence hash-chain persistence and verification.
- BlackBox API adapter.
- Unit tests for all added v0.4 capabilities.

## What still requires external integration

- PubPartner UI wiring.
- Iteration Wallet restore execution.
- BlackBox instance lifecycle management in the real app.
- Provider/model adapters.
- Real transcript datasets for detector calibration.
- Tokenizer-specific context counting.
- Voice/call/prosody pipelines.
- Database-backed audit browsing.

## Promotion recommendation

Use v0.4 as the Alex Prime safety/evidence core candidate. Do not promote it as the full PubPartner application. The correct next step is integration testing against real PubPartner Co-Lab events and BlackBox vault storage.
