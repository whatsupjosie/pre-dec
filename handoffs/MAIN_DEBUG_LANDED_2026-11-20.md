# Landing codex/main-debug-20261119 onto main's line, except two files

Branch: `integration/main-debug-land-clean-2026-11-20`
Tip: `b2c2103abc5862c9e834c31d99e82b9e2a3378e6`
Written 2026-11-20 by Claude (Opus 5) in a Linux sandbox. No GitHub Actions and
no CI were used. `main` was not pushed to. Nothing was deleted.

Read this with `MERGE_REPORT_2026-11-20.md`, which covers the eleven merges
already on `main`. This note covers one thing only: the twelfth branch, the one
that report left undecided.

## What this branch is, exactly

| | |
|---|---|
| Base | `main` at `538a40fb2d6efb540347036e3c36605729b57ebf` |
| Merged | `integration/main-debug-union-trial-2026-11-20` at `eacde8753402447e3454b07622fb2fcec8dd17e7` |
| Which makes an ancestor | `codex/main-debug-20261119` at `d3b9db81fc4a35d05db82de1d0de24dacf17e973` (verified with `git merge-base --is-ancestor`) |
| Size of the change | 43 files changed, 1289 insertions, 299 deletions |
| Merge conflicts | none |

The union resolutions were not redone. They were made on the trial branch and
are carried in by merging it, so the provenance of both lines survives.

What lands: camera filename reservation, FFmpeg overwrite refusal (`-n` in place
of `-y`), per-source capture failure persistence, real pause and resume of a
live capture with rollback, timeline transport repair, PANIC encoder handling,
and five new test files plus `tools/acceptance/studio_long_take.py`.

## What is held back, and why

`static/production25d_storage.js` and `static/production25d_app.js` are held at
`main`'s versions, proven by blob hash rather than by reading:

| File | `main` blob | this branch | |
|------|-------------|-------------|---|
| `static/production25d_storage.js` | `0cc59be1316db97bf67c4c5dc2eb284060fe8689` | `0cc59be1316db97bf67c4c5dc2eb284060fe8689` | identical |
| `static/production25d_app.js` | `b6f9b50722a1f1343049589508646b03a86d6215` | `b6f9b50722a1f1343049589508646b03a86d6215` | identical |

Those two files hold two incompatible local-recording architectures. Choosing
between them is Josie's decision, it is still open, and nothing here decides it.
Holding `main`'s side keeps her current architecture: IndexedDB version 3,
lease-based `captures` and `captureChunks`, `PubCast25DSourceRecordings`,
`recordingStarting`, a cancellable start token.

## Verified, not assumed

**Nothing landed references the other architecture.** Every one of the 41
changed code files was searched for the field names that exist only on
`codex/main-debug`'s side - `journals`, `panicActive`, `startingRecording`,
`captureWriter`, `recordingStarting` as theirs spells it, `chunked`. Zero hits.

**`main`'s own production25d code already provides what the two new tests
expect.** `stopRecording({immediate:true})` is at `static/production25d_app.js`
line 499 and the `immediate` branch at line 500, `incomplete` appears at nine
places, `recordings` at seven. The new tests are written against her API, not
against theirs.

**The three runtime dependency claims in the merge report are true on this
branch**, each checked by reading the line:

- `application.state.session_capture` is assigned at `main.py` line 1166 and
  awaited at lines 917 and 1930, so taking our side alone would have crashed on
  shutdown.
- `confirmed_stop_session_id` is imported at `modules/production_routes.py`
  line 49, used at line 404, defined at `modules/studio_console_actions.py`
  line 69.
- In `modules/recording.py` all five unioned names are in use: `ingest` 32
  times, `capture_errors` four, `local_metadata` three, `datetime` twice,
  `replace` six.

**Everything else `main` carries survived the merge.** `BRANCH_PROVENANCE.md`
(117 lines), `LARGE_FILE_INVENTORY_2026-11-20.md` (87), and
`MERGE_REPORT_2026-11-20.md` (346) are all present, and the hosted-save harness
fix (`reachFileMode: false`, `tests/test_2i_hosted_save_races_node.js` line 31)
is still there. Every changed `.py` file compiles.

