"""Native Rezepte-importieren pages at the UI-master viewports."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria import master_data_store as masters
from test_master_data_browser import master_server, targets  # noqa: F401
from test_master_data_db import STORAGE_PUBLIC_ID, signed_in
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_import import json_bytes, recipe
from test_recipe_import_routes import create
from test_rendered_ui import browser  # noqa: F401
from test_ui_korrektur_cookbooks_browser import _native_viewport_capture

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/density-imports-0913/after'

ROUTE_VIEWPORTS = ((360, 844), (1440, 900))
COMMIT_VIEWPORTS = (*ROUTE_VIEWPORTS, (720, 450))
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
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
        expect(page.get_by_text('Noch keine Importstapel')).to_be_visible()
        page.set_input_files('#source_file', str(source))
        page.get_by_label('ungeprüft').check()
        preview = page.get_by_role('button', name='Vorschau speichern')
        expect(preview).to_contain_text('Vorschau speichern')
        preview.click()
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
            page.get_by_role('button', name='Speichern', exact=True).click()
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
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
        expect(page.locator('thead th').first).to_have_text('Datei')
        expect(page.locator('td[data-label="Datei"]').first).to_be_visible()
        targets(page)
        shot = tmp_path / f'rezepte-import-shared-{width}x{height}.png'
        page.screenshot(path=str(shot), full_page=True)


@pytest.mark.parametrize('width,height', COMMIT_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
def test_commit_confirmation_and_recipe_link(b3, master_server, browser, width, height, javascript, tmp_path):  # noqa: F811
    app, _owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        food = masters.create_food(engine, actor, {
            'name': 'Browser-Zutat', 'base_unit_code': 'KG',
            'storage_location_public_ids': [STORAGE_PUBLIC_ID],
        })
    path = create(client, annotation='unreviewed')
    form = Forms(client.get(path).text).forms[path]
    form['row.1.ingredient.0.food_public_id'] = food.public_id
    form['row.1.duplicate_decision'] = 'create_new'
    form['action'] = 'save'
    assert client.post(path, data=form).status_code == 303
    ack = Forms(client.get(path).text).forms[path]
    ack['action'] = 'acknowledge'
    assert client.post(path, data=ack).status_code == 303
    base, cookie = master_server
    with browser.new_context(
        viewport={'width': width, 'height': height}, java_script_enabled=javascript,
        reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        _open(page, base, path)
        expect(page.get_by_role('heading', name='Importstapel übernehmen')).to_be_visible()
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('.admin-statusbar')).to_contain_text('Erledigt')
        expect(page.get_by_text('keine Veröffentlichung')).to_be_visible()
        targets(page)
        confirm_shot = tmp_path / f'rezepte-import-confirm-{width}-js-{javascript}.png'
        page.screenshot(path=str(confirm_shot), full_page=True)
        commit = page.get_by_role('button', name='Importstapel übernehmen')
        expect(commit).to_contain_text('Übernehmen')
        assert 'übernehmen' in (commit.get_attribute('aria-label') or '').lower()
        commit.click()
        expect(page.get_by_role('heading', name='Übernommene Rezepte')).to_be_visible()
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_contain_text('Zurück')
        expect(page.locator('main .btn-primary')).to_have_attribute('aria-label', 'Zurück zu den Rezepten')
        assert 'Zurück' in (page.locator('main .btn-primary').get_attribute('aria-label') or '')
        expect(page.locator('.admin-statusbar')).to_contain_text('Übernommen')
        expect(page.locator('.admin-list-row')).to_be_visible()
        expect(page.get_by_role('link', name='Bearbeiten', exact=True)).to_be_visible()
        targets(page)
        shot = tmp_path / f'rezepte-import-commit-{width}-js-{javascript}.png'
        page.screenshot(path=str(shot), full_page=True)
        page.get_by_role('link', name='Bearbeiten', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')


@pytest.mark.parametrize('width,height', SHARED_VIEWPORTS)
def test_commit_shared_viewports(b3, master_server, browser, width, height, tmp_path):  # noqa: F811
    _, _, client, _ = b3
    path = create(client, annotation='unreviewed')
    ack = Forms(client.get(path).text).forms[path]
    ack['action'] = 'acknowledge'
    assert client.post(path, data=ack).status_code == 303
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base, path)
        expect(page.get_by_role('heading', name='Importstapel übernehmen')).to_be_visible()
        targets(page)
        shot = tmp_path / f'rezepte-import-commit-shared-{width}x{height}.png'
        page.screenshot(path=str(shot), full_page=True)


def test_closed_row_details_stay_in_formdata_and_keep_file_identity(
    b3, master_server, browser, tmp_path,  # noqa: F811
) -> None:
    _, _, client, _ = b3
    source = tmp_path / 'rezepte.json'
    source.write_bytes(json_bytes(recipe('Browser Import')))
    base, cookie = master_server
    with browser.new_context(
        viewport={'width': 1440, 'height': 900}, java_script_enabled=True,
        reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base)
        expect(page.locator('[data-empty-kind="none"]')).to_contain_text('Noch keine Importstapel')
        page.set_input_files('#source_file', str(source))
        page.get_by_label('ungeprüft').check()
        page.get_by_role('button', name='Vorschau speichern').click()
        expect(page.get_by_role('heading', name='Importstapel')).to_be_visible()
        details = page.locator('#row-1-details')
        expect(details).not_to_have_attribute('open', '')
        keys = page.locator('form[action*="/admin/rezepte/import/"]').first.evaluate(
            'form => [...new FormData(form).keys()]',
        )
        assert 'row.1.title' in keys
        assert 'row.1.ingredient.0.quantity' in keys
        assert 'row.1.ingredient.0.unit_code' in keys
        assert 'row.1.ingredient.0.food_public_id' in keys
        assert 'row.1.target_recipe_public_id' in keys
        assert 'row_version' in keys
        form = page.locator('form[action*="/admin/rezepte/import/"]').first
        original = form.evaluate('f => [...new FormData(f)]')
        decision = page.get_by_label('Dublettenentscheidung', exact=True)
        initial_decision = decision.input_value()
        decision.select_option('skip_existing')
        expect(page.locator('[data-duplicate-target]')).not_to_have_attribute('hidden', '')
        decision.select_option(initial_decision)
        expect(page.locator('[data-duplicate-target]')).to_have_attribute('hidden', '')
        assert form.evaluate('f => [...new FormData(f)]') == original
        targets(page)
        identity = page.locator('[data-checked-identity]')
        expect(identity).to_contain_text('rezepte.json')
        expect(identity).not_to_contain_text('Dateihash')
        technical = page.locator('#import-technical')
        expect(technical).not_to_have_attribute('open', '')
        technical.locator('summary').click()
        expect(technical).to_have_attribute('open', '')
        expect(technical).to_contain_text('Dateihash')
        details.locator('summary').focus()
        expect(details.locator('summary')).to_be_focused()
        page.keyboard.press('Enter')
        expect(details).to_have_attribute('open', '')
        expect(page.get_by_label('Lebensmittel-UUID')).to_be_visible()
        page.locator('[data-import-upload] > summary').click()
        page.locator('#source_file').set_input_files({
            'name': 'andere-rezepte.json',
            'mimeType': 'application/json',
            'buffer': json_bytes(recipe('Andere Datei')),
        })
        expect(identity).to_contain_text('rezepte.json')
        expect(identity).not_to_contain_text('andere-rezepte.json')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / 'rezepte-import-identity-1440.png'), full_page=True)
        assert page.locator('main style').count() == 0


def test_recipe_import_native_cdp_zoom(b3, master_server, browser) -> None:  # noqa: F811
    _, _, client, _ = b3
    create(client)
    base, cookie = master_server
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='recipe-import-zoom-') as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True, base_url=base,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            page.goto(base + '/admin/rezepte/import')
            page.evaluate('document.fonts && document.fonts.ready')
            assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
            assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
            capture = _native_viewport_capture(page, EVIDENCE / 'native-200-rezepte-import.png')
            assert capture['layout']['cssVisualViewport']['zoom'] == 2
            expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
            icons = page.locator('main svg.icon').evaluate_all(
                'icons => icons.map(icon => icon.getBBox().width)',
            )
            assert icons and all(width > 0 for width in icons)


@pytest.mark.parametrize('width,height', ((320, 844), (2560, 1440)))
@pytest.mark.parametrize('javascript', (False, True))
def test_recipe_import_density_missing_viewports(
    b3, master_server, browser, width, height, javascript,  # noqa: F811
) -> None:
    from test_ui_korrektur_tools_browser import _assert_full_width, _assert_rendered_icons

    _, _, client, _ = b3
    path = create(client)
    base, cookie = master_server
    evidence = Path(__file__).resolve().parents[2] / '.claude/evidence/imports-coverage-fix-0913/after'
    evidence.mkdir(parents=True, exist_ok=True)
    with browser.new_context(viewport={'width': width, 'height': height},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base, path)
        expect(page.locator('[data-checked-identity]')).to_contain_text('Geprüftes Ergebnis')
        expect(page.get_by_role('button', name='Speichern', exact=True)).to_be_visible()
        details = page.locator('#row-1-details')
        expect(details).not_to_have_attribute('open', '')
        _assert_full_width(page, width)
        targets(page)
        summary = details.locator('summary')
        summary.focus()
        expect(summary).to_be_focused()
        page.keyboard.press('Enter')
        expect(details).to_have_attribute('open', '')
        if javascript:
            expect(details.get_by_label('Zielrezept', exact=True)).not_to_be_visible()
            page.get_by_label('Dublettenentscheidung').select_option('skip_existing')
        for label in ('Menge', 'Einheit', 'Lebensmittel-UUID', 'Zielrezept', 'Zielversion'):
            expect(details.get_by_label(label, exact=True)).to_be_visible()
        quantity = details.get_by_label('Menge', exact=True)
        quantity.fill('12.5')
        summary.focus()
        page.keyboard.press('Enter')
        expect(details).not_to_have_attribute('open', '')
        assert quantity.evaluate('node => new FormData(node.form).get(node.name)') == '12.5'
        page.keyboard.press('Enter')
        expect(details).to_have_attribute('open', '')
        expect(quantity).to_have_value('12.5')
        _assert_full_width(page, width)
        _assert_rendered_icons(page)
        targets(page)
        page.screenshot(path=str(evidence / f'recipe-open-{width}-js-{javascript}.png'), full_page=True)
        summary.click()
        expect(details).not_to_have_attribute('open', '')
        page.screenshot(path=str(evidence / f'recipe-closed-{width}-js-{javascript}.png'), full_page=True)


@pytest.mark.parametrize('javascript', [False, True])
def test_discard_requires_explicit_native_confirmation(b3, master_server, browser, javascript):  # noqa: F811
    from urllib.parse import parse_qs

    _, _, client, _ = b3
    path = create(client)
    base, cookie = master_server
    with browser.new_context(viewport={'width': 360, 'height': 900},
                             java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base, path)
        form = page.locator(f'form[action="{path}"]')
        table = page.locator('table.admin-table--stack')
        expect(table).to_have_count(1)
        assert table.locator('tbody tr').first.evaluate('e => getComputedStyle(e).display') == 'grid'
        assert table.locator('thead th:not([scope="col"]), tbody td:not([data-label])').count() == 0
        original = form.evaluate('f => [...new FormData(f)]')
        confirm = page.get_by_role('button', name='Verwerfen bestätigen', exact=True)
        expect(confirm).not_to_be_visible()
        page.locator('.admin-compact-actions > summary').focus()
        page.keyboard.press('Enter')
        discard = page.locator('summary[aria-label="Stapel verwerfen"]')
        expect(discard).to_be_visible()
        expect(discard).to_contain_text('Verwerfen')
        discard.focus()
        page.keyboard.press('Enter')
        expect(confirm).to_be_visible()
        expect(confirm).to_contain_text('Verwerfen')
        assert 'verwerfen' in (confirm.get_attribute('aria-label') or '').lower()
        expect(page.locator('#discard-consequence')).to_contain_text('vorhandene Rezepte bleiben unverändert')
        assert 'btn-danger' in confirm.get_attribute('class').split()
        assert form.evaluate('f => [...new FormData(f)]') == original
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        confirm.focus()
        with page.expect_request(lambda request: request.method == 'POST') as request:
            page.keyboard.press('Enter')
        sent = parse_qs(request.value.post_data, keep_blank_values=True)
        assert sent['action'] == ['cancel']
        for key, value in original:
            assert value in sent[key]
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_contain_text('Zurück')
        expect(page.locator('main .btn-primary')).to_have_attribute('aria-label', 'Zurück zu den Rezepten')
        assert 'Zurück' in (page.locator('main .btn-primary').get_attribute('aria-label') or '')
        expect(page.locator('.admin-statusbar')).to_contain_text('Verworfen')
        expect(page.locator('.admin-label').first).to_contain_text('Verworfen')
        expect(page.get_by_role('button', name='Verwerfen bestätigen', exact=True)).to_have_count(0)
