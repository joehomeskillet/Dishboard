#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
  echo "Verwendung: $0 /absoluter/pfad/cafeteria-YYYYMMDDTHHMMSSZ.dump" >&2
  exit 2
fi
backup=$1
[ -f "$backup" ] || { echo "Backup nicht gefunden: $backup" >&2; exit 1; }
backup_dir=$(CDPATH= cd -- "$(dirname -- "$backup")" && pwd)
backup_name=$(basename -- "$backup")
cd "$(dirname "$0")"

sha_file="$backup.sha256"
if [ -f "$sha_file" ]; then
  (cd "$backup_dir" && sha256sum -c "$(basename -- "$sha_file")")
fi

docker compose stop app backup
docker compose --profile ops run --rm \
  -v "$backup_dir:/restore-source:ro" \
  restore restore "/restore-source/$backup_name"
docker compose run --rm migrate
docker compose run --rm app python /app/manage.py validate-db --wait-seconds 30
docker compose up -d app backup
