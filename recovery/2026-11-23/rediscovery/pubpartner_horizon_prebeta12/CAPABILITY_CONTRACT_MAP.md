# Capability Contract Map

| Capability | Canonical implementation | Main callers / route | Tests / evidence | State |
|---|---|---|---|---|
| Production launcher | `run_pubpartner.py`; Windows wrappers | starts `pubpartner_app:app` | preflight, restart and control-plane probes | Working |
| FastAPI default | `pubpartner_app.py` | local port, `/pubpartner` | 90 live routes, no duplicate pairs | Working |
| Optional full host | `main.py` | deliberate full PubCast boot | v5.5/canonical wiring regressions | Retained, not default |
| Authentication | `auth.py`, `auth_routes.py`, `userdb.py` | `/api/auth/*` | auth productization + restart | Working |
| First owner | `userdb.create_owner_if_not_exists`; setup route | `/api/auth/setup` | real-process probe | Working |
| PubPartner turn flow | `pubpartner_core.py`, `pubpartner_routes.py` | `/api/pubpartner/turns/live` | live-loop tests and smoke | Working |
| Provider selection | `pubpartner_provider.py` | turn request provider config | provider-neutralizer tests | Working |
| Provider neutralization | `provider_neutralizer.py` | before friend-identity finalization | RC6 tests | Working |
| OpenAI-compatible providers | `openai_compatible_provider.py` | provider registry | structural and focused tests | Optional; key/service dependent |
| Ollama | `ollama_provider.py` | provider registry | live tests skipped without service | Optional / unverified live here |
| Session primer/guidance | guidance/profile modules | turn assembly | live-loop and guidance tests | Working |
| Friend identity | Alex/profile/voice pipeline | final response shaping | Alex foundation tests | Working, still prelaunch quality |
| Alex analysis | `alex_core.py`, `alex_routes.py` | bridge/provider path | Alex foundation and bridge tests | Working |
| Jeremy context | `jeremy_cricket.py` through configured spine | session context | bridge and continuity tests | Working with visible fallback |
| Alex/Jeremy bridge | `alex_jeremy_bridge.py` | friend turn + authority advisory | contract tests | Working |
| Pub Manager requests | `pub_manager_authority.py` | `/api/pubmanager/authority/requests` | 20 focused + adversarial tests | Working |
| Deterministic policy | `pub_manager_decision.py` | reviewer callback | decision-engine tests | Working |
| Human decision | Pub Manager authority/control routers | authenticated decision endpoints | focused tests | Working |
| Authority validation | authority store + bridge | Governance routes | mismatch/expiry/replay/concurrency tests | Working |
| Governance execution | `governance.py`, `governance_routes.py` | mute/freeze/etc. | real control-plane probe | Working for supported actions |
| BlackBox audit | dressing-room logger + persisted authority records | request/consume path | fail-closed tests | Working |
| Exact source persistence | source/verbatim/receipt stores | PubPartner APIs | smoke + restart | Working |
| Relationship persistence | `pubpartner_relationship.py` | relationship APIs | relationship engine tests | Working |
| Room Conductor | `room_conductor.py` | full `main.py` | canonical wiring tests | Working in full host; off by default |
| Bubble Stack | `bubble_stack.py`, `bubble_routes.py`, adapter modules | full `main.py` | finalized PubCast regressions | Working in full host; off by default |
| e-PETE | `pete_enhanced.py`, routes | full `main.py` | activation tests | Degraded fallback possible |
| Camera | camera modules | full `main.py` | regression tests | Retained; hardware not exercised |
| Recording | recording modules | full `main.py` | regression tests | Retained; live capture not exercised |
| Avatar / choreography | avatar and choreography modules | full `main.py` | integration regressions | Retained / partial productization |
| Voxel renderer | `pubcast_voxel_integration.py`, `bin/ws_renderer` | full `main.py` | bridge tests | Binary retained; live renderer path may degrade |
| Windows launcher | `.bat` + `.ps1` | calls project Python/venv launcher | static audit + path-with-spaces preflight | Native Windows execution not verified here |
| Preflight | `modules/pubpartner_preflight.py` | `run_pubpartner.py --preflight` | fresh final run | Working |
| Release sanitation | `scripts/sanitize_release.py` | release copy only | hygiene tests | Working after reconciliation repair |
