#!/usr/bin/env python3
"""Offline structural validator for the backlog-0909 work-package manifests.

Reads only the manifest files named on the command line. It makes no network,
database, provider or subprocess call, imports nothing outside the standard
library, and never guesses a repository path: every path it knows comes from the
manifests themselves.

Usage:
    python validate-plan.py --source-commit <sha> <manifest> [<manifest> ...]

Modes:
    full     every one of the 35 backlog requirements is covered by the given
             manifests. Only this mode can report RESULT=PASS (exit 0).
    partial  fewer slices were given. Dependencies that point into a slice which
             is not loaded are listed as unresolved instead of failing, reserved
             cross-slice anchors are named explicitly, and the run reports
             RESULT=PARTIAL (exit 2). A partial run is never a full pass.

Exit codes: 0 full pass, 1 failures found, 2 partial run without failures.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# The 35 backlog identifiers of docs/BACKLOG.md, grouped by owning slice.
SLICE_REQUIREMENTS = {
    'recipes': ('BAS-001', 'REC-001', 'REC-002', 'REC-003', 'REC-004', 'REC-005',
                'REC-006', 'REC-007', 'NUT-001', 'OFF-001'),
    'operations': ('CALC-001', 'INV-001', 'ORD-001', 'PKS-001', 'TRN-001', 'OPS-001'),
    'surfaces': ('UI-001', 'UI-002', 'UI-003', 'CAT-001', 'DSP-001', 'QA-001', 'DATA-001',
                 'BRD-001', 'TPL-001', 'TPL-002', 'TPL-003', 'API-001', 'ICO-001',
                 'ICO-002', 'SCR-001', 'SCR-002', 'SCR-003', 'IAM-001', 'IAM-002'),
}
ALL_REQUIREMENTS = frozenset(sum(SLICE_REQUIREMENTS.values(), ()))

# Package-id prefixes per slice, so a dependency into an unloaded slice can be
# told apart from a genuinely missing one.
SLICE_ID_PREFIXES = {
    'recipes': ('MP-REC-', 'MP-BAS-', 'MP-NUT-', 'MP-OFF-'),
    'operations': ('MP-CALC-', 'MP-INV-', 'MP-ORD-', 'MP-PKS-', 'MP-TRN-', 'MP-OPS-'),
    'surfaces': ('MP-UI-', 'MP-SCR-', 'MP-TPL-', 'MP-API-', 'MP-ICO-', 'MP-IAM-',
                 'MP-QA-', 'MP-DATA-', 'MP-BRD-', 'MP-CAT-', 'MP-DSP-'),
}
# Cross-slice anchors reserved by Root in the planning contract of 9 September 2026.
RESERVED_RECIPE_ANCHORS = frozenset({
    'MP-BAS-SCHEMA27', 'MP-BAS-FOUNDATIONS', 'MP-REC-BINDINGS', 'MP-REC-DATA-DRAFTS',
    'MP-REC-PDF-RELEASE', 'MP-REC-IMPORT-PARSER', 'MP-REC-SNAPSHOT-V2',
    'MP-REC-FREEZE-V2', 'MP-REC-IMPORT-BATCH', 'MP-REC-PLAN-PORTIONS',
    'MP-REC-SHOPPING-AGGREGATE',
})

REQUIRED_TOP_LEVEL = ('schema_version', 'slice', 'source_commit', 'requirements',
                      'work_packages')
REQUIRED_FIELDS = ('id', 'title', 'requirement_ids', 'kind', 'status', 'depends_on',
                   'existing_wp_id', 'sdd_sections', 'source_anchors', 'task',
                   'acceptance_criteria', 'contract_files', 'wiring_files', 'owned_files',
                   'forbidden_paths', 'migration_group', 'test_plan', 'external_inputs',
                   'risk', 'effort', 'preferred_lane', 'eligible_lanes',
                   'completion_evidence', 'rollback')
NON_EMPTY_FIELDS = ('id', 'title', 'requirement_ids', 'kind', 'status', 'sdd_sections',
                    'source_anchors', 'task', 'acceptance_criteria', 'owned_files',
                    'test_plan', 'risk', 'effort', 'preferred_lane', 'eligible_lanes',
                    'completion_evidence', 'rollback')
READ_ONLY_FIELD = 'read_only_contract_files'
OWNERSHIP_FIELDS = ('contract_files', 'wiring_files', 'owned_files')
STATUSES = frozenset({'READY', 'PLANNED', 'IN_PROGRESS', 'AWAITING_EXTERNAL',
                      'REVIEWED_LOCAL', 'INTEGRATED', 'DEPLOYED', 'ACCEPTED'})
KINDS = frozenset({'implementation', 'research', 'verification', 'external_acceptance',
                   'release'})
# An ownership claim is a repository-relative path, optionally marked as not yet
# existing with a proposed: prefix, optionally carrying a <ROOT_RESERVED_...>
# placeholder segment. Globs are not allowed: a write claim names one file.
CLAIM = re.compile(r'(?:proposed:)?[A-Za-z0-9._<>/-]+(?::[A-Za-z0-9._-]+)?')
# forbidden_paths are exclusion patterns, so they additionally allow * and may
# scope a symbol inside a file. They are never ownership claims.
PATTERN = re.compile(r'[A-Za-z0-9._<>/*-]+(?::[A-Za-z0-9._-]+)?')
PATTERN_FIELDS = ('forbidden_paths',)
PACKAGE_ID = re.compile(r'MP-[A-Z0-9]+(?:-[A-Z0-9]+)+')
STRING_FIELDS = ('id', 'title', 'kind', 'status', 'task', 'risk', 'effort',
                 'preferred_lane', 'rollback')
STRING_LIST_FIELDS = ('requirement_ids', 'depends_on', 'sdd_sections', 'source_anchors',
                      'acceptance_criteria', *OWNERSHIP_FIELDS, 'forbidden_paths',
                      'external_inputs', 'eligible_lanes', 'completion_evidence')


def text_value(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: object) -> bool:
    return isinstance(value, list) and all(text_value(item) for item in value)


def split_claim(claim: str) -> tuple[str, str]:
    """Return (bare path, symbol) for a path claim; symbol is '' when absent."""
    rest = claim[len('proposed:'):] if claim.startswith('proposed:') else claim
    path, separator, symbol = rest.partition(':')
    return path, symbol if separator else ''


def claim_problem(claim: object, *, pattern: bool = False) -> str | None:
    if not isinstance(claim, str) or not claim.strip():
        return 'not a non-empty string'
    if claim != claim.strip():
        return 'has surrounding whitespace'
    grammar = PATTERN if pattern else CLAIM
    if grammar.fullmatch(claim) is None:
        return ('does not match the allowed exclusion-pattern syntax' if pattern
                else 'does not match the allowed claim syntax')
    path, _ = split_claim(claim)
    if path.startswith('/') or '\\' in path or {'.', '..'} & set(path.split('/')):
        return 'is not a repository-relative path'
    return None


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def load(path: Path, report: Report) -> dict | None:
    try:
        plan = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError) as error:
        report.fail(f'{path.name}: unreadable manifest: {error}')
        return None
    if not isinstance(plan, dict):
        report.fail(f'{path.name}: manifest is not an object')
        return None
    for key in REQUIRED_TOP_LEVEL:
        if key not in plan:
            report.fail(f'{path.name}: missing top-level key {key}')
    if type(plan.get('schema_version')) is not int or plan['schema_version'] != 1:
        report.fail(f'{path.name}: schema_version must be integer 1')
    for key in ('slice', 'source_commit'):
        if not text_value(plan.get(key)):
            report.fail(f'{path.name}: {key} must be a non-empty string')
            return None
    if not string_list(plan.get('requirements')):
        report.fail(f'{path.name}: requirements must be a list of non-empty strings')
        return None
    if not isinstance(plan.get('work_packages'), list):
        report.fail(f'{path.name}: work_packages is not a list')
        return None
    if not plan['work_packages']:
        report.fail(f'{path.name}: empty work_packages')
    return plan


def check_shapes(wp: dict, where: str, report: Report) -> bool:
    """Reject malformed field types before iteration, hashing or graph insertion."""
    before = len(report.failures)
    for field in STRING_FIELDS:
        if not text_value(wp.get(field)):
            report.fail(f'{where}: {field} must be a non-empty string')
    for field in (*STRING_LIST_FIELDS, READ_ONLY_FIELD, 'proposed_files'):
        if field not in wp and field not in STRING_LIST_FIELDS:
            continue
        value = wp.get(field)
        if not isinstance(value, list):
            report.fail(f'{where}: {field} is not a list')
        elif not string_list(value):
            report.fail(f'{where}: {field} entry not a non-empty string')
    for field in ('existing_wp_id', 'migration_group'):
        if wp.get(field) is not None and not text_value(wp[field]):
            report.fail(f'{where}: {field} must be null or a non-empty string')
    tests = wp.get('test_plan')
    if not isinstance(tests, list):
        report.fail(f'{where}: test_plan is not a list')
    else:
        for test in tests:
            if (not isinstance(test, dict) or not text_value(test.get('kind'))
                    or not text_value(test.get('command'))
                    or not string_list(test.get('assertions')) or not test['assertions']):
                report.fail(f'{where}: test_plan entry requires kind/command/assertions')
    return len(report.failures) == before


def check_package(name: str, wp: dict, report: Report, declared: frozenset[str]) -> bool:
    wp_id = wp.get('id') if isinstance(wp.get('id'), str) else '<no id>'
    where = f'{name}:{wp_id}'
    for field in REQUIRED_FIELDS:
        if field not in wp:
            report.fail(f'{where}: missing field {field}')
    for field in NON_EMPTY_FIELDS:
        if field in wp and not wp[field]:
            report.fail(f'{where}: empty {field}')
    if not check_shapes(wp, where, report):
        return False
    if PACKAGE_ID.fullmatch(wp['id']) is None:
        report.fail(f'{where}: invalid package id')
    for dependency in wp['depends_on']:
        if PACKAGE_ID.fullmatch(dependency) is None:
            report.fail(f'{where}: invalid depends_on entry {dependency!r}')
    if wp.get('status') not in STATUSES:
        report.fail(f'{where}: unknown status {wp.get("status")!r}')
    if wp.get('kind') not in KINDS:
        report.fail(f'{where}: unknown kind {wp.get("kind")!r}')
    for requirement in wp['requirement_ids']:
        if requirement not in declared:
            report.fail(f'{where}: requirement_ids entry {requirement} is outside this slice')

    claims: dict[str, list[str]] = {}
    for field in (*OWNERSHIP_FIELDS, READ_ONLY_FIELD, 'proposed_files', 'forbidden_paths'):
        value = wp.get(field)
        if value is None:
            continue
        if not isinstance(value, list):
            report.fail(f'{where}: {field} is not a list')
            continue
        for claim in value:
            problem = claim_problem(claim, pattern=field in PATTERN_FIELDS)
            if problem is not None:
                report.fail(f'{where}: {field} entry {claim!r} {problem}')
                continue
            claims.setdefault(field, []).append(claim)

    owned = {split_claim(item)[0] for item in claims.get('owned_files', ())}
    for field in ('contract_files', 'wiring_files'):
        for claim in claims.get(field, ()):
            path, symbol = split_claim(claim)
            if path not in owned:
                report.fail(f'{where}: {field} entry {claim} is not an owned write')
            elif symbol:
                report.warn(f'{where}: {field} entry {claim} carries a symbol suffix; '
                            f'symbol anchors belong in source_anchors')
    for claim in claims.get(READ_ONLY_FIELD, ()):
        path, _ = split_claim(claim)
        if path in owned:
            report.fail(f'{where}: {claim} is both owned and read-only')
    if READ_ONLY_FIELD in wp and not wp.get('contract_files'):
        report.warn(f'{where}: contract_files is empty after the read-only split; '
                    f'no owned contract file is declared')
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('manifests', nargs='+', type=Path,
                        help='work-package manifests to validate')
    parser.add_argument('--source-commit', required=True,
                        help='expected backlog source commit of every manifest')
    parser.add_argument('--quiet', action='store_true',
                        help='print only the summary, the notes and the failures')
    options = parser.parse_args(argv)

    report = Report()
    plans: dict[str, dict] = {}
    seen_paths: set[Path] = set()
    seen_names: set[str] = set()
    for path in options.manifests:
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as error:
            report.fail(f'{path.name}: unreadable manifest path: {error}')
            continue
        if resolved in seen_paths or path.name in seen_names:
            report.fail(f'{path.name}: duplicate manifest path or basename')
            continue
        seen_paths.add(resolved)
        seen_names.add(path.name)
        plan = load(path, report)
        if plan is None:
            continue
        if plan.get('source_commit') != options.source_commit:
            report.fail(f'{path.name}: source_commit {plan.get("source_commit")!r} '
                        f'is not the expected {options.source_commit!r}')
        plans[path.name] = plan

    covered: set[str] = set()
    loaded_slices: set[str] = set()
    packages: dict[str, tuple[str, dict]] = {}
    graph: dict[str, list[str]] = {}
    for name, plan in plans.items():
        raw_slice = plan.get('slice')
        slice_name: str = raw_slice if isinstance(raw_slice, str) else ''
        if slice_name in loaded_slices:
            report.fail(f'{name}: duplicate slice {slice_name}')
        loaded_slices.add(slice_name)
        expected = SLICE_REQUIREMENTS.get(slice_name)
        declared = frozenset(plan.get('requirements') or ())
        if expected is None:
            report.fail(f'{name}: unknown slice {slice_name!r}')
        elif declared != frozenset(expected):
            report.fail(f'{name}: declared requirements do not match slice {slice_name}')
        slice_covered: set[str] = set()
        for wp in plan['work_packages']:
            if not isinstance(wp, dict):
                report.fail(f'{name}: work package is not an object')
                continue
            if not check_package(name, wp, report, declared):
                continue
            slice_covered.update(set(wp['requirement_ids']) & set(expected or ()))
            wp_id = wp.get('id')
            if isinstance(wp_id, str) and wp_id in packages:
                report.fail(f'{name}: duplicate package id {wp_id} '
                            f'(also in {packages[wp_id][0]})')
            elif isinstance(wp_id, str):
                packages[wp_id] = (name, wp)
                graph[wp_id] = wp['depends_on']
        missing_slice = set(expected or ()) - slice_covered
        if missing_slice:
            report.fail(f'{name}: requirement coverage gap: {sorted(missing_slice)}')
        covered |= slice_covered

    unloaded = {slice_name for slice_name in SLICE_ID_PREFIXES} - loaded_slices
    unloaded_prefixes = tuple(prefix for slice_name in unloaded
                              for prefix in SLICE_ID_PREFIXES[slice_name])
    full = covered == ALL_REQUIREMENTS
    unresolved_reserved: set[str] = set()
    unresolved_other: set[str] = set()
    for wp_id, dependencies in graph.items():
        for dependency in dependencies:
            if dependency in packages:
                continue
            if not full and dependency.startswith(unloaded_prefixes):
                (unresolved_reserved if dependency in RESERVED_RECIPE_ANCHORS
                 else unresolved_other).add(dependency)
            else:
                report.fail(f'{packages[wp_id][0]}:{wp_id}: dependency {dependency} '
                            f'does not resolve')

    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            report.fail(f'dependency cycle: {" -> ".join(stack + [node])}')
            return
        state[node] = 1
        for nxt in graph.get(node, ()):
            if nxt in graph:
                visit(nxt, stack + [node])
        state[node] = 2

    for node in graph:
        visit(node, [])

    if full:
        missing = sorted(ALL_REQUIREMENTS - covered)
        if missing:
            report.fail(f'requirement coverage gap: {missing}')
    else:
        report.note(f'partial run: slices loaded {sorted(loaded_slices)}, '
                    f'not loaded {sorted(unloaded)}')
        report.note(f'requirements covered {len(covered)}/{len(ALL_REQUIREMENTS)}; '
                    f'missing {sorted(ALL_REQUIREMENTS - covered)}')
        if unresolved_reserved:
            report.note(f'unresolved reserved recipe anchors: '
                        f'{sorted(unresolved_reserved)}')
        if unresolved_other:
            report.note(f'unresolved other cross-slice ids: {sorted(unresolved_other)}')

    print(f'manifests={len(plans)} packages={len(packages)} '
          f'requirements={len(covered)}/{len(ALL_REQUIREMENTS)} '
          f'failures={len(report.failures)} warnings={len(report.warnings)}')
    for line in report.notes:
        print(f'NOTE {line}')
    for line in ([] if options.quiet else report.warnings):
        print(f'WARN {line}')
    for line in report.failures:
        print(f'FAIL {line}')
    if report.failures:
        print('RESULT=FAIL')
        return 1
    if not full:
        print('RESULT=PARTIAL not-a-full-pass')
        return 2
    print('RESULT=PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
