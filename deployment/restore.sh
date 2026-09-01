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
[ -f "$sha_file" ] || { echo "Checksum-Datei fehlt: $sha_file" >&2; exit 1; }

verify_checksum() {
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

verify_checksum

restore_container() {
  docker compose --profile ops run --rm \
    -v "$backup_dir:/restore-source:ro" \
    restore "$@"
}

cleanup_candidate() {
  restore_container restore-cleanup-candidate
}

if ! candidate_database=$(restore_container restore-stage \
  "/restore-source/$backup_name" \
  "/restore-source/$(basename -- "$sha_file")")
then
  exit 1
fi
case "$candidate_database" in
  ''|[0-9]*|*[!A-Za-z0-9_]*|postgres|template0|template1)
    echo "Unsicherer Restore-Kandidat: $candidate_database" >&2
    exit 1
    ;;
esac
case "$candidate_database" in
  *_restore_candidate) ;;
  *) echo "Unerwarteter Restore-Kandidat: $candidate_database" >&2; exit 1 ;;
esac
[ "${#candidate_database}" -le 63 ] || { echo 'Restore-Kandidatname zu lang.' >&2; exit 1; }

if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" migrate
then
  cleanup_candidate
  exit 1
fi

if ! docker compose run --rm --no-deps -e "POSTGRES_DB=$candidate_database" \
  app python /app/manage.py validate-db --wait-seconds 30
then
  cleanup_candidate
  exit 1
fi

services_stopped=false
database_promoted=false

recover_on_exit() {
  status=$?
  trap - 0 1 2 15
  [ "$status" -eq 0 ] && exit 0
  set +e
  recovery_failed=false
  if [ "$database_promoted" = true ]; then
    docker compose stop app backup || recovery_failed=true
    restore_container restore-rollback || recovery_failed=true
    database_promoted=false
  fi
  if [ "$services_stopped" = true ]; then
    docker compose up -d app backup || recovery_failed=true
  fi
  [ "$recovery_failed" = false ] || status=1
  exit "$status"
}

trap recover_on_exit 0
trap 'exit 130' 1 2 15

services_stopped=true
docker compose stop app backup
restore_container restore-promote
database_promoted=true
docker compose run --rm --no-deps app python /app/manage.py validate-db --wait-seconds 30
docker compose up -d app backup
services_stopped=false
trap - 0 1 2 15
