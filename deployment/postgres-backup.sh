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

backup_once() {
  mkdir -p "$BACKUP_DIR"
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
  final_name=$(basename "$final")
  (
    cd "$BACKUP_DIR"
    sha256sum "$final_name" > "$final_name.sha256"
  )
  chmod 600 "$final.sha256"
  printf '{"created_at":"%s","database":"%s","format":"pg_dump-custom","sha256_file":"%s"}\n' \
    "$stamp" "$DB" "$(basename "$final.sha256")" > "$final.json"
  chmod 600 "$final.json"

  find "$BACKUP_DIR" -type f -name 'cafeteria-*.dump' -mtime "+$RETENTION" -delete
  find "$BACKUP_DIR" -type f \( -name 'cafeteria-*.dump.sha256' -o -name 'cafeteria-*.dump.json' \) -mtime "+$RETENTION" -delete
  echo "$final"
}

verify_checksum() {
  source_file=${2:-}
  checksum_file=${3:-}
  [ -n "$source_file" ] || { echo 'Restore-Datei fehlt.' >&2; exit 2; }
  [ -n "$checksum_file" ] || { echo 'Checksum-Datei fehlt.' >&2; exit 2; }
  [ -r "$source_file" ] || { echo "Restore-Datei nicht lesbar: $source_file" >&2; exit 1; }
  [ -r "$checksum_file" ] || { echo "Checksum-Datei nicht lesbar: $checksum_file" >&2; exit 1; }

  exec 3< "$checksum_file"
  if ! IFS=' ' read -r expected listed_name extra <&3; then
    exec 3<&-
    echo 'Checksum-Datei ist leer.' >&2
    exit 1
  fi
  if IFS= read -r extra_line <&3; then
    exec 3<&-
    echo 'Checksum-Datei muss genau einen Eintrag enthalten.' >&2
    exit 1
  fi
  exec 3<&-

  listed_name=${listed_name#\*}
  case "$expected" in
    ''|*[!0-9a-fA-F]*) echo 'Checksum-Datei enthält keinen SHA-256-Wert.' >&2; exit 1 ;;
  esac
  [ "${#expected}" -eq 64 ] || { echo 'Checksum-Datei enthält keinen SHA-256-Wert.' >&2; exit 1; }
  [ -z "$extra" ] && [ "$listed_name" = "$(basename "$source_file")" ] || {
    echo 'Checksum-Datei referenziert nicht exakt die Restore-Datei.' >&2
    exit 1
  }

  actual_line=$(sha256sum "$source_file")
  actual=${actual_line%% *}
  [ "$actual" = "$expected" ] || { echo 'SHA-256-Prüfung der Restore-Datei fehlgeschlagen.' >&2; exit 1; }
}

validate_database_names() {
  RESTORE_RUN_ID=${1:-${RESTORE_RUN_ID:-}}
  case "$RESTORE_RUN_ID" in
    ''|*[!A-Za-z0-9_]*)
      echo 'Restore-Laufkennung fehlt oder ist unsicher.' >&2
      exit 1
      ;;
  esac
  case "$DB" in
    ''|[0-9]*|*[!A-Za-z0-9_]*|postgres|template0|template1)
      echo "Unsicherer PostgreSQL-Datenbankname: $DB" >&2
      exit 1
      ;;
  esac
  CANDIDATE_DB="${DB}_restore_candidate_${RESTORE_RUN_ID}"
  ROLLBACK_DB="${DB}_restore_rollback_${RESTORE_RUN_ID}"
  FAILED_DB="${DB}_restore_failed_${RESTORE_RUN_ID}"
  RESTORE_OWNER_MARKER="menuplan-restore:${RESTORE_RUN_ID}"
  [ "${#CANDIDATE_DB}" -le 63 ] && [ "${#ROLLBACK_DB}" -le 63 ] && [ "${#FAILED_DB}" -le 63 ] || {
    echo 'PostgreSQL-Datenbankname ist für sichere Restore-Suffixe zu lang.' >&2
    exit 1
  }
}

admin_sql() {
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname=postgres \
    --set=ON_ERROR_STOP=1 --command="$1"
}

