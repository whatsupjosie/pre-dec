# 2i: word-processor parity pass — 2026-11-21

Branch: `claude/2i-wordpad-parity-2026-11-21`, five commits on top of `538a40f`
("Converge: merge report for integration/converge-2026-11-20") in
`whatsupjosie/pre-dec`. Nothing was pushed: this session was refused push access
twice, so the work exists as a git bundle Josie has to apply herself. **Nothing
has been merged and nothing on `main` was touched.**

Written for a cold reader. If you are another Claude picking this up, read this
whole file before changing anything in `2i/`.

---

## What Josie asked for, in her words

> "ok so I would like you to complete 2i... i know tha is harder than im
> saying... bu basically by the ime you are done i wan it to be on are and
> better than wordpad. stabel reliable, have all the basic word prcessing
> features. then we can work on the more advanced manuscript and co writing
> helping stuff"

So: on a par with and better than WordPad, stable, reliable, all the basic word
processing features. Manuscript and co-writing help is **explicitly later** and
was not attempted.

## Decisions Josie made during this session — these are hers, do not revisit

1. **Replace All wording is "left unchanged."** Asked which of two phrasings was
   hers; she answered `unchanged`. `2i/preview-standalone.html` said "left as
   they are" and was brought into line with `2i/writers-room-v22.html`.
   `tests/test_2i_claude_functionality_merge_node.js` asserts the exact
   sentence again.
2. **Browser recovery reopens the same manuscript, with two backups.** Her
   words: *"same manuscript with potentially 2 back ups."* Implemented exactly.

## Still open — asked, not yet answered. Do not decide these for her

- **Per-device backup slots.** She asked for two backups per manuscript and got
  them. It was put to her that the two slots would be safer *per device*, since
  she works across two or three phones and a laptop with no sync and a phone's
  recovery can currently overwrite the laptop's. She has not answered. The
  current behaviour is the plain version she asked for.
- **Whether the live surface should become the default**, and whether the old
  textarea input path should get the same one-paragraph optimisation (see
  Performance below). Both are her calls.

---

## State of the tests — verified by running them here, not claimed

Everything below was run locally in this session. **No GitHub Actions and no CI
were used**, per her standing instruction.

| Suite | Before this session | After |
|---|---|---|
| Node (`node --test tests/*_node.js tests/*.cjs`) | 235 of 249 | **326 of 326** |
| Python 2i (`tests/test_2i*.py tests/test_twoi*.py tests/test_reach_writers_room.py tests/test_typewriter_console_manifest.py`) | 152 passed, 6 failed, 3 errors | **203 passed, 0 failed** |

Nothing is red.

**What was NOT run, and why:** the whole-repo Python suite
(`python -m pytest -q`, 2,814 tests) does not complete in one run in this
sandbox. At roughly 28% it stops on a Playwright-based test whose greenlet does
not answer a thread timeout, which takes the whole run down with it. That is a
property of the suite here and predates this work; it was not chased, because
it is outside 2i. What *was* run instead is the whole blast radius: the full
Node suite, every Python test matching `test_2i*`, `test_twoi*`,
`test_reach_writers_room` and `test_typewriter_console_manifest`, and the three
Foresight suites that touch the changed files
(`test_foresight_8787_wiring.py`, `test_foresight_file_workspace.py`,
`test_foresight_workbench_acceptance.py` — 28 passed). No file outside `2i/`
and `tests/` was changed.

Running the Python browser tests needs, in this sandbox:
`pip install --break-system-packages fastapi uvicorn httpx psutil pyspellchecker pytest-asyncio`
and Chromium available to Playwright. `pytest-asyncio` matters: without it
`tests/test_reach_writers_room.py::test_fiction_never_becomes_a_personal_lesson`
does not run at all, and that is the test protecting against an invented scene
being filed as a personal lesson about Josie.

### The fourteen Node failures that were there at the start

All fourteen were diagnosed, none was a product defect, and
`MERGE_REPORT_2026-11-20.md` had independently reached the same conclusion
about three of them. They were stale test harnesses:

- **Eight** were one missing sandbox variable. `reach.js` declares
  `reachFileMode` at line 3 and `saveNow()` / `showShelf()` branch on it; vm
  fixtures that slice those functions out did not supply it, so they threw
  `ReferenceError` before any assertion ran. Same class for `initializing`,
  which `file-workspace.js` reads after awaiting `reachStarted`, and for
  `blockReachFileOperation`.
