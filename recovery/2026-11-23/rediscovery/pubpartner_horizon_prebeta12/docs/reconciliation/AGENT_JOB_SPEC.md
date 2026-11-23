# AGENT JOB: FULL PUBPARTNER / PUBCAST CANONICAL RECONCILIATION, REPAIR, AND RELEASE PASS

You are responsible for performing a complete file-by-file and function-by-function reconciliation of the currently supplied PubPartner, Pub Manager, Alex Prime, Provider Neutralizer, Bubble Stack, and related PubCast packages.

This is deliberately a long, exhaustive assignment. Do not rush it, summarize it prematurely, or stop after producing an audit. The final objective is a verified, coherent, bootable canonical build with a complete provenance record.

## PRIMARY GOAL

Create one authoritative PubPartner release candidate that:

* preserves every genuinely working subsystem
* eliminates accidental duplication and conflicting implementations
* uses the strongest verified implementation of each capability
* keeps each subsystem in its intended architectural role
* boots through one clearly identified production entrypoint
* passes all available tests that can run in the provided environment
* clearly distinguishes verified functionality from incomplete, optional, blocked, or untested functionality
* includes all files necessary for the build to be transferred to another engineer or AI without missing context

Do not merely declare one zip “newest” and assume it is best. Determine canonicality through code behavior, integration state, test coverage, provenance, and compatibility.

---

# INPUT PACKAGES TO RECONCILE

Inspect every supplied package and relevant loose file, including at minimum:

* `PubPartner_RC2_HANDOFF_20260712.zip`
* `PubPartner_PRELAUNCH_RC2_PUB_MANAGER_20260711.zip`
* `PubPartner_PRELAUNCH_RC6_PROVIDER_NEUTRALIZER_20260712.zip`
* `PubPartner_Handoff_2026-07-12.zip`
* `PubPartner_Handoff_2026-07-12 (1).zip`
* `PubPartner_Handoff_2026-07-09.zip`
* `PubCast_v5_6_verified_and_fixed_2026-07-12.zip`
* `PubCast_v5_6_BubbleStack_WIRED_2026-07-06.zip`
* `alex_prime_core_handoff_package(4).zip`
* `alex_prime_core_v0_10(1).zip`
* `alex_pub_partner_market_readiness_pass01_verified(1)(1).zip`
* all supplied manifests, preflight output, test output, hashes, reports, governance files, and standalone tests

Also inspect nested archives inside these packages when relevant. Do not treat a nested zip as proof of integration; inspect its contents and determine whether its code is actually active.

---

# NON-NEGOTIABLE ARCHITECTURAL RULES

## 1. Preserve Roles and Contracts

Do not replace one subsystem with another merely because their names sound similar.

Use the following department and capability model:

* **PubPartner:** persistent layer between the user and interchangeable LLM providers
* **Alex department:** relationship continuity, emotional interpretation, personalization, social intelligence, care and mediation
* **Jeremy department:** memory, context, continuity, commitments, delivery tracking, and decision routing
* **Pub Manager:** room orchestration, authority, moderation routing, emergency decisions, and human review
* **Provider layer:** interchangeable model providers such as OpenAI, Ollama, deterministic/mock, or future providers
* **e-PETE:** runtime health and subsystem coordination
* **Bubble Stack:** physics-informed kinetic and spatial consequence interpretation
* **Room Conductor:** internal room/session coordination
* **Governance Engine:** execution of bans, freezes, mutes, consent, entry control, and audit records
* **Studio systems:** camera, recording, avatar, voxel renderer, choreography, and performance infrastructure

Names and personas are secondary. Capability contracts and runtime behavior are primary.

## 2. Search by Function, Not Only Filename

For every required capability:

* search exact filenames
* search aliases and older names
* inspect imports
* inspect classes and functions
* inspect tests
* inspect route registration
* inspect compiled-cache clues where useful
* inspect donor packages
* compare function signatures and behavioral contracts

A missing filename does not prove a missing implementation.

A matching filename does not prove the correct implementation.

## 3. Do Not Blindly Merge

Do not combine files simply because each comes from a newer package.

