# READ notes: what Claude has actually read

Every entry here was read by Claude on the date shown, and says how much was read:

- **READ (full)**: every line;
- **READ (structure)**: the module docstring, every class and function with its first doc line, and its routes;
- **READ (differing lines)**: only the lines that differ from the current file (the near-identical files).

A verdict compares the file with `finish/control-room-engine` as it stands on that date. "Harvest" means it holds
something the build lacks and it is worth porting. Nothing has been ported yet unless the entry says so.

Fingerprints are git blob ids. To read a stored copy: `git hash-object` on any copy you have will give the same id,
and every location is listed in `zip_contents_index.tsv`.

## 1. The 84 near-identical engine-related files: READ (differing lines), 2026-11-26

These are files with 1 to 5 lines that the current file of the same name doesn't have. Every one of those lines was
read, along with up to five lines the current file has instead.

**Result.** Three files (six rows, counting versions) hold something real (bold below). Two need a closer read. The rest are older forms of the
current file: bare imports where current uses package imports; no ReachAuth where current has it; utcnow, .json() or
md5 where current uses the modern call; header-only differences; or tests of behavior that current deliberately
changed.

| File | Fingerprint | Compared with (current) | Verdict |
|---|---|---|---|
| NUDGE_MINIMAL.py | `b2a0a502d3` | modules/wired/NUDGE_MINIMAL.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| __init__.py | `4f6fd08fcb` | modules/bubble_stack_pikpc/__init__.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| affect_choreo_bridge.py | `33e67ad855` | modules/affect_choreo_bridge.py | Older version; the current file holds everything here plus later fixes. |
| audio_devices.py | `34366e3d24` | modules/audio_devices.py | Older version; the current file holds everything here plus later fixes. |
| audio_devices.py | `ccf5328485` | modules/audio_devices.py | Older version; the current file holds everything here plus later fixes. |
| avatar_assets.py | `5dc176d7e9` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/avatar_assets.py | Older version; the current file holds everything here plus later fixes. |
| bots.js | `0151e21bc9` | static/bots.js | Older version; the current file holds everything here plus later fixes. |
| byok_manager.py | `fc832a2551` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/byok_manager.py | Falls back to a built-in per-character system prompt ('Belle Époque Studios'); current recovery copy is shaped differently. NOT judged: needs a closer read. |
| cc_memory_store.py | `63615e84c2` | modules/cc_memory_store.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| cc_memory_store.py | `82c1409e6e` | modules/cc_memory_store.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| character_cast.py | `b645223bc7` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/character_cast.py | Display name 'Sir. Purfluous' and extra aliases ('sir purfluous', 'sir. purfluous'). Current canon spells it 'Sir Purfluous'; the aliases are harmless additions. Josie's call. |
| character_cast.py | `c81c798656` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/character_cast.py | Display name 'Sir. Purfluous' and extra aliases ('sir purfluous', 'sir. purfluous'). Current canon spells it 'Sir Purfluous'; the aliases are harmless additions. Josie's call. |
| choreo_demo.js | `2d7b20ec1c` | static/js/choreo_demo.js | Older: connects without ReachAuth / role checks the current file has; current is better. |
| choreography.html | `0c0408735a` | static/choreography.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| choreography_runtime.py | `e308c7512f` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/choreography_runtime.py | Comment/header or encoding-only difference; same behavior. |
| companion_runner.py | `ae72d4a350` | modules/wired/companion_runner.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| context_block.py | `a07866a22a` | modules/context_block.py | Comment/header or encoding-only difference; same behavior. |
| director.py | `e72a58ded8` | modules/wired/director.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| jeremy.py | `b64e61066d` | recovery/2026-11-23/rediscovery/rearview_foresight_memory_layer/rear_view_foresight/thinking_context/jeremy.py | Older version; the current file holds everything here plus later fixes. |
| jeremy_cricket.py | `026bfc7312` | code_collector/_moved_out/Thinking_Context_Collector/jeremy_cricket.py | Checks user ids starting 'bot_' where current checks 'bot-'. Which prefix bots use decides; not engine. |
| lighting_engine.py | `652c38e2fe` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/lighting_engine.py | Comment/header or encoding-only difference; same behavior. |
| locomotion.py | `50ca083dc3` | runtime/spine/performers/locomotion.py | Older version; the current file holds everything here plus later fixes. |
| main.rs | `eec74583dc` | pubcast_camera_recovery/src/main.rs | **HAS SOMETHING:** runs the Rust camera engine as a newline-JSON server (ffi::run_json_server). Part of the camera-engine bundle in section 2. |
| map.html | `dc61216be1` | static/map.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| memory_routes.py | `1ee54eb69a` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/memory_routes.py | Older: connects without ReachAuth / role checks the current file has; current is better. |
| mic_processor.js | `9bfeea63d4` | static/mic_processor.js | Older version; the current file holds everything here plus later fixes. |
| mic_profiles.js | `b96caced53` | static/mic_profiles.js | Older: connects without ReachAuth / role checks the current file has; current is better. |
| mic_routes.py | `ccd7273010` | modules/mic_routes.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| mocap_integration.py | `903464a075` | recovery/2026-11-23/rediscovery/motion_capture_v7/PubCast_All_Files_From_Chat_v2_MOCAP/pubcast_all_files/modules/mocap_integration.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| mocap_precision.py | `b15e9cf903` | modules/mocap_precision.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| performer_registry.py | `5c4a2042c9` | runtime/spine/performer_registry.py | Older version; the current file holds everything here plus later fixes. |
| pete_enhanced.py | `0424e4af73` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/pete_enhanced.py | Older version; the current file holds everything here plus later fixes. |
| production_routes.py | `fb7218d080` | recovery/2026-10-21/communications/modules/production_routes.py | Older version; the current file holds everything here plus later fixes. |
| program_audio_routes.py | `064810ad3d` | recovery/2026-10-21/communications/modules/program_audio_routes.py | Older: connects without ReachAuth / role checks the current file has; current is better. |
| program_audio_runtime.js | `bbac7b2f4f` | recovery/2026-10-21/communications/static/program_audio_runtime.js | Older version; the current file holds everything here plus later fixes. |
| pub_manager_recovery.py | `99a2168e07` | modules/pub_manager_recovery.py | **HAS SOMETHING:** a 'websocket.reconnect' recovery action and suggestion when the WebSocket is unhealthy; not in current modules/pub_manager_recovery.py. |
| pub_manager_recovery.py | `c48a907758` | modules/pub_manager_recovery.py | **HAS SOMETHING:** a 'websocket.reconnect' recovery action and suggestion when the WebSocket is unhealthy; not in current modules/pub_manager_recovery.py. |
| pubcast_room_layout.py | `be98f2908c` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/pubcast_room_layout.py | Comment/header or encoding-only difference; same behavior. |
| pubcast_vision_routes.py | `e2064b9e15` | modules/pubcast_vision_routes.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| pubcast_voxel_hollow_patch.py | `b179a3ad0b` | modules/wired/pubcast_voxel_hollow_patch.py | Comment-only difference: the usage line shows the PowerShell form (.\.venv\Scripts\python) where current shows plain python; same behavior. |
| pubworld.py | `9997094276` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/pubworld.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| pubworld_stage.html | `62f17d4578` | static/pubworld_stage.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| pubworld_stage.html | `ac3478d947` | static/pubworld_stage.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| purfluous.py | `3fdf05063c` | recovery/2026-11-23/rediscovery/pete_purfluous_nudge_early/purfluous.py | **HAS SOMETHING:** 'last_nudge_ago' is None when never nudged (current modules/room_conductor.py:813 rounds the time since an unset nudge); also accepts 'bot-' as well as 'bot_' users. Small real fix to port to room_conductor.py. |
| purfluous.py | `ffaefd1350` | recovery/2026-11-23/rediscovery/pete_purfluous_nudge_early/purfluous.py | **HAS SOMETHING:** 'last_nudge_ago' is None when never nudged (current modules/room_conductor.py:813 rounds the time since an unset nudge); also accepts 'bot-' as well as 'bot_' users. Small real fix to port to room_conductor.py. |
| purfluous.py | `2fc9fbe5de` | recovery/2026-11-23/rediscovery/pete_purfluous_nudge_early/purfluous.py | **HAS SOMETHING:** 'last_nudge_ago' is None when never nudged (current modules/room_conductor.py:813 rounds the time since an unset nudge); also accepts 'bot-' as well as 'bot_' users. Small real fix to port to room_conductor.py. |
| recording.py | `5b56434dbc` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/recording.py | Older version; the current file holds everything here plus later fixes. |
| recording.py | `596fd79dc4` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/recording.py | Older version; the current file holds everything here plus later fixes. |
| recording.py | `7bbfd2dc02` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/recording.py | Older version; the current file holds everything here plus later fixes. |
| response_composer.py | `08565b5a8a` | modules/wired/response_composer.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| room_conductor.py | `2fcf4657f0` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/room_conductor.py | Older version; the current file holds everything here plus later fixes. |
| runtime_control_routes.py | `05b19f85e0` | modules/runtime_control_routes.py | Comment/header or encoding-only difference; same behavior. |
| scene.rs | `e567a7d932` | run2_rust/scene.rs | Older version; the current file holds everything here plus later fixes. |
| schema.py | `697fd92214` | blackbox_event_language/schema.py | Older version; the current file holds everything here plus later fixes. |
| sir_purfluous_character_profile.py | `14ec08ab14` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/sir_purfluous_character_profile.py | Display name 'Sir. Purfluous' vs current 'Sir Purfluous'. Josie's call (spelling). |
| stage_3d.html | `ee180b854a` | static/stage_3d.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| stage_3d.html.pre_beefup_20260614.bak | `79654446fd` | static/stage_3d.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| stage_panoramic.html | `6aa9b7c0fb` | static/stage_panoramic.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| stage_panoramic.html | `dad67084ab` | static/stage_panoramic.html | Older: connects without ReachAuth / role checks the current file has; current is better. |
| studio_control.py | `e1f592c6b3` | recovery/2026-11-23/rediscovery/motion_capture_v7/PubCast_All_Files_From_Chat_v2_MOCAP/pubcast_all_files/modules/studio_control.py | Older version; the current file holds everything here plus later fixes. |
| switcher.js | `9ceb882332` | static/switcher.js | Older version; the current file holds everything here plus later fixes. |
| test_00_integrity.py | `640a20fc8d` | tests/test_00_integrity.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_alex_foundation_pass.py | `d9d5e4653f` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/tests/test_alex_foundation_pass.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_hardening.py | `cd039ffa49` | modules/wired/test_hardening.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| test_hardening.py | `000a76d5d3` | modules/wired/test_hardening.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| test_module_router_parity_guards.py | `33e648657f` | tests/test_module_router_parity_guards.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_orchestrator_streaming.py | `ead409d713` | tests/test_orchestrator_streaming.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |
| test_pubcast.py | `fa98a38f4a` | tests/test_pubcast.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_ready_wiring_routes.py | `c185191bac` | tests/test_ready_wiring_routes.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_round5_filesystem_collision_guards.py | `3261250672` | tests/test_round5_filesystem_collision_guards.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_runtime_spine.py | `073550f69c` | tests/test_runtime_spine.py | Test asserting older behavior the current code deliberately changed; keep current. |
| test_sync.py | `9f467d0078` | tests/pubpartner_federation/test_sync.py | Test asserting older behavior the current code deliberately changed; keep current. |
| universal_memory_system.py | `ec9f2a67d6` | modules/universal_memory_system.py | Comment/header or encoding-only difference; same behavior. |
| universal_memory_system.py | `0d84bb7547` | modules/universal_memory_system.py | Comment/header or encoding-only difference; same behavior. |
| userdb.py | `452f88635e` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/userdb.py | Older version; the current file holds everything here plus later fixes. |
| vault_engine.py | `0566a0771d` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/vault_engine.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| vault_engine.py | `86df93b758` | recovery/2026-11-23/rediscovery/pubpartner_horizon_prebeta12/modules/vault_engine.py | Older API (utcnow, .json(), md5 or get_event_loop) where current uses the modern form; nothing new. |
| vault_v21.py | `a3221466d4` | iteration_wallet/vault_v21.py | Older version; the current file holds everything here plus later fixes. |
| vault_v21.py | `56e1c1ecfa` | iteration_wallet/vault_v21.py | Older version; the current file holds everything here plus later fixes. |
| visual_patch_voxel_adapter.py | `d9bb775290` | modules/visual_patch_voxel_adapter.py | Older version; the current file holds everything here plus later fixes. |
| voxel_asset_manager.py | `53130983cd` | modules/voxel_asset_manager.py | Older version; the current file holds everything here plus later fixes. |
| voxel_set_contract.py | `ce44a5b14e` | modules/voxel_set_contract.py | Older version; the current file holds everything here plus later fixes. |
| voxel_studio.py | `5099d702ef` | modules/voxel_studio.py | Has a 'bake every loaded object to file' path the current file may lack (current writes the GLB directly). NOT judged: needs a closer read. |
| wired_server.py | `ec0249e537` | modules/wired/wired_server.py | Older: bare imports where the current file uses package-relative ones; no new behavior. |

