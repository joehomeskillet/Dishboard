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
    --set=ON_ERROR_STOP=1 --set=database_name="$DB" --set=lease_seconds="$LEASE_SECONDS" "$@"
}

ensure_control_tables() {
  control_psql --quiet >/dev/null <<'SQL'
CREATE TABLE IF NOT EXISTS public.menuplan_restore_control ( database_name text PRIMARY KEY, restore_run_id text NOT NULL, owner_run_id text NOT NULL, owner_token uuid NOT NULL, resource_token uuid NOT NULL, candidate_database text NOT NULL, rollback_database text NOT NULL, failed_database text NOT NULL, lifecycle text NOT NULL, recovery_from_state text, lease_expires_at timestamptz NOT NULL, original_comment text, old_database_verified boolean NOT NULL DEFAULT false, takeover_count integer NOT NULL DEFAULT 0, last_event text NOT NULL, updated_at timestamptz NOT NULL DEFAULT clock_timestamp() );
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS old_database_verified boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS public.menuplan_restore_audit ( event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, database_name text NOT NULL, restore_run_id text NOT NULL, owner_run_id text NOT NULL, owner_token uuid NOT NULL, lifecycle text NOT NULL, event text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT clock_timestamp() );
CREATE OR REPLACE FUNCTION public.menuplan_restore_renew( p_database_name text, p_restore_run_id text, p_owner_token uuid, p_lease_seconds integer ) RETURNS void LANGUAGE plpgsql AS $$ BEGIN UPDATE public.menuplan_restore_control SET lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds), updated_at = clock_timestamp() WHERE database_name = p_database_name AND restore_run_id = p_restore_run_id AND owner_token = p_owner_token AND lease_expires_at > clock_timestamp();
IF NOT FOUND THEN RAISE EXCEPTION 'restore lease is missing, foreign, or expired';
END IF;
END;
$$;
REVOKE ALL ON FUNCTION public.menuplan_restore_renew(text, text, uuid, integer) FROM PUBLIC;
SQL
}

restore_acquire() {
  validate_restore_run "$1"
  ensure_control_tables
  control_psql --quiet --tuples-only --no-align \
    --set=restore_run_id="$RESTORE_RUN_ID" --set=candidate_db="$CANDIDATE_DB" \
    --set=rollback_db="$ROLLBACK_DB" --set=failed_db="$FAILED_DB" <<'SQL'
\set QUIET 1
BEGIN;
SELECT pg_try_advisory_xact_lock(hashtextextended('menuplan-restore:' || :'database_name', 0)) AS gate_open \gset
\if :gate_open
SELECT gen_random_uuid()::text AS requested_owner_token, gen_random_uuid()::text AS requested_resource_token \gset
INSERT INTO public.menuplan_restore_control ( database_name, restore_run_id, owner_run_id, owner_token, resource_token, candidate_database, rollback_database, failed_database, lifecycle, lease_expires_at, original_comment, takeover_count, last_event, updated_at ) VALUES ( :'database_name', :'restore_run_id', :'restore_run_id', :'requested_owner_token'::uuid, :'requested_resource_token'::uuid, :'candidate_db', :'rollback_db', :'failed_db', 'acquired', clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), NULL, 0, 'lease_acquired', clock_timestamp() ) ON CONFLICT (database_name) DO UPDATE SET restore_run_id = EXCLUDED.restore_run_id, owner_run_id = EXCLUDED.owner_run_id, owner_token = EXCLUDED.owner_token, resource_token = EXCLUDED.resource_token, candidate_database = EXCLUDED.candidate_database, rollback_database = EXCLUDED.rollback_database, failed_database = EXCLUDED.failed_database, lifecycle = 'acquired', recovery_from_state = NULL, lease_expires_at = EXCLUDED.lease_expires_at, original_comment = NULL, old_database_verified = false, takeover_count = 0, last_event = 'lease_acquired', updated_at = clock_timestamp() WHERE menuplan_restore_control.lifecycle IN ('complete', 'aborted');
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND owner_token = :'requested_owner_token'::uuid ) AS lease_acquired \gset
\if :lease_acquired
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) VALUES (:'database_name', :'restore_run_id', :'restore_run_id', :'requested_owner_token'::uuid, 'acquired', 'lease_acquired');
COMMIT;
\echo :requested_owner_token
\else
ROLLBACK;
\warn 'Restore lease is active or incomplete; use explicit recovery takeover after expiry.'
SELECT 1 / 0;
\endif
\else
ROLLBACK;
\warn 'Restore lease is held by another host.'
SELECT 1 / 0;
\endif
SQL
}

