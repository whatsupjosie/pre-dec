# Current Runtime Truth

**Canonical version:** `0.1.0-prebeta.8+vessel-foundation.20260728`

## Default Boot Path

```text
RUN_PUBPARTNER_WINDOWS.bat / run_pubpartner_windows.ps1
    -> run_pubpartner.py
    -> preflight + persistent local security settings
    -> uvicorn pubpartner_app:app
    -> lifespan startup
       -> auth/user database
       -> GovernanceEngine
       -> PubManagerAuthorityStore + deterministic policy
       -> AlexJeremyBridge
       -> AlexCore
       -> optional CricketKeeper continuity store
       -> mounted Alex PubPartner vessel
       -> PubPartnerSpine + provider-neutralized friend loop
       -> object-bound Alex/Pub Manager/Governance routers
```

`pubpartner_app.py` is intentionally lighter than the full PubCast server, but it is no longer governance-light. Its live health response identifies the control plane as `alex_jeremy_pub_manager_governance`.

## Active by Default

| Capability | Active implementation | Runtime truth |
|---|---|---|
| Local auth | `modules/auth.py`, `auth_routes.py`, `userdb.py` | Active; first owner setup; persistent signed tokens |
| PubPartner spine | `modules/pubpartner_core.py`, `pubpartner_routes.py` | Active |
| PubPartner vessel | `modules/pubpartner_vessel/` | Active for Alex; single-file identity, scoped memory, context, integrity, backup, correction |
| Provider boundary | `pubpartner_provider.py`, `provider_neutralizer.py`, provider capability modules | Active; mock works without cloud keys |
| Exact source + receipts | `pubpartner_receipts.py`, persisted source/session stores | Active; restart-tested |
| Relationship continuity | `pubpartner_relationship.py`, profiles/guidance layers | Active; covered by tests |
| Alex | `alex_core.py`, `alex_routes.py` | Active |
| Jeremy bridge/continuity | `alex_jeremy_bridge.py`, optional `jeremy_cricket.py` | Active bridge; Cricket degrades visibly if unavailable |
| Pub Manager | `pub_manager_authority.py`, `pub_manager_decision.py` | Active deterministic authority and human review |
| Governance | `governance.py`, `governance_routes.py` | Active execution path for eligible authority grants |
| Black-box authority record | dressing-room BlackBox logger + authority store | Required for executable AI-origin authority paths; fail-closed behavior tested |
| BYOK | `byok_manager.py`, configured into friend spine | Optional; local mock/offline path remains usable |
| UI | `static/pubpartner.*` | Active at `/pubpartner` |

## Retained but Not Started by Default

The full `main.py` application retains Bubble Stack, e-PETE, voxel/Rust renderer, camera, recording, choreography, avatars, studio control, and Room Conductor integration. Those systems are not secretly started by the canonical lightweight launcher. This avoids hidden processes and keeps the friend application usable without studio hardware.

## Authority Truth

- `ban_user` and other permanent/punitive Class D actions remain human-required, regardless of critical urgency or AI advisory text.
- Eligible reversible containment can be automatically approved only under deterministic evidence policy and bounded duration.
- A client cannot supply a trusted authority packet.
- Grants are bound to action, target, user packet, and session; they expire and are consumed once.
- Governance replay after consumption is rejected.
- Failure to record required BlackBox evidence blocks executable approval.

## Release Claim

This is a verified private prelaunch candidate. It is not presented as publicly market-ready because native Windows execution, live external model services, installer/signing, broader accessibility, and production deployment security were not fully exercised in this Linux sandbox.
