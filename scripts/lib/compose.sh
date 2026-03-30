#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "${ENV_FILE:-}" ]]; then
  if [[ -f "$ROOT_DIR/infra/compose/.env.prod" ]]; then
    ENV_FILE="$ROOT_DIR/infra/compose/.env.prod"
  else
    ENV_FILE="$ROOT_DIR/infra/compose/.env.example"
  fi
fi

if [[ -z "${COMPOSE_FILE:-}" ]]; then
  if [[ "$ENV_FILE" == *".env.prod"* ]]; then
    COMPOSE_FILE="$ROOT_DIR/infra/compose/docker-compose.prod.yml"
  else
    COMPOSE_FILE="$ROOT_DIR/infra/compose/docker-compose.dev.yml"
  fi
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing compose file: $COMPOSE_FILE" >&2
  exit 1
fi

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}
