# 2i unification: current integration ledger (2026-11-20)

Branch: `integration/2i-unified-2026-11-20`, based on pre-dec `main` at `538a40fb2d6efb540347036e3c36605729b57ebf`.

## Decision: preserve the newer working design

This branch keeps the single-page notebook, left/right drawer tabs, adjustable margins, handwriting notebook mode, and the **interactive** touch-and-mouse typewriter. No 2i production UI or persistence implementation was overwritten by an older branch.

The current hosted routes in `main.py` serve the same `2i/writers-room-v22.html` at `/2i` and `/writers-room`, and the actual `/typewriter-console` route serves its clickable keys. The editor loads `2i-assets/typewriter-input.js` before `2i-assets/studio-desk.js`.

## Reconcile the branches by behavior, not branch names

- `2i-beta-polish`: its lock/undo/Replace All improvements are present in newer code through `NarrativeCore.remapProtected`, metadata-aware `restoreUndoPoint`, and the locked-line-safe Replace All path. The older three-column layout is *not* the design to install over the single-page notebook. The new browser acceptance cases in this branch preserve two of the behavioral requirements: protected lines resist edits, and locks travel when lines above are added/removed.
- `codex/2i-typewriter-visual-2026-11-17`: do not merge the static-image typewriter over the interactive iframe. Its file-URL artwork approach is not a tested replacement for functional offline keyboard interaction.
- `console-touch-typewriter-keys`: current main already has the interactive typewriter frame and map. The synthetic browser suite had been calling obsolete IDs and a different adapter; it now uses `#twoiTypewriterConsole`, `typewriter-input.js`, and the current ready/key message protocol.
- `tests/test_2i_claude_functionality_browser.py`: manuscript controls live inside the hidden Tools drawer in the current Write look. Tests now open that visible tab, require the button to become visible, click it, and close the drawer before checking results.

## Two changes actually made

1. **Modernized current 2i interaction acceptance:** corrected the browser tests to use the real Tools drawer; added behavioral tests for protected Write-mode lines in the current single-page editor. The tests keep their assertions about unchanged text, locks and Replace All.
2. **Reconnected real typewriter test contract:** removed retired `#twoiLiveKeysFrame` / `#twoiTouchableTypewriter` assumptions, switched to the current embedded iframe and input adapter, and completed the minimal synthetic host's render and manuscript state. Tests still cover physical-key events reaching the actual manuscript, Collab draft routing, exclusion of other-window messages and native undo.

## Evidence and limits

- **READ / STATIC VERIFIED:** inspected actual GitHub `main` code, routes, branch comparisons and current tests, and confirmed matching identifiers/asset loading order after the commits.
- **WROTE, NOT RUN:** three browser-test files were edited. The Chromium tests have **not** executed in this session because the repo could not be cloned from the local execution environment (GitHub DNS unreachable). Do not count new tests as passing.
- **UNKNOWN:** physical touch/keyboard operation on Windows and phones; full in-browser save-and-reload after the changes; offline typewriter interaction when the HTML is opened straight from `file://`; broad 2i test suite health. A stale branch test is not automatically a production defect; equally, a code-path inspection is not an acceptance pass.

## Remaining integration gates

A. Run `pytest -q tests/test_2i_claude_functionality_browser.py tests/test_2i_typewriter_event_browser.py tests/test_2i_typewriter_embedded_browser.py tests/test_2i_single_page.py` in a prepared local environment with Chromium installed. Compare to unmodified main, repair genuine failures, and retain both logs.

B. Run the hosted save/reload and recovery suite against the real Reach host; test interrupted save, concurrent edits and a fresh restart using disposable manuscripts, not the owner's work.

C. Verify `file://` typewriter interaction explicitly. The live iframe targets a server route; an offline self-contained typewriter must be proved separately before calling it supported.

D. Re-run accessibility, phone/tablet visual acceptance, DOCX/exports, and 2i's full test suite. Resolve only defects demonstrated by observable behavior.

**No main merge or release claim.** This is a contained reconciliation and acceptance advance, not the declaration that 2i is feature-complete.

## Non-Chromium execution evidence (same-day follow-up)

The local execution environment cannot resolve `github.com` for a clone, so the complete repository cannot be installed or exercised here. However, the connected GitHub API supplied **the actual current production JavaScript**; it was executed in a separate V8 JavaScript isolate using deterministic fake browser/HTTP boundaries. This is narrower than Node, Chromium, an actual server, or real IndexedDB.

**Final V8 source-execution checks: 44 passed, 0 failed.** Counts are individual assertions/scenarios, not a claim about the project's entire test suite:

| Boundary exercised | Passed | Tested |
| --- | ---: | --- |
| Actual `typewriter-input.js` and `narrative-core.js` | 16 | Caret/selection/Unicode/backspace/blocked input; protected-line remapping; bounded draft preservation; prior-scene context |
| Actual `saveDocument` extracted from `reach.js` | 9 | Hosted save; late edits and revision 2; shared in-flight save; 409/503 failures; missing browser recovery; no-network; Foresight-file guard; wrong-document race |
| Actual `studio-desk.js` | 13 | View switching, iframe handshake, Write/Collab routing, busy and invalid-state restrictions, spoofed-window/origin rejection, file-session guard |
| **Both actual** `studio-desk.js` and `typewriter-input.js` together | 6 | End-to-end fake-DOM relay for insertion, emoji backspace, Collab draft, protected beforeinput veto, foreign-origin rejection and busy-state rejection |

Harness-only false starts: initial V8 simulated browser lacked `URLSearchParams`, and an early parameter-based fake did not allow mutable state; those were repaired and rerun. An initial combined-adapter fake lacked `addEventListener`, then was repaired. The **final** results above exclude those harness setup failures. These results do not demonstrate that browsers render the UI or that disk persistence survives a restart.

**Additional inspection (non-execution):** all 17 external script/style references in `2i/writers-room-v22.html` resolve to tracked repository files through its hosted routes, with zero missing or duplicate links. The 48-slot typewriter hotspot manifest has zero missing required keys, duplicate IDs, overlapping keyboxes, out-of-range coordinates, or unwanted studio action IDs. Its referenced image exists in the repository. No image rendering was claimed.

**New committed regression suite:** `tests/test_2i_typewriter_real_adapter_node.js` directly loads the real production input adapter and studio desk into a fake DOM rather than substituting a fake editor adapter. Six scenarios are encoded and its JavaScript grammar parsed, but `node --test` on this newly created file remains **NOT RUN** until a local checkout is available. The six equivalent actual-source scenarios did run in the isolated V8 test above.

All production 2i source, manuscript storage format, and existing user content remain untouched by this integration branch. No CI workflows were invoked. The PR remains draft.
