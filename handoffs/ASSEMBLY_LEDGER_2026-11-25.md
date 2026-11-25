# Assembly branch: plan and ledger, 2026-11-25

The assembly branch is `claude/integrate-strongest-parts-2026-11-24` on whatsupjosie/pre-dec. It is the one branch everything converges on. Build new work on it, not on main or on older branches. Main has not moved since Nov 20 (538a40f), and it is in this branch. Curtsey merges this branch into main herself when she is ready. Nothing here was pushed to main and nothing was deleted.

The base is the studio line she chose to keep, `claude/studio-wire-avatars-2026-11-23` (45de912), which holds `claude/studio-assembly-2026-11-23`. Every other piece was merged or ported on top of it, one piece at a time, so each could be checked on its own.

Evidence words: RAN means it was run here. READ means the code was read. GUESS means inferred.

## Order it went in, and what each piece needed

1. EQ foundations (`claude/eq-foundations-2026-11-23`). Needs only the studio line.
2. The studio-line fixes (`claude/studio-line-missing-fixes-2026-11-24`): the main-debug recording, pause, PANIC, renderer and Counter fixes, ported against the studio's FFmpegCaptureEngine. Needs the studio's capture engine.
3. Cricket handoff, then the early-repo rediscovery (861 files under `recovery/`, additive).
4. Sir Purfluous and Code Collector (`claude/purfluous-more-cards-2026-11-24`, which holds the four other Purfluous branches and Code Collector). Its conflict with EQ in `companion_support/eq_disambiguation_engine.py` kept both lists of win phrases.
5. Portable 2i with the newer Airlock admission, Waiting Room and Purfluous greeting (`gpt/pubpartner-portable-2i-2026-11-22`, which holds `codex/studio-integration`). The slate's exempt paths gained the guest entry pages.
6. Beyond-October backend hardening (a594d30): Blackbox Light archive and search, backup isolation, calibration approval, cartridge memory in hosted turns, saved provider reuse. Needs EQ (its routes sit beside EQ's). Calibration was merged against 0dab95f, the commit the studio had ported it from. The two `pubpartner-*.yml` workflows were left out.
7. Beyond-October identity checkpoint (2e2c1e3). Needs the hardening merge: it runs inside the studio's witnessed dispatch and keeps the saved provider. From the unification branch (a29149d) only its authority map doc came in; its archive, backup and question changes were redone later that night on the hardening line.
8. Airlock engine (October-24, ca0e929), PEQ (Breaking-Dawn, 96cfff5), Camera Engine v2 and the full VDI engine (Drive). Added as code, not switched on. See "Waiting on Curtsey".
9. Step one's handoff and the recovered Drive files (`claude/find-what-we-made-2026-11-25`), SHA256SUMS checked OK.
10. The 2i Word workspace and offline launcher, wired into the File menu.
11. The Base-Horizon companion mode, link and avatar preference layer (Pub-Partner-Base-Horizon `claude/federation-merge`, c9d053a). Runs on pre-dec's own newer federation core.
12. The renderer's vendored Rust libraries (`claude/renderer-crates-vendored-2026-11-24`), then `bin/ws_renderer` rebuilt from them offline.
13. Step three's garbled-character fix on the control room, Airlock and stage pages.
14. The Word workspace guard (ad189776): a .2i switch is refused while a Word doc is open, and Open Word is hidden in file mode.
15. Step three's launcher fix (866b037d): the offline 2i launcher now serves the desk's typewriter and its files. Step three reports its new tests/test_2i_offline_launcher.py passes 15 (their run).
16. Step three's renderer bridge fix (f0985d6b): modules/voxel_webrtc_bridge.py now passes --port to the rebuilt ws_renderer, so an inherited PUBCAST_WS_PORT no longer wins over the bridge's own port.
17. The pause rebuild from the fixes thread (claude/studio-line-missing-fixes-2026-11-24, a4fafd1c), merged as de89f7b8. Pause now really pauses camcorder, data-only and main-camera takes: each camera's file closes on pause, the next piece starts on resume, and stop joins the pieces. RAN here, with ffmpeg and ffprobe present: in one run of test_capture_engine_safety and test_recording_modes_e2e together, 18 passed and 2 failed (the data-only and main-camera e2e tests). The two passed when run on their own, and the whole e2e file then passed 10 of 10 twice. GUESS: they are timing-sensitive under load. Not yet tried on Windows.
   The fixes thread then fixed the join with no ffprobe (4a05e402, handoff line f8270d74): the joined file takes the take's name, every piece stays beside it, and the join is reported as "unchecked". RAN here: test_capture_engine_safety, 11 passed.

## Every pre-dec branch (39 on GitHub at 04:15Z, Nov 25)

In means its tip is part of this branch (git ancestry), unless the line says otherwise.

| Date | Branch | Tip | Status | How or why |
|---|---|---|---|---|
| Nov 17 | console-touch-typewriter-keys | 3ee394a | Superseded | Its /typewriter-console route is in main.py. Nine of its sixteen files are here byte for byte; the other typewriter and console files here are later edits of the same work (Nov 18 to 20). READ |
| Nov 17 | 2i-beta-polish | df737ca | Waiting (decision 9) | Its two bug fixes are here in the studio's own form: Ctrl+Z stays inside text boxes and Caps Lock is handled (manuscriptShortcut), and Replace all spares locked lines. What is left is the Reach desk look in reach.css, writers-room and reach.js. Her call. READ |
| Nov 17 | codex/2i-typewriter-visual-2026-11-17 | 69e1550 | Waiting (decision 9) | Typewriter scene in every view, in studio-desk.js and a test. Decision 9 asks whether to keep it. |
| Nov 19 | codex/main-debug-20261119 | d3b9db8 | Superseded (ported) | Every one of its 25 commits is mapped in handoffs/STUDIO_LINE_MISSING_FIXES_2026-11-24.md: ported against the studio's capture engine, already present, or left out on purpose (IndexedDB v2; v3 is settled). |
| Nov 20 | integration/main-debug-union-trial-2026-11-20 | eacde87 | Superseded | A trial merge of main-debug into main, labeled not for main. The files it differs in (main.py, production and recording modules, control room, director switcher, Counter) were rewritten on the studio line and the main-debug changes ported. READ |
| Nov 20 | recovery/beyond-october-studio-exact-2026-11-22 | eacde87 | Superseded | Same commit as the union trial. |
| Nov 20 | integration/main-debug-land-clean-2026-11-20 | b282b2b | Superseded | Second attempt to land main-debug on main, plus a landing note. Same files as the trial. |
| Nov 20 | main | 538a40f | In | Base of the studio line. |
| Nov 20 | integration/2i-camera-repairs-2026-11-20 | 8ddfd31 | In | Through the studio line. |
| Nov 20 | integration/2i-unified-2026-11-20 | c514284 | In | Through the studio line. |
| Nov 21 | codex/pubpartner-connector-baseline | 2963fd0 | In | Through the studio line. |
| Nov 21 | codex/live-production | 17b29be | In | Through the studio line. |
| Nov 21 | codex/restore-director-dock | f66f285 | In | Through the studio line. |
| Nov 21 | codex/restore-mini-console | 59675d6 | In | Through the studio line. |
| Nov 21 | claude/camera-fixes-2026-11-21 | 4ad7c0d | In | Through the studio line. |
| Nov 21 | claude/avatar-live-camera-2026-11-21 | d11a1ff | In | Through the studio line. |
| Nov 21 | claude/recording-e2e-2026-11-21 | eddd8f5 | In | Through the studio line. |
| Nov 22 | claude/live-sources-2026-11-22 | f1d634e | In | Through studio-assembly. |
| Nov 22 | codex/studio-integration | 0d4d042 | In | Through portable-2i (step 5). |
| Nov 22 | feat/pubpartner-cartridge-context-2026-11-22 | 7b8c7ea | Waiting (decision 7) | Puts cartridge identity and scoped memory into FCP1. The hardening merge already does cartridge memory in FCP1 another way (_owned_cartridge_memories), so these compete. Which one fits her five-file cartridge design is her call. READ |
| Nov 22 | recovery/control-room-beyond-october-2026-11-22 | 5f05314 | Waiting | 38 commits ahead; 132 of its files differ from this branch, including recovery/beyond_october/ (108 files) that exist only there. Not brought in yet; asking whether she wants it in. |
| Nov 22 | gpt/pubpartner-portable-2i-2026-11-22 | a692d5b | In | Merged (step 5). |
| Nov 23 | claude/handoff-cricket-2026-11-23 | a531ff5 | In | Merged (step 3). |
| Nov 23 | claude/bring-in-donor-finds-2026-11-23 | c812e22 | In | Through rediscovery. |
| Nov 23 | claude/studio-assembly-2026-11-23 | 2541c09 | In | The base. |
| Nov 23 | claude/rediscovery-early-repos-2026-11-23 | a1b4063 | In | Merged (step 3). |
| Nov 23 | claude/studio-wire-avatars-2026-11-23 | 45de912 | In | The base tip. |
| Nov 23 | claude/eq-foundations-2026-11-23 | 5ef002f | In | Merged (step 1). |
| Nov 24 | claude/purfluous-character-salvage-2026-11-24 | 1d30d88 | In | Through purfluous-more-cards. |
| Nov 24 | claude/purfluous-ai-wiring-2026-11-24 | a9cdde5 | In | Through purfluous-more-cards. |
| Nov 24 | claude/purfluous-canon-2026-11-24 | 390a88a | In | Through purfluous-more-cards. |
| Nov 24 | claude/purfluous-cue-cards-2026-11-24 | f762b3e | In | Through purfluous-more-cards. |
| Nov 24 | claude/code-collector-2026-11-24 | c403fe6 | In | Through purfluous-more-cards. |
| Nov 24 | claude/purfluous-more-cards-2026-11-24 | a959a35 | In | Merged (step 4). |
| Nov 25 | claude/studio-line-missing-fixes-2026-11-24 | 90e3045 | In | Merged (step 2). Pause is still being rebuilt there; new commits get merged as they land. |
| Nov 25 | claude/find-what-we-made-2026-11-25 | b02994c | In | Merged (step 9 and the renderer findings). |
| Nov 25 | claude/renderer-crates-vendored-2026-11-24 | 151ce1d | In | Merged (step 12). |
| Nov 25 | claude/clean-shape-embed-2026-11-25 | bb5b325 | In by content | Same change as 4b566c7, already merged (git cherry shows it as present). |
| Nov 25 | claude/integrate-strongest-parts-2026-11-24 | this | The assembly branch | |

Totals: 30 in, 5 superseded, 4 waiting on her.

## From other repos and Drive

| Piece | Source | Status | Reachable |
|---|---|---|---|
| Backend hardening | Beyond-October a594d30 | Merged | Yes: /api/pubpartner/blackbox-light/* on the PubPartner router, mounted in main.py and pubpartner_app.py |
| Identity checkpoint | Beyond-October 2e2c1e3 | Ported | Yes: runs before every live PubPartner dispatch; result in the receipt. Its five tests pass (RAN) |
| Unification authority map | Beyond-October a29149d | Doc only | Doc |
| Airlock engine | October-24 ca0e929 | Code in, not mounted | No. RAN: the engine starts a session on pre-dec's governance, puts a guest in Waiting and reports the unsigned waiver |
| PEQ, cre_eq, broker, integration | Breaking-Dawn 96cfff5 | Code in, not mounted | No. RAN: the broker loads the full engine and returns a signal |
| Camera Engine v2 | Drive, blob 97ed3ee | Code in, not booted | No. RAN: create_camera_engine() builds |
| Full VDI engine | Drive, blob 6e13c18 | Code in, not wired | No. RAN: scores and returns a voice mode |
| 2i Word workspace and launcher | Drive zip 2i-Unified-Beta-2026-11-16 | Wired | Yes: File menu "Open Word document (.docx)", shown only outside file mode, and a .2i switch is refused while a Word doc is open (as in the zip). RAN: the launcher serves the page, the script, the editor, the DOCX engine and harfbuzz.wasm; both edited scripts pass node --check. Not clicked in a browser |
| Companion mode, link, avatar preference | Pub-Partner-Base-Horizon c9d053a | In, exported from pubpartner | Library only; no running path calls it in either repo. Its tests pass, 28 (RAN, with a stand-in for scikit-learn) |
| Renderer binary | rust_crate source with the ported fix | Rebuilt offline | Yes: bin/ws_renderer reads --port and --fps (RAN) |

Left out on purpose: the B-O pubpartner-*.yml workflows; The-Prime wholesale (it holds a secret key file and a grievance file); runtime data; Base-Horizon's tests/federation (needs fastapi, tests the older core) and reference/avatar_foundry (the studio has its own); the Rust camera bridge (for the Rust engine, already under recovery/).

## Waiting on Curtsey

1. Airlock: switch on the Oct 28 engine? Its admission gate would stop the current waiting room from admitting anyone until it is rebuilt around the waiver, and the waiver text is still a draft. pre-dec's governance also has no set_admission_gate yet.
2. PEQ: mount it? Its signal and observe routes take any user_id with no owner check, so they need owner scoping first. Hooking PEQ into replies (peq_enrich) would change what characters say, while the studio's EQ layer is shadow only.
3. Camera Engine v2: boot it beside CameraManager and director_engine, or replace them?
4. VDI: which engine EVO uses. The Drive one has a different API (no VDISignals, which EVO imports).
5. Decision 7: cartridge-context branch versus the hardening's cartridge memory.
6. Decision 9: the 2i-beta-polish Reach desk look and the typewriter-visual branch.
7. recovery/control-room-beyond-october: bring it in?
8. Earlier open items: the slate button covering onboarding Skip (decision 4); show clock labels IN and LEFT and the four clock questions (5); EQ on by default (6, set to on); Code Collector's P3 test (2); the broken code_collector/node_modules link to a scratch path (3, not removed because nothing is deleted without her word); the 0.4 everyday-wins intensity tier; Windows pause untried.

## Not checked here


- Route tests (RAN, Nov 25, after her yes to the libraries): fastapi 0.115.14, starlette 0.41.3 and httpx 0.28.1 installed in the cloud session only, matching requirements.txt. Across the Airlock arrivals, camera avatar, PubPartner hardening, Blackbox Light, calibration approval, identity checkpoint, cartridges, work notes, existing wiring and the Base-Horizon companion, link and avatar tests: 81 passed, 1 failed, 4 skipped (browser). scikit-learn is not installed (not yet approved), so a stand-in was used for it, and pytest-asyncio is not installed, so async tests ran through a scratch runner.
- One failed: test_owned_portable_cartridge_memory_reaches_hosted_private_prompt. Its error comes from the scikit-learn stand-in (no fit_transform), so it is unchecked, not known broken.
- tests/test_airlock.py can't load: it imports AdmissionBlocked from modules.governance, which pre-dec doesn't have. That is the admission gate that switching Airlock on needs (open call 1).
- Browser (playwright) tests were skipped; playwright is not installed.
- On the EQ and Purfluous files, 180 passed and 8 failed: four are the expected win-phrase cases tied to the 0.4 tier question, four need fastapi.
- No full suite since the studio line's last one (22 failed, 3129 passed, before the fixes).
