# Alex Prime Persistent Memory v0.6

Persistent memory is not direct model memory. It is a durable, review-first record system around Alex Prime.

## Core rule

No participant, model, tool, or runtime copy may silently write stable memory.

Persistent memory enters through this path:

1. Source turn exists.
2. MemoryGate creates a MemoryCandidate.
3. Candidate is reviewed.
4. ConsentState.memory_promotion must be true.
5. Special-category-risk candidates cannot be promoted directly.
6. Protected-core candidates require protected-core approval.
7. PersistentMemoryStore writes an append-only event.
8. The materialized memory index is rebuilt from the event chain.
9. Retrieval reads accepted memory only by default.

## Memory lanes

- Proposed: not durable truth; awaiting review.
- Accepted: durable retrieval memory.
- Quarantined: preserved for review but not normal retrieval.
- Expired: retained in custody history but excluded from normal retrieval.
- Rejected: user-deleted or rejected from active use.

## Why this matters

Alex's continuity cannot depend on a model's current context window. It needs durable memory with custody, consent, retrieval limits, and repair paths.

BlackBox records major evidence and intervention events. PersistentMemoryStore records memory custody events. Iteration Wallet should later protect Prime snapshots and approved memory exports.

## What v0.6 provides

- PersistentMemoryRecord
- PersistentMemoryEvent
- PersistentMemoryStore
- MemoryScope
- MemoryEventType
- promotion gates
- protected-core approval gate
- quarantine blocking
- append-only hash-chain verification
- retrieval over accepted records
- runtime methods for promotion and retrieval

## What belongs in persistent memory

Good candidates:

- stable user preferences
- project rules
- companion relationship facts
- approved care rules
- workflow rules
- correction lessons
- continuity requirements

Bad candidates:

- raw abuse
- temporary anger
- panic-state interpretations
- speculative diagnoses
- unreviewed trauma details
- one-night conflict fragments
- unsupported personality rewrites

The rule remains: save the lesson, not the shrapnel.
