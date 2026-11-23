# Pubcast 2i — Handoff (v9: bug-fix pass on top of v8)

**Date:** August 11, 2026
**File:** `2i_writers_room_v9.html` — built on `2i_writers_room_v8.html`, no visual/layout changes. This pass closes out every concrete bug raised across the three v8 review rounds (the "critical functional," "hostile reviewer," and "layered bugs" passes), plus a few more found during the fix pass itself.

Verified: script block extracted and passed `node --check`; brace/paren depth balanced; HTML tag counts balanced (1 `<html>`, 1 `<body>`, 1 `<script>`, 1 `<style>`, each open/close). Not verified: interactive testing in an actual browser — I don't have one in this environment. Please smoke-test before shipping (checklist at the bottom).

---

## Fixed this pass

### Critical — changed real behavior

1. **Demo scaffolding no longer overrides real AI generation.** `rerouteIfTriggered()` previously swapped the entire generation queue over to the hardcoded `SCENE`/`ALT_DOCKS`/`ALT_GENERIC` arrays on *every* structural edit, even with a real LLM configured and generating actual prose. It now checks `llmIsConfigured()` first: with a provider configured, a structural edit just clears the queue (`pool=[]`, `pointer=0`, branch label shows `live (AI-directed)`) and the existing `tick()`/`generateMoreIntoPool()` logic naturally re-asks the LLM using the *edited* manuscript as context. The demo branches are now genuinely just a fallback for out-of-the-box demo mode, as the code's own old TODO comment always said they should be.

2. **Structural-edit detection no longer lies about negated edits.** `isStructuralEdit()`'s keyword check was an unanchored substring match (`/leav/` matched inside "cleave"), and neither the keyword check nor the word-overlap fallback caught negation words ("never," "won't," "can't," "doesn't," "refuses," etc.) — so editing *"she would stay"* → *"she would never stay"* was reported as a **minor edit**, leaving every downstream line untouched even though the plot just reversed. Replaced with a word-boundary `STRUCTURAL_TRIGGER_RE` that includes common negation contractions, and a narrower `LOCATION_TRIGGER_RE` (used only for demo-mode branch selection) that keeps the old dock/leaving-specific behavior for that narrower purpose.

3. **Opening a saved document no longer indexes into the wrong pool.** `pool` (the array `pointer` indexes into) was never part of the save format — reopening a document restored `pointer` but left `pool` as whatever was in memory, which could be leftover demo content or an unrelated document's data. `pool` and `chatHistory` are now saved (format bumped to `version: 3`) and restored on open; files saved by older versions fall back to the demo array matching the restored branch rather than leaving stale content in place.

4. **Chat history is no longer silently wiped on every open.** `chatHistory` is now part of `documentPayload()` and is restored — and the visible chat log is rebuilt from it via a new `rebuildChatLogFromHistory()` — when a document is opened.

### Real bugs, now fixed

5. **Spiral spine canvas redraws on window resize.** Added a debounced `resize` listener that re-runs `drawSpiralSpine()`. Previously the canvas's internal pixel buffer was only ever sized once at load, so resizing the window stretched/distorted the graphic relative to its responsive container.

6. **`llmTestBtn` now guards against an unknown adapter**, matching the same check `callLLM()` already did, instead of throwing a raw "Cannot read properties of undefined" if it were ever reachable.

7. **Skip is no longer a no-op during active playback.** Previously, clicking Skip while a line was actively being read aloud did nothing (it only worked when fully stopped or during the reaction pause). It now also interrupts active speech and immediately advances, matching what "Skip ahead" implies.

8. **`downloadDocument()`'s anchor element is now attached to the DOM** before `.click()` and removed after — the previous detached-anchor pattern is a known gotcha in older Safari/Firefox.

9. **`selectedLineIndex` is a real feature now, not dead state.** Locked lines in the manuscript tail are clickable (click to select/deselect, with a visible highlight). "Unlock selected / line…" now edits the selected line **inline**, in place — no more two chained `prompt()` dialogs (the "which line number" prompt, then the "edit this text" prompt). This also fixes the "Unlock isn't really inline" complaint from the very first review round; it's now the same inline-textarea pattern the buffer/reading lines already used. "Lock all finalized text" now has real meaning (clears the current selection/edit state) instead of nulling a variable nothing read.

10. **`documentDirty` now actually protects unsaved work.** Added a `beforeunload` guard that warns before closing/navigating away with unsaved changes — the feature this piece of state existed for but was never built.

11. **Deduplicated the file-picker logic**, which was copy-pasted verbatim (with inconsistent formatting) in `openDocumentForEditing()` and `openReferenceDocument()`, into one shared `pickOpenFile()` helper.

12. **`saveDocument()`/`saveAsDocument()` no longer silently swallow write errors.** A failed write (permission revoked, disk full, etc.) now reports through `reportError()` before falling back, instead of silently changing what "Save" does with no explanation.

13. **`sendChat()` has a real re-entrancy guard.** Previously, disabling the Send button did nothing to stop the Enter-key listener from firing a second concurrent call — two in-flight requests could resolve out of order and show the wrong reply first. Added a `chatSending` flag checked at the top of the function itself (matching the pattern `generateMoreIntoPool()` already used correctly via its `generating` flag).

