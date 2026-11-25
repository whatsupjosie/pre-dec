# PEQ — Probabilistic EQ System

## Purpose

PEQ estimates latent emotional state and then separately estimates the most appropriate response.
It does not claim direct access to a person's internal emotion.

## Formal pipeline

```text
AUTHORIZED OBSERVATIONS
        |
        v
+---------------------------+
| CRITICAL REASONING /     |
| TRUTH-TESTING LAYER       |
|                           |
| claims -> assumptions ->   |
| competing explanations -> |
| discriminating tests ->   |
| supported/contested input  |
+-------------+-------------+
              |
              v
+---------------------------------------------+
| PEQ STATE                                  |
|                                             |
| General emotional knowledge                |
| + population baseline                       |
| + individual baseline                       |
| + situation                                |
| + history                                  |
| + current observations                      |
| + truth-test reliability                    |
| -> state-specific evidence weights          |
| -> probability-shaped posterior ranking     |
| -> operational confidence (max 98.5%)       |
+----------------------+----------------------+
                       |
                       v
+---------------------------------------------+
| PEQ RESPONSE                               |
|                                             |
| assessed state                             |
| + situation                                |
| + relationship                             |
| + interaction goal                         |
| + stakes / error cost                      |
| + confidence                               |
| -> competing response candidates            |
| -> recommended response                    |
| -> modulation / intensity                   |
+----------------------+----------------------+
                       |
                       v
EXISTING EMOTIONAL PERFORMANCE LAYER
                       |
                       v
                EXPRESSED RESPONSE
```

## Evidence model

An individual piece of evidence can support one state while weakening another. Therefore PEQ uses `state_directions`, not one universal `direction` value.

Example:

```text
High typing speed
    + excitement
    + anxiety
    + frustration
    - fatigue
```

This is a signal of arousal/activation, not a direct label of emotion.

## Confidence rule

Operational confidence is hard-capped at **98.5%**.

98.5% means overwhelming operational support under the current model. It does not mean absolute certainty and is not presently a statistically calibrated probability.

A high-quality direct report with no meaningful contradiction can therefore drive PEQ close to the ceiling. A direct report that triggers a meaningful incongruity/lie/sarcasm investigation must not receive that treatment until the contradiction is resolved.

## Truth / bullshit handling

A suspected lie, sarcasm, incongruity, contradiction, or other reliability failure is **not** itself a determination of falsity.

It triggers the Critical Reasoning layer:

```text
suspicion
  -> why is it suspicious?
  -> what proposition is actually being tested?
  -> what assumptions are involved?
  -> what competing explanations exist?
  -> what test best distinguishes them?
  -> what did the test actually show?
  -> rerun determination with the new evidence
```

## State vs Response

PEQ State answers:

> What emotional state is most probable?

PEQ Response answers:

> Given that state, what is the most appropriate response?

These are intentionally separate. A highly probable angry state may call for calm solidarity rather than anger.

## Response modulation

Confidence controls behavioral commitment:

```text
high confidence  -> full-strength response can be appropriate
moderate         -> restrained response
low / contested  -> conservative, reversible response
```

Stakes and the cost of a wrong response can increase restraint.

## Architecture boundaries

PEQ is an inference layer. It does not replace:

- PubPartner identity/authentication
- existing memory systems
- existing session infrastructure
- authority/policy systems
- provider/model dispatch
- Emotional Performance / prosody / animation
- BlackBox

**BlackBox access is prohibited.**

## Source alignment

This formal layer was built after the full available emotion-system review. In particular, the August 1 Alex EQ evidence run already established several principles that PEQ preserves: competing hypotheses, direct and contrary evidence, explicit hypothesis-not-fact status, user-confirmed corrections, temporary EQ evidence, preservation of ambiguity, and no BlackBox access. See the cited review material in the session handoff.

The older EQ Suit remains useful as a donor for signal extraction ideas, but its scalar state collapse is not treated as the PEQ truth model. The donor audit explicitly identifies that collapse and the absence of a correction path as major weaknesses.
