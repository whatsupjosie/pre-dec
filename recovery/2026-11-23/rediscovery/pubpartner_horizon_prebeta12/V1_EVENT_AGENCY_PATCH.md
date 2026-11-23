# PubPartner V1 Event Agency — Working Patch

**Source snapshot:** `Frozen_PubPartner_Pre-Beta_Snapshot_v0.1.0-prebeta.10_2026-07-28_15-20-00_PDT.zip`  
**Source SHA-256:** `865ae53e3f150fce9e9b14aafaaa8321556dff0ce317a01a83dbbfbb200e3e76`  
**Working version:** `0.1.0-prebeta.11-event-agency-v1`

## What changed

This is the first real architectural step toward persistent event agency.

### Added
`modules/event_agency.py`

Provides:
- typed `Event`
- append-only `EventLedger`
- lifecycle transitions
- `PersistentEventAgency` facade
- dependency-free persistence
- inspectable JSONL history

### Integrated
`modules/bots.py`

`BotManager.nudge(room_id, hint)` retains its existing public signature and behavior, but now records:

`nudge → queued → delivered/failed`

The model still receives the same private stage hint. No autonomous decision-making was added.

## Why this is the correct V1 seam

The current system already has a meaningful nudge pipeline:

`RoomConductor → BotManager.nudge() → synthetic payload → _schedule_reply() → _generate_and_send() → LLM → chat`

We instrumented that existing seam instead of replacing it.

That gives us a durable record of what the system already does before adding attention, intention, or autonomous action.

## What we deliberately did NOT add

- autonomous messaging
- new model calls
- attention scoring
- persistent intentions
- inferred relationship state
- model-generated authoritative memory
- permission bypasses
- changes to prompt semantics

Those belong to later experimental stages.

## Current event lifecycle

```text
RoomConductor
    ↓
BotManager.nudge()
    ↓
Event(type="nudge", status="queued")
    ↓
existing scheduling path
    ↓
existing LLM generation
    ↓
chat delivery
    ↓
Event status = delivered
```

Failure becomes `failed`.

## Baseline integrity

The uploaded source snapshot remains untouched. This working tree is a copy with the V1 patch.

## Next recommended step

Run the full existing test suite plus `tests/test_event_agency_v1.py`, inspect the resulting event ledger during a live nudge, then add **event observation** before adding attention or intentions.