14. **Voice recognition errors are no longer silent.** `recognizer.onerror` previously only turned off the pulsing red mic indicator with zero explanation. It now reports real failures (permission denied, no microphone, network error, service unavailable) through the same error channel as everything else, while staying quiet for the benign `no-speech` timeout case.

15. **Removed dead code:** the `typeof renderRefPane==='function'` guard in `render()` (the function is hoisted and always defined — this was the one inconsistent call site out of four), the unused `.voice-btn` CSS rule (the mic button was always styled via `#chatMicBtn`), and an unused `const llmModal` left over from an intermediate edit.

16. **Alerts replaced with the app's existing non-blocking channels where the interaction didn't need blocking input:** "no lines to unlock yet," "chapter changed," and file-open failures now use a new `toast()` helper (built on the existing flash-message plumbing) or `reportError()` (into the chat log) instead of native `alert()`. The one remaining `alert()` — the "voice input isn't supported in this browser" notice — was left as-is; it's a one-time capability wall, not a repeat-annoyance case.

### New fixes found during this pass (not in the original lists)

17. **LLM settings modal now caches its form inputs once**, matching the DOM-caching convention used everywhere else in the file (`llmFormInputs` object), instead of re-running `document.getElementById()` seven times per call in `populateLLMForm()`, `readLLMFormIntoConfig()`, and the test-connection handler.

18. **Escape key now closes the LLM settings modal and the hamburger menu**, and focus moves sensibly (into the modal's first field on open, back to the triggering button on close) — there was previously no keyboard escape hatch for either, and no focus management at all.

---

## Deliberately not touched (flagged, not silently ignored)

These are real, and were flagged as such in earlier review rounds, but are architecture/roadmap items rather than bugs — fixing them properly means a design decision or a larger change, not a line-level fix:

- **Single 1,500+ line file with no state/render/API separation.** Still the root cause of the *class* of bug this pass fixed instances of. A real fix is a refactor (state module + render module + API module), not a patch.
- **No streaming from the LLM.** Generation and chat replies still land all at once.
- **No undo/redo, no find & replace, no text formatting, no export beyond `.2i` JSON.** These are real word-processor features, not bugs — out of scope for a bug-fix pass.
- **No true collaboration** (multi-user presence, conflict resolution, comments from a second human, revision history/diff view). This remains a single-user, single-browser, local-file tool with an AI writing partner.
- **`showSaveFilePicker`/`showOpenFilePicker` are Chromium-only**; Firefox/Safari fall back to plain downloads, not in-place saves. This is disclosed behavior, not hidden, but a cross-browser-safe save path (e.g. IndexedDB-backed autosave) would be a deliberate design choice, not a quick fix.
- **`SpeechRecognition` (dictation) has no fallback on Firefox** — same reasoning as above.
- **API keys are stored in `localStorage` in plaintext.** Reasonable for a local single-user tool and disclosed in the settings modal's own copy, but worth a deliberate decision if this ever becomes multi-user.
- **Duplicated inline SVG data-URI button textures.** Cosmetic/file-size only, unrelated to correctness.
- **`id="writeRow"` is still an unreferenced HTML id.** Harmless (it's not fought over by anything), left alone rather than risk an unnecessary edit near the write-row markup.
- **`bufferedProtected` / `.pinned` / "pin" — three names for one concept.** Still not unified; a wide rename felt riskier than the value it'd add in this pass.
- **No full focus trap in the LLM modal** (tabbing can still leave the modal). Escape-to-close and initial/return focus were added; a complete trap is a larger a11y pass.

---

## Files in this handoff
- `2i_writers_room_v9.html` — the fixed file. Open directly in a browser (Chrome/Edge recommended for voice input and in-place Save).
- This file.

---

## Suggested smoke test before shipping

1. **No LLM configured:** confirm the tool still works end-to-end as a plain word processor (Add to draft, Play/Generate falls back to demo `SCENE` lines, structural edits reroute to `docks`/`generic` demo branches as before).
2. **With an LLM configured:** generate a few real lines, then edit one to include a trigger word ("actually," a negation like "never," etc.) — confirm the *next* lines are new LLM output continuing from the edit, not canned demo text about docks.
3. **Save → reload → Open** the same file: confirm buffer, committed text, branch, chat history, and playback pointer all come back correctly (try this after generating enough lines that `pointer` is mid-pool, not just at 0).
4. **Click a locked line** in the manuscript-tail area, then **Unlock selected / line…** from the menu — confirm it edits inline with no `prompt()` dialogs, and Save updates the manuscript.
5. **Resize the browser window** — confirm the spiral spine graphic stays crisp instead of stretching.
6. **Skip** while a line is actively being read aloud — confirm it interrupts and advances instead of doing nothing.
7. **Escape key** — confirm it closes the LLM settings modal and the hamburger menu.
8. Try to **close the tab with unsaved changes** — confirm the browser's native "leave site?" prompt appears.
