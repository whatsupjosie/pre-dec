# Control Room operator completion — 2026-11-26

## Ownership and preservation

- Working branch: finish/control-room-operator. Common base a4fafd1cf611cc1c77aad38c013c35a4f5e5ed35.
- Engine branch finish/control-room-engine belongs to Claude. No backend source edits, no main merge, no force push.
- Previous checkpoint fdc3ce90a0ef6997df66ec0f878ca66c822d1d3d. This round: b9631b0 (framing), ca1d6b6 (graphics/prompter/VTR confidence), 5f714c6 (switch/monitor hardening); browser tests and this handoff follow.
- Preserve the recovered photographic console, stage presets, renderer, clacker, full prompter and local take pipeline; avoid rewriting working components.

## Implemented

- Prior five commits: all three recording-mode controls, source selection/preflight, pause/resume, shared clocks, audio gain contract, timeline controls, genuine low-rate 2.5D confidence images, recording library and streamed ZIP export.
- Local Preview/Program camera framing: WASD with explicit opt-in, arrow buttons, zoom 1–4x, reversible preset reset. Local render uses effective shot. Frame edits logged as camera.framing with camera id, role, center, zoom; initial overrides in production.start.cameraFraming.
- A camera simultaneously on Program and Preview cannot be adjusted via the Preview control; explicit Program selection required. Block editing while the local camera pool is active; prevent creation of a pool with unsynchronized overrides. Cross-browser distribution of camera poses is not implemented.
- Shared lower_third cue reaches 2.5D Program canvas and is logged on change. Clear from the console; bounded text in render. Local stage can cue graphics when disconnected.
- Same-device one-time full prompter script handoff via random BroadcastChannel; source script preserved and no text in URL or request. Not a cross-device teleprompter protocol.
- VTR checks the local asset and offers confidence playback; server cue acknowledgement is no longer falsely presented as confirmed Program playback.
- Serialize camera mutations; bound registry polling, reject stale responses, guard image freshness, hold monitors closed through PANIC/blackout/test-bars command and recover only after a fresh response.

## Actual evidence, not release certification

- 12 framing logic assertions passed against source before commit (44 cumulative focused assertions including previous rounds).
- Syntax parsing of modified scripts passed in the connector's JS runtime.
- Local container cannot resolve github.com; fetched three JS modules from GitHub and reconstructed byte-for-byte. Verified Git blob hashes: framing 23cb1b4bcfe56195e3624bf1e135d1b3355ecb8b, guard bbe8ce008c6b550861871dd2347efaf6f7eab89c, prompter 2da6e5254dcfd9d3f9ebd0d3b518731d4fb9e73b.
- Actual Chromium 144, isolated component harness at 390x844 with test-double host responses: PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q tests/test_operator_components_browser.py -> 3 passed, 1 skipped. Camera buttons/keyboard/reset/lock, confidence hold/blackout/timeout/recovery and prompter validation passed. Cross-tab handoff skipped due to ERR_BLOCKED_BY_ADMINISTRATOR at isolated localhost origin. Not full-app end-to-end.
- Run the committed test with an ordinary Chromium environment and full host test suite. Existing clacker audio/video synchronization and 30-minute endurance remain unverified here.

## Integration contract and remaining work

- Claude owns distributed camera pose registration and authoritative output; coordinate camera.framing event ingestion and shared registry framing updates before enabling camera pool adjustments.
- VTR needs a real authoritative Program source and audio routing (not just mode=REPLAY/on_air state). Keep confidence playback separate. Require actual decoded frame and recorded audio/video proof.
- Existing independent participant audio/stems and true VU need backend channel IDs and lifecycle contract from engine branch; no invented meters.
- Confirm production-state authorization, lower_third and video-cue response schema; test stage render plus actual recorded lower third.
- Verify recording-state event reconciliation and reload/reconnect, recording modes, pause/resume, PANIC, archive download/import, and remote guest endurance. Verify browser assets and operator usability at desktop/tablet/phone sizes.
- After engine handoff, compare changed files and interfaces before merging; never blindly overwrite. Full integrated production acceptance is the release gate.
