# Loose parts inventory, 2026-11-23

Branch: claude/studio-assembly-2026-11-23. Made with tools/loose_parts_inventory.py (tested by tests/test_loose_parts_inventory.py) and a route check described below.

Labels, as in STUDIO_ASSEMBLY_2026-11-23.md: RAN = I ran it and saw the result. READ = I opened and read it. GUESS = my reasoning, not checked.

## The short answer

1. Python (RAN): 440 files examined; 319 are attached to the running app; 45 are reached only by tests; 10 only by build tools; 66 by nothing.
2. The backends are mostly attached (RAN). The app has 666 route entries. Only two files define routes that are not in the live app: modules/timeline.py (a second timeline router; the mounted one is modules/timeline_routes.py, so it is a duplicate, not a gap) and components/incubating/bubble_stack_router/bubble_stack_routes.py (labeled incubating by its folder).
3. The studio's real gap is screens, not Python. Many mounted routes have no screen that calls them. Table below.
4. Six pages have no link from any other screen. Table below.
5. Most of the 66 loose and 45 tests-only Python files are four families that are not the studio, or that CLAUDE.md says not to overlay: the old "wired" server stack (modules/wired, 29 files across both groups), run3_bridge (5) and run5_pubworld_camera (3), iteration_wallet (12, its own package), and pubpartner_federation (8). I attached none of these (GUESS that each family is superseded: I read their first docstring lines, not their behavior).

## Studio: routes that are mounted but no screen calls

