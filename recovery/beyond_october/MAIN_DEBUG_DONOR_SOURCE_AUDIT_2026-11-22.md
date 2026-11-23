# Beyond-October main-debug donor complete-source provenance audit

Date: 2026-11-22
Repository: `whatsupjosie/pre-dec`
Staging recovery branch: `recovery/control-room-beyond-october-2026-11-22`
Parent before this snapshot: `9cf6c82f5b33d4e23dde1d5e64983ea3d91e72de`

Purpose: safeguard the **entire original changed-file contents** of the two studio-rich divergent branches, not merely their commit ancestry. A merge may retain commits while resolving files differently. These are **exact Git blob reuse** snapshots, so binary assets remain byte-identical. None of these donor file snapshots replaces a live path or is a claim that the feature runs.

## main-debug-original-2026-11-19

Original ref: `codex/main-debug-20261119`, commit `d3b9db81fc4a35d05db82de1d0de24dacf17e973`. Diff against current pre-dec/main convergence: 46 changed files (46 present at source tip; 33 blob-identical at active path of staging runtime). Original branch comparison: diverged, ahead 25, behind 322.

| Original file path | Source blob SHA | Bytes | Staging runtime same bytes? | Donor snapshot path |
|---|---|---:|---|---|
| `2i-backend/server.js` | `4e447191afba3abcc753d9fe931393b94e1d5545` | 51613 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/2i-backend/server.js` |
| `2i-backend/test/bridge_contract.test.js` | `7d738d8fc2b0378173d813e20f78bdabaa52ecbc` | 10152 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/2i-backend/test/bridge_contract.test.js` |
| `2i/2i-assets/file-workspace.js` | `1f0ea36f13112fa0486b4228bd9827d24f6df00b` | 10109 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/2i/2i-assets/file-workspace.js` |
| `bin/ws_renderer` | `e3c6e65c29953fce7604d72b11d555d00243a106` | 1813256 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/bin/ws_renderer` |
| `conftest.py` | `40b076be94117dc5b3e40d35f9b33a14e19d4c6e` | 6082 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/conftest.py` |
| `handoffs/MAIN_DEBUG_2026-11-19.md` | `52b9eebd046f522e8db9a2385b615d5732842072` | 12121 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/handoffs/MAIN_DEBUG_2026-11-19.md` |
| `handoffs/MAIN_DEBUG_2026-11-19_EVIDENCE.json` | `aff61a750c61b8f74bb0e43dcce3bd993c38f2a7` | 1374 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/handoffs/MAIN_DEBUG_2026-11-19_EVIDENCE.json` |
| `main.py` | `9d23d1017c74850c8cdff6d2e55938a9fffbf435` | 218300 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/main.py` |
| `modules/cameras_advanced.py` | `173d320fb7d8d14036f82750503cdab0965bc1fc` | 44852 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/cameras_advanced.py` |
| `modules/capture.py` | `a1e54eeae3f5eb141ed40764f41b3aeca0a70422` | 16493 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/capture.py` |
| `modules/evo/camera_manager.py` | `3f3be4315e2fbbaae6a4a20e8aece327f3320546` | 38515 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/evo/camera_manager.py` |
| `modules/evo/switchblade_governor.py` | `abd7e3440e73d774c1a39b89b4bf81463d2cafb6` | 20197 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/evo/switchblade_governor.py` |
| `modules/mocap_integration.py` | `716c34a9c3b5b7e976313d7237b77911e61f03ea` | 22562 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/mocap_integration.py` |
| `modules/production_routes.py` | `15bd0c337348bd34370af41aaac77bfdeefaa4b8` | 30868 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/modules/production_routes.py` |
| `modules/recording.py` | `1c1906110c7b7b85916bfc6459969f020ff6d7b6` | 47051 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/modules/recording.py` |
| `modules/studio_console_actions.py` | `7e8765d94d7aeeeacb0edf8139507b908ded6712` | 7061 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/studio_console_actions.py` |
| `modules/timeline.py` | `b961e270e6a92b5598fe2432d648deba3abc72c2` | 16133 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/timeline.py` |
| `modules/timeline_routes.py` | `6fe81986bf6e42b094d4e7c209e9dc5f01f8cf79` | 9737 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/timeline_routes.py` |
| `modules/wired/NUDGE_MINIMAL.py` | `74528699900421b17f84c38affb520c68d959658` | 8100 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/modules/wired/NUDGE_MINIMAL.py` |
| `rust_crate/src/ws_renderer.rs` | `46fcc3b6afb165eb1005b25606c532b488840d76` | 30682 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/rust_crate/src/ws_renderer.rs` |
| `static/camera_try.html` | `c3ac6e8b189fff2a34bb6a9ea200705ca22c58a5` | 8479 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/static/camera_try.html` |
| `static/control_room.html` | `fb0853843b57a8cb2ff917720d0fc8138179b459` | 32137 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/control_room.html` |
| `static/director_switcher.html` | `e3eee5fec57fa73b240ecd98d7df02acecd5555b` | 51523 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/director_switcher.html` |
| `static/foresight_counter.html` | `fb73aef2e0d89112d10c97ac9763870a9b916227` | 38809 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/foresight_counter.html` |
| `static/production25d_app.js` | `b286d86d57c6dd77068df4a9b0360dde888da2bd` | 36178 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/production25d_app.js` |
| `static/production25d_storage.js` | `101f62fc851fc3bf4d63acc04d5bce77f0a51a07` | 4832 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/production25d_storage.js` |
| `static/program_audio_runtime.js` | `77481d15a0479258a1247dc01209a7990126d371` | 13939 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/program_audio_runtime.js` |
| `static/world_walk.html` | `b59eeef78763f17dedff9a7f8d649545b10c903e` | 103368 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/static/world_walk.html` |
| `static/world_walk_live.js` | `3e6daba496cb1cd3984c1c986912b73a716f9783` | 19182 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/static/world_walk_live.js` |
| `tests/alex_little_one/test_public_baby_role.py` | `c10a9ab16f2e0afa67c06e29a2e44a44b9af86bb` | 13052 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/alex_little_one/test_public_baby_role.py` |
| `tests/conftest.py` | `7e71877f6fd39e79b5b0a15e29b3efdf97b64cf6` | 2600 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/conftest.py` |
| `tests/test_audio_room_policy_node.js` | `1cb46864788e52be574ad8c87a12c7110de1f0df` | 1774 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_audio_room_policy_node.js` |
| `tests/test_bella_faux_pas_progress.py` | `945b7f11d3e90d36d6d0c7872d7830ec8c94c07c` | 13547 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_bella_faux_pas_progress.py` |
| `tests/test_camera_configuration_restart.py` | `fdcd8b1a4c56c50bfdd8a9805e06cb762fdfe0a1` | 1046 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_camera_configuration_restart.py` |
| `tests/test_camera_try_browser.py` | `61e0baba6ef84aea58c5f9099de1ef4c6fc2db7d` | 3730 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_camera_try_browser.py` |
| `tests/test_data_checkpoint_host_recovery.py` | `ebc572166c40e8441d47a494cf77c502148b6016` | 15534 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_data_checkpoint_host_recovery.py` |
| `tests/test_foresight_counter_layout_host.py` | `6fb6d5fc2d387c02c5c97afe3af28810e4d2cc6b` | 10175 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_foresight_counter_layout_host.py` |
| `tests/test_foresight_counter_workspaces.py` | `dd6a13c026f95740466d86c0a35e67d01d4a7826` | 18728 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_foresight_counter_workspaces.py` |
| `tests/test_foresight_file_workspace.py` | `732309c6a47ffd32b589aad9bd0a2754500afdaa` | 22707 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_foresight_file_workspace.py` |
| `tests/test_foresight_owner_recovery_node.js` | `ace77f96508ad14fdda007b85bd2130a4c98d36d` | 7708 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_foresight_owner_recovery_node.js` |
| `tests/test_production25d_browser.py` | `f47b9df037fb7496999cf5d292ae5c7c658c5f4e` | 20497 | DIFFERS/ABSENT | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_production25d_browser.py` |
| `tests/test_recording_portable_bundle.py` | `75d67cbb46116e8c2e6379cd93087e2e13711775` | 12488 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_recording_portable_bundle.py` |
| `tests/test_speech_host_acceptance.py` | `5346e61da546e56cfb2032fb3a32bea784d86cc5` | 16031 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_speech_host_acceptance.py` |
| `tests/test_studio_console_action_routes.py` | `8804d7bc6464a5207c52929430544f20d1319d39` | 12625 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_studio_console_action_routes.py` |
| `tests/test_timeline_playback_controls.py` | `36e93f55e130078d2c741579529247c0e452843a` | 4433 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tests/test_timeline_playback_controls.py` |
| `tools/acceptance/studio_long_take.py` | `45d34e44d7516cf60207ca1e8ba3596874141419` | 2470 | YES | `recovery/beyond_october/main-debug-original-2026-11-19/tools/acceptance/studio_long_take.py` |

## main-debug-union-trial-2026-11-20

Original ref: `integration/main-debug-union-trial-2026-11-20`, commit `eacde8753402447e3454b07622fb2fcec8dd17e7`. Diff against current pre-dec/main convergence: 43 changed files (43 present at source tip; 43 blob-identical at active path of staging runtime). Original branch comparison: diverged, ahead 26, behind 2.

| Original file path | Source blob SHA | Bytes | Staging runtime same bytes? | Donor snapshot path |
|---|---|---:|---|---|
| `2i-backend/server.js` | `4e447191afba3abcc753d9fe931393b94e1d5545` | 51613 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/2i-backend/server.js` |
| `2i-backend/test/bridge_contract.test.js` | `7d738d8fc2b0378173d813e20f78bdabaa52ecbc` | 10152 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/2i-backend/test/bridge_contract.test.js` |
| `bin/ws_renderer` | `e3c6e65c29953fce7604d72b11d555d00243a106` | 1813256 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/bin/ws_renderer` |
| `conftest.py` | `40b076be94117dc5b3e40d35f9b33a14e19d4c6e` | 6082 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/conftest.py` |
| `handoffs/MAIN_DEBUG_2026-11-19.md` | `52b9eebd046f522e8db9a2385b615d5732842072` | 12121 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/handoffs/MAIN_DEBUG_2026-11-19.md` |
| `handoffs/MAIN_DEBUG_2026-11-19_EVIDENCE.json` | `aff61a750c61b8f74bb0e43dcce3bd993c38f2a7` | 1374 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/handoffs/MAIN_DEBUG_2026-11-19_EVIDENCE.json` |
| `main.py` | `6ed12a020f8bb0e3761fb61ba936af7b99f805fe` | 225723 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/main.py` |
| `modules/cameras_advanced.py` | `173d320fb7d8d14036f82750503cdab0965bc1fc` | 44852 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/cameras_advanced.py` |
| `modules/capture.py` | `a1e54eeae3f5eb141ed40764f41b3aeca0a70422` | 16493 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/capture.py` |
| `modules/evo/camera_manager.py` | `3f3be4315e2fbbaae6a4a20e8aece327f3320546` | 38515 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/evo/camera_manager.py` |
| `modules/evo/switchblade_governor.py` | `abd7e3440e73d774c1a39b89b4bf81463d2cafb6` | 20197 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/evo/switchblade_governor.py` |
| `modules/mocap_integration.py` | `716c34a9c3b5b7e976313d7237b77911e61f03ea` | 22562 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/mocap_integration.py` |
| `modules/production_routes.py` | `8d273aa80e54b7977e28d409cc3dcc0ca8ff4655` | 32378 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/production_routes.py` |
| `modules/recording.py` | `23fbeb145a291664b8883ffd4dd9fb769fbf9dd3` | 56200 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/recording.py` |
| `modules/studio_console_actions.py` | `7e8765d94d7aeeeacb0edf8139507b908ded6712` | 7061 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/studio_console_actions.py` |
| `modules/timeline.py` | `b961e270e6a92b5598fe2432d648deba3abc72c2` | 16133 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/timeline.py` |
| `modules/timeline_routes.py` | `6fe81986bf6e42b094d4e7c209e9dc5f01f8cf79` | 9737 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/timeline_routes.py` |
| `modules/wired/NUDGE_MINIMAL.py` | `74528699900421b17f84c38affb520c68d959658` | 8100 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/modules/wired/NUDGE_MINIMAL.py` |
| `rust_crate/src/ws_renderer.rs` | `46fcc3b6afb165eb1005b25606c532b488840d76` | 30682 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/rust_crate/src/ws_renderer.rs` |
| `static/camera_try.html` | `c3ac6e8b189fff2a34bb6a9ea200705ca22c58a5` | 8479 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/camera_try.html` |
| `static/control_room.html` | `fb11a555fafac1dbacda64cdb221e51cc5426ca4` | 32295 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/control_room.html` |
| `static/director_switcher.html` | `7b500debf6ed259795f003ed3cd91a57253a0542` | 51840 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/director_switcher.html` |
| `static/foresight_counter.html` | `9e14c4a8d9015281a6ce84e702ba9695f737360e` | 40556 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/foresight_counter.html` |
| `static/program_audio_runtime.js` | `2e8efb038d67b6c4cd6969bf984da61742931ae7` | 17931 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/program_audio_runtime.js` |
| `static/world_walk.html` | `61ab893d391c4f263de07db8ac524bbf5444c5b7` | 104440 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/world_walk.html` |
| `static/world_walk_live.js` | `3e6daba496cb1cd3984c1c986912b73a716f9783` | 19182 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/static/world_walk_live.js` |
| `tests/alex_little_one/test_public_baby_role.py` | `c10a9ab16f2e0afa67c06e29a2e44a44b9af86bb` | 13052 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/alex_little_one/test_public_baby_role.py` |
| `tests/conftest.py` | `7e71877f6fd39e79b5b0a15e29b3efdf97b64cf6` | 2600 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/conftest.py` |
| `tests/test_audio_room_policy_node.js` | `1cb46864788e52be574ad8c87a12c7110de1f0df` | 1774 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_audio_room_policy_node.js` |
| `tests/test_bella_faux_pas_progress.py` | `945b7f11d3e90d36d6d0c7872d7830ec8c94c07c` | 13547 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_bella_faux_pas_progress.py` |
| `tests/test_camera_configuration_restart.py` | `fdcd8b1a4c56c50bfdd8a9805e06cb762fdfe0a1` | 1046 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_camera_configuration_restart.py` |
| `tests/test_camera_try_browser.py` | `61e0baba6ef84aea58c5f9099de1ef4c6fc2db7d` | 3730 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_camera_try_browser.py` |
| `tests/test_data_checkpoint_host_recovery.py` | `ebc572166c40e8441d47a494cf77c502148b6016` | 15534 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_data_checkpoint_host_recovery.py` |
| `tests/test_foresight_counter_layout_host.py` | `6fb6d5fc2d387c02c5c97afe3af28810e4d2cc6b` | 10175 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_foresight_counter_layout_host.py` |
| `tests/test_foresight_counter_workspaces.py` | `dd6a13c026f95740466d86c0a35e67d01d4a7826` | 18728 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_foresight_counter_workspaces.py` |
| `tests/test_foresight_file_workspace.py` | `f5f3ef5ff0c7028b176001e9a13fa88411a25da0` | 23258 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_foresight_file_workspace.py` |
| `tests/test_foresight_owner_recovery_node.js` | `ace77f96508ad14fdda007b85bd2130a4c98d36d` | 7708 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_foresight_owner_recovery_node.js` |
| `tests/test_production25d_browser.py` | `2d57ba6c4584766272b4feadea9749bbb62499b3` | 20577 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_production25d_browser.py` |
| `tests/test_recording_portable_bundle.py` | `75d67cbb46116e8c2e6379cd93087e2e13711775` | 12488 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_recording_portable_bundle.py` |
| `tests/test_speech_host_acceptance.py` | `5346e61da546e56cfb2032fb3a32bea784d86cc5` | 16031 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_speech_host_acceptance.py` |
| `tests/test_studio_console_action_routes.py` | `8804d7bc6464a5207c52929430544f20d1319d39` | 12625 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_studio_console_action_routes.py` |
| `tests/test_timeline_playback_controls.py` | `36e93f55e130078d2c741579529247c0e452843a` | 4433 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tests/test_timeline_playback_controls.py` |
| `tools/acceptance/studio_long_take.py` | `45d34e44d7516cf60207ca1e8ba3596874141419` | 2470 | YES | `recovery/beyond_october/main-debug-union-trial-2026-11-20/tools/acceptance/studio_long_take.py` |


## Interpretation and restrictions

- Every file changed at these branch tips (except deletions, if any) is retained as a full original Git blob at the snapshot path above. The merged version remains at the live path.
- Historical commits are carried by the recovery branch's ancestry, but this checkpoint explicitly retains the original branch-tip versions even when integration resolved conflicts away from them.
- Some changed files are outside Control Room scope (e.g. 2i). They are included **only** to guarantee that the complete changed-file sets of the studio recovery branches were not silently reduced. These extras do not justify 2i edits in the current recovery task.
- No feature is certified complete or functionally tested by SHA parity or Git history. Real studio recording, camera pixels, audio and export remain subject to the end-to-end acceptance specification.
- Additional post-convergence work from the newer pre-dec camera/live-source/recording branches is separately tracked and has not been imported here.
