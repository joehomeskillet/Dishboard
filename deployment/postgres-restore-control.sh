#!/bin/sh
# Sourced by postgres-backup.sh. The caller supplies validated connection settings,
# control_psql, validate_restore_run, and validate_owner_token.

ensure_control_tables() {
  control_psql --quiet >/dev/null <<'SQL'
CREATE TABLE IF NOT EXISTS public.menuplan_restore_control ( database_name text PRIMARY KEY, restore_run_id text NOT NULL, owner_run_id text NOT NULL, owner_token uuid NOT NULL, resource_token uuid NOT NULL, candidate_database text NOT NULL, rollback_database text NOT NULL, failed_database text NOT NULL, lifecycle text NOT NULL, recovery_from_state text, recovery_target text, lease_expires_at timestamptz NOT NULL, controller_heartbeat_at timestamptz, holder_backend_pid integer, holder_backend_start timestamptz, holder_application_name text, original_comment text, old_database_verified boolean NOT NULL DEFAULT false, resume_from_complete boolean NOT NULL DEFAULT false, rollback_retain_until timestamptz, takeover_count integer NOT NULL DEFAULT 0, last_event text NOT NULL, updated_at timestamptz NOT NULL DEFAULT clock_timestamp() );
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS old_database_verified boolean NOT NULL DEFAULT false;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS recovery_target text;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS controller_heartbeat_at timestamptz;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS holder_backend_pid integer;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS holder_backend_start timestamptz;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS holder_application_name text;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS resume_from_complete boolean NOT NULL DEFAULT false;
ALTER TABLE public.menuplan_restore_control ADD COLUMN IF NOT EXISTS rollback_retain_until timestamptz;
CREATE TABLE IF NOT EXISTS public.menuplan_restore_audit ( event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, database_name text NOT NULL, restore_run_id text NOT NULL, owner_run_id text NOT NULL, owner_token uuid NOT NULL, lifecycle text NOT NULL, event text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT clock_timestamp() );
CREATE TABLE IF NOT EXISTS public.menuplan_restore_retained ( database_name text NOT NULL, restore_run_id text NOT NULL, owner_run_id text NOT NULL, owner_token uuid NOT NULL, resource_token uuid NOT NULL, rollback_database text NOT NULL UNIQUE, rollback_marker text NOT NULL, retain_until timestamptz NOT NULL, pruned_at timestamptz, PRIMARY KEY (database_name, restore_run_id) );
CREATE OR REPLACE FUNCTION public.menuplan_restore_renew( p_database_name text, p_restore_run_id text, p_owner_token uuid, p_lease_seconds integer ) RETURNS void LANGUAGE plpgsql AS $$ BEGIN UPDATE public.menuplan_restore_control c SET lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds), updated_at = clock_timestamp() WHERE c.database_name = p_database_name AND c.restore_run_id = p_restore_run_id AND c.owner_token = p_owner_token AND c.lease_expires_at > clock_timestamp() AND EXISTS ( SELECT 1 FROM pg_stat_activity a JOIN pg_locks l ON l.pid = a.pid AND l.locktype = 'advisory' AND l.mode = 'ShareLock' AND l.granted WHERE a.pid = c.holder_backend_pid AND a.backend_start = c.holder_backend_start AND a.application_name = c.holder_application_name );
IF NOT FOUND THEN RAISE EXCEPTION 'restore lease is missing, foreign, or expired';
END IF;
END;
$$;
REVOKE ALL ON FUNCTION public.menuplan_restore_renew(text, text, uuid, integer) FROM PUBLIC;
CREATE OR REPLACE FUNCTION public.menuplan_restore_holder_heartbeat( p_database_name text, p_restore_run_id text, p_owner_token uuid, p_lease_seconds integer, p_controller_timeout integer ) RETURNS void LANGUAGE plpgsql AS $$ BEGIN UPDATE public.menuplan_restore_control c SET lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds), last_event = 'lease_heartbeat', updated_at = clock_timestamp() WHERE c.database_name = p_database_name AND c.restore_run_id = p_restore_run_id AND c.owner_token = p_owner_token AND c.holder_backend_pid = pg_backend_pid() AND c.lease_expires_at > clock_timestamp() AND c.controller_heartbeat_at > clock_timestamp() - make_interval(secs => p_controller_timeout) AND EXISTS ( SELECT 1 FROM pg_stat_activity a JOIN pg_locks l ON l.pid = a.pid AND l.locktype = 'advisory' AND l.mode = 'ShareLock' AND l.granted WHERE a.pid = c.holder_backend_pid AND a.backend_start = c.holder_backend_start AND a.application_name = c.holder_application_name );
IF NOT FOUND THEN RAISE EXCEPTION 'restore holder lost lease, advisory lock, or controller heartbeat';
END IF;
END;
$$;
REVOKE ALL ON FUNCTION public.menuplan_restore_holder_heartbeat(text, text, uuid, integer, integer) FROM PUBLIC;
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
SELECT NOT EXISTS (SELECT 1 FROM public.menuplan_restore_audit WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id') AND NOT EXISTS (SELECT 1 FROM public.menuplan_restore_retained WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id') AS run_id_unused \gset
\if :run_id_unused
INSERT INTO public.menuplan_restore_control ( database_name, restore_run_id, owner_run_id, owner_token, resource_token, candidate_database, rollback_database, failed_database, lifecycle, lease_expires_at, original_comment, takeover_count, last_event, updated_at ) VALUES ( :'database_name', :'restore_run_id', :'restore_run_id', :'requested_owner_token'::uuid, :'requested_resource_token'::uuid, :'candidate_db', :'rollback_db', :'failed_db', 'acquired', clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), NULL, 0, 'lease_acquired', clock_timestamp() ) ON CONFLICT (database_name) DO UPDATE SET restore_run_id = EXCLUDED.restore_run_id, owner_run_id = EXCLUDED.owner_run_id, owner_token = EXCLUDED.owner_token, resource_token = EXCLUDED.resource_token, candidate_database = EXCLUDED.candidate_database, rollback_database = EXCLUDED.rollback_database, failed_database = EXCLUDED.failed_database, lifecycle = 'acquired', recovery_from_state = NULL, recovery_target = NULL, lease_expires_at = EXCLUDED.lease_expires_at, controller_heartbeat_at = NULL, holder_backend_pid = NULL, holder_backend_start = NULL, holder_application_name = NULL, original_comment = NULL, old_database_verified = false, resume_from_complete = false, rollback_retain_until = NULL, takeover_count = 0, last_event = 'lease_acquired', updated_at = clock_timestamp() WHERE menuplan_restore_control.lifecycle IN ('complete', 'aborted');
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND owner_token = :'requested_owner_token'::uuid ) AS lease_acquired \gset
\if :lease_acquired
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) VALUES (:'database_name', :'restore_run_id', :'restore_run_id', :'requested_owner_token'::uuid, 'acquired', 'lease_acquired');
COMMIT;
\echo :requested_owner_token
\else
ROLLBACK;
\warn 'Restore lease is active or incomplete; use explicit recovery takeover after expiry.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
ROLLBACK;
\warn 'Restore run id was already used and cannot be reused.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
ROLLBACK;
\warn 'Restore lease is held by another host.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
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
UPDATE public.menuplan_restore_control SET owner_run_id = :'new_owner_run_id', owner_token = :'requested_owner_token'::uuid, lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), controller_heartbeat_at = NULL, holder_backend_pid = NULL, holder_backend_start = NULL, holder_application_name = NULL, takeover_count = takeover_count + 1, last_event = 'lease_expired_takeover', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND lifecycle NOT IN ('complete', 'aborted') AND lease_expires_at <= clock_timestamp();
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND owner_token = :'requested_owner_token'::uuid ) AS takeover_acquired \gset
\if :takeover_acquired
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'lease_expired_takeover' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
SELECT restore_run_id, owner_token::text AS replacement_token FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
COMMIT;
\echo :restore_run_id :replacement_token
\else
ROLLBACK;
\warn 'No expired incomplete restore lease is available for takeover.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
ROLLBACK;
\warn 'Restore lease holder is still connected.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_recovery_acquire() {
  new_owner_run_id=${1:-}
  case "$new_owner_run_id" in
    ''|*[!A-Za-z0-9_]*) echo 'Recovery-Owner-Laufkennung fehlt oder ist unsicher.' >&2; exit 1 ;;
  esac
  ensure_control_tables
  control_psql --quiet --tuples-only --no-align --set=new_owner_run_id="$new_owner_run_id" <<'SQL'
