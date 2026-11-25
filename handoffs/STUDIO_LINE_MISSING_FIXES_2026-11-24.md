# Studio line: the missing fixes, where they go and how, 2026-11-24

Branch: claude/studio-line-missing-fixes-2026-11-24 (pushed), started from claude/studio-assembly-2026-11-23 at 2541c09. Nothing is merged to main. No pull request is open. Work done 2026-11-24 and 2026-11-25 (Los Angeles).

Source of the fixes: codex/main-debug-20261119 (tip d3b9db8), the 25 commits it has past the common base c82069b. Every one of them was checked against the studio line's actual files, not against the merge plan page (that page undercounts the missing fixes and wrongly calls recording design open; it was not edited).

Labels: RAN = I ran it and saw the result. READ = I opened and read the code. GUESS = my reasoning, not checked.

## The map: every main-debug commit since the base

| Commit | What it fixes | On the studio line before this branch | What this branch did | Where it lives now |
|---|---|---|---|---|
| b4a966b | Reach bridge no longer files a user's work under the default name "user" | Missing (READ, file equal to base) | Ported, whole file | 2i-backend/server.js, 2i-backend/test/bridge_contract.test.js (commit 0164565) |
| 0b70045, 8a30942 | Camera Try keeps the final pose; the Bella Faux Pas walker keeps saved avatars and progress in order | Missing | Ported; world_walk.html by three-way patch, the rest whole | static/camera_try.html, static/world_walk_live.js, static/world_walk.html, tests/test_camera_try_browser.py, tests/test_bella_faux_pas_progress.py (0164565) |
| cb21ec1 | Missing type imports | Missing | Ported | modules/mocap_integration.py (line 49), switchblade_governor.py, wired/NUDGE_MINIMAL.py (9ef96f6) |
| d3b9db8 | Counter reports loading, redirecting, error and ready; speech runtime counts dialogue starts | Missing | Ported by patch, tests copied | static/foresight_counter.html, static/program_audio_runtime.js and six tests (f956fc5) |
| d637bb3 | Test clients no longer boot the whole app by accident | Missing (the cast-name part was present) | Ported | conftest.py, tests/conftest.py (f956fc5) |
| 7a0745a | FFmpeg never writes over a file | Missing: FFmpeg ran with -y and names started empty | Ported against this line's engine | modules/capture.py: start() and start_audio_input() use -n; _names_in_use and _reserved_names (890b24d) |
| b2b7d23 | Pause really pauses the encoders | Missing, and worse than main-debug's old code: the studio pause route never touched FFmpeg on any computer, so a "paused" take kept recording | First ported as main-debug's suspend (890b24d, b391380); then rebuilt, because suspending FFmpeg does not keep the pause out of the file (see below). Pause now works in all three take modes | modules/capture.py: _CaptureProcess.pause, FFmpegCaptureEngine.set_paused, _join, _joined_problem; modules/recording_modes.py: ModeTake.set_paused, _clock; modules/production_routes.py: pause_recording |
| e225c19 | Each failed camera is named and kept with the take; stop all encoders at once | Partly: the director panel already named failed starts; nothing was saved with the take, spawn failures were lost, stops ran one by one | Ported | modules/capture.py: stop(), failures(), _stop_failure; modules/recording.py: RecordingSession.capture_errors, note_capture_errors; modules/production_routes.py: _note_capture_errors, _start_errors (890b24d, cf5a13c, b391380) |
| 597174a | PANIC stops every take at once and a file that could not be added is kept for retry | Partly: PANIC already finished media before closing; it ran one take at a time and dropped files that failed to register | Ported | modules/production_routes.py: finish_all_captures, unregistered_outputs, CaptureNotFinished (b391380) |
| 884c1cd | Console stop finishes media before closing the take; host_override must be a real true or false | Missing (the long-take tool was present) | Ported | modules/studio_console_actions.py: confirmed_stop_session_id and the boolean check; modules/production_routes.py: studio_action_execute (b391380) |
| 9e872cb | Control Room shows which cameras failed | Missing | Ported, reading this line's list shape | static/control_room.html: failedRecordingSources, captureFailures (1bc5b48) |
| 62ad072 | Timeline cues share the production encoders; shutdown finishes recordings | Partly: cue sharing was present (begin_take, end_take); finishing recordings at shutdown was missing | Ported the shutdown part | main.py: _finish_recordings_at_shutdown on both lifespan exits; production_routes.py: router.shutdown_captures (9a0bb9c) |
| 11deaae | Timeline transport and cue fixes | Present except stopping the timeline player at shutdown | Ported that line | main.py, both lifespan exits (9a0bb9c) |
| 95399f5 | Renderer reports frames dropped at avatar capacity and reads --port, --fps, --log-level, --help | Missing | Source ported; binary NOT rebuilt (see open items) | rust_crate/src/ws_renderer.rs (0fea123) |
| 461ee0b | Advanced camera settings survive a restart | Present in a fuller form (metadata_from_record, auto-switch rules, failed saves raise) | Nothing | modules/cameras_advanced.py, modules/evo/camera_manager.py |
| 0a13d68 | PANIC interrupts a browser stop already in progress | Present in this line's own form | Nothing | static/production25d_app.js stopRecording |
| e7f2473, bf8cc63 | Metadata changes only after the write lands; external tracks copied into the take; ambiguous exports refused | Present (hand-ported earlier in be935e7) | Nothing | modules/recording.py: _commit_metadata, register_artifact, export_session |
| 13ebae6, 310c858 | 2i edit coalescing; director panel failure names | Present | Nothing | |
| 3866603, 958cf09 | IndexedDB version 2 journals | Not ported on purpose: the studio's production25d_storage.js is byte-identical to main's version 3 store, which is the settled design | Nothing | |

