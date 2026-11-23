# Changelog v0.9

## Added

- `alex_prime/identity_filter_bridge.py`
- `source_locked/identity_filter/identity_filter.py`
- `docs/IDENTITY_FILTER_INTEGRATION_v0_9.md`
- `examples/demo_identity_filter.py`

## Runtime additions

- `AlexRuntime.build_identity_upstream_packet(...)`
- `AlexRuntime.filter_identity_response(...)`

## Tests

Added five identity-filter regression tests. Full suite result: 53/53 passing.

## Main correction

v0.9 stops treating identity filtering as an external sidecar idea. It is now part of the Alex Prime runtime boundary.

External engines may provide content. They do not get to become Alex by claiming her voice.