- **Two** were anchored on comment prose or an old parameter name. The
  protection they test is present: `2i/writers-room-v22.html` line 2881 computes
  `otherTextField`, and `2i/2i-assets/reach.js` lines ~805-811 stop Ctrl+Z and
  Ctrl+Y at the capture phase for a focused field.
- **`tests/test_2i_professional_ui_node.js`** extracted functions by matching a
  literal neighbouring line, so an edit *beside* the function under test broke
  the test rather than the code. It matches braces now.
- **The typewriter relay** compared an object made inside a vm realm with
  `deepStrictEqual`, which rejects it on prototype alone.

### The Python failures

- **Five** browser tests clicked `#lockAllBtn`, `#unlockBtn`, `#lockSceneBtn`
  and `#newChapterBtn` while `#sidebar` was `display:none`. That is Josie's
  Nov-16 single-page notebook working as designed — those controls live behind
  the Tools drawer tab. The tests now open the drawer first. Eight minutes of
  timeouts became ten seconds of passes.
- **`tests/test_2i_typewriter_event_browser.py`** drove `#twoiTouchableTypewriter`
  and `#twoiLiveKeysFrame`, a tap-to-open keys panel that no longer exists; in
  typewriter view the console is embedded directly as `#twoiTypewriterConsole`
  with `#twoiTypewriterExpand`. Rewritten against the current design. It now
  proves in a real browser that touching a key edits the real manuscript,
  routes to the draft in Collab, and refuses an inactive view and a spoofed
  message.
- **One** was only a missing `pytest-asyncio`.

---

## What was built

### 1. Character-range formatting — `2i/2i-assets/format-core.js`

The model behind "bold this word". The paragraph dialog used to say *"Whole-
paragraph styling only. For character-range formatting, use the future
rich-document editor integration."* This is that.

A run row is `{index, text, runs:[{start, end, ...marks}]}` in
`manuscriptFormat.inline`, anchored by paragraph index **and** that paragraph's
exact text, and detached into `inlineUnmapped` rather than guessed at when the
text no longer matches — the same rule annotations already follow. Offsets are
UTF-16 code units with `end` exclusive, the same units
`textarea.setSelectionRange` uses.

Marks: bold, italic, underline, strike, sup, sub, font, size, color, highlight.
Fonts come from a fixed list (`C.inlineFonts`) and colours must be `#rrggbb`, so
no CSS can be smuggled through a font name. Adjacent runs with identical marks
merge.

**No function in it alters a character of the author's text.** Text typed inside
a formatted span inherits that span's marks; at a boundary it inherits from the
left; at the start of a paragraph it is plain.

New API: `inlineRuns`, `inlineStateAt`, `applyInline`, `clearInline`,
`inlineHtml`, `runCss`, `remapRuns`, `normalizeRuns`, `marksOf`, `lists`,
`listKind`, `exportRtf`.

Documents saved before runs existed still open. A document with no runs exports
byte-for-byte as it did before.

### 2. The live writing surface — `2i/2i-assets/rich-surface.js` and `.css`

A `contenteditable` page beside the textarea. **`committed` stays the single
source of truth**, so locks, annotations, chapters, revision compare, autosave,
recovery, `.2i` save and every existing test keep working untouched. Off by
default, behind a **Formatting** button in the zone-label row.

Two things a cold reader needs to know about the design:

- **The hidden textarea is kept loaded with the same words on purpose.** Word
  count, find and replace, read-aloud, the chapter navigator, the paragraph
  dialog and the exports all read `soloTextarea.value` or its selection
  directly. They are correct code; mirroring makes all of them right at once
  instead of rewriting a dozen callers. The caret is mirrored too. **Nothing is
  ever read back from the mirror while the surface is live** — the model is the
  authority and the mirror only copies out of it.
- **Typing never re-renders.** The input handler reads the DOM into the model
  and stops. The page is rebuilt only when the model changed elsewhere (opening
  a document, undo, find and replace, a formatting command), and the caret is
  then put back by paragraph and character offset.