Also already present, though the studio's own 11-23 handoff listed them as not diagnosed: production pause refuses a non-boolean (production_routes.py _bool_field), recording import never overwrites an existing zip and sanitizes the file name (import_recording). READ.

## How each recording fix works on this line

The studio line does not have main-debug's SessionCapture class, so main-debug's capture and route code could not be copied. Each idea was written against this line's FFmpegCaptureEngine, production routes and recording modes.

- No overwrite. Every new file name skips names already in the take folder, folded for letter case, and names a leftover .ffmpeg.log still holds, plus names a running encoder is writing in the same folder. FFmpeg also runs with -n, so it refuses rather than replaces. The microphone file gets the same treatment.
- Pause, why it was rebuilt. Suspending FFmpeg (SIGSTOP on Mac and Linux, NtSuspendProcess on Windows, main-debug's way) freezes the encoder but not the camera: a live camera's picture piles up while it is frozen and is written the moment it resumes, and a file camera catches up. RAN: a suspended take still held the paused stretch. So that way was dropped on every computer.
- Pause, how it works now. Pause closes each camera's file cleanly (the same stop key as a normal stop, then terminate after 8 seconds, then kill after 5), so the paused stretch is never recorded at all. Resume starts each camera again into the next piece, name.part002.webm and so on; a file camera picks up where it had got to, not from the start. Stop joins the pieces into the take's usual file name without re-encoding, checks the joined file (size, length within half a second plus a tenth per piece, same streams) and only then removes the pieces. If the join or the check fails, every piece is kept and listed in the take. Windows uses the same path, with no suspend calls.
- Pause in the take modes. Camcorder, data-only and main-camera takes all pause. While paused, show data keeps nothing (a cut made during the pause is not in it); it writes take.paused and take.resumed, and take.resumed notes where the cameras stood. A main-camera take does not follow cuts while paused; when it resumes it comes back on whatever camera is live then, and the program is assembled on take time with the pause removed. The take record lists each pause and the total paused seconds.
- Pause, limits. A phone or listener camera (RTMP or SRT listener) is disconnected at pause and has to reconnect at resume. After a resume there is a short gap while each camera comes back; in a main-camera program it shows as black. If a camera cannot stop, the ones that did are started again and the route answers 409 with the reason, so the take is never half paused. If a camera cannot come back, the take resumes with the rest and names it.
- Failures. Each source that fails to start (including one FFmpeg could not launch) or fails at stop is saved with the take as {source_id, error, phase}. If FFmpeg is missing on the computer, the take says so for each source. The list is written only when something failed, so clean takes keep their files unchanged. Takes saved by main-debug with its {source_id: error} map still load.
- Files never lost. A finished file that cannot be added to its take (a full disk) stays on disk and in a queue. Stop answers 409 naming the files and leaves the take open; pressing stop again adds them. PANIC and shutdown retry the queue too. An encoder that would not stop also answers 409, so stop can be pressed again.
- PANIC and shutdown finish every take at once, each take's media before its session is closed.
- Console stop checks confirm and the take first, finishes the media, then closes the take, and replies with artifacts, capture_report and capture_errors, which the director panel already reads.
- New fix, not from main-debug: when FFmpeg's input pipe breaks, stop used to wait for the input to end by itself, which never happens with a live camera. It now waits the normal grace time and then sends the stop signal. Found by the new tests.

## What was tested

- RAN: tests/test_capture_engine_safety.py (new, real FFmpeg on Linux), 8 passed: no overwrite of an earlier file or a leftover log's name; pause holds the file still and resume continues, no lag warning; a refused pause changes no encoder; an encoder that already ended does not block pause; a broken camera is named and the others record; a launch failure is recorded; three cameras stop together (under 16 seconds where one by one takes 24 or more); failures saved with the take and read back, including main-debug's old shape.
- RAN: tests/test_capture_output_names.py, 4 passed; the lag-report checks from tests/test_recording_pipeline_e2e.py, run by hand because that file needs httpx; tests/test_camera_fixes_2026_11_21.py, 60 passed, 1 not runnable here (needs fastapi).
- RAN: the real routes end to end with real FFmpeg, through a throwaway stand-in for fastapi kept outside the repo (not committed). All 27 checks passed: start and console start name the broken camera; the saved take names it; pause and resume through the route really stop and restart the file; a full disk keeps the file and the take open and a second stop saves it; console stop closes the take only after the encoders finished; an unconfirmed console stop touches nothing; text "false" for host_override is refused; PANIC stops two takes together in about 8 seconds and both keep their files; shutdown finishes a take still recording; a data-only take refuses pause and keeps recording; with no FFmpeg the take says nothing was recorded.
- RAN: node --check on the Control Room script and the ported browser files. Python import checks on every changed module.
- RAN, 2026-11-25, after the pause rebuild, with the web server libraries from requirements.txt installed in a scratch environment (the repo's own setup, nothing committed): tests/test_capture_engine_safety.py 10 passed, with new tests that a live camera's paused stretch is not in its file, a take stopped while paused keeps what was recorded, a file camera resumes where it had got to, an ended encoder does not block pause, and a camera that cannot come back is named. tests/test_recording_modes_e2e.py 10 passed, three of them new: a paused camcorder, data-only and main-camera take through the real routes with live test cameras, each checking the files leave the pause out (the camera's on-screen clock jumps by the pause), show data keeps nothing from the pause, and the main-camera program shows red, blue, red with its length equal to the take less the pause. The three new ones passed three runs in a row. Also passed: tests/test_recording_modes_unit.py, test_capture_output_names.py, test_camera_fixes_2026_11_21.py (91 with the two above), test_recording_pipeline_e2e.py, test_camera_capture_cleanup.py, test_blackbox_capture_disconnect.py, test_segmented_capture_and_preservation.py (17), test_live_sources_e2e.py, test_frontend_startup_contracts.py, test_module_router_parity_guards.py.
- The throwaway fastapi stand-in used on 11-24 is retired; its check that a data-only take refuses pause no longer applies.
- NOT RUN: the browser tests, Windows pause (READ only; it needs a run on her laptop), the Control Room in a real browser, and the renderer build.

## Open items for Josie

1. Answered: Josie said a paused camera should stop recording and actually pause. Done for all three take modes, as above.
2. Pause on Windows needs one real try on her laptop: start a take, pause for a few seconds, resume, stop, and check the file is about the take less the pause and that the pieces are gone.
3. bin/ws_renderer was not rebuilt, on hold. The renderer libraries (94 crates in rust_crate/Cargo.lock, 80 MB) are packaged, not built, on branch claude/renderer-crates-vendored-2026-11-24 (commit 151ce1d, from 2541c09), so they are kept. READ: rust_crate/src/ws_renderer.rs only acknowledges frames; its render tick logs a line and never sends a rendered picture back, and the voxel bridge is not written. So the renderer does not yet do what its own header says.
4. The director panel's pause shows "PAUSE FAILED" without the server's reason, because postJSON drops the reply on a 409. Not changed (not in main-debug, and it is her screen).
5. static/control_stations.js listens for recording_paused and recording_resumed events that nothing sends. Not changed.

## Not brought in (other sources, noted only)

- Big Zip: three zips over 10 MB wait on Josie unzipping them. Other Big Zip gaps: the predictive insight engine (no branch), full websocket message schemas, the Evo pieces in the "reference parts and ideas" zip, Saturday's event core (pubcast_event_core/contracts.py and runtime.py, only in the Saturday repo), and Friday-era code including the audio mixer page, the dressing-room lock and the Airlock port.
- The Beyond October folder of 108 files is only on origin/recovery/control-room-beyond-october-2026-11-22. Not brought in; pushing it waits on her yes.

## Merge notes

- RAN: git merge-tree of this branch with claude/studio-wire-avatars-2026-11-23 and with claude/eq-foundations-2026-11-23: both merge with no conflicts. No merge was made.
- RAN: claude/eq-foundations-2026-11-23 changes none of the files this branch changes.
