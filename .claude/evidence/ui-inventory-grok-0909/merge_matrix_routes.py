"""Merge newly registered routes/templates into the versioned matrix without dropping density metadata."""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cafeteria  # noqa: E402
from build_matrix import TEMPLATE_ROOT, build, classify, capability_of, fixture_for, hooks_for, layout_variant, method_roles_for, owning_mp, roles_for, states_for, templates_in, unwrap, view_source  # noqa: E402
from cafeteria.db import SCHEMA_VERSION  # noqa: E402

MATRIX_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-route-matrix.json'
MANIFEST_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-before-manifest.json'


def _key(row: dict) -> tuple:
    return (row['endpoint'], row['rule'], tuple(row['methods']))


def _density_stub(endpoint: str, mp: str, *, visual: bool, states: list[str]) -> dict:
    if not visual:
        return {
            'mockups': [],
            'rules': [],
            'acceptance': [],
            'owning_mp': mp,
            'core_task': endpoint,
            'example_url': '',
            'example_semantics': 'Runtime registration merged from create_app().',
            'fixture_source': 'reference_scaffold/tests/test_ui_route_inventory.py',
            'state_evidence': {},
            'browser_status': 'not_applicable',
            'usability_status': 'not_applicable',
            'source_status': 'verified_runtime_registration',
        }
    return {
        'mockups': ['M01', 'M20'],
        'rules': [f'R{i:02d}' for i in range(1, 11)],
        'acceptance': ['A01'],
        'owning_mp': mp,
        'core_task': endpoint,
        'example_url': '',
        'example_semantics': 'Runtime registration merged from create_app().',
        'fixture_source': 'reference_scaffold/tests/test_ui_route_inventory.py',
        'state_evidence': {state: 'not_run' for state in states},
        'browser_status': 'not_run',
        'usability_status': 'not_run',
        'source_status': 'verified_runtime_registration',
    }