## Test results

Run locally. Every number below was produced in this sandbox by the command
shown, on both trees, so before and after are comparable to each other. They are
*not* comparable to the counts in `MERGE_REPORT_2026-11-20.md`, which was run in
a better-equipped environment - see "What this sandbox could not do".

### Node

Command, identical on both: `node --test tests/*_node.js tests/*.cjs`

| Tree | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| `main` `538a40f` | 278 | 261 | 17 | 0 |
| This branch | 278 | 261 | 17 | 0 |

The 17 failing test *names* were compared, not just the counts, and the two sets
are identical. This reproduces the merge report's Node numbers exactly.

### Python

Command, identical on both: `python -m pytest -q -p no:randomly`

| Tree | Failed | Passed | Skipped | Errors | xfailed | Duration |
|------|--------|--------|---------|--------|---------|----------|
| `main` `538a40f` | 2 | 2487 | 243 | 94 | 1 | 10 min 40 s |
| This branch | 1 | 2503 | 327 | 14 | 1 | 10 min 42 s |

Read the three moves honestly:

- **Passed, 2487 to 2503.** Sixteen more real passes. The merge adds test files.
- **Errors, 94 down to 14.** Not a repair of product code. All 94 errors are
  browser tests that cannot find a browser; the merge brings a `try/except` that
  turns a hard error into a skip with a stated reason
  (`tests/test_foresight_file_workspace.py` line 60 area). Eighty errors became
  eighty skips, which is why skipped rises 243 to 327. Better reporting, same
  coverage. The 14 that remain are `tests/primp_chromium/test_mirror.py`, and
  their cause is now known - see below.
- **Failed, 2 down to 1.** Same story, not a fix:
  `test_data_checkpoint_host_recovery.py::test_restore_real_host_sign_in_open_work_and_play_recording`
  failed outright on `main` for want of a browser and now skips with a reason.
  The remaining failure,
  `tests/test_alex_routes_bridge.py::test_alex_routes_message_and_recent_memory`,
  is inherited and untouched: it passes alone and fails in a group run from
  cross-test state. The merge report found the same thing.

**No regressions.** No test that passed on `main` fails on this branch.

### The recording surface, driven in a real browser

The suite above skips most browser work, so the file this merge is really about
was run directly, with a browser bridged in (see below):

Command, identical on both: `python -m pytest -p no:randomly -q tests/test_production25d_browser.py`

| Tree | Result |
|------|--------|
| `main` `538a40f` | 17 passed, 0 failed, 3 min 12 s |
| This branch | 18 passed, 1 failed, 4 min 22 s |

All 17 pre-existing recording tests still pass with her architecture in place
and the landed server work underneath. Of the two tests the branch adds, one
passes - `test_panic_interrupts_an_ordinary_stop_without_polling`, which is the
PANIC behaviour. The other is red on arrival, and the cause is specific:

`test_crashed_studio_page_reopens_committed_media_in_another_tab` does
`page.locator("#sessionList button").filter(has_text="INCOMPLETE").click()`. On
her architecture that locator matches two buttons, not one: the take row
(`production25d_app.js` line 580) and a per-source row for the clacker sync
reference (line 586, `SYNC: Clacker reference · INCOMPLETE · 6700 bytes`).
Playwright refuses an ambiguous click, so the test fails before asserting
anything. Per-source recording rows are a feature her side has and theirs does
not, so this is a test written for a tree with fewer rows, not a defect in the
product.

The fix is one line in the test - narrow the locator to the take row, for
instance adding `has_text="Take"` alongside the INCOMPLETE filter, or selecting
the take button by its own text. **It has not been applied.** Changing a test's
assertions is a decision for Josie, and the merge report left the same class of
thing alone for the same reason.

### The Rust renderer

`cargo build --release --bin ws_renderer` in `rust_crate/`: **succeeds**, one
minute 18 seconds, three warnings, all `dead_code`. This is the first time that
source has been compiled here rather than taken on trust.

