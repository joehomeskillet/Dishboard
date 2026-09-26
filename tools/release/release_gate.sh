#!/usr/bin/env bash
# Release-Gate: Leitplanken A-C parallel auf je einem Pool, Teil D = Paket-Tests plus alle Testdateien,
# die laut label_grep.py entfernte sichtbare Texte zitieren. Auswertung per JUnit gegen known_red.txt:
# Das Gate blockiert nur bei NEUEN Fehlern oder bei Sammel-/Infrastrukturfehlern.
#
# Usage: release_gate.sh <worktree-root> <base-rev> [zusätzliche Testdateien relativ zu reference_scaffold ...]
#   <base-rev>  Live-Stand, normalerweise main (Label-Grep vergleicht ab git merge-base)
# Env: POOL_A..POOL_D, optional POOL_D2/POOL_D3 (Pool-Env-Namen für gate.sh),
#      DISHBOARD_TEST_VENV, DISHBOARD_POOL_ENV_DIR
#      RELEASE_GATE_DRY_RUN=1 gibt nur die Einteilung aus, ohne Pools oder Tests zu starten.
# Höchstens vier Gate-Prozesse auf dem Host gleichzeitig (OOM-Grenze); ein Pool nie doppelt belegen.
set -uo pipefail
if (($# < 2)); then
  sed -n '2,9p' "$0" >&2
  exit 2
fi
WT="$(cd "$1" && pwd)" || exit 2
BASE="$2"; shift 2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${RELEASE_GATE_OUT:-/var/tmp/dishboard-release-gate/$(date +%Y%m%d-%H%M%S)-$$}"
COMMON=(-p no:cacheprovider -p no:randomly --tb=line --show-capture=no -rfE)

# Feste Leitplanken; zusätzliche Dateien werden unten in Teil D aufgeteilt.
part_a=(tests/test_signage_patient.py tests/test_signage_ops_browser.py tests/test_signage_cafeteria_day.py
        tests/test_signage_cafeteria_week.py tests/test_public_contracts.py tests/test_public_equal_cards_browser.py
        tests/test_preview_equal_cards_browser.py)
part_b=(tests/test_admin_shell_ui.py tests/test_ui_master_shell_browser.py tests/test_ui_fullwidth_shell_browser.py
        tests/test_admin_week_tabler_browser.py tests/test_admin_week_equal_cards_browser.py
        tests/test_ui_korrektur_week_browser.py tests/test_week_review_browser.py tests/test_kitchen_calendar_browser.py
        tests/test_course_browser.py tests/test_recipe_navigation_browser.py)
part_c=(tests/test_admin_workflow_routes.py tests/test_admin_workflow_db.py tests/test_course_store_db.py
        tests/test_course_week_html.py tests/test_auth_routes.py tests/test_api_docs.py tests/test_ui_semantics.py
        tests/test_ui_semantic_macros_browser.py tests/test_admin_shared_patterns_browser.py tests/test_rendered_ui.py
        tests/test_calendar_event_routes.py tests/test_ui_korrektur_menus_browser.py
        tests/test_ui_korrektur_components_browser.py)

# Teil D: Paket-Tests + Label-Grep-Treffer, ohne Dubletten aus A-C.
# Eigene Starter und Session-Fixtures brauchen getrennte pytest-Prozesse.
if ! label_out="$(python3 "$HERE/label_grep.py" "$WT" "$BASE" --files)"; then
  echo "FEHLER: label_grep.py gegen $BASE fehlgeschlagen - Gate ohne Label-Zuschlag wäre unvollständig" >&2
  exit 2
fi
label_hits=()
[[ -n "$label_out" ]] && mapfile -t label_hits <<<"$label_out"
declare -A seen=()
for f in "${part_a[@]}" "${part_b[@]}" "${part_c[@]}"; do seen[$f]=1; done
candidates=()
for f in "$@" "${label_hits[@]}"; do
  [[ -n "$f" && -z "${seen[$f]:-}" ]] || continue
  seen[$f]=1
  if [[ ! -f "$WT/reference_scaffold/$f" ]]; then
    echo "WARNUNG: $f fehlt, nicht im Gate" >&2
    continue
  fi
  candidates+=("$f")
done
# Browser-Hinweise bewusst breit: im Zweifel ein eigener Prozess.
together=(); single=()
for f in "${candidates[@]}"; do
  grep -E 'playwright|_browser|test_rendered_ui' "$WT/reference_scaffold/$f" >/dev/null
  if (($? == 1)); then together+=("$f"); else single+=("$f"); fi
done
echo "Teil D: ${#candidates[@]} Dateien (${#label_hits[@]} aus Label-Grep)"
echo "gemeinsam: ${#together[@]} Dateien; einzeln: ${#single[@]} Dateien (je ein Prozess)"
declare -A pools=([a]="${POOL_A:-worker-test-api-int2}" [b]="${POOL_B:-worker-test-recipe-print-0908}"
                 [c]="${POOL_C:-worker-test-ps1}" [d]="${POOL_D:-worker-test-ps5}")
d_pools=("${pools[d]}")
[[ -z "${POOL_D2:-}" ]] || d_pools+=("$POOL_D2")
[[ -z "${POOL_D3:-}" ]] || d_pools+=("$POOL_D3")
declare -A pool_seen=()
for pool in "${pools[a]}" "${pools[b]}" "${pools[c]}" "${d_pools[@]}"; do
  if [[ ! "$pool" =~ ^[a-zA-Z0-9_-]+$ || -n "${pool_seen[$pool]:-}" ]]; then
    echo 'FEHLER: Pool-Namen müssen gültig und untereinander verschieden sein' >&2
    exit 2
  fi
  pool_seen[$pool]=1
done
parts=(a b c)
if ((${#together[@]})); then parts+=(d0); pools[d0]="${d_pools[0]}"; fi
for i in "${!single[@]}"; do
  part="d-$((i + 1))"
  parts+=("$part")
  pools[$part]="${d_pools[$(( (i + (${#together[@]} > 0)) % ${#d_pools[@]} ))]}"
done
if [[ "${RELEASE_GATE_DRY_RUN:-0}" == 1 ]]; then
  for group in a b c; do
    declare -n files="part_$group"
    printf '%s: %s Dateien\n' "$group" "${#files[@]}"
    printf '  %s\n' "${files[@]}"
  done
  for f in "${together[@]}"; do printf 'gemeinsam: pool=%s junit=d0.xml %s\n' "${pools[d0]}" "$f"; done
  for i in "${!single[@]}"; do
    part="d-$((i + 1))"
    printf 'einzeln: pool=%s junit=%s.xml %s\n' "${pools[$part]}" "$part" "${single[$i]}"
  done
  echo 'Parallelität: höchstens 4 Prozesse insgesamt, höchstens 1 je Pool'
  exit 0
fi
mkdir -p "$OUT" || exit 2
# Keine alten XML-Dateien in die Auswertung eines neuen Laufs aufnehmen.
if [[ -n "$(find "$OUT" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "FEHLER: Gate-Ausgabeverzeichnis nicht leer: $OUT" >&2
  exit 2
fi

declare -A active=() busy=() results=()
run_part() {
  local part="$1"; shift
  bash "$HERE/gate.sh" "${pools[$part]}" "$WT" -q "$@" "${COMMON[@]}" --junitxml="$OUT/$part.xml" \
    >>"$OUT/$part.log" 2>&1
}
reap() {
  local finished rc part
  wait -n -p finished "${!active[@]}"; rc=$?
  part="${active[$finished]}"
  results[$part]=$rc
  unset 'active[$finished]' 'busy[${pools[$part]}]'
}
for part in "${parts[@]}"; do
  while ((${#active[@]} >= 4)) || [[ -n "${busy[${pools[$part]}]:-}" ]]; do reap; done
  case "$part" in
    a) args=("${part_a[@]}");;
    b) args=("${part_b[@]}");;
    c) args=("${part_c[@]}");;
    d0) args=("${together[@]}");;
    d-*) args=("${single[$(( ${part#d-} - 1 ))]}");;
  esac
  run_part "$part" "${args[@]}" & active[$!]="$part"
  busy[${pools[$part]}]=1
done
while ((${#active[@]})); do reap; done

verdict=0; summary=""
for part in "${parts[@]}"; do
  rc="${results[$part]}"
  summary+=" $part=$rc"
  # 0 = grün, 1 = Testfehler (Auswertung unten); alles andere = Sammel-, Pool- oder Venv-Fehler.
  if ((rc > 1)); then
    echo "Teil $part: Exit $rc = Sammel-/Infrastrukturfehler, siehe $OUT/$part.log"
    verdict=1
  fi
  if [[ ! -s "$OUT/$part.xml" ]]; then
    echo "Teil $part: JUnit fehlt: $OUT/$part.xml"
    verdict=1
  fi
done
for part in "${parts[@]}"; do
  printf '== Teil %s: ' "$part"
  grep -E ' passed| failed| error' "$OUT/$part.log" | tail -n 1 || echo 'keine pytest-Zusammenfassung'
done

python3 "$HERE/new_failures.py" "$OUT"/*.xml
nf=$?
((nf)) && verdict=1
echo "RELEASE_GATE$summary new_failures_exit=$nf verdict=$verdict logs=$OUT"
exit "$verdict"
