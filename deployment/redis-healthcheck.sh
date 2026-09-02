#!/bin/sh
set -eu

secret_file=${REDIS_PASSWORD_FILE:-/run/secrets/redis_password}
[ -r "$secret_file" ] || exit 1
REDISCLI_AUTH=$(cat "$secret_file")
export REDISCLI_AUTH
exec redis-cli --no-auth-warning ping
