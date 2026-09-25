#!/usr/bin/env bash
# Release-Gate: Leitplanken A-C parallel auf je einem Pool, Teil D = Paket-Tests plus alle Testdateien,
# die laut label_grep.py entfernte sichtbare Texte zitieren. Auswertung per JUnit gegen known_red.txt:
# Das Gate blockiert nur bei NEUEN Fehlern oder bei Sammel-/Infrastrukturfehlern.
#
# Usage: release_gate.sh <worktree-root> <base-rev> [zusätzliche Testdateien relativ zu reference_scaffold ...]
#   <base-rev>  Live-Stand, normalerweise main (Label-Grep vergleicht ab git merge-base)
# Env: POOL_A..POOL_D (Pool-Env-Namen für gate.sh), DISHBOARD_TEST_VENV, DISHBOARD_POOL_ENV_DIR
# Höchstens vier Gate-Prozesse auf dem Host gleichzeitig (OOM-Grenze); ein Pool nie doppelt belegen.
set -uo pipefail
if (($# < 2)); then
  sed -n '2,9p' "$0" >&2
  exit 2
fi
WT="$(cd "$1" && pwd)" || exit 2
BASE="$2"; shift 2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="/var/tmp/dishboard-release-gate/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
COMMON=(-p no:cacheprovider -p no:randomly --tb=line --show-capture=no -rfE)

# Nur Dateien, die sync_playwright selbst starten; Session-Fixture-Dateien laufen in Teil D am Schluss.
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

# Teil D: Paket-Tests + Label-Grep-Treffer, ohne Dubletten aus A-C; eigene sync_playwright-Starter zuerst,
# sonst scheitern sie nach der Session-Fixture mit «Sync API inside the asyncio loop».
if ! label_out="$(python3 "$HERE/label_grep.py" "$WT" "$BASE" --files)"; then
  echo "FEHLER: label_grep.py gegen $BASE fehlgeschlagen - Gate ohne Label-Zuschlag wäre unvollständig" >&2
  exit 2
fi
label_hits=()
[[ -n "$label_out" ]] && mapfile -t label_hits <<<"$label_out"
declare -A seen=()
for f in "${part_a[@]}" "${part_b[@]}" "${part_c[@]}"; do seen[$f]=1; done
own=(); fixture=()
for f in "$@" "${label_hits[@]}"; do
  [[ -n "$f" && -z "${seen[$f]:-}" ]] || continue
  seen[$f]=1
  if [[ ! -f "$WT/reference_scaffold/$f" ]]; then
    echo "WARNUNG: $f fehlt, nicht im Gate" >&2
    continue
  fi
  if grep -q sync_playwright "$WT/reference_scaffold/$f"; then own+=("$f"); else fixture+=("$f"); fi
done
part_d=("${own[@]}" "${fixture[@]}")
echo "Teil D: ${#part_d[@]} Dateien (${#label_hits[@]} aus Label-Grep)"

declare -A pids=() pools=([a]="${POOL_A:-worker-test-api-int2}" [b]="${POOL_B:-worker-test-recipe-print-0908}"
                          [c]="${POOL_C:-worker-test-ps1}" [d]="${POOL_D:-worker-test-ps5}")
run_part() {
  local part="$1"; shift
  bash "$HERE/gate.sh" "${pools[$part]}" "$WT" -q "$@" "${COMMON[@]}" --junitxml="$OUT/$part.xml" \
    >"$OUT/$part.log" 2>&1
}
run_part a "${part_a[@]}" & pids[a]=$!
run_part b "${part_b[@]}" & pids[b]=$!
run_part c "${part_c[@]}" & pids[c]=$!
parts=(a b c)
if ((${#part_d[@]})); then
  run_part d "${part_d[@]}" & pids[d]=$!
  parts+=(d)
fi

verdict=0; summary=""
for part in "${parts[@]}"; do
  wait "${pids[$part]}"; rc=$?
  summary+=" $part=$rc"
  # 0 = grün, 1 = Testfehler (Auswertung unten); alles andere = Sammel-, Pool- oder Venv-Fehler.
  if ((rc > 1)); then
    echo "Teil $part: Exit $rc = Sammel-/Infrastrukturfehler, siehe $OUT/$part.log"
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
