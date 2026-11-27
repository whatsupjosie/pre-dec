# Parts index: every file in every zip and every branch, identified

Built 2026-11-26 by Claude (branch `finish/control-room-engine`, whatsupjosie/pre-dec). Look things up here first;
search the files only for what this log says it does not cover.

## What is in this folder

| File | One line per | Use it to |
|---|---|---|
| `zip_contents_index.tsv` | file inside any zip, at any depth (16,059 rows) | find a file by name, see where it lives, what it is, whether we already have it |
| `branch_files_index.tsv` | distinct file in any branch tip of any repo (14,429 rows, 196 branch tips) | find which repo/branch/path holds a file |
| `by_source/*.md` | source zip (108 pages) | read one zip's contents as a table |
| `drive_folders_index.tsv` | file in a Drive folder of extracted copies (1,426 rows) | find a Drive copy by name; see whether it is new |
| `stats.json` | the counts below | |

TSV files open in Excel/LibreOffice or any text editor (tab-separated). In PowerShell 5:
`Import-Csv .\zip_contents_index.tsv -Delimiter "`t" | Where-Object name -like "*renderer*"`

## Columns of `zip_contents_index.tsv`

- **name**: the file's name.
- **origin**: `project file`, or `third-party or build output (under X/)` for anything under .venv, site-packages,
  node_modules, vendor, target, `__pycache__` or .git.
- **location**: where the outermost zip is, then the path inside it. A zip inside a zip is shown as
  `outer zip >> inner.zip > path`. Drive locations give the Drive file id. GitHub locations give repo, branch and
  path; a zip committed to many branches lists three, plus how many more.
- **zip_nesting**: 1 = inside the outer zip, 2 = inside a zip inside it, and so on.
- **folder_depth**: folders above the file inside its zip.
- **size**: in bytes.
- **kind**: from the file's first bytes and extension.
- **what_it_is**: EXTRACTED from the file's own content. For Python that's the docstring, its functions and classes,
  and its routes; for JS its functions and the API paths it calls; for HTML its title, scripts and API calls; for
  Markdown its headings; for JSON its keys; for Rust its doc comment and items. Not a human judgement.
- **status**, one of:
  - `IN CURRENT BUILD`: identical content, or identical apart from line endings, somewhere in
    `finish/control-room-engine` (path given);
  - `IN CURRENT BUILD ONLY AS A PARKED COPY under recovery/`: in the tree, but only as a copy under `recovery/`
    that nothing live imports. Its potential reads "check whether it should be wired in". In
    `branch_files_index.tsv` the same case reads "only as a parked copy, not live";
  - `IN A GIT BRANCH, NOT IN THE CURRENT BUILD`: an example branch:path is given;
  - `NOT IN ANY REPO BRANCH`: exists only inside the zip.

  When a file of the same name exists in the current build, it is compared with the one whose path matches the most
  folders, counting lines only here versus lines only in current. For generic names (`__init__.py`, `main.py`,
  `README.md` and the like), no comparison is made unless at least the parent folder matches.
- **quality**: measured. Compiles or not (with the error); counts of functions, classes, and empty or raise-only
  functions; whether it's a test; line count; number of TODO/stub/mock/fake/placeholder words.
- **potential**: a rule from status, origin and quality (see the end of this page). A starting point, not a verdict.
- **fingerprint**: git's blob id of the content, the same id `git hash-object` gives.
- **same_content_count**: how many places in the zips hold this exact content.

## What was covered

- **Google Drive, account whatsupjosie, folder "big zip"** (id `12VLg8U4Yb9Gl-jVbR_OjYrZIfzB009Ww`): all 13 zips
  under 10 MB, downloaded and opened. Every size matches Drive's exactly.
- **PUBCAST_FIRST_PRIME_UPLOAD_PACKAGE_20260618_063754.zip** (69,099,094 bytes): over the Drive connector's 10 MB
  limit, so it was taken from GitHub The-Prime, where it is committed. Its size matches Drive's exactly, and the
  PRIME_CANON zip inside it (70,750,194 bytes) matches Drive's PRIME_CANON exactly. Both were opened.
