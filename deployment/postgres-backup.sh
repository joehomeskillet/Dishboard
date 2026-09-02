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
LEASE_SECONDS=${RESTORE_LEASE_SECONDS:-21600}
CONTROLLER_TIMEOUT=${RESTORE_CONTROLLER_TIMEOUT_SECONDS:-30}
ROLLBACK_RETENTION_SECONDS=${RESTORE_ROLLBACK_RETENTION_SECONDS:-604800}

[ -r "$PASSWORD_FILE" ] || { echo "PostgreSQL-Passwortdatei nicht lesbar: $PASSWORD_FILE" >&2; exit 1; }
export PGPASSWORD
PGPASSWORD=$(cat "$PASSWORD_FILE")

backup_once() {
  mkdir -p "$BACKUP_DIR"
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  temporary=$(mktemp "$BACKUP_DIR/.cafeteria-$stamp.XXXXXX")
  unique_name=${temporary##*/}
  unique_name=${unique_name#.}
  final="$BACKUP_DIR/$unique_name.dump"
  cleanup_temporary_backup() {
    status=$?
    trap - 0 1 2 15
    [ -z "$temporary" ] || rm -f -- "$temporary"
    exit "$status"
  }
  trap cleanup_temporary_backup 0
  trap 'exit 130' 1 2 15

  pg_dump \
    --host="$HOST" \
    --port="$PORT" \
    --username="$USER" \
    --dbname="$DB" \
    --schema=cafeteria \
    --exclude-table=cafeteria.auth_capability_secrets \
    --exclude-table=cafeteria.auth_capability_nonces \
    --exclude-table=cafeteria.auth_capability_secrets_id_seq \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    --lock-wait-timeout=10s \
    --file="$temporary"

  pg_restore --list "$temporary" >/dev/null
  mv "$temporary" "$final"
  temporary=
  trap - 0 1 2 15
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

validate_restore_run() {
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
  case "$LEASE_SECONDS" in
    ''|*[!0-9]*) echo 'RESTORE_LEASE_SECONDS muss eine positive Ganzzahl sein.' >&2; exit 1 ;;
  esac
  [ "$LEASE_SECONDS" -ge 1 ] && [ "$LEASE_SECONDS" -le 86400 ] || {
    echo 'RESTORE_LEASE_SECONDS muss zwischen 1 und 86400 liegen.' >&2
    exit 1
  }
  case "$CONTROLLER_TIMEOUT" in
    ''|*[!0-9]*) echo 'RESTORE_CONTROLLER_TIMEOUT_SECONDS muss eine positive Ganzzahl sein.' >&2; exit 1 ;;
  esac
  [ "$CONTROLLER_TIMEOUT" -ge 2 ] && [ "$CONTROLLER_TIMEOUT" -le 300 ] || {
    echo 'RESTORE_CONTROLLER_TIMEOUT_SECONDS muss zwischen 2 und 300 liegen.' >&2
    exit 1
  }
  case "$ROLLBACK_RETENTION_SECONDS" in
    ''|*[!0-9]*) echo 'RESTORE_ROLLBACK_RETENTION_SECONDS muss eine positive Ganzzahl sein.' >&2; exit 1 ;;
  esac
  [ "$ROLLBACK_RETENTION_SECONDS" -ge 3600 ] && [ "$ROLLBACK_RETENTION_SECONDS" -le 2592000 ] || {
    echo 'RESTORE_ROLLBACK_RETENTION_SECONDS muss zwischen 3600 und 2592000 liegen.' >&2
    exit 1
  }
  CANDIDATE_DB="${DB}_restore_candidate_${RESTORE_RUN_ID}"
  ROLLBACK_DB="${DB}_restore_rollback_${RESTORE_RUN_ID}"
  FAILED_DB="${DB}_restore_failed_${RESTORE_RUN_ID}"
  [ "${#CANDIDATE_DB}" -le 63 ] && [ "${#ROLLBACK_DB}" -le 63 ] && [ "${#FAILED_DB}" -le 63 ] || {
    echo 'PostgreSQL-Datenbankname ist für sichere Restore-Suffixe zu lang.' >&2
    exit 1
  }
}

validate_owner_token() {
  OWNER_TOKEN=${1:-}
  case "$OWNER_TOKEN" in
    ''|*[!0-9a-fA-F-]*) echo 'Restore-Owner-Token fehlt oder ist unsicher.' >&2; exit 1 ;;
  esac
  [ "${#OWNER_TOKEN}" -eq 36 ] || { echo 'Restore-Owner-Token ist ungültig.' >&2; exit 1; }
}

