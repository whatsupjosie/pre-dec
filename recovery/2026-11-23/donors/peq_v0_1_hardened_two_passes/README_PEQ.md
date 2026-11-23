# PEQ — Probabilistic EQ System

PEQ is the formal emotional-inference layer built around the source-backed PubPartner architecture.

## Two questions, explicitly separated

### PEQ State

> What emotional state is most probable given the available evidence?

Inputs are kept in separate evidence domains:

1. General emotional knowledge
2. Population baseline
3. Individual baseline
4. Situation/context
5. Person-specific history
6. Current observations/statements
7. Truth-tested reliability of contested inputs

### PEQ Response

> Given that assessed state, the situation, the relationship, the goal, the stakes, and the uncertainty, what response is most likely to be appropriate?

The response engine does **not** mirror the user's emotion automatically.

## Confidence rule

Operational confidence is hard-capped at **98.5%**.

That is an operational ceiling, not a calibrated probability and not metaphysical certainty. The system must preserve the distinction between evidence, inference, and certainty.

## Bullshit / incongruity rule

A suspected lie, sarcasm, contradiction, or incongruity is **not a truth verdict**. It is a trigger for the existing critical-reasoning layer to investigate the proposition, assumptions, alternatives, and discriminating tests.

## Existing-system boundaries

PEQ does not replace PubPartner identity, memory, session, authority, provider, or emotional-performance systems. It is designed as an inference layer that consumes authorized observations and produces state/response appraisals.

PEQ does not access BlackBox.

## Current statistical status

The present scorer is an **operational probability-shaped heuristic**, not a scientifically calibrated statistical model. The public contract is deliberately designed so a future calibrated model can replace the scorer without changing the State/Response architecture.

## Clinical-pattern evidence registry

PEQ now contains a small, explicitly non-diagnostic clinical-pattern evidence registry.
It does **not** diagnose the subject. It stores working-pattern hypotheses and response principles drawn from authoritative clinical/public-health sources.

Current registry entries include:

- trauma-related stress-response pattern;
- suspiciousness / threat-interpretation pattern.

Each entry carries source provenance, scope, limitations, response principles, and contraindications. A pattern match is represented as `working_hypothesis` with `diagnosis="none"`.

### Current source families

- NIMH PTSD and psychosis educational material;
- VA/DoD PTSD clinical practice guideline;
- SAMHSA trauma-informed-care guidance;
- VA National Center for PTSD material on trauma reminders and conditional grounding;
- American Psychiatric Association schizophrenia practice-guideline material and supporting CBT-for-psychosis guidance.

The registry deliberately separates **pattern evidence** from **diagnosis** and **response strategy**. It also preserves source limitations so PEQ does not silently treat a clinical guideline or educational summary as a universal statistical law.


## Evidence retrieval

PEQ includes a provenance-aware evidence retriever over the curated scientific registry. It uses a pre-built token index for fast first-pass candidate selection, then ranks by query coverage, title match, source-type authority, and modest recency. It actively diversifies source families and returns both primary retrieved evidence and a secondary range so the system does not collapse literature into a single answer.

Retrieval is intentionally **not** a diagnostic classifier and does not automatically convert a retrieved paper, dataset, guideline, or intervention into a numerical emotional-state contribution. Retrieved records preserve claims, source provenance, limitations, and automation status for the reasoning layer to evaluate.

The retriever also reports uncovered query terms. An uncovered term means only that the current registry does not represent it; it is not evidence against the proposition. Working-pattern ranking returns multiple non-diagnostic hypotheses supported by the observed-sign vocabulary and does not pad the result with zero-match conditions.

## Operational-value filter

Every retrieved or newly evaluated piece of evidence is assessed for whether it can improve one or more of six operational dimensions:

1. **Interaction** — how the system should communicate or relate to the person.
2. **Assessment** — what the system should believe, measure, or investigate.
3. **Response** — what the system should do or express.
4. **Prediction** — what the system can predict about likely next states, behavior, or needs.
5. **Risk management** — which errors or unsafe responses should be avoided and how cautious the system should be.
6. **Test selection** — what next observation or discriminating test would most efficiently reduce uncertainty.

Information that improves none of these remains informational rather than driving behavior. This filter does not decide whether evidence is true; it decides whether established or retrieved evidence has an operational reason to matter to PEQ.

The retrieval layer exposes this six-way profile for the evidence bundle and for each retrieved item, and the PEQ audit records it separately from diagnosis or state inference.
