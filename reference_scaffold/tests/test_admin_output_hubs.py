"""Output navigation uses authoritative roles and existing rendered destinations."""
from __future__ import annotations

import threading
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

import cafeteria
from cafeteria.admin import display_routes, workflow_routes  # noqa: F401
from cafeteria.public import routes as public_routes
from cafeteria.security import csrf_token
from cafeteria.signage import routes as signage_routes
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import (  # noqa: F401
    DATABASE_URL, DAY, ROOT, _login, database_engine,
)
from test_rendered_ui import browser, cafeteria_snapshot, patient_snapshot  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
PATHS = ('/admin/screens', '/admin/vorlagen')


@pytest.fixture
def hub_app(database_engine, tmp_path, monkeypatch):  # noqa: F811
    application = Flask(
        __name__,
        template_folder=str(ROOT / 'reference_scaffold/cafeteria/templates'),
        static_folder=str(ROOT / 'reference_scaffold/cafeteria/static'),
    )
    application.config.update(
        TESTING=True, SECRET_KEY='output-hub-test', LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True, DEMO_TODAY='2026-09-02',
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    auth = Blueprint('auth', __name__)
    auth.add_url_rule('/auth/logout', endpoint='logout', view_func=lambda: '')
    for blueprint in (auth, public_routes.bp, signage_routes.bp, workflow_routes.bp):
        application.register_blueprint(blueprint)
    application.context_processor(lambda: {'csrf_token': csrf_token})
    snapshots = {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}
    monkeypatch.setattr(public_routes, 'active_snapshot', lambda _db, profile, *a, **kw: snapshots[profile])
    return application


class MainLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inside = False
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.inside = True
        if tag == 'a' and self.inside:
            self.links.append(dict(attrs)['href'])

    def handle_endtag(self, tag):
        if tag == 'main':
            self.inside = False


def test_app_factory_registers_each_hub_once(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    rules = [rule.rule for rule in cafeteria.create_app().url_map.iter_rules()]
    for path in PATHS:
        assert rules.count(path) == 1


@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_hubs_use_existing_read_roles_and_link_all_real_targets(hub_app, database_engine, role):  # noqa: F811
    client, _ = _login(hub_app, database_engine, [role])
    for profile, values in [('staff_guest', _staff_values()), ('patient', _patient_values())]:
        _save(database_engine, profile, values)
    for path in PATHS:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        html = response.get_data(as_text=True)
        assert f'href="{path}" class="nav-link active" aria-current="page"' in html
        links = MainLinks(html).links
        expected_links = 10 if path == '/admin/vorlagen' and role == 'Cafeteria.Admin' else 8
        assert len(links) == expected_links and len(set(links)) == expected_links
        for link in links:
            target = client.get(link)
            assert target.status_code == 200, (link, target.status_code)
            if '/preview/print' in link:
                assert f'week={DAY}' in link
                assert target.data.startswith(b'%PDF-')
            elif link.startswith(('/cafeteria/', '/patienten/', '/signage/', '/druck/')):
                assert '?' not in link
                assert target.headers['X-Snapshot-Revision']


def test_hubs_reject_missing_roles_and_stale_authorization(hub_app, database_engine, monkeypatch):  # noqa: F811
    for path in PATHS:
        assert hub_app.test_client().get(path).status_code == 401
    client, _ = _login(hub_app, database_engine, [])
    for path in PATHS:
        assert client.get(path).status_code == 401
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])
    monkeypatch.setitem(cafeteria.roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'csv.export'})
    for path in PATHS:
        assert client.get(path).status_code == 403
    client, actor = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': actor})
    for path in PATHS:
        assert client.get(path).status_code == 401


@pytest.mark.parametrize('path', [
    '/admin/screens?week=2026-08-31', '/admin/screens?profile=patient',
    '/admin/vorlagen?profile=patient', '/admin/vorlagen?week=2026-09-01',
    '/admin/vorlagen?week=invalid', '/admin/vorlagen?week=2026-08-31&week=2026-09-07',
])
def test_hubs_reject_invalid_query_parameters(hub_app, database_engine, path):  # noqa: F811
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    assert client.get(path).status_code == 400


def test_selected_week_only_changes_saved_week_destinations(hub_app, database_engine):  # noqa: F811
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])
    response = client.get('/admin/vorlagen?week=2026-09-07')
    assert response.status_code == 200
    links = MainLinks(response.get_data(as_text=True)).links
    assert sum('week=2026-09-07' in link for link in links) == 4
    assert '/druck/cafeteria/woche' in links and '/druck/patienten/woche' in links


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_hubs_responsive_keyboard_and_native_week_selection(
    hub_app, database_engine, browser, width, javascript, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    server = make_server('127.0.0.1', 0, hub_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f'http://127.0.0.1:{server.server_port}'
    cookie = client.get_cookie('session')
    assert cookie is not None
    try:
        with browser.new_context(
            base_url=base_url, java_script_enabled=javascript,
            viewport={'width': width, 'height': 1100}, reduced_motion='reduce',
        ) as context:
            context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': base_url}])
            page = context.new_page()
            for path, title in zip(PATHS, ('Screens', 'Vorlagen'), strict=True):
                response = page.goto(path)
                assert response is not None and response.status == 200
                expect(page.get_by_role('heading', level=1)).to_have_text(title)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                for control in page.locator('main :is(.btn, .form-control)').all():
                    box = control.bounding_box()
                    assert box is not None and box['height'] >= 48
                    control.focus()
                    expect(control).to_be_focused()
                    assert control.evaluate(
                        "el => { const s = getComputedStyle(el); return s.boxShadow !== 'none' || "
                        "(s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0); }"
                    )
                page.screenshot(path=str(tmp_path / f'{title}-{width}-js-{javascript}.png'), full_page=True)
            page.get_by_label('Woche ab Montag').fill('2026-09-07')
            page.get_by_role('button', name='Woche anzeigen', exact=True).click()
            expect(page).to_have_url(f'{base_url}/admin/vorlagen?week=2026-09-07')
            expect(page.get_by_label('Cafeteria gewählte Woche öffnen')).to_have_attribute(
                'href', '/admin/cafeteria?week=2026-09-07',
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