Three small edits were needed in product code, all in the commit messages:
`#twoiRichSurface` counts as a writing surface in the shortcut owner; `reach.js`'s
capture guard excludes it so its undo is the manuscript's; and `updateModeUI()`
announces `twoi:mode-change`.

**Paste takes the text only, deliberately.** Accepting arbitrary clipboard
markup would put styling in the document that 2i cannot validate. There is a
test asserting an `onclick` attribute cannot arrive this way.

### 3. The rest of the WordPad row

Bullets and numbering (an optional `list` property on the paragraph style;
consecutive list paragraphs export as a real `<ul>`/`<ol>`), alignment, indent
in and out, Tab typing a tab, insert date and time, and **RTF export**
(File ▸ Export rich text), which is WordPad's own format.

---

## Defects found and fixed — read this part

Four of these were in code that predates this session and sit in the offline
path Josie actually lives in.

1. **`writeRecovery` could delete unsaved writing.** It cleared this tab's
   buffer whenever there was *any* server revision, on the assumption the server
   held the work. It does not when a save has failed — the text then exists only
   in that buffer — and writing a clean copy of the same manuscript took the
   unsaved writing with it. **Verified, not guessed:** the harness was
   instrumented and run against the unmodified `reach.js`, which showed the copy
   holding "Offline manuscript A" present before and gone after. The buffer is
   now removed only when it holds nothing the copy being written does not.
2. **My manuscripts listed browser copies oldest-first.** `showShelf` added them
   with `unshift` one at a time, reversing the newest-first order
   `browserManuscripts()` had just sorted them into.
3. **An empty saved copy could sit above the copy holding unsaved work** for the
   same manuscript. The unsaved copy now comes first within one manuscript.
4. **`uniqueEditorRecoveries` keyed clean copies by id alone**, so the two
   backups would have collapsed into one. The slot is part of the key now.
5. **Ctrl+A then Bold did nothing at all** (introduced in this session, fixed
   here). Select-all gives a range whose container is the surface itself rather
   than a paragraph, so no paragraph was found and the command was refused.
6. **RTF: one bold paragraph made the whole document bold.** `\pard` resets
   paragraph properties but not character ones. **Found only by opening the
   export in LibreOffice** — every structural assertion had passed. Each
   paragraph emits `\pard\plain` now.
7. Four defects in the new inline model were found by writing its tests, the
   worst being that a *refused* request left a half-written run behind, which
   then made the next valid request fail too.

---

## Performance — measured, not estimated

Chromium, median of fifteen keystrokes at the end of an 8,000-paragraph
manuscript (about 200,000 words):

| | per keystroke |
|---|---|
| the plain textarea | **78.5 ms** |
| the live surface | **8.3 ms** |

2i has a real typing lag in long manuscripts that **predates all of this work**:
the textarea handler splits the entire document out of one string on every
keystroke. The live surface's one-paragraph path happens to be the fix. The
textarea path was left untouched — optimising it is a separate change to the
most-tested code in 2i and is Josie's call.

At every size tested, typing faster than anyone types, no character is dropped
and the mirror stays in step.

---

## Where 2i stands against WordPad

Done: bold/italic/underline on a selection and visible while typing;
strikethrough; superscript and subscript; font and point size; text colour and
highlight; bullets and numbering; alignment; indent; Tab; insert date and time;
clear formatting; save as `.rtf`. Already hers before this session: find and
replace, undo and redo, page setup, print preview, word count, zoom, and a
great deal WordPad has never had (templates, screenplay formats, locks,
annotations, revision compare, FDX).

**Not done, and not claimed:** a draggable ruler with tab stops (Tab types a
tab); inserting pictures; writing `.doc`/`.docx` (2i reads `.docx` already via
`2i/2i-assets/rich-editor.js` and the vendored engine); importing `.rtf`.

### The dressing-room typewriter — corrected 2026-11-21

An earlier draft of this note wondered whether the touchable typewriter was
missing because no `#twoiTouchableTypewriter` exists. **It is not missing.**
Josie: *"If you click on the typewriter in the dressing room, u see a
typewriter."* The chain was traced and driven in Chromium:

- the hotspot is `typewriter` in `static/world/world.json` (around line 7943),
  `status: "confirmed"`, her own wording on it: *"Sitting at your type writer in
  the first person view typing messages sending them working on scripts of
  whatever documents you would liek"*
