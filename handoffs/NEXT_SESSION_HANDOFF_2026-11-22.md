# Next-session handoff, 2026-11-22 (written about 20:30 Los Angeles time)

Written for a reader with no other context. Read sections 1 to 3 before touching anything.

How to read the labels:
- RAN means I ran it in this session and saw the result.
- READ means I opened and read it.
- LISTED means I only saw the name or a one-line description. I know nothing more.
- GUESS means my own reasoning, not checked.
- Her words are in quotation marks, exactly as she said them. Do not tidy them.

## 1. Who and how

Josie Curtsey Cobbley. She cannot read code line by line. She reads plain-English designs and spots contradictions and workflow errors. The coding is the AIs' job; the writing and the design are hers. She is on a Windows laptop with PowerShell 5 and works under real token and bandwidth limits.

Her standing rules (from her preferences and the repo's CLAUDE.md and AGENTS.md):
- Do not push to main. Do not delete anything. Work on a new branch named for the task and date. Commit as Claude, not as Josie.
- No GitHub Actions or CI to test her work. Test locally or somewhere free.
- Plain text in chat. No code blocks.
- Never alter her words. Quote them.
- Never use "best" or "final" in a file or folder name.
- Follow her design as written. If you think part of it is wrong, say so and ask before changing it. If she asks a question, answer it before editing anything.
- Say plainly what is verified and what is not.
- If she turns down an idea, say which parts are actually required and why, then leave the decision to her. Do not answer with "fine, exactly your way."
- Use PowerShell 5 syntax for any command she runs.
- Repo rules: data/secure, data/users.db, private accounts, vaults and Blackbox recordings are runtime data and never go in public artifacts. Preserve the PubPartner Alex vessel blob 96fa66a728d07d5ff43b0d3d7fc17a466765cec1. "Never silently deploy, merge to main, delete, overwrite original assets, or announce product launch."
- Alex is a she. Alex's memories of Josie personally never reach Alex Core or the public.

## 2. What she asked for today, in her words

The recording modes (done, section 4):
- "I want to be able to record all three ways... record traditionally, same way you would with a camcorder... And I want the data only option. I want the avatar option... And I want the only render... while camera 2 isn't the one on the live screen, it's not being recorded. But when we cut to camera 2, camera 2 is now being recorded... data only, main camera only, standard camcorder."
- "All right, let's design it and integrate it. Just the three recording modes for now, then we can talk more about the engine."

Her design for how it should work, said earlier today:
- "all the cameras, they get all of the data, but they don't render the data... only actually rendering the shots they want to capture. So they can store the entire day of shooting cheaply because it's just the raw data and not massive image files. But they can turn that into image files anytime."
- "We can capture a single performance, decide that it's the best we've seen so far, and just replay that exact performance while somebody else does a live performance against it."

Her last message before this handoff (20:18):
- "We've basically pulled an entire control room out of the repo, and we're doing this now because goddammit, I want to get this in. Oh yeah, and there's still a bunch of shit that wasn't integrated for the control room, like consoles and shit, cameras and stuff back in Beyond October that didn't come over. We need to get that over here. But yeah, if you're good, tell me what mode to put you in before I ask you to just keep going on the work. And don't worry too much about the motion capture at the moment, because we're going to be concerned with motion capture very closely soon. But first, let's prove that we can record it."
- She also said she is "starting to think about dinner" and that "we gotta stretch out our tokens." Keep sessions short and the reading list short.

What I do not know: the control room she says was "pulled out of the repo" and the PubPartner "leaps" she mentions were done in other sessions. I have not read any of that work. Do not assume what is in it. Ask her which branch it is on, then read it before building on it.

## 3. Correction to what I told her earlier

I told her the show data keeps "every motion and choreography frame." That was overstated, and so is line 27 of handoffs/RECORDING_MODES_2026-11-22.md (corrected in that file in the same commit as this handoff). What the code actually does (READ in modules/recording_modes.py, modules/hub.py and main.py):
- The show data records everything that goes through the hub's system broadcast (hub.system). Choreography and mocap messages use that same broadcast, so they should be recorded, but that has not been proven in a real run. Josie has said mocap is not the concern right now (see section 7), so it is not a task here; it is only a fact about what the file may hold.
- People walking around PubWorld are not recorded. In main.py the PubWorld socket handler's player_move branch does nothing ("pass"), and presence goes to a private roster (pubworld_private). Recording either is a decision about whose movement is kept and in which rooms. It is hers to make. Do not do it unasked.
- Room messages are kept only from rooms the privacy table names and allows. The default table in modules/recording.py (around line 1144) names pub, green, conference, studio and dressing. Browser code also uses control, octagon and waitingroom, which the table does not name, so those are left out of the show data. Dressing is "never" and is never recorded.

## 4. State of the work (all of it is local; nothing is pushed)

Worktree: /home/claude/work/recording-modes. Branch claude/recording-modes-2026-11-22, three commits on top of origin/claude/live-sources-2026-11-22 (f1d634e):
- 7ff31d7 capture engine: record a microphone on its own, report progress
- 54c66d9 hub: let listeners see every message it sends
- 8eb55f0 recording modes: camcorder, data only, main camera only

Verified (RAN): 16 unit tests and 7 end-to-end tests for the modes pass; 93 recording-related tests pass together. A broad run earlier gave 964 passed, 4 skipped (speech models not installed), but that run was before three small last fixes. Only the recording part was rerun after them. In the end-to-end test, live cuts landed 3 to 66 ms late and armed cuts 0 ms late. Program lengths matched the plan (13.705 against 13.672 s).

Not tested: Windows, a real webcam, takes longer than about 15 seconds, any 3D stage camera, a take through the real control room.

Known weaknesses I told her about:
- Main camera mode starts the new camera at the moment of the cut, so cuts land up to about 0.07 s late unless arm_preview is on.
- Cameras that push a stream to us (listener RTMP or SRT sources) cannot be used in main camera mode. It refuses them.
- Data-only takes cannot yet be turned back into pictures. That needs the engine.
- modules/recording_modes.py is about 1,250 lines.
- The PubWorld 3D stage cameras are not covered, because the 3D stage is drawn in the browser.

Branch landscape as of my last fetch (origin is https://github.com/whatsupjosie/pre-dec.git). Run git fetch first, because origin/main may have moved today:
- origin/main was 538a40f, dated 2026-11-20 (GUESS: it has moved since, given her control-room work).
- origin/claude/recording-e2e-2026-11-21 (eddd8f5) is an ancestor of origin/claude/live-sources-2026-11-22 (f1d634e). live-sources is 8 commits ahead of main, recording-e2e is 7 ahead.
- origin/codex/studio-integration (261908d, 2026-11-22) conflicts with live-sources in modules/production_routes.py (two hunks, the capture helpers) and in main.py. RAN as a trial merge earlier; nothing was committed.
- Merging the modes branch onto main was clean at the time, because it carries the live-sources commits with it.

Bundles in /home/claude/out (made earlier today; each is a git bundle, check with git bundle list-heads):
- recording-modes-2026-11-22.bundle: origin/main..claude/recording-modes-2026-11-22, 11 commits, verified.
- recorded-takes-2026-11-22.bundle: branch claude/recorded-takes-2026-11-22 (24ca7ea). READ its handoff, RECORDED_TAKES_PORT_2026-11-22.md. It is a port of Codex commit 086420d. It records the real 3D stage canvas and the program audio mix as a take, with a take editor page. This matters for the 3D camera gap above. How it fits with the modes branch has NOT been worked out.
- pre-dec-spine-consolidation-2026-11-22.bundle (claude/spine-consolidation-2026-11-22, 21d60b4), pre-dec-dressing-room-lock-2026-11-22.bundle (claude/dressing-room-lock-2026-11-22, 099cc7c), airlock-port, peq-engine-port, pubpartner-base-horizon-link: LISTED only. I know the names and the heads, not the contents. Read their handoffs or commits before relying on them. The dressing-room lock may relate to the dressing-room question in section 6.

Other files in /home/claude/out:
- RECORDING_MODES_2026-11-22.md (full handoff for the modes, READ at writing time, with the one correction above)
- ENGINE_COMPARISON_2026-11-22.md (engine comparison and her design clarifications)
- BIG_ZIP_HARVEST_2026-11-22.md (the Drive harvest)

## 5. Decisions Josie owes (do not decide these for her)

1. Display names for the three modes. "Cameron" and "Mandalorian" were both floated and neither was chosen. The code uses camcorder, data_only, main_camera.
2. Where and how the mode switch appears in the control room.
3. Whether arm_preview defaults on. It is off now because she said a camera that isn't on the live screen isn't recorded. On gives exact cuts and costs a second encode the whole time.
4. Whether the dressing room is absolute. The recorder lets the host override. Making it absolute is a one-line change I have not made.
5. Landing order: recording-e2e and live-sources first, or rebase onto main.
6. Whether to push the branch.
7. Whether people's walking movement is recorded, whose, and in which rooms.
8. Which rooms beyond pub, green, conference, studio and dressing should be in the show data.

Older open decisions from earlier today, from the previous summary and not re-read: Alex crisis-detection fix; predictive_insight engine; camera auto-cut lock; spelling variant; The-Prime privacy items (data/byok/secure/master.key sits in the public The-Prime repo); Codex branch landing; airlock waiver; PEQ tables; cre_eq alias; Base/Horizon heartbeat; vault_store; Thursday cue library; DREAMS handlers; recorded-takes timing.

## 6. Work split by model

Josie asked for the work to be separated by model. The split is by risk. Sonnet 5.5 at medium effort: running, reading, comparing, measuring. Opus 5.5 at high effort: changing code that other code depends on, and merging. Each list has CHECK-IN points. At a CHECK-IN, stop, report to Josie in plain text, and wait. Make each list a task list with TaskCreate and tick it off with TaskUpdate.

### 6A. Sonnet track (read-only or test-only; changes only in tests and notes)

Do these in order. First: cd /home/claude/work/recording-modes, git status (expect only the untracked assets/vod/, which test runs leave behind and is not to be committed), git fetch, git log --oneline -5.

S1. Prove the three recording modes on a real take, through the real start and stop path. Her words: "let's prove that we can record it." Motion capture is NOT part of this task.
- Start a camcorder take, a data_only take and a main_camera take through the real API (POST /api/recording/{session_id}/start, then stop), the way the control room will, with the cameras and sound sources the studio really has. Use the studio's own cuts and cues as the events. Do not feed in mocap, and do not build mocap tests.
- For each take, report: the files produced, their lengths against the wall-clock length of the take, whether show_data verifies (verify_show_data says verified and closed), and in main_camera mode whether the program file's cuts match the cut log.
- If something fails on a real run that passed in the tests, that is the finding. Report it, do not patch around it.
- CHECK-IN 1: one line per mode: worked or did not, with the numbers.

S2. Measure the show data size on a long take.
- Run a 10-minute take with the events the studio really sends (cuts, cues, camera moves). Do not simulate mocap. Report file size per minute and the time to flush.
- She said the data should be cheap to keep ("store the entire day of shooting cheaply"). If size is a problem, say so with numbers. Do not add caps; her rule is that you ask before capping anything.
- CHECK-IN 2: size per minute and per hour, plus the memory use of the recorder.

S3. Inventory what in Beyond-October's control room did not come to pre-dec. Her words: "consoles and shit, cameras and stuff back in Beyond October that didn't come over."
- First ask her where Beyond-October is reachable. In earlier sessions it was read through Google Drive and the GitHub repos. Her repo list is in git or via mcp__claude-code-remote__list_repos.
- Branches already in pre-dec's origin that look like console work, LISTED by name and date only: codex/restore-director-dock (f66f285, 2026-11-21), codex/restore-mini-console (59675d6, 2026-11-21), console-touch-typewriter-keys (3ee394a, 2026-11-17), codex/live-production (17b29be, 2026-11-21, "Fix Control Room asset routing and studio startup sequencing"). Read what each contains before calling it missing.
- In the current worktree the static folder already has audio_console.html, camera_avatar_live.html, camera_connect.html, camera_pool_*.js, camera_rig.js, camera_station.js, console.css, console.js and others. Compare by blob hash and by content, not by name.
- Output a table in a file named CONTROL_ROOM_GAP_2026-11-22.md in handoffs/. Columns: item, where it lives in Beyond-October (repo, branch, path), in pre-dec? (hash match, differs, absent), what it does, whether it is good (say how you judged), what it would need to be wired in. READ means opened; LISTED means only the name.
- Her rule: before building anything new, check whether a more advanced version exists in her repos and Drive and compare rather than rebuild.
- CHECK-IN 3: show her the table. She decides what comes over. Do not copy anything into pre-dec on this task.

S4. Find what the control room she pulled out today contains.
- Ask her which branch or bundle it is. Read it. Write a one-page plain-English description of the control room as it is now: which consoles, which cameras, how they talk to the hub, and where the recording start and stop buttons are, if any.
- This feeds the mode-switch decision in section 5.
- CHECK-IN 4: show her the page before Opus does anything with it.

S5. Windows. Nothing here has run on Windows. Write a short PowerShell 5 test sheet she can run on her laptop (python -m pytest paths for the recording tests, and one real webcam take), with the exact expected output. Do not tell her to "go try it" as if she hadn't been running her builds there; give the commands and the expected result.
- CHECK-IN 5: hand her the sheet.

### 6B. Opus track (changes code other code depends on; needs her answers first)

Run each only after the named decision from section 5 is made. Branch names are new, named for the task and date. Never push to main.

O1. Landing order. Needs decision 5.
- Land recording-e2e and live-sources first, then the modes branch, onto a new branch off the current origin/main. Resolve the two production_routes.py capture-helper hunks and the main.py conflict with codex/studio-integration. Show her each conflict and its resolution in plain English before committing.
- Run the whole test suite on the merge. Compare against the pre-merge counts (964 passed, 4 skipped on the modes branch as of the broad run).
- CHECK-IN 6: conflict list and test counts. She approves before anything else is merged.

O2. Control-room consoles and cameras. Needs S3 and S4 and her go on the table.
- Bring over only the items she approves, one task each, each with its own test, on its own branch. Reuse the privacy checks (RecordingService._validate_sources, room_policy, room_is_recordable).
- CHECK-IN 7 after each item.

O3. Mode switch in the control room. Needs decisions 1, 2 and 3.
- This is her design. Bring her two or three layouts in plain English and ask. Do not build a layout she has not chosen.
- Wire the switch to POST /api/recording/{session_id}/start with mode, record_data, arm_preview (already in production_routes.py) and to the console action recording.start in modules/studio_console_actions.py.
- CHECK-IN 8.

O4. Recorded takes and the modes together. The 3D stage is drawn in the browser, so the server modes cannot record it. The recorded-takes branch records the canvas in the browser. Decide with her how a main-camera cut on a 3D camera would work. She has said "live we would have to do the Mandalorian technique... we only render it once," so a data-only 3D take means the show data is the recording and the browser draws it later. This is a design conversation first. Bring her three options (browser records the canvas; server replays the show data into a renderer; both) with the cost of each.
- CHECK-IN 9.

O5. Walking movement. Needs decisions 7 and 8. Change the player_move branch in main.py to send to the hub so it enters the show data, only for the rooms and people she names, with the privacy table applied. Test that a dressing-room walker is never recorded.
- CHECK-IN 10.

O6. Dressing room. Needs decision 4. Read the dressing-room-lock bundle first, since it may already do this. Then make it absolute if she says so.
- CHECK-IN 11.

O7. Split recording_modes.py (about 1,250 lines) into smaller modules with no behavior change: show data recorder and reader, program planning and joining, take, controller. The 23 mode tests plus the 70 older recording tests must pass unchanged. Do this last, after landing, so it does not add conflicts.
- CHECK-IN 12.

O8. Engine. Not started. She said: "then we can talk more about the engine." Option 3 in the engine comparison (a custom Rust core on open parts) waits for her go and for her laptop's graphics card and RAM. Read handoffs/ENGINE_COMPARISON_2026-11-22.md (in /home/claude/out) first. Do not begin without her go.

## 7. Things not to do

- Do not work on motion capture at all. Her words: "don't worry too much about the motion capture at the moment, because we're going to be concerned with motion capture very closely soon." Do not start on the engine or the circuit breaker bug either. She said: "don't do the circuit breaker bug unless we're going to use the engine."
- Do not push, merge to main, delete, or overwrite originals.
- Do not read the old handoff as complete; it overstated the motion data (section 3).
- Do not assume the PubPartner or control-room work from other sessions is in your worktree. Ask which branch.
- Do not commit assets/vod/.
- Do not edit the repo's other handoffs or her pasted text.

## 8. Files and paths

- Worktree: /home/claude/work/recording-modes (the older /home/claude/pre-dec may also exist)
- Modes code: modules/recording_modes.py, modules/recording.py, modules/capture.py, modules/hub.py, modules/production_routes.py, modules/studio_console_actions.py
- Tests: tests/test_recording_modes_unit.py, tests/test_recording_modes_e2e.py, tests/test_recording_pipeline_e2e.py
- API (RAN in tests): GET /api/recording/modes, GET /api/recording/{session_id}/mode, POST /api/recording/{session_id}/mode/assemble; the start route takes mode, record_data, arm_preview, sources_named
- Show data schema: pubcast-show-data/1 (gzip JSON Lines, header, events, footer with count and SHA-256). Mode record: pubcast-recording-mode/1 (recording_mode.json)
- Scratch (outside the repo): /home/claude/scratch/modes_smoke.py and modes_colors.py
- Handoffs: handoffs/RECORDING_MODES_2026-11-22.md (full design and code map), this file, and in /home/claude/out the engine and harvest notes

## 9. The very first thing to do

Read sections 1 to 3. Then tell Josie in two sentences which track you are on, and start with the first task on that track. Sonnet: S1. Opus: ask her for the answer to decision 5 and decision 4, then O1.
