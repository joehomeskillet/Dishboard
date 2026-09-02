#!/bin/sh
set -eu

RECOVERY_MODE=false
PRUNE_MODE=false
case "${1:-}" in
  --recover)
    [ "$#" -eq 1 ] || { echo "Verwendung: $0 --recover" >&2; exit 2; }
    RECOVERY_MODE=true
    ;;
  --prune-retained)
    [ "$#" -eq 1 ] || { echo "Verwendung: $0 --prune-retained" >&2; exit 2; }
    PRUNE_MODE=true
    ;;
  '')
    echo "Verwendung: $0 /absoluter/pfad/cafeteria-YYYYMMDDTHHMMSSZ.dump | --recover" >&2
    exit 2
    ;;
  *)
    [ "$#" -eq 1 ] || {
      echo "Verwendung: $0 /absoluter/pfad/cafeteria-YYYYMMDDTHHMMSSZ.dump | --recover" >&2
      exit 2
    }
    ;;
esac

cd "$(dirname "$0")"
backup_dir=
backup_name=
sha_file=

verify_checksum() {
  backup=$1
  [ -f "$backup" ] || { echo "Backup nicht gefunden: $backup" >&2; exit 1; }
  backup_dir=$(CDPATH= cd -- "$(dirname -- "$backup")" && pwd)
  backup_name=$(basename -- "$backup")
  sha_file="$backup.sha256"
  [ -f "$sha_file" ] || { echo "Checksum-Datei fehlt: $sha_file" >&2; exit 1; }

  exec 3< "$sha_file"
  if ! IFS=' ' read -r expected listed_name extra <&3; then
    exec 3<&-
    echo "Checksum-Datei ist leer: $sha_file" >&2
    exit 1
  fi
  if IFS= read -r extra_line <&3; then
    exec 3<&-
    echo "Checksum-Datei muss genau einen Eintrag enthalten: $sha_file" >&2
    exit 1
  fi
  exec 3<&-

  listed_name=${listed_name#\*}
  case "$expected" in
    ''|*[!0-9a-fA-F]*) echo "Ungültige SHA-256-Datei: $sha_file" >&2; exit 1 ;;
  esac
  [ "${#expected}" -eq 64 ] || { echo "Ungültige SHA-256-Datei: $sha_file" >&2; exit 1; }
  [ -z "$extra" ] && [ "$listed_name" = "$backup_name" ] || {
    echo "Checksum-Datei referenziert nicht exakt $backup_name." >&2
    exit 1
  }

  actual_line=$(sha256sum "$backup")
  actual=${actual_line%% *}
  [ "$actual" = "$expected" ] || { echo "SHA-256-Prüfung fehlgeschlagen: $backup" >&2; exit 1; }
}

restore_container() {
  if [ -n "$backup_dir" ]; then
    docker compose --profile ops run --rm --no-deps \
      -v "$backup_dir:/restore-source:ro" restore "$@"
  else
    docker compose --profile ops run --rm --no-deps restore "$@"
  fi
}

validate_run_id() {
  case "$restore_run_id" in
    ''|*[!A-Za-z0-9_]*) echo "Unsichere Restore-Laufkennung: $restore_run_id" >&2; exit 1 ;;
  esac
}

validate_owner_token() {
  case "$owner_token" in
    ''|*[!0-9a-fA-F-]*) echo 'Unsicherer Restore-Owner-Token.' >&2; exit 1 ;;
  esac
  [ "${#owner_token}" -eq 36 ] || { echo 'Ungültiger Restore-Owner-Token.' >&2; exit 1; }
}

lease_container=
lease_watchdog_pid=
lease_watchdog_status_file=
controller_heartbeat=${RESTORE_CONTROLLER_HEARTBEAT_SECONDS:-5}
controller_timeout=${RESTORE_CONTROLLER_TIMEOUT_SECONDS:-30}
case "$controller_heartbeat" in
  ''|*[!0-9]*) echo 'RESTORE_CONTROLLER_HEARTBEAT_SECONDS muss eine positive Ganzzahl sein.' >&2; exit 1 ;;
