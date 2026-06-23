#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

HOST="${MOMENTWEAVER_HOST:-127.0.0.1}"
PORT="${MOMENTWEAVER_PORT:-8787}"
RELOAD="${MOMENTWEAVER_RELOAD:-0}"
PYTHON_BIN="${MOMENTWEAVER_PYTHON:-python3}"

export PYTHONPATH="$ROOT_DIR/backend:${PYTHONPATH:-}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  exit 1
fi

echo "Starting MomentWeaver with $PYTHON_BIN at http://$HOST:$PORT"

if [ "$RELOAD" = "1" ]; then
  exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
