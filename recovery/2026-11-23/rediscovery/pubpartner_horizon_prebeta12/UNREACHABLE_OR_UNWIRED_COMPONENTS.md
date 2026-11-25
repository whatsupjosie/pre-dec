# Unreachable, Optional, or Not Default-Booted Components

## Not Default-Booted by Design

- Camera and advanced camera paths
- Recording and live recording pipeline
- Voxel/Rust renderer
- e-PETE studio coordination
- Bubble Stack live room routes
- Avatar performer and choreography production paths
- Room Conductor full production context
- Studio websocket/control room paths

These remain available through `main.py`, not through the canonical lightweight launcher.

## Present but Incomplete or Environment-Dependent

- Live Ollama provider: requires a running Ollama service and installed model.
- OpenAI/OpenAI-compatible provider: requires optional library, endpoint and user key.
- Camera/microphone/recording hardware: not exercised in this sandbox.
- Native Windows process behavior: wrappers were inspected and path-with-spaces preflight passed, but no Windows kernel was available.
- Several full-studio files still contain explicit future integration markers. They are not claimed complete merely because they compile.

## Donors Not Activated

- Alex Prime v0.10: independently clean at 55 tests, but not merged as a second active identity/memory engine.
- Alex adaptive companion: independently clean at 4 tests; preserved as reference.
- Pubcast AI Local: independently clean at 215 tests; overlapping alternate orchestration line, preserved as reference.
- Jeremy Hardened Beta: 21 tests passed and 1 behavioral test failed under compatible asyncio mode; not canonical.
- Loose legacy `test_pub_manager.py`: targets an older `modules.pub_manager` contract and a different no-history policy; useful requirements were mapped into current adversarial tests rather than reviving a duplicate authority engine.
