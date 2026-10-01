"""UI-DELTA: cookbook actions, static archive guidance and exclusive controls."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store as store
from test_cookbooks_browser import cookbook_server  # noqa: F401
from test_delta_renderer_browser import VISIBILITY
from test_master_data_db import signed_in
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_recipe_store_db import snapshot, target
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_cookbook_delta_contract(cookbook_server, browser, tmp_path, width, height, touch):  # noqa: F811
    data = cookbook_server
    failures = []
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch) as context:
        cookie = data['cookie']
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': data['base']}])
        page = context.new_page()

        def visit(path, label):
            assert page.goto(data['base'] + path).status == 200
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            # Filter summaries and their counters are the open DELTA-2b contract.
            for control in page.locator('main a.ui-sem-control:visible, main button.ui-sem-control:visible').all():
                rendered = control.evaluate(VISIBILITY)
                assert (rendered['icons'] == 1 and not rendered['text']) or (
                    rendered['icons'] == 0 and bool(rendered['text'])
                ), rendered

        visit('/admin/kochbuecher', 'empty-list')
        if page.locator('main [data-semantic="actions.add"]').count() != 1:
            failures.append('R-03: empty list has duplicate create actions')
        expect(page.locator('.page-header [data-semantic="actions.add"]')).to_have_attribute(
            'href', '/admin/kochbuecher/neu')

        with signed_in(data['engine'], data['actor']):
            location = store.get_location(data['engine'])
            book = store.create_cookbook(data['engine'], data['actor'], name='Saison-Küche',
                                         description='Rezepte für Herbst und Winter.',
                                         expected_location_id=location)
        path = '/admin/kochbuecher/' + book.public_id
        visit('/admin/kochbuecher', 'list')
        row = page.locator('main tbody tr')
        expect(row.get_by_text('0 Rezepte', exact=True)).to_be_visible()
        expect(row.locator('[data-semantic="actions.open"]')).to_have_attribute('href', path + '/ansicht')
        expect(row.locator('[data-semantic="actions.edit"]')).to_have_attribute('href', path)
        expect(row.locator('.admin-list-status, .admin-empty-value')).to_have_count(0)
        visit('/admin/kochbuecher?q=unmatched', 'search-empty')
        if page.locator('main [data-semantic="view.reset"]').count() != 1:
            failures.append('R-75: identical reset actions without archive filter')
        visit('/admin/kochbuecher?q=unmatched&archived=1', 'archive-search-empty')
        # Clear all filters and clear only the query have different meanings.
        expect(page.locator('main [data-semantic="view.reset"]')).to_have_count(2)
        visit(path + '/ansicht', 'view')
        expect(page.locator('main form')).to_have_count(0)
        visit(path, 'editor')
        expect(page.get_by_label('Name', exact=True)).to_have_value('Saison-Küche')
        visit(path + '/status', 'confirmation')
        for control in page.locator('form .ui-sem-control').all():
            assert control.evaluate(VISIBILITY)['icons'] == 0
        with signed_in(data['engine'], data['actor']):
            store.set_cookbook_active(data['engine'], data['actor'], target(book), active=False,
                                      expected_location_id=location)
        before = snapshot(data['owner'])
        visit(path, 'archived-editor')
        if page.locator('main details, main summary').count():
            failures.append('D-99: archive guidance still expands inline')
        if not page.locator('#cookbook-readonly-hint').is_visible():
            failures.append('D-99: archive guidance is not immediately readable')
        expect(page.locator('main form')).to_have_count(0)
        assert snapshot(data['owner']) == before
    assert not failures, failures
