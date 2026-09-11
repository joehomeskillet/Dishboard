"""Native Rezepte-importieren pages at the UI-master viewports."""
from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_master_data_browser import master_server, targets  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_import import json_bytes, recipe
from test_recipe_import_routes import create
from test_rendered_ui import browser  # noqa: F401

ROUTE_VIEWPORTS = ((390, 844), (1440, 900))
SHARED_VIEWPORTS = ((1024, 768), (768, 1024), (1920, 1080))


def _open(page, base, path='/admin/rezepte/import'):
    page.goto(base + path)
    page.evaluate('document.fonts && document.fonts.ready')
    return page


@pytest.mark.parametrize('width,height', ROUTE_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
def test_upload_conflict_keyboard_and_tabler(b3, master_server, browser, width, height, javascript, tmp_path):  # noqa: F811
    _, _owner, client, _ = b3
    source = tmp_path / 'rezepte.json'
    source.write_bytes(json_bytes(recipe('Browser Import')))
    base, cookie = master_server
    with browser.new_context(
        viewport={'width': width, 'height': height}, java_script_enabled=javascript,
        reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        _open(page, base)
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte importieren')
        expect(page.get_by_text('Noch keine Importstapel')).to_be_visible()
        page.set_input_files('#source_file', str(source))
        page.get_by_label('ungeprüft').check()
        page.get_by_role('button', name='Vorschau speichern').click()
        expect(page.get_by_role('heading', name='Importstapel')).to_be_visible()
        expect(page.get_by_text('Browser Import')).to_be_visible()
        path = urlsplit(page.url).path
        token = page.locator('input[name="row_version"]').input_value()
        stale_title = page.get_by_label('Titel', exact=True)
        data = Forms(client.get(path).text).forms[path]
        data['row.1.title'] = 'Andere Sitzung'
        assert data['row_version'] == token
        assert client.post(path, data=data).status_code == 303
        stale_title.fill('Mein ursprünglicher Entwurf')
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Entscheidungen speichern').click()
        assert outcome.value.status == 409
        expect(page.locator('#recipe-import-error')).to_be_visible()
        expect(page.get_by_label('Titel', exact=True)).to_have_value('Mein ursprünglicher Entwurf')
        page.get_by_role('link', name='Aktuellen Stand neu laden').click()
        expect(page.get_by_label('Titel', exact=True)).to_have_value('Andere Sitzung')
        targets(page)
        assets = page.locator('link[rel="stylesheet"]').evaluate_all(
            'els => els.map(el => new URL(el.href).pathname)')
        assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
        assert page.locator('main style, main [style]').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        if width == 1440:
            page.evaluate('document.documentElement.style.zoom = "2"')
            page.evaluate('document.fonts && document.fonts.ready')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.evaluate('document.documentElement.style.zoom = "1"')
        shot = tmp_path / f'rezepte-import-{width}-js-{javascript}.png'
        page.screenshot(path=str(shot), full_page=True)
        expected_conflict = 'Failed to load resource: the server responded with a status of 409 (CONFLICT)'
        assert all(error == expected_conflict for error in errors)


@pytest.mark.parametrize('width,height', SHARED_VIEWPORTS)
def test_shared_layout_viewports(b3, master_server, browser, width, height, tmp_path):  # noqa: F811
    _, _, client, _ = b3
    create(client)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base)
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte importieren')
        expect(page.get_by_role('columnheader', name='Datei')).to_be_visible()
        targets(page)
        shot = tmp_path / f'rezepte-import-shared-{width}x{height}.png'
        page.screenshot(path=str(shot), full_page=True)
