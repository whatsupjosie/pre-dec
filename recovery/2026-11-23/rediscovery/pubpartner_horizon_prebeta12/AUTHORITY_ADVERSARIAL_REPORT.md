# Authority Adversarial Report

## Verified Attacks and Outcomes

| Attempt | Required outcome | Observed |
|---|---|---|
| AI/provider advisory includes `approved: true` for ban | No self-approval | Ban remained `human_required` |
| Critical permanent ban with maximum evidence | Human review | `approved=false`, `human_required` |
| Critical bounded freeze with strong evidence | Minimum reversible containment allowed | `auto_approved`, 30-second request |
| Replay consumed freeze grant | Reject | HTTP 403 |
| Client supplies authority packet | Reject | Covered by bridge/governance contract tests |
| Grant target mismatch | Reject | Covered by reconciliation adversarial test |
| Grant action mismatch | Reject | Covered by reconciliation adversarial test |
| Grant session mismatch | Reject | Covered by reconciliation adversarial test |
| Expired grant | Reject | Covered by reconciliation adversarial test |
| Concurrent consumption | Exactly one consumer | Covered; one succeeds, others fail |
| BlackBox unavailable | Fail closed | Covered by Alex/Jeremy bridge tests |
| Duplicate incident signal | Do not create uncontrolled executable grants | Covered by authority store tests |
| Kick/ban under urgent pressure | No automatic permanent punishment | Covered |

## Real-Process Proof

The final probe started `run_pubpartner.py`, created an owner, queried policy, requested a permanent ban, requested a bounded freeze, executed the freeze through Governance, and replayed the same grant. The ban remained human-only; the first freeze executed; replay returned 403.

Raw output: `docs/reconciliation/raw_test_output/RC7_FINAL_CONTROL_PLANE_PROBE.txt`.
