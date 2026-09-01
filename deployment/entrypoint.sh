#!/bin/sh
set -eu

reject() {
  printf '%s\n' "deployment configuration rejected: $1" >&2
  exit 1
}

is_placeholder() {
  case "$1" in
    ''|00000000-0000-0000-0000-000000000000|REPLACE_*|CHANGE_ME*|example.invalid)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [ "${APP_ENV:-development}" = "production" ]; then
  [ "${DEMO_MODE:-false}" != "true" ] || reject "DEMO_MODE=true"
  [ "${SEED_DEMO:-false}" != "true" ] || reject "SEED_DEMO=true"
  [ -z "${DEMO_TODAY:-}" ] || reject "DEMO_TODAY must be empty"

  if [ "${ENTRA_ENABLED:-false}" = "true" ]; then
    is_placeholder "${ENTRA_TENANT_ID:-}" && reject "ENTRA_TENANT_ID"
    is_placeholder "${ENTRA_CLIENT_ID:-}" && reject "ENTRA_CLIENT_ID"

    secret_file=${ENTRA_CLIENT_SECRET_FILE:-}
    [ -n "$secret_file" ] && [ -r "$secret_file" ] || reject "ENTRA_CLIENT_SECRET_FILE"
    entra_secret=$(cat "$secret_file")
    [ -n "$entra_secret" ] || reject "ENTRA_CLIENT_SECRET_FILE"
    is_placeholder "$entra_secret" && reject "ENTRA_CLIENT_SECRET_FILE"
    unset entra_secret
  fi
fi

exec "$@"
