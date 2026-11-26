# Control Room engine completion — living handoff

Repository: whatsupjosie/pre-dec. Branch: `finish/control-room-engine` (pushed).
Base: `claude/integrate-strongest-parts-2026-11-24` at `ec7895a3`, the assembly branch. It contains the assignment's
starting commit `a4fafd1` (RAN: `git merge-base --is-ancestor a4fafd1 HEAD`). Why this base: see "Recovery".
ChatGPT's branch: `finish/control-room-operator` (starts at a4fafd1). This branch does not touch it, and it touches no
frontend file (no HTML, CSS or browser JavaScript under `static/` or `2i/`).
Owner: Josie Curtsey Cobbley. Nothing here is merged to main, to the assembly branch, or to December.

Evidence words, used everywhere below:
- **RAN**: I ran it here and saw the result.
- **READ**: I opened and read the code or file.
- **LISTED**: I saw only a name, size or hash.
- **GUESS**: my reasoning, not checked.
- **NOT RUN**: could not be run here; says why.

Machine for every RAN result: Linux cloud sandbox, 2 cores, 7 GB; Python 3.13; FFmpeg/ffprobe 6.1.1; Chromium headless
shell 1243 (software WebGL, SwiftShader); Playwright 1.56. **Nothing here ran on Windows.**

---

## Exact next task

1. Read "Regression run" at the end; if any failure is listed as NEW, fix it first.
2. Phase 5 reliability (not started): low disk during a take, renderer interruption (kill the headless browser mid-job:
   the job must fail with its reason and leave no file), network-camera loss mid-take (`ended_early` in `timing`
   and a `stalled` meter), restart recovery of a take and of a reconstruction job, and export of a take that has
   reconstructions (artifact + manifest data file travel; checked by import).
3. Main-camera and camcorder picture files of a paused take: they are still joined without their resume gaps (see
   Known defects 2). Decide with Josie: pad on join (re-encode), or keep the files and give editors the `timing`.
4. The three debugging rounds and the 30-minute endurance recording (section 9 and 10 of the assignment).
5. Windows: run `tests/test_reconstruction_e2e.py` on Josie's laptop with `PUBCAST_RENDER_BROWSER` unset, so it uses
   Microsoft Edge (find_browser picks channel "msedge" on Windows), and the pause test from the earlier handoff.

## Master checklist

Phase 1, production authority
- [x] One camera registry: `modules/cameras.py` CameraManager. READ: every route that changes Program or Preview goes
      through it; `cameras_advanced.py` / `evo/camera_manager.py` are kept as donors and only boot behind an explicit flag.
- [x] One Program/Preview broadcast: `modules/camera_broadcast.py`. READ.
- [x] FIXED: a dissolve was held only in SwitcherService's memory. It now travels on `CameraSwitchEvent.transition`
      into show data and to every page. RAN.
- [ ] Presets/PTZ: `/api/switcher/ptz` and `update_pose` exist and are recorded as `camera.pose`; not re-verified here.
- [ ] Admission/privacy: existing suites only (in the regression run below); no new work.

Phase 2, recording modes
- [x] Built and tested on the base (handoffs/RECORDING_MODES_2026-11-22.md, STUDIO_LINE_MISSING_FIXES_2026-11-24.md).
- [x] FIXED: after a pause, sources could drift apart. Nothing recorded where each piece sat on the clock, and show
      data's pause window ended late. Now every source report has a measured `timing`, show data uses the take's own
      pause window, and reconstruction places each sound piece where it was recorded. RAN: beeps in phase across a
      pause within 25 ms.
- [x] NEW: performer data in show data (`performance.frame`), and the stage and the Program mix at take start and resume.
- [ ] Camcorder/main-camera picture pieces are still joined without their gaps (Known defects 2).

Phase 3, renderer
- [x] Strongest renderer: the live 2.5D studio's own (`static/production25d_renderer.js` + `production25d_core.js` +
      `world_walk_glb.js`). The Rust `ws_renderer` still returns no picture (READ).
