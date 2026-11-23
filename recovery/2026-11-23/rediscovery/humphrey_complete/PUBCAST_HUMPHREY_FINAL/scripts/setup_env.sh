#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${1:-python3}"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PYTHON=".venv/bin/python"

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements/dev.txt

echo "Virtual environment ready. Activate it with: source .venv/bin/activate"
