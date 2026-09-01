#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")"

[ -f .env ] || cp .env.example .env
mkdir -p secrets

generate_secret() {
  target=$1
  bytes=$2
  if [ ! -f "$target" ]; then
    python3 - "$bytes" > "$target" <<'PY'
import secrets, sys
print(secrets.token_urlsafe(int(sys.argv[1])))
PY
  fi
}

generate_secret secrets/postgres_owner_password.txt 48
[ -s secrets/postgres_owner_password.txt ] || exit 1
generate_secret secrets/postgres_app_password.txt 48
generate_secret secrets/postgres_backup_password.txt 48
generate_secret secrets/flask_secret_key.txt 64
generate_secret secrets/redis_password.txt 48

if [ ! -f secrets/entra_client_secret.txt ]; then
  printf '%s\n' 'REPLACE_WITH_ENTRA_CLIENT_SECRET_FOR_PRODUCTION' > secrets/entra_client_secret.txt
fi
chmod 600 secrets/*.txt
printf '%s\n' 'Vorbereitet. Entra und lokale Benutzer wurden nicht provisioniert.'
printf '%s\n' 'Vor dem Produktionsstart reale Entra-Werte setzen und ENTRA_ENABLED=true aktivieren.'