- [x] NEW: reconstruction from show data, from Program (cuts and dissolves), any 2.5D camera, or a framing that never
      existed live, with the take's sound and the intended Program mix. RAN.
- [ ] The 2.5D studio does not send performer frames yet. That's ChatGPT's frontend (contract below). Until then a
      2.5D take has none, and reconstruction refuses it with that reason.

Phase 4, audio authority
- [x] NEW: independent channels (host, guest, AI performer, music, sfx, VTR, room; more can be added), separate from
      the six buses. The recovered console controls that share the dialogue bus are bus aliases, not channels.
- [x] Gain, mute and solo (in place) per channel; master and bus faders as before. The effective level is computed
      once on the server. Every change is published to players (`action: "mix"`) and kept in show data (`audio.mix`).
- [x] Meters, from two real sources:
      - the Program player's own measurement (`POST /api/program-audio/meters`), with who measured it and its age;
      - the sound files takes are writing, read by the server (`recording_inputs`), with `state`
        live / starting / stalled / unreadable. A dropped source shows `stalled`, named.
- [x] FIXED: guest-audio dropout, two causes, the first reproduced on the old code (see the commit and below).
- [x] NEW: reconstruction applies each channel's level over time to the sound track it names (`source_id`): the
      intended Program mix. RAN: guest brought down to 0.25 → −12.0 dB in the file.
- [ ] Music/SFX/VTR playback stems: these play in browsers; the server records what it captures (cameras,
      microphones, network sources). A browser-side Program-mix recording exists (studio25d_recording_ingest).
      Server-side stems of browser-played music are NOT built.

Phase 5 and the three debugging rounds: not started (Exact next task).

## Recovery: what was compared and why this base

RAN, 2026-11-26. 25 engine files compared by git blob across every branch tip of pre-dec (41) and December (9). The
files: capture, recording, recording_modes, production_routes, cameras, camera_broadcast, switcher_routes, program_audio
and its routes, participant_audio, audio_devices, mic_routes, hub, timeline, studio_console_actions, live_source_routes,
camera_pool, studio25d_media_routes, ws_renderer.rs, production25d_renderer.js, world_walk_glb.js, production25d_core.js,
main.py, blackbox_media, recorded_slate_sync.

| Finding | Evidence |
|---|---|
| Every other version is an older subset, or was ported into the studio line with reasons written down | RAN; READ handoffs/ASSEMBLY_LEDGER_2026-11-25.md, STUDIO_LINE_MISSING_FIXES_2026-11-24.md |
| `claude/integrate-strongest-parts-2026-11-24` (ec7895a) is strictly ahead of a4fafd1 on engine files: the join-unchecked fix, the rebuilt `bin/ws_renderer` and its `--port` fix, and Camera Engine v2 and VDI from Drive (not booted) | RAN merge-base; READ its ledger |
| `claude/clean-shape-embed-2026-11-25` forked before a4fafd1's pause rebuild | RAN (merge-base 90e3045) |
| ChatGPT's `finish/control-room-operator` changes none of the 25 | RAN |
| December `main-assembly` (4897d7a): no `recording_modes.py`; older capture, routes and renderer; its installs withdrawn | RAN |
| The-Prime (3 branches): engine files already present byte for byte under `recovery/`; `audio.js`, `switcher.js` are browser files | RAN |
| NowCurtsey-Build (7 branches): camera bus, bridge and recording pipeline present byte for byte; `theater_render_pipeline` serializes lit voxel meshes, draws no picture; its capture.py is older | RAN, READ |
| Saturday: `pubcast_event_core/__init__.py` imports `contracts.py` and `runtime.py`, which are on no branch | RAN |
| Big Zip (Drive): compared by content 2026-11-22 (446 source files). Not opened: Drive zips over 10 MB (Ring Me Jeeves Parts 135 MB, two friday zips, pucastpy, pub.zip, the codex_construction zips, pubcast_complete_debugged). The connector refuses files over 10 MB | READ handoffs/BIG_ZIP_HARVEST_2026-11-22.md |
| DREAMS `distributed_engine_node_close_loop.py`: work sharing between machines, generic encoder; no better renderer or recorder. Its rule "Audio Never Sacrificed" is to be applied in Phase 5 | READ |