- **GitHub**: every branch tip of 23 repos (196 tips): pre-dec, December, Beyond-October, October-24, The-Prime,
  Saturday, NowCurtsey-Build, DREAMS, friday, Thursday-, Pucast-Tuesday, Wednesday-, Just-The-Pubcast, Storage, 6.0-,
  Pubcaast-Breaking-Dawn, Pubcast-Reach, Parts-Live-Archive, Pub-Partner-Base-Horizon, The-Counter-and-2i,
  Pubcast-Phase-2-, Pubcast-AI-3-20-26-Agent-Pass and Iteration-Wallet. Every zip committed in any of them (94
  distinct zips) was opened.
- **Depth**: every zip was opened recursively, with no depth limit. The deepest found is zips 5 levels inside zips,
  and folders 10 levels inside a zip. Paths that would escape their folder: none found. Unreadable entries: none.

## What was NOT covered (each says why)

- Drive zips over 10 MB with no byte-identical copy on GitHub; the Drive connector refuses to download them:
  - `Ring Me Jeeves Parts 61126-526 PM.zip` (134,939,475 bytes)
  - `pucastpy and pub.zip` (38,200,180)
  - `codex_construction_pubcast_20260614.zip` (60,148,856), `_beefed` (60,209,464) and `_pubblocks` (60,141,231)
  - `pubcast_complete_debugged_2026-05-08.zip` (68,085,215)
  - `friday-Lunch (1).zip` (41,559,116) and `friday-whatsupjosie-further-better.zip` (41,473,396). Their names match
    GitHub's branch download of repo friday, branches Lunch and whatsupjosie-further-better. Those branches ARE in
    `branch_files_index.tsv`, but that the zips equal them is NOT verified.
- **Drive folders holding extracted copies** (listed 2026-11-26; see `drive_folders_index.tsv`): 1,426 files, listed by
  type: Python, JavaScript, HTML, CSS and zip in every folder below; plus Markdown, text and other binary files in
  pubcast_complete_debugged_2026-05-08.
  - **How each was identified.**
    - 24 were downloaded and hashed.
    - 1,394 match an indexed file by name and exact size. Five of these were sampled, downloaded and hashed, and all
      five were byte-identical to the predicted fingerprint.
  - **Result.**
    - 7 contents are new, meaning in no zip or branch tip: an older `capture.py` (Feb 2026); an older
      `pubcast_vision_integration.py`; `test_memory_systems.py`; a `conftest.py`; one small test; and
      `DEBUGGING_REPORT.md`. See READ_NOTES.md section 9.
    - 1 file could not be opened: a 15,284,978-byte `main.py` in codex_construction (Drive id
      1vrUMHt-1zO8D8O2HDVtpdLZ4cZOHA-w8), which is over the connector's 10 MB limit.
  - **Not listed in these folders.** Folder entries themselves; JSON and image files; Markdown/text outside
    pubcast_complete_debugged; Rust build `.d` files beyond the first 98; and the `.git` folder
    (1VwmtPI_-saCS11hFYcGXxFaIT3XyS531).
  - **Why the big zips are mostly covered after all.** These folders are extracted copies of the large zips that could
    not be downloaded. Almost all of their code is already in the index.