esac
[ "$controller_heartbeat" -ge 1 ] && [ "$controller_heartbeat" -le 60 ] || {
  echo 'RESTORE_CONTROLLER_HEARTBEAT_SECONDS muss zwischen 1 und 60 liegen.' >&2
  exit 1
}
case "$controller_timeout" in
  ''|*[!0-9]*) echo 'RESTORE_CONTROLLER_TIMEOUT_SECONDS muss eine positive Ganzzahl sein.' >&2; exit 1 ;;
esac
[ "$controller_timeout" -ge 2 ] && [ "$controller_timeout" -le 300 ] || {
  echo 'RESTORE_CONTROLLER_TIMEOUT_SECONDS muss zwischen 2 und 300 liegen.' >&2
  exit 1
}
[ $((controller_heartbeat * 2)) -le "$controller_timeout" ] || {
  echo 'RESTORE_CONTROLLER_HEARTBEAT_SECONDS muss höchstens halb so gross wie RESTORE_CONTROLLER_TIMEOUT_SECONDS sein.' >&2
  exit 1
}

start_lease_watchdog() {
  lease_watchdog_status_file=$(mktemp "${TMPDIR:-/tmp}/menuplan-restore-watchdog.XXXXXX")
  controller_pid=$$
  (
    while kill -0 "$controller_pid" 2>/dev/null; do
      if ! restore_container restore-assert-held "$restore_run_id" "$owner_token" >/dev/null 2>&1; then
        printf '%s\n' 'holder_or_heartbeat_lost' > "$lease_watchdog_status_file"
        docker compose stop app backup >/dev/null 2>&1 || true
        exit 73
      fi
      sleep "$controller_heartbeat"
    done
    printf '%s\n' 'controller_lost' > "$lease_watchdog_status_file"
    docker compose stop app backup >/dev/null 2>&1 || true
  ) &
  lease_watchdog_pid=$!
}

stop_lease_watchdog() {
  if [ -n "$lease_watchdog_pid" ]; then
    kill "$lease_watchdog_pid" >/dev/null 2>&1 || true
    wait "$lease_watchdog_pid" >/dev/null 2>&1 || true
    lease_watchdog_pid=
  fi
  if [ -n "$lease_watchdog_status_file" ]; then
    rm -f -- "$lease_watchdog_status_file"
    lease_watchdog_status_file=
  fi
}

assert_lease_holder() {
  [ -n "$lease_watchdog_pid" ] && kill -0 "$lease_watchdog_pid" 2>/dev/null || {
    echo 'Restore-Lease-Watchdog ist nicht aktiv.' >&2
    return 73
  }
  [ ! -s "$lease_watchdog_status_file" ] || {
    echo 'Restore-Lease-Watchdog meldet einen verlorenen Holder.' >&2
    return 73
  }
  restore_container restore-assert-held "$restore_run_id" "$owner_token" >/dev/null
}

start_lease_holder() {
  token_prefix=${owner_token%%-*}
  lease_name="menuplan-restore-${restore_run_id}-$token_prefix"
  lease_container=$(docker compose --profile ops run --detach --no-deps --name "$lease_name" \
    restore restore-hold "$restore_run_id" "$owner_token")
  [ -n "$lease_container" ] || { echo 'Restore-Lease-Container konnte nicht gestartet werden.' >&2; return 1; }
  attempts=0
  until restore_container restore-assert-held "$restore_run_id" "$owner_token" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    [ "$attempts" -lt 10 ] || {
      echo 'PostgreSQL-weite Restore-Lease wurde nicht rechtzeitig aktiv.' >&2
      return 1
    }
    sleep 1
  done
  start_lease_watchdog
  assert_lease_holder
}

stop_lease_holder() {
  stop_lease_watchdog
  [ -n "$lease_container" ] || return 0
  docker rm --force "$lease_container" >/dev/null
  lease_container=
}

