#!/usr/bin/env bash
# Bootstrap the Gitea instance running in the dev compose stack:
#   1. Wait for Gitea to be healthy.
#   2. Create the admin user (idempotent).
#   3. Generate a personal access token for the platform backend.
#   4. Write GITEA_ADMIN_TOKEN back into .env so the backend picks it up.
#
# Usage: bash infra/scripts/bootstrap-gitea.sh
#        make gitea.bootstrap
#
# Re-runs are safe; an existing token line in .env is replaced.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
CONTAINER="${GITEA_CONTAINER_NAME:-nta-gitea}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[bootstrap-gitea] .env not found at ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

: "${GITEA_HTTP_PORT:?GITEA_HTTP_PORT missing in .env}"
: "${GITEA_ADMIN_USER:?GITEA_ADMIN_USER missing in .env}"
: "${GITEA_ADMIN_PASSWORD:?GITEA_ADMIN_PASSWORD missing in .env}"
: "${GITEA_ADMIN_EMAIL:?GITEA_ADMIN_EMAIL missing in .env}"

GITEA_URL="http://127.0.0.1:${GITEA_HTTP_PORT}"
TOKEN_NAME="${GITEA_TOKEN_NAME:-nta-platform}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[bootstrap-gitea] docker is required" >&2
  exit 127
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[bootstrap-gitea] curl is required" >&2
  exit 127
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER_NAME:-nta-postgres}"
if docker inspect -f '{{.State.Running}}' "${POSTGRES_CONTAINER}" 2>/dev/null | grep -q true; then
  echo "[bootstrap-gitea] ensuring 'gitea' database exists in ${POSTGRES_CONTAINER}"
  if ! docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB:-postgres}" -tAc \
    "SELECT 1 FROM pg_database WHERE datname='gitea'" | grep -q 1; then
    docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "${POSTGRES_CONTAINER}" \
      psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB:-postgres}" -c "CREATE DATABASE gitea OWNER ${POSTGRES_USER};" >/dev/null
    echo "[bootstrap-gitea] created 'gitea' database"
    if docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null | grep -q true; then
      echo "[bootstrap-gitea] restarting ${CONTAINER} so it picks up the new database"
      docker restart "${CONTAINER}" >/dev/null
    fi
  fi
fi

echo "[bootstrap-gitea] waiting for Gitea at ${GITEA_URL} ..."
for _ in $(seq 1 60); do
  if curl -fsS "${GITEA_URL}/api/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "${GITEA_URL}/api/healthz" >/dev/null 2>&1; then
  echo "[bootstrap-gitea] Gitea did not become healthy in time" >&2
  exit 1
fi

echo "[bootstrap-gitea] creating admin user '${GITEA_ADMIN_USER}' (idempotent)"
if ! docker exec -u 1000 "${CONTAINER}" gitea admin user create \
  --username "${GITEA_ADMIN_USER}" \
  --password "${GITEA_ADMIN_PASSWORD}" \
  --email "${GITEA_ADMIN_EMAIL}" \
  --admin \
  --must-change-password=false \
  >/dev/null 2>&1; then
  echo "[bootstrap-gitea] admin user already exists, continuing"
fi

echo "[bootstrap-gitea] generating personal access token '${TOKEN_NAME}'"
delete_resp=$(curl -fsS -o /dev/null -w "%{http_code}" \
  -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
  -X DELETE \
  "${GITEA_URL}/api/v1/users/${GITEA_ADMIN_USER}/tokens/${TOKEN_NAME}" || true)
case "${delete_resp}" in
  204|404) ;;
  *) echo "[bootstrap-gitea] unexpected status ${delete_resp} while deleting old token" >&2 ;;
esac

create_payload=$(cat <<JSON
{"name":"${TOKEN_NAME}","scopes":["write:organization","write:repository","write:user","read:user"]}
JSON
)

token=$(curl -fsS \
  -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
  -H 'Content-Type: application/json' \
  -X POST \
  -d "${create_payload}" \
  "${GITEA_URL}/api/v1/users/${GITEA_ADMIN_USER}/tokens" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha1"])')

if [[ -z "${token}" ]]; then
  echo "[bootstrap-gitea] failed to obtain token from Gitea" >&2
  exit 1
fi

tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
if grep -q '^GITEA_ADMIN_TOKEN=' "${ENV_FILE}"; then
  awk -v t="${token}" 'BEGIN{FS=OFS="="} /^GITEA_ADMIN_TOKEN=/{$2=t} {print}' "${ENV_FILE}" > "${tmp}"
else
  cp "${ENV_FILE}" "${tmp}"
  printf '\nGITEA_ADMIN_TOKEN=%s\n' "${token}" >> "${tmp}"
fi
mv "${tmp}" "${ENV_FILE}"

echo "[bootstrap-gitea] GITEA_ADMIN_TOKEN written to ${ENV_FILE}"
echo "[bootstrap-gitea] Gitea UI: ${GITEA_URL}  user: ${GITEA_ADMIN_USER}"
