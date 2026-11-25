# UI Transplant Test Results

Commands executed:

```text
python -m compileall -q .
node --check static/pubpartner.js
pytest -q
python browser_smoke.py
python run_pubpartner.py --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/pubpartner
```

Final results are recorded in the release handoff. Tests use a separate disposable data directory; generated owner/runtime state is excluded from the packaged build.
