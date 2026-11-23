# Control Room / camera / recording / audio recovery staging
Date: 2026-11-22
Repository: whatsupjosie/pre-dec
Staging branch: recovery/control-room-beyond-october-2026-11-22

## Exact provenance and status

- Current published main when staged: 538a40fb2d6efb540347036e3c36605729b57ebf.
- This staging branch starts FROM the reconciled integration/main-debug-land-clean-2026-11-20 at b282b2ba33f7226d5933ac28cf4e88ca2e041c91. This is 28 commits ahead of the published main branch and carries the original Beyond-October codex/main-debug-20261119 history (d3b9db81fc4a35d05db82de1d0de24dacf17e973) plus its union/reconciliation commits. Those full revisions remain at their original paths, without transcription or truncation.
- The other Beyond-October studio-relevant unmerged development line is console-touch-typewriter-keys, at 3ee394a7ca66edd5e152eb0eca4de1709333bd7c. Its changed files are preserved byte-for-byte below, at their original blob SHA, under recovery/beyond_october/console-touch-typewriter-keys/.
- DO NOT claim console-touch changes have been applied to runtime paths. The donor line diverges from the main-debug branch. Its FULL files (including large main.py and the image asset) are copied as immutable Git blobs, not a handful of selected source lines. This staging copy is for conflict-aware integration.
- pre-dec already holds the original console-touch-typewriter-keys branch at the same SHA. This snapshot adds a complete recovery copy onto one staging branch for inspection and selective integration.
- Both the old control-ui-wiring and clacker-timecode and recording-endurance source lines are ancestors of the 538a40fb convergence and therefore already carried in the staging ancestry. Recheck runtime route parity before declaring them functional.
- Related newer pre-dec branches NOT included here: codex/studio-integration at 0d4d042c8aa243265f3b236b3098a94dbd36959e, claude/live-sources-2026-11-22, codex/restore-mini-console. These are separate follow-on reconciliation inputs, and should not be accidentally overwritten by these older donors.
- The uploaded, unpublished claude/recording-modes-2026-11-22 Git bundle is a separate later source and has NOT been ported by this commit. The existing separate timeline-fix patch should be checked when that bundle is imported.

## Integrity manifest (full Git blob SHA of source file)

| Source path on console-touch-typewriter-keys | Source blob SHA | Bytes | Staging snapshot path |
|---|---|---:|---|
| `STATUS.md` | `a97dbcabcccdfc9cb779e1aed36edad359437a9c` | 11905 | `recovery/beyond_october/console-touch-typewriter-keys/STATUS.md` |
| `handoffs/CONSOLE_TOUCH_AND_TYPEWRITER_2026-11-17.md` | `16fc714dc9bfc39b4633eb8bcabf1cbf861be54b` | 10827 | `recovery/beyond_october/console-touch-typewriter-keys/handoffs/CONSOLE_TOUCH_AND_TYPEWRITER_2026-11-17.md` |
| `main.py` | `760b0611a911532f61b8e25ff7bd550c9fd08ca4` | 217052 | `recovery/beyond_october/console-touch-typewriter-keys/main.py` |
| `static/audio_console_hotspot_manifest.json` | `b45a39317f8134ec5e4e6529dd02b4ec775b9089` | 5156 | `recovery/beyond_october/console-touch-typewriter-keys/static/audio_console_hotspot_manifest.json` |
| `static/console_hotspot_renderer.css` | `1e59fdad4c141852685398eb3f13702acb096352` | 6547 | `recovery/beyond_october/console-touch-typewriter-keys/static/console_hotspot_renderer.css` |
| `static/console_hotspot_renderer.js` | `e11ec48a90a11d07db9ae1d9155b6e350e3da56a` | 23609 | `recovery/beyond_october/console-touch-typewriter-keys/static/console_hotspot_renderer.js` |
| `static/studio_console_hotspots.js` | `c36ae7c7c95ab8dd44c49b335169739a63b1487c` | 12007 | `recovery/beyond_october/console-touch-typewriter-keys/static/studio_console_hotspots.js` |
| `static/typewriter_console.html` | `f94826695741545ebc83280e814ee6a11f1ceeea` | 1213 | `recovery/beyond_october/console-touch-typewriter-keys/static/typewriter_console.html` |
| `static/typewriter_console_demo.js` | `e54917780c6c8594b053aa8de6a24d2cbca4be47` | 3064 | `recovery/beyond_october/console-touch-typewriter-keys/static/typewriter_console_demo.js` |
| `static/typewriter_console_hotspot_manifest.json` | `af01ab4f61a161b4984836b429d906f493620929` | 7915 | `recovery/beyond_october/console-touch-typewriter-keys/static/typewriter_console_hotspot_manifest.json` |
| `static/typewriter_keys.webp` | `5926692e8aba61c5c8900aa7e5719d963f9e5bab` | 205296 | `recovery/beyond_october/console-touch-typewriter-keys/static/typewriter_keys.webp` |
| `static/typewriter_sound.js` | `6f0e578770dfdebca628756c3587189c7cc55beb` | 7815 | `recovery/beyond_october/console-touch-typewriter-keys/static/typewriter_sound.js` |
| `tests/test_console_hotspot_manifests.py` | `51ca3a02494f168cad2dc81dc081cd1554212b04` | 3934 | `recovery/beyond_october/console-touch-typewriter-keys/tests/test_console_hotspot_manifests.py` |
| `tests/test_console_touch_browser.py` | `5251e21bae7ed7cac6dc52016324678d62f52aca` | 33055 | `recovery/beyond_october/console-touch-typewriter-keys/tests/test_console_touch_browser.py` |
| `tests/test_typewriter_console_manifest.py` | `044502313591e040f00d6ab5d4a4c867d91288b7` | 2117 | `recovery/beyond_october/console-touch-typewriter-keys/tests/test_typewriter_console_manifest.py` |
| `tools/build_typewriter_manifest.py` | `1ea07dd069990ce8a77f04126fb94f2b0749b944` | 4775 | `recovery/beyond_october/console-touch-typewriter-keys/tools/build_typewriter_manifest.py` |

## Next steps for integration, not yet completed

1. Compare each donor snapshot against the live path at the staging commit and latest pre-dec studio branches. Reuse present changes; port only missing behavior with tests. Avoid wholesale replacement of newer main.py or console JS.
2. Reconcile touch hotspot maps, dragging and the audio-console hotspot manifest; preserve click permissions, camera Program/Preview truth, accurate recording status, guest audio and source privacy.
3. Reconcile and test actual photographic REC route, full-rate source capture, 2.5D Program, three recording modes, long-run audio, and portable takes.
4. Only after real UI/media acceptance, merge the integration branch into main. This staging operation has NOT performed tests or proven production readiness.

## Scope boundary

This is a source-recovery checkpoint, NOT a completion certificate, not a staging artifact that runs all features automatically, and not a substitute for full camera/audio/recording integration. No application path was overwritten while adding the donor snapshots.
