"""Generated conservative dependency selection; unknown inputs expand the gate."""
from __future__ import annotations

import ast
import re
import subprocess
from collections import defaultdict
from pathlib import Path

GUARDRAILS = (
    'test_signage_patient.py', 'test_signage_ops_browser.py',
    'test_signage_cafeteria_day.py', 'test_signage_cafeteria_week.py',
    'test_public_contracts.py', 'test_public_equal_cards_browser.py',
    'test_preview_equal_cards_browser.py',
)


def changed_paths(root: Path, base: str) -> list[str]:
    revision = subprocess.run(['rtk', 'git', 'rev-parse', '--verify', '--end-of-options', base + '^{commit}'],
                              cwd=root, shell=False, check=True, capture_output=True, text=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision):
        raise ValueError('Git did not return an exact commit ID')
    # RTK decorates porcelain diff output; plumbing retains NUL-delimited paths.
    changed = subprocess.run(['rtk', 'git', 'diff-index', '--name-only', '-z', revision, '--'],
                             cwd=root, shell=False, check=True, capture_output=True, text=True)
    untracked = subprocess.run(['rtk', 'git', 'ls-files', '--others', '--exclude-standard', '-z'],
                               cwd=root, shell=False, check=True, capture_output=True, text=True)
    return sorted(set((changed.stdout + untracked.stdout).split('\0')) - {''})


def build_map(root: Path) -> dict:
    scaffold = root / 'reference_scaffold'
    tests = sorted(p.relative_to(scaffold).as_posix() for p in (scaffold / 'tests').rglob('test_*.py'))
    paths = [*scaffold.rglob('*.py'), *(root / 'tools').glob('*.py')]
    paths = [p for p in paths if '.venv' not in p.parts and '__pycache__' not in p.parts]
    sources = {p.relative_to(root).as_posix(): p.read_text() for p in paths}
    modules = {}
    for path in paths:
        relative = path.relative_to(scaffold) if path.is_relative_to(scaffold) else path.relative_to(root)
        module = '.'.join(relative.with_suffix('').parts)
        if module.endswith('.__init__'):
            module = module[:-9]
        modules[module] = path.relative_to(root).as_posix()
        if relative.parts[0] in {'tests', 'tools'}:
            modules[path.stem] = path.relative_to(root).as_posix()
    reverse: dict[str, set[str]] = defaultdict(set)
    test_sources = {name: source for name, source in sources.items()
                    if name.startswith('reference_scaffold/tests/')}
    for name, source in sources.items():
        tree = ast.parse(source, filename=name)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr in {'route', 'get', 'post', 'put', 'delete', 'patch'}
                            and decorator.args and isinstance(decorator.args[0], ast.Constant)
                            and isinstance(decorator.args[0].value, str)):
                        fragments = [part for part in re.split(r'<[^>]+>', decorator.args[0].value)
                                     if len(part.strip('/')) >= 4]
                        for consumer, test_source in test_sources.items():
                            if any(fragment in test_source for fragment in fragments):
                                reverse[name].add(consumer)
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ''
                if node.level:
                    relative = Path(name).relative_to('reference_scaffold') if name.startswith('reference_scaffold/') else Path(name)
                    package = list(relative.parent.parts)
                    prefix = '.'.join(package[:len(package) - node.level + 1] + ([prefix] if prefix else []))
                imported = [prefix, *(prefix + '.' + alias.name for alias in node.names)]
            for module in imported:
                if module in modules:
                    reverse[modules[module]].add(name)
    templates = scaffold / 'cafeteria' / 'templates'
    assets = scaffold / 'cafeteria' / 'static'
    text_paths = [p for base in [templates, assets] for p in base.rglob('*')
                  if p.is_file() and p.suffix in {'.html', '.css', '.js'}]
    text_sources = {p.relative_to(root).as_posix(): p.read_text() for p in text_paths}
    for path in text_paths:
        name = path.relative_to(root).as_posix()
        resource_name = path.relative_to(templates if path.is_relative_to(templates) else assets).as_posix()
        for consumer, source in {**sources, **text_sources}.items():
            if consumer != name and (resource_name in source or path.name in source):
                reverse[name].add(consumer)
    mapping = {}
    for name in {*sources, *text_sources}:
        seen = {name}
        pending = [name]
        while pending:
            current = pending.pop()
            for consumer in reverse[current] - seen:
                seen.add(consumer)
                pending.append(consumer)
        selected = sorted(p.removeprefix('reference_scaffold/') for p in seen
                          if p.startswith('reference_scaffold/tests/test_') and p.endswith('.py'))
        if selected:
            mapping[name] = selected
    test_index = {name: index for index, name in enumerate(tests)}
    groups: list[tuple[int, ...]] = []
    group_index: dict[tuple[int, ...], int] = {}
    compact = {}
    for name, selected in sorted(mapping.items()):
        indices = tuple(test_index[test] for test in selected)
        if indices not in group_index:
            group_index[indices] = len(groups)
            groups.append(indices)
        compact[name] = group_index[indices]
    return {'version': 2, 'tests': tests, 'groups': groups, 'files': compact}


def select_tests(changed: list[str], impact: dict) -> tuple[list[str], list[str]]:
    all_tests = set(impact['tests'])
    selected: set[str] = set()
    reasons = []
    for name in changed:
        if name.startswith(('docs/', '.claude/')) and not any(x in name for x in ('snapshot', 'evidence')):
            continue
        direct = name.removeprefix('reference_scaffold/')
        if direct in all_tests:
            selected.add(direct)
        mapped = impact['files'].get(name, [])
        if isinstance(mapped, int):
            mapped = [impact['tests'][index] for index in impact['groups'][mapped]]
        if mapped:
            selected.update(mapped)
        elif direct not in all_tests:
            selected.update(all_tests)
            reasons.append('unknown dependency, full selection: ' + name)
        if any(part in name for part in ('templates/', '/static/', 'snapshot', 'signage', 'public')):
            selected.update('tests/' + file for file in GUARDRAILS if 'tests/' + file in all_tests)
            # Dynamic Jinja names and CSS effects are not provable from Python coverage.
            selected.update(test for test in all_tests if 'browser' in test or '/test_ui_' in test)
            reasons.append('UI guardrails and browser safety margin: ' + name)
    if not selected:
        selected.update(test for test in all_tests if Path(test).name in {
            'test_tools_test_gate.py', 'test_public_contracts.py', 'test_api_docs.py',
        })
        reasons.append('minimum guardrail for empty/documentation-only diff')
    return sorted(selected), reasons
