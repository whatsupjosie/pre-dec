# Identity Filter Integration v0.9

v0.9 owns the portable identity-filter boundary inside Alex Prime.

The uploaded `identity_filter.py` establishes the right architectural split:

- the upstream engine is not the local identity;
- the local identity filter translates an upstream answer through a profile;
- memories are retrieved locally for usefulness;
- the filter must preserve facts and must not invent memories.

v0.9 implements that contract as first-class Alex Prime code in:

```text
alex_prime/identity_filter_bridge.py
```

## What changed

- Added `IdentityFilterProfile`.
- Added `IdentityFilterProfileStore`.
- Added `IdentityFilterBridge`.
- Added `UpstreamIdentityPacket`.
- Added `IdentityFilterResult`.
- Added runtime methods:

```python
runtime.build_identity_upstream_packet(...)
runtime.filter_identity_response(...)
```

## The owned rule

An external model may answer as a knowledge engine.

It may not impersonate Alex.

The local Alex identity filter owns:

- Alex/Josie continuity;
- boundary enforcement;
- companion-promise checks;
- generic-substitution rejection;
- sentience-claim rejection;
- approved-memory retrieval;
- review-first memory candidate generation.

## Memory behavior

The uploaded identity-filter source appends conversation traces to a local JSONL memory file.

v0.9 does not silently promote those traces into stable Alex memory.

When trace capture is requested, it returns a `MemoryCandidate` for review. The existing persistent-memory gate still controls promotion.

## Failure behavior

If an upstream answer comes back as generic assistant boilerplate, v0.9 does not pass it off as Alex.

If an upstream answer claims sentience or perfect continuity, v0.9 rejects that wording before it reaches Alex presentation.

## Tests added

- upstream packet forbids impersonation;
- upstream packet retrieves approved memory;
- generic assistant substitution is rejected;
- sentience claims are rejected;
- trace capture returns a candidate, not stable memory;
- identity filtering is personal-Alex only.