## Implementation decisions (each weighed against alternatives)

1. **Reconstruction draws with the live studio's own code.** Options:
   (a) port the renderer to Python: rejected (a second source of truth; can't draw GLB actors);
   (b) finish the Rust renderer: rejected for now (no picture path);
   (c) run `production25d_renderer.js` unchanged in a headless browser on a fixed time step and pipe the frames to
       FFmpeg: chosen.
   RAN: rendering the same request twice gives the same frames, md5 for md5.
2. **The render host never touches the network or the web server.** `modules/render_host/` is not in `static/`. The
   driver answers every browser request from `static/` and `render_host/` only, and refuses the rest.
3. **Performer data goes through the one show-data recorder.** Same clock, pause rules and export. The hub copy
   (`performance_state`) is not kept twice.
4. **A take begins, and resumes, with the stage and the mix as they are** (`snapshot_providers`, stamped at t = 0 or at
   the resume instant). Found by the e2e test: a take started mid-show was black until the next change.
5. **Where a piece sits on the clock is measured, not inferred.** Options:
   (a) the spawn time: wrong by the device or network open time;
   (b) anchored at the stop: RAN wrong by 223 ms on a network source, because FFmpeg drops what is still queued at
       "q", while a piece still probing writes everything;
   (c) FFmpeg's own progress reports timestamped on arrival, taking the smallest (wall − out_time): chosen.
       RAN: the same beeps land 1 ms apart across pieces.
   Progress runs at FFmpeg's default interval. RAN: `-stats_period 0.1` made three existing tests fail and was removed.
6. **One pause window**: show data's take.paused / take.resumed are stamped at the instants pause and resume were asked,
   the same as the take record. Before, both landed late by the encoders' stop and start time.
7. **The sound mix is laid over silence exactly as long as the take** (`amix duration=first`). RAN: an open-ended
   `apad` after a mix of delayed pieces never ends in FFmpeg 6.1; reproduced alone.
8. **Meters read what was written since the previous reading**, never just "the last 0.2 s". RAN: FFmpeg wrote a WAV
   in 256 KB blocks (2.7 s), so a tail meter stepped over short sounds. Audio-only recordings now flush each packet
   (`-flush_packets 1`), so the file grows as fast as the source delivers.
9. **Guest audio**: a token bucket (5 s ahead, 1.25× refill) replaces the 1-second window. A per-desk ordered outbox
   replaces the send inside the guest's handler. A stalled desk loses its oldest audio and is told how much; a guest
   is never cut off for it.
10. Nothing invented. Black where the renderer cannot draw, named in the manifest's `stretches`. A file that fails
    ffprobe or a full decode is set aside as `.rejected.mp4` and never added to the take. A take with no performer
    data is refused with that reason.

## Changed-file inventory (this branch, since ec7895a)

| File | Change |
|---|---|
| modules/cameras.py | `CameraSwitchEvent.transition`; `set_program_source(..., transition=)`, `take(transition=)`, checked before anything moves |
| modules/switcher_routes.py | a dissolve passes its transition to the camera manager |
| modules/camera_broadcast.py | `camera_switch` payload gains `transition` |
| main.py | the camera logging wrapper passes the transition; performer data and reconstruction mounted; reconstruction stops at shutdown |
| modules/capture.py | `_ClockProbe` (measured piece start); piece lengths measured before the join; `timing` in every source report; `current_files()`; `-flush_packets 1` for audio-only |
| modules/recording_modes.py | `record(at=)`; `record_event`; `snapshot_providers` at start and resume; one pause window; `live_levels()` and `wav_tail_levels()` |
| modules/production_routes.py | exposes `router.recording_modes`, `router.program_audio_state`; mix into show data; meters wired |
| modules/program_audio.py | channels, effective gain, solo, mix, meters (additive; old status keys unchanged) |
| modules/program_audio_routes.py | `/channels`, `/channels/{id}`, `/solo/clear`, `/meters` |
| modules/participant_audio.py | token bucket; `HostOutbox` |
| modules/performance_capture.py | NEW |
| modules/reconstruction.py, modules/reconstruction_routes.py | NEW |
| modules/render_host/reconstruct.html, reconstruct.js | NEW |
| tests/test_performance_capture.py (27), tests/test_reconstruction_e2e.py (12), tests/test_participant_audio_resilience.py (5), tests/test_program_audio_channels.py (19) | NEW |
| tests/test_recording_modes_unit.py | one expectation: a serialized switch has `"transition": null` |

## API and event contracts for ChatGPT (frontend)

All routes need a signed-in operator with role `mod` or above unless said otherwise. All additions are backward
compatible: existing fields and routes are unchanged.

### 1. Performer data: the 2.5D studio must send this (not wired yet in static/production25d_app.js)
- `PUT /api/performance/frame`: one frame. Send it on every stage change: blocking, a performer starting or stopping
  moving, lower third, blackout, scores, set images, voxel prop, hologram. While someone speaks, also send the mouth
  weight `jaw` (up to 30 a second, or batched as below). Unchanged frames are accepted and not kept twice.
- `POST /api/performance/frames`: `{"frames": [...]}`, up to 120. Each frame carries `client_ms` (the sender's
  `performance.now()`), never going backwards; the spacing between frames is kept.
- `GET /api/performance/state`: `{"sequence", "stage", "age_seconds", "recorded_frames", "unchanged_frames_skipped"}`.

The frame's shape (the camera pool's `poolSnapshot()` shape is already valid):
```
{"package": "late_night",
 "performers": [{"id": "p25d-late_night-performer-1", "slot": "host", "avatar": "female" | "male",
                 "avatar_url": "/static/...glb" (optional, instead of avatar),
                 "position": [x 0..1, y 0..1], "vx": 0, "vy": 0, "moving": false,
                 "jaw": 0..1 (optional), "viseme": "AA" (optional)}],      up to 8, ids unique
 "lowerThird": false, "lowerText": "", "scores": [0, 0], "blackout": false, "hologram": false,
 "assets": {"back": "/static/...", "mid": "/static/...", "front": "/static/..."}   (optional),
 "voxelProp": {"prop_id", "x", "y", "size", "angle", "blocks": [{"x","y","z","color":"#rrggbb"}]}   (optional),
 "gestures": [{"performer": "<id>", "clip": "Wave"}]   (one-shot, optional),
 "client_ms": 12345.6   (optional)}
```
Reply: `{"ok": true, "sequence": n, "takes_recording": k}`, where k is how many live takes kept it (0 while paused or
when nothing records). An invalid frame gets 422 with the reason, and nothing is kept.
Hub system event, at most 10 a second: `{"type": "performance_state", "payload": {"sequence", "stage"}}`.