\set QUIET 1
BEGIN;
SELECT pg_try_advisory_xact_lock(hashtextextended('menuplan-restore:' || :'database_name', 0)) AS gate_open \gset
\if :gate_open
SELECT gen_random_uuid()::text AS requested_owner_token \gset
WITH changed AS (
  UPDATE public.menuplan_restore_control c
  SET owner_run_id = :'new_owner_run_id', owner_token = :'requested_owner_token'::uuid,
      lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer),
      controller_heartbeat_at = NULL, holder_backend_pid = NULL,
      holder_backend_start = NULL, holder_application_name = NULL,
      resume_from_complete = c.lifecycle = 'complete',
      takeover_count = takeover_count + 1,
      last_event = CASE WHEN c.lifecycle = 'complete' THEN 'complete_resume_acquired' ELSE 'lease_expired_takeover' END,
      updated_at = clock_timestamp()
  WHERE c.database_name = :'database_name' AND c.lifecycle <> 'aborted'
    AND (c.lifecycle = 'complete' OR c.lease_expires_at <= clock_timestamp()
      OR (COALESCE(c.controller_heartbeat_at, c.updated_at) <= clock_timestamp() - make_interval(secs => :'controller_timeout'::integer)
        AND NOT EXISTS ( SELECT 1 FROM pg_stat_activity a WHERE a.pid = c.holder_backend_pid
          AND a.backend_start = c.holder_backend_start
          AND a.application_name = c.holder_application_name )))
  RETURNING c.*
)
SELECT count(*) = 1 AS recovery_acquired FROM changed \gset
\if :recovery_acquired
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, last_event FROM public.menuplan_restore_control WHERE database_name = :'database_name';
SELECT restore_run_id, owner_token::text AS replacement_token, CASE WHEN resume_from_complete THEN 'resume' ELSE 'recover' END AS recovery_action FROM public.menuplan_restore_control WHERE database_name = :'database_name' \gset
COMMIT;
\echo :restore_run_id :replacement_token :recovery_action
\else
ROLLBACK;
\warn 'No recoverable restore state is available.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
\else
ROLLBACK;
\warn 'Restore lease holder is still connected.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_assert_complete_target() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" \
    --set=owner_token="$OWNER_TOKEN" <<'SQL' >/dev/null
