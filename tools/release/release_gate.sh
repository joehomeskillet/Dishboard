#!/usr/bin/env bash
# Release-Gate: Leitplanken A-C parallel auf je einem Pool, Teil D = Paket-Tests plus alle Testdateien,
# die laut label_grep.py entfernte sichtbare Texte zitieren. Auswertung per JUnit gegen known_red.txt:
# Das Gate blockiert nur bei NEUEN Fehlern oder bei Sammel-/Infrastrukturfehlern.
#
# Usage: release_gate.sh <worktree-root> <base-rev> [zusätzliche Testdateien relativ zu reference_scaffold ...]
#   <base-rev>  Live-Stand, normalerweise main (Label-Grep vergleicht ab git merge-base)
# Env: POOL_A..POOL_D (Pool-Env-Namen für gate.sh), DISHBOARD_TEST_VENV, DISHBOARD_POOL_ENV_DIR
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
OUT="/var/tmp/dishboard-release-gate/$(date +%Y%m%d-%H%M%S)"
COMMON=(-p no:cacheprovider -p no:randomly --tb=line --show-capture=no -rfE)

# Feste Leitplanken; zusätzliche Dateien werden unten auf D1/D2/D3 verteilt.
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
if ! groups="$(python3 - "$WT/reference_scaffold" "${candidates[@]}" <<'PY'
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
session_names = {'browser', 'browser_type', 'playwright', 'context', 'page', 'new_context',
                 'browser_context'}
modules = {}


def module(path):
    if path not in modules:
        source = path.read_text(encoding='utf-8')
        modules[path] = (source, ast.parse(source, filename=str(path)))
    return modules[path]


def imported_path(path, node):
    if not node.module:
        return None
    relative = Path(*node.module.split('.'))
    bases = [path.parent, root, root / 'tests']
    if node.level:
        bases = [path.parents[node.level - 1]]
    for base in bases:
        candidate = (base / relative).with_suffix('.py')
        if candidate.is_file():
            return candidate.resolve()
    return None


def resolve(path, name, visiting=frozenset()):
    key = (path, name)
    if key in visiting:
        return None
    for node in reversed(module(path)[1].body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return path, node
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == name or alias.name == '*':
                    imported = imported_path(path, node)
                    if imported:
                        found = resolve(imported, name if alias.name == '*' else alias.name,
                                        visiting | {key})
                        if found:
                            return found
    return None


def definitions(path):
    result = {}
    for node in module(path)[1].body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = (path, node)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    raise ValueError(f'{path}: Sternimport verhindert sichere Fixture-Einteilung')
                name = alias.asname or alias.name
                found = resolve(path, name)
                if found:
                    result[name] = found
    return result


def fixture_options(node):
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if getattr(target, 'attr', getattr(target, 'id', None)) == 'fixture':
            return {kw.arg: kw.value.value for kw in getattr(decorator, 'keywords', [])
                    if isinstance(kw.value, ast.Constant)}
    return None


def dependencies(node):
    names = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        mark = getattr(decorator.func, 'attr', '')
        if mark == 'parametrize' and decorator.args:
            value = decorator.args[0]
            indirect = any(kw.arg == 'indirect' and not
                           (isinstance(kw.value, ast.Constant) and kw.value.value is False)
                           for kw in decorator.keywords)
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and not indirect:
                names.difference_update(name.strip() for name in value.value.split(','))
        if mark == 'usefixtures':
            names.update(arg.value for arg in decorator.args if isinstance(arg, ast.Constant))
    for call in ast.walk(node):
        if (isinstance(call, ast.Call) and getattr(call.func, 'attr', '') == 'getfixturevalue'
                and call.args and isinstance(call.args[0], ast.Constant)):
            names.add(call.args[0].value)
    return names


for filename in sys.argv[2:]:
    path = root / filename
    source, tree = module(path)
    own = 'sync_playwright(' in source
    visible = {}
    # Pytest löst Fixture-Abhängigkeiten im Kontext der konsumierenden Datei auf.
    for parent in reversed(path.parents):
        if parent != root.parent and not parent.is_relative_to(root):
            continue
        conftest = parent / 'conftest.py'
        if conftest.is_file():
            visible.update(definitions(conftest))
    visible.update(definitions(path))
    fixtures = {}
    for name, (origin, node) in visible.items():
        options = fixture_options(node)
        if options is not None:
            fixtures[options.get('name', name)] = (origin, node, options)
    pending = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
            pending.update(dependencies(node))
    pending.update(name for name, (_, _, opts) in fixtures.items() if opts.get('autouse'))
    visited = set()
    session = False
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        if name not in fixtures:
            session |= name in session_names
            continue
        origin, node, options = fixtures[name]
        starter = 'sync_playwright(' in ast.get_source_segment(module(origin)[0], node)
        own |= starter
        session |= starter and options.get('scope') == 'session'
        deps = dependencies(node)
        # Eine gleichnamige Override-Fixture kann die Plugin-Fixture anfordern.
        session |= name in deps and name in session_names
        pending.update(deps - {name})
    print(('d3' if own and session else 'd1' if own else 'd2') + '\t' + filename)
PY
)"; then
  echo 'FEHLER: Teil-D-Einteilung fehlgeschlagen' >&2
  exit 2
