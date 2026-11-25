# Pre-Beta 12 — Event Agency V2 / Observation

## Added
- `modules/agency_observation.py`
- `tests/test_agency_observation.py`
- `RECONCILIATION_HORIZON_v0.1.md`

## Architectural change
The event substrate now distinguishes:

`event occurred` from `character observed event`.

A deterministic, inspectable attention/salience score is recorded with each observation. It uses event priority, confidence, recency, relationship salience, and context salience.

## Deliberate non-features
- no autonomous action
- no model-generated authoritative state
- no automatic intention creation
- no permission bypass
- no replacement of existing memory/relationship engines

## Validation
187 passed, 3 skipped.
