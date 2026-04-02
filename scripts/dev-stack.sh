#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_SCRIPT="$ROOT_DIR/scripts/dev-backend.sh"
FRONTEND_DIR="$ROOT_DIR/frontend"
PNPM_BIN="${PNPM:-pnpm}"

cleanup() {
  local exit_code="${1:-$?}"

  trap - EXIT INT TERM

  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi

  exit "$exit_code"
}

trap 'cleanup $?' EXIT
trap 'cleanup 130' INT TERM

"$BACKEND_SCRIPT" &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  "$PNPM_BIN" install
  "$PNPM_BIN" dev
) &
FRONTEND_PID=$!

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    exit $?
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID"
    exit $?
  fi

  sleep 1
done
