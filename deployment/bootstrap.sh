#!/bin/sh
set -eu
cd "$(dirname "$0")"

[ -f .env ] || cp .env.example .env
mkdir -p secrets

generate_secret() {
  target=$1
  bytes=$2
  if [ ! -f "$target" ]; then
    python - "$bytes" > "$target" <<'PY'
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
printf '%s\n' 'Vorbereitet. Demo-Start: docker compose up --build -d'
