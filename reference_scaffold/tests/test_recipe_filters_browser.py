"""Real native recipe filters at mobile/desktop sizes, with and without JavaScript."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from test_master_data_browser import master_server  # noqa: F401
from test_recipe_filter_reads import (  # noqa: F401
    app_engine, b3, complete_snapshot, filter_catalog, installed_pg16, pg16, seeded_pg16, seed_pages,
)
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width', [360, 768, 1024, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_recipe_filters_and_paging_are_read_only(b3, filter_catalog, master_server, browser,  # noqa: F811
                                                       width, javascript, tmp_path):
    _, owner, _, _ = b3
    tag, expected = seed_pages(b3)
    before = complete_snapshot(owner)
    base, cookie = master_server
    evidence = Path(os.environ.get('RECIPE_FILTER_EVIDENCE_DIR', str(tmp_path)))
    evidence.mkdir(parents=True, exist_ok=True)
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, writes, responses = [], [], {}
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: writes.append(request.method) if request.method != 'GET' else None)
        page.on('response', lambda response: responses.setdefault(urlsplit(response.url).path, []).append(response.status))
        response = page.goto(base + '/admin/rezepte')
        assert response.status == 200 and response.headers['cache-control'] == 'no-store'
        form = page.locator('form[action="/admin/rezepte"]')
        assert form.get_attribute('method') == 'get'
        form.locator('.admin-filter-more > summary').focus()
        page.keyboard.press('Enter')
        for label in ('Nach Rezepttitel suchen', 'Zutat', 'Kennzeichnung'):
            control = page.get_by_label(label, exact=True)
            control.focus()
            expect(control).to_be_focused()
            assert control.bounding_box()['height'] >= 48
        page.get_by_label('Nach Rezepttitel suchen', exact=True).fill('Seitensuppe')
        page.get_by_label('Zutat', exact=True).fill('rüebli')
        page.get_by_label('Kennzeichnung', exact=True).select_option(tag)
        page.get_by_label('Archivierte einschliessen', exact=True).check()
        page.get_by_role('button', name='Filtern', exact=True).focus()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        expect(page.locator('.recipe-card')).to_have_count(50)
        filters = {'q': ['Seitensuppe'], 'ingredient': ['rüebli'], 'tag': [tag], 'archived': ['1']}
        assert parse_qs(urlsplit(page.url).query) == filters
        next_link = page.locator('nav[aria-label="Rezeptseiten"] a[href*="page=2"]')
        next_link.focus()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        expect(page.locator('.recipe-card')).to_have_count(3)
        assert parse_qs(urlsplit(page.url).query) == filters | {'page': ['2']}
        # Cards carry "… ansehen" (/ansicht) and "… bearbeiten" (/<id>) links since the read-only view split.
        ids = page.locator('.recipe-card a[aria-label$=" bearbeiten"]').evaluate_all(
            'els => els.map(el => el.pathname.split("/").pop())')
        assert ids == expected[50:]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('main style, main [style]').count() == 0
        page.get_by_role('heading', level=1).scroll_into_view_if_needed()
        page.screenshot(path=str(evidence / f'recipes-{width}-js-{javascript}.png'), caret='initial')
        page.locator('nav[aria-label="Rezeptseiten"] a[href*="page=1"]').click()
        expect(page.locator('.recipe-card')).to_have_count(50)
        expect(page.locator('.admin-list-row')).to_have_count(50)
        expect(page.locator('.admin-list-row .admin-status--info')).to_have_count(50)
        page.get_by_role('link', name='Zurücksetzen', exact=True).click()
        assert urlsplit(page.url).query == ''
        expect(page.get_by_label('Nach Rezepttitel suchen', exact=True)).to_have_value('')
        expect(page.get_by_label('Zutat', exact=True)).to_have_value('')
        expect(page.get_by_label('Kennzeichnung', exact=True)).to_have_value('')
        expect(page.get_by_label('Archivierte einschliessen', exact=True)).not_to_be_checked()
        form.locator('.admin-filter-more > summary').click()
        page.get_by_label('Kennzeichnung', exact=True).select_option(filter_catalog['tag'])
        page.get_by_label('Zutat', exact=True).fill('keine solche Zutat')
        page.get_by_role('button', name='Filtern', exact=True).click()
        expect(page.locator('[data-empty-kind="no_match"] .empty-title')).to_have_text('Keine passenden Rezepte')
        expect(page.get_by_label('Kennzeichnung', exact=True)).to_have_value(filter_catalog['tag'])
        expect(page.locator('#tag option:checked')).to_have_text('Regional · archiviert')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.get_by_role('heading', level=1).scroll_into_view_if_needed()
        page.screenshot(path=str(evidence / f'recipes-empty-{width}-js-{javascript}.png'), caret='initial')
        assets = page.locator('link[rel="stylesheet"], script[src]').evaluate_all(
            'els => els.map(el => new URL(el.href || el.src).pathname)')
        assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
        assert all(200 in responses.get(asset, []) and set(responses[asset]) <= {200, 304}
                   for asset in assets if javascript or asset.endswith('.css'))
        assert not errors and not writes
        (evidence / f'metrics-{width}-js-{javascript}.json').write_text(json.dumps({
            'viewport': width, 'javascript': javascript, 'first_page': 50, 'second_page': 3,
            'native_keyboard_submit': True, 'no_horizontal_overflow': True,
            'console_errors': errors, 'writes': writes, 'assets': assets,
        }, indent=2), encoding='utf-8')
    assert complete_snapshot(owner) == before


@pytest.mark.parametrize('javascript', [False, True])
def test_polish_recipe_pages(b3, master_server, browser, javascript):  # noqa: F811
    """Exercise the six P3 pages with real recipes, an image and a frozen revision."""
    from cafeteria import recipe_store as store
    from test_master_data_db import signed_in
    from test_recipe_revision_routes import fields, upload
    from test_recipe_store_db import complete_line, payload

    app, _, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        row = store.create_recipe(engine, actor, payload(
            title='Polish Prüfrezept', ingredients=[complete_line(engine, actor)]),
            expected_location_id=store.get_location(engine))
    root = f'/admin/rezepte/{row.public_id}'
    assert upload(client, root + '/bilder').status_code == 303
    assert client.post(root + '/revisionen', data=fields(client, root + '/revisionen')).status_code == 303
    base, cookie = master_server
    evidence = Path(__file__).resolve().parents[2] / '.claude/evidence/p3-rezepte-after'
    evidence.mkdir(parents=True, exist_ok=True)
    with browser.new_context(java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        for width in (1440, 360):
            page.set_viewport_size({'width': width, 'height': 900})
            for name, path in (
                ('rezepte', '/admin/rezepte'), ('import', '/admin/rezepte/import'),
                ('images', root + '/bilder'), ('scale', root + '/skalierung'),
                ('revisionen', root + '/revisionen'), ('conflict', root),
            ):
                assert page.goto(base + path).status == 200
                if name == 'conflict':
                    page.locator('#recipe-editor input[name="row_version"]').evaluate("el => el.value = '0'")
                    original = page.locator('#recipe-editor').evaluate('f => [...new FormData(f)]')
                    with page.expect_response(lambda response: response.request.method == 'POST') as response:
                        page.get_by_role('button', name='Speichern', exact=True).click()
                    assert response.value.status == 400
                    expect(page.locator('#recipe-error')).to_be_visible()
                    recovered = page.locator('section input[type="hidden"]').evaluate_all(
                        'els => els.map(e => [e.name, e.value])')
                    assert recovered == original
                    assert page.locator('textarea:not([readonly])').count() == 0
                page.evaluate('document.fonts.ready')
                metrics = page.evaluate('''() => ({
                    height: document.documentElement.scrollHeight,
                    primary: [...document.querySelectorAll('main .btn-primary')].filter(e => e.checkVisibility()).length,
                    hints: [...document.querySelectorAll('main .form-hint')].filter(e => e.checkVisibility()).length,
                    overflow: document.documentElement.scrollWidth > innerWidth + 1
                })''')
                print('P3_METRICS ' + json.dumps(dict(page=name, width=width, javascript=javascript, **metrics)))
                page.screenshot(path=str(evidence / f'p3-{name}-{width}-js-{javascript}.png'), full_page=True)
                assert metrics['primary'] == 1
                assert not metrics['overflow']
                assert page.locator('main .btn-primary:visible').bounding_box()['y'] < 900
                if name == 'rezepte':
                    expect(page.locator('.admin-list-row')).to_be_visible()
                    expect(page.locator('.admin-list-row .admin-label').first).to_be_visible()
                elif name in ('images', 'scale', 'revisionen'):
                    expect(page.locator('table.admin-table.admin-table--stack').first).to_be_visible()
                for table in page.locator('main table').all():
                    classes = table.get_attribute('class').split()
                    assert 'admin-table' in classes and 'admin-table--stack' in classes
                    assert table.locator('thead th:not([scope="col"]), tbody td:not([data-label])').count() == 0
                    row_style = table.locator('tbody tr').first.evaluate('e => getComputedStyle(e).display')
                    assert row_style == ('grid' if width < 768 else 'table-row')
                if name == 'rezepte':
                    page.locator('.admin-filter-more > summary').click()
                help_control = page.locator('.admin-hint > summary').first
                help_control.focus()
                expect(help_control).to_be_focused()
                page.keyboard.press('Enter')
                expect(help_control.locator('..')).to_have_attribute('open', '')
                expect(page.locator('#' + help_control.get_attribute('aria-describedby'))).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.keyboard.press('Enter')
                if name == 'revisionen':
                    expected = page.locator('#recipe-freeze-form').evaluate('f => [...new FormData(f)]')
                    with page.expect_request(lambda request: request.method == 'POST') as request:
                        page.get_by_role('button', name='Gespeicherten Stand festhalten', exact=True).click()
                    from urllib.parse import parse_qsl
                    assert sorted(parse_qsl(request.value.post_data)) == sorted(map(tuple, expected))
                    expect(page.locator('#recipe-error')).to_be_visible()