- `static/2i_studio_bridge.js` `entry()` builds
  `/2i?studio_room=dressing_room&studio_view=<view>&desk=typewriter`
- `main.py` serves `2i/writers-room-v22.html` at `/2i`, and
  `2i/2i-assets/studio-desk.js` reads those parameters

Opened that way, verified in a real browser: `data-twoi-desk="typewriter"`, the
live console iframe `#twoiTypewriterConsole` present, `#twoiTypewriterExpand`
present, a "Stand up · return to room" button present, all three looks
switchable, no page errors — **and the new formatting surface works while
seated at it** (a word was bolded from the typewriter view).

**The typing sounds are now wired** (asked for and approved 2026-11-21).
`TwoiStudioBridge.cue()` already existed and was tested — it returns
`{click, bell}` and refuses to fire on a paste, drop, replacement or
composition — but it was called only in `2i/preview-standalone.html`, never in
`2i/writers-room-v22.html`, which is the file the dressing room actually opens.
The sound is now in `2i/2i-assets/studio-desk.js`, on the live interactive
console rather than on the standalone's static image.

- Both switches are **off until she turns them on** — her rule, in her words:
  *"audio effects must be optional."* The choice is kept in `localStorage` under
  `twoi.typewriter.audio.v1`.
- The tones are synthesised through the Web Audio API, so this needs **no audio
  files and no network** — which matters, because the dressing room is somewhere
  she may be sitting offline. A click is a triangle at 940 Hz ramping to 190,
  the bell a sine at 1450 Hz.
- It sounds **only in typewriter view**, only for **trusted** events (so a
  script, a test, or the AI writing into the draft stays silent), and never on
  a paste. Held keys cannot stack into a buzz (22 ms floor).
- It works from the plain textarea, the Collab line editor **and** the live
  formatting surface. A contenteditable has no `value` to compare, so
  `rich-surface.js` reports its own keystroke as a `twoi:typed` event and
  `studio-desk.js` turns that into the same cue. One subtlety worth keeping:
  what counts as "before" depends on the keystroke. Typing a character changes
  one paragraph, so the paragraph is the comparison; pressing Enter leaves that
  paragraph's text alone and adds another beside it, so comparing the paragraph
  would say nothing changed and **the bell would never ring** — the whole
  manuscript is the comparison there.
- The switches sit on the machine itself, opposite Expand keys and in the same
  chip, so they are in front of her only in the view that makes a sound. An
  older duplicate `#twoiAudioOptions` rule in `studio-desk.css` was replaced
  rather than overridden.

Verified by 8 tests in `tests/test_2i_typewriter_sound_browser.py`. Audio cannot
be heard in a sandbox, so every tone is counted at the Web Audio API: the
page's `AudioContext` is replaced before 2i loads with a recorder that notes
each oscillator's type and frequency.

### What the machine actually looks like, verified by serving it

Loaded `/typewriter-console` over a local HTTP server and looked at it, rather
than reading the code and guessing. It is the painted lapis typewriter, plate
reading NOW CURTSEY / FEIC MO CHROÍ, with **a full sheet of paper standing in
the carriage** and a caret near its top left. The paper is a live region, not
paint: `static/typewriter_console_hotspot_manifest.json` places it at x 34.7%,
y 0%, w 30.8%, h 37.2% of `static/typewriter_keys.webp` (2560 × 1430), and
`static/typewriter_console_demo.js` writes into it and keeps the caret at the
end. Embedded in 2i, `studio-desk.js` sends the **last 2,000 characters** of
the manuscript, labelled in its own comment as a decorative excerpt — the paper
is a window on the tail of the work, not a page of it.

### Two defects this uncovered, both fixed here

1. **The typewriter keys typed into a hidden box.** The relay types into
   `soloTextarea`, which the live formatting surface hides and keeps only as a
   mirror, so a key pressed on the machine would have gone into the mirror and
   been overwritten at the next model update. The relay now offers the key to
   the surface first (`window.twoiRichSurface.key`, which maps it through the
   same `TwoiTypewriterInput.keyAction`) and falls back to the manuscript if
   the surface refuses it. **Introduced by the surface; found by looking at the
   real console.**