\set QUIET 1
SELECT EXISTS (
  SELECT 1 FROM public.menuplan_restore_control c
  JOIN pg_database d ON d.datname = c.database_name AND d.datallowconn
  WHERE c.database_name = :'database_name' AND c.restore_run_id = :'restore_run_id'
    AND c.owner_token = :'owner_token'::uuid AND c.lifecycle = 'complete'
    AND c.lease_expires_at > clock_timestamp()
    AND CASE WHEN c.recovery_target = 'old' THEN c.old_database_verified
      AND shobj_description(d.oid, 'pg_database') IS NOT DISTINCT FROM c.original_comment
      ELSE shobj_description(d.oid, 'pg_database') =
        'menuplan-restore-candidate:' || c.restore_run_id || ':' || c.resource_token::text
    END
) AS completed_target_proven \gset
\if :completed_target_proven
\else
\warn 'Completed restore target is not safely resumable.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
  verify_database "$DB"
}

restore_mark_complete_services_running() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" \
    --set=owner_token="$OWNER_TOKEN" <<'SQL' >/dev/null
WITH changed AS ( UPDATE public.menuplan_restore_control SET resume_from_complete = false, last_event = 'complete_services_running', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lifecycle = 'complete' AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS services_recorded FROM changed \gset
\if :services_recorded
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'complete_services_running' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_state() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  next_state=${3:-}
  case "$next_state" in
    migrated|candidate_validated|services_stopped|live_validated|writer_release_committed|app_validated|complete) ;;
    *) echo "Unzulässiger Restore-Lifecycle: $next_state" >&2; exit 1 ;;
  esac
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=next_state="$next_state" <<'SQL' >/dev/null
\set QUIET 1
BEGIN;
SELECT pg_advisory_xact_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
WITH changed AS ( UPDATE public.menuplan_restore_control SET lifecycle = :'next_state', lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), rollback_retain_until = CASE WHEN :'next_state' = 'complete' THEN COALESCE(rollback_retain_until, clock_timestamp() + make_interval(secs => :'rollback_retention_seconds'::integer)) ELSE rollback_retain_until END, last_event = 'state:' || :'next_state', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() AND CASE :'next_state' WHEN 'migrated' THEN lifecycle IN ('candidate_ready', 'migrated') WHEN 'candidate_validated' THEN lifecycle IN ('migrated', 'candidate_validated') WHEN 'services_stopped' THEN lifecycle IN ('candidate_validated', 'services_stopped') WHEN 'live_validated' THEN lifecycle IN ('promoted', 'live_validated') WHEN 'writer_release_committed' THEN lifecycle IN ('live_validated', 'writer_release_committed') WHEN 'app_validated' THEN lifecycle IN ('writer_release_committed', 'recovery_ready', 'app_validated') WHEN 'complete' THEN lifecycle = 'app_validated' ELSE false END RETURNING 1 ) SELECT count(*) = 1 AS state_changed FROM changed \gset
\if :state_changed
INSERT INTO public.menuplan_restore_retained (database_name, restore_run_id, owner_run_id, owner_token, resource_token, rollback_database, rollback_marker, retain_until) SELECT database_name, restore_run_id, owner_run_id, owner_token, resource_token, rollback_database, 'menuplan-restore-rollback:' || restore_run_id || ':' || resource_token::text, rollback_retain_until FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND lifecycle = 'complete' AND EXISTS (SELECT 1 FROM pg_database WHERE datname = rollback_database) ON CONFLICT (database_name, restore_run_id) DO UPDATE SET retain_until = EXCLUDED.retain_until;
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, last_event FROM public.menuplan_restore_control WHERE database_name = :'database_name';
COMMIT;
\else
ROLLBACK;
\warn 'Restore lease is missing, foreign, or expired.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_hold() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  [ "$LEASE_SECONDS" -ge 3 ] || {
    echo 'RESTORE_LEASE_SECONDS muss für einen Holder mindestens 3 sein.' >&2
    exit 73
  }
  heartbeat_seconds=$((CONTROLLER_TIMEOUT / 3))
  lease_heartbeat_seconds=$((LEASE_SECONDS / 3))
  [ "$lease_heartbeat_seconds" -ge "$heartbeat_seconds" ] || heartbeat_seconds=$lease_heartbeat_seconds
  [ "$heartbeat_seconds" -ge 1 ] || heartbeat_seconds=1
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=heartbeat_seconds="$heartbeat_seconds" <<'SQL'
\set QUIET 1
SELECT set_config('application_name', 'menuplan_restore_holder:' || resource_token::text, false) AS holder_application_name FROM public.menuplan_restore_control WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid \gset
SELECT pg_advisory_lock_shared(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT pg_backend_pid() AS holder_backend_pid, backend_start AS holder_backend_start FROM pg_stat_activity WHERE pid = pg_backend_pid() \gset
WITH changed AS ( UPDATE public.menuplan_restore_control SET lease_expires_at = clock_timestamp() + make_interval(secs => :'lease_seconds'::integer), controller_heartbeat_at = clock_timestamp(), holder_backend_pid = :'holder_backend_pid'::integer, holder_backend_start = :'holder_backend_start'::timestamptz, holder_application_name = :'holder_application_name', last_event = 'lease_held', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS holder_ready FROM changed \gset
\if :holder_ready
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, 'lease_held' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
\warn 'Restore lease holder could not attach.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SELECT public.menuplan_restore_holder_heartbeat(:'database_name', :'restore_run_id', :'owner_token'::uuid, :'lease_seconds'::integer, :'controller_timeout'::integer);
\watch :heartbeat_seconds
SQL
}

restore_assert_held() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" \
    --set=owner_token="$OWNER_TOKEN" <<'SQL' >/dev/null
\set QUIET 1
WITH held AS ( SELECT c.database_name FROM public.menuplan_restore_control c JOIN pg_stat_activity a ON a.pid = c.holder_backend_pid AND a.backend_start = c.holder_backend_start AND a.application_name = c.holder_application_name WHERE c.database_name = :'database_name' AND c.restore_run_id = :'restore_run_id' AND c.owner_token = :'owner_token'::uuid AND c.lease_expires_at > clock_timestamp() AND EXISTS ( SELECT 1 FROM pg_locks l WHERE l.pid = c.holder_backend_pid AND l.locktype = 'advisory' AND l.mode = 'ShareLock' AND l.granted ) ), pulsed AS ( UPDATE public.menuplan_restore_control c SET controller_heartbeat_at = clock_timestamp(), updated_at = clock_timestamp() FROM held WHERE c.database_name = held.database_name RETURNING 1 ) SELECT count(*) = 1 AS holder_live FROM pulsed \gset
\if :holder_live
\else
\warn 'PostgreSQL-weite Restore-Lease hat keinen lebenden Lock-Holder.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_prune_retained() {
  case "$DB" in
    ''|[0-9]*|*[!A-Za-z0-9_]*|postgres|template0|template1)
      echo "Unsicherer PostgreSQL-Datenbankname: $DB" >&2
      exit 1
      ;;
  esac
  ensure_control_tables
  control_psql --quiet <<'SQL' >/dev/null