def main() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    existing = {_key(row): row for row in matrix['routes']}
    app = cafeteria.create_app()
    added = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.endpoint, item.rule)):
        methods = sorted(m for m in (rule.methods or set()) if m not in {'HEAD', 'OPTIONS'})
        view = app.view_functions.get(rule.endpoint)
        source = view_source(view) if view else ''
        templates = templates_in(rule.endpoint, source)
        classification = classify(rule.endpoint, rule.rule, set(methods), templates, source)
        capability = capability_of(source, view, tuple(rule.arguments or ()))
        mp = owning_mp(rule.endpoint, classification)
        if mp == 'unmapped' and rule.endpoint.startswith('admin.'):
            if rule.endpoint.startswith('admin.cost_'):
                mp = 'MP-UI-FOUNDATIONS'
            elif rule.endpoint.startswith('admin.inventory_'):
                mp = 'MP-UI-FOUNDATIONS'
            elif rule.endpoint.startswith('admin.order_'):
                mp = 'MP-UI-COPY-IMPORT'
            elif rule.endpoint.startswith('admin.courses_'):
                mp = 'MP-UI-MENU-EDITOR'
        row = {
            'endpoint': rule.endpoint,
            'rule': rule.rule,
            'methods': methods,
            'blueprint': rule.endpoint.split('.')[0] if '.' in rule.endpoint else '',
            'classification': classification,
            'visual': classification in {'html', 'html_fragment'},
            'templates': templates,
            'capability': capability,
            'roles': roles_for(capability, classification, rule.endpoint),
            'method_roles': method_roles_for(rule.endpoint),
            'layout_variant': layout_variant(rule.endpoint, templates),
            'owning_mp': mp,
            'family_variants': [],
            'module': getattr(__import__('inspect').getmodule(unwrap(view)), '__name__', None) if view else None,
            'source_discovered': True,
            'fixture': fixture_for(rule.endpoint, classification),
            'states': states_for(rule.endpoint, classification),
            'hooks': hooks_for(rule.endpoint, templates),
        }
        row['density'] = _density_stub(rule.endpoint, mp, visual=row['visual'], states=row['states'])
        row['density']['example_url'] = rule.rule.replace('<any(cafeteria, patienten):family>', 'cafeteria')
        key = _key(row)
        if key not in existing:
            matrix['routes'].append(row)
            existing[key] = row
            added.append(rule.endpoint)

    fresh = build()
    templates_by_path = {item['path']: item for item in fresh['templates']}
    known = {item['path'] for item in matrix['templates']}
    for path, item in templates_by_path.items():
        disk = TEMPLATE_ROOT / path
        item = deepcopy(item)
        item['sha256'] = hashlib.sha256(disk.read_bytes()).hexdigest()
        if path not in known:
            matrix['templates'].append(item)
            known.add(path)
        else:
            for row in matrix['templates']:
                if row['path'] == path:
                    row['sha256'] = item['sha256']
                    if not row.get('used_by_endpoints') and item.get('used_by_endpoints'):
                        row['used_by_endpoints'] = item['used_by_endpoints']
                    break

    for row in matrix['routes']:
        density = row.setdefault('density', {})
        if not density.get('example_url'):
            density['example_url'] = row['rule'].replace('<any(cafeteria, patienten):family>', 'cafeteria')
        if not density.get('acceptance'):
            density['acceptance'] = ['A01']
        if row.get('visual'):
            if not density.get('mockups'):
                density['mockups'] = ['M01', 'M20']
            if not density.get('rules'):
                density['rules'] = [f'R{i:02d}' for i in range(1, 11)]
            if row.get('states') and not density.get('state_evidence'):
                density['state_evidence'] = {state: 'not_run' for state in row['states']}
            density.setdefault('browser_status', 'not_run')
            density.setdefault('usability_status', 'not_run')
        else:
            density.setdefault('browser_status', 'not_applicable')
            density.setdefault('usability_status', 'not_applicable')
        density.setdefault('source_status', 'verified_runtime_registration')
        density.setdefault('fixture_source', 'reference_scaffold/tests/test_ui_route_inventory.py')
        if row.get('owning_mp') == 'unmapped' and row['endpoint'].startswith('admin.'):
            if row['endpoint'].startswith('admin.cost_'):
                row['owning_mp'] = 'MP-UI-FOUNDATIONS'
            elif row['endpoint'].startswith('admin.inventory_'):
                row['owning_mp'] = 'MP-UI-FOUNDATIONS'
            elif row['endpoint'].startswith('admin.order_'):
                row['owning_mp'] = 'MP-UI-COPY-IMPORT'
            elif row['endpoint'].startswith('admin.courses_'):
                row['owning_mp'] = 'MP-UI-MENU-EDITOR'
            if 'density' in row:
                row['density']['owning_mp'] = row['owning_mp']

    post_only = {'admin.cost_preview'}
    csv_download = {'admin.order_basket_csv'}
    blocks = {block['id']: block for block in matrix['coverage_blocks']}
    if 'post_only_html_form' not in blocks:
        matrix['coverage_blocks'].append({
            'id': 'post_only_html_form',
            'reason': 'POST-only HTML previews are exercised through form fixtures, not bare GET screenshots.',
            'endpoints': sorted(post_only),
            'status': 'blocked_post_only_html',
        })
    else:
        block = blocks['post_only_html_form']
        block['endpoints'] = sorted(set(block.get('endpoints', [])) | post_only)
    if 'native_csv_bytes' not in blocks:
        matrix['coverage_blocks'].append({
            'id': 'native_csv_bytes',
            'reason': 'CSV attachment bytes are separate from HTML screenshots.',
            'endpoints': sorted(csv_download),
            'status': 'blocked_classified_download',
        })
    else:
        block = blocks['native_csv_bytes']
        block['endpoints'] = sorted(set(block.get('endpoints', [])) | csv_download)

    route_mp = {item['endpoint']: item['owning_mp'] for item in matrix['routes']}
    for row in matrix['templates']:
        if row.get('owning_mp', 'unmapped') == 'unmapped':
            if row.get('used_by_endpoints'):
                row['owning_mp'] = route_mp.get(row['used_by_endpoints'][0], 'MP-UI-REF-WORKSPACE')
            elif row['kind'] in {'partial', 'layout'}:
                row['owning_mp'] = 'MP-UI-MACROS'
            else:
                row['owning_mp'] = 'MP-UI-REF-WORKSPACE'
    matrix['meta']['schema'] = SCHEMA_VERSION
    matrix['meta']['route_count'] = len(matrix['routes'])
    matrix['meta']['template_count'] = len(matrix['templates'])
    matrix['meta']['html_route_count'] = sum(1 for row in matrix['routes'] if row['visual'])
    MATRIX_PATH.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    current = manifest['current_inventory']
    current['source_commit'] = matrix['meta']['source_commit']
    current['schema'] = SCHEMA_VERSION
    current['route_count'] = matrix['meta']['route_count']
    current['template_count'] = matrix['meta']['template_count']
    from urllib.parse import urlsplit
    from werkzeug.exceptions import HTTPException
    adapter = app.url_map.bind('localhost')
    blocked = {endpoint for block in matrix['coverage_blocks']
               if block['status'].startswith('blocked') for endpoint in block['endpoints']}
    covered_endpoints = set()
    for row in manifest['captures']:
        if row.get('status') != 200 or row.get('rendered') is not True:
            continue
        try:
            endpoint, _ = adapter.match(urlsplit(row['path']).path, method='GET')
        except HTTPException:
            continue
        covered_endpoints.add(endpoint)
    uncaptured = sorted(
        row['endpoint'] for row in matrix['routes']
        if row['visual'] and row['endpoint'] not in blocked and row['endpoint'] not in covered_endpoints
    )
    current['uncaptured_visual_endpoints'] = uncaptured
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'added_routes={len(added)} endpoints={added}')


if __name__ == '__main__':
    main()