## 2. The April 2026 camera-engine bundle (DREAMS repo, inside zips), 2026-11-26

Where it is: GitHub DREAMS, branches main, april-branch-1 and april-branch-2.
`dreams_repo_import_package_2026-04-06.zip >> archives/source-zips/pubcast_integrated_consolidated_program_2026-04-06.zip > full_pubcast_extracted/build/`.
The same files also sit in `vbg4bg4pubcast_2026-04-05.zip` and in `pubcast_core_separate_bundle_2026-04-06.zip > core_extracted/`.
None of it is in any repo branch outside those zips.

| File | Read | What it is | Verdict |
|---|---|---|---|
| `rust_camera/src/ffi.rs` (`31df1fb5d7`) | READ (full) | Runs the Rust camera engine as a newline-delimited JSON server on stdin/stdout. Methods: status, world, tick, take, set_program, set_preview, packets, program_packet, update_object, fallback (four levels), recover. | **Harvest candidate.** The current crate `pubcast_camera_recovery/` has no process interface (its main.rs only prints a demo). This is the missing bridge between Python and the Rust camera engine. It would need porting to the current crate's types, not copying. |
| `rust_camera/src/shot.rs` (`3bb6b42da8`) | READ (full) | Shot queue: a TargetSpec carries intent (framing goal, follow behavior, headroom, eyeline, hands in frame, avoid occlusion); a ShotSpec has a priority, targets, a lens override, cue conditions and fallback shots; the queue is sorted by priority. | Superseded in idea. The current crate has `camera/shot_queue.rs` and `camera/targeting.rs`. The TargetSpec fields (eyeline, hands, occlusion) are worth checking against the current targeting. |
| `rust_camera/src/world.rs` (`48ff709c07`) | READ (first 70 of 296 lines) | The virtual world the cameras film: Transform3D with distance, lerp, yaw/pitch toward. Cameras know every object and re-render rather than rebuild. | The current crate has no world module (only `scene/`). Not judged further: the rest of the file is unread. |
| `rust_camera/src/main.rs` (`eec74583dc`) | READ (full, 3 lines) | Calls `ffi::run_json_server()`. | With ffi.rs. |
| `modules/rust_camera/virtual_camera_engine.py` (`12f3aec8`) | READ (structure) | The Python twin of the Rust engine: SceneGraph with frustum query, TargetTracker, ShotEvaluation, a four-level fallback ladder, VirtualCamera, and parallax offsets for stage.html. | Superseded. The current `modules/camera_engine.py` ("Unified Camera Engine v2", 1,083 lines) has all of it plus ShotResolver, ShotQueue, TickLoop and StudioEventBus. Note: nothing in main.py or modules/ imports `modules/camera_engine.py`; the live authority is `modules/cameras.py` CameraManager. |
| `modules/control_room.py` (`1b2a9cfb`) | READ (lines 1 to 300 of 358) | A take state machine: Idle, SlateRaised, Ready, ActionInitiated, Preroll (5 s), LiveTake, Cut, Cancelled. It hands scene camera assignments to the engine at slate. ACTION is broadcast to the set but marked not captured in output, with studio-only audio zones (writers room, lobby and dressing room excluded). | Ideas only. The current `modules/studio_slate.py` is stronger: it persists across restarts, is director-authenticated, and has phases idle/standby/take/ended with a clap. Worth taking over as ideas: a preroll before live, and the ACTION signal kept out of the recorded output with zone-limited audio. |
| `modules/virtual_camera_routes.py` (`1b422de2`) | READ (structure) | REST plus `/ws/vcam` at 15 fps serving the engine's last tick (status, state, cameras, scene, program frame, set program/preview, target, fallback, update object). | Superseded by the current camera routes. |