control_psql() {
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname=postgres \
    --set=ON_ERROR_STOP=1 --set=database_name="$DB" --set=lease_seconds="$LEASE_SECONDS" \
    --set=controller_timeout="$CONTROLLER_TIMEOUT" \
    --set=rollback_retention_seconds="$ROLLBACK_RETENTION_SECONDS" "$@"
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RESTORE_CONTROL_LIBRARY=${RESTORE_CONTROL_LIBRARY:-$SCRIPT_DIR/postgres-restore-control.sh}
[ -r "$RESTORE_CONTROL_LIBRARY" ] || {
  echo "Restore-Control-Bibliothek nicht lesbar: $RESTORE_CONTROL_LIBRARY" >&2
  exit 1
}
. "$RESTORE_CONTROL_LIBRARY"

verify_database() {
  database=$1
  pgcrypto_state=$(psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$database" \
    --set=ON_ERROR_STOP=1 --tuples-only --no-align \
    --command="SELECT CASE WHEN to_regprocedure('public.digest(bytea,text)') IS NOT NULL
        AND encode(public.digest(convert_to('restore-check', 'UTF8'), 'sha256'), 'hex') ~ '^[0-9a-f]{64}$'
        AND to_regnamespace('cafeteria') IS NOT NULL AND EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname = 'cafeteria' AND c.relkind IN ('r', 'p')
        ) THEN 'ready' ELSE 'invalid' END;")
  [ "$pgcrypto_state" = ready ] || {
    echo "Datenbank $database enthält kein gültiges pgcrypto/Cafeteria-Schema." >&2
    exit 1
  }
}

create_candidate() {
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=candidate_db="$CANDIDATE_DB" <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND candidate_database = :'candidate_db' AND lifecycle = 'staging' AND lease_expires_at > clock_timestamp() ) AS lease_ok \gset
\if :lease_ok
SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db') AS candidate_absent \gset
\if :candidate_absent
UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_create_pending', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'candidate_create_pending', updated_at = clock_timestamp() WHERE database_name = :'database_name';
SELECT 'menuplan-restore-candidate:' || restore_run_id || ':' || resource_token::text AS candidate_marker FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
CREATE DATABASE :"candidate_db" TEMPLATE template0;
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
COMMENT ON DATABASE :"candidate_db" IS :'candidate_marker';
UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_created', last_event = 'candidate_created', updated_at = clock_timestamp() WHERE database_name = :'database_name';
\else
\warn 'Fremde oder vorhandene Restore-Datenbank wird nicht verändert.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Restore lease is missing, foreign, or expired.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_abort() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=candidate_db="$CANDIDATE_DB" <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() AND lifecycle IN ('acquired', 'staging', 'candidate_create_pending', 'candidate_created', 'candidate_ready', 'migrated', 'candidate_validated') ) AS abort_allowed \gset
\if :abort_allowed
SELECT 'menuplan-restore-candidate:' || restore_run_id || ':' || resource_token::text AS candidate_marker FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db') AS candidate_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS candidate_owned \gset
\if :candidate_exists
\if :candidate_owned
\else
\warn 'Fremde Restore-Datenbank wird nicht verändert.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'candidate_db' AND pid <> pg_backend_pid();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
DROP DATABASE :"candidate_db";
\endif
UPDATE public.menuplan_restore_control SET lifecycle = 'aborted', lease_expires_at = clock_timestamp(), last_event = 'aborted', updated_at = clock_timestamp() WHERE database_name = :'database_name';
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, last_event FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
\warn 'Restore abort refused for foreign, expired, or promoted state.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_stage() {
  source_file=$1
  checksum_file=$2
  validate_restore_run "$3"
  validate_owner_token "$4"
  cleanup_needed=true
  cleanup_staging_failure() {
    status=$?
    trap - 0 1 2 15
    if [ "$status" -ne 0 ] && [ "$cleanup_needed" = true ]; then
      restore_abort "$RESTORE_RUN_ID" "$OWNER_TOKEN" || status=1
    fi
    exit "$status"
  }
  trap cleanup_staging_failure 0
  trap 'exit 130' 1 2 15

  verify_checksum restore-stage "$source_file" "$checksum_file"
  pg_restore --list "$source_file" >/dev/null
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"

  restore_state_internal=staging
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=next_state="$restore_state_internal" <<'SQL' >/dev/null
\set QUIET 1
BEGIN;
SELECT pg_advisory_xact_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = :'next_state', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'state:' || :'next_state', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'acquired' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS state_changed FROM changed \gset
\if :state_changed
COMMIT;
\else
ROLLBACK;
\warn 'Restore stage requires the acquired lease state.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL

  create_candidate
  pg_restore --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --no-owner --no-privileges --exit-on-error "$source_file"
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --set=ON_ERROR_STOP=1 --command='CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;' >/dev/null
  verify_database "$CANDIDATE_DB"
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" <<'SQL' >/dev/null
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_ready', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'candidate_ready', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'candidate_created' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS candidate_ready FROM changed \gset
\if :candidate_ready
\else
\warn 'Restore candidate-ready transition changed no row.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
  cleanup_needed=false
  trap - 0 1 2 15
  echo "$CANDIDATE_DB"
}

