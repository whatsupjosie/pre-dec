# Studio assembly, 2026-11-23

Branch: claude/studio-assembly-2026-11-23 (pushed). Built on claude/one-source-2026-11-22 (eb691bf), which is 90 commits past pre-dec main 538a40f. Main has not moved since 538a40f as of 2026-11-23 05:40 Los Angeles time. Nothing here has been merged to main.

Labels: RAN = I ran it and saw the result. READ = I opened and read it. LISTED = I saw only a name or count. GUESS = my reasoning, not checked.

## What changed (all RAN against the tests named)

1. static/pubpartner_calibration_ui.js. The calibration screen built '/api/pubpartner' + path. tests/test_frontend_contract_compat.py reads every /api literal in static/ and accepts a router base only when it ends in a slash. Now '/api/pubpartner/' + the path with leading slashes removed. Behavior unchanged. RAN: test_frontend_contract_compat.py and the calibration tests, 15 passed.

2. modules/studio_slate.py and tests/test_studio_slate.py. The slate middleware added a stylesheet and a script to every 200 HTML response, including /foresight-counter, so the Counter no longer matched static/foresight_counter.html byte for byte. Added SLATE_EXEMPT_PATHS for /foresight-counter and /static/foresight_counter.html, plus a test. RAN: test_studio_slate.py, test_foresight_reach_runtime.py, test_frontend_startup_contracts.py, all passed.

3. Timeline playback controls and the timeline recording cue.
   - modules/timeline.py and modules/timeline_routes.py are the Beyond-October codex/main-debug-20261119 versions (the union-trial copy is byte-identical; git blobs b961e270 and 6fe81986), adopted whole. This branch carried an older player whose routes called player.play() and player.pause(), which do not exist, so play, pause, resume and stop through the HTTP routes could not work. The donor adds seek, monotonic timing, cue validation and critical-cue failure.
   - main.py: the timeline camera cue follows the donor. The timeline record cue now tracks its own take and stops only that take. The previous handler stopped the most recent active session, which could end an operator's take. The cue fails the timeline when capture reports warnings or no media.
   - modules/production_routes.py: new begin_take and end_take, exposed on the router and used by the stop route and the timeline, so a timeline take goes through the same capture pipeline as a control-room take. The donor's SessionCapture class does not exist on this branch, so the donor's record handler could not be used as written.
   - RAN: tests/test_timeline_playback_controls.py, 3 passed, including a real encoded h264 take while an operator's countdown session stays untouched. RAN: 17 related test files, 128 passed; six Node tests (production25d core, wiring, switcher bridge, capture, archive, studio25d confidence), all passed.

4. Recording safety (modules/recording.py, modules/capture.py). Reason: four ways a take could lose or misreport media. Source: the same ideas as codex/main-debug-20261119 (READ its recording.py and capture.py hunks), written by hand against this branch's code because the two files differ too much for a whole-file copy (recording.py 356 differing lines, capture.py 448).
   - A failed first metadata write used to leave a ghost session in memory, so the same take could not be retried. start_session now reserves the folder, writes, and only then registers the session; on failure it removes only the empty folder it just made.
   - Stop, pause, resume, archive, activate and marker changes now go through _commit_metadata: the new state is written from a copy first, and the live session changes only after the write succeeds. A full disk can no longer leave memory saying "stopped" while the saved file says "active".
   - Media registered from outside the take is copied into the take (flushed to disk, then renamed into place) and identified by a digest of where it came from. Two different external files with the same name stay two artifacts after a restart; registering the same file again replaces its own copy only. New artifact field source_key, written to the take file only when set, so older take files read as before.
   - export_session refuses a take whose artifacts resolve to one file ("relink original media") instead of zipping the same bytes twice.
   - start_session also refuses a repeated source in one take.
   - capture.py: sources whose ids clean to the same file name ("cam/a" and "cam_a"), or differ only in letter case, used to be written to one file by FFmpeg with -y, the later one overwriting the earlier. Each source now gets its own file (cam_a.mp4, cam_a-2.mp4, ...). Backslashes in a source id are now cleaned too.
   - RAN: tests/test_recording_portable_bundle.py with main-debug's three new tests added unchanged (all pass); new tests/test_capture_output_names.py, 4 passed; the old code was run against the same colliding ids and gave cam_a.wav twice. tests/test_recording_pipeline_e2e.py, 21 passed (real FFmpeg takes). 19 non-browser test files that touch recording or capture, 270 passed, 0 failed.
   - NOT ported: the main-debug test that checks overlapping names through SessionCapture (class not on this branch; covered by the new test instead), recording import not overwriting an existing zip, production pause rejecting a non-boolean, import sanitizing a filename. Those three were not diagnosed on this branch.

