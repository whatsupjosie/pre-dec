# Canonical Boot Sequence

1. Windows wrapper or user calls `python run_pubpartner.py`.
2. Launcher resolves project root and data directory.
3. Launcher creates/reuses a persistent local JWT secret and enables authenticated local-owner mode.
4. Preflight verifies Python, writable storage, critical files, dependencies, port, CORS and auth configuration.
5. Uvicorn starts `pubpartner_app:app`.
6. Lifespan aligns `userdb` with the selected data directory and initializes tables.
7. Governance, Pub Manager authority store, Alex/Jeremy bridge, AlexCore and optional Jeremy Cricket are constructed.
8. PubPartner spine is configured with the bridge and continuity provider.
9. Object-bound Alex, Pub Manager and Governance routers are mounted before the first request is served.
10. UI is available at `/pubpartner`; first-run owner setup is required.
11. Shutdown closes the bridge and Jeremy store. The launcher does not intentionally leave a hidden server process.
