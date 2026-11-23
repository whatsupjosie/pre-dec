# PEQ Back-Breaker Test — 2026-08-14

## Purpose

This pass deliberately attacked PEQ's highest-risk failure mode: false certainty that looks reasonable because the individual signals are plausible.

## Adversarial classes

- correlated multimodal evidence presented as if independent;
- repeated lexical evidence;
- direct self-report versus contradictory evidence;
- symmetric emotional conflict;
- adverse context against seductive positive wording;
- empty/no-signal input;
- person-specific and population modifiers;
- executed discriminating truth tests;
- mixed truth-test outcomes;
- high-stakes response modulation;
- paraphrase stability;
- irrelevant-context invariance;
- non-diagnostic clinical-pattern lock-in;
- scientific dissent versus apparent consensus.

## Defects found and corrected

1. **Correlated evidence inflation:** contributions had no correlation grouping and could stack as independent evidence. Contributions now have correlation groups and per-group directional caps.
2. **False neutralization:** low-margin evidence was being collapsed to neutral even when real evidence existed. Neutral fallback now applies only to genuinely evidence-free cases.
3. **Evidence-presence bug:** the informative-evidence check looked only at generic `direction`, missing `state_directions`. It now evaluates directional contribution across the actual state set.
4. **Profile evidence was bookkeeping-only:** recognized person-specific emotional baseline facts now contribute bounded directional evidence.
5. **Population baseline was bookkeeping-only:** explicit caller-supplied population baseline context now contributes bounded directional evidence while retaining low reliability.
6. **Seductive positive wording could survive adverse context:** negative situational context now carries stronger state-specific counter-evidence.
7. **High-confidence response selection:** response candidate scoring was relying too heavily on raw posterior rather than the PEQ operational confidence. High-confidence supported states now select the intended primary response rather than needless clarification.
8. **Scientific and clinical evidence remain non-diagnostic:** retrieval and clinical pattern matching do not automatically become conclusions or actions.

## Verification

- Full suite: **76 passed**
- Back-breaker suite: **23 passed**
- Python compilation: passed
- Empty-input safety: passed
- Repeated lexical evidence: capped / non-ceiling
- Correlated multimodal evidence: capped / non-ceiling
- High-confidence supported direct report: 98.5% operational ceiling
- High-stakes response: intensity reduced while response remains decisive when state confidence is high
- Contested evidence: no full-strength commitment

## Remaining model-level limitation

The numerical model is still an explicitly weighted, uncalibrated operational model. Its percentages are not yet empirically calibrated probabilities. Correlation grouping is conservative and hand-defined; a future learned dependency model can improve this without changing the public PEQ contracts.