For every conflicting implementation, record:

* source package
* relative path
* file hash
* modification metadata, treated as low-trust
* imports and dependents
* public interfaces
* tests covering it
* known regressions
* unique capabilities
* integration status
* recommended canonical choice
* reason for the choice

## 4. No Destructive Cleanup

Do not delete source material.

Noncanonical or superseded files must be:

* retained outside the runtime tree
* moved into a clearly labeled archive/reference directory, or
* excluded from the final canonical runtime package while documented in the provenance report

Do not alter protected authored content under `source_locked/`.

## 5. Provider Independence

The model provider must remain interchangeable.

Alex, Jeremy, Pub Manager, memory, governance, and friend identity must not depend on a specific provider’s personality or proprietary response format.

Provider-specific flavor must be normalized before the final friend-identity layer is applied.

## 6. Pub Manager Authority Policy

Preserve this authority distinction:

### Automatic reversible emergency actions may include:

* temporary mute
* temporary freeze
* hold action
* stop recording
* emergency save
* reduce performance load
* isolate or pause a failing subsystem
* select a safe recovery path

Automatic actions must be:

* reversible
* time-bounded where appropriate
* based on explicit evidence
* logged
* visible to the human
* reviewable and reversible by the human

### Human approval is required for irreversible or punitive actions, including:

* permanent ban
* permanent removal
* permanent trust revocation
* deletion of memory or user data
* destructive permission changes
* permanent exclusion from the platform

Do not permit an AI provider, Alex, Jeremy, or Pub Manager to authorize its own irreversible action.

## 7. Audit Failure Must Be Visible

Any authority action requiring black-box recording must fail closed or be clearly marked non-executable when the audit record cannot be created.

Never silently execute an authority action without its required audit record.

---

# PHASE 1 — PRESERVATION AND INVENTORY

1. Record starting disk space.
2. Record every supplied file and archive.
3. Calculate SHA-256 hashes.
4. Extract each package into its own uniquely named read-only intake directory.
5. Never extract multiple packages over one another.
6. Recursively inventory nested archives.
7. Produce:

   * `SOURCE_PACKAGE_INVENTORY.csv`
   * `SOURCE_PACKAGE_HASHES.sha256`
   * `EXTRACTION_MAP.md`
   * `NESTED_ARCHIVE_INVENTORY.csv`

For every package, identify:

* likely project root
* apparent entrypoint
* test directories
* documentation
* manifests
* generated caches
* binaries
* authored/protected material
* suspicious duplicate trees

---

# PHASE 2 — FILE AND CAPABILITY MAP

Create two separate maps.

## File Canonicality Map

Produce `FILE_CANONICALITY_TABLE.csv` and `.md` containing:

* relative path
* source package
* SHA-256
* file size
* classification
* active/imported status
* duplicate group
* canonical candidate
* reason
* risk
* action taken

Required classifications include:

* `CANONICAL_ACTIVE`
* `CANONICAL_SUPPORT`
* `CANONICAL_TEST`
* `CANONICAL_DOCUMENTATION`
* `CANONICAL_UI_ASSET`
* `CANONICAL_RUNTIME_BINARY`
* `CANONICAL_SUPPORT_NOT_BOOTED`
* `NONCANONICAL_REFERENCE`
* `HISTORICAL_DOCUMENTATION`
* `GENERATED_CACHE`
* `LOCAL_CONFIGURATION`
* `PROTECTED_AUTHORED_CONTENT`
* `UNKNOWN_REQUIRES_REVIEW`

## Capability Contract Map

Produce `CAPABILITY_CONTRACT_MAP.md`.

At minimum, trace:

* production launcher
* FastAPI entrypoint
* authentication
* first-run owner creation
* PubPartner chat flow
* provider selection
* provider neutralization
* engagement/session primer
* friend identity application
* Alex analysis
* Alex personalization
* Jeremy context retrieval
* Jeremy continuity tracking
* Alex/Jeremy bridge
* Pub Manager request creation
* Pub Manager deterministic policy
* human decision route
* authority packet validation
* Governance execution
* black-box audit recording
* memory persistence
* relationship persistence
* Room Conductor
* Bubble Stack
* e-PETE
* camera
* recording
* avatar
* voxel renderer
* choreography
* UI
* Windows launcher
* preflight
* health reporting

