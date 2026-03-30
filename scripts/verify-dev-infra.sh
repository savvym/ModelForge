#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/infra/compose/docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/infra/compose/.env.example}"
DEV_GATEWAY_CONTAINER="${DEV_GATEWAY_CONTAINER:-nta-dev-gateway}"
DEV_GATEWAY_URL="${DEV_GATEWAY_URL:-http://127.0.0.1:8081}"
S3_PROBE_URL="${S3_PROBE_URL:-$DEV_GATEWAY_URL/nta-default}"
ATTEMPTS="${DEV_GATEWAY_VERIFY_ATTEMPTS:-30}"

echo "[verify] Waiting for $DEV_GATEWAY_CONTAINER to load its nginx config"
for _ in $(seq 1 "$ATTEMPTS"); do
  if docker exec "$DEV_GATEWAY_CONTAINER" nginx -t >/tmp/nta-gateway-nginx-test.log 2>&1; then
    break
  fi

  sleep 1
done

if ! docker exec "$DEV_GATEWAY_CONTAINER" nginx -t >/tmp/nta-gateway-nginx-test.log 2>&1; then
  cat /tmp/nta-gateway-nginx-test.log >&2 || true
  echo "Dev gateway failed nginx config validation." >&2
  exit 1
fi

expected_server_header="$(
  docker exec "$DEV_GATEWAY_CONTAINER" nginx -v 2>&1 | sed 's/^nginx version: //'
)"

echo "[verify] Probing $S3_PROBE_URL through the dev gateway"
for _ in $(seq 1 "$ATTEMPTS"); do
  response_headers="$(curl -sS -D - -o /dev/null "$S3_PROBE_URL" --max-time 5 || true)"

  if [[ "$response_headers" == *"Server: $expected_server_header"* ]] \
    && [[ "$response_headers" == *"Content-Type: application/xml"* ]]; then
    echo "$response_headers" | sed -n '1,8p'
    echo
    echo "Dev infra is ready: :8081 is served by $DEV_GATEWAY_CONTAINER with object-store routing."
    exit 0
  fi

  sleep 1
done

echo "Dev infra verification failed." >&2
echo "Expected :8081 to be served by $expected_server_header and proxy /nta-default to object storage." >&2
echo >&2
echo "Latest response headers from $S3_PROBE_URL:" >&2
echo "$response_headers" >&2
echo >&2
echo "Recent $DEV_GATEWAY_CONTAINER logs:" >&2
docker logs "$DEV_GATEWAY_CONTAINER" --tail=60 >&2 || true
exit 1