\set QUIET 1
SELECT pg_advisory_lock(hashtextextended('menuplan-restore:' || :'database_name', 0));
SELECT EXISTS ( SELECT 1 FROM public.menuplan_restore_retained r JOIN pg_database d ON d.datname = r.rollback_database WHERE r.database_name = :'database_name' AND r.pruned_at IS NULL AND r.retain_until <= clock_timestamp() AND shobj_description(d.oid, 'pg_database') IS DISTINCT FROM r.rollback_marker ) AS foreign_due_database \gset
\if :foreign_due_database
\warn 'Fremd markierte Rollback-Datenbank wird nicht automatisch gelöscht.'
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
WITH missing AS ( UPDATE public.menuplan_restore_retained r SET pruned_at = clock_timestamp() WHERE r.database_name = :'database_name' AND r.pruned_at IS NULL AND r.retain_until <= clock_timestamp() AND NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname = r.rollback_database) RETURNING r.* ) INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, 'complete', 'rollback_retention_absent' FROM missing;
SELECT format('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %L AND pid <> pg_backend_pid();', r.rollback_database) FROM public.menuplan_restore_retained r JOIN pg_database d ON d.datname = r.rollback_database WHERE r.database_name = :'database_name' AND r.pruned_at IS NULL AND r.retain_until <= clock_timestamp() AND shobj_description(d.oid, 'pg_database') = r.rollback_marker ORDER BY r.retain_until, r.rollback_database \gexec
SELECT format('DROP DATABASE %I;', r.rollback_database) FROM public.menuplan_restore_retained r JOIN pg_database d ON d.datname = r.rollback_database WHERE r.database_name = :'database_name' AND r.pruned_at IS NULL AND r.retain_until <= clock_timestamp() AND shobj_description(d.oid, 'pg_database') = r.rollback_marker ORDER BY r.retain_until, r.rollback_database \gexec
WITH pruned AS ( UPDATE public.menuplan_restore_retained r SET pruned_at = clock_timestamp() WHERE r.database_name = :'database_name' AND r.pruned_at IS NULL AND r.retain_until <= clock_timestamp() AND NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname = r.rollback_database) RETURNING r.* ) INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, 'complete', 'rollback_retention_pruned' FROM pruned;
SELECT pg_advisory_unlock(hashtextextended('menuplan-restore:' || :'database_name', 0));
SQL
}

