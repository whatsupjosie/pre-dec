# Handoff: the one-source branch, 2026-11-22 (written 20:35 Los Angeles time)

Written for a reader with no other context. This replaces handoffs/NEXT_SESSION_HANDOFF_2026-11-22.md, which was written before the one-source branch existed. Read it only if you want the Sonnet/Opus split's first draft; this file has the current state.

Labels: RAN = I ran it and saw the result. READ = I opened and read it. LISTED = I saw only the name or a count. GUESS = my reasoning, not checked. Her words are in quotation marks, exactly as she said them.

## 1. What Josie wants, in her words

- "The entire point of this is to have one fucking main source of truth. That's the entire point of having this new repo."
- "No, get the shit from the other repo and put together the goddamn studio and, you know, do the camera work and recording work that you were talking about doing."
- "No, I want it all together."
- "Dude, I told you to focus on the control room."
- "And I told you to give me a fucking handoff!"
- Earlier today: "there's still a bunch of shit that wasn't integrated for the control room, like consoles and shit, cameras and stuff back in Beyond October that didn't come over. We need to get that over here."
- Motion capture: "don't worry too much about the motion capture at the moment, because we're going to be concerned with motion capture very closely soon. But first, let's prove that we can record it." And later: "I told you not to worry about the mocap." Do not do any mocap work.
- The recording modes she designed: "data only, main camera only, standard camcorder." And: "Just the three recording modes for now, then we can talk more about the engine."

What went wrong this evening, so the next Claude does not repeat it: I spent time on things she did not ask for (PubPartner calibration, old branches, a full-suite run) when she wanted the control room. The control room is the focus. She is also very tired and short on tokens ("we gotta stretch out our tokens"): do not run long jobs she did not ask for, and answer her short.

## 2. Her standing rules

- Do not push to main. Do not delete anything. New branch named for the task and date. Commit as Claude.
- No GitHub Actions or CI. Test locally.
- Plain text in chat, no code blocks.
- Never alter her words. Quote them.
- Never put "best" or "final" in file or folder names.
- Follow her design as written. If you think part of it is wrong, say so and ask before changing it. When she asks a question, answer it before editing.
- Say plainly what is verified and what is not. Do not lie, omit or spin.
- PowerShell 5 for any command she runs.
- Repo rules (CLAUDE.md): read STATUS.md before changing anything; do not overlay an old donor on the newer Counter or communications runtime; data/secure, data/users.db, accounts, vaults and Blackbox recordings are runtime data and never go in public artifacts; preserve the PubPartner Alex vessel blob 96fa66a728d07d5ff43b0d3d7fc17a466765cec1; every change needs reason, paths, provenance, tests and a tested/untested ledger; "Don't count a route as a working service or a DOM mock as production."

## 3. The one-source branch (where everything is)