For each capability, document:

* canonical implementation
* donor implementations
* active entrypoint
* callers
* dependencies
* tests
* current state: working, partial, optional, blocked, stale, or unverified

---

# PHASE 3 — ENTRYPOINT AND IMPORT-GRAPH TRACING

Trace the actual production runtime beginning with every candidate launcher and entrypoint.

Determine:

* which launcher is canonical
* which Python file the launcher starts
* which FastAPI application is served
* which routers are mounted
* which globals and application-state objects are initialized
* which systems are merely present but never instantiated
* which systems are instantiated but unreachable
* which systems fail closed
* which optional systems degrade gracefully
* which stale entrypoints could mislead future workers

Produce:

* `RUNTIME_IMPORT_GRAPH.md`
* `ROUTE_REGISTRATION_TABLE.csv`
* `BOOT_SEQUENCE.md`
* `UNREACHABLE_OR_UNWIRED_COMPONENTS.md`

Do not label a component “integrated” merely because the file imports.

---

# PHASE 4 — CONFLICT RECONCILIATION

For each duplicate or conflicting subsystem:

1. Compare implementations directly.
2. Run their relevant tests.
3. Identify unique useful behavior.
4. Select the strongest compatible canonical implementation.
5. Port only missing, proven capabilities when safe.
6. Preserve the receiving subsystem’s role and public contract.
7. Add regression tests before or alongside integration.
8. Record the exact provenance of every accepted change.

Pay particular attention to:

* Pub Manager versions
* governance versions
* Alex/Jeremy bridge versions
* provider-neutralization passes
* Alex Prime and PubPartner personality layers
* relationship and memory persistence
* authentication changes
* launcher changes
* `main.py` variants
* Bubble Stack bridges and routes
* e-PETE/runtime wiring
* duplicated test suites
* stale generated handoff code

Produce `CONFLICT_RESOLUTION_LEDGER.md`.

Every resolution entry must include:

* conflict ID
* files compared
* canonical winner
* useful donor behavior retained
* behavior rejected
* tests run
* remaining uncertainty

---

# PHASE 5 — REPAIR AND INTEGRATION

Create a clean working tree from the selected canonical base.

Repairs must be narrowly scoped and evidence-driven.

Required outcomes:

* one canonical production launcher
* one canonical production application entrypoint
* one Pub Manager authority path
* one Governance execution path
* one Alex/Jeremy bridge contract
* one provider-neutralization path
* one friend-identity application path
* no duplicate active memory systems serving the same contract
* no duplicate active relationship stores
* no stale router mounted alongside the canonical router
* no client-supplied trusted authority packets
* no self-approval path for irreversible actions
* no hidden fallback that claims full functionality while bypassing the intended subsystem

Retain optional integrations honestly. An unavailable optional provider or renderer must report degraded/optional status rather than falsely reporting complete activation.

---

# PHASE 6 — TESTING

Run tests in layers.

## Layer A — Static and Structural

* compile all production Python files
* import all canonical modules
* scan for unresolved imports
* scan for duplicate routes
* scan for accidental wildcard CORS
* scan for hardcoded secrets
* scan for TODO, placeholder, stub, and `pass` logic
* scan for protected-content modifications
* verify launcher targets
* verify manifest completeness

## Layer B — Focused Contract Tests

Run and repair tests covering:

* Alex/Jeremy bridge
* Pub Manager
* governance
* authentication
* relationship persistence
* memory persistence
* provider neutralization
* provider interchangeability
* Bubble Stack
* Room Conductor
* e-PETE
* camera and recording regressions
* Windows launcher behavior
* first-run boot

## Layer C — Full Test Suite

Run the complete test suite.

Do not claim skipped external tests passed.

Separate results into:

* passed
* failed
* skipped because optional service unavailable
* blocked by environment
* not collected
* flaky or nondeterministic

## Layer D — End-to-End Runtime

Boot the canonical application and exercise real HTTP routes.

