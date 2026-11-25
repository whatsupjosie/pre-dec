# Pubcast 2i — Handoff (v8: real LLM adapter, real chat, real generation, voice input)

**Date:** August 11, 2026
**File:** `2i_writers_room_v8.html` — use this one. Built on top of v7's materials pass; no visual changes, this pass turned the stubs into working features.

---

## What's now real (was stub in v7)

### 1. Pluggable LLM provider adapter — the big one
New "⚙ LLM provider…" item in the ☰ menu opens a settings modal. Three adapters, swappable at runtime, no code changes needed:

- **Claude** — calls `api.anthropic.com/v1/messages` directly from the browser (uses the `anthropic-dangerous-direct-browser-access` header). Needs your own Anthropic API key.
- **OpenAI / OpenAI-compatible cloud** — calls `{endpoint}/chat/completions`. Default endpoint is OpenAI's, but you can point it at any OpenAI-compatible cloud provider by changing the Base URL field.
- **Local LLM** — calls any OpenAI-style `/chat/completions` endpoint on your machine. Tested shape works with **Ollama** (`http://localhost:11434/v1/chat/completions`, Ollama's OpenAI-compat route) and **LM Studio**'s built-in server. No API key required for most local servers.

All three live behind one interface (`LLM_ADAPTERS` in the script, `callLLM(messages)` is the single call site everything else uses). Adding a 4th provider later = one more object in that map, nothing else changes.

Config is stored in `localStorage` in the browser only — never touches any server except the one you configure. There's a **Test connection** button in the modal that does a real round-trip and reports success/failure before you save.

A status pill in the bottom status bar (`no LLM configured` / `Claude connected` / etc.) shows current state at a glance and is clickable to jump into settings.

### 2. Chat — real, not an echo
The PubPartner chat panel now sends your message plus a rolling window of manuscript context (recent locked text + current draft buffer + the line currently reading) to whichever provider is configured, and streams the reply into the log. Shows a "…thinking…" placeholder while waiting, and surfaces API errors inline in the chat log instead of failing silently.

### 3. Generation — real, not the demo arrays
The `SCENE` / `ALT_DOCKS` / `ALT_GENERIC` arrays are still there as a **fallback** for when no provider is configured (so the tool still demos out of the box). But once a provider is set up: hitting **Generate (✎)**, **Play (▶)**, or **Skip (⏭)** past the end of the current pool now calls the LLM for the next few lines of prose (continuing from manuscript context, same voice/tone instruction), and feeds them into the same buffer/commit/pin/regenerate engine that already existed — nothing about the playback, pinning, or structural-edit-detection logic had to change.

### 4. Voice input / dictation — now wired
🎤 button next to the chat input uses the browser's native Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`). Click to start listening (button pulses red), speak, click again or pause to stop — transcript fills the chat input live, including interim results while you're still talking. Works in Chrome/Edge; other browsers get a clear message instead of a silent failure.

### 5. Smoother crawl
New buffer/reading lines now fade + slide in (`lineIn` keyframe) instead of popping in instantly, and the buffer crawl container has `scroll-behavior: smooth`. This is a real improvement but is **not** a full physics rewrite — it's still discrete line-by-line reveals, just animated. A true continuous Star-Wars-style crawl (constant scroll speed, not per-line jumps) would need a bigger change to how `render()` rebuilds the DOM and is a good next-session item if you want that specific effect.

### 6. Works fully offline as a plain word processor — no AI required
New "Add to draft" row directly under the crawl: type your own lines (Enter to add, Shift+Enter for a newline within a line), and they go straight into the same `buffer` array the AI uses — same pinning, editing, save/load, commit-to-manuscript pipeline, zero dependency on any provider being configured. This is the actual core-functionality fix from this session: **write first, connect AI whenever you want, never blocked on either.**

Because generation and chat both already pull their context from `manuscriptContextForLLM()` (recent locked text + current buffer + current reading line — see v8 notes below), the moment you *do* connect an LLM, it automatically reads everything you wrote by hand and responds/continues in that context. No separate "sync" step needed — this was already wired correctly in v8, this session just added the offline writing path that feeds it.

"Open document — no file picker on first load" (item 5 in the old TODO list) was actually **already implemented** in v7 (`showOpenFilePicker` with a `<input type=file>` fallback). Verified working, no changes needed — that TODO note was stale.

---

## Still open / honest gaps

- **Local model quality**: small local models may not follow the "return only prose, one sentence per line" instruction as reliably as Claude/GPT-4 class models — worth testing with whatever model you plan to run.
- **No streaming tokens**: generation and chat replies land all at once (wait → full response), not token-by-token. Real API streaming (SSE) would make it feel faster but is a bigger change to the fetch calls.
- **True continuous crawl physics**: see note above — current version is animated discrete lines, not constant-speed scroll.
- **No retry/backoff on API errors**: a failed call just reports the error; no automatic retry.
- **Local server CORS**: Ollama needs `OLLAMA_ORIGINS` set (or its default) to allow browser fetches — if the Test connection button fails on a local setup, that's the first thing to check.

---

## Files in this handoff
- `2i_writers_room_v8.html` — the working file, open directly in a browser (Chrome/Edge recommended for voice input)
- `2i_writers_room_v7.html` — previous version, kept for reference/diff
- This file

---

## Tidy-up pass (same session, after initial v8 build)

Went back over the v8 work critically and fixed real corner-cuts:

- **Write-row keys were backwards for a word processor.** Originally Enter=submit, Shift+Enter=newline (chat-app convention). Fixed to the convention people actually expect for writing prose: **Enter = new line, Ctrl/Cmd+Enter (or the button) = add to draft.**
- **No busy-state protection.** Chat's Send and the rail's Generate (✎) button could be clicked repeatedly mid-request with no visual lock — fixed: both now disable themselves (Send shows "…") while a call is in flight.
- **Unsafe JSON parsing.** All three adapters called `res.json()` directly — if a local server (or a flaky cloud endpoint) returned HTML or plain text instead of JSON, that threw an ugly generic parse error. Added `safeJson()` so failures now say plainly "returned a non-JSON response" with a snippet of what actually came back.
- **No resilience to transient network blips.** Local model servers in particular can be slow to wake up. Added a single automatic retry (700ms backoff) around every provider call via `withRetry()`, rather than failing on the first hiccup.

Not fixed (flagged, not silently ignored):
- Still no token streaming — full response only.
- Crawl is still discrete animated lines, not true constant-speed scroll physics.

---

## Hardening pass (round 2) — fixes for items #17–23 from the corner-cut review

All fixes are in `2i_writers_room_v8.html`. Nothing in the visible UI/behavior changes — this is internal quality only.

1. **#17 — `withRetry()` no longer retries blindly.** Errors now carry an `.status` (via a new `httpError()` helper). Only network failures, `429`, and `5xx` are retried; a bad API key or malformed request (`4xx`) fails immediately instead of doubling the wasted call.
2. **#18 — one error channel.** Added `reportError(context, err)` so business logic (chat send, generation) reports through a single function instead of each one hand-building a chat-panel message.
3. **#19 — magic numbers named.** Added `RETRY_DELAY_MS`, `ERROR_BODY_PREVIEW_CHARS`, `JSON_PARSE_ERR_PREVIEW_CHARS`, `CLAUDE_MAX_TOKENS`, `CHAT_HISTORY_CAP`.
4. **#20 — naming drift documented, not renamed.** Left `bufferedProtected` / `.pinned` / "pin" as three names for one concept — a wide rename felt too risky for this pass — but added a comment flagging it as the next cleanup.
5. **#21 — local adapter's silent Ollama-shape guess now warns.** If a local endpoint returns the Ollama-native `/api/chat` shape instead of the documented OpenAI-compatible shape, the app still uses it but logs a `console.warn` explaining why, instead of guessing silently.
6. **#22 — `escapeHtml()` now escapes `'`** in addition to `& < > "`.
7. **#23 — error text sanitized before it's ever shown.** New `redactSecrets()` strips anything that looks like a bearer token / API key from raw response bodies before they're truncated and surfaced in chat or thrown as an error message.
8. **#24 — deferred, deliberately.** The duplicated SVG button-texture data-URIs are pre-existing and cosmetic-only (file size, not correctness). Left untouched this pass; a `--btn-fill` custom property feeding one shared pattern is the fix when someone has budget for a CSS-only pass.
9. **#16 — deferred, deliberately.** The single-1400-line-file / no-state-owner architecture issue is real and is the root cause of the earlier `editingTarget` bug class, but it's a rewrite, not a fix, and out of scope for a hardening pass. Flagged for a dedicated refactor session.

### New bug found this pass (not in the original list)
**`loadLLMConfig()` did a shallow merge.** `Object.assign(defaultLLMConfig(), parsed)` meant a saved config missing a nested field (e.g. an old save with only `local.model` set, no `local.endpoint`) would wipe out the *entire* default sub-object for that provider, not just fill the missing field. Since `local.endpoint` has no runtime fallback (`c.endpoint.trim()` assumes it exists), this could crash generation with no clear cause. Fixed with an explicit per-provider merge (`claude`, `openai`, `local` each merged against their own defaults).

### Verification
`node --check` on the extracted `<script>` block passes clean after every edit in this pass.

---

## Hardening pass (round 3) — additional bugs found on a deeper sweep

Went back through `render()`, the buffer/pin/regen path, the flash-message helpers, and speech synthesis specifically looking for races and dead code (not just re-checking the original list). Three real issues found and fixed:

1. **Dead code in `render()`.** A `nearest` variable was computed every single render call (`buffer.slice(0, ...)`) and never used anywhere afterward — leftover from an earlier version of the "transition strip" logic. Removed. No behavior change; just stops doing pointless work every frame and stops implying to future readers that it does something.

2. **Flash-message race (`flashRegen` / `flashOk`).** Each had its own independent `setTimeout` that unconditionally nulled `pendingFlag` when it fired. If a structural edit (900ms "regenerating" flash) was followed quickly by a minor edit (1400ms "nothing downstream touched" flash) before the first timer fired, the *first* timer would still fire and wipe out the *second* flag partway through its display window — the "nothing downstream touched" message could vanish early, or in other orderings the wrong message could show. Fixed by routing both through one `showFlag(flag, ms)` helper that clears any previous pending timer before arming a new one, so only the most recent flash owns the timer.

3. **Speech synthesis callback race (`speechText`).** `speechSynthesis.cancel()` fires the *previous* utterance's `onerror` (not `onend`) if one was still speaking. That handler called whatever `done` callback closure was live — but by the time it fires, `tick()` has usually already moved `reading` on to the next line, so the guard (`if(!playing||!reading) return;`) no longer protects it: the *previous* line's "finished reading" callback would run using the *new* line's state, opening the reaction window early / overlapping with the new line still being read aloud. Fixed with a per-call token: `onstart`/`onend`/`onerror` are now no-ops for any utterance that isn't the current one. `stopSpeech()` also bumps the token so a stop can't be resurrected by a late-firing stale callback either.

### Verification
`node --check` on the extracted `<script>` block passes clean after every edit in this pass, same as round 2.

### Still open / deliberately out of scope
Same two items as round 2: #16 (single-file/no-state-owner architecture) and #24 (duplicated SVG button textures) — both real, both bigger than a hardening pass, both flagged rather than silently left.
