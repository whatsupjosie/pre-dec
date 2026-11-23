# PubCast / PubPartner — Project Handoff

Distilled from a long Gemini design chat. This captures decisions made, not conversational flavor. Use this to re-onboard a new session fast.

## 1. The Big Picture
- **PubCast** = the whole show/platform: a 2.5D/3D gamified virtual production studio (stage, control room, crew).
- **PubPartner** = originally a piece of PubCast, spun out into its own standalone product: a persistent AI companion/assistant, LLM-agnostic, usable with or without PubCast.
- **Iteration Wallet** = a separate secure workspace for assets, rules, tools, and edit history.
- All three are treated as independent "programs" (like windows/boroughs in one city) that share underlying logic but don't force each other to load.

## 2. Identity Architecture: Cartridge + Memory Card + Console
Metaphor: retro game hardware.
- **Cartridge (~1MB)** — lightweight, swappable identity/role layer: behavioral constitution, tone rules, voice params, positive/negative exemplars, *base/core memories only* (who they are, who you are, the relationship's core facts). This is what makes a partner instantly "themselves" even with nothing else loaded.
- **Memory Card (large, growable)** — the actual save file: full episodic history, project artifacts, lyrics, audio/image assets, deep evidence/theories. Tied to a specific cartridge via hash/ID. Without it, the partner is still fully "them," just can't recall specific past events ("the Cancun test") — and should say so honestly rather than confabulate.
- **Console / Runtime (PubPartner itself)** — the universal translator. This is the piece that should be tailored per-environment, NOT the cartridge. It adapts identity+memory to whatever cognitive engine (local LLM, cloud API) and embodiment surface (text, voice, PubWorld, VR/metaverse via VRM/glTF avatar export) it's plugged into.
- Key architectural principle: **cartridges stay pure/declarative** (personality+role+rules); **PubPartner is the adapter layer** that does the heavy lifting of compatibility. Don't push universal-compatibility requirements down into the cartridge.

## 3. Current Codebase Assessment (as of the review in-chat)
**Working:**
- Core spine: `AlexCore`, `MemoryCore`, `AlexJeremyBridge` — state machine (GUIDE/COMPANION/MIRROR/ANCHOR/WITNESS) + offline snapshot/restore.
- `FCP1Packet` / `VerbatimVault` — verbatim text (lyrics, quotes) stored as immutable reference IDs instead of dumped into LLM context. Tested, restorable.
- `PubPartnerProviderDispatcher` — clean provider-neutral routing with graceful degrade to mock/offline on missing keys or failed endpoints.
- Prebeta UI shell (`pubpartner.html/css/js`) — modular panel layout, passes layout-contract tests.
- Most advanced overall build referenced: **PubPartner PreBeta 12** (`0.1.0-prebeta.12+responsive-tray-hardening.20260728`), superseding prebeta.8. Used as the authority in a donor-code audit that rejected older "Thinking Context"/"EQ Suit" packets.
- Most advanced *PubCast-only* build referenced: **PubCast 5.6** ("solid, can be trusted").

**Broken / fragile:**
- Memory hygiene: near-everything gets stored as a memory node — no promotion gate between transient chatter and durable relationship facts → long-term context pollution risk.
- `_estimate_valence()` / `_classify_memory_type()` are keyword/string heuristics, not real NLP — miss sarcasm/nuance.
- Multiple competing memory authorities in parallel (`UniversalMemorySystem`, `MemoryIndex`, `CricketKeeper`, `MemoryCore`) risk desync.
- Rust FFI mesh rendering path decodes but the full GPU draw loop is unwired; some vision routes from earlier specs are missing from the active tree.

**Recommended next engineering steps (in priority order):**
1. Build an Evidence & Promotion Layer — gate what gets written to durable identity tables (require confidence threshold or explicit user confirmation).
2. Unify all memory reads/writes behind `MemoryCore` / the single SQLite engine; kill parallel stores.
3. Wrap `PubPartnerProviderDispatcher` calls in independent per-provider `CircuitBreaker`s so one dead endpoint can't hang the app.
4. Finalize `.pubpartner` as a clean, atomic, single-file SQLite container (mount/unmount/backup/duplicate).
5. Physically decouple the Cartridge (identity) from the Memory Card (history) into separate swappable files — this is designed conceptually but not yet split in code.

## 4. Voxel Engine — Dual-Engine Worker Architecture (for the 3D/broadcast side)
Goal: prevent the compute-heavy engine from freezing/crashing the host machine.
- **Dual-Engine split**: Main Thread (visual/UI, "Core 1") vs. Compute Worker (heavy meshing/culling/physics, "Core 2"), communicating via SharedArrayBuffer + message passing.
- **CPU Budget Governor**: heavy loops get an ~8ms time budget per tick; they yield (non-blocking) instead of hogging the thread.
- **Dynamic Memory Watchdog**: monitors worker memory (soft cap ~1–2GB); on approach, soft-evicts least-critical data (e.g., compresses undo history) rather than crashing.
- **Job Queue Gate**: single-job serialization (`isJobRunning` / AppState check) — prevents stacking simultaneous heavy jobs (e.g., spamming "Bake Mesh").
- **Intelligent Resource Management (IRM)** — the adaptive layer on top of the above:
  - Health Score from FPS + input latency (Excellent / Stable / Struggling thresholds defined in-chat).
  - **Event-driven, periodic checks** (not constant): timer starts only during BAKING/DISMANTLING/REBUILDING or high voxel count, runs every 3–5 seconds, stops when load drops.
  - Actuator: dynamically adjusts `VOXEL_BATCH_SIZE` (±20%/40%) based on health score.
  - Debugged refinements: averaged/damped adjustment (5-sample window, max 10%/cycle) to prevent oscillation; visibility-aware `requestAnimationFrame` timer instead of `setTimeout`; immediate-check flag if FPS drops below 20; Worker re-reads batch size from SharedArrayBuffer every loop iteration (not just once) to avoid stale-config race conditions.
- Garbage/dead code elimination handled via standard tree-shaking (Webpack/Rollup/Vite) + minification (Terser) at build time — no custom system needed.

## 5. UI System
- **Two UIs**: (1) a full 2.5D/3D gamified studio map for PubCast production, (2) a **floating tray system** as the lightweight, phone-friendly home-screen/menu layer (this is effectively the PubPartner interface).
- **Tray = window.** Each tray is an isolated context: control room, live feed, crew chat, public chat, a personal chat with your partner, etc. Jump between them without paying the render cost of the full 3D map.
- **Borough metaphor**: PubPartner, PubCast, Iteration Wallet are independent "blocks" in one city, connected by shared memory/roads but individually lightweight to load.
- **PubCast-launch transition**: opening PubCast from inside PubPartner pops a welcome tray to center stage briefly, then shrinks/docks it into the top menu bar (menu icons visually "arrive" from it), while your active tray stays prominent. Accompanied by a brief bloom/glow + soft focal-blur flash (half a second, not painful) to draw attention to the new menu items, optionally with a soft sound cue.
- **Foreign apps run *inside* PubPartner trays** (e.g., a Facebook tab), not the other way around — PubPartner acts as the sandboxed host/OS shell, not a guest in someone else's environment. For true external 3D spaces (metaverse platforms), the partner's avatar exports as a standard VRM/glTF "shell" while cognition/memory stay local, tethered via API/WebSocket — with a restrictive "Travel Cartridge" limiting what gets remembered/shared off-device.
- **Agent-controlled desktop trays**: a picture-framed window showing a *PubPartner-mediated* view of your desktop (never raw OS access). The AI can be handed control to click/type/scroll inside that frame only. Full transparency — you watch everything live; closing the tray (✕) is an instant, total kill switch.
- **Blackbox logging**: every keystroke and mouse action inside an agent-controlled tray is recorded (same Blackbox layer used elsewhere for authority actions) — a tamper-proof action ledger.
- **Speed Bar / Output Governor**: the LLM can think/process at full speed internally, but on-screen *actuation* (typing) is throttled to a set WPM (e.g., up to ~100 WPM) so a human can watch and steer in real time, or set to full autonomous speed for unsupervised runs.

## 6. Collaborative Writing / Teleprompter Mode (the most fully-specified feature)
The core insight: stop treating AI output as an all-or-nothing block; make it a steerable, reviewable stream.
- **Layout**: top of screen = finalized, locked manuscript (crisp computer font). Bottom ~2/3 = active staging zone on a lined-notebook/pencil-font visual, where the AI is drafting ~half a page ahead.
- **Buffer size**: needs to be ~5 lines (a small paragraph), not 1–2 — enough for a human to follow along "karaoke style" while the AI reads aloud, and still have time to react before text locks in.
- **Reading vs. locking**: when read aloud, the AI is speaking from the *staging* zone. Only after a line scrolls fully past the buffer/threshold does it convert to finalized computer print — the buffer must give real reaction time, not just be a finish line.
- **Play/Pause/Edit**: hit pause anytime; click into the draft to retype a word/line directly. On resume, the AI absorbs the edit as new ground truth and cascades the change forward through the rest of its *unfinalized* buffer only (e.g., swap which character is speaking → downstream text in the draft updates; text already finalized above the line is untouched).
- **Skeleton-first**: before generating prose, agree on a shared outline/destination for the scene/section (where it needs to end up) so the AI isn't improvising blind — described as "sharing the map before driving."
- **Draft vs. Manuscript state**:
  - Draft (pencil) = fluid, can be silently rewritten/erased by the AI itself when corrected (e.g., "they're still in the restaurant, not the docks") — nothing here is "canon" yet.
  - Manuscript (locked computer print) = permanent once crossed the threshold. The AI can no longer silently edit it. To change it, a paragraph/section must be explicitly clicked and unlocked — ideally **at the paragraph or single-line level**, not the whole document, so a proofread request can't cause collateral edits elsewhere.
- **Auto-finalize on close**: closing the session finalizes whatever was in the buffer, but tags it as an **"unreviewed draft"** rather than fully approved manuscript text — distinct from human-approved finalized text.
- **Format-agnostic**: same engine underlies standard prose, screenplay format (30/60-min, feature), and legal pleading paper (numbered line format) — just a template/formatting layer over the same streaming buffer.
- **Broadcast/teleprompter extension**: same top/threshold/staging structure applies live-on-air — top = live, untouchable broadcast copy; a black-line "staging" zone just below holds incoming edits/breaking updates that can still be caught and fixed before they scroll into the live zone. Explicit design goal: **this is a safety net, not an invitation to edit live** — real broadcast practice is to finalize before air; live edits are last-resort.
- **Stated purpose**: this isn't about hiding AI use — it's about preserving actual authorship. The user stays "hands on the wheel" the whole time (catch bad word choices, redirect wrong turns, approve by not stopping), so the output remains genuinely their voice rather than a one-shot generation they passively accept.

## 7. Open Threads / Things Not Yet Decided
- Exact visual transition mechanics between tray-view and full 3D map (slide vs. overlay) — floated but not settled.
- How deeply a partner should be allowed to "read" content inside a sandboxed foreign-app tray (e.g., summarizing a Facebook tab) vs. staying strictly blind to it for privacy — not settled.
- Whether manual mid-stream corrections should auto-log as a permanent "Lesson" in the Iteration Wallet — floated, not settled.
- Physical Cartridge/Memory Card file-format split is a target, not yet implemented in code.

---
*Compiled as a working handoff — re-verify against actual source files before treating any "working/broken" status above as current, since the underlying transcript may predate later changes.*
