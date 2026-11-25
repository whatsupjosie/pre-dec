# What we already made: the strongest version of each part, 2026-11-25

Task: "Find the best of what we've already made." Step one of three. Step two (plan and integrate) and step three (clean up, shape, embed) build on this file.

This file only reports. Nothing was merged, ported, deleted, installed or tested. No CI was touched.

Labels used below:
- RAN: a git or hash comparison I ran myself (no tests).
- READ: I opened the file or document and read it.
- LISTED: I only saw the name, size or date.
- GUESS: my judgment from the above.

Picks are by contents, dates and wiring, never by names like "best" or "final".

Reference point: the studio line, `claude/studio-wire-avatars-2026-11-23` (45de912, Nov 23), which contains `claude/studio-assembly-2026-11-23` (2541c09). Josie said "Yes." on Nov 24 to keeping the studio line.

## Summary

The studio line is the strongest running PubCast, and nothing found today beats it as a whole.

Six things that are stronger than what the studio line has, and live somewhere else:
1. Josie's Airlock (waiver, detention, sealed records) on the October-24 repo.
2. The fullest PEQ engine on the Pubcaast-Breaking-Dawn repo.
3. A Unified Camera Engine v2 that exists only in Google Drive.
4. A full Voice Dominance Index engine that exists only in Google Drive.
5. The Nov 22 PubPartner backend hardening on Beyond-October, which never reached pre-dec.
6. The Word (.docx) editing workspace for 2i, which exists only in a Drive zip.

## Per part