- Worktree: /home/claude/work/one-source. Branch: claude/one-source-2026-11-22. Local only; not pushed. Built from origin/main 538a40f (2026-11-20, "Converge: merge report for integration/converge-2026-11-20"). The repo is https://github.com/whatsupjosie/pre-dec.git. Run git fetch first: main may have moved today.
- Commits on top of main (git log --oneline origin/main..HEAD shows them; merges listed in order):
  - e0ca03b merges claude/camera-fixes-2026-11-21
  - d85784b merges claude/live-sources-2026-11-22. This brought in recording-e2e, avatar-live-camera and 2i-camera-repairs too, because they are ancestors of live-sources (git said "already in" for the last two when I tried them).
  - e64f15b merges integration/2i-unified-2026-11-20
  - 2d0be28 merges codex/restore-director-dock (Restore The Prime's Director Dock behavior)
  - c805cca merges codex/restore-mini-console (Recover on-set mini console and wire current switcher)
  - codex/live-production (17b29be, "Fix Control Room asset routing and studio startup sequencing") was already inside the branch by then.
  - ba93c31 merges codex/pubpartner-connector-baseline
  - ca43583 merges codex/studio-integration. TWO CONFLICTS, resolved by me (section 4).
  - 9634f7c merges claude/recording-modes-2026-11-22 (the three recording modes). ONE CONFLICT, resolved by me (section 4).
  - 11ed0f2 PubPartner calibration from Beyond-October (separable; section 5).
- Not merged, on purpose: the four branches with no common history with main (git merge-tree exits 128): codex/main-debug-20261119, console-touch-typewriter-keys, 2i-beta-polish, codex/2i-typewriter-visual-2026-11-17. I compared them by file. Counts of file versions not found anywhere in this branch's history: 122, 89, 93, 33 (LISTED; GUESS that most are older versions of files main already replaced; NOT checked file by file). Only six file paths exist in those branches and not in this one; I copied them in as a separate commit (section 5): handoffs/MAIN_DEBUG_2026-11-19.md, handoffs/MAIN_DEBUG_2026-11-19_EVIDENCE.json, tests/test_timeline_playback_controls.py, tools/acceptance/studio_long_take.py (a 30-minute browser take acceptance test, relevant to long takes), handoffs/2I_BETA_POLISH_2026-11-17.md, tests/test_2i_polish_browser.py.
- The old branch claude/recording-modes-2026-11-22 (worktree /home/claude/work/recording-modes, head af3c0c0 at the time) is untouched and still exists.

## 4. The three conflicts and how I resolved them (READ the code; RAN only a syntax parse)

All in modules/production_routes.py and main.py. Check these first if anything about recording start/stop looks wrong.
- main.py: both sides added router includes. Kept both: the camera view and live-source routers (from live-sources) and the voxel placement router (from studio-integration).
- production_routes.py, studio-integration merge: studio-integration added capture_start_tasks and capture_stop_tasks (one start and one stop per session; a stop that arrives while cameras are still starting is refused with HTTP 409 "Recording was stopped while its cameras were starting"). live-sources added session_audio_inputs (the microphone chosen at start). I kept all three. The start task now passes audio_input only when a microphone was chosen. The line that pops session_audio_inputs moved into _collect_capture_artifacts.
- production_routes.py, recording-modes merge: kept the capture tasks and added the RecordingModeController, session_mode_options, the mode begin at the top of _start_capture_for_session, and recording_modes.end(...) at the top of _collect_capture_artifacts (git merged that part cleanly).
- GUESS / not checked: a stop that arrives while recording_modes.begin() is still running is not covered by the 409 guard, because the guard only covers the plain capture start. This edge was not tested.

## 5. What else is on the branch and what is uncommitted

- 11ed0f2 PubPartner calibration (modules/pubpartner_calibration.py, static/pubpartner_calibration_ui.js, two test files, a checkpoint note, calibration routes appended to modules/pubpartner_routes.py, and a menu item, window and script tag in static/pubpartner.html) is from Beyond-October commit 0dab95f. It was NOT what Josie asked for tonight. It is one commit and can be dropped without touching anything else. Its two test files pass: 11 passed (RAN). The GitHub workflow from Beyond-October (.github/workflows/pubpartner-calibration.yml) was NOT brought over because of her no-GitHub-Actions rule.
- Six files from the older branches (section 3) are copied into the worktree. If the next Claude does not see them committed, they are uncommitted; check git status.
- assets/vod/ in the older worktree is test debris; never commit it.

## 6. What the Beyond-October comparison actually found (RAN)

This matters because Josie believes consoles and cameras "didn't come over."
- Beyond-October was cloned shallow (depth 1, main branch only) to /home/claude/whatsupjosie/beyond-october, head 0dab95f, 2026-11-22. It has 1,783 tracked files. pre-dec main has 2,521.
- Only six files are in Beyond-October main and not in pre-dec main, and all six are the PubPartner calibration work (section 5).
- Of 103 console, camera, director, switcher, rig and recorder files in Beyond-October, 88 are byte-identical to pre-dec and the other 15 differ; for 11 of those, Beyond-October's version exists on an older pre-dec branch, and for the other 4 the difference is only in files this branch changed. Across the whole tree, 146 of the 148 differing files hold a version pre-dec's history already has. Only modules/pubpartner_routes.py and static/pubpartner.html carry a Beyond-October version pre-dec has never seen (they are the calibration hooks, merged).
- So by file comparison against Beyond-October main, no console or camera file is missing from pre-dec. This does NOT prove she is wrong: (a) only Beyond-October's main was cloned, not its other branches; (b) the consoles she means may live in her Drive, in another repo, or in a branch I did not fetch; (c) I compared files, not behaviour. The next Claude must ask her which consoles she means by name, and look in the Beyond-October branches and her Drive for them. Do not claim the gap is closed.

## 7. The control room as it stands on this branch (READ; nothing run in a browser)

- Pages: static/control_room.html (399 lines, image console), static/studio_control_room.html (1,211 lines), static/director_switcher.html (1,276 lines; has the REC button, id recordBtn, and pause, marker and export calls), static/director_console.html, static/safe_console.html, static/audio_console.html, static/pete_director.html. main.py serves studio_control_room.html, director_console.html and director_switcher.html by route (lines about 2815 to 2833) and logs /static/control_room.html at startup.
- Recording from the control room: all three pages that record (control_room.html, studio_control_room.html, director_switcher.html) start recording through the studio action recording.start with session_id, sources, profile_id "broadcast_mp4", countdown_seconds. None passes a mode, so they all start a plain camcorder take, which works. modules/studio_console_actions.py already accepts mode and record_data for recording.start, so the switch is only missing in the page. director_switcher.html's toggleRecord() is at about line 1007; it records only the current program camera.
- There is NO mode switch in any page yet. Where it goes and what it is called are hers to decide (names "Cameron" or "Mandalorian" were floated, none chosen). Do not invent a layout; bring her two or three options in plain English.
- Nothing here has been run in a real browser or against a running server. "Verify real launch, menus ... and actual UI behavior" is the repo's own bar (CLAUDE.md).

## 8. Test status (be exact)

- RAN and passed: the two calibration test files (11 passed).
- RAN before the merges, on the old recording-modes branch: 23 new mode tests and 70 older recording tests pass; a broad run gave 964 passed, 4 skipped.
- STARTED, NOT FINISHED: a full run of the whole tests folder on the one-source branch was running in the background (output in /tmp/full_suite.log; it was about 21 percent through with no failures printed when I last looked). Its final result is UNKNOWN. Re-run it in a controlled way and read the summary line. The repo's own ledger says the console-touch-typewriter-keys branch had 2,302 passed, 0 failed (LISTED, from a commit message), but that is a different branch.
- NOT run on this branch since the merges: the recording tests (tests/test_recording_modes_unit.py, tests/test_recording_modes_e2e.py, tests/test_recording_pipeline_e2e.py), and anything in a browser.

## 9. Work split by model, with check-in points

Josie asked for the work to be split into Sonnet and Opus lists, with the task lists as check-in points. At each CHECK-IN, stop, report in plain text, and wait for her. Use TaskCreate and TaskUpdate. Control room first.

### Sonnet (run, read, compare, measure; no behaviour changes)

S1. Settle the test state. Run the recording tests and the control-room tests on the one-source branch, then the full suite once, and report counts. Any failure: report which test and what it says; do not fix yet.
- CHECK-IN 1: numbers, plain English.

S2. Find the consoles she means. Ask her to name them. Then look in the other Beyond-October branches (git fetch with a depth, or the GitHub branch list), the other repos in mcp__claude-code-remote__list_repos, and her Drive for those named consoles. Compare by file hash with this branch. Write handoffs/CONTROL_ROOM_GAP_2026-11-22.md: item, where it lives, in this branch (same, differs, absent), whether it is better and how you judged.
- CHECK-IN 2: show her the table. She chooses what comes over.

S3. Describe the control room in one page of plain English: pages, how they reach the hub and the camera routes, where recording starts and stops, which buttons exist. Based on the files in section 7 plus a real launch (python main.py or the repo's launcher run_reach.py; read STATUS.md first) and a browser look if a browser is available.
- CHECK-IN 3.

S4. Prove recording from the control room, through the real page and the real server, in all three modes, once the mode switch exists (O2). Report files produced, lengths against wall-clock length, and verify_show_data. No mocap.
- CHECK-IN 4.

S5. Long take. tools/acceptance/studio_long_take.py is a 30-minute browser take; do not run it without asking her (it takes 30 minutes). Offer it.

### Opus (change code that other code depends on; each waits for her answer)

O1. Landing. When she says so, bring the one-source branch to main by whatever route she chooses (pull request or her own merge). Never push to main. Check first whether origin/main has moved.
- CHECK-IN 5.

O2. The mode switch in the control room. Needs her answers: names, placement, whether arm_preview defaults on. Propose two or three layouts in plain English and let her choose. Wire the page to recording.start with mode and record_data, which are already supported. Test it in a real browser.
- CHECK-IN 6.

O3. Bring over any consoles she names that are missing (from S2), one at a time, each with its test and provenance, each on its own branch.
- CHECK-IN 7 after each.

O4. The studio-integration conflict resolution (section 4): review it with fresh eyes, add a test for a stop arriving while a mode take is starting, and fix the gap if the test shows one.
- CHECK-IN 8.

O5. Decisions she still owes (from the recording-modes work): display names; where the switch goes; whether arm_preview defaults on; whether the dressing room is absolute (the recorder allows a host override; her rule says never; one line); walking in PubWorld (player_move is discarded in main.py, so walking is not recorded) and which rooms are in the show data (only pub, green, conference, studio and dressing are named in the privacy table; control, octagon and waitingroom are not).

O6. Engine. Not started; she said "then we can talk more about the engine." Do not begin without her go.

## 10. Do not

- Do not do mocap.
- Do not work on PubPartner, the engine, or the circuit breaker bug ("don't do the circuit breaker bug unless we're going to use the engine").
- Do not push, merge to main, or delete.
- Do not build on the older handoff's claim that the show data keeps every motion frame; that claim is corrected in handoffs/RECORDING_MODES_2026-11-22.md.
- Do not tell her something is working that you have not run.

## 11. First thing to do

Read sections 1, 2 and 10. Tell Josie in one sentence which list you are on. Sonnet: start S1. Opus: ask her for the control-room names and placement in O2.