start_and_validate_app() {
  assert_lease_holder || return 1
  docker compose up -d --wait --no-deps app || return 1
  assert_lease_holder || return 1
  docker compose exec -T app python /app/healthcheck.py || return 1
  restore_container restore-state "$restore_run_id" "$owner_token" app_validated || return 1
  assert_lease_holder || return 1
  restore_container restore-state "$restore_run_id" "$owner_token" complete || return 1
}

start_backup_and_record_complete() {
  assert_lease_holder || return 1
  docker compose up -d --no-deps backup || return 1
  assert_lease_holder || return 1
  restore_container restore-complete-services-running "$restore_run_id" "$owner_token" || return 1
}

repair_production_capabilities() {
  assert_lease_holder || return 1
  docker compose run --rm --no-deps migrate || return 1
  assert_lease_holder || return 1
  restore_container restore-ensure-auth-capabilities "$restore_run_id" "$owner_token" production || return 1
  assert_lease_holder || return 1
  docker compose run --rm --no-deps migrate || return 1
  assert_lease_holder || return 1
  restore_container restore-reset-auth-capabilities "$restore_run_id" "$owner_token" production || return 1
}

resume_completed_services() {
  assert_lease_holder || return 1
  restore_container restore-assert-complete-target "$restore_run_id" "$owner_token" || return 1
  repair_production_capabilities || return 1
  assert_lease_holder || return 1
  docker compose run --rm --no-deps -e RESTORE_RECOVERY_VALIDATION=true \
    app python /app/manage.py validate-db --wait-seconds 30 || return 1
  assert_lease_holder || return 1
  docker compose up -d --wait --no-deps app || return 1
  assert_lease_holder || return 1
  docker compose exec -T app python /app/healthcheck.py || return 1
  start_backup_and_record_complete || return 1
}

recover_database_and_app() {
  assert_lease_holder || return 1
  restore_container restore-recover "$restore_run_id" "$owner_token" || return 1
  repair_production_capabilities || return 1
  assert_lease_holder || return 1
  docker compose run --rm --no-deps -e RESTORE_RECOVERY_VALIDATION=true \
    app python /app/manage.py validate-db --wait-seconds 30 || return 1
  start_and_validate_app || return 1
  resume_complete=true
  start_backup_and_record_complete || return 1
  resume_complete=false
}

if [ "$PRUNE_MODE" = true ]; then
  restore_container restore-prune-retained
  exit 0
fi

restore_run_id=
owner_token=
candidate_ready=false
services_stop_started=false
lease_acquired=false
resume_complete=false

recover_on_exit() {
  status=$?
  trap - 0 1 2 15
  [ "$status" -eq 0 ] && exit 0
  set +e
  cleanup_failed=false

  if [ "$lease_acquired" = true ]; then
    if [ "$services_stop_started" = true ]; then
      stop_confirmed=true
      docker compose stop app backup || stop_confirmed=false
      recovery_proven=false
      if [ "$resume_complete" = true ]; then
        recovery_command=resume_completed_services
      else
        recovery_command=recover_database_and_app
      fi
      if [ "$stop_confirmed" = true ] && "$recovery_command"; then
        recovery_proven=true
      fi
      if [ "$recovery_proven" = true ]; then
        services_stop_started=false
        candidate_ready=false
        stop_lease_holder || cleanup_failed=true
        lease_acquired=false
      else
        docker compose stop app backup >/dev/null 2>&1
        echo 'App und Backup bleiben gestoppt: der gewählte Recovery-Stand ist nicht vollständig bewiesen.' >&2
        cleanup_failed=true
      fi
    elif [ "$candidate_ready" = true ]; then
      if assert_lease_holder; then
        restore_container restore-abort "$restore_run_id" "$owner_token" || cleanup_failed=true
      else
        cleanup_failed=true
      fi
    fi
  fi
  stop_lease_holder || cleanup_failed=true
  [ "$cleanup_failed" = false ] || status=1
  exit "$status"
}

trap recover_on_exit 0
trap 'exit 130' 1 2 15

