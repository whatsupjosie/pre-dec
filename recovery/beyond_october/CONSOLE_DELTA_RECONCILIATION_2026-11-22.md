# Console-touch source reconciliation against staged studio code
Verified 2026-11-22 by checking full Git blob SHAs, not names or snippets.

Staged runtime basis: `integration/main-debug-land-clean-2026-11-20`, commit `b282b2ba33f7226d5933ac28cf4e88ca2e041c91`.
Beyond-October donor: `console-touch-typewriter-keys`, commit `3ee394a7ca66edd5e152eb0eca4de1709333bd7c`.
Donor copies are under `recovery/beyond_october/console-touch-typewriter-keys/`, preserving the *entire* contents of each of the 16 changed files.

## Exact contents already in the staged runtime (11/16)

These 11 paths have the **same Git blob SHA** in the original donor and the staged runtime at the original path. Do **not** overwrite or reimplement them on the assumption that they are missing.

- `handoffs/CONSOLE_TOUCH_AND_TYPEWRITER_2026-11-17.md` (`16fc714d`)
- `static/audio_console_hotspot_manifest.json` (`b45a3931`)
- `static/console_hotspot_renderer.css` (`1e59fdad`)
- `static/console_hotspot_renderer.js` (`e11ec48a`)
- `static/studio_console_hotspots.js` (`c36ae7c7`)
- `static/typewriter_console_hotspot_manifest.json` (`af01ab4f`)
- `static/typewriter_keys.webp` (`5926692e`)
- `tests/test_console_hotspot_manifests.py` (`51ca3a02`)
- `tests/test_console_touch_browser.py` (`5251e21b`)
- `tests/test_typewriter_console_manifest.py` (`04450231`)
- `tools/build_typewriter_manifest.py` (`1ea07dd0`)

## Differing source files (5/16), not yet blindly copied onto runtime

| Path | Staged runtime blob | Console donor blob | Reconciliation |
|---|---|---|---|
| `STATUS.md` | `eb1f5f86` | `a97dbcab` | Historical status text; don't overwrite current status |
| `main.py` | `6ed12a02` | `760b0611` | Larger newer runtime; `/typewriter-console` and `/audio-console` routes exist in both; compare other behavior before applying anything |
| `static/typewriter_console.html` | `ef77c608` | `f9482669` | Separate typewriter design line; preserve both, outside immediate Control Room scope |
| `static/typewriter_console_demo.js` | `a49bd269` | `e5491778` | Separate typewriter design line; preserve both |
| `static/typewriter_sound.js` | `f03339e1` | `6f0e5787` | Separate typewriter design line; preserve both |

## Production-related branch coverage

- Beyond-October `codex/main-debug-20261119` commit `d3b9db81fc4a35d05db82de1d0de24dacf17e973` is an ancestor of the staging base (verified compare: 0 behind).
- Beyond-October `integration/main-debug-union-trial-2026-11-20` is also an ancestor of the staging base (verified: 0 behind).
- Beyond-October `gpt/control-ui-wiring-2026-11-08`, `gpt/clacker-timecode-verification`, `gpt/guest-recording-triage-2026-11-13`, `gpt/participant-clock-prototype-2026-11-13`, `gpt/live-studio-setup-2026-11-09`, `gpt/recording-endurance-2026-11-13`, and `gpt/speech-playback-lifecycle` are ancestors of the old convergence commit on current main. No copied fragments needed for ancestry retention.

## Do not confuse recovery with running acceptance

The staging branch carries **29 commits ahead of pre-dec/main**, with **44 active-path file changes** from the reconciled main-debug line, plus 16 exact donor snapshots and one recovery manifest (61 files in the first recovery comparison). It does not prove that photographic REC, real 2.5D capture, guest audio over 30 minutes, or portable three-mode recording work. The unpublished November 22 recording-modes bundle remains a separate later import.

Next engineering action: reconcile this staging branch with newer `codex/studio-integration`, `claude/live-sources-2026-11-22`, `codex/restore-mini-console` and the uploaded recording-modes bundle, then run real end-to-end acceptance tests before touching main.
