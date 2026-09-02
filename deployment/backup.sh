#!/bin/sh
set -eu
cd "$(dirname "$0")"

if [ "$#" -gt 1 ]; then
  echo "Verwendung: $0 [/absolutes/host-backup-verzeichnis]" >&2
  exit 2
fi

if [ "$#" -eq 0 ]; then
  exec docker compose run --rm backup once
fi

export_dir=$1
case "$export_dir" in
  /*) ;;
  *) echo 'Das Export-Verzeichnis muss absolut sein.' >&2; exit 2 ;;
esac
mkdir -p "$export_dir"
export_dir=$(CDPATH= cd -- "$export_dir" && pwd)

container_path=$(docker compose run --rm \
  -e BACKUP_DIR=/export \
  -v "$export_dir:/export" \
  backup once)
case "$container_path" in
  *'
'*) echo 'Unerwartete mehrzeilige Backup-Ausgabe.' >&2; exit 1 ;;
esac
backup_name=$(basename -- "$container_path")
case "$backup_name" in
  cafeteria-*.dump) ;;
  *) echo "Unerwarteter Backup-Dateiname: $backup_name" >&2; exit 1 ;;
esac

host_backup="$export_dir/$backup_name"
[ -f "$host_backup" ] || { echo "Exportiertes Backup fehlt: $host_backup" >&2; exit 1; }
[ -f "$host_backup.sha256" ] || { echo "Exportierte Checksum-Datei fehlt: $host_backup.sha256" >&2; exit 1; }
printf '%s\n' "$host_backup"
