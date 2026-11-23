# Startup and Diagnostics

Canonical launcher: `run_pubpartner.py`

```bash
python run_pubpartner.py --preflight
python run_pubpartner.py
```

Options:

```text
--host 127.0.0.1    local interface; default and recommended
--port 8000         local port
--data-dir PATH     alternate user-data location
--no-browser        do not open a browser automatically
--preflight         diagnose and exit
--allow-network     explicitly permit a non-loopback bind
--unsafe-no-auth    isolated development only; disable authentication
```

The launcher creates `data/pubpartner/secure/jwt_secret.txt` on first run. That file is runtime data and is deliberately absent from release archives.

First-run account setup happens in the browser. No default owner password is shipped.

Preflight report: `data/pubpartner/preflight_latest.json`

Windows launcher log: `pubpartner_windows_launcher.log`