prepare_capability_target() {
  validate_restore_run "$1"
  validate_owner_token "$2"
  target_database=${3:-}
  case "$target_database" in
    production) target_database=$DB; required_lifecycle=production ;;
    "$CANDIDATE_DB") required_lifecycle=migrated ;;
    *) echo 'Capability-Zieldatenbank ist nicht leasegebunden.' >&2; exit 73 ;;
  esac
  restore_assert_held "$RESTORE_RUN_ID" "$OWNER_TOKEN"
  capability_allowed=$(control_psql --quiet --tuples-only --no-align \
    --set=restore_run_id="$RESTORE_RUN_ID" --set=owner_token="$OWNER_TOKEN" \
    --set=target_database="$target_database" --set=required_lifecycle="$required_lifecycle" <<'SQL'
SELECT CASE WHEN EXISTS ( SELECT 1 FROM public.menuplan_restore_control c JOIN pg_database d ON d.datname = :'target_database' WHERE c.database_name = :'database_name' AND c.restore_run_id = :'restore_run_id' AND c.owner_token = :'owner_token'::uuid AND ( (:'required_lifecycle' = 'production' AND c.lifecycle IN ('recovery_ready', 'complete')) OR c.lifecycle = :'required_lifecycle' ) AND c.lease_expires_at > clock_timestamp() AND ( :'target_database' = :'database_name' OR shobj_description(d.oid, 'pg_database') = 'menuplan-restore-candidate:' || c.restore_run_id || ':' || c.resource_token::text ) ) THEN 'allowed' ELSE 'blocked' END;
SQL
  )
  [ "$capability_allowed" = allowed ] || {
    echo 'Capability-Operation ist für Lease, Lifecycle oder Datenbank nicht erlaubt.' >&2
    exit 73
  }
}

