# PubCast V10 Market-Ready TODO

A prioritized checklist to move the current PubCast scaffold to a production-ready release that honors the 16ms frame budget, shared-memory bridge, steampunk control HUD, and the Curtsey/Sir Purfluous/Alex cast.

## 0) Safety & backups (do before heavy changes)
- Create a full backup of the repo prior to experimental engine/capture work (e.g., `tar czf pubcast-backup.tgz .`).
- Gate any moonshot refactors behind an explicit opt-in and keep the current branch green.

## 1) Twin-core C++ engine completion (1080p/480i, 60fps target)
- Author `cpp_core/CMakeLists.txt` to build `main.cpp` + `camera_capture.cpp` into a single binary; add a release profile with `-O3`, LTO, and PCH.
- Finalize SHM contract (`PubCastBridge.h` + `shm_layout` mirror): camera state array, switcher state, command ring buffer, GPU health/FPS fields; add version tag + checksum to detect mismatches.
- Lock the command contract to the lowercase verbs now used by the bridge (`register_camera`, `load_scene`, `ptz`, `record_start`/`record_stop`) so the Python/UI calls land in the ring without being treated as heartbeats.
- While Unreal is unavailable, stand up a CPU/OpenGL fallback renderer that can load GLTF/OBJ and emit 1080p/480i frames into the mux path so the pipeline is functional before the full GPU stack lands.
- Implement GPU-backed rendering with a swap-safe fallback buffer ("Technical Difficulties") when stalls exceed 2 frames; ensure program feed encode to MP4 1080p@30 (with 480i fallback) never drops frames.
- Expose PTZ deltas, scene-load, record start/stop, and avatar pose commands via the ring buffer; ack each command back into SHM for Python polling.
- Add a 3s boot budget check: log and refuse to serve frames if initialization overruns.

## 2) Python bridge & media pipeline hardening
- Replace simulated bridge send/recv with real SHM attachment and ring-buffer enqueue/ack parsing; surface bridge health + FPS to the UI.
- Keep shared-memory lifecycle explicit: the bridge owns/unlinks when it creates the block; test harnesses should attach/detach cleanly without BufferError noise.
- Wire FFmpeg-based recording (H.264 + AAC) with file rollover, disk-space guardrails, and 480i/1080p presets; feed mux start/stop into `RecordingLibrary` with accurate duration/size.
- Connect audio mixer scaffolding (mute/solo/meters) to the record bus; persist mixer state alongside switcher layouts.
- Add structured logging (JSON) for command enqueue/acks, heartbeats, and mux lifecycle; ensure all loops sleep/yield to avoid CPU spin.

## 3) Scene graph & assets (The Noir Lot / The Talk Show)
- Load GLTF/OBJ scenes for Noir (volumetric spots, film grain post, vintage camera mesh) and Talk Show (bright studio, wood desk, velvet sofa, skyline backdrop).
- Implement active-camera LookAt IK for the avatar; maintain 16ms budget by profiling draw/animation passes and culling when idle.
- Add scene-load commands to SHM and confirm state reflection in Python snapshots and UI badges.

