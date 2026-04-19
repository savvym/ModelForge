#!/usr/bin/env bash

detect_app_env_file() {
  local root_dir="${1:?root_dir is required}"

  if [[ -n "${APP_ENV_FILE:-}" ]]; then
    echo "${APP_ENV_FILE}"
    return 0
  fi

  if [[ -f "$root_dir/.env.dev.local" ]]; then
    echo "$root_dir/.env.dev.local"
    return 0
  fi

  echo "$root_dir/.env"
}

load_app_env_file() {
  local root_dir="${1:?root_dir is required}"
  local env_file
  env_file="$(detect_app_env_file "$root_dir")"

  if [[ ! -f "$env_file" ]]; then
    echo "Missing app env file: $env_file" >&2
    return 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a

  export APP_ENV_FILE="$env_file"
}