## 3. Recording, capture and timeline: older versions, 2026-11-26

READ (structure) for all of these, compared with the live files.

| File | Versions in zips | Verdict |
|---|---|---|
| `capture.py` | `0f5d6018` (Prime canon, 274 lines) | Older: one FFmpeg per source, pause by SIGSTOP. Current `modules/capture.py` has everything here plus 829 more lines. Nothing to harvest. |
| `recording.py` | `4fb48406`, `5fbd53c0` (714 lines); `5b56434d` (635); `596fd79d`, `7bbfd2dc` (573) | Older forms of the live `modules/recording.py` (64,785 bytes): every method listed exists there (mark_moment, privacy_matrix, record_camera_switch, export/import). Nothing to harvest. |
| `timeline.py`, `timeline_routes.py` | `8d034073`, `355d9fab` | Older forms of the live ones (main.py wires timeline_routes at line 1350). Nothing to harvest. |
| `recording_pipeline_routes.py` | `ab8204ce` | Older form of the live one (EDL and FCPXML export, markers). Nothing to harvest. |
| `recording_evo_bridge.py` | `f8b9143b` (`Slightly older still good... zip` on Drive, id 1SwzA3x5iZmwBRrrxnC0aNUlXHE674Sy1, `>> pubcast_ai_complete/pubcast_build/pubcast_evo_FINAL.zip > pubcast_evo/`) | **Idea worth keeping:** when recording starts, EVO's level-of-detail is locked to full fidelity ("every frame matters") and released at stop. Not in the current build. It patches RecordingService's start/stop by monkey-patching, which should not be copied; the policy should be a recording-mode hook. |