database_state() {
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname=postgres \
    --set=ON_ERROR_STOP=1 --tuples-only --no-align \
    --command="SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname = '$1')
      THEN COALESCE((SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = '$1'), '<unmarked>')
      ELSE '<absent>' END;"
}

require_absent_database() {
  state=$(database_state "$1")
  [ "$state" = '<absent>' ] || {
    echo "Fremde oder vorhandene Restore-Datenbank wird nicht verändert: $1" >&2
    exit 1
  }
}

require_owned_database() {
  state=$(database_state "$1")
  [ "$state" = "$RESTORE_OWNER_MARKER" ] || {
    echo "Fremde Restore-Datenbank wird nicht verändert: $1" >&2
    exit 1
  }
}

mark_owned_database() {
  admin_sql "COMMENT ON DATABASE \"$1\" IS '$RESTORE_OWNER_MARKER';" >/dev/null
}

terminate_database() {
  admin_sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$1' AND pid <> pg_backend_pid();" \
    >/dev/null
}

allow_database() {
  admin_sql "ALTER DATABASE \"$1\" ALLOW_CONNECTIONS $2;" >/dev/null
}

rename_database() {
  admin_sql "ALTER DATABASE \"$1\" RENAME TO \"$2\";" >/dev/null
}

drop_database() {
  dropdb --host="$HOST" --port="$PORT" --username="$USER" --if-exists "$1"
}

drop_owned_database() {
  require_owned_database "$1"
  terminate_database "$1"
  drop_database "$1"
}

verify_pgcrypto() {
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --set=ON_ERROR_STOP=1 \
    --command='CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;' >/dev/null
  pgcrypto_state=$(psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --set=ON_ERROR_STOP=1 --tuples-only --no-align \
    --command="SELECT CASE WHEN to_regprocedure('public.digest(bytea,text)') IS NOT NULL
        AND encode(public.digest(convert_to('restore-candidate', 'UTF8'), 'sha256'), 'hex') ~ '^[0-9a-f]{64}$'
      THEN 'ready' ELSE 'invalid' END;")
  [ "$pgcrypto_state" = ready ] || {
    echo 'Restore-Kandidat konnte pgcrypto/digest() nicht bereitstellen.' >&2
    exit 1
  }
}

restore_stage() {
  source_file=$1
  checksum_file=$2
  validate_database_names "$3"
  verify_checksum restore-stage "$source_file" "$checksum_file"
  pg_restore --list "$source_file" >/dev/null

  candidate_created=false
  cleanup_staging_failure() {
    status=$?
    trap - 0 1 2 15
    cleanup_failed=false
    if [ "$candidate_created" = true ]; then
      drop_owned_database "$CANDIDATE_DB" || cleanup_failed=true
    fi
    if [ "$cleanup_failed" = true ]; then
      echo "Restore-Kandidat konnte nicht bereinigt werden: $CANDIDATE_DB" >&2
      status=1
    fi
    exit "$status"
  }
  trap cleanup_staging_failure 0
  trap 'exit 130' 1 2 15

  require_absent_database "$CANDIDATE_DB"
  createdb --host="$HOST" --port="$PORT" --username="$USER" --template=template0 "$CANDIDATE_DB"
  candidate_created=true
  mark_owned_database "$CANDIDATE_DB"

  pg_restore \
    --host="$HOST" \
    --port="$PORT" \
    --username="$USER" \
    --dbname="$CANDIDATE_DB" \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    "$source_file"

  verify_pgcrypto

  schema_state=$(psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --set=ON_ERROR_STOP=1 --tuples-only --no-align \
    --command="SELECT CASE WHEN to_regnamespace('cafeteria') IS NOT NULL AND EXISTS (
      SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'cafeteria' AND c.relkind IN ('r', 'p')
    ) THEN 'ready' ELSE 'invalid' END;")
  [ "$schema_state" = ready ] || { echo 'Restore-Kandidat enthält kein gültiges Cafeteria-Schema.' >&2; exit 1; }

  candidate_created=false
  trap - 0 1 2 15
  echo "$CANDIDATE_DB"
}

restore_cleanup_candidate() {
  validate_database_names "$1"
  drop_owned_database "$CANDIDATE_DB"
}

restore_promote() {
  validate_database_names "$1"
  require_owned_database "$CANDIDATE_DB"
  require_absent_database "$ROLLBACK_DB"

  promotion_state=initial
  recover_promotion() {
    status=$?
    trap - 0 1 2 15
    [ "$status" -eq 0 ] && exit 0
    set +e
    recovery_failed=false
    case "$promotion_state" in
      candidate_locked)
        allow_database "$CANDIDATE_DB" true || recovery_failed=true
        ;;
      production_locked)
        allow_database "$DB" true || recovery_failed=true
        allow_database "$CANDIDATE_DB" true || recovery_failed=true
        ;;
      production_renamed)
        rename_database "$ROLLBACK_DB" "$DB" || recovery_failed=true
        allow_database "$DB" true || recovery_failed=true
        allow_database "$CANDIDATE_DB" true || recovery_failed=true
        ;;
      candidate_promoted)
        terminate_database "$DB" || recovery_failed=true
        rename_database "$DB" "$CANDIDATE_DB" || recovery_failed=true
        rename_database "$ROLLBACK_DB" "$DB" || recovery_failed=true
        allow_database "$DB" true || recovery_failed=true
        allow_database "$CANDIDATE_DB" true || recovery_failed=true
        ;;
    esac
    if [ "$recovery_failed" = true ]; then
      echo 'Fehlgeschlagene Promotion konnte nicht vollständig zurückgesetzt werden.' >&2
      status=1
    fi
    exit "$status"
  }
  trap recover_promotion 0
  trap 'exit 130' 1 2 15

  allow_database "$CANDIDATE_DB" false
  promotion_state=candidate_locked
  terminate_database "$CANDIDATE_DB"
  allow_database "$DB" false
  promotion_state=production_locked
  terminate_database "$DB"
  rename_database "$DB" "$ROLLBACK_DB"
  promotion_state=production_renamed
  rename_database "$CANDIDATE_DB" "$DB"
  promotion_state=candidate_promoted
  allow_database "$DB" true
  promotion_state=complete
  trap - 0 1 2 15
}

