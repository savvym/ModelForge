#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
UV_BIN="${UV:-uv}"

cleanup() {
  local exit_code="${1:-$?}"

  trap - EXIT INT TERM

  if [[ -n "${WORKER_PID:-}" ]]; then
    kill "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
  fi

  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi

  exit "$exit_code"
}

trap 'cleanup $?' EXIT
trap 'cleanup 130' INT TERM

cd "$BACKEND_DIR"

"$UV_BIN" run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

"$UV_BIN" run python -m apps.worker.dev &
WORKER_PID=$!

while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID"
    exit $?
  fi

  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    wait "$WORKER_PID"
    exit $?
  fi

  sleep 1
done
