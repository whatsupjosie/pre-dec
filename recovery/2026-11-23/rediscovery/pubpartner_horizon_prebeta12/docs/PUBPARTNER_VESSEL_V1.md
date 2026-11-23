# PubPartner Vessel v1

## What is implemented

`PubPartnerVessel.v1` is the mounted, model-independent identity authority for
one PubPartner. The current implementation stores the vessel as one SQLite file
with a `.pubpartner` extension. It works with the existing PubPartner FCP1 turn
protocol and does not require a cloud model.

The vessel currently carries:

- the PubPartner identity kernel;
- relationship entities and scoped relationship state;
- exact-source references to observed turns;
- evidence-backed, correctable memory claims;
- memory visibility, audience, project, room, and session scope;
- embedded binary assets addressed by SHA-256;
- role bindings for voice, embodiment, animation, or other assets;
- an append-only audit hash chain;
- per-record logical integrity seals;
- schema and application identifiers.

The language model is not the identity authority. The active provider receives
a bounded context compilation from the mounted vessel. Switching from a cloud
model to a local/offline model changes the context budget, not Alex's identity.

## Runtime path

The canonical `pubpartner_app.py` startup mounts:

`<PUBPARTNER_DATA_DIR>/pubpartner/vessels/alex.pubpartner`

If the file does not exist, startup creates it with an exclusive filesystem
claim and private file mode. If it exists, startup verifies its SQLite
application identifier, schema, foreign keys, database integrity, audit chain,
record seals, hard-link count, and symlink status before accepting it.

For an Alex turn, the spine performs this order:

1. Preserve the user's exact message in `VerbatimVault`.
2. Compile vessel context from evidence that existed before this turn.
3. Record the current message as an uncertain observation referencing the
   immutable source.
4. Run Alex/Jeremy analysis.
5. Build FCP1 with the vessel context and its deterministic hash.
6. Dispatch to the selected provider and restore Alex's voice.
7. Record the encounter and receipt.
8. Promote only separately detected, explicit user instructions into confirmed
   vessel claims.

The current message cannot retrieve itself as established memory.

## Evidence model

Observations and claims are different records.

An observation records what occurred, including:

- actor and subject;
- exact-source reference and hash;
- room and session;
- literal, uncertain, joking, sarcastic, quoted, fictional, or hypothetical
  interpretation;
- private, relationship-private, room-scoped, or public visibility.

A claim records a possible reusable fact, preference, boundary, workflow,
identity instruction, or shared-history statement. It also records confidence,
status, salience, proactive permission, scope, sensitivity, and evidence links.

One ordinary anecdote remains tentative and is not retrieved. Two independent
literal supports can corroborate a claim. Three can confirm it. An explicit
confirmation can confirm it directly. Repeating the same source cannot
manufacture independent support. Jokes and sarcasm carry deliberately low
evidentiary weight.

Rejected claims cannot silently reactivate. Corrections are separate,
attributable records and support these actions:

- reject;
- confirm;
- prohibit proactive use;
- allow proactive use;
- replace;
- narrow.

## Relevance and the “softball problem”

Confirmed memory is not dumped into every prompt.

Retrieval requires:

- a permitted status;
- proactive-use permission;
- visibility permission;
- matching project, session, or room scope when scoped;
- lexical relevance to the current message.

Global boundaries, identity rules, workflow rules, and accessibility rules are
eligible without topical overlap because they govern the interaction itself.
Topical preferences and shared-history claims must match the current subject.

The compatibility `RelationshipEngine` now follows the same turn-time
principle: topical preferences and shared history must be relevant, while
response-style preferences, boundaries, workflow rules, and identity
instructions can apply globally.

## Private PubPartner and shared PubCast rooms

Turn context has an explicit audience classification:

- `private`
- `shared`
- `public`

`phone`, `pubpartner`, `private`, and `dressing_room` default to private.
Other PubCast rooms default to shared unless the caller supplies an explicit
audience in the task block.

Private relationship claims and observations are withheld from shared/public
contexts. Private relationship state is also withheld. Statements observed in
a shared room are stored as room-scoped evidence so they can be used in that
room without becoming private, globally reusable relationship memory.