restore_rollback() {
  validate_database_names "$1"
  require_owned_database "$DB"
  require_absent_database "$FAILED_DB"

  rollback_state=initial
  recover_rollback() {
    status=$?
    trap - 0 1 2 15
    [ "$status" -eq 0 ] && exit 0
    set +e
    recovery_failed=false
    case "$rollback_state" in
      production_locked)
        allow_database "$DB" true || recovery_failed=true
        ;;
      production_renamed)
        rename_database "$FAILED_DB" "$DB" || recovery_failed=true
        allow_database "$DB" true || recovery_failed=true
        ;;
      rollback_promoted)
        allow_database "$DB" true || recovery_failed=true
        ;;
    esac
    if [ "$recovery_failed" = true ]; then
      echo 'Fehlgeschlagener Rollback konnte nicht vollständig zurückgesetzt werden.' >&2
      status=1
    fi
    exit "$status"
  }
  trap recover_rollback 0
  trap 'exit 130' 1 2 15

  allow_database "$DB" false
  rollback_state=production_locked
  terminate_database "$DB"
  rename_database "$DB" "$FAILED_DB"
  rollback_state=production_renamed
  rename_database "$ROLLBACK_DB" "$DB"
  rollback_state=rollback_promoted
  allow_database "$DB" true
  drop_database "$FAILED_DB"
  rollback_state=complete
  trap - 0 1 2 15
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
  restore-stage)
    restore_stage "${2:-}" "${3:-}" "${4:-${RESTORE_RUN_ID:-}}"
    ;;
  restore-cleanup-candidate)
    restore_cleanup_candidate "${2:-${RESTORE_RUN_ID:-}}"
    ;;
  restore-promote)
    restore_promote "${2:-${RESTORE_RUN_ID:-}}"
    ;;
  restore-rollback)
    restore_rollback "${2:-${RESTORE_RUN_ID:-}}"
    ;;
  *)
    echo "Unbekannter Modus: $MODE" >&2
    exit 2
    ;;
esac
