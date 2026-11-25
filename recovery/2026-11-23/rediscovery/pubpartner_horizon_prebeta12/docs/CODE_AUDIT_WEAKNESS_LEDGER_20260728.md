# PubPartner Character-Level Code Audit and Weakness Ledger

**Audit date:** 2026-07-28

**Audited baseline:** `a987345` (`0.1.0-prebeta.8+vessel-foundation.20260728`)

**Purpose:** Preserve every confirmed defect and deferred weakness found during
the character-level audit so code-quality work is not lost between handoffs.

## What “character-level” covered

The audit read every tracked source/text file as strict UTF-8 and inspected
2,744,598 bytes across 278 files. It checked raw bytes, line endings, invisible
Unicode controls, Python tokenization and AST construction, duplicate Python
definitions, duplicate literal dictionary keys, duplicate JSON keys, Python
byte-compilation, JavaScript syntax, shell syntax, static name resolution,
security patterns, dependency advisories, and the repository test suite.

The semantic manual pass concentrated on destructive and trust-bearing paths:
recording import/export, identity-derived paths, BYOK credential storage,
authentication boundaries, PubPartner vessel storage, memory evidence,
correction provenance, visibility filtering, context compilation, backups, and
vault integrity handling.

## Confirmed defects fixed in this audit

| Area | Defect | Resolution |
|---|---|---|
| BYOK character packets | `build_character_packet()` referenced nonexistent `_CHARACTER_SYSTEM_PROMPTS` and crashed. | Routed through the existing canonical/fallback prompt resolver. |
| Room conductor | Three annotations/constructors referenced nonexistent `JeremyConfig`. | Replaced with `RoomConductorConfig`. |
| Vault watcher | Its exception handler referenced undefined `logger`, masking the original integrity error with another crash. | Added the module logger and an executed failure-path regression test. |
| Recording service | `Any` was used but not imported. | Corrected the type import. |
| Bubble Stack package | Public sandbox symbols were imported twice and redefined. | Consolidated one complete public import/export list. |
| Recording filesystem boundary | API and ZIP-controlled `session_id` values were joined directly to recording paths, permitting `../` path escape. | Added strict service-level identifier validation before any directory or file operation. |
| User-state/avatar filesystem boundary | `X-Client-Id` or token subjects were used directly in user/avatar filenames. | Added collision-resistant `storage_key()` mapping and applied it to all affected paths. |
| BYOK user isolation | Distinct unsafe-looking user IDs could sanitize to the same encrypted credential and model files. | Applied collision-resistant storage keys; tested separate secrets for colliding-looking identities. |
| Vessel corrections | `replace`/`narrow` changed retrieval text but left `object_json` holding the old value. | Updates the stored value and normalized text atomically. |
| Vessel correction provenance | A correction could reference another subject’s memory event. | Requires the correction event to exist and match the claim subject. |
| Vessel correction collisions | Replacing text with an existing claim could leak a raw SQLite uniqueness failure. | Detects the collision and raises a domain-level `VesselConflictError` with transaction rollback. |
| Dependency security | `cryptography<46` forced installation of versions with published advisories. | Requires `cryptography>=48.0.1,<49.0`; dependency audit is clean. |
| Non-security identifiers | Four short identifiers used MD5, creating noisy high-severity scanner reports and a poor future default. | Moved new identifier/fingerprint generation to SHA-256. |

## Verified scan results

- No invalid UTF-8, NUL bytes, BOMs, mixed newline encodings, bare carriage
  returns, bidirectional override controls, or zero-width controls.
- No duplicate JSON keys, duplicate Python definitions, duplicate literal
  dictionary keys, Python parse failures, or Python tokenize failures.
- No unresolved-name or redefinition findings after the fixes.
- Python `compileall`, all tracked JavaScript syntax checks, the tracked shell
  launcher syntax check, and `git diff --check` pass.
- Full suite: **176 passed, 3 skipped**.
- Dependency audit: **no known vulnerabilities** in `requirements.txt`.
- Bandit’s remaining medium reports are two intentional all-interface bind
  defaults and two allowlisted-table SQL constructions; neither SQL table name
  is caller-controlled.

## Deferred weaknesses — preserve for the next hardening pass

