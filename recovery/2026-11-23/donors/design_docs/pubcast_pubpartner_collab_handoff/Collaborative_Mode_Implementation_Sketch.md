# Collaborative Mode — Implementation Sketch

Companion to `collaborative_mode_prototype.html`, which demonstrates the front-end interaction mechanic with simulated (non-AI) text. This doc sketches what a real backend needs to look like.

## What the prototype proves
- Segment-based state (`pending` → `staged` → `committed`) driven purely by status, not separate data structures.
- A reveal-speed consumer decoupled from generation speed.
- Edit-triggers-regeneration-forward, without touching committed text.
- Paragraph-level unlock on already-committed text, as an explicit, separate action from normal editing.

## What it does NOT prove (needs real backend)
- Real model streaming instead of a canned sentence pool.
- Persistence across a closed tab/session (the "auto-finalize as unreviewed draft" rule).
- Real audio/TTS word-level sync for the karaoke highlight.
- Multi-session/multi-document handling.

## Data model

```
Document {
  id
  skeleton: { summary, beats: [{ id, description, target_state }] }
  committed: [ Paragraph ]
  session_state: 'idle' | 'streaming' | 'paused'
}

Paragraph {
  id
  text
  locked: bool          // true unless explicitly unlocked
  committed_at
}

StagingSegment {
  id
  text
  status: 'pending' | 'staged'
  order
  audio_start_ms?        // if TTS alignment is available
  audio_end_ms?
}
```

Keep `StagingSegment`s ephemeral — they don't need to survive a server restart the way `Paragraph`s do. On tab-close, whatever's left in staging gets swept into a `Draft` record (see below) rather than lost.

```
Draft {
  id
  document_id
  segments: [ StagingSegment ]   // frozen snapshot
  created_at
  reviewed: false
}
```

## Core API surface

```
POST   /documents                          create document + skeleton
GET    /documents/:id                       fetch committed text + skeleton
POST   /documents/:id/stream/start          begin generation from current committed tail
POST   /documents/:id/stream/pause
POST   /documents/:id/stream/resume
POST   /documents/:id/segments/:id/edit     { text }  -> regenerates forward from this point
POST   /documents/:id/paragraphs/:id/unlock
POST   /documents/:id/paragraphs/:id/save   { text }  -> re-locks
POST   /documents/:id/close                 sweeps remaining staged segments into a Draft
GET    /documents/:id/drafts                list unreviewed drafts for this document
```

`stream/start` and the edit-triggered regeneration both resolve to the same underlying call:

```
regenerate_from(document, anchor_text, skeleton) -> stream of segments
```

Where `anchor_text` = last committed paragraph + (if mid-edit) the just-edited segment text. This is the whole trick that makes "cascade" work — it's not a special diff algorithm, it's just: throw away stale staged segments, re-prompt from the new anchor + skeleton, let the model's own consistency do the rest.

## Streaming/pacing separation

Two independent rates, don't conflate them:

- **Model throughput** — however fast tokens actually arrive from the provider. Buffer these server-side into complete sentences/segments before exposing anything to the client.
- **Reveal rate (WPM governor)** — a server-side (or client-side, doesn't matter much) timed consumer draining the segment buffer at the user's chosen pace. Pause/resume only touches this consumer — the underlying model call is untouched, so pausing never wastes a generation or needs to be resumed mid-token.

This also means "think 3 paragraphs ahead" is just: let the buffer grow past what's currently revealed, capped at some max lookahead (the prototype uses a 5-segment cap; production probably wants this configurable per-document).

## Commit rule
Auto-commit a segment when either:
- it scrolls past the threshold (client signals `segment_viewed_and_passed`), or
- a paragraph boundary is reached and N seconds pass with no edit to anything still in staging.

Once committed, the model must not be able to touch it — enforce this server-side (`regenerate_from` only ever operates on segments still in `staged`/`pending`, never on `Paragraph` rows) so a sloppy prompt later in the session can't silently rewrite something ten paragraphs back.

## TTS / karaoke sync (if voice mode is in scope)
Use a TTS provider that returns word- or phrase-level timestamps (ElevenLabs and a few others support alignment metadata). Store `audio_start_ms`/`audio_end_ms` per segment at generation time; client highlights whichever segment's range contains current playback time. Without alignment data, fall back to estimating highlight timing from the WPM setting — good enough for v1, not audio-accurate.

## Suggested build order
1. Segment state machine + manuscript/staging UI (prototype already covers this — port to your real stack, e.g. React + your existing PubPartner tray shell).
2. `regenerate_from` wired to a real model call, no pacing yet (reveals instantly).
3. Add the reveal-rate consumer/governor.
4. Add paragraph unlock + Draft sweep-on-close.
5. Add skeleton/beat tracking as persistent context.
6. TTS alignment last — it's additive and doesn't block anything above it.