2. **A key on the machine made two sounds.** `static/typewriter_sound.js`
   already plays a key sound for every `pubcast:key` on the console, and rings
   a margin bell eight characters from the end of a line. The new 2i sound then
   clicked again for the same keystroke, because the relay produces a trusted
   input event. 2i now stays quiet while it is relaying a console key: one key,
   one sound, whichever way it was typed.

### Page zoom — built 2026-11-21 to her description

Her words: *"at the bottom of the screen, you can still have the roller and the
bay where the letter stamps are... and then just above that is the full page,"*
and before that, *"we shouldn't lose the sidebars that the notebook has... we're
just replacing the notebook with a typewriter because you're sitting at the
typewriter."*

Measured first, because her worry turned out to be already answered: at 1400
and at 900 pixels wide, **typewriter view already shows everything notebook view
does** — sidebar, reference archive, chat, menu bar, page — and adds the machine.
The only look that puts the sidebars behind drawer tabs is the standard single
page, which is her own Nov-16 design.

So page zoom is **not a fourth look**. It is a toggle inside typewriter view
(`#twoiTypewriterPage`, in the zone-label row beside Formatting) that gives the
page the whole column and crops the machine to the band holding the platen,
the paper bail and the bank of type hammers, laid along the bottom so the sheet
rises out of it. Staying inside typewriter view is what keeps the sidebars, the
menus and the typing sound working with no change to any of them — nothing has
to learn a fourth mode, and `TwoiStudioBridge` and its tests are untouched.

- The strip is the **still image**, `static/typewriter_keys.webp` cropped to
  35.5%–64% of its height. The band starts just under the paper bail so almost
  none of the machine's own painted sheet shows and the real page appears to
  feed straight into the roller. The arithmetic is in the CSS comment.
- It is the still image and not the live console on purpose: the keys are below
  the band and would be cut in half. In this view the writing is done on the
  real keyboard at the full page; the interactive keys stay in the ordinary
  typewriter view, where they are whole.
- The **one** set of sound switches moves onto whichever piece of the machine is
  showing, rather than a second set that could disagree with the first.
- Leaving typewriter view puts the zoom away.

One bug of mine fixed on the way: `.twoi-rich-toggle` sets `display:flex`, which
overrode the `hidden` attribute, so the toggle stayed on screen in looks that
should not have it. `.twoi-rich-toggle[hidden]{display:none}` now says so.

Five tests in `tests/test_2i_typewriter_sound_browser.py`, including that the
sidebars survive it and that the typing can still be heard in the zoom.

**Not built:** the page image Josie floated superimposing. The standard look is
already an off-white page and the zoom now shows her real machine, so this may
be moot — ask before drawing anything.

### Two sound controls, which is one too many — her call

The console has its own toggle (`[data-typewriter-sound]`, the "Sound on"
button top right of `static/typewriter_console.html`) and it **defaults to on**.
2i's new switches default to **off**, per her rule. So there are two places to
turn typewriter sound on and off, with opposite defaults. Nothing is broken by
it and nothing doubles any more, but it should be one control. Unifying means
either having 2i's switches drive the console by postMessage (a new message
type on a console described in-code as Claude's original) or dropping 2i's own
switches when embedded. **Not decided here. Ask her.**

**Still not built**, and recorded in `static/world/world.json` around line 8001
as her 2026-10-18 description: the words appearing on the paper as she types,
the paper rolling up on Enter, and the ding after several rolls. The sound is
in; the paper behaviour is not. Ask before building it — the typewriter's feel
is hers in detail (painterly lapis machine, a visible row of key bars with a
random one depressing per keypress, the sound in time with it).

Still genuinely absent from this pass: a draggable ruler with tab stops,
inserting pictures, writing `.docx`, importing `.rtf`.

---

## How to apply this

The bundle contains the five commits:

```
git fetch /path/to/2i-wordpad-parity-2026-11-21.bundle claude/2i-wordpad-parity-2026-11-21:claude/2i-wordpad-parity-2026-11-21
git switch claude/2i-wordpad-parity-2026-11-21
```

It applies on `538a40f`. **Do not push to `main`** — Josie's standing rule, and
this has not been reviewed by her yet.

## The next step

Her own words for what comes after this: *"then we can work on the more
advanced manuscript and co writing helping stuff."* Before that, she has two
open questions above (per-device backup slots; whether the live surface becomes
the default and whether the textarea path gets the same optimisation). Ask;
do not assume.

