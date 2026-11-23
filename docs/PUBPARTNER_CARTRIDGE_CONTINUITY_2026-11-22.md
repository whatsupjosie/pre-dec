# PubPartner cartridge continuity: reconciliation and activation
**Branch:** `feat/pubpartner-cartridge-context-2026-11-22` from `whatsupjosie/pre-dec` main
**Status:** implementation written to isolated branch. Local bridge smoke test passed using a stand-in for the existing loader. Full PubPartner startup, current repository pytest, real provider and browser tests have **not** been executed in this environment.

## What was inspected
- `pubpartner/cartridge.py`: validated YAML character, voice, appearance, seed JSONL; creates/reuses `memories.db`.
- `pubpartner/memory_store.py`: existing SQLite store and offline TF-IDF + recency + importance ranking.
- `pubpartner/portable_runtime.py`: independent standalone loop that stores user turns as episodic memories; not the FCP1 app's memory admission policy.
- `modules/pubpartner_cartridges.py`: creates a cartridge and registers its friend profile; routes existed but were missing from the minimal `pubpartner_app.py`.
- `modules/pubpartner_core.py`: VerbatimVault, user-owned work notes, relationship lessons and FCP1, plus Alex vessel binding.
- `modules/pubpartner_vessel/{runtime,memory,context}.py`: Alex's evidence-backed and correction-capable vessel. This is a separate authority, not a source to flatten into generic cartridge DBs.
- `modules/alex_memory.py`: specialist Alex recall and emotional state.
- `modules/cc_memory_store.py`: Code Collector *engineering/code-session* memory, not the correct authority for a companion's personal or project memory.
- `modules/universal_memory_system.py`: per-character / room-conductor memory, separate from user-owned relationship continuity.
- `docs/PUBPARTNER_PROJECT_NOTES_2026-11-19.md`: saved notes per user/project, draft autosaves, no unreviewed draft given to the model.
- `docs/alex_eq_2026-11-10/PUBPARTNER_MEMORY_EVALUATION_2026-11-10.txt`: historical limitation that saved conversation history wasn't recalled across new sessions.

## Authority map
| State | Authority | Do not do |
| --- | --- | --- |
| Original user text | VerbatimVault | Do not summarize or overwrite the raw source. |
| Replies/receipt trail | PubPartner turn log / receipts | Do not claim all replies are sealed like user text. |
| User/project decisions | WorkNotesStore | Do not put drafts or project IP in the character cartridge. |
| User/companion relationship | RelationshipEngine / authorized vessel | Do not write other users' private data into a shared cartridge. |
| Character's authored identity/voice/seed memories | Cartridge YAML and `memories.db` | Do not substitute CC or universal scene memory as a new master. |
| Studio scene characters | UniversalMemorySystem | Do not treat it as the user's personal journal. |
| Code/engineering capture | Code Collector | Keep its context store separate. |

## Exact reversible changes
1. **`pubpartner_app.py`** mounts existing `create_pubpartner_cartridge_router(DATA_DIR)` in the local control plane, preserving authentication.
2. **`modules/pubpartner_cartridge_context.py`** checks the server-side registered friend profile and canonical cartridge folder; uses the existing `load_cartridge()` and `MemoryStore.query()` rather than inventing new store/ranking. It reads authored identity, voice and appearance, with bounded fields, and includes cartridge memories **only** for the recorded creator in a private turn.
3. **`modules/pubpartner_core.py`** incorporates the loaded cartridge into FCP1, carries the canonical character fields to providers, and merges cartridge laws into the friend profile without replacing authored friend instructions. Failures report `cartridge_context.status=error` without destroying the verbatim turn path.
4. **`tests/test_pubpartner_cartridge_context.py`** tests identity, recall, isolation, path rejection and FCP1 integration.

No databases, canonical Alex vessel, project notes, personal records, old cartridges, or models were migrated or replaced.

## How to activate on a local computer
Use a working copy of `whatsupjosie/pre-dec` at this branch, with its dependencies installed.

```bash
git fetch origin
git switch feat/pubpartner-cartridge-context-2026-11-22
python run_pubpartner.py --preflight
python run_pubpartner.py
```

Then open the locally served `http://127.0.0.1:8000/pubpartner`. Use the existing **File → New Cartridge** workflow. New characters are stored in `data/pubpartner/cartridges/<id>`; their friend profiles are registered alongside them.

The app is loopback-only by default and authenticated unless explicitly opted out. Do not expose the server publicly or disable authentication. A real generative response still requires a configured working model/provider; offline diagnostic/mock responses are not proof of model quality.

### Readback checks
- `GET /api/pubpartner/cartridges` works for an authenticated user.
- Select the created character and send a private turn using an appropriate working provider.
- The turn's `cartridge_context.status` should be `ok`; `fcp1.cartridge` should match the YAML.
- When the creator has stored eligible cartridge memories, `fcp1.m` should include entries with `src=character_cartridge`. Other users or shared rooms must not receive them.
- Verify the original message restores byte-for-byte through VerbatimVault, and that restarting doesn't lose the cartridge/profile/DB.
- Run `pytest -q tests/test_pubpartner_cartridge_context.py tests/pubpartner_core/test_memory_store.py tests/test_pubpartner_cartridges.py` in an environment containing all program dependencies. The latter suite includes browser cases and may need a browser installation.

## Next merge stages, not claimed complete
1. Verify real app startup, authenticated HTTP routes, UI creation, provider turn, reload, model swap, and user isolation on the exact PR head. Run independent browser/phone acceptance.
2. Audit whether **new** cartridges should have their own evidence-backed, per-user vessel memory, using the existing vessel infrastructure and authorization. The present change gives them authored character memory and separately already-existing user/work relationship memory, not Alex's full vessel automatically.
3. Reconcile portable-runtime automatic episodic capture with core's explicit lesson admission. Do **not** blindly import every old chat as an accepted biographical memory.
4. Extend cross-session conversation retrieval by user/project/friend from existing original logs and work notes; add cited provenance, correction, superseding, deletion controls and token budgeting.
5. Independently check migration/backups/rollback, path traversal, cross-account permissions, model fallback, corruption, file locks and Windows/offline operation before offering a merge to main.

## Rollback
Don't merge until accepted. Delete/close the proposed branch if rejected; current main stays unchanged. If merged later, revert only the commits in this branch, preserving all existing databases and user-generated cartridge folders.
