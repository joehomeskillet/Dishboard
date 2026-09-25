#!/usr/bin/env bash
# Deploy-Stand in einem Blick (liest nur): Live-Revision und Startzeit des App-Containers, Health, Login,
# main-HEAD, Commits der Integrationslinie vor main und das Deploy-Alter in Minuten.
#
# Usage: deploy_status.sh [<integrationslinie>]   Default: $DISHBOARD_INTEGRATION_BRANCH oder integrate/uiux-0920
# Exit 1: Deploy-Alter > 120 min und die Integrationslinie hat Commits vor main (Release-Zug überfällig),
#         oder Produktion ist nicht healthy bzw. Login liefert nicht 200.
# Das Deploy-Alter ist die Laufzeit des Containers; ein Neustart ohne Deploy setzt es ebenfalls zurück.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INT="${1:-${DISHBOARD_INTEGRATION_BRANCH:-integrate/uiux-0920}}"
CONTAINER=suedhang-cafeteria-app-1
LOGIN_URL=http://127.0.0.1:8789/auth/login
MAX_AGE_MIN=120

fmt='{{index .Config.Labels "org.opencontainers.image.revision"}} {{.State.StartedAt}} {{if .State.Health}}{{.State.Health.Status}}{{else}}ohne-healthcheck{{end}}'
if ! read -r live started health < <(docker inspect -f "$fmt" "$CONTAINER" 2>/dev/null); then
  echo "FEHLER: Container $CONTAINER nicht lesbar" >&2
  exit 2
fi
age_min=$(( ($(date +%s) - $(date -d "$started" +%s)) / 60 ))
login=$(curl -s -o /dev/null -L --max-time 15 -w '%{http_code}' "$LOGIN_URL")
main=$(git -C "$REPO" rev-parse --short=10 main)
pushed=$(git -C "$REPO" rev-parse --short=10 github/main 2>/dev/null || echo '?')
ahead=$(git -C "$REPO" rev-list --count "main..$INT" 2>/dev/null || echo '?')
undeployed=$(git -C "$REPO" rev-list --count "$live..main" 2>/dev/null || echo '?')

echo "Live:          ${live:0:10}  seit $(date -d "$started" '+%Y-%m-%d %H:%M %Z')  health=$health  login=$login"
echo "main:          $main  (github/main $pushed, Commits main vor Live: $undeployed)"
echo "$INT: $ahead Commits vor main"
echo "Deploy-Alter:  $age_min min"

status=0
if [[ "$health" != healthy || "$login" != 200 ]]; then
  echo "WARNUNG: Produktion nicht gesund (health=$health, login=$login)"
  status=1
fi
if ((age_min > MAX_AGE_MIN)) && [[ "$ahead" =~ ^[0-9]+$ ]] && ((ahead > 0)); then
  echo "WARNUNG: Release-Zug überfällig - letzter Deploy vor $age_min min, $ahead Commits warten in $INT"
  status=1
fi
((status)) || echo "STATUS: OK"
exit "$status"
