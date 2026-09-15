"""Real native full-text search field on `/admin/rezepte` at mobile/desktop sizes,
without JavaScript (NoJS GET submit)."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_master_data_browser import master_server  # noqa: F401
from test_recipe_filter_reads import recipe_ids
from test_recipe_search_db import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, search_lab, seeded_pg16, step,
)
from test_rendered_ui import browser  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/fts-ui-0915'


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_native_text_search_is_keyboard_operable_ranked_and_no_overflow(
        b3, search_lab, master_server, browser, width, height):  # noqa: F811
    lab = search_lab
    title_hit = lab['recipe']('Zauberwort Auflauf')
    lab['recipe']('Andere Suppe', steps=[step('Sauce langsam passieren')])
    base, cookie = master_server
    evidence = EVIDENCE
    evidence.mkdir(parents=True, exist_ok=True)
    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=False,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, writes = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: writes.append(request.method) if request.method != 'GET' else None)
        response = page.goto(base + '/admin/rezepte')
        assert response.status == 200 and response.headers['cache-control'] == 'no-store'
        form = page.locator('form[action="/admin/rezepte"]')
        assert form.get_attribute('method') == 'get'
        control = page.get_by_label('Suche', exact=True)
        control.focus()
        expect(control).to_be_focused()
        assert control.bounding_box()['height'] >= 44
        control.fill('zauberwort')
        page.get_by_role('button', name='Suchen', exact=True).focus()
        expect(page.get_by_role('button', name='Suchen', exact=True)).to_be_focused()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        assert 'text=zauberwort' in page.url
        expect(page.locator('.recipe-card')).to_have_count(1)
        expect(page.get_by_role('heading', level=2, name='Zauberwort Auflauf', exact=True)).to_be_visible()
        assert recipe_ids(page.content()) == [title_hit.public_id]
        expect(page.get_by_text('Sortiert nach Relevanz.', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.get_by_role('heading', level=1).scroll_into_view_if_needed()
        page.screenshot(path=str(evidence / f'recipes-search-{width}x{height}.png'), caret='initial')
        assert not errors and not writes
