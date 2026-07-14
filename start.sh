#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment if it exists
if [ -d "$ROOT_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
  export MOMENTWEAVER_PYTHON="${MOMENTWEAVER_PYTHON:-$ROOT_DIR/.venv/bin/python3}"
fi

PYTHON_BIN="${MOMENTWEAVER_PYTHON:-python3}"

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  echo "Set MOMENTWEAVER_PYTHON=/path/to/python if your system Python uses another name." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, PIL" >/dev/null 2>&1; then
  echo "Missing Python dependencies in the current system Python environment." >&2
  echo "Install them with:" >&2
  echo "  $PYTHON_BIN -m pip install -r requirements.txt" >&2
  exit 1
fi

exec "$ROOT_DIR/scripts/dev.sh"