## 4. Native renderer, camera crate and performer files, 2026-11-26

| File | Read | What it is | Verdict |
|---|---|---|---|
| `renderer.rs` (`480d687f`, 914 lines). Where: DREAMS branch New-Twin-Pubcast-Rust-Pythos-duo, `pubcast_engine_locked_bundle.zip >> pubcast_renderer_workspace_fixed2.zip > pubcast_renderer_workspace/src/renderer.rs` | READ (first 60 lines and every item name) | A native wgpu renderer: frame budget (16.67 ms target, 33.33 ms ceiling, quality drops at 13.34 ms), mesh pool with LRU eviction, metrics, camera uniform, and a real fallback draw path. Its header says it does NOT yet do voxel meshing, the Python-Rust bridge, real telemetry or scene-driven meshes. | **Candidate for a native renderer backend**: nothing like it is in the build (`experiments/prime_rust_recovery/src/renderer.rs` is a 206-byte trait). NOT compiled here. It needs a GPU or a software Vulkan, so per the build rules it could only ever be optional. Josie's call. |
| `camera.rs` (`f62299b1`, 431 lines), `engine.rs` (`9492afcb`), `fallback.rs` (`b01a2a5a`), `packet.rs` (`8e2d88ed`), `lib.rs` (`dc1766fd`): the April 2026 `rust_camera` crate from section 2 | READ (every item name and comment) | VirtualCamera with roles, operator and intent modes, lens profiles (wide, medium, close-up, overhead), shot queue, follow, scene truth, a fallback ladder and packets. CameraEngine: program/preview/take, assign scene, distribute scene truth, tick, packets, the PubCast lineup. | Same family as the current `pubcast_camera_recovery/` crate (camera/, control_room/, scene/), which is larger. What the April crate has and the current one lacks: the JSON server (ffi.rs), world.rs, per-shot lens profiles. |
| `camera.rs` (`05e77446`), `scene.rs` (`e567a7d9`), `lib.rs` (`ff030dce`), `render_window.rs` (`ca482871`), all from the renderer workspace | READ (item names) | The wgpu workspace's view-projection camera, an empty SceneManager (7 lines), and a window example. | Parts of the renderer.rs entry above. |
| `ws_renderer.rs` (`7d2e8d12`) | READ (item names, comments) | WebSocket avatar renderer tick loop. | Older than the current `rust_crate/src/ws_renderer.rs` (7 lines only here, 47 only in current). Nothing to harvest. |
| `voxel.rs` (`5655718e`) | READ (item names) | Voxel chunks and a mesher. | Older than the current `run2_rust/voxel.rs`. Nothing to harvest. |
| `facial_performance.py` (`e1f8a515`, 661 lines). Where: Drive `Slightly older still good... zip` (1SwzA3x5iZmwBRrrxnC0aNUlXHE674Sy1) `>> pubcast_ai_complete/pubcast_build/pubcast_evo_FINAL.zip > pubcast_evo/facial_performance.py` | READ (every differing line against the live `modules/evo/facial_performance.py`) | Performer and audience face analysis (MediaPipe, DeepFace) feeding the prosody and VDI engines. | **Harvest.** The live file is a placeholder in two places, and this one does the real work: `_expression_velocity` returns 0.0 live, while this measures nose-tip and lip-corner motion between frames; `_breathing_rate` returns 15.0 live, while this tracks nose height over 10 s and counts peaks. It also fixes `face_area` (live uses `.size`, which counts colour channels). Port with care: it runs face_mesh a second time per frame (the landmarks should be reused), and its imports are bare where the live file's are package imports. |
| `facial_performance.py` (`f0da9e34`, Breaking-Dawn `not_yet_integrated/`) | READ (differing lines counted) | An earlier form. | The live file is this plus 8 lines. Nothing to harvest. |
| `evo_bus_wiring.py` (`195fe3e7`, April bundle) | READ (structure) | EVO subscribes to the take lifecycle. At slate, characters go to places; at ready, performance is armed; at action, energy ramps and blinks are suppressed; at live, full expressivity; at cut, characters relax. When the program camera changes, the characters' eyelines turn to the new camera. A mid-take cut gets a brief composure hold. | **Idea worth keeping**: nothing in the build turns eyelines to the program camera or ties EVO to the take state. It depends on the old ControlRoom bus; it would hook to CameraManager's switch event and the slate phases. |
| `performance_manager.py`, `performer_state.py`, `animation_authority.py` (`0d47ef2d`), `avatar_motion.py` | READ (structure) | Earlier forms. | Each is smaller than its live counterpart in `runtime/spine/` or `modules/`, and the live one has more. Nothing to harvest. |
| `camera_manager.py` (`1724da3a`), `_camera_manager_v5_retired.py`, `_cameras_advanced_v5_retired.py`, `cameras_advanced.py` (`dee7d1fb`), `cameras.py` (`a687840c`, a 26-line shim) | READ (structure) | AdvancedCameraManager: USB, IP, OBS virtual camera and voxel-engine TCP sources, monitoring, and cut, preview and auto transitions. | Older forms of the live `modules/cameras_advanced.py`, which main.py imports at line 408. Nothing to harvest. |

