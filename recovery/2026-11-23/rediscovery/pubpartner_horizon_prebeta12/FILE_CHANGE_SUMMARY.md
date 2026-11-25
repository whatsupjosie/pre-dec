# File Change Summary — Canonical Reconciliation RC7

## Changed Runtime Files

- `pubpartner_app.py`
  - made the lightweight app boot Alex, Jeremy bridge, Pub Manager and Governance together
  - mounted object-bound routes during lifespan
  - added honest minimal-runtime engineering action executor
  - exposed control-plane truth in app health
- `scripts/sanitize_release.py`
  - removes named user profiles and generated authority/runtime data
  - recreates empty seed directories with `.gitkeep`
- `VERSION`
  - advanced to canonical reconciliation version

## Added Tests

- `tests/test_reconciliation_authority_adversarial.py`
- `tests/test_reconciliation_release_hygiene.py`
- `tests/test_pubpartner_app_control_plane_wiring.py`

## Added Verification Script

- `scripts/pubpartner_control_plane_probe.py`

## Added/Updated Current Documentation

- `README_START_HERE.md`
- `CURRENT_RUNTIME_TRUTH.md`
- `CAPABILITY_CONTRACT_MAP.md`
- `RUNTIME_IMPORT_GRAPH.md`
- `BOOT_SEQUENCE.md`
- `UNREACHABLE_OR_UNWIRED_COMPONENTS.md`
- `CONFLICT_RESOLUTION_LEDGER.md`
- `PROVENANCE_LEDGER.md`
- `FILE_CHANGE_SUMMARY.md`
- `TEST_RESULTS_SUMMARY.md`
- `AUTHORITY_ADVERSARIAL_REPORT.md`
- `WINDOWS_LAUNCH_VERIFICATION.md`
- `POWERSHELL_QUICK_START.txt`
- `PROCESS_AND_DISK_ACCOUNTING.md`
- `FINAL_ACCOUNTABILITY.md`

## Protected Content

No authored file under `source_locked/` was changed.