At minimum test:

* preflight
* first-run authentication
* login
* protected route rejection
* health
* PubPartner UI load
* provider selection
* deterministic/mock conversation
* Alex/Jeremy processing
* Pub Manager reversible automatic action
* human approval path
* irreversible action held for human review
* governance execution
* audit-log creation
* relationship persistence across restart
* memory persistence across restart
* clean shutdown

Produce raw output files. Do not replace raw test output with prose summaries.

---

# PHASE 7 — ADVERSARIAL AUTHORITY TESTING

Attempt to defeat the governance design.

Test at minimum:

* client supplies `approved: true`
* provider text claims an action is approved
* Alex signal claims an action is approved
* Jeremy signal claims an action is approved
* duplicate incident requests
* replayed approval
* expired approval
* approval for one target reused for another
* approval for one action reused for another
* black-box recorder unavailable
* malformed authority packet
* low-confidence emergency
* conflicting Alex and Jeremy recommendations
* critical reversible emergency without a human present
* permanent ban requested under critical urgency
* restart during pending review
* restart during temporary containment
* tampered persistence file
* concurrent requests for the same incident

Permanent ban must not become automatically executable merely because urgency is high.

Produce `AUTHORITY_ADVERSARIAL_REPORT.md` with exact inputs and observed outputs.

---

# PHASE 8 — WINDOWS PRODUCT VERIFICATION

The intended user environment is Windows 10.

Verify:

* launcher uses the project virtual environment
* launcher does not depend on Bash
* required commands can be run from PowerShell
* paths with spaces work
* first-run configuration is understandable
* persistent secret is created safely
* browser opens to the correct local URL
* repeated launch does not create multiple hidden server processes
* shutdown stops processes cleanly
* logs are discoverable
* failure messages identify corrective actions
* disk use is bounded and documented

Do not modify registry, services, PATH, firewall, drivers, partitions, BIOS, or other system-core settings.

Produce:

* `WINDOWS_LAUNCH_VERIFICATION.md`
* `POWERSHELL_QUICK_START.txt`
* `PROCESS_AND_DISK_ACCOUNTING.md`

---

# PHASE 9 — FINAL RELEASE PACKAGE

Create a release directory containing only:

* canonical runtime code
* required assets
* required configuration templates
* canonical tests
* launchers
* preflight tools
* current documentation
* provenance and accountability records

Do not include:

* `.pytest_cache`
* `__pycache__`
* temporary extraction trees
* duplicate source packages
* unnecessary old releases
* secrets
* local user data
* misleading historical reports presented as current truth

Historical material may be placed in a separately labeled reference archive, not inside the production runtime tree.

Create:

* final canonical zip
* SHA-256 file
* complete manifest with hashes
* top-level `README_START_HERE.md`
* `CURRENT_RUNTIME_TRUTH.md`
* `KNOWN_LIMITATIONS.md`
* `PROVENANCE_LEDGER.md`
* `FILE_CHANGE_SUMMARY.md`
* `TEST_RESULTS_SUMMARY.md`
* all raw test outputs
* rollback copy of the original selected base

---

# REQUIRED FINAL ACCOUNTABILITY

Before declaring completion, answer all of these plainly:

1. Where did you cut corners?
2. What did you leave out?
3. Which claims were directly verified?
4. Which claims rely on previous handoffs?
5. Which tests were skipped or blocked?
6. Which capabilities are present but not wired?
7. Which capabilities are wired but degraded?
8. What could you have misinterpreted?
9. Did you edit any protected authored content?
10. Is the package complete enough for another engineer to continue without the original chat?

Do not call the project market-ready unless the evidence supports that claim.

---

# COMPLETION STANDARD

This assignment is not complete when an audit document exists.

It is complete only when there is:

* a reconciled canonical working tree
* a bootable packaged release
* a verified manifest
* honest test evidence
* documented unresolved limitations
* traceable provenance for all accepted implementations
* no unexplained duplicate authority, provider, memory, relationship, or entrypoint paths

Do the work continuously and methodically. Do not stop after finding the first working build. Do not substitute confidence for evidence.
