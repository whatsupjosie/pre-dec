# Big zip harvest — 2026-11-22

Written so a reader with no other context can pick this up. Verified means I ran
it or read it; anything not verified says so.

## What Josie asked

> "I want you to g ointo my googel drive. there is a folder there called big zip.
> I want you to go thrugh it and find any other bits of good code tha we can use
> here. Nothing in particular HAS to be used unless its for a system of ours tha
> is missing or incomplete, but if its better than what we have. then lets gget
> it and ipliment it"

"Here" is pre-dec (`whatsupjosie/pre-dec`).

## Where big zip is and what is in it

Drive folder **big zip**, id `12VLg8U4Yb9Gl-jVbR_OjYrZIfzB009Ww`, account
whatsupjosie. Contents, all verified by listing:

| Item | What it is |
|---|---|
| `PUBCAST_FIRST_PRIME_UPLOAD_PACKAGE_20260618_063754.zip` (69,099,094 bytes) | Outer zip holding `PUBCAST_FIRST_PRIME_CANON_20260618_062816.zip` and its SHA-256 note. The canon zip is the `codex_construction_pubcast_20260614` project, 1,530 entries. |
| `codex_construction_pubcast_20260614/` | An extracted copy of that same project. |
| `pubcast_complete_debugged_2026-05-08/` | An older May copy of the codebase (429 source files). |
| `visual_patch_kit_for_big_zip_20260611_…/` | The Visual Patch Kit copy bundle: runtime files, docs, `voxel_engine_reference/` (copies of big zip files), and `reference_packages/handoff_package_visual_patch_adaptive_props_20260610_210745.zip`. |
| `response_composer.py`, `conversation_state.py`, `meaning_maker.py` (loose) | Already in pre-dec at `modules/wired/`. Identical except pre-dec's use package-relative imports, which is the fixed form. |