fi
own=(); fixture=(); mixed=()
while IFS=$'\t' read -r group f; do
  case "$group" in
    d1) own+=("$f") ;;
    d2) fixture+=("$f") ;;
    d3) mixed+=("$f") ;;
  esac
done <<<"$groups"
echo "Teil D: ${#candidates[@]} Dateien (${#label_hits[@]} aus Label-Grep)"
echo "D1: ${#own[@]} Dateien; D2: ${#fixture[@]} Dateien; D3: ${#mixed[@]} Dateien (je ein Prozess)"
if [[ "${RELEASE_GATE_DRY_RUN:-0}" == 1 ]]; then
  for group in a b c; do
    declare -n files="part_$group"
    printf '%s: %s Dateien\n' "$group" "${#files[@]}"
    printf '  %s\n' "${files[@]}"
  done
  for f in "${own[@]}"; do printf 'D1: %s\n' "$f"; done
  for f in "${fixture[@]}"; do printf 'D2: %s\n' "$f"; done
  for f in "${mixed[@]}"; do printf 'D3: %s\n' "$f"; done
  exit 0
fi
mkdir -p "$OUT"

declare -A pids=() pools=([a]="${POOL_A:-worker-test-api-int2}" [b]="${POOL_B:-worker-test-recipe-print-0908}"
                          [c]="${POOL_C:-worker-test-ps1}" [d]="${POOL_D:-worker-test-ps5}")
run_part() {
  local part="$1"; shift
  bash "$HERE/gate.sh" "${pools[${part:0:1}]}" "$WT" -q "$@" "${COMMON[@]}" --junitxml="$OUT/$part.xml" \
    >>"$OUT/$part.log" 2>&1
}
run_part a "${part_a[@]}" & pids[a]=$!
run_part b "${part_b[@]}" & pids[b]=$!
run_part c "${part_c[@]}" & pids[c]=$!
parts=(a b c)
if ((${#own[@]})); then
  run_part d1 "${own[@]}" & pids[d1]=$!
  parts+=(d1)
fi
if ((${#fixture[@]})); then
  # Bash bewahrt den Exit-Code für das zweite wait in der Auswertung unten auf.
  if [[ -n "${pids[d1]:-}" ]]; then wait "${pids[d1]}"; fi
  run_part d2 "${fixture[@]}" & pids[d2]=$!
  parts+=(d2)
fi
previous="${pids[d2]:-${pids[d1]:-}}"
for i in "${!mixed[@]}"; do
  if [[ -n "$previous" ]]; then wait "$previous"; fi
  part="d3-$((i + 1))"
  run_part "$part" "${mixed[$i]}" & pids[$part]=$!
  parts+=("$part")
  previous="${pids[$part]}"
done

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
