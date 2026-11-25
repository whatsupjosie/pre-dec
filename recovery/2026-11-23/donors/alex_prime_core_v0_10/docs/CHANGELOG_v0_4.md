# Alex Prime Core v0.4 Changelog

## Added

- Evidence recorder contract.
- Local tamper-evident JSONL evidence recorder.
- BlackBox adapter for Iteration Wallet evidence recorders that expose `write_event()` and `verify_chain()`.
- `AlexRuntime.inspect_and_record()` for atomic inspection plus evidence persistence.
- Personal Alex support-state engine adapted from the uploaded Alex companion material.
- Co-Lab brief builder for Jeremy/Alex/linked-model scoped context packets.
- Evidence, personal support, and Co-Lab brief demos.
- Six additional unit tests.

## Hardened

- Evidence export now verifies hash-chain integrity.
- Tampering with stored evidence is detected by test.
- Personal support is context-locked to `personal_alex`.
- Co-Lab briefs scope memory differently for non-core AI participants.

## Current test status

`24/24` unit tests pass.
