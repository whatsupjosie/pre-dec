# Conflict Resolution Ledger

## CR-001 — Canonical Base

**Compared:** RC2 Pub Manager, July 12 RC2 handoff, RC6 Provider Neutralizer.  
**Winner:** RC6 Provider Neutralizer.  
**Why:** Fresh extraction reproduced 126 passed / 3 skipped before reconciliation; it retained the July 12 authentication and continuity work while adding provider-neutralization and multi-provider modules.  
**Rejected behavior:** Choosing by filename/date alone.

## CR-002 — Default Entrypoint vs. Full PubCast Entrypoint

**Conflict:** `run_pubpartner.py` launched `pubpartner_app.py`, while Pub Manager/Governance/Alex routes were only fully mounted in `main.py`.  
**Resolution:** Keep the lightweight launcher, but mount the non-negotiable control plane in `pubpartner_app.py`. Heavy studio systems remain opt-in through `main.py`.  
**Proof:** real-process control-plane probe and new wiring tests.

## CR-003 — Automatic Authority

**Conflict:** older loose test line denied urgent reversible actions without learned history; current Pub Manager uses deterministic bounded emergency policy.  
**Resolution:** preserve deterministic reversible containment with evidence, expiry, audit and one-use execution; keep permanent/punitive actions human-only.  
**Proof:** decision-engine, adversarial, fail-closed and live execution tests.

## CR-004 — Alex Prime vs. Active Alex/PubPartner Path

**Conflict:** Alex Prime contains richer overlapping continuity, drift and identity systems.  
**Resolution:** do not activate a second competing friend/memory path. Preserve Alex Prime untouched as a validated donor/reference package and map future capabilities by contract.  
**Proof:** Alex Prime independently passed 55 tests; no `source_locked/` authored material edited.

## CR-005 — Jeremy Donor

**Conflict:** Jeremy Hardened Beta appeared more specialized than the active bridge.  
**Resolution:** reject as canonical because modern pytest required compatibility mode and one actual mode-transition behavior test still failed. Preserve as reference.  
**Proof:** 21 passed, 1 failed with exact failure output retained.

## CR-006 — Bubble/Studio Systems

**Conflict:** overlapping PubCast and PubPartner packages could imply copied or stale studio code.  
**Resolution:** retain implementations that hash-match the verified/finalized PubCast line for Bubble Stack, Room Conductor, voxel bridge, camera, recording, studio control and renderer. Do not start them in the lightweight app.  
**Proof:** cross-build SHA-256 reconciliation table and regressions.

## CR-007 — Release Data

**Conflict:** candidate tree contained generated databases, keys, named profile data, logs and bridge commands after tests.  
**Resolution:** repair the release sanitizer, add a release-hygiene test, sanitize after final validation, and verify the final manifest from the sanitized copy.  
**Rejected behavior:** shipping runtime residue because a previous manifest happened to include or ignore it.
