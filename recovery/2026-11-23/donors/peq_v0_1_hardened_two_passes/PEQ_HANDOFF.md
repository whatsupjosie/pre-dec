# PEQ v0.1 — Formal Architecture Handoff

## What was built

PEQ (Probabilistic EQ) is now a formal, executable two-question system:

1. **PEQ State:** What emotional state is most probable?
2. **PEQ Response:** Given the assessed state, context, relationship, goal, stakes, and uncertainty, what response is most likely appropriate?

## Core implementation

### `peq/state.py`
Builds an evidence ledger across:

- general emotional knowledge;
- population baseline;
- individual baseline;
- situation/context;
- history;
- current observations;
- logical truth-test reliability.

Each evidence item can support one state while weakening another through `state_directions`.

### `peq/response.py`
Maintains a separate response-appraisal problem. It does not simply mirror the user's inferred emotion. Confidence and stakes modulate the behavioral intensity.

### `peq/system.py`
Orchestrates the two questions and emits an auditable result.

### `cre_eq/`
The existing Critical Reasoning Engine remains the truth-testing backplane. PEQ does not treat an emotion heuristic as truth. Suspicious or contradictory inputs can trigger reasoning tests, and their results become PEQ evidence.

## Confidence ceiling

Operational confidence is capped at **98.5%**. It is explicitly not a calibrated probability. A corroborated, high-reliability direct report can reach the ceiling; a contested report is deliberately held down until the contradiction is investigated.

## Verification

Current focused debugging revision: five-pass review completed; 44 tests pass, compilation passes, numerical fuzz probes pass, retrieval stress probes pass, and clean-checkout pytest execution is configured through pytest.ini.


- `python -m pytest -q` → **44 passed**
- `python -m py_compile cre_eq/*.py peq/*.py demo.py demo_peq.py` → PASS
- `python demo_peq.py` → PASS

## Architectural boundaries

PEQ is not a replacement for existing PubPartner identity, session, memory, authority, provider, or emotional-performance systems.

**BlackBox is outside the PEQ data boundary.**

The existing August 1 Alex EQ evidence implementation is the source-aligned precedent for competing hypotheses, direct/contrary evidence, explicit hypothesis-not-fact treatment, user-confirmed correction, temporary EQ evidence, ambiguity preservation, and BlackBox separation. fileciteturn22file5L508-L529

The donor audit explicitly identified the older EQ Suit's major weakness as collapsing raw signals into scalar state conclusions and failing to preserve user correction as a first-class epistemic event. fileciteturn22file13L979-L989

## What is intentionally not claimed

This version is an executable architecture and operational scoring model, not a scientifically validated human-emotion classifier. Calibration, empirical likelihood ratios, labeled evaluation data, multimodal feature extraction, and genuinely independent reasoning methods remain later engineering work.
