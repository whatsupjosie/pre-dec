# Recording modes: camcorder, data only, main camera only
Prepared 2026-11-22 by Claude for Josie and for whoever picks this up next.

Branch: `claude/recording-modes-2026-11-22`. Not pushed, not merged. Nothing on `main` changed.

## What Josie asked for, in her words (2026-11-22)
"I want to be able to record all three ways. Is that possible? I want to be able to record traditionally, same way you would with a camcorder. You hit record, you tape it, and you record everything that just goes on in front of the camera. And you hear everything that goes on in front of the camera or wherever the mics are laid up. And I want the data only option. I want the avatar option. We'll call it the Cameron. Or the Mandalorian, I don't know. And I want the only render, you know, what's actually recorded option. So like you described, you know, just like while camera 2 isn't being recorded, or while camera 2 isn't the one on the live screen, it's not being recorded. But when we cut to camera 2, camera 2 is now being recorded. But when we cut back to camera 1, now we're recording camera 1. You know, recorded and rendered. And yeah, data only, main camera only, standard camcorder."

Then: "All right, let's design it and integrate it. Just the three recording modes for now, then we can talk more about the engine."

The names "Cameron" and "Mandalorian" are **not decided**. The code uses neutral ids taken from her own last sentence: `camcorder`, `data_only`, `main_camera`. A display name can be put on each when she chooses.

## Base: why this branch is not on main
It is built on `origin/claude/live-sources-2026-11-22` (f1d634e), itself on `origin/claude/recording-e2e-2026-11-21`. Both are earlier Claude branches, pushed, not merged. They fix capture bugs on `main` that would break these modes (x264's default preset encodes 1080p59.94 at about half real time on a two-core machine, so takes came out short; the web profile's codec names were not FFmpeg encoder names; failed starts were silent), and they add microphone input. So landing this branch means landing those two first, or rebasing this one onto `main` and resolving `modules/capture.py` and `modules/production_routes.py` by hand.

Codex's `origin/codex/studio-integration` already conflicts with live-sources in `modules/production_routes.py` (the two capture helpers) and `main.py`. This branch touches the same two helpers. See "Merging" below.