The committed binary is a separate question. `bin/ws_renderer` is 1,813,256
bytes on this branch (`e3c6e65c29953fce7604d72b11d555d00243a106`), replacing
`main`'s 9,687,192 bytes (`136c3cc2f109f7a55b208400a5be5682afaecf7d`). That
swap is what `LARGE_FILE_INVENTORY_2026-11-20.md` lines 70 to 73 predicted. The
release build here produced 2,133,336 bytes, the same order as the smaller one
and nothing like the larger, which is consistent with `main` carrying a debug
build and this branch carrying a release build. It is *not* proof: a different
rustc version and stripping both move the size, and the hashes do not match
(built `7bbe894ab002a4a100fa193b37b8776b0688adf1a6ec620519f2269b3a49a3d5`,
committed `82148b059bc270098b12af3cc1a09734ec97fd62ed11fecfd2b52074801c360a`).
A committed binary cannot be verified by reading. The honest move is to rebuild
it on the laptop from `rust_crate` and keep the source as the authority.

## What this sandbox could not do

- **The pinned browser bundle was absent.** `requirements-dev.txt` pins
  `playwright==1.56.0`, which expects chromium revision 1194; this machine has
  revision 1243 and Chrome for Testing 153 at `/usr/bin/google-chrome`, and
  `cdn.playwright.dev` is blocked by the egress proxy. For the two
  `test_production25d_browser.py` runs the installed binaries were linked into
  the path the client expects. So those runs used chromium 157 headless shell
  and chrome 153 under a 1.56 client, not the pinned combination. The 35 passes
  and the one failure are real, but the browser is not the pinned one.
- **`pytest-playwright` is not declared and not installed.** That is the whole
  cause of the 14 `primp_chromium` errors the merge report recorded without a
  diagnosis: `tests/primp_chromium/conftest.py` line 77 asks for the `page`
  fixture, which only that plugin provides, so every test in the file errors at
  setup. `requirements-dev.txt` declares `playwright` but not the plugin, so
  this happens on any clean checkout. Adding `pytest-playwright` to
  `requirements-dev.txt` is a one-line change and is **not** part of this
  branch. It belongs with the other undeclared test dependencies the merge
  report listed, `zstandard` and `msgpack`.
- **Windows was not run at all.** This is Linux only.

## One behaviour change worth knowing about before Windows

`modules/capture.py` now pauses a live capture for real. `CaptureProcess.set_paused`
sends SIGSTOP and SIGCONT, and where those signals do not exist it raises
`NotImplementedError("This platform cannot suspend an active FFmpeg capture")`.
Windows has no SIGSTOP. The code this replaces was documented as "Send SIGSTOP
to all processes (Unix) or no-op on Windows", so pausing on Windows used to
silently do nothing and now raises instead. The route at
`modules/production_routes.py` line 543 calls it.

That is the more honest of the two behaviours - a pause that does nothing is
worse than a pause that says it cannot - but on the laptop it will surface as an
error where it used to surface as silence. Flagging it rather than changing it:
deciding what a Windows pause should do is a design call, not a merge.

## Still open after this branch

1. **The local-recording architecture.** Untouched and still Josie's to decide.
   If theirs ever wins, the two files are on `codex/main-debug-20261119` at
   `d3b9db81f` and nothing here has overwritten them.
2. **The one red new test**, diagnosed above, one line, not applied.
3. **`pytest-playwright`, `zstandard`, `msgpack`** undeclared in
   `requirements-dev.txt`. Together they are the difference between 94 tests
   erroring or skipping and 94 tests running.
4. **`tests/test_alex_routes_bridge.py::test_alex_routes_message_and_recent_memory`**,
   inherited cross-test state.
5. **The committed `bin/ws_renderer`**, which should be rebuilt on the laptop
   rather than trusted from the repository.
6. **`2i-beta-polish` and `codex/2i-typewriter-visual-2026-11-17`**, decisions
   two and three in the merge report. Both are 2i look decisions and neither is
   touched here.

## Next step

Review this branch and, if the holding of the two production25d files is right,
merge it into `main`. It is a merge, so `main` moves forward without rewriting
anything already there.