**How the 69MB zip was read.** The Drive connector refuses files over 10MB. The
first commit of `whatsupjosie/The-Prime` ("Add PubCast First Prime canon
package", 2026-06-18) is that exact zip, same byte count, so it was taken from
GitHub. The inner zip's SHA-256 matched the note written on Josie's machine on
18 June: `275115011b49…c45720`. Nothing in it was run.

## How it was compared

Every source file (`.py .js .jsx .ts .html .css .rs .toml .mjs`; not `rubish/`,
Rust `target/`, or caches) was compared by content against every blob on every
branch of pre-dec, so a renamed or moved copy still counts as already present.

June snapshot, 446 source files:
- 228 identical to something in pre-dec;
- 159 at the same path but different, 8 under another path but different;
- 51 not in pre-dec in any form. 49 of those are Codex's own `pre_…` backups
  taken just before it edited a file in June, which are older by definition.

For the 167 that differ, every function, class, method and route the June copy
defines was checked against every pre-dec copy. 152 are fully covered. The 15
that are not were each read by hand:

| File | Verdict |
|---|---|
| `llm_framework.py` keyed adapters lost `stream` | **Pre-dec is better.** June swapped the process-wide API key environment variable per request, so two users streaming at once could swap keys. Pre-dec gives each adapter its own key and inherits streaming. |
| `auth.py` lost three `_fallback_*` functions | **Pre-dec is better.** It made the fallback the main path and added empty-password rejection, canonical token checks and a size cap. |
| `tts.js` lost `speakServer` | Not lost. Server speech is on by default through another path; the route is in `main.py`. |
| `stage.html` lost `mirrorFrame`, `buildCompositeCanvas` | June's were placeholders: a canvas painted "PUBCAST AI — LIVE" and an empty canvas. |
| `cameras_advanced.py` lost `_generate_test_frame` | A stub: June's capture loop filled the buffer with fake frames. |
| `bar.html` lost the jukebox | Dead in June too: no server, then or now, handles `jukebox_action`. |
| `dressing.html` lost room codes | **Real loss — restored.** See below. |
| `purfluous.py` absent | Renamed and grown into `modules/room_conductor.py`; every function carried over. |
| `version_comparison.html` absent | Not code. It is a side-by-side of two drafts of Josie's Hawkes grievance. Deliberately not brought into pre-dec. |
| `analytics.html`, `gallery.html`, `pub_partner_chat.html`, test files | Rewritten under new names, or Purfluous tests renamed with the module. |

The May copy: 429 files; 3 names pre-dec lacks, all also in June and covered
above. 19 files had no same-name, same-size twin; all 19 were downloaded and
checked the same way. Nothing lost.

One mistake of mine, caught and corrected: the first pass could not parse files
starting with a byte-order mark, which would have counted 15 June files as fully
covered without reading them. Fixed and re-run; the result was unchanged.

## What was taken

### 1. The runtime spine: two June spines joined into one

Branch **`claude/spine-consolidation-2026-11-22`**, from
`origin/codex/studio-integration` (Codex's branch, not main — see "Bases" below).

In June two runtime spines were built in parallel from the same brief and never
joined:
- the **minimal** one (from `codex_construction`, 15 June) shipped in pre-dec.
  It alone has `RuntimeState`, `replication.py` and the camera, director and pub
  stations;
- the **rich** one (spine work folder, 10 June) has the Visual Patch Kit,
  interaction fitting, motion retargeting and feedback, animation runtime, mocap
  diagnostics, skeleton binding, and a 64-test suite. It came back whole from the
  handoff package zip above.

On 2026-11-21 Codex started bringing the rich one over ("Wire recovered Visual
Patch Kit into the PubWorld stage") and stopped partway. It kept the minimal
event bus and removed `FrozenDict` from the kit files to fit. Every Codex edit
to the kit was checked; all were that removal.

The merge keeps everything from both. Decisions where they disagreed:
- **Event bus**: the rich bus. It fixes a real bug on main: one failing
  subscriber stopped every later subscriber and raised into the emitter. Events
  are now immutable all the way down. From the minimal bus: a non-callable handler
  is refused at subscribe time, and the last unsubscribe forgets the event type.
  `emit_async` runs plain handlers inline on the caller's thread; the rich bus ran
  them on worker threads with no lock anywhere in the spine.
- **Animation authority**: rich spine's named layers, minimal spine's per-bone
  resolution, so an overlay on the head no longer freezes a walking performer's
  legs. Ties break by registration order, not clock time.
- **Poses** are flat bone maps; the animation name lives on the performer.
- **Registry**: rich, with `sitting` and `falling` restored.
- **Stations**: every station event carries `station_id` and `station_type`.

Also on that branch:
- `modules/avatar_assets.py`: `AvatarManifest.pack_by_id()`. One June test needs
  it. The improved `avatar_assets.py` that test was written against is not in
  Drive; every copy there (22) was checked.
- `tests/test_runtime_spine.py` — **Josie's existing test, three assertions
  changed.** `pose["bones"]["head"]` → `pose["head"]` (twice) and
  `skeleton_pose["animation"]` → `current_animation`. They check the same things
  in the canonical pose shape. Only that test ever used the old shape.
- `tests/test_runtime_spine_consolidation.py`: 18 tests for the decisions above.
  Each was confirmed to fail when the code it replaces was put back.
- `pytest.ini`: `runtime/spine/tests` added to `testpaths`, so the June suite runs
  on every plain `python -m pytest`. Collected count went from 2,885 to 2,949.
- `runtime/spine/README.md`: the June README with a consolidation section.

Verified: June suite 64/64; old spine test 4/4; consolidation 18/18; 96 spine and
kit tests together; 491 tests in the 28 files that touch the spine or kit, with
the one failure pre-existing on Codex's branch and on main (see below).
Full suite (2,927 collected less the studio file `test_production25d_browser.py`,
run separately): 2,694 ran before a Chromium hang forced a clean interrupt.
Of those, 43 failed or errored. Every one was rerun:
- 36 browser tests fail the same way when run alone, and fail identically on
  Codex's untouched branch: 19 failures, 17 errors, no test differing.
  Causes seen: the Primp mirror tests need the `pytest-playwright` plugin's
  `page` fixture, not installed in this sandbox; the 2i tests time out clicking
  `#lockAllBtn` on Codex's branch (they pass on main-based 2i); the rest time out
  under software rendering on two cores.
- `test_avatar_imports` and `test_foresight_reach_runtime` fail on Codex's
  untouched branch too. `test_frontend_contract_compat` is the 114/125 broken
  references item below.
- `test_alex_routes_bridge` passes alone on both branches; in the full run it
  was a casualty of the data-folder pollution below. `test_bella_faux_pas_progress`
  passed on mine and failed on Codex's on rerun, so it is flaky.
The 252 tests the interrupted run never reached: the 64 June spine tests were
already green. The other 188, less the crash test below, were run as a batch:
184 passed, 3 failed. `test_writers_room_real_http::test_manuscript_survives_real_http_process_restart`
fails on Codex's untouched branch too. `test_studio_slate::test_live_voice_only_verified_director_can_transmit`
passes alone. `test_world_walk_host_integration::test_bella_faux_pas_studio_opens_from_the_foresight_counter_in_the_dressing_room`
passes 5 of 5 alone on both branches; run directly after the slate test it fails
3 of 3 on Codex's untouched branch and 2 of 3 on mine. Test ordering, pre-existing.

**Conclusion: no failure anywhere in the suite traces to this branch.**
The lock branch was not given its own full run; it was checked with the 25 test
files that mention the dressing room (failures there also fail on main, or were
the data-folder pollution) and with the broken-references check.

The hang: `test_studio25d_capture_browser.py::test_full_browser_process_crash_preserves_take_in_reopened_profile`
deliberately crashes Chromium, then spins forever in its `finally` closing a dead
context; pytest-timeout fires once per test and had already fired. Not run again.

### 2. The dressing room's room-code lock

Branch **`claude/dressing-room-lock-2026-11-22`**, from `origin/main`.

The server side has worked since June (`/api/dressing-room/security/status`,
`/code`, `/enter`). When `dressing.html` was rebuilt the page stopped calling it,
so the lock had no controls anywhere. The June card is back on the current page,
between Avatar Presets and File Uploads, June's wording unchanged; script in
`static/dressing_room_lock.js`. Changes from June: identity follows the rest of
PubCast (signed in, `reach_auth.js` and the token decide; signed out with sign-in
off, `pubcast.clientId` as world chat uses — not June's `pubcastHostId`);
malformed codes refused in the page with the server's own message; the success
message no longer vanishes; a lockout says when it ends; server text only ever as
text.

Verified: `tests/test_dressing_room_lock_browser.py`, 9 tests, real server with
sign-in enforced and a second with it off, in Chromium. Each June regression was
put back in turn and caught. The page adds no broken API references (114 on main,
114 on the branch).

## Bases, and why

- The spine branch sits on **Codex's** `codex/studio-integration`, because that is
  where the kit lives and is wired into the stage. Building on main would have
  meant porting the kit a second time. It lands only if Codex's branch does.
- The lock branch sits on **main**; Codex's branch does not touch the dressing room.
- My 2i branch, `claude/2i-wordpad-parity-2026-11-21`, is untouched by this.

Nothing was pushed. Nothing on main changed. Nothing was deleted from any repo.

## Found, not fixed — Josie's decision

1. **The-Prime is public and contains two things that should not be.** Inside the
   zip inside its first commit: `data/byok/secure/master.key` (44 bytes, the BYOK
   encryption key) and `modules/wired/version_comparison.html` (grievance drafts,
   sections X–XII). No provider API keys were found anywhere in it (nine key
   patterns checked). The master key matters only if the same key still encrypts
   real keys on the laptop; it is not in pre-dec. The Alex files in that snapshot
   are smoke tests only. Options: make The-Prime private; or rewrite its history to
   drop that commit; and either way rotate the BYOK master key if it is still in use.
2. **Sign-in-off redirect loop (on main).** Signed out with sign-in off, every page
   that loads `program_audio_runtime.js` (7 pages) bounces to `/login` and back
   about five times a second: `/api/program-audio/events` answers 401, and
   `reach_auth.js` sends any 401 to login. Measured: 33 navigations in 6 seconds
   on untouched main.
3. **Pages call endpoints that do not exist.** 114 static references on main have
   no route; Codex's branch adds 11 (`/api/studio/slate`, `/api/studio/emergency-save`,
   `/api/recording/start`, `/api/recording/…preflight`, `/api/conversations/…`
   exports, `/api/chat/rooms`, `/api/chat/dm/active`, `/api/studio25d/voxel-props/`).
   Some exist in modules that are never mounted; `/api/studio/slate` and
   `/api/chat/rooms` are defined nowhere. Test: `test_no_broken_static_api_refs_after_startup`.
4. **Room-code server, two inconsistencies.** Setting a new code does not ask for
   the current one (turning the lock off does), and it clears an active lockout.
   The status endpoint trusts a raw `X-Client-Id` header with no sign-in, so anyone
   can read whether a given room is locked, flagged or has an incident on file.
   It never exposes codes or hashes.
5. **A full test run writes into the repo's real `data/` folder.** Verified twice
   in worktrees (a full `python -m pytest`, and the 25 dressing-room-related files
   together; each of those files run alone wrote nothing, so it is state leaking
   between tests). Effects, checked:
   - `data/pubpartner/vessels/alex.pubpartner` (SQLite, tracked) grew from 147,456
     to 192,512 bytes. **No memory rows changed**: every table's row count is the
     same as committed. What was added is full-text search structure
     (`memory_claims_fts*`, `memory_events_fts*`, `memory_search_ready_v1`), i.e. a
     schema upgrade the app also performs when it opens a vessel.
   - New files: `byok/secure/master.key`, `pubpartner/profiles/users/josie.json` and
     `anon.json`, `production_slates.sqlite3`, `governance.db`, logs, emergency-bridge
     commands, and more; plus `assets/vod/`. The two profiles are defaults written
     only if missing (`_write_if_missing`), so they will not replace a real profile.
     Not verified: whether any test calls `save_profile` on a real id.
   - On Josie's laptop, `data/` is her live data. Until tests are isolated, do not
     run the full suite in the checkout that holds real data.
   The specific leaking test was not identified (needs a bisection of the full run).

## Open questions for Josie

- American or British spelling (still needed for the 2i spell check).
- Whether to land Codex's `codex/studio-integration`; the spine branch depends on it.
- What to do about The-Prime (item 1).
- Whether the room-code server should ask for the current code before replacing it.

## Second pass: every repo, every branch, zips opened (same day, later)

Josie's instruction, her words: "as you are checking repos make sure that you are re ggoing at least five folders deep if needed reading enough of everything so you can difinitivly identify what they are and if we have it and if it is good. and open zips to see wht is inside and check the contence".

**Status: partly done. Read the "Not done" list below before trusting this section as complete.**

### Method

- The Drive "big zip" tree also holds 22 GitHub repos Josie keeps, plus Saturday and The-Prime. They were cloned as blobless bare repos and each file's git blob SHA was compared with every blob in pre-dec's whole history, then by path and file name. Missing blobs were fetched on demand.
- **Every branch was compared, not only HEAD.** A HEAD-only comparison misses finished work on side branches (the airlock below was on one).
- Zips were opened recursively to five levels, refusing any entry whose path escapes the folder. Tools are in /home/claude/bigzip/tools on the machine that did this (unzip_all.py, hash_vs_predec.py, branch_tips.py, gap_ident.py, and earlier ones); that folder is session scratch, so if you need them again, ask for them to be rebuilt.
- For each file not in pre-dec: read its docstring and classes, and checked whether pre-dec defines the same classes under any name.

### What was ported — four more branches, each tested, none pushed

All based on pre-dec origin/main (538a40f) unless stated. Each carries its own handoff in handoffs/.

1. **claude/airlock-port-2026-11-22** (4a096e2; bundle airlock-port-2026-11-22.bundle). Josie's Airlock, found on an unmerged side branch: waiver signed by the owner and the AI, avatar check, detention, ladder warning, timeout, booted; sealed thought records opened only through an incident. Added modules/airlock.py, airlock_routes.py, 39 tests. Small edits to governance.py (an admission gate hook), governance_routes.py (409 when blocked), recording.py (privacy table: guest_foundry never, detention expected) and main.py (mounts the router). **The gate is deliberately not installed**: it needs a waiver step in waiting_room.html first; main.py has a comment saying exactly which line to add. Pre-dec's hardened black-box recorder refuses to reopen a damaged log, so the original tamper test was changed to expect refusal after damage; the handoff says so. Option for Josie: a continuation log so evidence continues after a tamper. Verified: 39 airlock tests; the neighbouring suites 279 passed, 1 skipped; three failures that are identical on baseline.
2. **claude/peq-engine-port-2026-11-22** (3d55ab2; bundle peq-engine-port-2026-11-22.bundle). The PEQ emotional engine and cre_eq (critical reasoning) from August and September builds, with their tests and docs, plus an adapter (modules/peq_orchestrator_adapter.py) that turns a PEQ reading into the signal the Alex emotional orchestrator accepts. Never marked clinical; a failed reading publishes nothing; private_, vault_, sanctuary_ and therapy_ profile keys are stripped. Verified: 100 PEQ tests; 127 with the orchestrator tests; 15 adapter tests; five adapter mutations each caught. **Not wired anywhere.** The state-to-number tables (PEQ_STATE_VALENCE, PEQ_STATE_TENSION) are my draft numbers and need Josie's design. Found, not fixed: cre_eq's alias table lacks "excited", "worried", "tired" and similar (so "excited" reads inconclusive); sarcasm detection is narrow; a claimed "99 tests" build was not found, only 85. PEQ's own priority in the orchestrator is the lowest (30), and selection is by credibility first, so it cannot override a stronger source. Pre-existing and identical on baseline: test_alex_routes_bridge::test_alex_routes_message_and_recent_memory fails when run after four other test files and passes alone.
3. **claude/pubpartner-base-horizon-link-2026-11-22** (5a983b1; bundle pubpartner-base-horizon-link-2026-11-22.bundle). Josie's design: PubPartner Base is built into PubCast and Horizon is the portable version. Adds companion_mode.py, link.py, avatar_preference.py on pre-dec's federation engine. 28 tests, eight mutations caught. Not wired. NEVER_ON_HORIZON is a constant nothing uses yet.
4. **claude/recorded-takes-2026-11-22** (fd4e300; bundle recorded-takes-2026-11-22.bundle). Recorded stage takes and the take editor from Codex commit 086420d. Full detail in handoffs/RECORDED_TAKES_PORT_2026-11-22.md. This branch sits on the spine branch, and **it also carries this handoff file**.

The earlier branches still exist: claude/2i-wordpad-parity-2026-11-21, claude/spine-consolidation-2026-11-22, claude/dressing-room-lock-2026-11-22, claude/bridge-file-heartbeat-2026-11-22, claude/recording-fidelity-lock-2026-11-22, claude/vdi-shot-smoothing-2026-11-22. Bundles are in the out folder.

**Merge note.** The recording-fidelity and VDI branches both edit the same get_status line in main.py; land one, then the other will need a hand merge.

### Identified and deliberately not ported — my judgments, Josie may overrule

- **LittleMode V2 (DREAMS):** identical to pre-dec's modules/littlemode_protocol.py once line endings are ignored. We have it.
- **DREAMS bridge_final_review:** an ancestor of pre-dec's bridge_raw and bridge_bulletproof. Superseded.
- **DREAMS distributed_engine_node_close_loop.py (1,593 lines):** 46 definitions pre-dec's 782-line modules/evo/distributed_engine.py lacks (VideoEncoder, MeshGenerator, AudioProcessor, VoxelRenderer, RustRendererBridge). **Identified by names; not read in depth. Undecided.**
- **Thursday avatar_motion_spine, avatar_motion_bridge, avatar_performance_cues (May 9):** a catalog of task and prop cues (dance, carry, push a cart, drive, operate a camera rig, etiquette). It targets an older skeleton schema and needs an adapter to pre-dec's motion stack; pre-dec has 53 conversational gestures. A content library, not code we lack. Josie's call whether she wants the cue catalog.
- **Wednesday-@Dinner runtime/*.py (22 files, the May "continuous spine job"):** an earlier, parallel design to pre-dec's runtime/spine and pub_manager_authority. Porting would create a second authority.
- **vault_store.py (NowCurtsey Hubcast-Security-Reach-10-2-26, Spark-Assignment, Pubcast-Reach):** a content-addressed, hash-chained SQLite vault whose triggers refuse UPDATE or DELETE of locked rows, with only humans able to lock. Pre-dec's vault_engine_hardened uses OS file locking instead. Weaknesses I saw: unbounded recursion in verify_chain, author_type not part of the hash, lock() logs "ok" even when no row changed. Nothing in pre-dec would call it. An option, not a gap.
- **Iteration Wallet and BlackBox** (6.0-, Iteration-Wallet, The-Prime zips): a separate product (oubliette_transaction and others). Pre-dec has docs only. Josie is deciding its place; see her memory notes on the wallet.

### Identified by docstring only — NOT assessed

NowCurtsey branch claude/nowcurtsey-repo-audit-rlsqkc: pubcast_take_manager, virtual_camera_bus, camera_engine_bridge, capture_routes, media_router, pubcast_clip_upload_route, purfluous.py (559 lines), voxel_renderer, greedy_mesh, load_theater_asset. Pubcast-AI-3-20-26-Agent-Pass branch "2nd": extractors/conversation.py (452 lines), conversation_server.py, tools/build_extension_bundle.py, export_plain_files.py (chat extraction; related to Josie's OmniVault idea). October-24 codespaces start_pubcast.py; 6.0- quarantine.py; the pub-experiment "Practice" "(2)" duplicate copies.

### Not done — be clear about this

1. The non-.py content in each repo (md, html, json, jsonl, .bbx, .cs, zips and so on) is not classified.
2. The 2,276 Drive-only items (not in any repo) are not classified.
3. Drive zips over 10 MB that the connector refuses and that were not found on GitHub are not opened: Ring Me Jeeves Parts 61126-526 PM.zip (134.94 MB); friday-Lunch (1).zip and friday-whatsupjosie-further-better.zip (about 41.5 MB each); pucastpy and pub.zip (38.2 MB); the codex_construction_pubcast_20260614 zip and its _beefed and _pubblocks variants (about 60 MB each); pubcast_complete_debugged_2026-05-08.zip (68 MB). Some are probably copies of repos already compared, but that is a guess until they are opened.
4. The Saturday mirror on GitHub has two commits; the Drive repo's commit d0f47aa is not in it. Contents not compared.
5. The NowCurtsey capture and take modules, the DREAMS engine node and the conversation extractors are identified but not read in depth.
6. The Beyond-October side branches were not all read.

## Open questions for Josie

- American or British spelling (needed for the 2i spell check).
- Whether to land Codex's codex/studio-integration; the spine branch depends on it.
- The-Prime: private, rewrite its history, rotate the BYOK key (items 1 under "Found, not fixed").
- Whether the room-code server should ask for the current code before replacing it.
- Alex crisis detection: options 1 and 2 recommended, option 3 is the real fix.
- The predictive_insight engine (files49.zip): wanted or not.
- Whether automatic camera cutting locks while recording.
- Airlock: add the waiver step to the waiting room, then install the admission gate?
- PEQ: the state-to-number tables, and where PEQ is called from.
- The cre_eq alias fix ("excited", "worried", "tired").
- Whether to wire Base and Horizon heartbeats.
- vault_store: wanted as an option? The Thursday cue catalog: wanted?
- Land recorded takes now, or after the on-set camera console (df9d30f)?

## Next step

Josie decides on The-Prime and the test-data pollution first (both touch things that are hers and private). Then the unfinished classification above continues; it needs the over-10 MB zips from her machine or from GitHub.