restore_takeover() {
  new_owner_run_id=${1:-}
  case "$new_owner_run_id" in
    ''|*[!A-Za-z0-9_]*) echo 'Recovery-Owner-Laufkennung fehlt oder ist unsicher.' >&2; exit 1 ;;
  esac
  case "$DB" in
    ''|[0-9]*|*[!A-Za-z0-9_]*|postgres|template0|template1) echo "Unsicherer PostgreSQL-Datenbankname: $DB" >&2; exit 1 ;;
  esac
  ensure_control_tables
  control_psql --quiet --tuples-only --no-align --set=new_owner_run_id="$new_owner_run_id" <<'SQL'
\set QUIET 1
BEGIN;
SELECT pg_try_advisory_xact_lock(hashtextextended('menuplan-restore:' || :'database_name', 0)) AS gate_open \gset
\if :gate_open
SELECT gen_random_uuid()::text AS requested_owner_token \gset
UPDATE public.menuplan_restore_control SET owner_run_id = :'new_owner_run_id', owner_token = :'requested_owner_token'::uuid, lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), takeover_count = takeover_count + 1, last_event = 'lease_expired_takeover', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND lifecycle NOT IN ('complete', 'aborted') AND lease_expires_at <= clock_timestamp();
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND owner_token = :'requested_owner_token'::uuid ) AS takeover_acquired \gset
\if :takeover_acquired
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'lease_expired_takeover' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
SELECT restore_run_id, owner_token::text AS replacement_token FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
COMMIT;
\echo :restore_run_id :replacement_token
\else
ROLLBACK;
\warn 'No expired incomplete restore lease is available for takeover.'
SELECT 1 / 0;
\endif
\else
ROLLBACK;
\warn 'Restore lease holder is still connected.'
SELECT 1 / 0;
\endif
SQL
}

restore_state() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  next_state=${3:-}
  case "$next_state" in
    migrated|candidate_validated|services_stopped|live_validated|complete) ;;
    *) echo "Unzulässiger Restore-Lifecycle: $next_state" >&2; exit 1 ;;
  esac
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=next_state="$next_state" <<'SQL' >/dev/null
\set QUIET 1
BEGIN;
SELECT pg_advisory_xact_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = :'next_state', lease_expires_at = CASE WHEN :'next_state' = 'complete' THEN clock_timestamp() ELSE clock_timestamp() + make_interval(secs => :'lease_seconds'::integer) END, last_event = 'state:' || :'next_state', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() AND CASE :'next_state' WHEN 'migrated' THEN lifecycle IN ('candidate_ready', 'migrated') WHEN 'candidate_validated' THEN lifecycle IN ('migrated', 'candidate_validated') WHEN 'services_stopped' THEN lifecycle IN ('candidate_validated', 'services_stopped') WHEN 'live_validated' THEN lifecycle IN ('promoted', 'live_validated') WHEN 'complete' THEN lifecycle IN ('live_validated', 'recovery_ready') ELSE false END RETURNING 1 ) SELECT count(*) = 1 AS state_changed FROM changed \gset
\if :state_changed
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, last_event FROM public.menuplan_restore_control WHERE database_name = :'database_name';
COMMIT;
\else
ROLLBACK;
\warn 'Restore lease is missing, foreign, or expired.'
SELECT 1 / 0;
\endif
SQL
}

restore_hold() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  heartbeat_seconds=$((LEASE_SECONDS / 3))
  [ "$heartbeat_seconds" -ge 1 ] || heartbeat_seconds=1
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=heartbeat_seconds="$heartbeat_seconds" <<'SQL'
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
UPDATE public.menuplan_restore_control SET lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'lease_held', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND last_event = 'lease_held' ) AS holder_ready \gset
\if :holder_ready
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'lease_held' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
\warn 'Restore lease holder could not attach.'
SELECT 1 / 0;
\endif
WITH renewed AS ( UPDATE public.menuplan_restore_control SET lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'lease_heartbeat', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT CASE WHEN count(*) = 1 THEN 1 ELSE 1 / 0 END FROM renewed;
\watch :heartbeat_seconds
SQL
}

