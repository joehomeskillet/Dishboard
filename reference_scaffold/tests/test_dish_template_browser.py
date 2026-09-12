"""Native Gerichtvorlagen pages at the UI-master viewports."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_dish_template_routes import COLUMNS, create, fields, snapshot
from test_master_data_browser import master_server, targets  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_rendered_ui import browser  # noqa: F401

EVIDENCE = Path(os.environ.get(
    'DISH_TEMPLATE_EVIDENCE_DIR', '/tmp/grok-goal-793b78fb2d60/implementer/dish-template-screens',
))
ROUTE_VIEWPORTS = ((390, 844), (1440, 900))
SHARED_VIEWPORTS = ((1024, 768), (768, 1024), (1920, 1080))


def _open(context_page, base, path='/admin/gerichtvorlagen'):
    page = context_page
    page.goto(base + path)
    page.evaluate('document.fonts && document.fonts.ready')
    return page


@pytest.mark.parametrize('width,height', ROUTE_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
def test_list_create_conflict_and_tabler(b3, master_server, browser, width, height, javascript, tmp_path):  # noqa: F811
    _, owner, client, _ = b3
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
        expect(page.get_by_role('heading', level=1)).to_have_text('Gerichtvorlagen')
        for column in COLUMNS:
            expect(page.get_by_role('columnheader', name=column)).to_have_count(0)
        expect(page.get_by_text('Noch keine Gerichtvorlagen')).to_be_visible()
        page.get_by_role('link', name='Vorlage anlegen').click()
        expect(page.get_by_role('heading', name='Vorlage anlegen')).to_be_visible()
        page.get_by_label('Titel', exact=True).fill('Browser Vorlage')
        page.get_by_label('Menüart').select_option('MENU_1')
        page.get_by_label('Geltungsbereich').select_option('common')
        page.get_by_role('button', name='Speichern').click()
        expect(page.get_by_role('link', name='Browser Vorlage')).to_be_visible()
        for column in COLUMNS:
            expect(page.get_by_role('columnheader', name=column)).to_be_visible()
        expect(page.get_by_text('Menü 1', exact=True)).to_be_visible()
        expect(page.get_by_text('Gemeinsam', exact=True)).to_be_visible()
        expect(page.get_by_text('Aktiv', exact=True)).to_be_visible()
        page.get_by_role('link', name='Browser Vorlage').click()
        path = urlsplit(page.url).path
        token = page.locator('input[name="updated_at"]').input_value()
        assert fields(client, path)['updated_at'] == token
        stale_title = page.get_by_label('Titel', exact=True)
        data = fields(client, path)
        data['title'] = 'Andere Sitzung'
        assert client.post(path, data=data).status_code == 303
        stale_title.fill('Mein ursprünglicher Entwurf')
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Speichern').click()
        assert outcome.value.status == 409
        expect(page.locator('#dish-template-error')).to_be_visible()
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
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        EVIDENCE.chmod(0o700)
        shot = EVIDENCE / f'gerichtvorlagen-{width}-js-{javascript}.png'
        page.screenshot(path=str(shot), full_page=True)
        shot.chmod(0o600)
        expected_conflict = 'Failed to load resource: the server responded with a status of 409 (CONFLICT)'
        assert all(error == expected_conflict for error in errors)
        assert snapshot(owner)['dish_templates']


@pytest.mark.parametrize('width,height', SHARED_VIEWPORTS)
def test_shared_layout_viewports(b3, master_server, browser, width, height, tmp_path):  # noqa: F811
    _, _, client, _ = b3
    create(client, title=f'Liste {width}')
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base)
        expect(page.get_by_role('heading', level=1)).to_have_text('Gerichtvorlagen')
        for column in COLUMNS:
            expect(page.get_by_role('columnheader', name=column)).to_be_visible()
        targets(page)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        shot = EVIDENCE / f'gerichtvorlagen-shared-{width}x{height}.png'
        page.screenshot(path=str(shot), full_page=True)
        shot.chmod(0o600)
