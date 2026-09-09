"""Inventory consistency: real Flask registration and templates, not a static mirror."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from flask import Flask, session

import cafeteria
from cafeteria import db as cafeteria_db
from cafeteria.public import routes as public_routes
from sqlalchemy import text
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser, cafeteria_snapshot, patient_snapshot  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-route-matrix.json'
MANIFEST_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-before-manifest.json'
TEMPLATE_ROOT = ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-inventory-grok-0909'

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
    assert len(disk) == 75


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
    payload = {
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
    with application.test_request_context():
        session['user'] = {'id': user_id}
        session['authz_version'] = int(authz_version)
        recipe = recipe_store.create_recipe(
            database_engine, actor, payload, expected_location_id=int(location_id))
        revision = recipe_store.freeze_revision(
            database_engine, actor,
            ObjectExpectation(recipe.public_id, recipe.row_version),
            expected_location_id=int(location_id),
        )
    return recipe.public_id, revision.public_id


def test_capture_before_screenshots_and_manifest(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    sys.path.insert(0, str(EVIDENCE))
    from capture import Outputs, run_capture  # noqa: E402

    from cafeteria.component_catalog_store import create_component
    from test_admin_workflow_routes import _scope

    matrix_before = MATRIX_PATH.read_bytes()
    manifest_before = MANIFEST_PATH.read_bytes()
    screenshots_before = {
        path.name: path.stat().st_mtime_ns
        for path in sorted((EVIDENCE / 'screenshots').glob('*.png'))
    }
    application = _factory(monkeypatch, tmp_path, database_engine)
    _save_reviewed(database_engine, 'staff_guest', _staff_values())
    _save_reviewed(database_engine, 'patient', _patient_values())
    client, user_id = _login(application, database_engine, ['Cafeteria.Admin'])
    editor_id = cafeteria_db.upsert_entra_user(
        database_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000001',
            'oid': '00000000-0000-0000-0000-0000000000ed',
            'sub': 'inventory-editor',
            'name': 'Redaktion',
            'preferred_username': 'editor@example.invalid',
        },
        ['Cafeteria.Editor'],
    )
    with database_engine.begin() as connection:
        editor_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
            {'id': editor_id},
        ).scalar_one()
    editor_client = application.test_client()
    with editor_client.session_transaction() as current:
        current['user'] = {'id': editor_id, 'name': 'Redaktion'}
        current['authz_version'] = editor_version
        current['_csrf_token'] = 'inventory-editor-csrf'
    scope = _scope(database_engine, user_id)
    component = create_component(
        database_engine, scope, 'side', 'Kartoffelstock', 'CH', 'common', (), (),
    )
    cookie = client.get_cookie(application.config['SESSION_COOKIE_NAME'])
    editor_cookie = editor_client.get_cookie(application.config['SESSION_COOKIE_NAME'])
    detail = f"/admin/cafeteria/komponenten/{component['public_id']}"
    recipe_id, revision_id = _recipe_revision(application, database_engine, user_id)
    revision_detail = f'/admin/rezepte/{recipe_id}/revisionen/{revision_id}'
    # The saved week 2026-08-31 is the real prior week of 2026-09-07, whose target
    # week does not exist yet, so this renders the actual copy form instead of a 404.
    copy_success = '/admin/cafeteria/copy?week=2026-09-07'
    # An ordinary regression run writes to a throwaway path. Only an explicit capture
    # invocation may build a separate new evidence set; neither touches the baseline.
    explicit = os.environ.get('UI_CAPTURE_OUT')
    outputs = Outputs.into(Path(explicit) if explicit else tmp_path / 'capture')
    manifest = run_capture(
        application, browser, cookie, editor_cookie, snapshots_ok=True,
        extra_admin_paths=[detail, revision_detail, copy_success],
        reference_paths=[revision_detail],
        out=outputs,
    )
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

    assert MATRIX_PATH.read_bytes() == matrix_before
    assert MANIFEST_PATH.read_bytes() == manifest_before
    assert {
        path.name: path.stat().st_mtime_ns
        for path in sorted((EVIDENCE / 'screenshots').glob('*.png'))
    } == screenshots_before