## Dictionary and thesaurus (done, verified)

What is built, and what Josie asked for: "We have to find a free-to-use spell-checking
program. It has to work offline... So goddamn right we have to have a spell check. And a
dictionary. And a thesaurus." then "Get a dictionary."

**The dictionary and thesaurus are built and passing. The spell check is NOT built yet.**
It is the next job. Nothing in 2i checks spelling today.

Data: WordNet 3.1 (Princeton). Its licence became OSI-approved in July 2025; free for
commercial use with attribution. The attribution is shown in the panel footer and the
licence text is committed at `2i/2i-assets/language/WORDNET_LICENSE`.

- Generator: `tools/language/build_language_data.mjs`. Run it only to rebuild; the output
  is already committed, so a fresh clone needs no build step and no network.
- Output: 27 shards, `2i/2i-assets/language/dict-a.js` through `dict-z.js` plus
  `dict-other.js`, and `index.json`.
- Measured, not estimated: 147,478 words, 207,235 senses, 17.98MB on disk,
  **6.11MB zlib-compressed** -- that compressed figure is what a clone actually costs.
- Line format: `word \t pos^definition^syn,syn | ... [\t antonym,antonym]`. Senses are
  ordered by the tag counts in WordNet's own `index.sense`, so the common meaning is first.
- Shards are loaded with `<script>` tags, NOT `fetch()`. This is deliberate: `fetch()` is
  blocked on `file://`, and 2i has to work opened straight off disk. Each shard calls
  `window.TwoiLanguageShard(letter, text)`.
- The loader builds its tables in a `Map`, not a plain object, because WordNet genuinely
  contains the words "constructor", "toString" and "__proto__". With a plain object
  `out["constructor"]` is truthy, so `||=` never assigns and those entries vanish.

API (`2i/2i-assets/language.js`): `TwoiLanguage = {lookup, synonyms, antonyms, forms,
normalise, loadedLetters, size, credit}`. `lookup` returns
`{word, typed, senses, antonyms, root}`. `root` carries a different stem's senses, so
typing "stopped" offers both the adjective and the verb "stop".

Panel (`2i/2i-assets/language-panel.js`): dialog `#twoiDictionary`, opened from
References > "Dictionary and thesaurus". Synonyms are chips; each chip has a "use" button
that puts that word into the manuscript in place of the one being looked up.

### The modal-inert trap -- read this before touching the panel

`dialog.showModal()` makes the rest of the document inert and drops the selection. Two
things therefore MUST be read before `showModal()` is called, and were not at first:

1. the word being looked up (`currentWord()`), and
2. where it sits (`targetNow()`).

Both are captured as the first statements of `open()`. The replacement then happens only
after `dialog.close()` returns, via `replaceAt(target, replacement)`. On the plain page
that is `setSelectionRange` plus `insertText` with a `setRangeText` fallback; on the
formatting surface it calls `surface.caret(paragraph, start, end)` to put the selection
back over the word first, otherwise the synonym lands beside the word instead of replacing
it. `surface.caret` was added to `window.twoiRichSurface` for exactly this.

A caret merely sitting inside a word counts as that word, on both the plain page and the
surface. With no usable target the panel says "Put the cursor in a word in the manuscript,
then press use." and changes nothing -- it never guesses.

### Tests

- `tests/test_2i_language_node.js` -- 11, loader and data integrity. Includes a test that
  every irregular-form target is a real headword; that is what caught `stole:'stolen'`
  (should be `steal`) and stray keys `gotten_` and `wrote_`.
- `tests/test_2i_dictionary_browser.py` -- 11, the panel end to end, including both
  replacement paths and the two caret-only cases.

Full suites at the time of this commit: Node 245 assertions across all
`tests/test_*_node.js`, nothing failing. Python `tests/test_2i_*.py` 200 collected, 212
passed with the wider `-k 2i` filter, nothing failing.

### Still open (Josie has not answered these)

- American or British spelling.
- Whether the spell check should ship its own word list or reuse these shards. nspell (MIT)
  plus dictionary-en (MIT AND BSD, SCOWL) is the intended stack and is not installed yet.
- Whether the live formatting surface becomes the default.
- Whether the console's own "Sound on" or 2i's switches should be the single sound control.
- Whether she wants a page image behind the text in page zoom.