### 2. Camera switch: a new field
The `camera_switch` payload now has `"transition"`: `{"type": "cut", "duration_ms": 0}`, or
`{"type": "dissolve", "duration_ms": n}`.

### 3. Program audio: channels, solo, meters
- `GET /api/program-audio/channels` returns `{"ok", "mix"}`, where mix is
  `{"sequence", "master_volume", "buses": {bus: {volume, muted}}, "channels": {id: {...}}}`. Each channel:
  `{"id", "label", "kind", "bus", "gain" 0..2, "muted", "solo", "source_id", "effective_gain", "effective_db", "audible"}`.
- `POST /api/program-audio/channels/{id}` with any of `{"gain", "muted", "solo", "label", "source_id"}`. Returns
  `{"ok", "mix", "event_sequence"}`. A bad field gets 400 and changes nothing; an unknown channel gets 404.
- `POST /api/program-audio/channels` with `{"id", "kind", "label"?, "bus"?, "gain"?, "muted"?, "solo"?, "source_id"?}`
  adds a channel (a second guest, say). Kinds: host, guest, ai, music, sfx, vtr, room, other.
- `POST /api/program-audio/solo/clear`.
- Players receive every mix change on `/api/program-audio/events` as `{"action": "mix", "mix": {...}}`. Apply each
  channel's `effective_gain` to that channel's source. Master and bus faders are already folded in.
