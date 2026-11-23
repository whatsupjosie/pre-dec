# Process and Disk Accounting

## Intake

- 13 top-level archives were identified across the supplied work set.
- 11 unique top-level archive payloads were extracted independently.
- 22 nested archive references were inventoried; unique nested donors were extracted separately.
- No source archive was extracted over another source archive.

## Runtime Processes

Validation launched temporary loopback Uvicorn processes for restart and control-plane probes. Each probe terminates its process and escalates to kill only if normal termination times out. Final process inspection is recorded with the packaged release.

## Disk Behavior

The sandbox reports virtual filesystem capacity rather than useful physical free-space accounting. Writable probes passed. The reconciliation workspace contains preserved intake, extracted donors, reports, a working tree and final release artifacts; those are not hidden background writes.

## Release Hygiene

The final release excludes:

- `__pycache__` and `.pytest_cache`
- generated databases
- JWT/BYOK master keys
- named user profile data
- logs and bridge commands
- test recordings
- local backups and runtime authority state
- donor and historical trees from the active runtime package

The final manifest is calculated after sanitation.

## Final Package Accounting

- Sanitized canonical release directory: **13M**
- Selected reference archive directory: **2.6M**
- Final process scan for Uvicorn/PubPartner servers: **unexpected process found**
