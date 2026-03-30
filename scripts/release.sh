#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/infra/compose/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/infra/compose/docker-compose.prod.yml}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"

usage() {
  cat <<'EOF'
Usage: ./scripts/release.sh [--migrate]

Options:
  --migrate   Apply database migrations during release
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --migrate)
      RUN_MIGRATIONS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Create it from infra/compose/.env.prod.example first."
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

echo "[1/5] Build application images"
compose build frontend api worker

echo "[2/5] Start stateful infrastructure"
compose up -d postgres redis temporal temporal-ui rustfs

echo "[3/5] Run one-shot init jobs"
compose up -d temporal-namespace-init rustfs-init

if [[ "$RUN_MIGRATIONS" == "true" ]]; then
  echo "[4/5] Apply database migrations"
  compose run --rm api alembic upgrade head
else
  echo "[4/5] Skip database migrations"
fi

echo "[5/5] Start gateway and application services"
compose up -d --remove-orphans api worker frontend gateway

echo
echo "Release completed. Current service status:"
compose ps
