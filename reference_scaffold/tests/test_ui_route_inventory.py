"""Inventory consistency: real Flask registration and templates, not a static mirror."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from flask import Flask, session

import cafeteria
from cafeteria import db as cafeteria_db
from cafeteria.public import routes as public_routes
from sqlalchemy import text
from werkzeug.exceptions import HTTPException
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import (  # noqa: F401
    DATABASE_URL, _hidden, _login, _menu_form, _scope, database_engine,
)
from test_master_data_routes import Forms
from test_rendered_ui import browser, cafeteria_snapshot, patient_snapshot  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-route-matrix.json'
MANIFEST_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-before-manifest.json'
TEMPLATE_ROOT = ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-inventory-grok-0909'
PRIMARY = {(1440, 900), (390, 844)}
ROLES = ('Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin')
EMPTY_PATHS = ['/admin/cafeteria/menues', '/admin/rezepte', '/admin/kochbuecher',
               '/admin/grundlagen', '/admin/cafeteria/komponenten']
MENU = '/admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1'

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding='utf-8'))


def _factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_engine) -> Flask:  # noqa: F811
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    application = cafeteria.create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY='ui-inventory',
        LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-02',
        LOCAL_AUTH_ENABLED=True,
        SESSION_COOKIE_SECURE=False,
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    snapshots = {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}
    monkeypatch.setattr(public_routes, 'active_snapshot', lambda _db, profile, *a, **kw: snapshots[profile])
    return application


def test_matrix_matches_real_create_app_registration(monkeypatch, tmp_path, database_engine):  # noqa: F811
    application = _factory(monkeypatch, tmp_path, database_engine)
    registered = {
        (rule.endpoint, rule.rule, tuple(sorted(m for m in (rule.methods or set()) if m not in {'HEAD', 'OPTIONS'})))
        for rule in application.url_map.iter_rules()
    }
    documented = {
        (row['endpoint'], row['rule'], tuple(row['methods']))
        for row in _matrix()['routes']
    }
    assert registered == documented, (
        f'missing_from_matrix={sorted(registered - documented)[:20]!r} '
        f'extra_in_matrix={sorted(documented - registered)[:20]!r}'
    )


def test_every_template_file_is_in_the_matrix() -> None:
    disk = {
        str(path.relative_to(TEMPLATE_ROOT)).replace('\\', '/')
        for path in TEMPLATE_ROOT.rglob('*.html')
    }
    documented = {row['path'] for row in _matrix()['templates']}
    assert disk == documented
    assert len(disk) == 76


def test_each_route_has_owning_mp_or_explicit_unmapped() -> None:
    allowed_unmapped = {'static', 'health.live', 'health.ready'}
    for row in _matrix()['routes']:
        mp = row['owning_mp']
        assert mp, row['endpoint']
        if mp == 'unmapped':
            assert row['endpoint'] in allowed_unmapped
        else:
            assert mp.startswith('MP-')
    for template in _matrix()['templates']:
        assert template['owning_mp'].startswith('MP-')
        assert template['used_by_endpoints'] or template['kind'] in {'partial', 'layout'}


def test_roles_and_navigation_are_documented() -> None:
    common = _matrix()['common']
    for role in ('anonymous', 'Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'):
        assert role in common['roles']
    nav = common['navigation']
    assert nav['sidebar_insufficient'] is True
    for key in ('can_browse_recipes', 'can_manage_users', 'can_configure_display'):
        assert key in nav['conditionals']
        assert nav['conditionals'][key]['visible_for']


def _recipe_payload() -> dict:
    return {
        'title': 'Kartoffelstock mit Rüebli',
        'description': 'Synthetische Testrezeptur ohne Produktivdaten.',
        'servings': '4', 'servings_unit_code': 'PORTION',
        'prep_minutes': 15, 'cook_minutes': 25,
        'source': {'kind': 'manual', 'reference': None, 'url': None,
                   'note': None, 'fetched_at': None},
        'ingredients': [{
            'line_public_id': None, 'group_label': None, 'ingredient_text': 'Kartoffeln',
            'food_public_id': None, 'quantity': '800', 'unit_code': 'G', 'note': None,
            'source_kind': 'manual', 'source_reference': None, 'fetched_at': None,
        }],
        'steps': [{'instruction': 'Kartoffeln schälen und weich kochen.',
                   'duration_minutes': 25, 'image_sha256': None}],
        'tag_public_ids': [], 'images': [],
    }


def _recipe_revision(application: Flask, database_engine, user_id: int) -> tuple[str, str]:  # noqa: F811
    """Create one same-site recipe and freeze an immutable v1 revision, via the real store."""
    from cafeteria import recipe_store
    from cafeteria.auth.local_users import ActorExpectation
    from cafeteria.master_data_types import ObjectExpectation

    with database_engine.connect() as connection:
        location_id = connection.execute(
            text('SELECT id FROM cafeteria.locations WHERE active ORDER BY id')
        ).scalar_one()
        authz_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user_id}
        ).scalar_one()
    actor = ActorExpectation(user_id, int(authz_version))
    with application.test_request_context():
        session['user'] = {'id': user_id}
        session['authz_version'] = int(authz_version)
        recipe = recipe_store.create_recipe(
            database_engine, actor, _recipe_payload(), expected_location_id=int(location_id))
        revision = recipe_store.freeze_revision(
            database_engine, actor,
            ObjectExpectation(recipe.public_id, recipe.row_version),
            expected_location_id=int(location_id),
        )
    return recipe.public_id, revision.public_id


def _fixture_descriptor() -> dict:
    from cafeteria.branding_config import default_config

    users = {}
    for role, suffix, name in [('Editor', 'ed', 'Redaktion'), ('Publisher', 'ab', 'Publikation')]:
        users[f'Cafeteria.{role}'] = {
            'tid': '00000000-0000-0000-0000-000000000001',
            'oid': f'00000000-0000-0000-0000-0000000000{suffix}',
            'sub': f'inventory-{role.lower()}', 'name': name,
            'preferred_username': f'{role.lower()}@example.invalid',
        }
    users['Cafeteria.Admin'] = {
        'tid': '00000000-0000-0000-0000-000000000001',
        'oid': '00000000-0000-0000-0000-000000000002', 'sub': 'workflow-test-admin',
        'name': 'Küche', 'preferred_username': 'workflow.admin@example.invalid',
    }
    return {
        'demo_today': '2026-09-02', 'week': '2026-08-31', 'copy_week': '2026-09-07',
        'weeks': {'staff_guest': _staff_values(), 'patient': _patient_values()},
        'snapshots': {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()},
        'component': {'kind': 'side', 'name': 'Kartoffelstock', 'origin_country_code': 'CH',
                      'origin_scope': 'common', 'allergens': [], 'labels': []},
        'recipe': _recipe_payload(), 'recipe_revision': 1,
        'cookbook': {'name': 'Inventar-Kochbuch', 'description': 'Synthetische Testdaten.'},
        'master_data': {'kind': 'tag', 'code': 'INVENTORY', 'name': 'Inventar-Test'},
        'branding': {'action': 'save', 'name': 'Inventar-Testmarke', 'config': default_config()},
        'local_user': {'username': 'inventory-fixture', 'display_name': 'Inventar-Test',
                       'roles': ['Cafeteria.Editor'], 'password_policy': 'ephemeral_never_recorded'},
        'screen_template': 'cafeteria-week-photo', 'print_template': 'standard',
        'fragment': {'day': '2026-08-31', 'meal': 'LUNCH', 'option': 'MENU_1'},
        'users': users, 'roles': list(ROLES),
        'invalid': {'internal_chf': 'kein-preis', 'admin_density': 'inventory-invalid',
                    'prep_minutes': 'keine-minuten'},
    }


def _role_clients(application, engine) -> tuple[dict, int]:
    admin, user_id = _login(application, engine, ['Cafeteria.Admin'])
    clients = {'Cafeteria.Admin': admin}
    for role, claims in _fixture_descriptor()['users'].items():
        if role == 'Cafeteria.Admin':
            continue
        identifier = cafeteria_db.upsert_entra_user(engine, claims, [role])
        with engine.connect() as connection:
            version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                         {'id': identifier}).scalar_one()
        client = application.test_client()
        with client.session_transaction() as current:
            current.update(user={'id': identifier, 'name': claims['name']}, authz_version=version)
            current['_csrf_token'] = 'inventory-role-csrf'
        clients[role] = client
    return clients, user_id


def _invalid_cases(recipe_path: str) -> list[dict]:
    values = _fixture_descriptor()['invalid']
    return [dict(path=path, field=field, value=values[field], form=form, button=button,
                 marker=marker, message=message) for path, field, form, button, marker, message in [
        (MENU, 'internal_chf', '[data-menu-editor]', 'Speichern', 'err-int',
         'Preis muss als CHF-Betrag eingegeben werden.'),
        ('/admin/design/darstellung', 'admin_density', '#display-settings-form',
         'Darstellung speichern', 'admin-density-error', 'Bitte eine der angebotenen Optionen auswählen.'),
        (recipe_path, 'prep_minutes', '#recipe-editor', 'Rezept speichern', 'recipe-error',
         'Minuten müssen zwischen 0 und 10080 liegen.'),
    ]]


def _invalid_action(case: dict):
    def submit(page) -> None:
        form = page.locator(case['form'])
        field = form.locator(f'[name="{case["field"]}"]')
        if case['field'] == 'admin_density':
            field.evaluate('(el, value) => el.add(new Option("Ungültige Testoption", value))', case['value'])
            field.select_option(case['value'])
        else:
            field.fill(case['value'])
        with page.expect_response(lambda response: response.request.method == 'POST'
                                  and urlsplit(response.url).path == urlsplit(case['path']).path) as response:
            with page.expect_navigation(wait_until='domcontentloaded'):
                form.get_by_role('button', name=case['button'], exact=True).click()
        assert response.value.status == 400
        error = page.locator('#' + case['marker'])
        error.wait_for(state='visible')
        assert case['message'] in error.inner_text()
    return submit


def _prepare_inventory_entities(application, database_engine, admin_user_id) -> dict:  # noqa: F811
    from cafeteria import branding, master_data_store, recipe_store
    from cafeteria.auth.local_users import ActorExpectation, create_local_user
    from cafeteria.component_catalog_store import create_component

    data = _fixture_descriptor()
    for profile, values in data['weeks'].items():
        _save_reviewed(database_engine, profile, values)
    scope = _scope(database_engine, admin_user_id)
    c = data['component']
    component = create_component(database_engine, scope, c['kind'], c['name'],
                                 c['origin_country_code'], c['origin_scope'], c['allergens'], c['labels'])
    recipe_id, revision_id = _recipe_revision(application, database_engine, admin_user_id)
    with database_engine.connect() as connection:
        version = int(connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                         {'id': admin_user_id}).scalar_one())
    actor = ActorExpectation(admin_user_id, version)
    with application.test_request_context():
        session.update(user={'id': admin_user_id}, authz_version=version)
        book = recipe_store.create_cookbook(database_engine, actor, **data['cookbook'],
                                           expected_location_id=scope.location_id)
        tag = master_data_store.create_vocabulary(database_engine, actor=actor, **data['master_data'])
    local = data['local_user']
    user = create_local_user(database_engine, actor=actor, username=local['username'],
                             display_name=local['display_name'], roles=tuple(local['roles']),
                             password=secrets.token_urlsafe(32))
    brand = branding.change_branding(database_engine, admin_user_id, version, 0, **data['branding'])
    recipe = f'/admin/rezepte/{recipe_id}'
    paths = {
        'admin.component_detail': f"/admin/cafeteria/komponenten/{component['public_id']}",
        'admin.copy_get': '/admin/cafeteria/copy?week=2026-09-07',
        'admin.menu_get': MENU,
        'admin.header_get': '/admin/cafeteria/header?week=2026-08-31',
        'admin.service_get': '/admin/cafeteria/service?week=2026-08-31&day=2026-08-31&meal=LUNCH',
        'admin.branding_preview': f"/admin/design/marke/vorschau/{brand['revisions'][-1]['id']}",
        'admin.cookbook_edit': f'/admin/kochbuecher/{book.public_id}',
        'admin.cookbook_status': f'/admin/kochbuecher/{book.public_id}/status',
        'admin.local_user_detail': f'/admin/benutzer/{user.public_id}',
        'admin.master_data_new': '/admin/grundlagen/tags/neu',
        'admin.master_data_detail': f'/admin/grundlagen/tags/{tag.public_id}',
        'admin.print_template_editor': '/admin/vorlagen/cafeteria?week=2026-08-31',
        'admin.recipe_print_template_editor': f'/admin/vorlagen/rezepte?recipe={recipe_id}&recipe_revision={revision_id}',
        'admin.recipe_edit': recipe, 'admin.recipe_images': recipe + '/bilder',
        'admin.recipe_revisions': recipe + '/revisionen', 'admin.recipe_scale': recipe + '/skalierung',
        'admin.recipe_status': recipe + '/status',
        'admin.recipe_revision': f'{recipe}/revisionen/{revision_id}',
        'admin.screen_template_assignment': '/admin/screens/cafeteria/wochenvorlage',
        'admin.screen_template_preview': f"/admin/vorlagen/screens/cafeteria/{data['screen_template']}",
    }
    cases = _invalid_cases(recipe)
    # The recorder captures the menu editor itself (all five viewports); listing it again
    # would overwrite the same screenshot file with a duplicate manifest row.
    return {'endpoint_paths': paths,
            'extra_admin_paths': [path for key, path in paths.items() if key != 'admin.menu_get'],
            'reference_paths': [paths['admin.recipe_revision']], 'invalid_cases': cases,
            'state_captures': [(case['path'], 'invalid', _invalid_action(case)) for case in cases]}


def _resolved_captures(application, manifest) -> list[tuple[str, dict]]:
    adapter = application.url_map.bind('localhost')
    result = []
    for row in manifest['captures']:
        try:
            endpoint, _ = adapter.match(urlsplit(row['path']).path, method='GET')
        except HTTPException:
            continue
        result.append((endpoint, row))
    return result


def _visual_gaps(application, matrix, manifest) -> list:
    blocked = {endpoint for block in matrix['coverage_blocks']
               if block['status'].startswith('blocked') for endpoint in block['endpoints']}
    covered = {(endpoint, row['viewport']['width'], row['viewport']['height'])
               for endpoint, row in _resolved_captures(application, manifest)
               if row['status'] == 200 and row.get('rendered') is True}
    return sorted((route['endpoint'], width, height) for route in matrix['routes']
                  if route['visual'] and route['endpoint'] not in blocked
                  for width, height in PRIMARY if (route['endpoint'], width, height) not in covered)


def _assert_meta(manifest) -> None:
    meta = manifest['meta']
    assert meta['fixture']['status'] == 'caller_supplied'
    assert len(meta['fixture']['sha256']) == 64 and set(meta['fixture']['sha256']) <= set('0123456789abcdef')
    fonts = {path.name for path in (TEMPLATE_ROOT.parent / 'static').rglob('fira-sans-*.woff2')}
    assert len(fonts) == 4 and fonts <= {Path(path).name for path in meta['font_files']}
    assert all(meta['runtime'][key] for key in ('platform', 'python', 'playwright'))
    assert meta['demo_today'] == '2026-09-02'
    assert meta['browser_version'] and meta['captured_at']
    assert (meta['locale'], meta['timezone'], meta['dpr']) == ('de-CH', 'Europe/Zurich', 1)
    assert meta['live_requests'] is False


def _assert_states(application, matrix, manifest) -> None:
    resolved = _resolved_captures(application, manifest)
    selectors = {(endpoint, row['suffix']) for endpoint, row in resolved}
    missing = [(state['id'], capture) for state in matrix['states'] for capture in state['captures']
               if (capture['endpoint'], capture['suffix']) not in selectors]
    assert not missing, missing
    empty = [row for _, row in resolved if row['suffix'] == 'empty']
    assert len(empty) == 10 and all(row['status'] == 200 for row in empty)
    assert {(row['path'], row['viewport']['width'], row['viewport']['height']) for row in empty} == {
        (path, width, height) for path in EMPTY_PATHS for width, height in PRIMARY}
    for endpoint in ('admin.menu_get', 'admin.display_settings', 'admin.recipe_edit'):
        invalid = [row for ep, row in resolved if ep == endpoint and row['suffix'] == 'invalid']
        assert len(invalid) == 2, (endpoint, invalid)
        assert {(row['viewport']['width'], row['viewport']['height']) for row in invalid} == PRIMARY
        assert all(row['rendered'] and row['readiness']['error'] is None for row in invalid)
    assert not [block for block in manifest['coverage_blocks'] if block['status'] == 'blocked_state_not_reached']
    roles = [row for _, row in resolved if row['suffix'].startswith('role-nav-')]
    assert len(roles) == 6
    assert {(row['role'], row['viewport']['width'], row['viewport']['height']) for row in roles} == {
        (role, width, height) for role in ROLES for width, height in PRIMARY}
    admin_only = {'Benutzer & Zugriff', 'Design & Marke', 'Bereiche & Zeiten'}
    baseline = json.loads(MANIFEST_PATH.read_bytes())
    historical = manifest == baseline
    for row in roles:
        assert row['status'] == 200 and row['rendered']
        nav = set(row['nav_items'])
        if historical:
            # Preserve the versioned before capture; new captures use the four-area shell.
            assert {'Rezepte', 'Kochbücher'} <= nav
            assert admin_only <= nav if row['role'] == 'Cafeteria.Admin' else not admin_only & nav
        else:
            assert nav == {'Wochenplan', 'Menüs & Bausteine', 'Vorschau & Bildschirme', 'Einstellungen'}


def test_inventory_fixture_paths_render_for_admin(monkeypatch, tmp_path, database_engine):  # noqa: F811
    application = _factory(monkeypatch, tmp_path, database_engine)
    client, user_id = _login(application, database_engine, ['Cafeteria.Admin'])
    prepared = _prepare_inventory_entities(application, database_engine, user_id)
    results = [(endpoint, path, client.get(path).status_code) for endpoint, path in prepared['endpoint_paths'].items()]
    assert all(status == 200 for _, _, status in results), results
    for case in prepared['invalid_cases']:
        path = urlsplit(case['path']).path
        body = client.get(case['path']).text
        if case['field'] == 'internal_chf':
            data = _menu_form(_csrf=_hidden(body, '_csrf', form_action=path),
                              row_version=_hidden(body, 'row_version', form_action=path), external_chf='14.50')
        else:
            data = Forms(body).forms[path]
        data[case['field']] = case['value']
        if case['field'] == 'admin_density':
            data['action'] = 'save'
        response = client.post(path, data=data)
        assert response.status_code == 400, (path, response.status_code, response.text)
        assert f'id="{case["marker"]}"' in response.text and case['message'] in response.text, response.text


def test_matrix_roles_match_server_side_authorization(monkeypatch, tmp_path, database_engine):  # noqa: F811
    application = _factory(monkeypatch, tmp_path, database_engine)
    clients, user_id = _role_clients(application, database_engine)
    clients['anonymous'] = application.test_client()
    prepared = _prepare_inventory_entities(application, database_engine, user_id)
    adapter = application.url_map.bind('localhost')
    paths = set(prepared['extra_admin_paths'])
    for rule in application.url_map.iter_rules():
        if rule.endpoint.startswith('admin.') and 'GET' in rule.methods and rule.arguments <= {'family'}:
            paths.update(adapter.build(rule.endpoint, {'family': family} if rule.arguments else {})
                         for family in ('cafeteria', 'patienten'))
    routes = {row['endpoint']: row for row in _matrix()['routes'] if row['visual'] and 'GET' in row['methods']}
    results = []
    for path in sorted(paths):
        endpoint, _ = adapter.match(urlsplit(path).path, method='GET')
        if endpoint not in routes:
            continue
        for role, client in clients.items():
            status = client.get(path).status_code
            matches = status == 401 if role == 'anonymous' else (status != 403) == (role in routes[endpoint]['roles'])
            results.append(dict(endpoint=endpoint, path=path, role=role, status=status, matches=matches))
    assert {row['endpoint'] for row in results} == {key for key in routes if key.startswith('admin.')}
    assert all(row['matches'] for row in results), json.dumps(results, ensure_ascii=False, indent=2)


def test_inventory_invalid_browser_actions(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    from threading import Thread
    from werkzeug.serving import make_server

    application = _factory(monkeypatch, tmp_path, database_engine)
    client, user_id = _login(application, database_engine, ['Cafeteria.Admin'])
    prepared = _prepare_inventory_entities(application, database_engine, user_id)
    cookie = client.get_cookie(application.config['SESSION_COOKIE_NAME'])
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        live = f'http://127.0.0.1:{server.server_port}'
        with browser.new_context(base_url=live) as context:
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live}])
            page = context.new_page()
            for width, height in sorted(PRIMARY):
                page.set_viewport_size({'width': width, 'height': height})
                for path, _, action in prepared['state_captures']:
                    assert page.goto(path).status == 200
                    action(page)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_every_shared_state_has_owner_fixture_and_capture_selectors() -> None:
    matrix = _matrix()
    endpoints = {row['endpoint'] for row in matrix['routes']}
    assert 'role_navigation' in {state['id'] for state in matrix['states']}
    for state in matrix['states']:
        assert state['owning_mp'].startswith('MP-') and state['fixture'] and state['captures'], state
        assert all(item['endpoint'] in endpoints and 'suffix' in item for item in state['captures']), state


def test_versioned_manifest_covers_every_visual_route(monkeypatch, tmp_path, database_engine):  # noqa: F811
    application = _factory(monkeypatch, tmp_path, database_engine)
    manifest = json.loads(MANIFEST_PATH.read_bytes())
    assert not _visual_gaps(application, _matrix(), manifest), _visual_gaps(application, _matrix(), manifest)
    _assert_states(application, _matrix(), manifest)
    _assert_meta(manifest)


def _superseded_manifest(previous: bytes, wp_id: str | None) -> dict:
    manifest = json.loads(previous)
    rows = []
    for row in manifest['captures']:
        if 'readiness' in row:
            status = ('superseded_by_newer_capture' if row['readiness'].get('error') is None
                      else 'superseded_failed_readiness')
        elif row['path'] in {'/cafeteria/wochenangebot/', '/patienten/wochenplan/'}:
            status = 'invalid_blank_lazy_images'
        elif row['suffix'] == 'dialog-publish':
            status = 'invalid_hardcoded_record'
        else:
            status = 'superseded_unverified_readiness'
        rows.append({**{key: row.get(key) for key in ('path', 'viewport', 'suffix', 'screenshot', 'screenshot_sha256')},
                     'status': status, 'reason': status.replace('_', ' ')})
    return {'manifest_sha256': hashlib.sha256(previous).hexdigest(),
            'source_commit': manifest['meta'].get('source_commit'),
            'captured_at': manifest['meta'].get('captured_at'), 'superseded_by_wp': wp_id,
            'recorder_defects': ['Listener nach DOMContentLoaded entfernt.',
                                 'Feste 250-ms-Wartezeit statt Bereitschaft.', 'Publish-Dialog-Zeile hartkodiert.'],
            'rows': rows}


def test_capture_before_screenshots_and_manifest(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    sys.path.insert(0, str(EVIDENCE))
    from capture import Outputs, run_capture

    explicit = os.environ.get('UI_CAPTURE_OUT')
    promote = os.environ.get('UI_CAPTURE_PROMOTE') == '1'
    if promote and not explicit:
        pytest.fail('UI_CAPTURE_PROMOTE=1 verlangt UI_CAPTURE_OUT.')
    directory = Path(explicit) if explicit else tmp_path / 'capture'
    if (directory / 'screenshots').resolve() == (EVIDENCE / 'screenshots').resolve():
        pytest.fail('UI_CAPTURE_OUT darf die Original-PNG nicht überschreiben.')
    matrix_before, manifest_before = MATRIX_PATH.read_bytes(), MANIFEST_PATH.read_bytes()
    screenshots_before = {path.name: (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                          for path in (EVIDENCE / 'screenshots').glob('*.png')}
    application = _factory(monkeypatch, tmp_path, database_engine)
    # Imported database_engine is function-scoped: its schema/seed reset precedes every test.
    with database_engine.connect() as connection:
        for table in ('menu_weeks', 'recipes', 'cookbooks', 'menu_components', 'foods', 'tags'):
            assert connection.execute(text(f'SELECT count(*) FROM cafeteria.{table}')).scalar_one() == 0, table
    clients, user_id = _role_clients(application, database_engine)
    cookies = {role: client.get_cookie(application.config['SESSION_COOKIE_NAME']) for role, client in clients.items()}
    prepared: dict = {}

    def prepare_entities() -> dict:
        prepared.update(_prepare_inventory_entities(application, database_engine, user_id))
        # run_capture accepts only these keys; the full result stays available for the assertions below.
        return {key: prepared[key] for key in ('extra_admin_paths', 'reference_paths', 'state_captures')}

    identity = {key: value.strip() for key in ('wp_id', 'lane', 'model')
                if (value := os.environ.get('UI_CAPTURE_' + key.upper(), '')).strip()}
    outputs = Outputs.promoting(directory) if promote else Outputs.into(directory)
    manifest = run_capture(
        application, browser, cookies['Cafeteria.Admin'], cookies['Cafeteria.Editor'], snapshots_ok=True,
        out=outputs, capture_identity=identity or None, role_cookies=cookies,
        fixture_descriptor=_fixture_descriptor(), empty_paths=EMPTY_PATHS, prepare_entities=prepare_entities,
        supersedes=_superseded_manifest(manifest_before, identity.get('wp_id')) if promote else None,
    )
    assert MATRIX_PATH.read_bytes() == matrix_before
    assert MANIFEST_PATH.read_bytes() == ((directory / 'ui-before-manifest.json').read_bytes()
                                         if promote else manifest_before)
    assert {path.name: (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in (EVIDENCE / 'screenshots').glob('*.png')} == screenshots_before
    assert not _visual_gaps(application, _matrix(), manifest), _visual_gaps(application, _matrix(), manifest)
    _assert_states(application, _matrix(), manifest)
    _assert_meta(manifest)
    revision_detail = prepared['endpoint_paths']['admin.recipe_revision']
    copy_success = prepared['endpoint_paths']['admin.copy_get']
    assert outputs.manifest_paths[0].is_file()
    rendered = [row for row in manifest['captures'] if row.get('rendered')]
    assert len(rendered) >= 40
    viewports = {(row['viewport']['width'], row['viewport']['height']) for row in rendered}
    assert (1440, 900) in viewports
    assert (390, 844) in viewports
    assert (1920, 1080) in viewports
    assert manifest['meta']['locale'] == 'de-CH'
    assert manifest['meta']['timezone'] == 'Europe/Zurich'
    assert manifest['meta']['dpr'] == 1
    assert manifest['meta']['live_requests'] is False
    assert any(row['path'] == '/admin/cafeteria' for row in rendered)
    assert any(row['path'] == '/cafeteria/heute/' for row in rendered)
    assert any(row['path'].startswith('/admin/cafeteria/komponenten/') for row in rendered)
    assert any(row['suffix'] == 'anonymous-401' for row in rendered)
    assert any(row['suffix'] == 'editor-403' for row in rendered)

    detail_rows = [row for row in rendered if row['path'] == revision_detail]
    assert {(row['viewport']['width'], row['viewport']['height']) for row in detail_rows} == {
        (1440, 900), (390, 844), (1024, 768), (768, 1024), (1920, 1080)
    }
    assert all(row['status'] == 200 for row in detail_rows)
    copy_rows = [row for row in rendered if row['path'] == copy_success]
    assert {(row['viewport']['width'], row['viewport']['height']) for row in copy_rows} == {
        (1440, 900), (390, 844)
    }
    assert all(row['status'] == 200 for row in copy_rows)
    error_copy = [row for row in manifest['captures'] if row['suffix'] == 'missing-week-404']
    assert error_copy and all(row['status'] == 404 for row in error_copy)
    assert all('readiness' in row for row in rendered)
    assert all(row['readiness']['error'] is None for row in rendered)

    with application.test_client() as probe:
        assert probe.get('/admin/cafeteria').status_code == 401