restore_promote() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  fail_after=false
  case "${RESTORE_FAIL_AFTER_STATE:-}" in
    '') ;;
    production_renamed)
      [ "${RESTORE_TESTING:-false}" = true ] || {
        echo 'Restore-Failpoint ist nur mit RESTORE_TESTING=true erlaubt.' >&2
        exit 1
      }
      fail_after=true
      ;;
    *) echo 'Unbekannter Restore-Failpoint.' >&2; exit 1 ;;
  esac
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=candidate_db="$CANDIDATE_DB" --set=rollback_db="$ROLLBACK_DB" \
    --set=fail_after="$fail_after" <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT EXISTS (SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'complete') AS already_complete \gset
\if :already_complete
\quit
\endif
SELECT EXISTS (SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'candidate_validated' AND lease_expires_at > clock_timestamp() AND candidate_database = :'candidate_db' AND rollback_database = :'rollback_db') AS lease_ok \gset
\if :lease_ok
SELECT 'menuplan-restore-candidate:' || restore_run_id || ':' || resource_token::text AS candidate_marker, 'menuplan-restore-rollback:' || restore_run_id || ':' || resource_token::text AS rollback_marker FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS candidate_owned, NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'rollback_db') AS rollback_absent, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name') AS production_exists \gset
\if :candidate_owned
\if :rollback_absent
\if :production_exists
UPDATE public.menuplan_restore_control SET lifecycle = 'promotion_started', original_comment = (SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = :'database_name'), lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'promotion_started', updated_at = clock_timestamp() WHERE database_name = :'database_name';
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
COMMENT ON DATABASE :"database_name" IS :'rollback_marker';
UPDATE public.menuplan_restore_control SET lifecycle = 'production_marked', last_event = 'production_marked' WHERE database_name = :'database_name';
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"candidate_db" ALLOW_CONNECTIONS false;
UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_locked', last_event = 'candidate_locked', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer) WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'candidate_db' AND pid <> pg_backend_pid();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" ALLOW_CONNECTIONS false;
UPDATE public.menuplan_restore_control SET lifecycle = 'production_locked', last_event = 'production_locked', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer) WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'database_name' AND pid <> pg_backend_pid();
UPDATE public.menuplan_restore_control SET lifecycle = 'production_rename_pending', last_event = 'production_rename_pending', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" RENAME TO :"rollback_db";
UPDATE public.menuplan_restore_control SET lifecycle = 'production_renamed', last_event = 'production_renamed' WHERE database_name = :'database_name';
\if :fail_after
\warn 'Injected restore failure after production_renamed.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_promote_pending', last_event = 'candidate_promote_pending', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"candidate_db" RENAME TO :"database_name";
UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_promoted', last_event = 'candidate_promoted' WHERE database_name = :'database_name';
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" ALLOW_CONNECTIONS true;
UPDATE public.menuplan_restore_control SET lifecycle = 'promoted', last_event = 'promoted', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'promoted' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
\warn 'Produktionsdatenbank fehlt; Recovery ist erforderlich.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Fremde oder vorhandene Rollback-Datenbank wird nicht verändert.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Fremder Restore-Kandidat wird nicht verändert.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Restore promotion requires a valid candidate and nonexpired owner lease.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_recover_topology() {
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=candidate_db="$CANDIDATE_DB" --set=rollback_db="$ROLLBACK_DB" <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
WITH changed AS ( UPDATE public.menuplan_restore_control SET recovery_from_state = COALESCE(recovery_from_state, lifecycle), recovery_target = CASE WHEN COALESCE(recovery_from_state, lifecycle) IN ('writer_release_committed', 'app_validated') THEN 'candidate' ELSE 'old' END, lifecycle = 'recovery_started', last_event = 'recovery_started', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle NOT IN ('complete', 'aborted') AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS recovery_started FROM changed \gset
\if :recovery_started
SELECT 'menuplan-restore-candidate:' || restore_run_id || ':' || resource_token::text AS candidate_marker, 'menuplan-restore-rollback:' || restore_run_id || ':' || resource_token::text AS rollback_marker FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
SELECT recovery_target FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name') AS production_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS production_is_candidate, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name' AND shobj_description(oid, 'pg_database') = :'rollback_marker') AS production_is_marked_old, EXISTS (SELECT 1 FROM pg_database p JOIN public.menuplan_restore_control c ON c.database_name = :'database_name' WHERE p.datname = :'database_name' AND shobj_description(p.oid, 'pg_database') IS NOT DISTINCT FROM c.original_comment AND (c.old_database_verified OR c.recovery_from_state IN ('acquired', 'staging', 'candidate_create_pending', 'candidate_created', 'candidate_ready', 'migrated', 'candidate_validated', 'services_stopped', 'promotion_started'))) AS production_is_original, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'rollback_db') AS rollback_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'rollback_db' AND shobj_description(oid, 'pg_database') = :'rollback_marker') AS rollback_owned, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db') AS candidate_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS candidate_owned \gset
\if :rollback_exists
\if :rollback_owned
\else
\warn 'Fremde Rollback-Datenbank blockiert Recovery.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\endif
SELECT :'recovery_target' = 'candidate' AS keep_candidate \gset
\if :keep_candidate
\if :production_is_candidate
\if :rollback_owned
\if :candidate_exists
\warn 'Vorhandener Kandidatenname blockiert sichere Candidate-Recovery.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" ALLOW_CONNECTIONS true;
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = 'recovery_candidate_ready', last_event = 'recovery_candidate_ready', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND recovery_target = 'candidate' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS recovery_candidate_ready FROM changed \gset
\if :recovery_candidate_ready
\else
\warn 'Candidate recovery transition changed no row.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Rollback database is missing after the writer-release point of no return.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Committed candidate is not present at the production name.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\if :production_is_candidate
\if :rollback_owned
\if :candidate_exists
\warn 'Vorhandener Kandidatenname blockiert sichere Recovery.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" ALLOW_CONNECTIONS false;
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'database_name' AND pid <> pg_backend_pid();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" RENAME TO :"candidate_db";
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"rollback_db" RENAME TO :"database_name";
\else
\warn 'Alter Datenbankstand fehlt; Kandidat wird nicht als Recovery angenommen.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\elif :production_exists
\if :production_is_marked_old
\elif :production_is_original
\else
\warn 'Produktionsname gehört keinem beweisbaren alten Datenbankstand.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\elif :rollback_owned
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"rollback_db" RENAME TO :"database_name";
\else
\warn 'Alter Datenbankstand ist nicht beweisbar vorhanden.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" ALLOW_CONNECTIONS true;
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = 'recovery_old_proof_pending', last_event = 'recovery_old_proof_pending', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND recovery_target = 'old' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS recovery_old_ready FROM changed \gset
\if :recovery_old_ready
\else
\warn 'Old-database recovery transition changed no row.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\endif
\else
\warn 'Restore recovery requires the same nonexpired owner token.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