restore_assert_held() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  held=$(control_psql --quiet --tuples-only --no-align --set=restore_run_id="$RESTORE_RUN_ID" \
    --set=owner_token="$OWNER_TOKEN" <<'SQL'
SELECT CASE WHEN EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() AND last_event IN ('lease_held', 'lease_heartbeat') ) THEN 'held' ELSE 'missing' END;
SQL
  )
  [ "$held" = held ] || { echo 'PostgreSQL-weite Restore-Lease konnte nicht gehalten werden.' >&2; exit 73; }
}

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
SELECT 1 / 0;
\endif
\else
\warn 'Restore lease is missing, foreign, or expired.'
SELECT 1 / 0;
\endif
SQL
}

restore_abort() {
  validate_restore_run "$1"
  validate_owner_token "$2"
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
SELECT 1 / 0;
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
SELECT 1 / 0;
\endif
SQL
}

restore_stage() {
  source_file=$1
  checksum_file=$2
  validate_restore_run "$3"
  validate_owner_token "$4"
  restore_state_internal=staging
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=next_state="$restore_state_internal" <<'SQL' >/dev/null
\set QUIET 1
BEGIN;
SELECT pg_advisory_xact_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
UPDATE public.menuplan_restore_control SET lifecycle = :'next_state', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'state:' || :'next_state', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'acquired' AND lease_expires_at > clock_timestamp();
SELECT EXISTS (SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lifecycle = 'staging') AS state_changed \gset
\if :state_changed
COMMIT;
\else
ROLLBACK;
\warn 'Restore stage requires the acquired lease state.'
SELECT 1 / 0;
\endif
SQL
  verify_checksum restore-stage "$source_file" "$checksum_file"
  pg_restore --list "$source_file" >/dev/null

  cleanup_staging_failure() {
    status=$?
    trap - 0 1 2 15
    [ "$status" -eq 0 ] && exit 0
    restore_abort "$RESTORE_RUN_ID" "$OWNER_TOKEN" || status=1
    exit "$status"
  }
  trap cleanup_staging_failure 0
  trap 'exit 130' 1 2 15

  create_candidate
  pg_restore --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --no-owner --no-privileges --exit-on-error "$source_file"
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$CANDIDATE_DB" \
    --set=ON_ERROR_STOP=1 --command='CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;' >/dev/null
  verify_database "$CANDIDATE_DB"
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" <<'SQL' >/dev/null
UPDATE public.menuplan_restore_control SET lifecycle = 'candidate_ready', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), last_event = 'candidate_ready', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'candidate_created' AND lease_expires_at > clock_timestamp();
SQL
  trap - 0 1 2 15
  echo "$CANDIDATE_DB"
}

restore_promote() {
  validate_restore_run "$1"
  validate_owner_token "$2"
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
\quit 0
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
SELECT 1 / 0;
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
SELECT 1 / 0;
\endif
\else
\warn 'Fremde oder vorhandene Rollback-Datenbank wird nicht verändert.'
SELECT 1 / 0;
\endif
\else
\warn 'Fremder Restore-Kandidat wird nicht verändert.'
SELECT 1 / 0;
\endif
\else
\warn 'Restore promotion requires a valid candidate and nonexpired owner lease.'
SELECT 1 / 0;
\endif
SQL
}

