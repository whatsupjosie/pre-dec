# Alex Prime Core v0.6 Change Log

## Added

- Durable PersistentMemoryStore with append-only hash-chained event log.
- PersistentMemoryRecord and PersistentMemoryEvent data models.
- MemoryScope and MemoryEventType enums.
- Promotion path from MemoryCandidate into accepted persistent memory.
- Consent gate for memory promotion.
- Protected-core approval gate for identity and care-rule memory.
- Quarantine block for intense or special-category-risk memory.
- Retrieval over accepted memory records with matched terms.
- Runtime methods for memory promotion and retrieval.
- Persistent memory demo.
- Persistent memory engineering note.
- Tests for consent, promotion, quarantine, protected-core approval, retrieval, and tamper detection.

## Design decision

Persistent memory is separate from BlackBox evidence. BlackBox records intervention evidence. PersistentMemoryStore records approved memory custody. Iteration Wallet should later protect Prime snapshots and approved export bundles.