5. Loose-parts inventory (handoffs/LOOSE_PARTS_INVENTORY_2026-11-23.md, tools/loose_parts_inventory.py, tests/test_loose_parts_inventory.py). RAN: tool on this branch (440 Python files: 319 attached, 45 tests-only, 10 tools-only, 66 loose); 3 tests pass and one fails when the byte-order-mark handling is deliberately broken. Finding: the backends are attached; the studio's gap is screens (timeline transport buttons, readiness before a take, a link to the phone-camera page, and others). Nothing was attached, because each attachment needs a placement choice that is Josie's.

6. Show clocks, step 1 of 3 (numbers only; no screen changed). Josie's design, in her words:
   - "the top one would be how far into the show you are, and the bottom one would be how much longer you have till the end"
   - "If you're not doing a TV show with a set length, it's less important." (so the time-left clock exists only for a show with a set length, like 24:10 or 5:35)
   - "Everybody needs to see it. Everyone, even the actors"; "Usually there's a big physical clock in the control room, and then there's another one on set."
   - "they both have to show seconds ... Usually they're digital, like an alarm clock."; the fraction is "for editing", so it is frames (HH:MM:SS:FF), and "24 default".
   - The production clock (countdown to action) is a separate thing from this time code (position in the work).
   Paths: modules/timeline.py (format_time_code, frame_rate and set_length on TimelineDefinition, TimelinePlayer.clocks), modules/timeline_routes.py (status, list, load and the websocket carry the clocks), tests/test_timeline_show_clocks.py. Old timeline files without the new keys load as 24 fps with no set length.
   RAN: 33 new tests pass (spot-checked by hand: 20.5 s at 24 fps is 00:00:20:12; 1450 s is 00:24:10:00; a show at 20.5 s with a set length of 1450 has 00:23:49:12 left); breaking the frame count on purpose failed 2 of them; the 5 timeline-related test files pass together (65).
   NOT done: the picture for Josie to approve, the clocks on screens (control room and the set screens stage.html, stage_3d.html, stage_panoramic.html), Play/Pause/Stop/jump for the director only. Tasks 12 and 13.
   Not tested: the websocket feed (it needs a crew login).
   Open, for Josie: (a) the timeline stops counting at its script length, so after the last cue the time-in clock freezes; should the show clock keep running past it? (b) time left goes negative with a minus sign once past the set length; this is my choice, not hers. (c) 29.97 drop-frame is not offered (only 24, 25, 30). (d) Who can read the clocks: the status route had no login check in the code I read, the websocket needs a crew login; cast screens would need one or the other.
   Found while reading, not changed: static/director_switcher.html's clock counts from when the page opened, not from the show, and its frame field runs 00 to 30 (31 values); the control room's clock is the wall-clock time of day (its own comment says so); the stage pages' clocks are 0.6rem faint text.

6b. Show clocks, step 2 of 3: Josie approved the look (no screen file changed yet; nothing built since commit 485a690).
   Her answers, in her own words, typos kept: "greegreen or blue" (I read: green or blue, not red); then "one of each"; then "green on op bue under and hell if we can switch beween ble green yellow and red.... why not". Then I asked whether the color choice should change only the screen she is looking at or every screen, recommending her own screen only, and she answered "ok".
   So the decision is: top clock green, bottom clock blue by default; each clock can be switched on its own among blue, green, yellow and red; the choice belongs to the screen you are on, not to the director. READ from her words: the colors, the defaults, the four choices. Her "ok" answers my one question, so the per-screen scope is hers.
   Not answered, so still mine: the labels IN (how far into the show) and LEFT (how much is left) are my words; she was asked what she would call them and has not replied. I also told her that red is the color of on-air and recording lights on a set; she kept red in the list ("why not"), so red stays.
   The picture she approved (an inline widget, not a file in the repo): seven-segment digits drawn as seven rectangles, 24 frames a second, show length 24:10, near-black panel #0b0f0e, unlit segments at 10 percent opacity; green #3ddc84, blue #4da3ff, yellow #ffd23f, red #ff4d4d.
   Where the clocks go (from her design): one big clock in the control room, and one on set for everyone, "even the actors". The set screens are static/stage.html, static/stage_3d.html and static/stage_panoramic.html.
   What I had found when she said the chat was full (READ by search only, files not fully opened):
   - Existing clock spots: static/control_room.html line 74 (id pgmTc) and lines 290 to 292 (time of day, its own comment says it is not recorder time); static/stage.html lines about 428 (clock-feed), 613 (timecode) and 903 to 911; static/stage_3d.html lines about 105 and 626 to 632; static/stage_panoramic.html lines about 978 and 2274 to 2280; static/director_switcher.html lines about 605, 1128 and 1165 (the only page that calls /api/timeline). No clock-like hit in static/studio_control_room.html or static/pubworld_stage.html (its only match is a three.js clock).
   - Routes (modules/timeline_routes.py): GET /status, GET /list, POST /load, /play, /pause, /resume, /stop, /seek, and WebSocket /ws. No page except director_switcher.html uses any of them.
   Plan, NOT built, for the next session:
   - One shared script that draws the two clocks, reads the status route (or the websocket), counts smoothly in between updates, and saves each clock's color in the browser for that screen (localStorage inside try/catch). The file name static/show_clocks.js is my proposal.
   - Mount it on the control room and the three set screens.
   - Director-only Play, Pause, Stop and jump-to-time, calling the routes above (they already require the mod role).
   - Before writing it, check static/director_switcher.html and static/editor_interchange.js for a clock or seven-segment drawing worth reusing (not checked).
   - Test in a real browser the way the existing *_browser.py tests do, not with a mock page; also test that a cast member without crew login can see the clocks (open question (d) above).
   Still open for Josie: (a) to (d) above, and the labels.

