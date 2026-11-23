# Scientific Claim Evidence Layer

This revision makes supporting evidence, replication, credible dissent, null findings, and methodological criticism first-class properties of a scientific proposition.

## Core rule

A scientific source is not a vote. Each source is attached to a proposition with an explicit relationship:

- `support` — evidence favoring the proposition.
- `replication` — independently obtained evidence supporting the same proposition.
- `dissent` — professionally credible evidence challenging the proposition.
- `null` — evidence that does not reproduce the expected effect.
- `methodological_critique` — a credible challenge to measurement, design, construct validity, generalizability, or inference.

## Independence

`independent_group` is mandatory for meaningful replication accounting. Two papers using the same cohort or evidence base must not silently count as two independent confirmations.

## Dissent

A dissenting source is retained when its source is professionally credible and directly bears on the proposition. Dissent reduces operational readiness; it is not deleted because it is a minority position.

## Unknown sources

A source ID that is not in PEQ's scientific registry is recorded as unresolved and contributes no evidence weight.

## Important limitation

The current layer is an evidence-base assessor, not an empirical meta-analysis engine. It does not yet calculate formal pooled effect sizes, confidence intervals, publication bias, or GRADE-style certainty. Those are future research-infrastructure tasks.
