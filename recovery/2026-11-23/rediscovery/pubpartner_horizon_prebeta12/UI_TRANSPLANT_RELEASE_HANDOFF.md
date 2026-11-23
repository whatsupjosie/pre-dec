# PubPartner UI Transplant Release Handoff

## Build

Version: `0.1.0-prebeta.10+wallet-ui-transplant.20260728`

This is a verified pre-beta UI candidate, not a Prime, complete, production-ready, or market-ready build.

## Boot

Windows: run `RUN_PUBPARTNER_WINDOWS.bat`.

PowerShell: `powershell -ExecutionPolicy Bypass -File .\run_pubpartner_windows.ps1`

macOS/Linux: `./run_pubpartner_mac_linux.sh`

Direct: `python run_pubpartner.py`

Then open the printed local `/pubpartner` address.

## Verification

- Protected input hashes matched the handoff manifest.
- Baseline: Python compile pass; JavaScript syntax pass; 176 passed, 3 skipped.
- Final: Python compile pass; JavaScript syntax pass; 180 passed, 3 skipped.
- Real lightweight server boot: pass; `/pubpartner` returned HTTP 200.
- Chromium command/UI smoke: pass; 10 trays, 8 menus, 34 command controls, correct Media and Memory routing, theme switch, versioned save, and corrupt-layout recovery; zero console errors and zero page errors.
- The real server and browser smoke used disposable data outside the build tree.

## Authority boundaries

The Frozen Iteration Wallet remained unchanged. No Wallet custody, passkey, LabCopy, Candidate/Prime promotion, Oubliette, identity, or storage namespace behavior was imported. The Alex affect Prime remained unchanged and was not merged by file replacement.

## Runtime-state exclusion

No `users.db`, `master.key`, provider key, owner credential, generated conversation, or browser-test data is included in this package.
DISK_END
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda         63G   21G   39G  35% /

RELEVANT_PROCESSES_END
  264 tini            tini -- /opt/pyvenv-python-tool/bin/python -m uvicorn --host 0.0.0.0 --port 8080 --log-config /opt/python-tool/uvicorn_logging.config jupyter_server.app:app
  279 python          /opt/pyvenv-python-tool/bin/python -m uvicorn --host 0.0.0.0 --port 8080 --log-config /opt/python-tool/uvicorn_logging.config jupyter_server.app:app