## Known and not fixed

- REGRESSION, needs Josie's decision. Eight browser tests (tests/test_human_profile_onboarding_browser.py, 6, and tests/test_human_profiles_browser.py, 2) pass on main and fail on this branch. Cause (READ and RAN): the slate launcher button (#pubcast-slate-open, "Open production slate") appears on member-facing screens for any signed-in user and intercepts clicks on the onboarding "Skip optional details" button. static/studio_slate.js says "One shared floor slate per top-level PubCast screen", so global placement is the written design; the clash with member screens is a consequence. Options: exempt the onboarding and profile pages (like the Counter); show the launcher only to floor roles; or move the launcher so it never covers page controls. Not changed.
- Failing on main too (RAN on main 538a40f): tests/test_2i_format_matrix.py audio and video decode for m4a, mp4 and mov (3); tests/test_clacker_recording_browser.py; tests/test_camera_pool_browser.py; tests/test_admitted_guest_recording_browser.py; tests/test_participant_audio_browser.py (2 fail on main, 1 on this branch). GUESS: this sandbox has no real cameras or the codecs; not diagnosed.
- tests/test_pubpartner_connections.py (2 failures in the earlier full run): file does not exist on main, so no baseline. Not diagnosed.
- tests/primp_chromium/test_mirror.py: 14 errors, "recursive dependency involving fixture browser_type_launch_args". No baseline on main. UNKNOWN whether it is this branch or the sandbox.
- One unexplained event: in one run of 6 recording files together, tests/test_recording_pipeline_e2e.py::test_recording_holds_picture_and_sound_for_the_whole_take[broadcast_mp4-h264-aac-mp4] failed on its "no capture warnings" assertion (FFmpeg exited 0, 18.8 MB written). It passed alone, passed in two later runs of the whole file, and passed on the code from before item 4. One later run of 19 files also stalled at 90% and was killed by my timeout; it finished in 108 s on rerun. GUESS: machine load from other test runs; not proven.
- Test hygiene found while running: tests/horizon_ref_character_audit_regressions.py is not named test_*.py so normal collection skips it, and when it is run explicitly it leaves main.hub unset and fails 12 hub tests in tests/test_05_services.py that otherwise pass (50 passed on main and here). Running several pytest processes at once in one working copy also made single tests fail because they share the data folder; run them one after another.
- The full suite has NOT been rerun since the first three commits or since item 4. Last full run, before them: 22 failed, 3129 passed, 12 skipped, 6 xfailed, 14 errors (48 minutes).

## Left behind from the never-merged branches (partly checked)

Method: put each branch's own differing non-browser test files onto this branch's code and run them. RAN for codex/main-debug-20261119 only (27 files): 26 failed, 10 errors, 194 passed. Not run: console-touch-typewriter-keys, 2i-beta-polish, codex/2i-typewriter-visual-2026-11-17.

Triage so far (READ the messages, did not diagnose each):
- 10 errors in test_production_notes.py: the old test creates crew accounts and gets 410, "Invite guests through Guests and invitations. Each guest brings their own PubCast identity; new local crew accounts are retired." Newer deliberate behavior on this branch; the old tests are obsolete.
- 4 in test_studio_console_action_routes.py import SessionCapture, the main-debug capture design this branch replaced with FFmpegCaptureEngine and the production router's capture tasks. These need rewriting against the current pipeline, not a code port.
- Diagnosed and fixed in item 4 above: overlapping source names; the three portable-bundle tests.
- Still candidates, NOT diagnosed: recording import must not overwrite an existing zip; production pause rejects non-boolean; import sanitizes filename.

## Not done

- A real launch and a real recorded take through the control-room pages in all three modes.
- The recording mode switch in the control room (names, placement, arm_preview default are Josie's to decide).
- S2: consoles she means by name.
- Landing on main.

## Housekeeping

- data/pubpartner/vessels/alex.pubpartner is rewritten by a test run in the working copy. The committed blob is the canonical 96fa66a728d07d5ff43b0d3d7fc17a466765cec1; I restored the working copy and checked the hash. GUESS: some test writes to that tracked file; not found which.
- Untracked runtime data from test runs (data/byok/secure/master.key, databases, assets/vod) was never added. Use explicit paths when committing.
- claude/studio-restore-2026-11-22 (local only, never pushed) was started on ChatGPT's recovery branch and abandoned; its two bugs do not exist on this branch.
