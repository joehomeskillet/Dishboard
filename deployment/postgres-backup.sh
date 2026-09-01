#!/bin/sh
set -eu

MODE=${1:-once}
HOST=${POSTGRES_HOST:-db}
PORT=${POSTGRES_PORT:-5432}
DB=${POSTGRES_DB:-cafeteria}
USER=${POSTGRES_USER:-cafeteria_backup}
PASSWORD_FILE=${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_backup_password}
BACKUP_DIR=${BACKUP_DIR:-/backups}
INTERVAL=${BACKUP_INTERVAL_SECONDS:-86400}
RETENTION=${BACKUP_RETENTION_DAYS:-30}

[ -r "$PASSWORD_FILE" ] || { echo "PostgreSQL-Passwortdatei nicht lesbar: $PASSWORD_FILE" >&2; exit 1; }
export PGPASSWORD
PGPASSWORD=$(cat "$PASSWORD_FILE")
mkdir -p "$BACKUP_DIR"

backup_once() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  base="$BACKUP_DIR/cafeteria-$stamp"
  temporary="$base.dump.tmp"
  final="$base.dump"

  pg_dump \
    --host="$HOST" \
    --port="$PORT" \
    --username="$USER" \
    --dbname="$DB" \
    --schema=cafeteria \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    --lock-wait-timeout=10s \
    --file="$temporary"

  pg_restore --list "$temporary" >/dev/null
  mv "$temporary" "$final"
  chmod 600 "$final"
  sha256sum "$final" > "$final.sha256"
  chmod 600 "$final.sha256"
  printf '{"created_at":"%s","database":"%s","format":"pg_dump-custom","sha256_file":"%s"}\n' \
    "$stamp" "$DB" "$(basename "$final.sha256")" > "$final.json"
  chmod 600 "$final.json"

  find "$BACKUP_DIR" -type f -name 'cafeteria-*.dump' -mtime "+$RETENTION" -delete
  find "$BACKUP_DIR" -type f \( -name 'cafeteria-*.dump.sha256' -o -name 'cafeteria-*.dump.json' \) -mtime "+$RETENTION" -delete
  echo "$final"
}

restore_once() {
  source_file=${2:-}
  [ -n "$source_file" ] || { echo 'Restore-Datei fehlt.' >&2; exit 2; }
  [ -r "$source_file" ] || { echo "Restore-Datei nicht lesbar: $source_file" >&2; exit 1; }
  pg_restore --list "$source_file" >/dev/null

  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$DB" \
    --set=ON_ERROR_STOP=1 \
    --command='DROP SCHEMA IF EXISTS cafeteria CASCADE;'

  pg_restore \
    --host="$HOST" \
    --port="$PORT" \
    --username="$USER" \
    --dbname="$DB" \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    "$source_file"
}

case "$MODE" in
  once)
    backup_once
    ;;
  loop)
    while true; do
      backup_once
      sleep "$INTERVAL"
    done
    ;;
  restore)
    restore_once "$@"
    ;;
  *)
    echo "Unbekannter Modus: $MODE" >&2
    exit 2
    ;;
esac
