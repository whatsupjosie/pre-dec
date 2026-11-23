# Rediscovery: early-repo finds brought into pre-dec (2026-11-23)

Branch: claude/rediscovery-early-repos-2026-11-23 (made from claude/bring-in-donor-finds-2026-11-23 at c812e22; main untouched).
Folder: recovery/2026-11-23/rediscovery/
Manifest: recovery/2026-11-23/rediscovery/MANIFEST_SHA256.json (681 files committed, SHA-256 each, source repo, commit and zip chain for each; every hash re-checked after writing, 0 mismatches).

## Reason
Josie asked to bring all the early-repo finds into pre-dec under a folder labelled rediscovery. Everything here is an additive donor copy. Nothing in an active module, route, launcher or test path was changed, and nothing was wired in. Per CLAUDE.md, moving any piece out of recovery/ needs her approval, targeted tests and regression checks.

## What was copied (folder, source, what it is)
- editor_core: The-Counter-and-2i, editor_core.zip. Offline spelling, grammar, thesaurus, rhyme and meter tools and a model-backed plot-hole checker, with tests.
- intercom_and_camera_bus: NowCurtsey-Build, pubcast_run_bundle.zip (intercom.py, virtual_camera_bus.py, camera_engine_bridge.py, studio_camera_preflight.py) plus loose vault_store.py, unified_bridge.py, PUBCAST_CHAPTER_RULE_REVIEW.md and two camera notes.
- rearview_foresight_memory_layer: Storage, pubcast_utilities_systems_part3.zip > RearViewForesight_MemoryLayer_v2__2_.zip. Chat-session extractor, browser extension scraper, installer, thinking_context package.
- motion_capture_v7: Storage, part3 zip > Motion_capture_system_and_pubcast_7.zip, with the nested zip also expanded for reading.
- humphrey_complete, navigation_and_humphrey_setup, camera_files, pete_purfluous_nudge_early, animation_skeleton_rust_and_hologram: Storage part3 and part4 zips (Rust animation and avatar-fitting files, hologram avatar export, Humphrey navigation and setup, camera files, early pete.py, purfluous.py, nudge patch).
- thursday_animation: Thursday- (animation guide, presets in JS and Python, behavior-animation, motion-runtime and GLB motion-consumer bundles).
- bone_converter_and_fpr: Pubcast-AI-3-20-26-Agent-Pass, pubcast_2026-03-21_final_code.zip (modules/bone_converter.py and tools/fpr, the Functional Purpose Report generator, schema and docs).
- blender_characters: Pucast-Tuesday, assets/avatar/cast (Sir Purfluous and RePete build scripts, handoffs and GLBs; Pete avatar script).
- security_plan_and_vault: Thursday-, pubcast-vault-final-hardened.zip (security architecture plan, Iteration Wallet and Oubliette phases, hardening, TLS setup, audio chimes).
- history_docs: Gemini avatar-creator chat (10-11-25), the PubCast + PubPartner + 2i master document, Storage handoffs, Bubble Stack dossier and reconciliation, 2i writers room versions v2 to v12 with their handoffs, collaborative prototype, belle epoque mockup.
- pubpartner_horizon_prebeta12: The-Counter-and-2i, PubPartner_Horizon_v0.1.0-prebeta.12.zip (390 files).
- pub_partner_base_horizon_repo: the whole Pub-Partner-Base-Horizon repo (25 files), including LETTER_TO_NEXT_AI.md.

## Deliberately NOT copied (and why)
- Cobbley_Case_Files_and_Handoff_8-8-26 (1).zip (The-Counter-and-2i): her legal case files. Private, and pre-dec is public.
- curtsey_context (WHO_I_AM, PUBCAST_VISION, SONGS_AND_NOTES): personal files, in Pubcast-Phase-2- and in Storage part4. Not read, not copied. Her call.
- ChatGPT Image Aug 12, 2026 PNG (2.5 MB), and the 20 to 23 MB whole-PubCast snapshot zips (Just-The-Pubcast-main.zip, Agent-Pass assets and merged zips): too big to be donors, and they are whole old builds.
- Ten more runtime-data files (sample user and document records, logs, a test recording) that pre-dec's own .gitignore kept out of the commit: six JSON files under humphrey_complete/.../src/data, and four files under data/logs and data/recordings in the Horizon prebeta.12 tree. Also listed in the manifest under not_copied.
- Seven runtime-data or secret-shaped files inside the Horizon prebeta.12 zip, caught by the copy script and left out: data/users.db, data/vault/vault.db, data/governance/governance.db, data/system/system_memory.db, data/byok/secure/master.key, and two .gitkeep placeholders in secure folders. Listed in the manifest under not_copied.
- Python bytecode, caches, debug build output.

## Checks run (all local, none on GitHub)
- Secret and personal-data scan of every copied file: no real keys, tokens, addresses, phone numbers or emails found. Matches were placeholders (sk-ant-... in form hints and an .env example) and false positives (the word eviction).
- editor_core tests: 24 passed (needed pyspellchecker, nltk, cmudict, pydantic and the WordNet word list installed in the sandbox; not part of this repo and nothing auto-installs).
- Pub-Partner-Base-Horizon tests: 76 passed, matching its own letter.
- All 316 Python files parse as Python 3 except one: motion_capture_v7/.../core/main_v7.py line 33 reads "from dotenv import load_load_dotenv()", which is a syntax error in the donor itself. Left as found.
- intercom.py, virtual_camera_bus.py and camera_engine_bridge.py import cleanly on their own.
- Of the files copied, 149 of the original 691 are byte-identical to files already in pre-dec (flagged in the manifest with identical_to_existing_pre_dec_file). Notably, the memory layer's thinking_context package (mount, memory, sqlite_backend, protocols, circuit_breaker, nudge_queue) is already in pre-dec, and thinking_context/jeremy.py differs by one comment line. So pre-dec already has the server half of that layer. The parts pre-dec lacks are the conversation extractor, the browser-extension scraper and session endpoints, and install.py.

## Untested
- The Rearview Foresight extractor, extension and installer (no tests shipped, nothing run).
- Everything in thursday_animation, humphrey, navigation, mocap, hologram, Rust files, Blender scripts, GLBs, the vault package, FPR tools, bone_converter and the Horizon prebeta.12 tree beyond syntax parsing.
- Behavior of intercom beyond import. Not mounted, no route, no UI.
- Whether any of this conflicts with pre-dec's own mocap_integration.py, mocap_precision.py, bubble_stack.py, iteration wallet and Oubliette files. Not compared yet beyond byte-identity.

## Notes for Josie
- Some source files keep names that include the word final (for example 8-10 HANDOFF_FINAL.md, PUBCAST_HUMPHREY_FINAL, pubcast-vault-final-hardened). They are verbatim donor names kept so the provenance and internal references still match. No new file or folder created here uses that word.
- 73 files in pubpartner_horizon_prebeta12 carry the former name "Joshua Cobbley" in their copyright headers. 100 files already in pre-dec carry it too, so this is not a new exposure, but pre-dec is public. Nothing was edited. Her call.

## Next step
Decide which piece moves first out of recovery/. Suggested order: editor_core (tests pass, self-contained), then the intercom, then the extractor and extension half of the memory layer.
