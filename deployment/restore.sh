#!/bin/sh
set -eu

RECOVERY_MODE=false
case "${1:-}" in
  --recover)
    [ "$#" -eq 1 ] || { echo "Verwendung: $0 --recover" >&2; exit 2; }
    RECOVERY_MODE=true
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
}

stop_lease_holder() {
  [ -n "$lease_container" ] || return 0
  docker rm --force "$lease_container" >/dev/null
  lease_container=
}

restore_run_id=
owner_token=
candidate_ready=false
services_stop_started=false
lease_acquired=false

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
      if restore_container restore-recover "$restore_run_id" "$owner_token" \
        && docker compose run --rm --no-deps -e RESTORE_RECOVERY_VALIDATION=true \
          app python /app/manage.py validate-db --wait-seconds 30
      then
        recovery_proven=true
      fi
      if [ "$stop_confirmed" = true ] && [ "$recovery_proven" = true ]; then
        if docker compose up -d app backup \
          && restore_container restore-state "$restore_run_id" "$owner_token" complete
        then
          services_stop_started=false
        else
          docker compose stop app backup >/dev/null 2>&1
          cleanup_failed=true
        fi
      else
        echo 'App und Backup bleiben gestoppt: der alte Datenbankstand ist nicht vollständig bewiesen.' >&2
        cleanup_failed=true
      fi
    elif [ "$candidate_ready" = true ]; then
      restore_container restore-abort "$restore_run_id" "$owner_token" || cleanup_failed=true
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
  takeover=$(restore_container restore-takeover "$recovery_owner_run_id")
  set -- $takeover
  [ "$#" -eq 2 ] || { echo 'Unerwartete Recovery-Takeover-Antwort.' >&2; exit 1; }
  restore_run_id=$1
  owner_token=$2
  validate_run_id
  validate_owner_token
  lease_acquired=true
  start_lease_holder
  services_stop_started=true
  docker compose stop app backup
  restore_container restore-recover "$restore_run_id" "$owner_token"
  docker compose run --rm --no-deps -e RESTORE_RECOVERY_VALIDATION=true \
    app python /app/manage.py validate-db --wait-seconds 30
  docker compose up -d app backup
  restore_container restore-state "$restore_run_id" "$owner_token" complete
  services_stop_started=false
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

if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" migrate; then
  restore_container restore-abort "$restore_run_id" "$owner_token"
  candidate_ready=false
  exit 1
fi
restore_container restore-state "$restore_run_id" "$owner_token" migrated

if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" \
  app python /app/manage.py validate-db --wait-seconds 30
then
  restore_container restore-abort "$restore_run_id" "$owner_token"
  candidate_ready=false
  exit 1
fi
restore_container restore-state "$restore_run_id" "$owner_token" candidate_validated

services_stop_started=true
docker compose stop app backup
restore_container restore-state "$restore_run_id" "$owner_token" services_stopped
restore_container restore-promote "$restore_run_id" "$owner_token"
docker compose run --rm --no-deps app python /app/manage.py validate-db --wait-seconds 30
restore_container restore-state "$restore_run_id" "$owner_token" live_validated
docker compose up -d app backup
restore_container restore-state "$restore_run_id" "$owner_token" complete
services_stop_started=false
stop_lease_holder
lease_acquired=false
trap - 0 1 2 15
