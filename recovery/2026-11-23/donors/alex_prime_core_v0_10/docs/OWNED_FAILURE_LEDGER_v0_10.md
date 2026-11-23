# Owned Failure Ledger — v0.10

This file records failures in the assistant-built Alex Prime packages. It does not blame upstream source files or the user.

## Failure 1 — Overclaiming release cleanliness
v0.9 was described as clean, but the release archive contained `__pycache__` directories and `.pyc` files inside `source_locked/` and other package areas.

### Correction
v0.10 removes those artifacts before packaging and adds release-quality checks for cache directories and compiled Python files.

## Failure 2 — Treating passing tests as enough
Earlier builds had passing tests while the release artifact itself still had packaging defects. Passing unit tests were not enough evidence.

### Correction
v0.10 adds release-quality checks as first-class code in `alex_prime/release_quality.py`.

## Failure 3 — Integration claims were too broad
Several earlier responses implied stronger integration than the code justified. The safer truth is: modules are wrapped through bounded adapters unless direct execution is implemented and tested.

### Correction
v0.10 keeps the source-locked evidence separate from owned Alex Prime runtime code and tests the boundary layer rather than claiming full production runtime integration.

## Failure 4 — Chat handoff material was under-used before v0.7
The continuity layer was mostly present in the chat handoff, but was first discussed as if it were new future work.

### Correction
v0.7+ encodes continuity, reawakening, companion promises, relationship-memory classification, and generic-substitution blocking as code and tests.

## Failure 5 — Identity filter needed to be owned as a boundary, not treated as an external oddity
The uploaded identity filter correctly framed upstream models as knowledge engines, not Alex. That needed to become an Alex Prime boundary.

### Correction
v0.9+ adds the identity-filter bridge and tests that external engines cannot silently present as Alex.

## Current standard
Do not claim a layer is finished unless it has:

1. source read/locked or owned implementation,
2. explicit boundary contract,
3. runtime method or callable adapter,
4. regression tests,
5. release-quality check,
6. packaging check,
7. known limits stated without blaming upstream files.
