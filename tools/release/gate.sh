#!/usr/bin/env bash
# Pytest auf einem Test-Pool. Die Ports des Pools werden zur Laufzeit per `docker port` aufgelöst,
# weil die Pool-Env-Dateien nach einem Container-Neustart veraltete Host-Ports tragen.
#
# Usage: gate.sh <pool-env-name> <worktree-root> [pytest-args ...]
#   <pool-env-name>  Basisname einer Env-Datei in $DISHBOARD_POOL_ENV_DIR, z. B. worker-test-api-int2
#   <worktree-root>  Checkout, dessen reference_scaffold getestet wird
# Env:
#   DISHBOARD_TEST_VENV     Test-Venv (Default /var/lib/dishboard-test-venv, Fallback /tmp/dishboard-shared-venv)
#   DISHBOARD_POOL_ENV_DIR  Pool-Env-Dateien (Default <Haupt-Checkout>/.claude/state/handover-2026-09-05, nur lokal)
# Die Pool-Env-Dateien enthalten Zugangsdaten der Test-Datenbanken: nur sourcen, nie ausgeben.
set -uo pipefail
if (($# < 2)); then
  sed -n '2,11p' "$0" >&2
  exit 2
fi
POOL="$1"; WT="$2"; shift 2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

common_dir="$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)" || exit 97
ENV_DIR="${DISHBOARD_POOL_ENV_DIR:-$(dirname "$common_dir")/.claude/state/handover-2026-09-05}"
if [[ ! -f "$ENV_DIR/$POOL.env" ]]; then
  echo "FEHLER: Pool-Env $ENV_DIR/$POOL.env fehlt" >&2
  exit 97
fi

VENV="${DISHBOARD_TEST_VENV:-/var/lib/dishboard-test-venv}"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "WARNUNG: $VENV fehlt, nutze /tmp/dishboard-shared-venv (systemd-tmpfiles löscht dort Dateien nach 10 Tagen)" >&2
  VENV=/tmp/dishboard-shared-venv
fi
# Ein von tmpfiles beschädigter Venv fällt sonst erst nach Minuten als ImportError bei der Collection auf.
if ! "$VENV/bin/python" -c 'from flask_session import Session' 2>/dev/null; then
  echo "FEHLER: Venv $VENV unvollständig - neu aufbauen (docs/operations/release-zug.md, Abschnitt 7)" >&2
  exit 96
fi

set -a
# shellcheck disable=SC1090
. "$ENV_DIR/$POOL.env"
set +a

pg_port=$(docker port "$TEST_DATABASE_CONTAINER" 5432/tcp) || exit 95
pg_port=${pg_port##*:}
redis_name=${TEST_DATABASE_CONTAINER%-pg16}-redis
redis_port=$(docker port "$redis_name" 6379/tcp) || exit 95
redis_port=${redis_port##*:}

TEST_DATABASE_URL=$(printf '%s' "$TEST_DATABASE_URL" | sed -E "s|:[0-9]+/|:${pg_port}/|")
TEST_REDIS_URL=$(printf '%s' "$TEST_REDIS_URL" | sed -E "s|:[0-9]+/|:${redis_port}/|")
export TEST_DATABASE_URL TEST_REDIS_URL
echo "POOL=$TEST_DATABASE_CONTAINER pg=$pg_port redis=$redis_port venv=$VENV"

cd "$WT/reference_scaffold" || exit 97
"$VENV/bin/python" -m pytest "$@"
rc=$?
echo "GATE_EXIT=$rc cwd=$PWD"
exit $rc
