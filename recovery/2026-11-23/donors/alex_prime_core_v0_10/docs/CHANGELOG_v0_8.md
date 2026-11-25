# Alex Prime Core v0.8 Changelog

v0.8 corrects the prior integration mistake: uploaded source files are now source-locked, hashed, parsed, inventoried, and tested instead of being treated as vague inspiration.

## Added

- `alex_prime/source_intake.py`
  - AST-based source inventory
  - SHA-256 hashes
  - import/class/method extraction
  - explicit runtime-risk marker reporting

- `alex_prime/source_contracts.py`
  - BlackBox, CameraManager, DistributedEngine, E-Pete, Pete, VDI/Prosody, FacialPerformance, Switchblade, and Alex adaptive companion boundary contracts
  - validates direct E-Pete speech attempts
  - validates audio-sacrifice violations

- `alex_prime/adaptive_companion_bridge.py`
  - compatibility bridge for the uploaded `alex_core_adaptive_companion` source package
  - runtime method `consult_adaptive_companion_source(...)`
  - personal-context-only enforcement

- `source_locked/uploaded_pubcast_sources/`
  - locked copies of the uploaded production-layer source files

- `source_locked/alex_core_adaptive_companion/`
  - locked copy of the uploaded Alex adaptive companion core, excluding cache artifacts

- `config/source_inventory_v0_8.json`
  - machine-readable source inventory

- `docs/SOURCE_INTAKE_AUDIT_v0_8.md`
- `docs/SOURCE_BOUNDARY_CONTRACTS_v0_8.md`

## Tests added

- uploaded source inventory parses locked source files
- camera source runtime-risk markers are detected
- E-Pete direct speech is blocked by source contract
- audio sacrifice is blocked by source contract
- uploaded adaptive companion source engine runs through bridge
- adaptive companion source bridge is personal-only

## Honest finding

Several uploaded source files contain unfinished/simulation-runtime markers. v0.8 does not promote those sections as complete. It preserves them as locked source material, exposes their risk markers in the audit, and wraps them behind boundary contracts.
