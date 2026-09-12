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


@pytest.mark.parametrize('width', [390, 1440])
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
        for label in ('Nach Rezepttitel suchen', 'Zutat', 'Tag'):
            control = page.get_by_label(label, exact=True)
            control.focus()
            expect(control).to_be_focused()
            assert control.bounding_box()['height'] >= 48
        page.get_by_label('Nach Rezepttitel suchen', exact=True).fill('Seitensuppe')
        page.get_by_label('Zutat', exact=True).fill('rüebli')
        page.get_by_label('Tag', exact=True).select_option(tag)
        page.get_by_label('Archivierte einschliessen', exact=True).check()
        page.get_by_role('button', name='Suchen', exact=True).focus()
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
        ids = page.locator('.recipe-card a[aria-label]').evaluate_all(
            'els => els.map(el => el.pathname.split("/").pop())')
        assert ids == expected[50:]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('main style, main [style]').count() == 0
        page.get_by_role('heading', level=1).scroll_into_view_if_needed()
        page.screenshot(path=str(evidence / f'recipes-{width}-js-{javascript}.png'), caret='initial')
        page.locator('nav[aria-label="Rezeptseiten"] a[href*="page=1"]').click()
        expect(page.locator('.recipe-card')).to_have_count(50)
        page.get_by_role('link', name='Filter zurücksetzen', exact=True).click()
        assert urlsplit(page.url).query == ''
        expect(page.get_by_label('Nach Rezepttitel suchen', exact=True)).to_have_value('')
        expect(page.get_by_label('Zutat', exact=True)).to_have_value('')
        expect(page.get_by_label('Tag', exact=True)).to_have_value('')
        expect(page.get_by_label('Archivierte einschliessen', exact=True)).not_to_be_checked()
        page.get_by_label('Tag', exact=True).select_option(filter_catalog['tag'])
        page.get_by_label('Zutat', exact=True).fill('keine solche Zutat')
        page.get_by_role('button', name='Suchen', exact=True).click()
        expect(page.get_by_role('heading', name='Keine passenden Rezepte', exact=True)).to_be_visible()
        expect(page.get_by_label('Tag', exact=True)).to_have_value(filter_catalog['tag'])
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