- `/api/program-audio/status` also carries `channels`, `solo_active` and `mix_sequence`. Its old keys are unchanged.
- `POST /api/program-audio/meters`: the player that renders Program reports what it measures, several times a second.
  Body: `{"program": {"rms_dbfs", "peak_dbfs", "clipped"?}, "channels": {id: {...}}}`, dBFS −120..0.
- `GET /api/program-audio/meters` returns two parts:
  - `"program_player"`: `{"measured", "measured_by", "age_seconds", "stale", "levels"}`;
  - `"recording_inputs"`: a list of `{"session_id", "source_id", "file", "levels": {"peak_dbfs", "rms_dbfs",
    "seconds_recorded", "window_seconds", "clipped"}, "last_write_age_seconds", "state", "stale"}`, where `state` is
    live, starting, stalled or unreadable. A `peak_dbfs` of null means nothing new since the last reading, not silence.
- To put a guest's microphone on its own channel, set that channel's `source_id` to the camera or input id the take
  records (reconstruction uses it for the intended mix).

### 4. Participant audio desk: a new message
The desk may now receive `{"type": "gap", "dropped_frames": {"<peer hex>": n}}`, just before the next audio, when it
fell more than 8 MB behind. The frames' own sequence numbers show where the gap is. The guest stays connected.

### 5. Reconstruction
- `GET /api/reconstruction/capabilities`: the browser found (or why not), ffmpeg/ffprobe, and the choices.
- `POST /api/recording/{session_id}/reconstruct` with `{"camera": "program" | "p25d_<package>_<shot>" | {"center": [x, y],
  "zoom": 1..4}, "fps": 24|25|30, "quality": "standard"|"master", "audio": "take"|"none", "label"?}` returns the job.
  409 while the take is recording; 400 with the reason; 404 when there is no such take.
- `GET /api/reconstruction/jobs/{job_id}`: `state` (queued | rendering | cancelling | complete | failed | cancelled),
  `progress {frames_done, frames_total, seconds}`, `result {file, artifact, manifest, frames, duration, stretches,
  render_seconds}`, and `error` in words.
- `POST /api/reconstruction/jobs/{job_id}/cancel`; `GET /api/recording/{session_id}/reconstructions`.
- A finished video is a take artifact; its manifest is a take data file.

## Test commands and results

From the repository folder. On Windows, the same lines in PowerShell 5, with `python` from the PubCast environment:
```
python -m pytest -q tests/test_performance_capture.py tests/test_program_audio_channels.py tests/test_participant_audio_resilience.py
python -m pytest -q tests/test_reconstruction_e2e.py
python -m pytest -q tests/test_recording_modes_e2e.py tests/test_capture_engine_safety.py tests/test_recording_modes_unit.py
```
RAN, 2026-11-26 (Linux):
- tests/test_performance_capture.py: 27 passed.
- tests/test_program_audio_channels.py: 19 passed; with tests/test_program_audio_routes.py and _contract.py, 26.
- tests/test_participant_audio_resilience.py: 5 passed, with tests/test_participant_audio.py (7). Old relay, same
  3 s backlog: 76 of 150 frames delivered, then the guest was disconnected.
