# PubPartner Prebeta 9 Character Audit — Start Here

**Version:** `0.1.0-prebeta.9+character-audit.20260728`

**Date:** 2026-07-28
**Status:** verified private prelaunch candidate; **not claimed market-ready**

## What This Package Is

This is the reconciled PubPartner/PubCast candidate plus the first functional
PubPartner vessel foundation. The vessel is a single-file, model-independent
authority for Alex's identity, relationships, evidence-governed memory, scoped
context, and embedded asset bindings. Read `docs/PUBPARTNER_VESSEL_V1.md` for
the implemented format, runtime order, privacy boundary, CLI, and validation.

The most important repair is architectural: `run_pubpartner.py` starts `pubpartner_app:app`, and that default app now boots **Alex + Jeremy + Pub Manager + Governance together**. Before this reconciliation, those control-plane systems existed in the package but were only mounted by the heavy `main.py` PubCast application.

## Canonical Launch

Windows:

```powershell
.\run_pubpartner_windows.ps1
```

or double-click:

```text
RUN_PUBPARTNER_WINDOWS.bat
```

Portable command:

```powershell
python run_pubpartner.py
```

Diagnostics only:

```powershell
python run_pubpartner.py --preflight
```

The first launch opens local owner setup. The canonical launcher enables authenticated local-owner mode and creates a persistent local signing secret in the chosen data directory.

## Runtime Choice

- `pubpartner_app.py` — **canonical default**. Persistent friend layer, provider interchangeability, Alex/Jeremy bridge, Pub Manager, Governance, auth, relationship and source/receipt continuity. Heavy studio systems stay off.
- `main.py` — optional full PubCast/Studio host. It contains camera, recording, voxel, Bubble Stack, e-PETE, avatar, and production infrastructure. It is retained but is not the default user launcher.

## Verified Results

- Full current suite: **163 passed, 3 skipped**.
- Skips: three live-Ollama tests because no live Ollama service/model was available.
- Fresh preflight: **Overall OK**.
- Local friend-loop smoke: exact source restored and receipt chain verified.
- Restart probe: owner auth, signing secret, turn history, and exact source survived a real stop/restart.
- Control-plane probe: critical permanent ban stayed `human_required`; bounded critical freeze auto-approved, executed once, and replay was rejected with HTTP 403.
- Dynamic canonical route inventory: 90 routes; no duplicate method/path pairs.

Raw outputs are under `docs/reconciliation/raw_test_output/`.

## Read Next

1. `CURRENT_RUNTIME_TRUTH.md`
2. `CAPABILITY_CONTRACT_MAP.md`
3. `KNOWN_LIMITATIONS.md`
4. `TEST_RESULTS_SUMMARY.md`
5. `FINAL_ACCOUNTABILITY.md`
6. `docs/reconciliation/source_audit/`

## Important Boundary

Permanent bans, kicks, destructive deletion, and other irreversible or punitive actions are not automatically authorized. Pub Manager may automatically permit only policy-eligible, reversible, evidence-backed containment for bounded periods. Authority grants are server-loaded, target/action/session bound, auditable, expiring, and one-use.

## Protected Material

No authored material under any Alex Prime `source_locked/` tree was edited. Alex Prime and other donor implementations were evaluated separately and preserved as reference material rather than blindly merging duplicate memory/identity systems into the active runtime.