## What each mode does now
- **camcorder** (the default, as before): every camera chosen for the take records picture and sound for the whole take, through the existing capture path. New: the show data and the mode record are kept with it.
- **data_only**: no picture at all. The show data is recorded, plus the sound of every chosen camera that carries sound, and the microphone if one was chosen, each as its own WAV file for the whole take.
- **main_camera**: only the camera on the live screen (the switcher's program) records picture. When the program changes, the new camera starts, and the old one stops once the new one is delivering frames, so there is no gap. Sound of every chosen camera that carries sound, and the microphone, records for the whole take. When the take stops, the pieces are joined into one program file at the take's own profile, in the background, and that file is added to the take. Program sound in the joined file is the microphone when there is one, otherwise each camera's own sound (audio follows video).
  - `arm_preview` (off by default, because Josie said a camera that is not on the live screen is not recorded): the camera on preview records too, so a take from preview lands with no delay. Costs a second encode the whole time.

Under all three, unless `record_data` is false (not allowed for data only), the **show data** is recorded.

## Files each take now has (in its folder under `recordings/<session_id>/`)
- `show_data.jsonl.gz`: gzip JSON Lines. A header (mode, profile, cameras with position/rotation/fov/focus/tags but **no endpoints**, because stream addresses can hold keys; program and preview at the start; the privacy table), then one line per event: `camera.switch`, `camera.pose` (from the camera manager), `hub.system` (every system message the hub sent: camera cuts, studio actions, audio cues, and, in principle, mocap and choreography frames, which go through the same broadcast but have NOT been proven in a real run; people walking in PubWorld are NOT recorded because the player_move handler in main.py discards them. Corrected 2026-11-22 evening, see NEXT_SESSION_HANDOFF_2026-11-22.md section 3), `hub.room` (room messages, only from rooms the privacy table names and allows). Footer: event count and SHA-256 of every line before it. Flushed every second; a crash loses at most the last second, and the reader still returns every whole line.
- `recording_mode.json`: the mode, every cut (asked for, took effect, how late in ms, how handled), every stretch of the live screen (which camera, which piece, or why there is none: `private`, `not_in_take`, `failed_to_start`, `no_capture_engine`), every piece of picture with its timing and FFmpeg report, the sound tracks, the microphone, the show-data summary, the program join and any notes.
- main camera only: `program_NNNN_<camera>.<ext>` (one per piece), `sound_<camera>.wav`, `microphone.wav`, `program.<ext>` (the join), and next to the join its FFmpeg log and filter script.

Both data files are listed in the take's metadata (`data_files`) and travel with export (`data/` in the bundle, hashed in the manifest) and import (checked and restored byte for byte).

## How to use it (HTTP)
- `POST /api/recording/start` takes three new optional fields: `mode` (`camcorder` default, `data_only`, `main_camera`), `record_data` (true default), `arm_preview` (false default). With no `sources`, main camera only uses every camera the privacy rules allow, so any of them can be cut to; the other modes use the program camera as before.
- `GET /api/recording/modes`: the three modes and what each does.
- `GET /api/recording/{session_id}/mode`: the mode record, live during the take.
- `POST /api/recording/{session_id}/mode/assemble`: join a stopped main-camera take's program again (after a restart or a failed join). Never overwrites an existing program file.
- The console action `recording.start` takes `mode` and `record_data` the same way.

Refused with a reason (400): unknown mode; data only with `record_data` false; main camera with no program camera, with the program camera not in the take, with an audio-only profile, or with a camera that waits for its sender to connect (RTMP/SRT on 0.0.0.0, which cannot be opened and closed per cut; record those in camcorder mode).

## Privacy
Cuts follow the same rules as choosing a camera at the start (`RecordingService._validate_sources`): a camera in a "never" place (the dressing room) or a "with_permission" place (the green room) is not recorded without the host override. A cut to one leaves a black stretch marked `private`, and no file of it exists. Room messages enter the show data only from rooms the privacy table names and allows; private message rooms (`dm____`, `dmv2_`) and presence lists never do. Rooms not in the table are left out (a deliberate, conservative choice: room names are not camera locations).

**For Josie to decide (existing rule, not changed):** the recorder already lets the host override record a "never" place, including the dressing room. Her rule is "you can be recorded anywhere except the dressing room". The show data follows the same rule as the cameras, so it can be overridden too. If the dressing room should be absolute, that is a one-line change in `_validate_sources` and `room_is_recordable`; it was not made without her say.

## Verified (RAN, in Claude's Linux sandbox, FFmpeg 6.1.1, two cores)
- `tests/test_recording_modes_unit.py`: 16 passed. Show data written, read and verified; a file cut off by a crash reads up to its last whole line; an altered line is caught; never overwrites; program plan arithmetic (exact pieces, black holes of exact length, no overlap, slivers dropped, a file camera's half-second read-ahead handled); room privacy; the hub reports each message once and a broken listener changes nothing; mode requests checked; data files out and back through export/import byte for byte; altered, missing or path-escaping data refused leaving nothing; takes from before modes existed load as camcorder; a stopped take's program joined from its record alone after a "restart"; 60 random cut/preview/take sequences with a stand-in capture engine never left a camera recording that should not be (this test fails if the armed-preview fix in `_set_preview` is reverted; checked).
- `tests/test_recording_modes_e2e.py`: 7 passed. Real host, two live cameras (FFmpeg sending in real time over UDP multicast, each painting its own clock into the picture), real files judged with ffprobe and decoding. Results from the run:
  - main camera, cuts at 3.0 / 6.5 / 9.5 s on live cameras without arming: the joined program showed red, blue, red, blue changing within a frame of where the record says; each camera's picture clock agreed between its stretches to within about 0.04 s (the program keeps real time across cuts); the program lasted 13.71 s for a 13.67 s plan; cut delays recorded 3 to 66 ms. That small delay is real for these sources because FFmpeg holds the frames it buffered while opening the stream; a camera that takes longer to open will show a longer delay, and the record will say how long.
  - armed preview, two takes: 0 ms delay on both.
  - dressing-room camera: refused at the start; cut to mid-take, a black stretch marked private, no file of it.
  - data only: two sound-only WAV files with the right tones for the whole take, no picture, the cuts in the show data.
  - camcorder: unchanged result, plus show data and mode record.
  - export: both data files in the bundle, byte for byte, hashes in the manifest.
  - joining took 2 to 4 s for 9 to 14 s takes at 1280x720 VP9.
- Existing suites on this branch: the recording pipeline, portable bundle, integrity audit, capture cleanup, camera broadcast, 2.5D recording guard, live sources, DM privacy: 93 passed together with the new tests. A wider run of 101 existing non-browser test files touching recording, the hub or the routes: 964 passed, 4 skipped (speech models not installed), before three small last fixes; the recording-related part was rerun after them.
- One existing test was changed: `tests/test_recording_pipeline_e2e.py::test_a_tampered_bundle_is_refused_and_leaves_nothing_behind` renamed every `.json` in a bundle, which now includes `data/recording_mode.json`, so it was refusing the bundle for a duplicate name instead of for the flipped byte it is meant to catch. It now renames only the top-level metadata and also checks that the refusal is the integrity check.

## Not verified, or not done (plain)
- **Windows.** Nothing here ran on Windows. The microphone track uses the live-sources microphone input (DirectShow on Windows), untested there.
- **PubWorld 3D cameras.** These modes record what the server can capture: files, network cameras, webcams, microphones. The PubWorld stage is drawn by three.js in the browser, and native voxel cameras (`rust://`) have no media. Camcorder mode for several 3D cameras would need each camera's view rendered; main camera only for 3D is how the browser stage already works (it draws the program view). Making the browser stage honour these modes is engine work, not done.
- **Turning data-only takes back into pictures.** Needs a renderer that replays the show data. Not built. The data is complete enough to start from (camera moves and cuts, motion and choreography frames, studio actions), but avatar and set versions are not pinned in the header yet.
- **Virtual (test-pattern) cameras** record faster than real time (FFmpeg's lavfi has no clock pacing). That is the existing capture behaviour; the mode record flags such a piece as not paced to the clock.
- **Pause** does not pause capture, in any mode (existing behaviour of the pause route).
- **No control-room control yet.** The modes are reachable through the API and the console action. Where the mode switch goes in the control room, and what it looks like, is Josie's design; not added.
- Real webcams and phones were not tested; cut delay on them is not measured.
- Very long takes were not run (the longest was about 15 s). The show data grows with mocap and choreography frame rates; no size cap.

## Merging
- Onto live-sources (its base): fast-forward.
- With `origin/codex/studio-integration`: expect conflicts in `modules/production_routes.py` inside `_start_capture_for_session` and `_stop_capture_for_session` (Codex reworked both into task-tracked starts and stops; live-sources and this branch add lines at their tops) and in `main.py` (between live-sources and Codex, not this branch). The resolution: keep Codex's task tracking, keep live-sources' microphone handling, and keep this branch's two blocks first in each helper (the mode starts before any FFmpeg check, because show data needs none; a mode that owns capture returns its own media before the camcorder path).

## Code map
- `modules/recording_modes.py` (new): `validate_mode_request`, `default_sources`, `ShowDataRecorder`, `iter_show_data`, `verify_show_data`, `room_is_recordable`, `plan_program`, `ModeTake` (one take), `RecordingModeController` (one per server).
- `modules/recording.py`: `RecordingSession.mode`, `.record_data`, `.data_files`; `start_session(mode=, record_data=)`; `attach_data_file`; export and import carry `data/`.
- `modules/capture.py`: `start_audio_input` (a microphone on its own), `live_report`, `running`; the spawn and start-check code shared by both start paths.
- `modules/hub.py`: `add_event_observer` / `remove_event_observer`; every message is reported once to listeners before it is sent.
- `modules/production_routes.py`: one controller; the two hooks; the start route's new fields; the three new routes.
- `modules/studio_console_actions.py`: `recording.start` takes `mode` and `record_data`.

## Next steps (for Josie to choose)
1. Decide the display names (Cameron / Mandalorian or others) and where the mode switch sits in the control room.
2. Decide whether the dressing room is absolute (no host override).
3. Land recording-e2e and live-sources, then this branch; or ask for it rebased onto main.
4. Engine work: make the browser stage honour camcorder and main-camera modes for PubWorld cameras, and replay data-only takes into pictures.
