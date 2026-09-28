#!/usr/bin/env bash
# Deploy-Stand in einem Blick (liest nur): Live-Revision und Startzeit des App-Containers, Health, Login,
# main-HEAD, Commits der Integrationslinien vor github/main und das Deploy-Alter in Minuten.
#
# Usage: deploy_status.sh [<integrationslinie> ...]
# Ohne Argumente: Host-Linie (sonst $DISHBOARD_INTEGRATION_BRANCH) plus lokale integrate/*-Linien.
# DISHBOARD_EXPECTED_REVISION: optionaler vollständiger SHA, der nach Deploy live sein muss.
# Exit 1: Deploy-Alter > 120 min und eine ausgewählte Linie hat Commits vor github/main,
#         zusätzliche entdeckte Linien zählen nur mit einem letzten Commit jünger als 7 Tage,
#         oder Produktion ist nicht healthy bzw. Login liefert nicht 200.
# Exit 2: Container oder angeforderte Integrationslinien nicht lesbar.
# Das Deploy-Alter ist die Laufzeit des Containers; ein Neustart ohne Deploy setzt es ebenfalls zurück.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE=/var/lib/dishboard-release-train
line=''
if [[ -f "$STATE/line" ]]; then IFS= read -r line <"$STATE/line"; fi
primary="${line:-${DISHBOARD_INTEGRATION_BRANCH:-integrate/uiux-0920}}"
if (($#)); then lines=("$@"); else lines=("$primary"); fi
echo "Zug-Linie:     ${line:-nicht konfiguriert}"
for item in last_success ALERT; do
  echo "$item:"
  if [[ -f "$STATE/$item" ]]; then cat "$STATE/$item"; else echo '  nicht vorhanden'; fi
done
CONTAINER=suedhang-cafeteria-app-1
LOGIN_URL=http://127.0.0.1:8789/auth/login
MAX_AGE_MIN=120
ACTIVE_MAX_AGE_SEC=$((7 * 24 * 60 * 60))

fmt='{{index .Config.Labels "org.opencontainers.image.revision"}} {{.State.StartedAt}} {{if .State.Health}}{{.State.Health.Status}}{{else}}ohne-healthcheck{{end}}'
if ! read -r live started health < <(docker inspect -f "$fmt" "$CONTAINER" 2>/dev/null); then
  echo "FEHLER: Container $CONTAINER nicht lesbar" >&2
  exit 2
fi
age_min=$(( ($(date +%s) - $(date -d "$started" +%s)) / 60 ))
login=$(curl -s -o /dev/null -L --max-time 15 -w '%{http_code}' "$LOGIN_URL")
main=$(git -C "$REPO" rev-parse --short=10 main)
pushed=$(git -C "$REPO" rev-parse --short=10 github/main 2>/dev/null || echo '?')
undeployed=$(git -C "$REPO" rev-list --count "$live..github/main" 2>/dev/null || echo '?')
if (($# == 0)); then
  if ! lines_raw=$(git -C "$REPO" for-each-ref --format='%(refname:short)' 'refs/heads/integrate/'); then
    echo "FEHLER: lokale Integrationslinien nicht lesbar" >&2
    exit 2
  fi
  while IFS= read -r INT; do
    [[ -z "$INT" || "$INT" == "$primary" ]] || lines+=("$INT")
  done <<< "$lines_raw"
fi

echo "Live:          ${live:0:10}  seit $(date -d "$started" '+%Y-%m-%d %H:%M %Z')  health=$health  login=$login"
echo "main (lokal):  $main  (github/main $pushed, Commits github/main vor Live: $undeployed)"
cutoff=$(( $(date +%s) - ACTIVE_MAX_AGE_SEC ))
warn_lines=()
warn_ahead=()
read_error=0
for INT in "${lines[@]}"; do
  if ! ahead=$(git -C "$REPO" rev-list --count "github/main..$INT" 2>/dev/null); then
    echo "$INT: nicht lesbar (Vergleich mit github/main)"
    read_error=1
    continue
  fi
  echo "$INT: $ahead Commits vor github/main"
  if [[ "$ahead" =~ ^[0-9]+$ ]] && ((ahead > 0)); then
    if (($# == 0)) && [[ "$INT" != "$primary" ]]; then
      tip_ts=$(git -C "$REPO" log -1 --format=%ct "$INT" 2>/dev/null || echo 0)
      [[ "$tip_ts" =~ ^[0-9]+$ ]] && ((tip_ts > cutoff)) || continue
    fi
    warn_lines+=("$INT")
    warn_ahead+=("$ahead")
  fi
done
echo "Deploy-Alter:  $age_min min"

status=0
if [[ -n "${DISHBOARD_EXPECTED_REVISION:-}" && "$live" != "$DISHBOARD_EXPECTED_REVISION" ]]; then
  echo "WARNUNG: Live-Revision $live entspricht nicht Kandidat $DISHBOARD_EXPECTED_REVISION"
  status=1
fi
if [[ "$health" != healthy || "$login" != 200 ]]; then
  echo "WARNUNG: Produktion nicht gesund (health=$health, login=$login)"
  status=1
fi
if ((age_min > MAX_AGE_MIN)) && ((${#warn_lines[@]} > 0)); then
  for i in "${!warn_lines[@]}"; do
    echo "WARNUNG: Release-Zug überfällig - letzter Deploy vor $age_min min, ${warn_ahead[$i]} Commits warten in ${warn_lines[$i]}"
  done
  status=1
fi
((read_error)) && status=2
((status)) || echo "STATUS: OK"
exit "$status"