- Drive folders (the original list; all but .git are now listed as above):
  - `codex_construction_pubcast_20260614` (1_A_yjDZxhfL8B3Fm3MPXKMNz5K2B9Y96)
  - `codex_construction_pubcast_20260614_pubblocks` (192ISPO4EeHV-Hr6qfymEUQOsjM0DI9p2)
  - `pubcast_complete_debugged_2026-05-08` (1vOOX-CbaYiF8J8aSzrOV21evR55gwV8n)
  - `codex_current_wiring_file_copies_20260615` (1ptCvocK0cVDj5kyD1tNk63B_ov8R4rO_)
  - `codex_ready_wiring_file_copies_20260615_133303` (1mLKxDiLWqxT5ludSMX1-Nw1r0FjPC1XB)
  - `codex_autonomous_session_planning` (1-mcRzMq4RFDH-dr_JSoCADVPmh5g-8zK)
  - `rubbish` (1bN5Y93EQgDZ5QPAtP8NSpZOf8EvNlgIV), `duplicates` (1HvEU6rCeOO2Omg8JoMFI-RqvoF_8iEy2) and `.git` (1VwmtPI_-saCS11hFYcGXxFaIT3XyS531)
- Git history: only each branch's latest commit is indexed. A file that exists only in an older commit is not here.
- Repos not attached to this session: October (private), Pub-Experiment (private), Shirtshow (no branches) and
  Iteration-Wallet's history.
- Loose (unzipped) files elsewhere in Drive, outside "big zip".

## Counts (from `stats.json`)

- **Zips**: 16,059 file entries; 7,798 distinct contents.
  - Distinct contents: 1,111 already in the current build; 4,167 in some branch but not the current build;
    2,520 in no repo branch at all (they exist only in these zips).
  - 11,029 entries are project files; 5,030 are third-party libraries or build output.
- **Branches**: 14,429 distinct files across 196 branch tips.
- **Flagged for a human read**: 1,059 distinct project code files. 599 of them touch the engine by name or content
  (the word list is in `tools/parts_index/candidates.py`).

## Checks run on this index (RAN, 2026-11-26)

- **Status column**: 600 random rows (200 of each status) checked against git directly. "In current build" rows
  exist in the `finish/control-room-engine` tree; "in a branch" rows exist in the fetched branch store and not in
  current; "nowhere" rows are absent from the store of all 196 branch tips. **600 of 600 correct.**
- **Comparison column**: 12 random rows recounted independently (line multiset difference). **12 of 12 correct.**
- **Defects found and fixed before this was committed**:
  - files with a byte-order mark were wrongly marked "does not compile";
  - the comparison read an empty current file because of a wrong branch name; it now stops instead of passing;
  - the comparison was made against any file of the same name, even an unrelated `__init__.py`;
  - code summaries showed code lines, and missed /*! */ block comments;
  - 501 locations were cut short before the path inside the zip;
  - third-party library files were flagged as harvest candidates.
  - (found 2026-11-26, after the first commit) the list of current files was keyed by content, so 544 current paths
    whose content also sits at another path were invisible to the name comparison. Example: `facial_performance.py`
    in the zips was marked "no same-named file" though `modules/evo/facial_performance.py` exists. Fixed and rebuilt.
    8 distinct contents changed verdict; no status changed.
- **Note on "closest current file"**: this is the current file of that name with the fewest differing lines. It can be
  a copy under `recovery/` rather than the live one under `modules/`. Before porting, compare with the live file too.

## Human reading

`READ_NOTES.md` (in this folder, growing) holds what Claude has actually read, file by file: what it does, its
quality and its potential, marked READ. Everything else in the TSVs is EXTRACTED, as described above.

## The potential rules

| Condition | Potential |
|---|---|
| identical to current | nothing to harvest |
| under .venv, site-packages, node_modules, vendor, target, `__pycache__`, .git | third-party or build output, no harvest value |
| `.pyc` | compiled cache; value only if its source is lost |
| same name in current, 0 lines only here | subset of current |
| same name in current, 1 to 5 lines only here | near-identical; check those lines |
| same name in current, more than 3× as many lines only in current | mostly older; read the lines only here |
| same name in current, otherwise | different version with content of its own: read and compare |
| current file of that name is empty | check whether this content is needed |
| code with no same-named file in current | candidate to read for missing parts |
| Python that does not compile | reference only |
| test file | may cover behavior worth keeping |
| notes or handoff | read for decisions or lost context |
| media | check whether a screen or set needs it |
