#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif python3 -c "import uvicorn" >/dev/null 2>&1; then
    # Railway/Railpack installs application dependencies before the start command.
    PYTHON="python3"
else
    echo "Creating local virtual environment and installing dependencies..."
    python3 -m venv "$PROJECT_ROOT/.venv"
    "$PROJECT_ROOT/.venv/bin/python" -m pip install --upgrade pip
    "$PROJECT_ROOT/.venv/bin/python" -m pip install -r "$PROJECT_ROOT/requirements.txt"
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
fi

cd "$PROJECT_ROOT"
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