## 5. Voice, mocap, routes and engines: compared line by line with the live file, 2026-11-26

READ (every non-comment line that the live file doesn't have, and every class or function that only one side has).

| File | Live file | Verdict |
|---|---|---|
| `prosody_engine.py` (`e5878e4f`). Where: Drive `Slightly older still good... zip` (1SwzA3x5iZmwBRrrxnC0aNUlXHE674Sy1) `>> pubcast_ai_complete/pubcast_build/pubcast_evo_FINAL.zip > pubcast_evo/prosody_engine.py` | `modules/evo/prosody_engine.py` | **Harvest.** The live `_cartesia_emotion` is a 3-rule stub: fixed levels from style, crack and pitch. This one grades every level (lowest to high) from the actual values: warmth gives positivity; crack probability gives sadness; pitch range with style gives curiosity; direct address with proximity gives trust; slow speech with warmth gives anticipation; capped at 3 emotions. A small, contained port. |
| `distributed_engine.py` (`faa70bd1`, same zip) | `modules/evo/distributed_engine.py` | Its extra 149 lines are local stand-in copies of the bridge, circuit-breaker and IRM classes, used when `modules.bridge` is missing ("stub mode"). The live file has every real function. Nothing to harvest. |
| `mocap_integration.py` (`76b7688b`, Prime canon) | `modules/mocap_integration.py` | Older: the live file has `open()` and `_receive_frames()` with the task kept and cancelled. Nothing to harvest. |
| `production_routes.py` (`5004e16f`, `fb7218d0`, `370d190b`) | `modules/production_routes.py` (1,086 lines) | Older (473 to 662 lines). Nothing to harvest. |
| `program_audio_routes.py` (`064810ad`) | `modules/program_audio_routes.py` | Older, without the current role check. Nothing to harvest. |
| `stage_compat_routes.py` (`c176446f`, `4cd64e85`) | `modules/stage_compat_routes.py` | Older; they trust an `X-Client-Id` header as identity, which the live file doesn't. Nothing to harvest. |
| `pubcast_twin_engine_service.py` (`e457e849`) | `run3_bridge/pubcast_twin_engine_service.py` | Two lines differ. Nothing to harvest. |
| `avatar.py` (`ea3ed727`), `choreography_controller.py` (`df0a32a6`) | `modules/avatar.py`, `modules/choreography_controller.py` | Older; the live ones are larger, and the differing lines are formatting of the same logic. Nothing to harvest. |

## 6. Avatar building from art: small tools that exist only in zips, 2026-11-26

READ (structure; each is 18 to 90 lines). These are for building a character model (Lena), not for the show's
reconstruction from show data. Each zip that holds them is committed in many branches (`branch_files_index.tsv` gives
every location by the zip's fingerprint). The build has none of them: no TRELLIS, visual hull, Blender worker or GLB audit.

| File | What it says it is | Honest limits it states |
|---|---|---|
| `trellis_integration/reconstruct_with_trellis.py` (`bb7e4c05`), `prepare_views.py` (`544020ed`) | Multi-view reconstruction of Lena with Microsoft's TRELLIS; normalizes the artwork first | Needs the official TRELLIS install and CUDA; "no substitute silhouette meshing" |
| `reconstruct.py` (`3e59d7d2`), `preview.py` (`2e2fbfa0`), `render_check.py` (`add3397a`) | Two-view silhouette visual-hull reconstruction, offline and reproducible | "Not a learned 3D model"; occluded limbs are not inferred |
| `pubcast_avatar_studio_corrected/rig_pipeline.py` (`b3d3456c`), `blender_worker.py` (`1706c670`), `reconstruction/mesh_scale.py` (`ddc5bc7a`), `upstream_photo_to_mesh/mesh_units.py` (`006e1e9c`, adapted from an MIT project) | Rigging inside Blender 4.x, and scaling a reconstructed GLB to metres | "Provisional", "no canonical certification"; needs Blender |
| `pubcast_avatar_rebuild/build_offline_glb.py` (`0c1ece27`), `audit_existing_glb.py` (`31617cb4`), `extract_canonical.py` (`764431a0`) | A self-contained skinned, animated glTF test fixture; a read-only GLB audit; extraction of the Rust `create_pubcast_rig` construction | The fixture says it is "NOT a Lena character model" |

Verdict: candidates for the avatar area, not the control-room engine. `audit_existing_glb.py` could serve the engine as
a check on the GLB actors that `world_walk_glb.js` loads. None of them were run here.

## 7. Control-room pages found in zips (frontend, so ChatGPT's area), 2026-11-26

READ (every function name, every API path called, and the CSS section comments). Claude does not edit the frontend on
this branch. They are listed so the operator side can find them, and for the backend routes they expect.

| File | Where | What it is | Backend routes it calls: does the build have them? |
|---|---|---|---|
| `station_ccu.html` (`28d3d737`, 446 lines) | GitHub Storage main: `pubcast_utilities_systems_part3.zip >> util3/pubcast_session_2026-05-13.zip > pubcast_session_handoff/static/` (only in that zip) | A camera control unit drawn over a console image: camera strip, presets 1 to 4, shots 1 to 6, focus, zoom, knob, joystick, trackball, tally lamp, return video, monitor | `/api/cameras/{focus,zoom,pantilt,preset,shot,tally,return,knob,menu,param,trackball,switch}` and `/ws/controlroom`: **none exist.** The build has PTZ and pose at `/api/switcher/ptz/{id}` and `/api/switcher/pose/{id}`, and moves at `/api/camera-moves`. A CCU would be wired to those; tally, preset recall and return video have no backend. |
| `station_audio (1).html` (`e9ec3df0`, 406 lines) | GitHub Just-The-Pubcast main (also in Storage's `Just-The-Pubcast-main.zip`) | An audio station drawn over a console image: faders, knobs, arc buttons, mute, keyboard bar | `/api/audio/{channel,knob,route}`: **none exist under those names.** The build's channel strip is `/api/program-audio/channels` and `/api/program-audio/channels/{id}` (gain, mute, solo), from this branch. |
| `control_room.html` (`41a6e40a`, `595bfd79`, `c7ab68bf`) | Prime canon; DREAMS bundle; Storage session 2026-05-13 | Console-image control rooms with hotspots: PGM/PVW, cut, record, panic, mute all, presets, stations bar | They call `/api/cameras/cut`, `/api/cameras/switch`, `/api/recording/start`, `/api/production/panic`. The live `static/control_room.html` differs from all three. |
| `director_switcher.html` (`855bed78`, 1,205 lines) | Prime canon | Switcher with truth card, danger panel, aux, fade, pause recording, marker, bars, export | Older than the live `static/director_switcher.html` (137 lines only here, 230 only live). |
| `studio_control_room.html` (`206fc815`) | Prime canon | Audio matrix, countdown, preflight checks | Near the live file (47 lines only here, 63 only live). |
| `pubcast_control_room_v14.html` (`0181f9d5`, 3,687 lines) | a zip committed in three branches (`curtsey_context/code/`), only in that zip | A large styled control room ("brass and gold", "teal marble"); calls `/api/switcher` | Not compared further. Its look is Josie's design work: the operator side should look at it before changing any control-room look. |
| `control_room_ui.html` (`36e49dfa`) | The-Prime assembled-pubcast (in a branch) | Resizable trays, telemetry, layout persisted at `/api/layout` | Not compared further. |
| `mocap.html` (`8546daf5`), `pubcast-control.html` (`47253231`), `Enhanced_control_room_HTML_integration_-_Claude.html` (`31845a16`) | 2026-03-21 code zip; Drive `Slightly older still good` zip; Thursday- breakfast zip | A mocap status panel; a procedural-avatar canvas; a 1,945-line launcher page | Not compared further. |
| `studio.js` (8 versions) | avatar rebuild zips (section 6) | The browser side of the avatar tools: geometry, GLB load, rest pose, edge-stretch measure | With section 6. |

## 8. Engine parts already in the tree but parked (under `recovery/`, not wired), 2026-11-26

**Correction, 2026-11-27.** One row below was wrong: the recording preflight IS live (see its row). Re-checked
the same day with `git ls-files modules`: the intercom (now ported, commit 8fc67042), the frame bus and the camera
engine bridge have no file of that name live. That is a check by file name, the same kind as the one that failed,
so each module's key classes were also searched in `modules/` and `main.py`, and found only under `recovery/`.

The index used to call these "IN CURRENT BUILD; nothing to harvest". They are in the tree only as copies under
`recovery/`, and nothing live imports them. The index now says "IN CURRENT BUILD ONLY AS A PARKED COPY under
recovery/" (zips) and "only as a parked copy, not live" (branches). That covers 585 distinct contents from the zips
and 738 branch files.

READ (structure; for intercom.py, the module docstring in full). Each was checked against the live code for an
equivalent (git grep for its key names, outside `recovery/`, `evidence/` and the index).

| File (in the tree at) | What it is | Live equivalent? | Verdict |
|---|---|---|---|
| `recovery/2026-11-23/rediscovery/intercom_and_camera_bus/modules/intercom.py` (376 lines; originally NowCurtsey `pubcast_run_bundle.zip`, 2026-08-24) | The director's PA: announcements to one room or all rooms; mod and above always may; mod can grant access to named users (scoped by room, revocable; a grantee can't grant). Every announcement is transcribed into the chat of each targeted room. Audio passes through a loudspeaker filter (bandpass 400 Hz to 4 kHz, soft-knee compression, light saturation). Routes in that bundle's main.py: `/api/intercom/{announce,grant,revoke,grants,history}`. | None. `modules/studio_slate.py` has a live floor microphone, but no announcements, grants or transcripts. | **Harvest candidate, audio authority (Phase 4).** Wire it as a channel of program audio, kept out of the recording unless chosen, with its routes behind the current auth. |
| `.../intercom_and_camera_bus/modules/virtual_camera_bus.py` (253 lines) | The latest rendered frame of each virtual camera, fanned out to monitors; measured fps; a feed counts as live with a frame in the last 2 s; accepts a browser canvas `toDataURL`; "taps" write every frame of a camera to disk as numbered images. Served in that bundle at `/api/cameras/feeds` and `/api/cameras/{id}/frame`. | None: no frame bus or multiview feed in the live code. | **Harvest candidate** for multiview monitors and an ISO tap per camera (camcorder mode). The disk tap as numbered images should go to the capture engine instead. |
| `.../intercom_and_camera_bus/modules/studio_camera_preflight.py` (191 lines) | Checks before capture, without capturing: is every camera's view vector valid, is each camera visible, is the studio ready to record. | **CORRECTED 2026-11-27: yes.** The build already has `modules/studio_camera_preflight.py`, a newer copy of this file with more checks (native voxel and 2.5D sources), imported by `modules/production_routes.py` and serving `/api/recording/preflight`. The first version of this row said "None live". That was wrong: the check that produced it cut its output short. | Not a port. Extended in place on 2026-11-27 (machine checks and a start gate; commit 3fcdff9e). |
| `.../intercom_and_camera_bus/modules/camera_engine_bridge.py` (198 lines) | When the program or preview source is a VOXEL_3D camera, it sends CAMERA_MODE_SWITCH to the Rust CameraEngine over the ws_renderer WebSocket; registers voxel cameras at boot. | None live; mentioned only in handoffs (`handoffs/recovered_progress/CAMERA_RENDERER_CONTRACT_V1.md`). | Goes with the Rust camera JSON server (section 2). Decide them together. |
| `recovery/2026-11-23/rediscovery/camera_files/video_switcher.py` (608 lines), `camera_router.py`, `camera_integration.py`, `camera_manager.py` (`a6ab4d86`), `camera_control_ui.js` | A vision mixer ("Camera 1 is hot. Ready 2. Take 2."): inputs, program, preview, timed transitions, recording sessions, input health. | `modules/cameras.py` CameraManager plus `modules/switcher_routes.py` (now with dissolves on the switch event, from this branch). | Superseded as authority. The input-health monitoring loop is worth comparing against CameraManager. |
| `recovery/2026-11-23/rediscovery/thursday_animation/...`: `behavior_motion_pipeline.py`, `.js`, `glb_motion_retargeter.py`, `avatar_glb_motion_consumer.js`, `avatar_motion_runtime.js` | Behavior-to-motion pipeline and GLB motion retargeting. | The live renderer drives GLB actors through `static/world_walk_glb.js`. | Not judged: needs a full read against the live actor path. |
| `recovery/.../pubpartner_horizon_prebeta12/modules/` (`cameras.py`, `cameras_advanced.py`, `recording.py`, `recording_pipeline*.py`, `timeline*.py`, `mocap_*.py`, `performance_manager.py`) | An older whole build (PubPartner Horizon prebeta 12) parked for reference. | The live `modules/` files of the same names. | Older. This is why "closest current file" sometimes names a file in this folder: see PARTS_INDEX.md. |

## Not yet read (as of 2026-11-26)

Of the 599 engine-related candidates (the selection rule is in `tools/parts_index/candidates.py`):

- **Tests (103).** Not read yet. Each is a test file in no branch or not in the build.
- **Iteration Wallet and BlackBox family (about 150 files)**: `canonical_evidence.py`, `runtime_continuity.py`,
  `passkey_gate.py`, `outbox.py`, `recorder.py`, `sentinel.py`, `migration.py`, `server.py` (6 versions with
  `/api/v21/...` routes) and their tests. The engine word list caught them ("record", "blackbox"), but they are the
  Iteration Wallet / BlackBox product, not the control room. They need their own read, and that is Josie's call to
  prioritize.
- **Monolith main.py variants (13 `main.py`, plus `main_UPDATED*.py`, `main_comprehensive.py`, `main_temp.py`).** Only
  their routes were compared. Routes in them the live build lacks, besides those above:
  - `/api/intercom/*`, `/api/cameras/feeds`, `/api/cameras/{id}/frame` and `/api/cameras/{id}/aim` (NowCurtsey
    run_bundle, 2026-08-24);
  - `/api/purfluous/scenes` (five versions);
  - `/api/mode/{status,override,clear_override}` (`7d05dd9f`);
  - `/api/controlroom/{slate,ready,action,cut,cancel,status}` and `/api/cameras/{id}/{fallback,recover}`
    (`production_routes.py` `370d190b`, the April ControlRoom).

  The full list is in `missing_routes.json`, made by the route comparison in this folder.
- **Everything else in the 599** not named in sections 1 to 8.

## 9. New contents found in the Drive folders of extracted copies, 2026-11-26

READ (structure; for the report, its first 60 lines). These seven contents are in no zip and no branch tip.

| File | Drive id | Read | Verdict |
|---|---|---|---|
| `capture.py` (`aa6421f4`, 248 lines, Feb 2026), in pubcast_complete_debugged and codex_construction_pubblocks | 1qFb9l6de2e-GCKgmrMUOpXlk-Y8jGG7_, 1FWTcXEMQA8KUc3y_m1ksPtOPxbBP7U44 | structure | An earlier form of the capture engine: one FFmpeg per source. Older than the Prime-canon copy in section 3. Nothing to harvest. |
| `pubcast_vision_integration.py` (`0e26abf9`), codex_construction | 1LYcJztxHE52aUsGiiiAGrUSwUFxuZr0K | every differing line against the live `modules/pubcast_vision_integration.py` | Older. Three lines differ, and the live file fixes all three. One is a real bug in this copy: `logger.info("broadcast_started", quality=...)` passes a keyword that the standard library's logging rejects. Nothing to harvest. |
| `test_memory_systems.py` (`ffde98db`), codex_construction | 14YR5Vcff0NzpoMh06epBcNRNUOU__i70 | structure | A runnable script that tests the Alex, Jeremy and CC memory systems and the bridge protocol. Not engine. |
| `conftest.py` (`c4ac1517`), codex_construction | 1KGKU1JxHw91uNrduGsWhLW5xTkZgdb41 | structure | Test fixtures: an app client with no startup, and a client run through the real startup. Worth comparing with the build's `tests/conftest.py` before a test-infrastructure change. |
| `test_beefed_up_recovery_wiring.py` (`1ffc6f0a`, 1,107 bytes), codex_construction_pubblocks | 1Uma9A5b84zsRsbX0w8EW-ZgHT0fvyCMC | structure | Four checks that the safe-console and Pub Manager routes are declared and their scripts load. Not engine. |
| `DEBUGGING_REPORT.md` (`2d696b16`, 2026-05-08), at the top of pubcast_complete_debugged | 1NNLYV-FhGAOaOwT93233XaTDF1BDXOg7 | first 60 lines | It claims "No critical bugs found. System is production-ready" and lists eight avatar-performer fixes. That is a claim from its writer; nothing here verifies it. Its fix list is useful as a checklist for `avatar_performer.py`. |

## 10. The engine-related test files in the zips, 2026-11-26

READ (every import, and how many tests each holds) for all 142 test files among the 599 candidates. Eight of them
were RUN against `finish/control-room-engine`: in a throwaway detached worktree, with the project venv. Nothing was
committed from the run.

**What they test**
- 80 test the Iteration Wallet / BlackBox product (`iteration_wallet.*`). That package is not in the build, so they
  cannot run here. Josie's call (see "Not yet read").
- 6 need modules that are gone from the build: `runtime.pub_manager`, older `runtime.spine` names, `blackbox_plugin`.
- 22 import modules that are live; 34 import no project module (static checks of files).

**RAN, the eight whose subject is live and whose file name the build's tests/ doesn't have**

| Test (fingerprint) | Result | Why |
|---|---|---|
| `tests__test_pub_manager_recovery.py` (`5d3645b5`) | 4 passed | The live `modules/pub_manager_recovery.py` still meets it. Could be added to the build's tests as it is. |
| `tests__test_pub_partner_chat.py` (`3f5fe15e`) | 4 passed | Same: the live `modules/pub_partner_chat.py` meets it. |
| `test_15_api_coverage.py` (`08d1faa4`) | 14 passed, 14 failed | Every failure is a 404 on a path the live build renamed or dropped. Checked by listing the live app's 641 routes after a real startup: `/api/pete/status` is now `/api/pete-enhanced/status` and `/api/internal/pete/status`; `/api/jeremy/status` is now `/api/jeremy/health`; `/api/memory/status` is gone (the live memory routes are per character); `/api/vs/*` (voxel studio) is not mounted. These are renames, not regressions, except that voxel studio has no live routes. |
| `test_alex_foundation_pass.py` (`d9d5e465`) | 6 passed, 6 failed | The failures look for launcher and UI files at paths the build doesn't have (FileNotFoundError). |
| `test_09_character_registration.py`, `test_08_memory_persistence.py` | 11 and 14 failed | They call methods that the live BotManager and UniversalMemorySystem no longer have (`set_memory_system`, `register_character`). Older API. |
| `test_architecture_boundaries.py` (`665390a9`) | 1 passed, 1 failed | Needs `blackbox_plugin`. |
| `test_sir_purfluous.py` (`ed49ce96`) | cannot import | Needs a module named `sir_purfluous`, which the build doesn't have. |

**Correction, made in the same session.** The first version of this section said that no test file imports
`capture`, `recording_modes`, `cameras` or `program_audio`. That was written before it was checked, and it was wrong.
A check by import found two, and both were then RUN:

- `test_pubcast.py` (`fa98a38f`) imports `modules.recording` and `modules.cameras`: 27 passed, 1 failed. The failure
  expects 4 recording profiles where the live build has 5. It differs from the build's own `tests/test_pubcast.py` by
  5 lines.
- `test_module_router_parity_guards.py` (`33e64865`) imports `modules.recording_pipeline_routes`: 9 passed, 2 failed.
  Its stand-in recording service lacks `get_session` and the `operator` argument, which the live routes now use.

Neither failure is a regression in the build: in both, the test is older than the live interface.
