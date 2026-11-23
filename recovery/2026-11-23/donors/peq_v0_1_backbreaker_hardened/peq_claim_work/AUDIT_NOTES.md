# CRE-EQ v0.1 Prototype — Self-Audit

## Corrections made after adversarial review

1. **Repeated identical runs were not independent.** The original best-of-three implementation treated repeated executions of the same deterministic engine as replication. It now requires distinct `method_id` values before declaring a majority validated; otherwise it reports `majority_but_not_independent`.

2. **The emotion vocabulary was incomplete.** Direct reports such as `anger`, `happiness`, and `grief` were not all represented cleanly. Explicit state aliases and distinct anger/grief states were added.

3. **Direct-report evidence was underweighted.** A user statement is now materially stronger evidence than weak behavioral heuristics, but the resulting confidence is still capped and explicitly labeled uncalibrated.

4. **Confidence looked too much like probability.** The output now labels the confidence as `uncalibrated_assessed_confidence`. It is a ranking heuristic, not a statistically calibrated probability.

5. **The working-state store was not actually persistent.** It is now an atomic JSON-backed store when a path is supplied.

6. **Low-signal conversations could cause pointless test planning.** Ordinary neutral messages no longer trigger a manufactured discrimination test.

7. **Word matching could false-match substrings.** Single-word lexical signals now use word boundaries; phrases still use literal phrase matching.

## Remaining limitations

- The current affective hypothesis model is intentionally deterministic and heuristic. It is a logic-layer prototype, not a scientifically validated emotion classifier.
- Multimodal feature extraction is not implemented here; audio/video fields are explicit feature interfaces only.
- `method_id` is a declared independence boundary, not proof that two methods are genuinely independent. A production implementation needs a method registry and independence audit.
- Evidence `strength` is metadata and is not yet a complete probabilistic measurement model.
- The current confidence score is not calibrated against a labeled corpus. Calibration and validation belong to a later empirical layer.
- The prototype does not access BlackBox and does not replace PubPartner identity, memory, authority, session, or performance systems.

## What this prototype is meant to prove

The prototype demonstrates the control flow and epistemic bookkeeping: observation → hypothesis → discrimination → determination → response appraisal → audit trace. It is deliberately not pretending that the heuristic emotion rules are already scientifically validated.


## Retrieval boundary

Scientific retrieval is intentionally non-authoritative in the current PEQ v0.1 revision: retrieved literature is preserved as provenance-aware context/navigation and is not silently converted into state evidence merely because it matched a query. A future evidence-adapter layer may promote specific validated claims into explicit EvidenceContribution objects.