restore_recover_topology() {
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=candidate_db="$CANDIDATE_DB" --set=rollback_db="$ROLLBACK_DB" <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT EXISTS (SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle NOT IN ('complete', 'aborted') AND lease_expires_at > clock_timestamp()) AS lease_ok \gset
\if :lease_ok
UPDATE public.menuplan_restore_control SET recovery_from_state = COALESCE(recovery_from_state, lifecycle), lifecycle = 'recovery_started', last_event = 'recovery_started', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name';
SELECT 'menuplan-restore-candidate:' || restore_run_id || ':' || resource_token::text AS candidate_marker, 'menuplan-restore-rollback:' || restore_run_id || ':' || resource_token::text AS rollback_marker FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name') AS production_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS production_is_candidate, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name' AND shobj_description(oid, 'pg_database') = :'rollback_marker') AS production_is_marked_old, EXISTS (SELECT 1 FROM pg_database p JOIN public.menuplan_restore_control c ON c.database_name = :'database_name' WHERE p.datname = :'database_name' AND shobj_description(p.oid, 'pg_database') IS NOT DISTINCT FROM c.original_comment AND (c.old_database_verified OR c.recovery_from_state IN ('acquired', 'staging', 'candidate_create_pending', 'candidate_created', 'candidate_ready', 'migrated', 'candidate_validated', 'services_stopped', 'promotion_started'))) AS production_is_original, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'rollback_db') AS rollback_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'rollback_db' AND shobj_description(oid, 'pg_database') = :'rollback_marker') AS rollback_owned, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db') AS candidate_exists, EXISTS (SELECT 1 FROM pg_database WHERE datname = :'candidate_db' AND shobj_description(oid, 'pg_database') = :'candidate_marker') AS candidate_owned \gset
\if :rollback_exists
\if :rollback_owned
\else
\warn 'Fremde Rollback-Datenbank blockiert Recovery.'
SELECT 1 / 0;
\endif
\endif
\if :production_is_candidate
\if :rollback_owned
\if :candidate_exists
\warn 'Vorhandener Kandidatenname blockiert sichere Recovery.'
SELECT 1 / 0;
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
SELECT 1 / 0;
\endif
\elif :production_exists
\if :production_is_marked_old
\elif :production_is_original
\else
\warn 'Produktionsname gehört keinem beweisbaren alten Datenbankstand.'
SELECT 1 / 0;
\endif
\elif :rollback_owned
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"rollback_db" RENAME TO :"database_name";
\else
\warn 'Alter Datenbankstand ist nicht beweisbar vorhanden.'
SELECT 1 / 0;
\endif
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
SELECT format('COMMENT ON DATABASE %I IS %L;', :'database_name', original_comment) FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gexec
SELECT public.menuplan_restore_renew(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer);
ALTER DATABASE :"database_name" ALLOW_CONNECTIONS true;
UPDATE public.menuplan_restore_control SET lifecycle = 'recovery_topology_restored', last_event = 'recovery_topology_restored', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp();
\else
\warn 'Restore recovery requires the same nonexpired owner token.'
SELECT 1 / 0;
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
SELECT 1 / 0;
\endif
\endif
SQL
}

restore_recover() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_recover_topology
  allow_state=$(control_psql --quiet --tuples-only --no-align <<'SQL'
SELECT CASE WHEN EXISTS ( SELECT 1 FROM pg_database WHERE datname = :'database_name' AND datallowconn ) THEN 'allowed' ELSE 'blocked' END;
SQL
  )
  [ "$allow_state" = allowed ] || { echo 'Wiederhergestellte Datenbank erlaubt keine Verbindungen.' >&2; exit 1; }
  verify_database "$DB"
  cleanup_recovered_candidate
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" <<'SQL' >/dev/null
UPDATE public.menuplan_restore_control SET lifecycle = 'recovery_ready', last_event = 'recovery_ready', old_database_verified = true, lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'recovery_topology_restored' AND lease_expires_at > clock_timestamp();
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'recovery_ready' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
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
  restore-hold) restore_hold "${2:-}" "${3:-}" ;;
  restore-assert-held) restore_assert_held "${2:-}" "${3:-}" ;;
  restore-stage) restore_stage "${2:-}" "${3:-}" "${4:-}" "${5:-}" ;;
  restore-state) restore_state "${2:-}" "${3:-}" "${4:-}" ;;
  restore-abort|restore-cleanup-candidate) restore_abort "${2:-}" "${3:-}" ;;
  restore-promote) restore_promote "${2:-}" "${3:-}" ;;
  restore-recover|restore-rollback) restore_recover "${2:-}" "${3:-}" ;;
  *) echo "Unbekannter Modus: $MODE" >&2; exit 2 ;;
esac
