"""UI-DELTA: dish-template context, planning and optional metadata."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

from test_delta_renderer_browser import VISIBILITY
from test_dish_template_routes import create, snapshot
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_dish_template_delta_contract(b3, master_server, browser, tmp_path, width, height, touch):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Gemüse-Teller')
    before = snapshot(owner)
    base, cookie = master_server
    failures = []
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()

        def visit(route, label):
            assert page.goto(base + route).status == 200
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            # DELTA-2b owns the unresolved filter summary and chip modes.
            for control in page.locator('main a.ui-sem-control:visible, main button.ui-sem-control:visible').all():
                rendered = control.evaluate(VISIBILITY)
                assert (rendered['icons'] == 1 and not rendered['text']) or (
                    rendered['icons'] == 0 and bool(rendered['text'])
                ), rendered

        visit('/admin/gerichtvorlagen', 'list')
        expect(page.locator('tbody tr')).to_have_count(1)
        expect(page.locator('td[data-label="Dazu"]')).to_be_empty()
        if page.locator('td[data-label="Menüart"]').inner_text().strip():
            failures.append('P-29: absent menu type must leave an empty cell')
        plan = page.get_by_role('link', name='Gemüse-Teller als Menü einplanen', exact=True)
        expect(plan).to_have_attribute('href', path + '/einplanen')
        if plan.evaluate(VISIBILITY) != {'icons': 0, 'text': 'Einplanen', 'pseudos': [], 'gap': '0px'}:
            failures.append('R-23: planning needs an unambiguous exclusive text action')
        visit('/admin/gerichtvorlagen?q=unmatched', 'search-empty')
        if page.locator('main [data-semantic="view.reset"]').count() != 1:
            failures.append('R-74: duplicate complete reset')
        visit(path, 'editor')
        if page.locator('#template-recipe-details summary').count():
            failures.append('D-76: context still expands inline')
        if page.locator('main a[href="/admin/gerichtvorlagen"]').count() != 1:
            failures.append('R-22: duplicate return to list')
        expect(page.locator('[name="updated_at"]')).to_have_count(1)
        visit(path + '/einplanen', 'planning')
        if not page.locator('#planning-refresh-hint').is_visible():
            failures.append('D-98: planning guidance not immediately readable')
        if page.locator('main details, main summary').count():
            failures.append('D-98: planning guidance still expands inline')
        if page.locator(f'main a[href="{path}"]').count() != 1:
            failures.append('R-25: duplicate return to template')
        expect(page.locator('[name="template_context"]')).to_have_count(1)
        page.get_by_label('Woche ab Montag', exact=True).fill('2026-10-05')
        page.get_by_role('button', name='Ziel aktualisieren', exact=True).click()
        expect(page.get_by_label('Woche ab Montag', exact=True)).to_have_value('2026-10-05')
        expect(page.locator('#planning-summary')).to_contain_text('Gemüse-Teller')
    assert snapshot(owner) == before
    assert not failures, failures
