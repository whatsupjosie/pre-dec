# CRE-EQ Prototype

A standalone, dependency-free prototype of the Critical Reasoning Emotional Intelligence logic layer.

## What this slice proves

- Raw text/typing/audio/vision inputs become **observations**, not emotional conclusions.
- Personal baselines produce explicit deviations.
- Multiple competing emotional hypotheses are maintained.
- Direct user self-report receives stronger evidentiary treatment than weak inference.
- A discrimination test can be planned and executed separately.
- The engine produces the requested **formal determination** and **interpretive assessment**.
- Response appraisal is separate from user-state inference: anger in the user does not imply anger as the companion response.
- Best-of-three replication is implemented, with disagreement preserved for root-cause analysis.
- A structured reasoning trace captures observations, assumptions, hypotheses, tests, results, and unresolved questions.
- A small JSON-serializable working-state store is included for context continuity.

## Deliberate boundaries

This package does not replace PubPartner identity, memory, session, BlackBox, authority, provider, or performance systems. Those should integrate around this core later.

The current multimodal inputs are feature interfaces only; camera/audio feature extraction is not fabricated here.

## Run

```bash
python -m pytest -q
python demo.py
```

## PEQ — Probabilistic EQ System

The new formal PEQ layer lives under `peq/` and answers two separate questions:

1. **PEQ State:** What emotional state is most probable?
2. **PEQ Response:** Given that state and the context, what response is most likely appropriate?

PEQ uses the existing `CriticalReasoningEngine` as its truth-testing backplane, keeps evidence domains distinct, supports per-state evidence directions, and caps operational confidence at 98.5%.

See `PEQ_ARCHITECTURE.md` and run `python demo_peq.py`.

## Scientific evidence expansion

This revision adds a provenance-aware scientific evidence registry covering population datasets, validated measurement instruments, peer-reviewed systematic reviews/meta-analyses, professional clinical frameworks, and evidence-backed intervention families. See `SCIENTIFIC_EVIDENCE_EXPANSION.md` and `RESEARCH_SOURCES.md`.