- tests/test_reconstruction_e2e.py: 12 passed, about 2 min 40 s. These are measured from the files themselves:
  valid H.264 of the take's length; cuts and dissolve at the recorded times; a mid-dissolve frame is a blend;
  alternate angles; the guest at 0.69 then 0.55; parallax (desk ≈ 0.82, wall ≈ 0.17 of the framing shift);
  identical frames on re-render; beeps in phase across the pause within 25 ms; −12 dB intended mix; live meters;
  nothing kept while paused; unauthenticated sender refused; a recording take not reconstructed.
- Three regressions found and fixed before committing. They came from my `-stats_period 0.1` and failed on this
  branch but passed on ec7895a in a separate worktree (RAN both).
- Regression run: see the end of this file.

## Known defects and blockers
1. The 2.5D studio does not send performer frames yet (ChatGPT, `static/production25d_app.js`).
2. Camcorder and main-camera picture pieces of a paused take are joined without their resume gaps. Their `timing` says
   where each belongs. Main-camera assembly already uses its own timing. Camcorder files are not padded.
3. Server-side stems of browser-played music, SFX and VTR are not built (the browser plays them).
4. Rendering speed on this 2-core machine: RAN 12.3 to 13.5 frames a second at 1280x720 (JPEG intermediate,
   two GLB performers), so a 30-minute take at 30 fps takes about 70 minutes per angle. Not optimized yet.
5. Windows: NOT RUN. The browser driver expects Edge there; untested.
6. The Rust `ws_renderer` still renders nothing; reconstruction does not use it.

## Commit checkpoints
- a354092 Dissolves travel on the camera switch event
- 4a080d5 Capture: measure where every piece of picture and sound sits on the clock
- 5514272 Performer data, one pause window, and reconstruction from any camera
- 896da9a Guest audio: stop dropping a guest after a stall or a slow desk
- 5d5026c Capture: progress at FFmpeg's default interval; sound files written as they are made
- c91b6e2 Program audio authority: independent channels, solo, meters, and the intended mix
- (next) this handoff

## Dated log
- 2026-11-26 07:58–10:30 (Los Angeles): recovery comparison; base moved to ec7895a; renderer proven; dissolve fix;
  performer data; reconstruction; sound placement and one pause window; guest-audio dropout; channels, solo, meters
  and the intended mix. The e2e tests found and drove fixes for: black start of take, sound placement, an FFmpeg apad
  hang, the late pause window, meter blocks (256 KB writes), a missing file during input probing, and the
  `-stats_period` regression.

## Regression run

RAN 2026-11-26, after the last code change: 40 test files in one run (every non-browser test file whose name starts
with capture, recording, camera, blackbox_capture, segmented_capture, live_sources, frontend_startup,
module_router_parity, main_route_authorization, timeline, studio_console, production, program_audio,
participant_audio, switcher, stage_compat, 2_5d or studio25d, plus this branch's four new files).
Result: **458 passed, 1 failed, 3 skipped**, in 13 min 15 s.

The one failure: `tests/test_recording_pipeline_e2e.py::test_recording_holds_picture_and_sound_for_the_whole_take[broadcast_mp4-h264-aac-mp4]`,
on its "no capture warnings" assertion (a 1080p H.264 take).
- Rerun alone: 3 of 3 passed on this branch, and 3 of 3 on the base ec7895a, in a separate worktree (RAN).
- handoffs/STUDIO_ASSEMBLY_2026-11-23.md records the same test failing the same way once under load, on the base.
- GUESS, not proven: the encoder briefly ran under real time while two cores ran 40 suites, and the engine rightly
  warned. Not caused by this branch, as far as these runs show.

The 3 skips: browser tests whose Playwright build differs from the installed Chromium. They are NOT RUN, not passed.

Not in this run: the full suite (over 3,000 tests, about 50 minutes). Its last full run was before this branch, and
is recorded in STUDIO_ASSEMBLY_2026-11-23.md.