persist_old_database_proof() {
  fail_after_proof=false
  case "${RESTORE_FAIL_AFTER_STATE:-}" in
    '') ;;
    old_database_proof_persisted)
      [ "${RESTORE_TESTING:-false}" = true ] || {
        echo 'Restore-Failpoint ist nur mit RESTORE_TESTING=true erlaubt.' >&2
        exit 1
      }
      fail_after_proof=true
      ;;
    *) echo 'Unbekannter Restore-Failpoint.' >&2; exit 1 ;;
  esac
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=fail_after_proof="$fail_after_proof" <<'SQL' >/dev/null
\set QUIET 1
WITH changed AS ( UPDATE public.menuplan_restore_control SET old_database_verified = true, lifecycle = 'old_database_proof_persisted', last_event = 'old_database_proof_persisted', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND recovery_target = 'old' AND lifecycle IN ('recovery_old_proof_pending', 'old_database_proof_persisted') AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS old_database_proof_persisted FROM changed \gset
\if :old_database_proof_persisted
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'old_database_proof_persisted' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\if :fail_after_proof
\warn 'Injected restore failure after old_database_proof_persisted.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
\warn 'Old database proof could not be persisted.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SELECT format('COMMENT ON DATABASE %I IS %L;', :'database_name', original_comment) FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND old_database_verified \gexec
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = 'recovery_topology_restored', last_event = 'recovery_topology_restored', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND recovery_target = 'old' AND old_database_verified AND lifecycle = 'old_database_proof_persisted' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS recovery_topology_restored FROM changed \gset
\if :recovery_topology_restored
\else
\warn 'Recovery topology finalization changed no row.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

cleanup_recovered_candidate() {
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=candidate_db="$CANDIDATE_DB" <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT 'menuplan-restore-candidate:' || restore_run_id || ':' || resource_token::text AS candidate_marker FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() \gset
SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db') AS candidate_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS candidate_owned \gset
\if :candidate_exists
\if :candidate_owned
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'candidate_db' AND pid <> pg_backend_pid();
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
DROP DATABASE :"candidate_db";
\else
\warn 'Fremder Kandidat wird während Recovery nicht gelöscht.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\endif
SQL
}

restore_recover() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  restore_recover_topology
  allow_state=$(control_psql --quiet --tuples-only --no-align <<'SQL'
SELECT CASE WHEN EXISTS ( SELECT 1 FROM pg_database WHERE datname = :'database_name' AND datallowconn ) THEN 'allowed' ELSE 'blocked' END;
SQL
  )
  [ "$allow_state" = allowed ] || { echo 'Wiederhergestellte Datenbank erlaubt keine Verbindungen.' >&2; exit 1; }
  verify_database "$DB"
  recovery_target=$(control_psql --quiet --tuples-only --no-align \
    --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" <<'SQL'
SELECT recovery_target FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid;
SQL
  )
  case "$recovery_target" in
    old)
      persist_old_database_proof
      cleanup_recovered_candidate
      recovery_from_lifecycle=recovery_topology_restored
      ;;
    candidate)
      recovery_from_lifecycle=recovery_candidate_ready
      ;;
    *) echo 'Recovery-Ziel fehlt oder ist unbekannt.' >&2; exit 73 ;;
  esac
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=recovery_target="$recovery_target" --set=recovery_from_lifecycle="$recovery_from_lifecycle" <<'SQL' >/dev/null
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = 'recovery_ready', last_event = 'recovery_ready', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND recovery_target = :'recovery_target' AND lifecycle = :'recovery_from_lifecycle' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS recovery_ready FROM changed \gset
\if :recovery_ready
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'recovery_ready' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
\warn 'Recovery-ready transition changed no row.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