### 1. Studio and recording
- Strongest: the studio line. RAN: its browser store is the IndexedDB v3 design (`static/production25d_storage.js`, blob 0cc59be). That design records a SHA-256 for every chunk, holds leases, and recovers interrupted takes. READ (other threads' notes): it has FFmpegCaptureEngine, timeline transport and show clocks.
- Missing from it: the main-debug fixes. These are FFmpeg no-overwrite (`-n`), the Windows pause error, per-source failure persistence, the Rust renderer rebuild, Reach chat identity, the Counter readiness flag, two missing imports, and part of the camera config round trip. A parallel task is porting these, so this one doesn't repeat that work.
- RAN, Drive Nov 23 uploads: `capture (1).py`, `production_routes.py` and `camera_manager.py` are older versions of the studio line's files. All of their definitions are on the studio line, and the studio copies are larger.
- Candidates not on the studio line (RAN, by definition name):
  - Pubcaast-Breaking-Dawn, branch `claude/hubcast-horizon-base-u2b1oy` (Sep 7), file `WORKING_PROGRAM/pubcast/modules/pubcast_take_manager.py`. A TakeManager with take segments, composite and replay (22 definitions not on the studio line).
  - Pubcaast-Breaking-Dawn, `media_router.py`. A media library with ffprobe metadata and tags (18 definitions).
  - NowCurtsey-Build, `merge_9626/modules/capture_routes.py`. Capture router with pause and resume (8 definitions).
  - GUESS: these overlap the studio line's own take handling. Compare behavior before bringing any of them in.

### 2. Cameras and shot direction
- Strongest running: the studio line (`camera_manager`, `camera_pool`, `cameras_advanced`, `director_engine`, `rust_camera_runtime`, `studio_camera_preflight`).
- Stronger design, not wired: Drive `camera_engine.py` (Download folder, uploaded Nov 23). Its header calls it "PubCast Unified Camera Engine v2". It is 1,083 lines with 99 definitions, including SceneGraph, ShotResolver, ShotQueue, TargetTracker, TickLoop at 30 fps, StudioEventBus and proactive fallback levels. Its math is noted as mapping one to one to glam in Rust.
  - RAN: none of its classes exists in any pre-dec, Beyond-October or older-repo branch tip. Line overlap with any camera file is 2% or less.
  - READ: header and class list only, not the body.
  - GUESS: the strongest camera-intent design we have. Bring it in as a donor file, then decide whether director_engine takes on its ShotResolver.

### 3. Audience read and voice (VDI)
- Drive `vdi_engine.py` (Download folder, 23.5 KB) is a full Voice Dominance Index engine. Its formula is VDI = 0.35 LAI + 0.40 CBS + 0.25 CCI, and it has chat, reaction and content ingestion and zones.
  - RAN: 20 of its 24 definitions are in no repo. The `modules/evo/vdi_engine.py` that sits in pre-dec and six older repos is a different, smaller 13.7 KB file with 4% line overlap.
  - Not wired anywhere. GUESS: strongest VDI.
  - Drive `vdi_engine (1).py` is the smaller repo version (RAN, size match).

### 4. 2i writers room
- Strongest running: the studio line's `2i/writers-room-v22.html` (171 KB), which builds on main's 169.9 KB copy. Josie's rule from the 2i chat: "v 12 is correct" (v12 is the 2i base).
- Not in any repo: the Nov 16 zip `2i-Unified-Beta-2026-11-16.zip` (Drive, 4.8 MB) holds:
  - `2i/2i-assets/docx-workspace.js` (File, Open Word document)
  - a standalone launcher, `2i/open_2i.py` and `Open 2i.cmd`
  - `START_HERE.md`
  - RAN: 24 of its 34 source files match known blobs. Its other assets are older than the studio copies: the studio has more lines in `reach.js`, `file-workspace.js` and `format-menu.js`.
- RAN: main got the offline DOCX engine files on Nov 18 (d993d26, `2i/2i-assets/vendor/docx/`). But the writers room on main and on the studio line never mentions docx, so the engine is present and unused. The zip's copy loads `2i-assets/docx-workspace.js`.
  - GUESS: the Word feature needs the zip's `docx-workspace.js`, plus its menu hooks ported onto the studio's newer writers room.
- Still open from the plan: decision 9 (the 2i-beta-polish look, and whether to drop the typewriter-visual branch).

### 5. Alex, EQ and PEQ
- EQ: the studio child `claude/eq-foundations-2026-11-23` (5ef002f) has the shadow EQ layer, off by default. Eight designs are not built. The 0.4 "everyday wins" tier is waiting on Josie's yes.
- PEQ engine: strongest is Pubcaast-Breaking-Dawn, branch `claude/hubcast-horizon-base-u2b1oy` (Sep 7), folder `WORKING_PROGRAM/pubcast/modules/peq/`. RAN against both donor copies already in pre-dec (`recovery/2026-11-23/donors/peq_v0_1_hardened_two_passes`, `peq_v0_1_backbreaker_hardened`, on `claude/rediscovery-early-repos-2026-11-23`):
  - Breaking-Dawn loses no definition. It adds 2 to `state.py`, 1 to 4 to `system.py`, and is larger in every file.
  - The same branch has `peq_broker.py` (PEQBroker, signals, subscribers) and `peq_integration.py` (observe and avatar-subscribe routes). Neither is on the studio line.
- This is the source the lost Nov 22 peq-engine-port came from (see Lost work).

### 6. PubPartner
- Strongest backend: Beyond-October `gpt/pubpartner-backend-hardening-2026-11-22` (a594d30, 24 commits). RAN: it contains B-O main, and none of its new files are in pre-dec. Its commits cover:
  - Blackbox Light full-dialogue archive
  - owner-scoped backups
  - traversal fixes
  - calibration approval feeding the RelationshipEngine
  - five tests
- Same date, separate lines, also not in pre-dec (RAN):
  - `gpt/pubpartner-identity-checkpoint-2026-11-22` (2e2c1e3): a one-second identity checkpoint before each reply.
  - `gpt/pubpartner-unification-foundation-2026-11-22` (a29149d): an authority map, plus neutral open-ended feeling-and-cause questions before emotion inference.
- When bringing them over, leave out `.github/workflows/pubpartner-*.yml`, per her no-CI rule. B-O commit notes say runtime tests are pending.
- pre-dec side: `feat/pubpartner-cartridge-context-2026-11-22`, and `gpt/pubpartner-portable-2i-2026-11-22`. The studio line took calibration from B-O 0dab95f.
- Pub-Partner-Base-Horizon repo, branch `claude/federation-merge` (Sep 7): `companion_mode.py`, `link.py`, `avatar_preference.py` and federation tests. RAN: not on the studio line. Source of the lost base-horizon-link port.
- Drive `horizon_ref_pubpartner_relationship_engine.py` is the same size as a test file already in pre-dec recovery (RAN, size only).

### 7. Airlock, waiting room, Sir Purfluous
- Strongest Airlock: October-24 repo, branch `airlock-waiver-detention-2026-10-28` (ca0e929, Oct 28).
  - `modules/airlock.py`: 1,274 lines. Its header says "Josie's design (2026-10-28 conversation)". It covers the waiting room with no links, being pulled in by someone inside, the waiver the owner and the owner's AI both sign, detention and sealed records. READ: header.
  - `modules/airlock_routes.py` (28 definitions not on the studio line) and `tests/test_airlock.py`. RAN: AirlockEngine is on no pre-dec branch.
  - The studio line has only `modules/airlock_guard.py` and `tests/test_airlock_arrivals.py`. Source of the lost airlock-port.
- Sir Purfluous: newest is `claude/purfluous-more-cards-2026-11-24` (a959a35). READ its diagnostics handoff: soak (1,000 replies, 0 errors), fuzz (58 inputs, 0 errors) and routing 37 of 37.
  - Its own full-suite run reports 2,885 passed, 13 failed, 17 errors. The author traced none of them to that day's work. That was their run, not mine.
  - Untangle from Code Collector by cherry-pick (plan doc).

### 8. Runtime spine, physics, voxel and render
- Strongest running: the studio line, which already joins the June runtime spines (Big Zip harvest, READ).
- Donor candidates, RAN by definition name, not on the studio line:
  - Wednesday- repo, branch `Dinner` (May 8), `runtime/`: `boot_sequence.py` (30 spine API routes), `state_authority.py` (transactions), `boot_order.py`, and the world, motion, AI-router, persistence and avatar services. The harvest called this a parallel design, and that still holds.
  - DREAMS repo, branch `New-Twin-Pubcast-Rust-Pythos-duo` (Apr 14), `distributed_engine_node_close_loop.py`: VideoEncoder, AudioProcessor, MeshGenerator, VoxelRenderer and RustRendererBridge (24 definitions). Also `pubcast_bridge_final_review.py`, a spooled wire bridge.
  - NowCurtsey-Build, `merge_9626/theater_render_pipeline/.../voxel_renderer_lighting_fixed.py`: LOD selector and lighting (15 definitions).
  - The Big Zip task found `distributed_engine_node_real.py` in the friday zips (its notes).
- GUESS: keep the studio spine. Take the DREAMS and friday encoders only if the renderer needs them.

### 9. Avatar motion
- Thursday- repo, branch `avatar-motion-spine-upload-integration` (May 9): `avatar_motion_spine.py` (router, runtime doctor), `avatar_motion_bridge.py`, `avatar_performance_cues.py` (the harvest's "Thursday cue catalog") and `nervous_system_routes.py`. RAN: none on the studio line.
- The studio line has `claude/studio-wire-avatars-2026-11-23`. GUESS: the cue catalog is the useful piece. The spine overlaps the studio's own.

### 10. Twin engine and Pete
- Drive `twin_engine_service (1).py` and `pubcast_twin_engine_service (1).py`: RAN, hash-identical to the pre-dec copies.
- Drive `epete.py`: identical to NowCurtsey and October, and 99% of its lines are in the studio's `modules/evo/epete.py`.
- Drive `pete_enhanced.py`: older. The studio's 47 KB copy has 21 more definitions.
- Strongest: the studio line.

### 11. Other pieces
- Pub-Experiment, branch `pubcast-v5-6-web-cargo-ready-20260710` and others: a 75 KB `main` with prototype and prop routes (74 definitions not on the studio line), a multi-provider `bot_llm_adapter`, and a `rust_crate` renderer gate. LISTED by definition name only.
- Pubcast-Phase-2-, `modules/split_llm.py` (Mar 29): SplitLLMManager and TaskRouter. The studio's `split_llm.py` is a different, smaller file. RAN.
- Drive `pubcast_patch (1).py`: a one-time Phase-1 setup script that writes into `control.html`. It is in no repo. GUESS: superseded; don't run it.
- Iteration Wallet is its own product. Its repo has `vault_engine_v3.py` and `app_v3.py`. Not judged here.
- Code Collector: `claude/code-collector-2026-11-24` (48bc039). Its tracked `code_collector/node_modules` symlink points at a scratch path and is broken (plan thread, RAN). Removing it waits on her yes.

## Lost work (Nov 22 Big Zip ports)

RAN on Nov 24: these port branches are on no branch on GitHub, and no bundle of them is in Drive. Sources located today:
- airlock-port: October-24 `airlock-waiver-detention-2026-10-28`.
- peq-engine-port: Pubcaast-Breaking-Dawn `claude/hubcast-horizon-base-u2b1oy`, `modules/peq/`, `peq_broker.py`, `peq_integration.py`.
- pubpartner-base-horizon-link: Pub-Partner-Base-Horizon `claude/federation-merge`.
- dressing-room-lock, bridge-file-heartbeat, recording-fidelity-lock and vdi-shot-smoothing: sources not located in this pass. GUESS: vdi-shot-smoothing relates to the Drive VDI and camera engines in sections 2 and 3.

## Keep out of pre-dec (pre-dec is public)

- The-Prime is public and holds a secret key file and a grievance file. Take nothing from it wholesale. Its `main.py`, `memory_routes.py` and `app.py` show many definitions not on the studio line (RAN), but read them before taking any piece.
- Runtime data (`data/secure`, `users.db`, vaults, Blackbox recordings) never goes in.
- Preserve the Alex vessel blob 96fa66a728d07d5ff43b0d3d7fc17a466765cec1.

## What I read versus only listed

- RAN: every branch tip of 19 older repos.
  - Every source file's blob was checked against all of pre-dec and Beyond-October history: 7,250 known blobs.
  - All 757 older-repo Python files not found there were fetched and checked by definition name against the studio line.
  - Name matches can hide different bodies, and different names can hide the same code.
  - Older-repo history below the branch tips was not compared.
- RAN and READ: the ten Drive Nov 23 Python files I downloaded, plus hash matches for the rest by size. The Nov 16 2i zip, unpacked and hashed.
- READ: the handoffs BIG_ZIP_HARVEST, LOOSE_PARTS_INVENTORY, STUDIO_ASSEMBLY, the first part of HANDOFF_ONE_SOURCE, PURFLUOUS_DIAGNOSTICS, and other tasks' notes (merge plan, recording designs, Big Zip, EQ).
- LISTED, not opened:
  - The ten zips and seven Markdown files in the Drive Download folder (Nov 23). These include PubCast_AI_v7_Complete, pubcast_engine_full, pubcast_camera_engine, the camera vision zip, the ui menu workset, Actor Academy v0.1, the v7 wiring parts, pubcast_alpha_github, friend_core_package, the Reach 2.5D stage spec, the voxel wiring plan and the EQ vision.
  - `PubCast_Reach_COMBINED_EMPATHY_EQ_2026-10-02.zip` (12.5 MB, over Drive's 10 MB download limit).
  - The older bundles (pubcast_full_bundle 49 MB, the Apr 16 integrated bundle 23 MB, the run bundle).
  - The Big Zip harvest's 2,276 Drive-only items, still unclassified.
- Waiting on Josie: she said she will unzip Ring Me Jeeves Parts, pucastpy and pub, and the beefed codex_construction zip into the Drive folder "big zip". Those can be compared once they are there.
- `recovery/beyond_october/` (108 files) is taken from the merge plan task's notes, not re-read.

## Renderer (added 2026-11-25, asked for first)

Question: which build draws avatar pictures for the virtual cameras, and which can turn takes that hold only data into video.

Draws avatar pictures for a virtual camera today:
- `static/camera_avatar_live.js`, `static/camera_avatar_live.html` and `modules/camera_view_routes.py`, from commit d11a1ff (Nov 21). This is on the studio line, and its router is mounted in `main.py`.
- READ: it draws one GLB avatar in three.js, from the pose of a registered camera read from CameraManager. It moves the bones through `static/avatar_glb_motion_consumer.js`. With `publish=1` it sends JPEG frames to `/api/studio25d/media/frames/<camera>` every 250 ms.
- Its motion source is a demo performer (a host-clock wave and breath), and its own docstring says so. It does not read takes.

Records stage pixels to video, live only:
- `static/stage_3d.html` with `static/studio_take_recorder.js`, on the studio line.
- READ: it captures the 3D stage canvas at 30 fps, mixes the audio, and records with the browser's MediaRecorder.

Turns a data-only take into video: no build does this end to end.
- GUESS: the shortest path uses parts already on the studio line. Replace `demo_motion` in `camera_view_routes.py` with motion played back from the take on the timeline transport. Then record the `camera_avatar_live` canvas the way `studio_take_recorder.js` records the stage, or send its frames through FFmpeg.
- DREAMS `distributed_engine_node_close_loop.py` (e4bb5c7) has a VideoEncoder that pipes raw frames through FFmpeg to libx264 or VP9. It could be a server-side encoder.

The Rust GPU renderers (READ headers, RAN signal counts). All of them draw to a window surface with wgpu and winit. None reads frames back, and none is compiled.
- `run2_rust/renderer.rs` (422 lines)
- `rust_crate/pubcast_renderer_hardened.rs` (471 lines). It says headless start "fails honestly".
- `run2_rust/pubcast_renderer_v5_5_ready.rs` (711 lines)
- `rust_crate/pubcast_renderer_built_on_claude.rs` (823 lines). The largest. Its header says voxel meshing, the Python to Rust bridge and scene mesh extraction are still not solved.
- Also `run2_rust/voxel.rs`, `voxel.wgsl` (camera uniform plus a flat colour shader), `scene.rs` (avatars with skeletons) and `skeleton.rs`.
- RAN: `rust_crate/Cargo.toml` builds only `ws_renderer` and lists no wgpu, winit or image crate. `run2_rust/` has no Cargo.toml, and the donor `.rs` files sit outside `src/`. So the shipped `bin/ws_renderer` cannot draw. It tracks state and replies over the WebSocket.
- GUESS: `pubcast_renderer_built_on_claude.rs` is the strongest Rust starting point. It would need an offscreen texture and readback before it could feed video.

Not renderers, though they sound like them:
- `modules/bridge_bulletproof.py`: the twin-engine bridge, moving data over shared memory, TCP or files. It makes no pictures. The largest version is 1,336 lines, blob 54f614cc.
- `modules/wired/voxel_renderer.py` (30,752 bytes, the same as the four Drive copies of Jun 10): it builds LOD voxel meshes as compressed binary. It makes no pictures.
- NowCurtsey `voxel_renderer_lighting_fixed.py`: meshes plus lighting.
- `static/foresight_matter.cpp`: the only C++ found. It is a material renderer (WASM) for the Foresight Counter trays, not for avatars.
- The Thursday GLB motion consumer bridge, under `recovery/2026-11-23/rediscovery/thursday_animation/` on `claude/rediscovery-early-repos-2026-11-23`: behavior animation, presets and a retargeter. It feeds avatar motion and outputs no pixels.

Not found: a C++ voxel engine, in any repo branch tip or by Drive title. The voxel inventory (Drive `CODEX_VOXEL_ENGINE_INVENTORY_AND_WIRING_PLAN_20260617.md`, READ) points to `engine.rs` inside `podcast_ai_voxel_engine_COMPLETE.zip`. That zip was not opened this pass.
