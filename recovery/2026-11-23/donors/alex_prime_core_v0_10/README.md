# Alex Prime Core v0.10

This release owns the packaging and quality-gate failures found after v0.9.

## Main correction
v0.9 contained cache artifacts in the release archive despite being described as clean. v0.10 adds a release-quality module and tests so cache artifacts and banned owned-code markers are caught.

## Key additions
- `alex_prime/release_quality.py`
- `docs/OWNED_FAILURE_LEDGER_v0_10.md`
- release-quality tests for cache detection and owned-file marker checks

## Validation
- Unit tests: 55/55 passing
- Release archive: checked clean for `__pycache__`, `.pyc`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
- Source-locked files remain verbatim except runtime-generated cache artifacts are excluded from release packaging

## Principle
No blame-shifting to user-provided files. Alex Prime owns its adapters, boundaries, packaging, tests, and claims.