How measured (RAN): the app was started inside a temporary test (not kept), all route entries were written out, and each /api or /ws path, cut at its first {, was searched for in static/, 2i/, bella-live.html and Reach_Phone_Standalone.html. A screen that builds an address from pieces can hide a call from this search. I read static/director_switcher.html to check the timeline row and the search was right. "Tests only" means a test calls it and no screen does. A route that only a test calls is not a working service.

| Part | What exists | What is missing | Who decides |
|---|---|---|---|
| Timeline playback | /api/timeline play, pause, resume, stop, seek, list, and a websocket. Load, play, pause, seek, resume, stop and status are exercised by tests/test_timeline_playback_controls.py (RAN); list and the websocket are not | director_switcher.html can load a timeline and shows its state and progress. Nothing starts, pauses, stops or seeks one | Josie: where the buttons go |
| Readiness before a take | /api/recording/preflight and /api/studio/readiness | No screen calls either; the control room does not show them before recording | Josie |
| Phone or laptop as a camera | static/camera_connect.html and .js, /api/live-sources/audio-inputs and /listener | Nothing links to the page. Phones need https for camera access and run_reach.py serves plain http (LIVE_SOURCES_2026-11-22.md, limit 1) | Josie: link placement, and https (launcher TLS or a tunnel) |
| Recording mode choice | /api/recording/modes, /profiles, /privacy, /import (tests only) | The mode switch itself (handoff decisions 1 to 3 on names, placement, arm_preview) | Josie |
| Camera visibility and scenes | /api/cameras/visibility, /api/switcher/scenes (no test, no screen) | A screen, if wanted. GUESS: may be meant as API-only | Josie |
| BlackBox operator routes | save, verify, preserve, status, archive-policy (tests only) | A screen | Josie |
| Media intake | /api/media/intake and /formats (nothing calls them) | A screen or a caller | Josie |
| Audio devices and mics | /api/audio/devices/select and /active, /api/mic/profiles, /api/mic/cough/status (tests only); /api/audio/devices/test (nothing) | A screen | Josie |
| Program audio recovery | /api/program-audio/recovery/{action_id} (tests only) | A screen | Josie |
| Camera boxer, Rust camera control | /api/boxer/status and /override, /api/camera/rust-control/status | A screen | Josie |
| Structured logs | /api/logs/recent, /systems, /ws (tests only) | A screen | Josie |

## Finished Python that nothing mounts

| File | What it is | Why it is not attached | Next |
|---|---|---|---|
| modules/clip_analysis.py | Measures a video clip: format, sharpness, exposure, hard cuts, loudness, noise floor. tests/test_clip_analysis.py | No route and no screen | Josie: should it run after every take, or on request |
| modules/range_preservation.py | Copies a recorded time range out of segmented capture and verifies it (segmented_capture.py is attached) | Only a test imports it | Josie |
| modules/runtime_compat_bootstrap.py | One call that mounts runtime_control_routes and stage_compat_routes | Superseded: modules/production_routes.py already imports both (READ) | None; leave |
| modules/evo/camera_manager.py | The advanced camera manager | main.py keeps it as a donor and boots it only when PUBCAST_ENABLE_LEGACY_ADVANCED_CAMERA=1 (READ, near line 1258) | None; deliberate |
| modules/documents.py | Document and message storage for the typewriter workspace | No route; static/typewriter_console.html makes no /api calls (READ) | Josie, with 2i |
| modules/mode_resolver.py | Turns production mode into Jeremy's and the bots' behavior | Tests only; not about recording | Josie |
| modules/integrity_checker.py, modules/security_authority.py | Vault corruption watcher; owner and host access gate | Tests only; not studio | Josie |
| modules/glb_motion_retargeter.py | Avatar motion payload cleaning | Mocap-adjacent; handoff says leave mocap | None |

## Pages nothing links to

avatar_controls.html (Avatar Controls), avatar_foundry.html (Avatar Foundry), camera_connect.html (Connect this camera), camera_try.html (Camera controls: try them), choreography.html (Choreography Studio), pete_director.html (Pete Director). Each opens if its address is typed, because main.py mounts static/. None can be reached from another screen. Fourteen more pages are named only in main.py (full list in the tables; most are probably routes, GUESS: I did not check each).

## Not attached on purpose

- modules/wired, run3_bridge, run5_pubworld_camera: an older parallel server and engine stack. CLAUDE.md: do not overlay an old donor on the newer runtime.
- modules/affect_wiring.py says in its own header "DEPRECATED — DO NOT WIRE THIS IN" (READ).
- iteration_wallet: a standalone product (its own server and command line). Whether it sits beside PubCast is Josie's call.
- modules/avatar_motion.py, modules/mocap_precision.py: mocap; the handoff says leave it.

## What this pass changed

Added tools/loose_parts_inventory.py and tests/test_loose_parts_inventory.py (3 tests, RAN; a deliberate break of the byte-order-mark handling made one fail, then restored). No part was attached. Every attachment above needs a placement or behavior choice that is Josie's (CLAUDE.md: do not change her design; handoff: do not invent the control-room layout). Nothing was deleted or moved.

## Not checked

Whether any screen link is visible on screen, not just present in the file. Modules loaded by a name built at run time. The old branches console-touch-typewriter-keys, 2i-beta-polish and codex/2i-typewriter-visual-2026-11-17 against this branch's tests.

## Tables made by the tool

## Python files

Python files examined: 440. Attached to the running app: 319. Tools only: 10. Tests only: 45. Loose: 66.


### TESTS_ONLY (45)

| File | What it says it is | Imported by | Tests |
|---|---|---|---|
| experiments/camera_recording_audit/test_camera_contract.py | Camera/recording integration contract tests for October's isolated experiment branch. | - | - |
| modules/agency_observation.py | Observation layer for PubPartner's persistent event-agency substrate. | event_agency.py | horizon_ref_agency_observation.py, test_agency_observation.py |
| modules/cc_memory_store.py | cc_memory_store.py — Code Collector Tier 2 persistent memory | - | test_memory_systems.py |
| modules/character_engine.py | modules/character_engine.py — Character Intelligence Layer | - | test_pubcast.py |
| modules/clip_analysis.py | Measured technical analysis of a video clip (no AI model required). | - | test_clip_analysis.py |
| modules/documents.py | Local document and message storage for the PubCast typewriter workspace. | - | test_document_owner_transaction.py, test_document_state_validation.py, test_integration_storage_boundaries.py (+2) |
| modules/event_agency.py | Persistent event-agency substrate for PubPartner. | agency_observation.py | horizon_ref_agency_observation.py, horizon_ref_event_agency_v1.py, test_agency_observation.py |
| modules/evo/camera_manager.py | PubCast AI - Advanced Camera Management System | - | test_camera_configuration_persistence.py, test_camera_configuration_restart.py, test_camera_fixes_2026_11_21.py |
| modules/glb_motion_retargeter.py | GLB motion retargeting helpers for PubCast avatar motion commands. | - | test_glb_motion_retargeter.py |
| modules/integrity_checker.py | Background Integrity Checker | - | test_integrity_checker_truthfulness.py |
| modules/mode_resolver.py | modules/mode_resolver.py — Production Mode Resolver | - | test_pubcast.py |
| modules/prompt_context_builder.py | Build compact natural-language memory context for model prompts. | - | test_memory_foundation_codex.py |
| modules/pubpartner_rephrase.py | Alex voice rewrite pass: neutral facts in, Alex's voice out, nothing added or lost. | - | test_pubpartner_rephrase.py |
| modules/pubpartner_vessel/__main__.py | Command-line administration for PubPartner vessel files. | - | horizon_ref_pubpartner_vessel_unittest.py, test_pubpartner_vessel_unittest.py |
| modules/range_preservation.py | modules/range_preservation.py — copy a recorded time range into its own file | - | test_segmented_capture_and_preservation.py |
| modules/runtime_compat_bootstrap.py | modules/runtime_compat_bootstrap.py — one-call mounting for compatibility routes. | - | test_runtime_compat_bootstrap.py |
| modules/security_authority.py | PubCast security authority and classified-data access gate. | - | test_security_authority.py |
| modules/situation_reading.py | situation_reading.py - the situation-first reading model for Alex. | - | test_situation_reading.py |
| modules/vault_engine.py | Iteration Wallet - Vault Engine | - | horizon_ref_character_audit_regressions.py |
| modules/wired/anti_parroting.py | Compatibility exports for the shared Base/Horizon companion implementation. | companion_core.py, companion_runner.py, conversation_state.py (+3) | - |
| modules/wired/companion_core.py | companion_core.py | companion_runner.py, pubcast_runtime.py | test_companion_recovery.py |
| modules/wired/contradiction_tracker.py | Compatibility exports for the shared Base/Horizon companion implementation. | companion_core.py | test_companion_recovery.py |
| modules/wired/conversation_state.py | conversation_state.py | pubcast_runtime.py, response_composer.py | - |
| modules/wired/director.py | director.py | pubcast_runtime.py, response_composer.py | - |
| modules/wired/eq_adaptor.py | EQ ADAPTOR — Emotional Intelligence Middleware | gpt_adapter.py | test_eq_transitions.py |
| modules/wired/known_vs_novel.py | Compatibility exports for the shared Base/Horizon companion implementation. | companion_core.py, conversation_state.py, pubcast_runtime.py | - |
| modules/wired/meaning_maker.py | meaning_maker.py | companion_core.py, companion_runner.py, conversation_state.py (+1) | - |
| modules/wired/observation_engine.py | Compatibility exports for the shared Base/Horizon companion implementation. | conversation_state.py, pubcast_runtime.py | test_companion_recovery.py |
| modules/wired/orchestrator_hardening.py | Orchestrator hardening for production resilience. | hardened_websocket.py, test_hardening.py | - |
| modules/wired/orchestrator_wired.py | WIRED ORCHESTRATOR | - | test_orchestrator_streaming.py |
| modules/wired/pubcast_runtime.py | pubcast_runtime.py | - | test_companion_recovery.py |
| modules/wired/rate_limiter.py | Rate limiting for PubCast AI. | hardened_websocket.py, test_hardening.py | - |
| modules/wired/response_composer.py | response_composer.py | pubcast_runtime.py | - |
| modules/wired/safeguards.py | Compatibility exports for the shared Base/Horizon companion implementation. | companion_core.py, conversation_state.py, director.py (+1) | - |
| modules/wired/test_hardening.py | Test suite for PubCast AI production hardening. | - | - |
| pubpartner/cli.py | Command-line interface for PubPartner. | - | test_companion_horizon_host.py |
| pubpartner/pubpartner_federation/__init__.py |  | docking.py, engine.py, service.py (+1) | portable_companion_wheel_smoke.py, test_companion_docking.py, test_companion_sync_durability.py (+1) |
| pubpartner/pubpartner_federation/docking.py | Owner-scoped Base/Horizon docking on the existing sync engine. | - | portable_companion_wheel_smoke.py, test_companion_docking.py, test_companion_sync_durability.py (+1) |
| pubpartner/pubpartner_federation/engine.py |  | __init__.py, docking.py, service.py | - |
| pubpartner/pubpartner_federation/identity.py |  | __init__.py, docking.py, service.py | - |
| pubpartner/pubpartner_federation/protocol.py |  | __init__.py, engine.py, service.py (+1) | test_companion_sync_durability.py |
| pubpartner/pubpartner_federation/store.py |  | __init__.py, docking.py, engine.py (+1) | - |
| run3_bridge/test_pubcast_twin_engine_service.py |  | - | - |
| test_04_websockets_FIXED.py | test_04_websockets.py — WebSocket routing and connectivity | - | - |
| test_run1_live.py | Run 1 verification — 15+ turn conversation through the REAL integrated path. | - | - |

### TOOLS (10)

| File | What it says it is | Imported by | Tests |
|---|---|---|---|
| blackbox_decoder/__init__.py | BlackBox decoder and report helpers. | blackbox_hardening_check.py, blackbox_smoke.py | test_blackbox_event_language.py, test_blackbox_storage_experiment.py |
| blackbox_decoder/offline_decoder.py | Decode BlackBox coded records into human-readable reports. | __init__.py | - |
| modules/bridge_raw.py | modules/bridge.py — Twin Engine Communication Bridge | distributed_engine.py, probe_camera_compute.py | test_round9_evo_irm_bridge_contract.py |
| modules/data_checkpoint.py | Offline, byte-preserving host-data checkpoints, independent of the app runtime. | pubcast_checkpoint.py | test_data_checkpoint.py, test_speech_system.py |
| modules/evo/distributed_engine.py | DISTRIBUTED ENGINE NODE | probe_camera_compute.py | test_round9_evo_irm_bridge_contract.py |
| modules/filler_cream.py | Filler Cream — bounded local filling between neighbouring surface pieces. | filler_cream_fixture.py, voxel_studio.py, feic_mo_chroi_heart.py (+1) | test_filler_cream.py, test_voxel_studio_filler.py |
| modules/filler_cream_fixture.py | Inspectable Filler Cream proof fixtures. Designed in 1/64-block units; S scales them to the internal | filler_cream_view.py | test_filler_cream.py, test_voxel_studio_filler.py |
| modules/pubcast_world.py | pubcast_world.py — the connected PubCast world (rooms, views, exits, images) | pubcast_world_placement.py, calib_proof.py, gen_placements.py | test_pubcast_world.py, test_pubcast_world_json.py, test_pubcast_world_placement.py |
| modules/pubcast_world_placement.py | pubcast_world_placement.py — where things stand inside each room picture | build_world_json.py, calib_proof.py | test_pubcast_world_json.py, test_pubcast_world_placement.py, test_world_walk_browser.py |
| modules/voxel_studio.py | voxel_studio.py — PubWorld Voxel Studio | filler_cream.py, filler_cream_fixture.py, filler_cream_view.py | test_filler_cream.py, test_voxel_studio_filler.py |

### LOOSE (66)

| File | What it says it is | Imported by | Tests |
|---|---|---|---|
| blackbox_recorder.py | Small self-contained append-only BlackBox recorder used by PubCast. | - | - |
| codex_add_pubblocks.py |  | - | - |
| codex_ast_check.py |  | - | - |
| components/incubating/bubble_stack_router/bubble_stack_routes.py | modules/bubble_stack_routes.py — Bubble Stack PIKPC API Routes | - | - |
| components/incubating/theory_evidence_bridge/theory_evidence_bridge.py | modules/theory_evidence_bridge.py — Wires evidence_layer, contradiction_engine, | - | - |
| conftest_FIXED.py | conftest.py — PubCast AI startup test fixtures | - | - |
| foresight/lab/morph2.py |  | - | - |
| foresight/lab/shot2.py |  | - | - |
| iteration_wallet/__init__.py | Standalone Iteration Wallet package. | app.py, gatekeeper.py, guard.py (+2) | - |
| iteration_wallet/app.py | Application object compatibility wrapper. | - | - |
| iteration_wallet/blackbox.py | Iteration Wallet BlackBox evidence chain. | server.py | - |
| iteration_wallet/ceremony.py | Human ceremony token primitives for Iteration Wallet. | server.py | - |
| iteration_wallet/cli.py | Local-only command helpers for Iteration Wallet. | - | - |
| iteration_wallet/gatekeeper.py | Protected action gatekeeper for Iteration Wallet. | guard.py, server.py | - |
| iteration_wallet/guard.py | Compatibility guard surface for protected-action policy. | - | - |
| iteration_wallet/identity.py | Local identity/session records for Iteration Wallet. | gatekeeper.py | - |
| iteration_wallet/notification_manager.py | Human-intent notification and access decision primitives. | gatekeeper.py, server.py | - |
| iteration_wallet/server.py | Local FastAPI route surface for Iteration Wallet. | app.py | - |
| iteration_wallet/vault.py | Compatibility wrapper for the active v2.1 custody engine. | - | - |
| iteration_wallet/vault_v21.py | Iteration Wallet v2.1 custody vault. | server.py, vault.py | - |
| modules/affect_wiring.py | ⚠️  DEPRECATED — DO NOT WIRE THIS IN.  (marked 2026-08-23, Run 1) | - | - |
| modules/avatar_motion.py | modules/avatar_motion.py — Avatar motion-capture presets for PubCast. | - | - |
| modules/bubble_stack_pikpc/routes.py |  | - | - |
| modules/camera_manager.py | Compatibility adapter for the advanced camera manager. | - | - |
| modules/contradiction_engine.py | contradiction_engine.py — Contradiction Memory & Instability Detection | theory_evidence_bridge.py | - |
| modules/deformation_math.py |  | streaming_chain_resolver.py | - |
| modules/engine.py | Pubcast Core Engine | - | - |
| modules/evidence_layer.py | modules/evidence_layer.py — Evidence Layer & Theory Engine | theory_evidence_bridge.py | - |
| modules/linux_enforcer.py | Linux Enforcement Engine | - | - |
| modules/littlemode_protocol.py | LittleMode Protocol v2.0 | - | - |
| modules/mocap_precision.py | PubCast High-Precision Webcam Motion Capture  v2.0 | - | - |
| modules/orchestrator_raw.py |  | - | - |
| modules/pete_avatar.py | Pete Avatar Builder — PubCast AI v5.6 | - | - |
| modules/pete_repeat_character_profiles_v2.py | Canonical character profiles for Belle Époque / PubCast house AIs. | - | - |
| modules/response_execution_layer.py | response_execution_layer.py — Production Response & Conduct System | - | - |
| modules/scene_contract.py | scene_contract.py — Generic Scene / Engine / Builder / Contact for the PubCast | bubble_stack_routes.py | - |
| modules/secure_secrets.py | Secure Secrets Handling | - | - |
| modules/split_llm.py | modules/split_llm.py — Compatibility Shim | - | - |
| modules/streaming_chain_resolver.py |  | bubble_stack_routes.py | - |
| modules/theory_graph.py | theory_graph.py — Theory Graph, Meta-Theory Engine & Presence Mode | theory_evidence_bridge.py | - |
| modules/unified_bridge.py | UnifiedBridge — Python side of the PubCast V3 C++ shared-memory bridge. | - | - |
| modules/universal_avatar_builder_v1.py | PubCast Universal Avatar Builder v1.0 | - | - |
| modules/vision.py |  | - | - |
| modules/wired/NUDGE_MINIMAL.py | MINIMAL NUDGE INTEGRATION | - | - |
| modules/wired/acceptance_engine.py | Compatibility exports for the shared Base/Horizon companion implementation. | companion_runner.py | - |
| modules/wired/animation_presets_complete.py | Complete Animation Presets Library for Pubcast Avatars | - | - |
| modules/wired/companion_runner.py | companion_runner.py | - | - |
| modules/wired/conversation_pacing.py | Compatibility exports for the shared Base/Horizon companion implementation. | companion_runner.py | - |
| modules/wired/ethereal_avatar_generator.py | Ethereal Avatar 3D Model Generator for PubCast AI | - | - |
| modules/wired/gpt_adapter.py | OPENAI GPT ADAPTER | - | - |
| modules/wired/hardened_websocket.py | Hardened WebSocket handler for PubCast AI. | - | - |
| modules/wired/pubcast_voxel_hollow_patch.py | pubcast_voxel_hollow_patch.py | - | - |
| modules/wired/unified_runtime_boot.py | UNIFIED RUNTIME BOOTLOADER | wired_server.py | - |
| modules/wired/voxel_renderer.py | voxel_renderer.py — Production Voxel Renderer | - | - |
| modules/wired/wired_server.py | WIRED FASTAPI SERVER | - | - |
| modules/wired/wired_system.py | WIRED SYSTEM — Jeremy Cricket + BotManager + NudgeQueue | NUDGE_MINIMAL.py | - |
| pubpartner/pubpartner_federation/memory.py |  | service.py | - |
| pubpartner/pubpartner_federation/service.py |  | - | - |
| run3_bridge/bridge_bulletproof.py | VOXEL BRIDGE - THE TWIN ENGINE CONNECTION | - | - |
| run3_bridge/pubcast_twin_engine_demo.py |  | - | - |
| run3_bridge/pubcast_twin_engine_service.py |  | - | - |
| run3_bridge/unified_bridge.py | UnifiedBridge — Python side of the PubCast V3 C++ shared-memory bridge. | - | - |
| run5_pubworld_camera/distributed_engine.py | DISTRIBUTED ENGINE NODE | - | - |
| run5_pubworld_camera/marching_cubes.py | MARCHING CUBES MESH GENERATOR | - | - |
| run5_pubworld_camera/pubworld.py | PubWorld Scene Management System | - | - |
| setup_smollm.py | Install/check all declared runtime requirements, then launch SmolLM. | - | - |

## Pages in static/

| Page | Title | Linked from | Verdict |
|---|---|---|---|
| analytics.html | PubCast — Analytics | main.py, foresight.html, foresight_programs.js | linked |
| audio_console.html | PubCast Audio Console | main.py | main.py only |
| avatar_controls.html | PubCast — Avatar Controls | - | nothing links to it |
| avatar_foundry.html | PubCast — Avatar Foundry | - | nothing links to it |
| avatar_import.html | Import Avatar · PubCast | main.py, pubpartner.html, world_walk.html | linked |
| avatar_studio_demo.html | PubCast Avatar Studio Demo | pubworld_hotspots.py, world.html | linked |
| avatar_walk_test.html | PubCast AI - Manny Walk Proof | main.py | main.py only |
| bar.html | PubCast — The Pub | main.py, foresight.html, foresight_programs.js | linked |
| base.html | {% block title %}PubCast AI{% endblock %} | control.html, dressing_foundry.html | linked |
| builder.html | PubCast AI — Scene Builder | main.py | main.py only |
| byok.html | PubCast — Model Configuration | index.html, Reach_Phone_Standalone.html, main.py | linked |
| camera_avatar_live.html | Camera View · live avatar | main.py, camera_avatar_live.js | linked |
| camera_connect.html | Connect this camera | - | nothing links to it |
| camera_pool_worker.html | PubCast — Contribute camera rendering | camera_pool_controller.js | linked |
| camera_try.html | Camera controls: try them | - | nothing links to it |
| choreography.html | PubCast — Choreography Studio | - | nothing links to it |
| control.html |  | main.py | main.py only |
| control_room.html | PubCast AI â€” Control Room | lab.html, main.py, camera_pool_controller.js, director_switcher.html (+3) | linked |
| director_console.html | PubCast Director Console | main.py | main.py only |
| director_switcher.html | PubCast AI - Director Switcher | lab.html, main.py, foresight.html, foresight_programs.js | linked |
| doctor.html | PubCast AI — Doctor | main.py, foresight.html, foresight_programs.js | linked |
| dressing.html | PubCast — Dressing Room | main.py, foresight.html, foresight_programs.js | linked |
| dressing_foundry.html |  | main.py | main.py only |
| foresight.html | Foresight — The Counter | main.py | main.py only |
| foresight_care.html | Foresight — CARE and EQ | foresight.html, foresight_programs.js | linked |
| foresight_counter.html | Foresight — The Counter | main.py, studio_slate.py | linked |
| foresight_file_shelf.html | PubCast saved files | foresight_programs.js | linked |
| foresight_shell.html | PubCast shell | preview-standalone.html, foresight_files.js, foresight_programs.js | linked |
| gallery.html | PubCast — Gallery | lab.html, main.py, foresight.html, foresight_programs.js | linked |
| general_chat.html | PubCast · General Chat | main.py | main.py only |
| human_contacts.html | Contacts and messages | foresight_programs.js, human_profile.js | linked |
| human_profile.html | Your PubCast profile | foresight_programs.js, human_contacts.html, human_profile.js, login.html | linked |
| human_visits.html | PubCast visits | foresight_programs.js, human_visits.js, login.html | linked |
| index.html | PubCast AI | main.py, start_reach.py, FBXLoader.js | linked |
| launch.html | PubCast AI — Launch | main.py | main.py only |
| login.html | PubCast — Sign In | main.py, camera_connect.js | linked |
| map.html | PubCast AI — Ecosystem Map | main.py, foresight.html, foresight_programs.js | linked |
| mini_console.html | PubCast · On-set mini console | director_switcher.html, foresight_programs.js, pubworld_stage.html | linked |
| participant_audio.html | PubCast — Contribute microphone audio | production25d_audio_panel.js | linked |
| pete_director.html | Pete Director | - | nothing links to it |
| primp.html | Primp · Your face, your canvas | avatar_foundry.html, foresight_programs.js | linked |
| production25d.html | PubCast — 2.5D Television Studio & Control Room | control_room.html | linked |
| production_groups.html | Production groups | foresight_programs.js | linked |
| pub_partner_chat.html | PubCast — Chat | main.py | main.py only |
| pubcast_lighting_explorer.html | PubCast Lighting Explorer | main.py | main.py only |
| pubcast_teleprompter.html | PubCast Teleprompter v1 Codex 20260420 | lab.html, foresight.html, foresight_programs.js | linked |
| pubpartner.html | PubPartner — Your AI friend, carried across models | main.py, pubpartner_core.py, pubpartner_preflight.py, pubpartner_app.py | linked |
| pubworld_stage.html | PubWorld — Stage Builder | main.py, foresight.html, foresight_programs.js | linked |
| safe_console.html | PubCast Safe Console | main.py | main.py only |
| stage.html | PubCast AI â€” Stage | main.py, control_room.html, foresight.html, foresight_programs.js (+2) | linked |
| stage_3d.html | PubCast AI — 3D Studio (Experimental) | director_console.html, stage_panoramic.html | linked |
| stage_panoramic.html | PubCast AI — Panoramic Studio | main.py, foresight.html, foresight_programs.js, stage.html | linked |
| studio_control_room.html | PubCast AI — Studio Control Room | main.py, studio_websocket.py, foresight.html, foresight_programs.js | linked |
| take_editor.html | PubCast Take Timeline | studio_slate.js | linked |
| twoi_chat_archive.html | 2i · Chat Archive | main.py | main.py only |
| typewriter_console.html | PubCast Typewriter | studio-desk.js, main.py | linked |
| waiting_room.html | PubCast AI â€” Airlock | main.py, foresight.html, foresight_programs.js, human_visits.js (+1) | linked |
| world.html | PubWorld — A Rear View Foresight Production | main.py, foresight.html, foresight_programs.js, world_walk_live.js | linked |
| world_chat.html | 2i · Chat | main.py | main.py only |
| world_walk.html | Bella Faux Pas Studio | bella-live.html, main.py, studio_progress.py, production25d.html (+2) | linked |