record_capability_event() {
  event=$1
  control_psql --quiet --set=restore_run_id="$RESTORE_RUN_ID" \
    --set=owner_token="$OWNER_TOKEN" --set=required_lifecycle="$required_lifecycle" \
    --set=event="$event" <<'SQL' >/dev/null
WITH changed AS ( UPDATE public.menuplan_restore_control SET last_event = :'event', updated_at = clock_timestamp() WHERE database_name = :'database_name' AND restore_run_id = :'restore_run_id' AND owner_token = :'owner_token'::uuid AND ( (:'required_lifecycle' = 'production' AND lifecycle IN ('recovery_ready', 'complete')) OR lifecycle = :'required_lifecycle' ) AND lease_expires_at > clock_timestamp() RETURNING 1 ) SELECT count(*) = 1 AS event_recorded FROM changed \gset
\if :event_recorded
INSERT INTO public.menuplan_restore_audit (database_name, restore_run_id, owner_run_id, owner_token, lifecycle, event) SELECT database_name, restore_run_id, owner_run_id, owner_token, lifecycle, :'event' FROM public.menuplan_restore_control WHERE database_name = :'database_name';
\else
DO $failure$ BEGIN RAISE EXCEPTION USING MESSAGE = current_query(); END $failure$;
\endif
SQL
}

restore_ensure_auth_capabilities() {
  prepare_capability_target "$1" "$2" "$3"
  ensure_result=$(psql --host="$HOST" --port="$PORT" --username="$USER" \
    --dbname="$target_database" --set=ON_ERROR_STOP=1 --quiet --tuples-only --no-align \
    --command='SELECT cafeteria.ensure_auth_capability_state();')
  [ "$ensure_result" = 1 ] || {
    echo 'Capability-Schema-Reparatur bestätigte nicht exakt einen Zustand.' >&2
    exit 73
  }
  record_capability_event auth_capability_state_ensured
}

restore_reset_auth_capabilities() {
  prepare_capability_target "$1" "$2" "$3"
  psql --host="$HOST" --port="$PORT" --username="$USER" --dbname="$target_database" \
    --set=ON_ERROR_STOP=1 --quiet <<'SQL' >/dev/null
SET search_path TO cafeteria, public;
DO $capability_reset$
DECLARE
    hard_reset_result smallint;
BEGIN
    IF to_regclass('cafeteria.auth_capability_secrets') IS NULL
       OR to_regclass('cafeteria.auth_capability_nonces') IS NULL
       OR to_regprocedure('cafeteria.hard_reset_auth_capability_state()') IS NULL THEN
        RAISE EXCEPTION 'Capability-Schema oder privilegierter Reset-Pfad fehlt.';
    END IF;
    SELECT cafeteria.hard_reset_auth_capability_state() INTO hard_reset_result;
    IF hard_reset_result <> 1 THEN
        RAISE EXCEPTION 'Capability-Hard-Reset bestätigte nicht exakt ein neues Secret.';
    END IF;
    IF (SELECT count(*) FROM cafeteria.auth_capability_secrets) <> 1
       OR (SELECT count(*) FROM cafeteria.auth_capability_secrets WHERE active) <> 1
       OR EXISTS (SELECT 1 FROM cafeteria.auth_capability_nonces) THEN
        RAISE EXCEPTION 'Capability-Reset konnte nicht bewiesen werden.';
    END IF;
END
$capability_reset$;
SQL
  record_capability_event auth_capability_state_hard_reset
}
