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

Updated 2026-11-27. Josie approved this order ("break that up into a workflow and let's knock them off"):
intercom → preflight → fault tests → 30-minute endurance → handoff. All five are done; see the Dated log.

1. Read "Regression run" at the end; if any failure is listed as NEW, fix it first.
2. Open defect B, first (Known defects 8): sound-only WAV files drift long, up to 0.88 s in 30 minutes. This decides
   whether a data-only take can be reconstructed in sync to the end.
3. Open defect A (Known defects 7): `tests/test_recording_modes_e2e.py::test_data_only_records_no_picture_every_sound_and_the_show_data`
   fails most runs: a sound file is 7.06 s against a 7.0 s bound. It fails the same way at 8fc67042, before the
   capture changes of 2026-11-27 (RAN 4 of 4), so it is not from them. Two explanations are in Known defects 8;
   the likelier one is that the test times the take from after the start's 0.6 s startup check, so the file is
   longer than the test's clock, not the take's. Tell them apart, then fix the cause or the test, with evidence.
4. Josie's decision, still open: camcorder pause gaps (Known defects 2).
5. Still not done from Phase 5: renderer interruption (kill the headless browser mid-reconstruction), network-camera
   loss mid-take beyond an encoder dying (the source stops sending), a guest dropping, through the real host
   (unit-tested only), restart recovery of a reconstruction job, and export of a take with reconstructions.