## 4) Avatar & cast integration
- Deliver Curtsey avatar asset (`static/avatars/curtsey.gltf` or OBJ): ~25â€“50k tris, 34DD silhouette, steampunk wardrobe, rigged with blendshapes; expose pose test in control UI and bridge.
- Keep Sir Purfluous as the theatrical persona (cartoon Peter O'Toole vibe); ensure prompts pull from the latest directive and stay async to avoid render stalls.
- Preserve Alex as text-only assistant (no 3D draw); make UI route chat to Alex when selected while Curtsey handles stage presence.

## 5) Control HUD polish (steampunk theme, low latency)
- Add joystick/PTZ widgets, scene-load buttons, and live FPS/bridge-health badges; ensure every action debounces to stay <16ms per tick.
- Show active/preview/program, recording status (duration/size/health), and avatar status in the header; include offline banner + retry when WS is down >10s.
- Provide keyboard shortcuts (space=cut, R=record, arrow keys=PTZ) with guardrails against rapid repeats; log operator actions in the event log.

## 6) AI/RAG pipeline for Curtsey (Sir Purfluous) and Alex
- Stand up Ollama (Qwen 2/2.5 1B) service with async call path; build a RAG index over PubCast codebase + lore/manuals + cinema/hardware archives.
- Implement trigger hooks: on scene/camera cuts, send system prompts per the directive, return within 2s, and stream output into the control log (prep for TTS).
- Cache recent embeddings and throttle requests to avoid flooding the model during rapid cuts; ensure failures degrade gracefully with operator-visible alerts.

## 7) Ops, packaging, and stability
- Ship systemd/supervisor configs to auto-restart C++ engine and FastAPI app; add health endpoints for liveness/readiness.
- Bundle an "Ops Panel" showing CPU/GPU/disk/network gauges, bridge load, and mux health; emit alerts/webhooks on degraded states.
- Add retention/auto-prune for recordings and snapshots; expose knobs in config/UI.
- Package installation/upgrade scripts (deps, FFmpeg, Ollama model pull) and document platform targets.

## 8) Testing & certification (The Gauntlet)
- Extend gauntlet harnesses to 20+ cycles for PTZ/scene/record/AI triggers; add a 60-minute soak that records 1080p without drops or crashes.
- Keep the shared-memory engine/camera gauntlet as a first-class gate: it must exit without leaked handles and report FPS/command counts for regression tracking.
- Add edge-case tests: bad camera IDs, low disk space, SHM version mismatch, model timeout; verify graceful degradation and zero crashes.
- Capture metrics for each run (FPS, dropped frames, WS disconnects) and store in artifacts for regression tracking.

## 9) Market-ready delivery
- Provide a guided first-run setup (disk/GPU/FFmpeg/Ollama checks) before enabling record.
- Swap placeholder preview with low-latency feed (LL-DASH/HLS/WebRTC) per input with signal bars and audio meters.
- Finalize documentation: operator quick-start, engine build/run, AI setup, backup/restore, and troubleshooting playbook.

## 10) Integrated Council (post-engine hook-up)
- After the twin-core engine is stable and the UI/control surface is wired, stand up the â€œIntegrated Councilâ€ architecture so the user is a first-class participant in the room.
- Backend (`council.py`): replace the prototype with the provided Cocktail Party variant that injects the User as seat #5, shares a single history buffer, and lets the user speak anytime while agents continue autonomous debate; keep mock brain calls swappable with real OpenAI/Gemini/Anthropic/Qwen clients.
- Frontend (`council.html`): replace with the provided stage layout that visually seats Gemma/Chatty/Claudia/Quinn plus â€œYOU â€“ THE DIRECTOR,â€ animates thinking/speaking states, and pipes responses via WebSocket + SpeechSynthesis; keep gold accent (#d4af37) for the user card.
- Flow: user messages broadcast to all agents; 2â€“3 agents reply per turn; manual â€œpokeâ€ can force a specific agent; history stays in window so agents reference each other and the user; ensure TTS is cancel-safe and UI remains responsive.

## 11) Voxel 3D engine final assembly & launch gate
- Lock the Voxel Engine runtime to the shared-memory contract: one authoritative SHM creator, deterministic offsets for camera/switcher/command ring, and checksum/version checks on attach; refuse to render if mismatched.
- Replace simulator loops with real GPU-rendered frames: implement the Noir/Talk Show GLTF scene graph, per-camera LookAt IK on Curtsey, film-grain/volumetric pass for Noir, studio lighting for Talk Show, all within the 16ms frame budget.
- Hook PTZ/scene/record commands from Python through SHM into the render loop and emit acks plus FPS/GPU health back; ensure record start/stop toggles MP4 mux (1080p/480i) without dropping frames or starving UI updates.
- Wire preview/program frame export to the control HUD (LL-DASH/HLS/WebRTC stub acceptable if bandwidth-limited) and ensure the â€œTechnical Difficultiesâ€ buffer swaps in instantly on GPU stall or scene load failure.
- Integrate the audio path: pass mixer outputs into the muxer, keep lipsync within Â±1 frame, and surface meters/health flags in the HUD; fail-safe to muted audio rather than crashing.
- Run a 60-minute soak on the live engine with 20-cycle gauntlet bursts every 5 minutes (PTZ/scene/record), record metrics (FPS, dropped frames, SHM acks, mux errors), and only declare GA when zero crashes and no leaked handles are observed.

## 12) Engine operations hardening & cutover
- Implement a strict SHM/engine lifecycle contract: a single pid owns creation/unlink; add lockfiles + PID stamps, and refuse attach when stale, logging operator guidance instead of crashing.
- Add a â€œbridge conformanceâ€ self-check: on startup, enumerate command verbs in SHM, round-trip a dummy PTZ + record toggle, and fail closed with a readable status if the C++ side or Python side drifts.
- Ship crash-only-noise watchdogs around render, mux, and AI triggers: catch/clip exceptions, downgrade to safe modes (muted audio, frozen last frame, placeholder avatar pose) while keeping UI responsive.
- Build a preflight â€œlaunch checklistâ€ endpoint/UI: GPU/encoder availability, disk free, Ollama up, SHM version, audio devices; block record until all lights are green.
- Add ops hooks: structured event stream for SHM attach/detach, mux start/stop, scene loads, and PTZ bursts; publish to file + stdout with rotation, and surface recent faults in the HUD.
- Cutover plan: run dual-path simulation (sim engine + live engine) in staging for 1 hour with mirrored commands; compare FPS/acks/mux metrics, then flip production to live engine once parity is proven.
