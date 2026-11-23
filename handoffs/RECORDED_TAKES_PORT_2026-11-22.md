# Recorded stage takes — port onto the spine base, 2026-11-22

Written for a reader with no other context. "Verified" means I ran it.

## What this is

Branch **claude/recorded-takes-2026-11-22**, one commit (fd4e300) on top of
claude/spine-consolidation-2026-11-22. It is a cherry-pick of Codex commit
**086420d** from the branch codex/recorded-slate-sync-2026-10-28 (dated October
24-28, never merged into pre-dec main). That branch was found while checking every
branch of the Drive repos for work not in pre-dec; it is real, finished work.

What the feature does (from the Codex handoffs, which are included unchanged as
handoffs/RECORDED_SYNC_ORIGINALS_2026-10-28.md and SYNC_AND_STEMS_2026-10-28.md):
- the director records the real 3D stage canvas and the program audio mix as a take;
- 14-channel PCM stems share one sample clock; checkpoints every 15 seconds;
- a clap cue is found in the recorded picture and sound and the sync is measured,
  not assumed; the original is always kept, an aligned copy is made by FFmpeg;
- a take editor page (static/take_editor.html) with eight tracks and per-track nudges.

## What I changed while merging (three things, all small)

1. main.py: kept both sides; added ("/api/studio/slate/takes/", 128 MiB) to the
   large-upload limits.
2. static/director_console.html: this base has the hotspot console mount, Codex's
   had a different page. I kept the base page and put back the one iframe the
   recorder films: title "Program stage recording source", src /static/stage_3d.html.
   Without it the take button reports "Open the director console or a 3D stage".
3. static/studio_slate.js: the base slate forwards from iframes to the top window.
   I merged in the record-take button, the take log, "Clap / begin take", and
   window.PubCastSlate gaining getTiming and getTakeResult. **One line is mine, not
   Codex's:** findStage now accepts a window that has a canvas and
   PubcastProgramAudio.buses, as well as one with PubCastStageCamera. Reason:
   PubCastStageCamera is defined by Codex commit df9d30f (the on-set camera
   console), which this base does not contain, so stage detection failed and the
   take button never armed. If df9d30f is landed later, both conditions hold.

Also from Codex, unchanged: stage_3d.html gets preserveDrawingBuffer:true so the
canvas can be filmed.

## Verified

- tests/test_recorded_slate_sync.py and test_recorded_take_routes.py: 7 passed.
- tests/test_studio_slate.py: 6 of 7 pass. The seventh,
  test_live_voice_only_verified_director_can_transmit, hangs. It also hangs on the
  baseline without this port (and is the "passes alone" item in the harvest handoff),
  so it is not caused by this branch; I did not fix it.
- tests/test_recorded_sync_browser.py (real Chromium records the real stage, FFmpeg
  checks the take, the editor saves a nudge, a final MP4 renders): **passed end to
  end once on this branch** after the stage-detection fix. It is timing-sensitive
  in this sandbox, which has no GPU: run results were fail, fail, pass on this branch,
  and pass, pass, fail on Codex's own untouched commit (one failure was
  "unverified" instead of "verified_recorded_cue"; one was the reference stem ending
  about 2,048 samples before the fifteen-second checkpoint). So one pass proves the
  merge works; it does not prove the test is stable. Run it on your laptop.

## Not done

- No handoff-level review of how the take log interacts with the slate's
  generation counter on this base: logTake sends generation from the slate the
  page last read. I did not test two directors taking at once.
- Not run: the rest of the suite on this branch.

## Decision for Josie

Land this with the spine branch, or hold it until df9d30f (control room and on-set
camera console) lands, which makes the one-line stage-detection change unnecessary.
