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

require_strong_secret_file() {
  label=$1
  secret_file=$2
  [ -n "$secret_file" ] && [ -r "$secret_file" ] || reject "$label"
  role_secret=$(cat "$secret_file")
  [ "${#role_secret}" -ge 32 ] || reject "$label"
  compact_secret=$(printf '%s' "$role_secret" | tr -cd '[:alnum:]' | tr '[:upper:]' '[:lower:]')
  case "$compact_secret" in
    *changeme*|*change*|*default*|*password*|*secret*|*demo*|*example*|*placeholder*)
      unset role_secret compact_secret
      reject "$label"
      ;;
  esac
  unset role_secret compact_secret
}

case "${APP_ENV:-development}" in
  production|migration)
    [ -z "${AUTH_ISSUER_DATABASE_URL:-}" ] || reject "AUTH_ISSUER_DATABASE_URL is forbidden"
    require_strong_secret_file \
      "POSTGRES_AUTH_ISSUER_PASSWORD_FILE" \
      "${POSTGRES_AUTH_ISSUER_PASSWORD_FILE:-}"
    ;;
esac

if [ "${APP_ENV:-development}" = "production" ]; then
  [ "${DEMO_MODE:-false}" != "true" ] || reject "DEMO_MODE=true"
  [ "${SEED_DEMO:-false}" != "true" ] || reject "SEED_DEMO=true"
  [ -z "${DEMO_TODAY:-}" ] || reject "DEMO_TODAY must be empty"

  canonical_domain=dishboard.joelduss.xyz
  canonical_origin="https://$canonical_domain"
  [ "${APP_PUBLIC_BASE_URL:-}" = "$canonical_origin" ] || \
    reject "APP_PUBLIC_BASE_URL must equal $canonical_origin"
  [ "${CAFETERIA_DOMAIN:-}" = "$canonical_domain" ] || \
    reject "CAFETERIA_DOMAIN must equal $canonical_domain"
  [ "${SESSION_COOKIE_SECURE:-false}" = "true" ] || reject "SESSION_COOKIE_SECURE must be true"

  app_image=${APP_IMAGE:-}
  case "$app_image" in
    *@sha256:*) image_digest=${app_image##*@sha256:} ;;
    *) reject "APP_IMAGE must use an immutable sha256 digest" ;;
  esac
  case "$image_digest" in
    ''|*[!0-9a-f]*) reject "APP_IMAGE must use an immutable sha256 digest" ;;
  esac
  [ "${#image_digest}" -eq 64 ] || reject "APP_IMAGE must use an immutable sha256 digest"

  is_placeholder "${ENTRA_TENANT_ID:-}" && reject "ENTRA_TENANT_ID"
  is_placeholder "${ENTRA_CLIENT_ID:-}" && reject "ENTRA_CLIENT_ID"

  secret_file=${ENTRA_CLIENT_SECRET_FILE:-}
  [ -n "$secret_file" ] && [ -r "$secret_file" ] || reject "ENTRA_CLIENT_SECRET_FILE"
  entra_secret=$(cat "$secret_file")
  [ -n "$entra_secret" ] || reject "ENTRA_CLIENT_SECRET_FILE"
  is_placeholder "$entra_secret" && reject "ENTRA_CLIENT_SECRET_FILE"
  unset entra_secret
fi

exec "$@"