6. Windows (Josie's laptop): run `tests/test_recording_faults_e2e.py` needs Linux (it uses /proc and tmpfs). On
   Windows, check by hand: start a take, end the host in Task Manager, and see that no ffmpeg.exe stays running
   (modules/child_lifetime.py, the job object, is NOT TESTED). Also open a fragmented MP4 take in the editor Josie
   uses (GUESS: current editors read them; not checked).
7. The three debugging rounds of the assignment: not yet run as separate rounds.

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

Phase 4, added 2026-11-27
- [x] NEW: the director's PA (intercom), ported from the NowCurtsey run bundle. See the 2026-11-27 log and commit 8fc67042.

Phase 5, reliability (2026-11-27)
- [x] Preflight before rolling, and a gate on every start path (route, studio action, timeline): no FFmpeg, an
      unwritable folder, or disk for under 2 minutes refuse the take with the reason. RAN.
- [x] An encoder killed mid-take, in each mode: named in the report; what it wrote is kept and plays; the program
      covers the whole take with black from the death, and says so. RAN. FIXED: crash-safe live files; a dead program
      encoder's picture was misplaced and the program cut short.
- [x] The host killed mid-take: no encoder survives it (Linux, RAN); the take comes back interrupted, its files play.
      FIXED: encoders and the program assembler used to outlive the host. Windows mechanism NOT TESTED.
- [x] The disk filling mid-take: stop says "No space left ... retry", keeps every file; gate refuses; with room a
      second stop finishes the take. RAN.
- [x] 30-minute endurance, all three modes at once: PASSED on df765bbb (see "Endurance"). Open: sound-only drift
      (Known defects 8).
- [ ] Renderer interruption, a source that stops sending, a guest dropping through the real host, export with
      reconstructions (Exact next task 4).
- [ ] The three debugging rounds as separate rounds.

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
| modules/intercom.py, modules/intercom_routes.py | NEW 2026-11-27: the director's PA (ported; provenance in the module header) |
| modules/hub.py | `post_chat_message(notify_ai=False)`: a line that does not wake the AI cast |
| modules/studio_camera_preflight.py | 2026-11-27: `mode`, machine checks (FFmpeg, writable folder, disk), `gate`, `start_gate`, `PreflightRefusal` |
| modules/recording.py | 2026-11-27: `start_session` runs the gate; `session.preflight` |
| modules/capture.py | 2026-11-27: crash-safe live muxing (`_CRASH_SAFE_MUXING`, `live=`); encoders and joins tied to the host |
| modules/child_lifetime.py | NEW 2026-11-27: encoders end with the host (Linux PR_SET_PDEATHSIG; Windows job object, untested) |
| modules/segmented_capture.py, modules/reconstruction.py | 2026-11-27: their FFmpeg tied to the host |
| modules/recording_modes.py | 2026-11-27: an ended-early segment is anchored where it died (`Segment.ended_early`), the assembly warns; the assembler is tied to the host; offline render `live=False` |
| tests/test_intercom.py (17), tests/test_intercom_real_host.py (1), tests/test_recording_start_gate.py (10), tests/test_recording_faults_e2e.py (6), tests/test_capture_crash_safety.py (5) | NEW 2026-11-27 |
| tools/acceptance/test_engine_endurance.py | NEW 2026-11-27: the 30-minute run, excluded from ordinary collection |

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

### 6. Intercom (the director's PA), 2026-11-27
- `POST /api/intercom/announce` `{text, rooms: [room ids] | null (every live room), audio: bool = true, voice: str}`
  → `{ok, announcement_id, delivered: [...], failed: {room: reason}, had_audio, audio_note, ...}`.
  Errors: 400/413 (bad body, text over 500 characters), 403 (no access to a named room; private rooms never),
  409 (no live room), 429 (one per speaker every 2 s).
- Each targeted room receives `{"type": "intercom", "payload": {announcement_id, speaker_id, speaker_name, text, room,
  all_rooms, audio_b64 (base64 WAV, PA-filtered) | null, duration, at}}`, then its chat line from user `__intercom__`.
  Play `audio_b64` when present; the text always arrives.
- mod+: `POST /api/intercom/grant {user_id, rooms | null, note}`, `POST /api/intercom/revoke {user_id}`,
  `GET /api/intercom/grants`, `GET /api/intercom/history`. Signed in: `GET /api/intercom/status`.

### 7. Recording preflight and the start gate, 2026-11-27
- `POST /api/recording/preflight` now also takes `mode`, `record_data`, `planned_minutes`, and answers `machine`
  (ffmpeg, ffprobe, writable, free_bytes, estimated_bytes_per_minute, minutes_of_disk, outputs) and `gate`.
- `POST /api/recording/start` may answer **409** `{"detail": {"message", "refusals": [{code, message}], "machine"}}`
  (codes `no_ffmpeg`, `not_writable`, `disk_full`). A started take's response has `preflight: {warnings, issues,
  minutes_of_disk}`: show these to the director (e.g. "the disk holds 12 minutes of this take").
- A stop on a full disk answers 409 with "No space left ... stop the take again to retry": offer the retry.

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
7. (2026-11-27) The data-only e2e test fails most runs: a sound file 7.06 s against a 7.0 s bound. It fails the same
   way at 8fc67042, before the capture changes (RAN 4 of 4). Exact next task 2. See 8 for a likely cause.
8. (2026-11-27) Sound-only WAV files from network sources run longer than the take: 0.24–0.41 s over 2 minutes,
   0.30–0.88 s over 30 minutes (endurance, both RAN). The camcorder files' own sound (Opus in WebM) and the program's
   sound do NOT do this (within 0.07 s). Because the excess grows, part of it is drift, not a fixed start offset.
   GUESS at the cause: the WAV path writes every decoded sample with no clock correction, while the muxed
   files follow the input timestamps. The effect: a data-only reconstruction places each WAV by its measured
   start, so near the end of a 30-minute take its sound could sit up to about 0.9 s off the picture.
   Next step: measure a tone's phase against the camera clock along the file, then decide on `aresample=async`
   or timestamp-driven writing. Defect 7 (a 7.06 s file for a 6 s take) may be the start of the same thing.
9. (2026-11-27) Windows: `modules/child_lifetime.py`'s job object is NOT TESTED. If it fails, it logs one warning and
   recording works as before, but encoders may outlive a killed host there.
10. (2026-11-27) A live MP4/MOV is now a fragmented MP4. FFmpeg, browsers and the program assembly read it (RAN).
    Josie's editor: NOT CHECKED.

## Commit checkpoints
- a354092 Dissolves travel on the camera switch event
- 4a080d5 Capture: measure where every piece of picture and sound sits on the clock
- 5514272 Performer data, one pause window, and reconstruction from any camera
- 896da9a Guest audio: stop dropping a guest after a stall or a slow desk
- 5d5026c Capture: progress at FFmpeg's default interval; sound files written as they are made
- c91b6e2 Program audio authority: independent channels, solo, meters, and the intended mix
- c91b6e2 .. 9b47817: handoff; parts index (several commits)
- 8fc67042 Intercom: the director's PA, ported into the build
- 3fcdff9e Recording preflight: check the machine, and gate every start
- c344d400 READ notes: correct the preflight row
- 7c1809de Faults mid-take: crash-safe live files, encoders end with the host, a dead program encoder
- df765bbb Main camera: cuts keep up, the program stays on the clock; assembler tied to the host
- (next) endurance result, evidence, this handoff

## Dated log
- 2026-11-26 07:58–10:30 (Los Angeles): recovery comparison; base moved to ec7895a; renderer proven; dissolve fix;
  performer data; reconstruction; sound placement and one pause window; guest-audio dropout; channels, solo, meters
  and the intended mix. The e2e tests found and drove fixes for: black start of take, sound placement, an FFmpeg apad
  hang, the late pause window, meter blocks (256 KB writes), a missing file during input probing, and the
  `-stats_period` regression.

- 2026-11-27 01:00–04:00 (Los Angeles), after Josie's "break that up into a workflow and let's knock them off":
  - **Intercom**: ported, and proved through the real host (8fc67042).
  - **Preflight**: the build already had it, newer than the parked copy. The parts index had wrongly said it was
    not live; that is corrected. Extended with machine checks and a gate on every start (3fcdff9e).
  - **Fault tests**: through the real host. They found and drove fixes for:
    - crash-unsafe live files;
    - encoders outliving a killed host;
    - a dead program encoder misplaced, with the program cut short (7c1809de).
  - **First 30-minute endurance run** (code before df765bbb), all three modes at once, 89 cuts, 30 PA
    announcements:
    - host memory 195.6 → 197.4 MB;
    - every file decodes cleanly and runs 1800.06–1800.41 s for 1800.09 s of take;
    - picture and sound within 0.07 s of each other in every file.
    - It failed on one thing: the program ran 0.74 s long (the assembly's own warning).
    - That raw report was lost to pytest's temp-folder rotation; the numbers here are copied from this session's
      printout of it.
  - **A 4-minute run with a cut every 3 s** then found cuts falling 13 s behind. Both are fixed (df765bbb):
    80 of 80 cuts, median 92 ms late, program within 8 ms.
  - **The 30-minute run on the final code** (df765bbb): passed; see "Endurance" below.

## Regression run

RAN 2026-11-27 03:46, on df765bbb (the last code change). 46 test files in one run: every non-browser test file
whose name has record, capture, segment, production, reconstruct, switch, camera, studio_console, timeline,
preflight, intercom, program_audio, participant_audio, performance, range_pres, preservation, crash_safety or
faults.
Result: **473 passed, 2 failed, 3 skipped**, in 13 min 56 s. Neither failure is new:
- `test_recording_modes_e2e.py::test_data_only_records_no_picture_every_sound_and_the_show_data`: known defect 7.
  It fails the same way at 8fc67042, before the capture changes.
- `test_recording_pipeline_e2e.py::test_recording_holds_picture_and_sound_for_the_whole_take[broadcast_mp4-...]`:
  "no capture warnings" under load, the same as on 2026-11-26. Run alone right after: 2 of 2 passed. This
  includes the broadcast MP4 case, now written as a fragmented MP4.

The 3 skips: browser tests (Playwright's Chromium is not installed here). NOT RUN, not passed.
Not in this run: the full suite (over 3,000 tests).

Earlier, 2026-11-26: 40 files, 458 passed, 1 failed (the same broadcast_mp4 load case), 3 skipped.

## Endurance

`tools/acceptance/test_engine_endurance.py`, excluded from ordinary collection. Command (PowerShell 5):
`$env:PUBCAST_ENDURANCE_SECONDS = "1800"; python -m pytest -s -p no:cacheprovider tools\acceptance\test_engine_endurance.py`
(`PUBCAST_ENDURANCE_CUT_EVERY` sets the seconds between cuts; default 20). It needs UDP multicast on loopback and
FFmpeg, and it uses /proc to find encoders, so as written it runs on Linux only. NOT RUN on Windows.

RAN 2026-11-27 04:06–05:03 on df765bbb: **passed** (56 min 20 s including checking). All three recording modes
at once on one host (2 cores), two cameras, a cut every 20 s, a PA announcement every minute. The report and the
main-camera take record are kept in `evidence/engine-endurance-2026-11-27/`.
- 1800.17 s of take. Host memory 195.3 → 197.7 MB. 89 cuts and 30 announcements, none refused.
- Every cut recorded, median 29 ms late, worst 340 ms.
- Program: 90 pieces, 1800.141 s, expected 1800.133 s, no warning; picture and sound 0.001 s apart.
- Camcorder files 1800.166 s each; picture and sound within 0.07 s. Every file (7 whole files, 90 program pieces)
  decodes cleanly from start to end.
- Sound-only files (data only, and main camera's per-camera sound) ran **0.30 to 0.88 s longer** than the take
  (1800.47 to 1801.05 s). See Known defects 8: this grew from 0.24–0.41 s in a 2-minute run, so part of it builds
  up over time.