| Priority | Location | Weakness / consequence | Recommended next work |
|---|---|---|---|
| High | `modules/pubpartner_vessel/store.py` | Audit and record-integrity hashes are unkeyed. A local writer able to alter the SQLite file can recompute both chains. They detect accidents and unsophisticated tampering, not a hostile local administrator. | Add an owner-held signing/HMAC key, signed root checkpoints, key rotation, and explicit trust-state reporting. |
| High | PubPartner vessel contents | Relationship history, memories, and identity data are plaintext SQLite. File permissions are the only confidentiality layer. | Add optional authenticated encryption with a recovery/export design and measurable key-loss behavior. |
| High | `modules/recording.py` and recording upload route | ZIP imports have no cumulative expanded-byte or member-count budget. A zip bomb or huge archive can exhaust disk; an interrupted import can leave a partial session directory. | Add configurable compressed/expanded limits, member count limits, streaming accounting, exclusive targets, and transactional staging cleanup. |
| High | direct `uvicorn` startup / `modules/route_security.py` | Authentication defaults to relaxed mode unless launched through `run_pubpartner.py`. An operator starting the ASGI app directly can expose write routes unintentionally. | Fail closed outside an explicit development flag; make runtime security mode prominent in health and UI. |
| High | multiple legacy `_safe_slug`/filename helpers | Several non-credential stores still normalize identifiers without a digest. Production usernames are restricted, but relaxed/local callers can create collisions in guidance, receipts, session, or avatar files. | Replace identity-derived legacy slugs with one versioned storage-key service and provide an audited migration. |
| Medium | vessel path mounting and backup | Symlink checks are pathname-based and do not pin every ancestor/file descriptor across SQLite open, validation, and replacement. A hostile concurrent local process can still create TOCTOU races. | Add trusted-root policy, ancestor checks, platform-specific handle pinning where possible, and adversarial race tests. |
| Medium | `modules/pubpartner_vessel/store.py::_decode` | Malformed JSON columns silently become defaults. Integrity seals catch post-write modification, but malformed legacy/state data can be hidden instead of diagnosed. | Raise typed corruption errors for authoritative fields; reserve fallback behavior for explicitly versioned legacy imports. |
| Medium | `modules/pubpartner_vessel/context.py::_clip` | The final character budget can truncate a JSON-bearing context line midway, weakening inspectability and confusing smaller models. | Budget by complete sections/items and emit a structured truncation manifest rather than slicing the final string. |
| Medium | memory event sources | A caller-supplied `source_hash` is accepted without checking it against content or a canonical external source record. | Separate content hash from external evidence hash and verify resolvable evidence references at ingestion. |
| Medium | append-only JSONL stores | Several guidance, receipt, and audit writers use process-local/no locking and do not fsync each append. Concurrent writes or power loss can corrupt their tail. | Consolidate on one durable append primitive with locking, checksums, recovery, and bounded repair. |
| Medium | network defaults | `modules/appconfig.py` defaults the main host to `0.0.0.0`; `modules/bridge_raw.py` binds UDP on all interfaces. | Default every standalone component to loopback and require an explicit network-exposure switch. |
| Medium | dependency/API drift | TestClient emits a Starlette deprecation warning for the current `httpx` integration. | Align FastAPI/Starlette/httpx versions and update test construction before the deprecated adapter is removed. |
| Low | repository-wide static debt | Broad Ruff produced 4,129 findings, dominated by typing modernization, broad exception catches, framework `Depends()` idioms, import order, and unused imports. Critical undefined names were separated and fixed. | Triage by rule family; do not bulk-auto-fix framework code. Start with 372 broad catches, 143 unused imports, and 31 silent exception handlers. |
| Low | textual hygiene | Baseline contains 1,373 trailing-whitespace lines and 14 lines over 500 characters, mostly legacy UI/CSS and dense profile data. | Normalize only in isolated formatting commits to keep functional reviews readable. |
| Compatibility | BYOK legacy IDs | Existing credential files created for identifiers containing unsafe filename characters cannot be automatically attributed safely because the old sanitizer was collision-prone. | Build an owner-confirmed migration tool that inventories ambiguous files and never guesses ownership. |

## Tooling gaps

- Rust sources were byte-scanned, but `cargo`/`rustc` were unavailable, so the
  Rust crates were not compiler-checked.
- PowerShell launchers were byte-scanned, but PowerShell was unavailable, so
  they were not parser-executed.
- Three repository tests remain intentionally skipped; the final test report
  should retain their names and reasons rather than counting them as passes.

## Next recommended audit order

1. Keyed/signed vessel integrity and encrypted-at-rest design.
2. Recording import resource limits and transactional staging.
3. Replace remaining collision-prone identity path helpers.
4. Fail-closed direct-server authentication and network binding.
5. Durable concurrent JSONL writer consolidation.
6. Broad-exception and unused-code cleanup by subsystem.
