# Uploaded File Integration Notes — v0.4

## blackbox(4).py

Used as the contract target for `BlackBoxEvidenceRecorder`.

Expected methods:

- `write_event(event_type, summary, **kwargs)`
- `verify_chain()`

Alex writes `ALEX_AUDIT_BUNDLE` events through this adapter. The adapter checks that an event hash comes back and that verification returns a dictionary.

## alex_core_adaptive_companion(3).zip

Used as source material for `personal_support.py`.

Pulled forward concepts:

- support hypotheses, not diagnoses
- care needs
- care style selection
- communication protocol selection
- low-density support under overload
- honest-feedback mode
- Jeremy notification when load should be reduced

## files (51)/(52)

Used as context for Jeremy/PubCast companion integration.

Pulled forward concepts:

- Jeremy as continuity/nudge spine
- PubPartner needs scoped context packets
- Alex and Jeremy should coordinate instead of merging roles

## files (53)

Used as quality/intake context.

Pulled forward concepts:

- prefer best-version candidates over raw duplicates
- record integration decisions explicitly
- protect Prime from unreviewed imports

## files (54)/(55)

Used as compatibility and build-audit context.

Pulled forward concepts:

- adapter layer over invasive replacement
- build audits before promotion
- preserve existing tested spines instead of replacing them blindly
