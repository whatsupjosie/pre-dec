# PEQ v0.1 Focused Correctness Review

## Fixes made in this pass

1. Direct self-report evidence was corrected so an explicit report for one state supports that state and weakens alternatives instead of acting as generic positive evidence for every state.
2. Executed CRE discrimination-test results now enter the PEQ evidence ledger with state-specific support/weakening directions. Test reliability alone no longer stands in for the actual test result.
3. PEQ Response now computes a separate response-appraisal confidence from response-candidate spread, state confidence, and stakes. It no longer simply reuses the state confidence as the response confidence.
4. PEQ Response candidate ranking now considers interaction goal, relationship context, stakes, state posterior, and reversible alternatives rather than assigning a fixed 1.0 score to the state-mapped response.

## Verification

- Pytest: 44 passed
- Python compileall: passed
- Runtime probes: empty text, NaN, infinity, and unknown explicit state completed without exceptions or non-finite output.
- BlackBox access: none

## Remaining limitations intentionally not expanded in this pass

- Probability outputs remain model-derived operational confidence, not empirically calibrated probabilities.
- Population/general-knowledge records are still primarily evidence provenance and prior-contract scaffolding; they are not yet a fitted population likelihood model.
- Response candidate generation remains bounded to a curated response vocabulary; it is not yet a learned policy optimizer.
- No third-party static-analysis tool was available in the environment (ruff/pyflakes not installed).