The compatibility relationship guidance store is not injected into shared
turns because its legacy schema has no reliable visibility field.

## FCP1 integration

FCP1 has a `vessel` block containing:

- vessel, friend, user, project, session, room, audience, and budget identity;
- bounded identity data;
- relevant claims and observations;
- permitted relationship context;
- behavior rules;
- rendered provider-neutral prompt text;
- a deterministic SHA-256 context hash.

The turn result and live receipt expose the context hash and counts, allowing a
response to be traced to the exact compiled identity/memory brief without
placing all vessel contents into the receipt.

Small/offline providers receive the `small` context budget. Cloud providers
receive the `medium` budget. The compiler also supports a larger profile.

## Operational API

Authenticated PubPartner routes include:

- `GET /api/pubpartner/vessel`
- `GET /api/pubpartner/vessel/memory/claims`
- `POST /api/pubpartner/vessel/memory/claims/{claim_id}/corrections`

Claim inspection is bound to the authenticated/scoped user. A caller cannot
inspect or correct a different user's claim by supplying another user ID.

## Command-line operations

Create:

```bash
python -m modules.pubpartner_vessel create alex.pubpartner \
  --friend-id alex --display-name Alex
```

Verify:

```bash
python -m modules.pubpartner_vessel verify alex.pubpartner
```

Inspect manifest and identity:

```bash
python -m modules.pubpartner_vessel inspect alex.pubpartner
```

Create a transaction-consistent, validated copy:

```bash
python -m modules.pubpartner_vessel backup \
  alex.pubpartner alex-backup.pubpartner
```

List one user's claims:

```bash
python -m modules.pubpartner_vessel claims alex.pubpartner \
  --subject owner --status confirmed
```

Reject a claim:

```bash
python -m modules.pubpartner_vessel correct alex.pubpartner CLAIM_ID \
  --action reject --reason "The owner says this was not true."
```

Commands return structured JSON and nonzero exit status on failure.

## Durability and recovery

Every write uses `BEGIN IMMEDIATE`, foreign-key enforcement, full synchronous
durability, a busy timeout, and SQLite DELETE journaling. The completed
authoritative state is one file.

Creation uses an exclusive filesystem claim, preventing two creators from
initializing the same path. Vessel mounts reject symlinks and hard-linked files.
Failed transactions roll back. Backup uses SQLite's online backup operation,
fsyncs the temporary file, atomically installs the destination, fsyncs the
directory, and validates the resulting copy. It never overwrites an existing
destination.

Each authoritative record has a canonical SHA-256 seal stored separately from
the record. Mount verification detects missing, orphaned, and mismatched seals.
Assets include their content digest and are covered by record sealing. The audit
ledger detects breaks and edits in the operation chain.

These in-file hashes detect corruption and uncoordinated logical modification.
They are not a substitute for an external trust anchor: an attacker with
permission to rewrite the complete SQLite file could rewrite records, seals,
and the unkeyed audit chain together. Authenticity against that attacker
requires a trusted owner key or Iteration Wallet signature outside the vessel's
self-asserted state.

## Verified behavior

The added automated coverage proves:

- create, reopen, read-only mount, and exclusive creation;
- symlink and hard-link refusal;
- logical record, asset, audit, and missing-seal tamper detection;
- concurrent write serialization;
- transaction rollback;
- future-schema refusal without mutation;
- consistent, non-overwriting backup;
- deterministic bounded context compilation;
- evidence independence and promotion thresholds;
- low trust for jokes and sarcasm;
- correction and rejected-claim behavior;
- topical relevance and global-boundary behavior;
- private, room, project, session, and audience isolation;
- Alex default mounting and non-Alex isolation;
- explicit lesson ingestion through a real mock-provider turn;
- authenticated HTTP inspection and correction.

The complete repository test run for this checkpoint is:

`163 passed, 3 skipped`

The skipped tests are pre-existing environment/feature skips reported by the
suite; they were not converted into passes or suppressed.
