# Runtime Import Graph

## Canonical Lightweight Runtime

```text
run_pubpartner.py
  -> modules.pubpartner_preflight
  -> uvicorn("pubpartner_app:app")

pubpartner_app.py
  -> auth + auth_routes + userdb
  -> pubpartner_routes
      -> PubPartnerSpine
      -> provider boundary
      -> receipts/verbatim/session/relationship stores
  -> AlexCore + alex_routes
  -> AlexJeremyBridge
      -> Alex advisory
      -> Jeremy/context advisory
      -> authority reviewer callback
  -> PubManagerAuthorityStore
      -> PubManagerDecisionEngine
      -> BlackBox logger
      -> one-use authority persistence
  -> GovernanceEngine + governance_routes
      -> server-loaded authority validation
      -> bounded execution
  -> optional CricketKeeper
  -> optional BYOKManager
```

## Deliberately Separate Heavy Runtime

```text
main.py
  -> all of the above families plus
  -> Room Conductor
  -> Bubble Stack
  -> e-PETE/runtime bridges
  -> voxel/Rust renderer
  -> camera/recording/studio control
  -> choreography/avatar systems
```

The light app does not import or start heavy studio devices. The full host remains available for deliberate studio integration and regression work.
