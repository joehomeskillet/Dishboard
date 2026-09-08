"""Real store, route and browser contracts for the read-only PDF catalog."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria.print_templates import SETTING_PREFIX
from test_admin_output_hubs import MainLinks
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401
from test_print_template_routes import editor_app, fields  # noqa: F401
from test_rendered_ui import browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
PDF_TARGETS = {f'/admin/vorlagen/{family}{suffix}' for family in ('cafeteria', 'patienten')
               for suffix in ('', '/vorschau.pdf')}
SCREEN_TARGETS = {f'/admin/vorlagen/screens/{family}/{prefix}-week-{mode}'
                  for family, prefix in [('cafeteria', 'cafeteria'), ('patienten', 'patient')]
                  for mode in ('photo', 'text')}


def settings(engine):
    with engine.connect() as connection:
        return connection.execute(text(
            'SELECT id, setting_key, setting_value FROM cafeteria.settings ORDER BY id'
        )).all()


def populate(client, engine):
    for family, profile, values in (
        ('cafeteria', 'staff_guest', _staff_values()),
        ('patienten', 'patient', _patient_values()),
    ):
        _save(engine, profile, values)
        path = f'/admin/vorlagen/{family}?week={DAY}'
        assert client.post(path, data=fields(name='Aktiver Herbst', header_text='Aktiver Stand')).status_code == 303
        assert client.post(path, data=fields('activate', 1, 2)).status_code == 303
        assert client.post(path, data=fields(version=2, revision=2, name='Winter & Festtage', header_text='Neuer Entwurf')).status_code == 303
        assert client.post(path, data=fields('copy', 3, 3, name='Festliche Kopie')).status_code == 303


def test_virtual_catalog_and_missing_week_never_initialize_settings(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    before = settings(database_engine)
    page = client.get(f'/admin/vorlagen?week={DAY}')
    assert page.status_code == 200 and page.headers['Cache-Control'] == 'no-store'
    assert page.text.count('data-template-id="standard"') == 3
    recipe_links = [link for link in MainLinks(page.text).links
                    if urlsplit(link).path == '/admin/vorlagen/rezepte']
    assert len(recipe_links) == 1
    assert parse_qs(urlsplit(recipe_links[0]).query) == {'template': ['standard'], 'revision': ['1']}
    recipe_editor = client.get(recipe_links[0])
    assert recipe_editor.status_code == 200 and recipe_editor.headers['Cache-Control'] == 'no-store'
    assert '<iframe' not in recipe_editor.text
    assert {link for link in MainLinks(page.text).links if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    for link in SCREEN_TARGETS:
        preview = client.get(link)
        assert preview.status_code == 404 and preview.headers['Cache-Control'] == 'no-store'
    for link in MainLinks(page.text).links:
        if urlsplit(link).path not in PDF_TARGETS:
            continue
        response = client.get(link)
        if '/vorschau.pdf' in link:
            assert response.status_code == 404
        else:
            assert response.status_code == 200
            assert 'noch keine gespeicherten Menüs' in response.text
            assert '<iframe' not in response.text
    assert settings(database_engine) == before


def test_catalog_revision_links_render_real_saved_pdfs_without_mutation(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(client, database_engine)
    before = settings(database_engine)
    active = {family: client.get(f'/admin/{family}/preview/print?week={DAY}').data
              for family in ('cafeteria', 'patienten')}
    response = client.get(f'/admin/vorlagen?week={DAY}')
    assert response.status_code == 200
    assert 'Winter &amp; Festtage' in response.text and 'Winter & Festtage' not in response.text
    assert response.text.count('Aktiver Herbst · Revision 2') == 2
    assert response.text.count('Neuester Stand: Revision 3 · Entwurf') == 2
    assert response.text.count('Festliche Kopie') == 2
    assert {link for link in MainLinks(response.text).links if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    links = [link for link in MainLinks(response.text).links if urlsplit(link).path in PDF_TARGETS]
    assert len(links) == 12
    for link in links:
        query = parse_qs(urlsplit(link).query)
        assert query['week'] == [DAY]
        result = client.get(link)
        assert result.status_code == 200, link
        if '/vorschau.pdf' in link:
            assert result.mimetype == 'application/pdf' and result.data.startswith(b'%PDF-')
            assert result.headers['X-Print-Template-Revision'] == f"{query['template'][0]}:{query['revision'][0]}"
            if query['revision'] == ['2']:
                family = urlsplit(link).path.split('/')[3]
                assert result.data == active[family]
    for family, payload in active.items():
        assert client.get(f'/admin/{family}/preview/print?week={DAY}').data == payload
    changed = MainLinks(client.get('/admin/vorlagen?week=2026-09-07').text).links
    assert {link for link in changed if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    assert all(parse_qs(urlsplit(link).query)['week'] == ['2026-09-07']
               for link in changed if urlsplit(link).path in PDF_TARGETS)
    assert settings(database_engine) == before


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_read_roles_see_catalog_but_no_privileged_revision_links(editor_app, database_engine, role):  # noqa: F811
    admin, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(admin, database_engine)
    client, _ = _login(editor_app, database_engine, [role])
    response = client.get('/admin/vorlagen')
    assert response.status_code == 200 and 'Aktiver Herbst · Revision 2' in response.text
    assert not any(urlsplit(link).path in PDF_TARGETS for link in MainLinks(response.text).links)
    assert {link for link in MainLinks(response.text).links if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    for link in SCREEN_TARGETS:
        assert client.get(link).status_code == 404
    assert client.get(f'/admin/vorlagen/patienten?week={DAY}&revision=3').status_code == 403
    assert client.get(f'/admin/vorlagen/patienten/vorschau.pdf?week={DAY}&revision=3').status_code == 403


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_corrupt_catalog_is_explicit_no_store_503_without_replacement(editor_app, database_engine, profile):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(client, database_engine)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.settings SET setting_value=CAST(:value AS jsonb) '
                                'WHERE setting_key=:key'), {'value': json.dumps({'broken': True}), 'key': SETTING_PREFIX + profile})
    before = settings(database_engine)
    response = client.get('/admin/vorlagen')
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'role="alert"' in response.text and 'Gespeicherte Druckvorlagen sind ungültig' in response.text
    assert 'data-template-id' not in response.text
    assert settings(database_engine) == before


@pytest.mark.parametrize('width', [390, 1440])
def test_catalog_browser_real_assets_revision_names_and_keyboard(
    editor_app, database_engine, browser, width, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(client, database_engine)
    before = settings(database_engine)
    server = make_server('127.0.0.1', 0, editor_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    # Consume fixture mutation flashes before capturing the returning reader.
    assert client.get('/admin/vorlagen').status_code == 200
    cookie = client.get_cookie(editor_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        with browser.new_context(viewport={'width': width, 'height': 1100}, service_workers='block') as context:
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            page = context.new_page()
            responses = {}
            methods = []
            errors = []
            page.on('request', lambda request: methods.append(request.method))
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: responses.update({urlsplit(response.url).path: response.status}))
            result = page.goto(f'{base}/admin/vorlagen?week={DAY}', wait_until='networkidle')
            assert result is not None and result.status == 200
            expect(page.get_by_role('heading', level=1)).to_have_text('Vorlagen')
            assert page.locator('[data-template-id]').count() == 5
            assert page.locator('[data-template-id] use[href$="#tabler-pencil"]').count() == 5
            weekly_cards = page.locator('article.card:has([data-template-id]):not([aria-labelledby="recipe-templates-heading"])')
            assert weekly_cards.count() == 2
            assert weekly_cards.locator('[data-template-id]').count() == 4
            assert weekly_cards.locator('[data-template-id="standard"]').count() == 2
            for item in weekly_cards.locator('[data-template-id="standard"]').all():
                expect(item.get_by_role('heading')).to_have_text('Winter & Festtage')
                expect(item.get_by_text('Aktiver Herbst · Revision 2', exact=False)).to_be_visible()
            recipe_card = page.locator('article[aria-labelledby="recipe-templates-heading"]')
            assert recipe_card.locator('[data-template-id="standard"]').count() == 1
            expect(recipe_card.get_by_text('Neuester Stand: Revision 1', exact=True)).to_be_visible()
            recipe_link = recipe_card.get_by_role('link', name='Rezeptvorlageneditor öffnen', exact=True)
            recipe_target = urlsplit(recipe_link.get_attribute('href'))
            assert recipe_target.path == '/admin/vorlagen/rezepte'
            assert parse_qs(recipe_target.query) == {'template': ['standard'], 'revision': ['1']}
            assets = page.locator('link[rel="stylesheet"], script[src]').evaluate_all(
                "els => els.map(el => new URL(el.href || el.src).pathname)"
            )
            assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
            assert any('tabler' in asset and asset.endswith('.js') for asset in assets)
            assert all(responses.get(asset) == 200 for asset in assets)
            assert not any(asset.endswith('/app.css') for asset in assets)
            assert page.locator('.list-group').first.evaluate("el => getComputedStyle(el).display") == 'flex'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for link in page.locator('main .btn').all():
                link.focus()
                expect(link).to_be_focused()
                box = link.bounding_box()
                assert box is not None and box['height'] >= 48
            evidence = Path(os.environ.get('CATALOG_EVIDENCE_DIR', str(tmp_path)))
            evidence.mkdir(parents=True, exist_ok=True)
            evidence.chmod(0o700)
            screenshot = evidence / f'catalog-{width}.png'
            page.get_by_role('heading', level=1).click()
            page.screenshot(path=str(screenshot), full_page=True)
            screenshot.chmod(0o600)
            editor = weekly_cards.locator('[data-template-id="standard"]').first.get_by_role('link', name='Vorlageneditor öffnen')
            target = editor.get_attribute('href')
            editor.focus()
            editor.press('Enter')
            expect(page).to_have_url(base + target)
            expect(page.locator('input[name="name"]').first).to_have_value('Winter & Festtage')
            assert methods and set(methods) == {'GET'}
            assert not errors
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert settings(database_engine) == before
