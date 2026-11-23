# Test Results Summary

## Canonical RC7

| Validation | Result |
|---|---|
| Compile all production/test Python | PASS |
| JavaScript syntax | PASS |
| Full pytest | **132 passed, 3 skipped** |
| Fresh preflight | **Overall OK** |
| Local friend-loop smoke | PASS |
| Authenticated restart/continuity | PASS |
| Real control-plane authority probe | PASS |
| Dynamic route registration | 90 routes; 0 duplicate method/path pairs |
| Path-with-spaces preflight | PASS |

The three skips are live-Ollama tests. They were not counted as passes.

## Donor Validation

| Donor | Result | Canonical decision |
|---|---|---|
| Alex Prime v0.10 | 55 passed | Reference; not duplicated into active runtime |
| Alex adaptive companion | 4 passed | Reference |
| Pubcast AI Local | 215 passed | Reference; overlapping alternate runtime |
| Jeremy Hardened Beta | 21 passed, 1 failed | Rejected as canonical |

## Raw Evidence

See `docs/reconciliation/raw_test_output/`, especially:

- `RC7_POST_CONTROL_PLANE_FULL_PYTEST.txt`
- `RC7_FINAL_PREFLIGHT.txt`
- `RC7_FINAL_LOCAL_SMOKE.txt`
- `RC7_FINAL_RESTART_PROBE.txt`
- `RC7_FINAL_CONTROL_PLANE_PROBE.txt`
- donor-specific pytest outputs
