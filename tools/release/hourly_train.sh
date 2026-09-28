#!/usr/bin/env bash
# Stündlicher, sitzungsunabhängiger Release-Zug; Start siehe docs/operations/release-zug.md.
# TRAIN_DRY_RUN=1 prüft den echten Kandidaten, startet aber weder Gate noch Push/Deploy.
# TRAIN_LINE ist nur im Trockenlauf erlaubt, etwa beim erstmaligen Einrichten des Hosts.
set -euo pipefail
umask 077
REPO=/nvmetank1/projects/menuplan
WT="$REPO/.claude/worktrees/release-train"
STATE=/var/lib/dishboard-release-train
LOG_ROOT=/var/tmp/dishboard-release-train
DRY="${TRAIN_DRY_RUN:-0}"
SHA=unbekannt
STEP=Start
mkdir -p "$STATE" "$LOG_ROOT"
exec 9>"$STATE/lock"
if ! flock -n 9; then
  echo 'Release-Zug läuft bereits; nichts zu tun.'
  exit 0
fi
OUT=$(mktemp -d "$LOG_ROOT/$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
exec > >(tee "$OUT/train.log") 2>&1

finish() {
  local rc=$?
  local cleanup_rc=0
  trap - EXIT
  # Nur der exklusive Zug-Worktree: auch Gate-Artefakte und Fehlerläufe aufräumen.
  if [[ -e "$WT" ]]; then
    git -C "$REPO" worktree remove --force "$WT" >>"$OUT/worktree.log" 2>&1 || cleanup_rc=$?
  fi
  git -C "$REPO" worktree prune >>"$OUT/worktree.log" 2>&1 || cleanup_rc=$?
  if ((cleanup_rc)); then
    echo "Worktree-Aufräumen fehlgeschlagen (Exit $cleanup_rc); siehe $OUT/worktree.log"
    if ((rc == 0)); then
      rc=$cleanup_rc
      STEP=Worktree-Aufraeumen
    fi
  fi
  if ((rc)); then
    {
      printf 'Zeit: %s\nSHA: %s\nSchritt: %s\nExit: %s\nLog: %s\n' \
        "$(date -u +%FT%TZ)" "$SHA" "$STEP" "$rc" "$OUT"
      if [[ -f "$OUT/gate.log" ]]; then
        grep '^NEU' "$OUT/gate.log" || true
      fi
    } >"$STATE/ALERT.tmp"
    mv "$STATE/ALERT.tmp" "$STATE/ALERT"
    logger -t dishboard-release-train "ALERT sha=$SHA step=$STEP exit=$rc logs=$OUT" || true
    echo "ALERT: $STEP (Exit $rc), SHA=$SHA, Logs=$OUT"
  fi
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

STEP=Linie
if [[ "$DRY" == 1 && -n "${TRAIN_LINE:-}" ]]; then
  LINE="$TRAIN_LINE"
else
  [[ -z "${TRAIN_LINE:-}" ]] || { echo 'TRAIN_LINE ist nur im Trockenlauf erlaubt'; exit 2; }
  mapfile -t lines <"$STATE/line"
  ((${#lines[@]} == 1)) || { echo 'line muss genau eine Zeile enthalten'; exit 2; }
  LINE="${lines[0]}"
fi
git check-ref-format "refs/heads/$LINE" >/dev/null
STEP=Fetch
git -C "$REPO" fetch github main >"$OUT/fetch.log" 2>&1
SHA=$(git -C "$REPO" rev-parse --verify "refs/heads/$LINE^{commit}")
BASE=$(git -C "$REPO" rev-parse --verify 'refs/remotes/github/main^{commit}')
printf 'Linie: %s\nKandidat: %s\nBasis: %s\nLogs: %s\n' "$LINE" "$SHA" "$BASE" "$OUT"
ahead=$(git -C "$REPO" rev-list --count "$BASE..$SHA")
if ((ahead == 0)); then
  echo 'nichts zu tun: Linie hat keine Commits vor github/main.'
  exit 0
fi

STEP=Worktree
if [[ -e "$WT" ]]; then
  git -C "$REPO" worktree remove --force "$WT" >"$OUT/worktree.log" 2>&1
fi
git -C "$REPO" worktree prune >>"$OUT/worktree.log" 2>&1
git -C "$REPO" worktree add --detach "$WT" "$SHA" >>"$OUT/worktree.log" 2>&1
[[ "$(git -C "$WT" rev-parse --show-toplevel)" == "$WT" ]]
[[ "$(git -C "$WT" rev-parse --path-format=absolute --git-common-dir)" == \
   "$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)" ]]
STEP=Abstammung
git -C "$WT" merge-base --is-ancestor "$BASE" "$SHA"
echo 'Abstammung: github/main ist Vorfahre des Kandidaten.'
STEP=Manifest
python3 "$WT/tools/build_manifest.py" --verify >"$OUT/manifest.log" 2>&1 || {
  cat "$OUT/manifest.log"; exit 1;
}
cat "$OUT/manifest.log"
STEP=PII
pii_count=$(git -C "$WT" rev-list --count "$SHA" -- \
  docs/design/uiux-handoff-2026-09-20/03_REFERENCES/accepted-settings/a02b14e0-da12-4edd-b57e-8b3ce2d3082d.png)
echo "PII-Historie: $pii_count"
[[ "$pii_count" == 0 ]]

STEP=Pools
# Kein source/eval: Die Konfiguration enthält nur Pool-Namen, keine Shell und keine Secrets.
unset POOL_A POOL_B POOL_C POOL_D POOL_D2 POOL_D3
declare -A configured=()
if [[ -f "$STATE/pools" ]]; then
  while IFS= read -r entry || [[ -n "$entry" ]]; do
    [[ -z "$entry" || "$entry" == \#* ]] && continue
    [[ "$entry" =~ ^(POOL_[ABCD]|POOL_D[23])=([a-zA-Z0-9_-]+)$ ]] || {
      echo 'Ungültige pools-Zeile (Inhalt wird nicht ausgegeben).'; exit 2;
    }
    key="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"
    [[ -z "${configured[$key]:-}" ]] || { echo 'Doppelter Pool-Schlüssel'; exit 2; }
    configured[$key]=1
    export "$key=$value"
  done <"$STATE/pools"
else
  [[ "$DRY" == 1 ]] || { echo 'Host-Konfiguration pools fehlt'; exit 2; }
  echo 'Trockenlauf: pools fehlt; Gate-Defaults, keine zusätzlichen D-Pools.'
fi
for key in POOL_A POOL_B POOL_C POOL_D; do
  [[ "$DRY" == 1 || -n "${!key:-}" ]] || { echo "$key fehlt in pools"; exit 2; }
done
for key in POOL_A POOL_B POOL_C POOL_D POOL_D2 POOL_D3; do
  printf '%s=%s\n' "$key" "${!key:-<Gate-Default bzw. nicht gesetzt>}"
done
STEP=Paketdateien
git -C "$WT" diff --name-only -z --diff-filter=ACMRT "$BASE" "$SHA" -- \
  'reference_scaffold/tests/test_*.py' >"$OUT/changed-tests"
tests=()
while IFS= read -r -d '' file; do tests+=("${file#reference_scaffold/}"); done <"$OUT/changed-tests"
# Gate und known_red.txt müssen aus demselben geprüften Kandidaten stammen.
gate=(bash "$WT/tools/release/release_gate.sh" "$WT" github/main "${tests[@]}")
printf 'Gate-Aufruf:'; printf ' %q' "${gate[@]}"; printf '\n'
if [[ "$DRY" == 1 ]]; then
  echo 'TRAIN_DRY_RUN=1: Vorprüfungen OK; kein Gate, Push oder Deploy.'
  exit 0
fi

STEP=Gate
# Externe Fetches dürfen während des Gates die Vergleichsbasis nicht verschieben.
# SHA statt beweglichem Ref beim echten Lauf; Ausgabe oben nennt den üblichen Aufruf.
gate[3]="$BASE"
export RELEASE_GATE_OUT="$OUT/junit"
unset RELEASE_GATE_DRY_RUN
timeout --kill-after=30s 52m "${gate[@]}" >"$OUT/gate.log" 2>&1
grep -qx 'NEW_FAILURES=0' "$OUT/gate.log"
STEP=Kandidat-unveraendert
[[ "$(git -C "$WT" rev-parse HEAD)" == "$SHA" ]]
# Gate-Evidence darf Dateien verändern; gepusht wird ausschliesslich der geprüfte SHA.
STEP=Push
# Expliziter SHA, normaler Fast-Forward-Push; Haupt-Checkout und lokale main bleiben unberührt.
git -C "$REPO" -c push.followTags=false push github "$SHA:refs/heads/main" >"$OUT/push.log" 2>&1
STEP=Deploy
systemctl start dishboard-deploy-main.service >"$OUT/deploy.log" 2>&1
STEP=Live-Pruefung
# Compose may return before Docker's first successful healthcheck. Only the
# exact deployed candidate in "starting" gets this bounded readiness allowance.
ready_deadline=$((SECONDS + 60))
while :; do
  ready_remaining=$((ready_deadline - SECONDS))
  ((ready_remaining > 0)) || { echo 'FEHLER: Healthcheck nach 60s weiterhin starting'; exit 1; }
  if ! ready_state=$(timeout "$ready_remaining" docker inspect -f \
    '{{index .Config.Labels "org.opencontainers.image.revision"}} {{if .State.Health}}{{.State.Health.Status}}{{else}}ohne-healthcheck{{end}}' \
    suedhang-cafeteria-app-1); then
    echo 'FEHLER: Readiness-Status nicht lesbar'; exit 2
  fi
  read -r ready_revision ready_health <<< "$ready_state"
  [[ "$ready_revision" == "$SHA" ]] || {
    echo "FEHLER: Live-Revision $ready_revision entspricht nicht Kandidat $SHA"; exit 1;
  }
  case "$ready_health" in
    healthy) break ;;
    starting) echo "Readiness: health=starting; noch ${ready_remaining}s Budget" ;;
    *) echo "FEHLER: Produktion nicht gesund (health=$ready_health)"; exit 1 ;;
  esac
  sleep 1
done
DISHBOARD_EXPECTED_REVISION="$SHA" bash "$WT/tools/release/deploy_status.sh" "$LINE"
printf '%s %s\n' "$SHA" "$(date -u +%FT%TZ)" >"$STATE/last_success.tmp"
mv "$STATE/last_success.tmp" "$STATE/last_success"
rm -f "$STATE/ALERT"
echo "ERFOLG: $SHA deployed; Logs=$OUT"