case "$MODE" in
  once) backup_once ;;
  loop)
    while true; do
      backup_once
      sleep "$INTERVAL"
    done
    ;;
  restore-acquire) restore_acquire "${2:-}" ;;
  restore-takeover) restore_takeover "${2:-}" ;;
  restore-recovery-acquire) restore_recovery_acquire "${2:-}" ;;
  restore-hold) restore_hold "${2:-}" "${3:-}" ;;
  restore-assert-held) restore_assert_held "${2:-}" "${3:-}" ;;
  restore-assert-complete-target) restore_assert_complete_target "${2:-}" "${3:-}" ;;
  restore-complete-services-running) restore_mark_complete_services_running "${2:-}" "${3:-}" ;;
  restore-stage) restore_stage "${2:-}" "${3:-}" "${4:-}" "${5:-}" ;;
  restore-state) restore_state "${2:-}" "${3:-}" "${4:-}" ;;
  restore-abort|restore-cleanup-candidate) restore_abort "${2:-}" "${3:-}" ;;
  restore-promote) restore_promote "${2:-}" "${3:-}" ;;
  restore-recover|restore-rollback) restore_recover "${2:-}" "${3:-}" ;;
  restore-ensure-auth-capabilities) restore_ensure_auth_capabilities "${2:-}" "${3:-}" "${4:-}" ;;
  restore-reset-auth-capabilities) restore_reset_auth_capabilities "${2:-}" "${3:-}" "${4:-}" ;;
  restore-prune-retained) restore_prune_retained ;;
  *) echo "Unbekannter Modus: $MODE" >&2; exit 2 ;;
esac