if [ "$RECOVERY_MODE" = true ]; then
  recovery_owner_run_id="recovery_$(date -u +%Y%m%dT%H%M%SZ)_$$"
  takeover=$(restore_container restore-recovery-acquire "$recovery_owner_run_id")
  set -- $takeover
  [ "$#" -eq 3 ] || { echo 'Unerwartete Recovery-Takeover-Antwort.' >&2; exit 1; }
  restore_run_id=$1
  owner_token=$2
  recovery_action=$3
  validate_run_id
  validate_owner_token
  lease_acquired=true
  start_lease_holder
  services_stop_started=true
  assert_lease_holder
  docker compose stop app backup
  case "$recovery_action" in
    recover) recover_database_and_app ;;
    resume)
      resume_complete=true
      resume_completed_services
      resume_complete=false
      ;;
    *) echo 'Unbekannte Recovery-Aktion.' >&2; exit 1 ;;
  esac
  services_stop_started=false
  candidate_ready=false
  stop_lease_holder
  lease_acquired=false
  trap - 0 1 2 15
  exit 0
fi

backup=$1
verify_checksum "$backup"
restore_run_id=${RESTORE_RUN_ID:-"$(date -u +%Y%m%dT%H%M%SZ)_$$"}
validate_run_id
owner_token=$(restore_container restore-acquire "$restore_run_id")
validate_owner_token
lease_acquired=true
start_lease_holder

assert_lease_holder
candidate_database=$(restore_container restore-stage \
  "/restore-source/$backup_name" \
  "/restore-source/$(basename -- "$sha_file")" \
  "$restore_run_id" \
  "$owner_token")
case "$candidate_database" in
  ''|[0-9]*|*[!A-Za-z0-9_]*|postgres|template0|template1)
    echo "Unsicherer Restore-Kandidat: $candidate_database" >&2
    exit 1
    ;;
esac
case "$candidate_database" in
  *"_restore_candidate_$restore_run_id") ;;
  *) echo "Unerwarteter Restore-Kandidat: $candidate_database" >&2; exit 1 ;;
esac
[ "${#candidate_database}" -le 63 ] || { echo 'Restore-Kandidatname zu lang.' >&2; exit 1; }
candidate_ready=true

assert_lease_holder
if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" migrate; then
  assert_lease_holder
  restore_container restore-abort "$restore_run_id" "$owner_token"
  candidate_ready=false
  exit 1
fi
assert_lease_holder
restore_container restore-state "$restore_run_id" "$owner_token" migrated
assert_lease_holder
restore_container restore-ensure-auth-capabilities \
  "$restore_run_id" "$owner_token" "$candidate_database"
assert_lease_holder
if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" migrate; then
  assert_lease_holder
  restore_container restore-abort "$restore_run_id" "$owner_token"
  candidate_ready=false
  exit 1
fi
assert_lease_holder
restore_container restore-reset-auth-capabilities \
  "$restore_run_id" "$owner_token" "$candidate_database"

assert_lease_holder
if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" \
  app python /app/manage.py validate-db --wait-seconds 30
then
  assert_lease_holder
  restore_container restore-abort "$restore_run_id" "$owner_token"
  candidate_ready=false
  exit 1
fi
assert_lease_holder
restore_container restore-state "$restore_run_id" "$owner_token" candidate_validated

services_stop_started=true
assert_lease_holder
docker compose stop app backup
assert_lease_holder
restore_container restore-state "$restore_run_id" "$owner_token" services_stopped
assert_lease_holder
restore_container restore-promote "$restore_run_id" "$owner_token"
assert_lease_holder
docker compose run --rm --no-deps app python /app/manage.py validate-db --wait-seconds 30
assert_lease_holder
restore_container restore-state "$restore_run_id" "$owner_token" live_validated
assert_lease_holder
restore_container restore-state "$restore_run_id" "$owner_token" writer_release_committed
start_and_validate_app
resume_complete=true
start_backup_and_record_complete
resume_complete=false
services_stop_started=false
candidate_ready=false
stop_lease_holder
lease_acquired=false
trap - 0 1 2 15
