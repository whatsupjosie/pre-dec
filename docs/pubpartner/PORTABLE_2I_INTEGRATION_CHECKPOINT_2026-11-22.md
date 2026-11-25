# Portable PubPartner + 2i: integration checkpoint (2026-11-22)

Branch: `gpt/pubpartner-portable-2i-2026-11-22`
Based on: `pre-dec/codex/studio-integration` (preserves NEWER 2i editor and separate 2i Chat mode).

## Reused, not rebuilt
- `2i/writers-room-v22.html` and all existing `2i/2i-assets`: the complete newer editor in this branch (not the older Beyond-October copy).
- `modules.writers_room.create_writers_room_router`: real owner-scoped document store, revision control, versioning/fork API.
- `modules.manuscript_intelligence.make_router`: existing chapter indexing, signals, generation via PubPartnerSpine (no new LLM).
- `modules.hub.Hub` and `modules.chat_rooms`: local HTTP/WebSocket World Chat transport used by the **separate** `/2i/chat` mode (previously reachable only from the heavy PubCast host).
- `static/twoi_chat_archive.html`: existing 2i chat archive view.
- `pubpartner_app.py`: portable standalone app without studio/cameras.

## Routes included in Portable
- `/2i`, `/writers-room`, `/2i-v22` → same full newer editor.
- `/2i/chat`, `/2i/chat/archive` → new 2i Chat and archive pages.
- `/2i-assets/*` → existing editor scripts/styles.
- `/api/writers-room/*` → documents and version history.
- `/api/pubpartner/manuscript/*` → existing indexed manuscript work.
- `/api/chat/*`, `/ws/chat/*` → existing local chat transport.
- PubPartner File menu → local 2i editor / Chat.

## Authority and docking rule
- **Undocked:** Portable 2i is independently usable for local documents, chat, and offline changes. It owns its own working state. The local World Chat room is *local*, not a falsely claimed connection to PubCast's remote World room.
- **Docked and authenticated:** PubCast 2i takes editorial and sync lead. Portable remains fully operable but cannot overwrite PubCast manuscripts or chats without a verified sync decision. The transport must validate the paired owner and Base identity and journal pending local changes before any leadership transition.
- **Disconnect:** Portable resumes as local lead using its retained working copy and queued changes.
- The existing `pubpartner_federation.SyncEngine` has vector clocks/conflict support; new 2i document sync and a verified leader handoff still need dedicated wiring. No successful pairing/leadership switch is claimed in this branch.

## Dictionary check: NOT YET FOUND
The user reported adding a dictionary on November 21. Inspection of both `pre-dec/codex/studio-integration` and `pre-dec/integration/2i-unified-2026-11-20` found browser spellcheck and older WordNet resource metadata, plus a Node `/api/thesaurus` endpoint, **but no confirmed newer dictionary interface/implementation**. This is a missing source-of-truth input, NOT permission to replace yesterday's work with a new generic dictionary. Locate the exact newest dictionary implementation before releasing/merging the portable package. Test lexical data and interface offline.

## Important distinction: two chat contexts
- Writer sidebar chat: private AI writing conversation via existing PubPartner turn pipeline, manuscript context retained separately from personal memory.
- `/2i/chat`: independent general Chat mode, initially the existing PubCast World Chat transport. In Portable it is a **local** chat room until authenticated docking. Do NOT conflate either with the other or silently merge their histories.

## Verification and release gate
- Source changes and model-free HTTP route tests are committed.
- Python tests and real Chromium/phone checks **have not run** in this branch.
- Before merge: test editor save/reload/fork, chat REST + websocket, offline restart, private chat boundary, 2i menu, source asset references, dictionary, and paired docking/undocking conflict handling.
- Do not overwrite the newer editor with the older Beyond-October 2i tree or merge this branch merely because route registration succeeds.
