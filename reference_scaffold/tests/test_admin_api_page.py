from __future__ import annotations

import re
import json
from datetime import date, timedelta
from collections.abc import Iterator
from pathlib import Path
from threading import Thread

import pytest
from flask import Blueprint, Flask
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from cafeteria import db as database
from cafeteria.admin import workflow_routes
from cafeteria.security import csrf_token
from cafeteria.ui import register_ui

from test_admin_workflow_routes import (
    APP_PASSWORD,
    BACKUP_PASSWORD,
    DATABASE_URL,
    ISSUER_PASSWORD,
    ROOT,
    _drop_schema,
    _login,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

API_CSS = Path(__file__).resolve().parents[1] / 'cafeteria/static/admin-settings-schnittstellen.css'


def test_api_settings_css_keeps_shared_row_actions() -> None:
    css = API_CSS.read_text(encoding='utf-8')
    assert '[data-api-keys] .admin-row-actions' not in css
    assert 'flex-wrap: nowrap' not in css


def _register(application: Flask) -> Flask:
    from cafeteria.admin import api_routes  # noqa: F401

    auth = Blueprint('auth', __name__)
    auth.add_url_rule('/logout', endpoint='logout', view_func=lambda: '')
    signage = Blueprint('signage', __name__)
    signage.add_url_rule('/preview/cafeteria', endpoint='cafeteria_week', view_func=lambda: '')
    signage.add_url_rule('/preview/patient', endpoint='patient_week', view_func=lambda: '')
    application.register_blueprint(auth)
    application.register_blueprint(signage)
    application.register_blueprint(workflow_routes.bp)
    application.context_processor(lambda: {'csrf_token': csrf_token})
    return application


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


@pytest.fixture
def app(database_engine: Engine, tmp_path: Path) -> Flask:
    application = Flask(
        __name__,
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
        static_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'static'),
    )
    application.config.update(
        SECRET_KEY='workflow-test-secret',
        LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-02',
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    register_ui(application)
    return _register(application)


@pytest.fixture
def admin_client(app: Flask, database_engine: Engine):
    return _login(app, database_engine, ['Cafeteria.Admin'])[0]


@pytest.fixture
def editor_client(app: Flask, database_engine: Engine):
    return _login(app, database_engine, ['Cafeteria.Editor'])[0]


def _create_form(csrf: str = 'workflow-csrf') -> dict[str, str]:
    return {
        '_csrf': csrf,
        'label': 'Integrations-Test',
        'scopes': 'preview.read',
        'channels': 'cafeteria',
        'expires_at': (date.today() + timedelta(days=30)).isoformat(),
    }


def test_admin_sees_api_page_with_links_and_status(admin_client) -> None:
    response = admin_client.get('/admin/api')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '/api/v1/docs' in body
    assert '/api/v1/openapi.json' in body
    assert '/fhir/metadata' in body
    assert 'data-api-status' in body


def test_editor_gets_403(editor_client) -> None:
    assert editor_client.get('/admin/api').status_code == 403


def test_create_shows_plaintext_once(admin_client) -> None:
    created = admin_client.post('/admin/api/keys', data=_create_form(), follow_redirects=True)
    body = created.get_data(as_text=True)
    assert created.status_code == 200
    assert 'data-new-key' in body
    assert re.search(r'dbk_[A-Za-z0-9_-]{32}', body)
    assert 'Dieser Schlüssel wird nur einmal angezeigt.' in body
    second = admin_client.get('/admin/api')
    assert second.status_code == 200
    assert 'data-new-key' not in second.get_data(as_text=True)


def test_revoke_changes_status(admin_client) -> None:
    admin_client.post('/admin/api/keys', data=_create_form(), follow_redirects=True)
    overview = admin_client.get('/admin/api')
    match = re.search(r'data-key-id="([^"]+)"', overview.get_data(as_text=True))
    assert match is not None
    public_id = match.group(1)
    revoked = admin_client.post(
        f'/admin/api/keys/{public_id}/revoke',
        data={'_csrf': 'workflow-csrf'},
        follow_redirects=True,
    )
    assert revoked.status_code == 200
    body = revoked.get_data(as_text=True)
    assert f'data-key-id="{public_id}"' in body
    assert 'data-key-state="revoked"' in body
    assert 'data-status="revoked"' in body


def test_csrf_failure_returns_400(admin_client) -> None:
    response = admin_client.post('/admin/api/keys', data=_create_form(csrf='invalid'))
    assert response.status_code == 400


def test_query_parameters_return_400(admin_client) -> None:
    assert admin_client.get('/admin/api?debug=1').status_code == 400


def test_page_render_contract(admin_client) -> None:
    body = admin_client.get('/admin/api').get_data(as_text=True)
    assert 'data-page="api"' in body
    assert 'table[data-api-keys]' not in body
    assert 'data-api-keys' in body
    assert 'id="api-key-create"' in body
    assert '/api/v1/docs' in body
    assert '/api/v1/openapi.json' in body
    assert '/fhir/metadata' in body
    assert re.search(r'<script[^>]*>[^<]+</script>', body, re.I) is None
    assert 'style=' not in body


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_api_browser_layout_native_post_and_keyboard(admin_client, javascript):
    application = admin_client.application
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    evidence = ROOT / '.claude/state/wp18-evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    measurements = []
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch() as browser:
                with browser.new_context(java_script_enabled=javascript, reduced_motion='reduce') as context:
                    name = application.config['SESSION_COOKIE_NAME']
                    cookie = admin_client.get_cookie(name)
                    assert cookie is not None
                    context.add_cookies([{'name': name, 'value': cookie.value, 'url': origin}])
                    page = context.new_page()
                    page.goto(origin + '/admin/api', wait_until='networkidle')
                    expect(page.locator('[data-api-keys]')).to_contain_text('Noch keine API-Schlüssel')
                    expect(page.locator('[data-api-keys] a[href="#api-key-label"]')).to_be_visible()
                    expect(page.locator('main .btn-primary')).to_have_count(1)
                    primary = page.locator('main .btn-primary')
                    primary.focus()
                    assert float(primary.evaluate('e => getComputedStyle(e).outlineWidth').removesuffix('px')) >= 2
                    primary.press('Enter')
                    expect(page.locator('#api-key-label')).to_be_visible()
                    expect(page.locator('#api-key-label')).to_be_focused()
                    initial = page.locator('#api-key-create').evaluate('e => [...new FormData(e)]')
                    assert initial == [['_csrf', 'workflow-csrf'], ['label', ''],
                                       ['expires_at', _create_form()['expires_at']]]
                    page.locator('#api-key-label').fill('Küchenintegration')
                    page.locator('#api-key-scope-preview').check()
                    page.locator('#api-key-channel-cafeteria').check()
                    page.locator('#api-key-channel-patienten').check()
                    selected = page.locator('#api-key-create').evaluate('e => [...new FormData(e)]')
                    assert selected == [['_csrf', 'workflow-csrf'], ['label', 'Küchenintegration'],
                                        ['expires_at', _create_form()['expires_at']],
                                        ['scopes', 'preview.read'], ['channels', 'cafeteria'],
                                        ['channels', 'patienten']]
                    summary = page.locator('#api-key-create-title')
                    summary.focus()
                    summary.press('Enter')
                    summary.press('Enter')
                    assert page.locator('#api-key-create').evaluate('e => [...new FormData(e)]') == selected
                    with page.expect_response(lambda r: r.request.method == 'POST') as response:
                        page.locator('#api-key-create button[type="submit"]').press('Enter')
                    assert response.value.status == 303
                    expect(page.locator('[data-new-key]')).to_be_visible()
                    expect(page.locator('[data-new-key-hint]')).to_have_text('Dieser Schlüssel wird nur einmal angezeigt.')
                    # Never capture or log the generated secret.
                    page.reload(wait_until='networkidle')
                    expect(page.locator('[data-new-key]')).to_have_count(0)
                    for width, height in [(360, 844), (768, 1024), (1024, 768), (1440, 900)]:
                        page.set_viewport_size({'width': width, 'height': height})
                        page.evaluate('document.fonts.ready')
                        expect(page.locator('main .btn-primary')).to_have_count(1)
                        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
                        table = page.locator('[data-api-keys] table')
                        expect(table).to_have_class(re.compile(r'\badmin-table--stack\b'))
                        expect(table.locator('tbody td:not([data-label])')).to_have_count(0)
                        row_actions = table.locator('.admin-row-actions').first
                        shared = row_actions.evaluate('el => { const cs = getComputedStyle(el); return {wrap: cs.flexWrap, gap: cs.gap, display: cs.display}; }')
                        assert shared['display'] == 'flex', shared
                        assert shared['gap'] == '8px', shared
                        assert shared['wrap'] == ('wrap' if width < 768 else 'nowrap'), (width, shared)
                        assert table.locator('tbody tr').first.evaluate(
                            'el => getComputedStyle(el).display'
                        ) == ('grid' if width < 768 else 'table-row')
                        bar = page.locator('.admin-statusbar')
                        expect(bar).to_be_visible()
                        expect(bar.locator('.admin-statusbar-item')).to_have_count(2)
                        assert bar.locator('dt').all_inner_texts() == ['Cafeteria', 'Patienten']
                        expect(bar.locator('.admin-statusbar-item--warning')).to_have_count(2)
                        assert bar.locator('.admin-statusbar-value-text').all_inner_texts() == [
                            'Nicht veröffentlicht', 'Nicht veröffentlicht',
                        ]
                        expect(bar).not_to_contain_text('Revision')
                        expect(page.locator('[data-api-technical]')).not_to_have_attribute('open', '')
                        metrics = page.evaluate('''() => ({width: innerWidth,
                            height: document.documentElement.scrollHeight,
                            row: document.querySelector('[data-key-id]').getBoundingClientRect().height,
                            primary: document.querySelectorAll('main .btn-primary').length,
                            hints: [...document.querySelectorAll('main .form-hint')].filter(el => el.checkVisibility()).length,
                            open: document.querySelectorAll('main details[open]').length,
                            overflow: document.documentElement.scrollWidth - innerWidth})''')
                        assert metrics['overflow'] <= 1, metrics
                        assert metrics['row'] <= (96 if width >= 1024 else 280), metrics
                        targets = page.locator('main :is(.btn, summary)').evaluate_all(
                            'es => es.filter(e => e.checkVisibility()).map(e => e.getBoundingClientRect().height)')
                        assert targets and min(targets) >= 48, targets
                        measurements.append(metrics)
                        page.screenshot(path=str(evidence / f'after-{javascript}-{width}.png'), full_page=True)
                        page.locator('main .btn-primary').click()
                        expect(page.locator('#api-key-label')).to_be_focused()
                        # Checkbox labels are the full native 48px click targets; glyphs stay 20px.
                        controls = page.locator('#api-key-create :is(.form-control, .form-check, button)').evaluate_all(
                            'es => es.map(e => e.getBoundingClientRect().height)')
                        assert controls and min(controls) >= 48, controls
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        page.locator('#api-key-create-title').click()
                    # Technical links remain reachable by keyboard, including without JS.
                    technical = page.locator('[data-api-technical] > summary')
                    technical.focus()
                    technical.press('Enter')
                    expect(page.get_by_role('heading', name='Technische Versionen')).to_be_visible()
                    docs = page.locator('a[href="/api/v1/docs"]')
                    expect(docs).to_be_visible()
                    expect(docs).to_contain_text('Swagger UI')
                    expect(docs).to_have_attribute('target', '_blank')
                    openapi = page.locator('a[href="/api/v1/openapi.json"]')
                    expect(openapi).to_contain_text('OpenAPI')
                    expect(openapi).to_have_attribute('title', 'OpenAPI öffnen')
                    fhir = page.locator('a[href="/fhir/metadata"]')
                    expect(fhir).to_contain_text('FHIR')
                    expect(fhir).to_have_attribute('title', 'FHIR öffnen')
                    technical.press('Enter')
                    # Direct labeled revoke plus «Mehr» for details; confirmation stays native.
                    revoke = page.locator('form[action$="/revoke"]')
                    expect(revoke.locator('summary')).to_contain_text('Widerrufen')
                    expect(revoke.locator('button')).not_to_be_visible()
                    more = page.locator('.ui-sem-actions > summary')
                    more.focus()
                    more.press('Enter')
                    details = page.locator('.admin-api-key-details > summary')
                    expect(details).to_have_attribute('title', re.compile(r'Details zu '))
                    details.press('Enter')
                    expect(page.locator('[data-label="Präfix"]')).to_be_visible()
                    revoke.locator('summary').press('Enter')
                    assert revoke.evaluate('e => [...new FormData(e)]') == [['_csrf', 'workflow-csrf']]
                    if javascript:
                        page.once('dialog', lambda dialog: dialog.dismiss())
                        revoke.locator('button').click()
                        expect(page.locator('[data-key-state="active"]')).to_have_count(1)
                        page.once('dialog', lambda dialog: dialog.accept())
                    with page.expect_response(lambda r: r.request.method == 'POST') as response:
                        revoke.locator('button').press('Enter')
                    assert response.value.status == 303
                    expect(page.locator('[data-key-state="revoked"]')).to_be_visible()
                    # Actual server validation retains choices and opens the failed form.
                    page.locator('main .btn-primary').click()
                    page.locator('#api-key-label').fill('Fehler bleibt sichtbar')
                    page.locator('#api-key-channel-patienten').check()
                    with page.expect_response(lambda r: r.request.method == 'POST') as response:
                        page.locator('#api-key-create button').click()
                    assert response.value.status == 400
                    expect(page.locator('[data-api-create]')).to_have_attribute('open', '')
                    expect(page.locator('.error-region')).to_be_visible()
                    expect(page.locator('#api-key-label')).to_have_value('Fehler bleibt sichtbar')
                    expect(page.locator('#api-key-channel-patienten')).to_be_checked()
                    expect(page.locator('#api-key-scope-preview')).not_to_be_checked()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        (evidence / f'measurements-{javascript}.json').write_text(json.dumps(measurements, indent=2))
        print('WP18 measurements:', json.dumps(measurements))
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
