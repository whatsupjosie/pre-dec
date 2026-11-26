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
