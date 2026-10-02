"""UI-DELTA shopping and orders: static fields, one navigation action, read preview."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from cafeteria import roles
from cafeteria.order_basket_store import get_basket
from cafeteria.shopping_list_store import add_manual_item, create_shopping_list
from delta_browser_evidence import capture_delta
from test_bf_error_paths_browser import _setup
from test_delta_renderer_browser import VISIBILITY
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_shopping_order_delta(b3, master_server, browser, monkeypatch, tmp_path,  # noqa: F811
                             width, height, touch, javascript):
    base, cookie = master_server
    failures = []
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()

        def capture(label):
            capture_delta(page, tmp_path / f'{label}.png', touch)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if page.locator('main details, main summary').count():
                failures.append(label + ': content accordion')
            for control in page.locator('main .ui-sem-control:visible, main .admin-segment-switch a').all():
                rendered = control.evaluate(VISIBILITY)
                assert not rendered['pseudos'], rendered
                assert (rendered['icons'] == 1 and not rendered['text']) or (
                    rendered['icons'] == 0 and bool(rendered['text'])
                ), rendered

        def visit(route, label):
            assert page.goto(base + route).status == 200
            capture(label)

        visit('/admin/bestellung', 'orders-empty')
        if page.locator('main a[href="/admin/bestellung?open=lieferant#code"]').count() != 1:
            failures.append('R-30: duplicate supplier entry')
        visit('/admin/einkaufslisten', 'shopping-empty')
        navigation_y = page.locator('.shopping-filter').evaluate('el => el.getBoundingClientRect().y + scrollY')
        if page.locator('main a[href="#title"]').count() != 1:
            failures.append('R-26: duplicate list creation entry')
        if not page.locator('#note').is_visible() or not page.locator('#menu_week_public_id').is_visible():
            failures.append('D-75: optional create fields hidden')
        if page.locator('#einkaufsliste-neu-extra > summary').count():
            page.locator('#einkaufsliste-neu-extra > summary').click()
        page.locator('#title').fill(' ')
        page.locator('#note').fill('Fehlernotiz bleibt')
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.locator('.shopping-create-form button').click()
        assert rejected.value.status == 400
        expect(page.locator('#note')).to_have_value('Fehlernotiz bleibt')
        capture('shopping-error')
        error_navigation_y = page.locator('.shopping-filter').evaluate('el => el.getBoundingClientRect().y + scrollY')
        if abs(error_navigation_y - navigation_y) > 1:
            failures.append('N-14: navigation moves below error/form')

        state = _setup(b3)
        shopping = create_shopping_list(state['engine'], state['scope'], title='Vorrat-Liste',
                                        note='Die Notiz bleibt unmittelbar lesbar.')
        add_manual_item(state['engine'], state['scope'], shopping, item_text='Beutel ohne Einheit')
        shopping_url = '/admin/einkaufslisten/' + shopping
        visit('/admin/bestellung', 'orders-filled')
        expect(page.locator('#artikel .admin-list-status')).to_have_count(0)
        for selector in ('#basket_supplier', '#code', '#article_code'):
            if not page.locator(selector).is_visible():
                failures.append(selector + ': hidden native field')
        visit('/admin/einkaufslisten', 'shopping-filled')
        filled_navigation_y = page.locator('.shopping-filter').evaluate('el => el.getBoundingClientRect().y + scrollY')
        if abs(filled_navigation_y - navigation_y) > 1:
            failures.append('N-13: navigation moves below counts')
        expect(page.locator('.shopping-list .admin-list-status')).to_have_count(0)
        visit(shopping_url, 'shopping-note')
        if not page.get_by_text('Die Notiz bleibt unmittelbar lesbar.', exact=True).is_visible():
            failures.append('D-74: note hidden')

        visit(state['basket'], 'basket')
        if page.locator('main a[href="/admin/bestellung"]').count() != 1:
            failures.append('R-31: duplicate basket return')
        original = page.locator('#basket-save').evaluate('form => [...new FormData(form)]')
        original_version = get_basket(state['engine'], state['location'], state['basket_id'])['row_version']
        save_actions = page.locator('[data-sticky-form="basket-save"]')
        expect(save_actions.locator('button')).to_have_count(1)
        expect(save_actions.locator('button')).to_have_attribute('data-semantic', 'actions.save')
        assert save_actions.evaluate('el => getComputedStyle(el).position') == ('sticky' if javascript else 'static')
        if javascript:
            page.locator('#line-qty-new').focus()
            assert save_actions.evaluate('el => getComputedStyle(el).position') == 'static'
            page.locator('#line-qty-new').evaluate('el => el.blur()')
        dialog = page.locator('dialog#korb-vorschau')
        if dialog.count():
            def background_geometry():
                return page.locator(':is(.page-header, .order-lines tr, .order-lines th, .order-lines td):visible').evaluate_all(
                    'els => els.map(el => { const r = el.getBoundingClientRect(); '
                    'return {x: r.x, y: r.y + scrollY, width: r.width, height: r.height}; })')

            trigger = page.locator('#korb-vorschau-trigger')
            trigger.focus()
            frame = page.locator('.page-body').bounding_box()
            scroll = page.evaluate('scrollY')
            background = background_geometry()
            trigger.press('Enter')
            expect(dialog).to_be_visible()
            expect(dialog.locator('pre')).to_contain_text('Fehlerartikel')
            expect(dialog.locator('form, input, select')).to_have_count(0)
            capture('basket-preview')
            opened = background_geometry()
            opened_scroll = page.evaluate('scrollY')
            if javascript:
                page.keyboard.press('Escape')
                expect(trigger).to_be_focused()
            else:
                dialog.get_by_role('link', name='Schliessen', exact=True).click()
                expect(trigger).to_be_in_viewport()
                trigger.focus()
                expect(trigger).to_be_focused()
                if scroll > 0:
                    assert page.evaluate('scrollY') > 0
            expect(dialog).not_to_be_visible()
            after = page.locator('.page-body').bounding_box()
            geometry = {'before': frame, 'after': after, 'scroll_before': scroll,
                        'scroll_open': opened_scroll, 'scroll_after': page.evaluate('scrollY'),
                        'background_before': background, 'background_open': opened,
                        'background_after': background_geometry()}
            (tmp_path / 'preview-geometry.json').write_text(json.dumps(geometry, indent=2))
            assert abs(frame['width'] - after['width']) <= 1, geometry
            for measured in (opened, geometry['background_after']):
                assert len(measured) == len(background), geometry
                for before_box, after_box in zip(background, measured, strict=True):
                    assert all(abs(before_box[key] - after_box[key]) <= 1 for key in before_box), geometry
            if javascript:
                assert abs(geometry['scroll_before'] - geometry['scroll_open']) <= 1, geometry
                assert abs(geometry['scroll_before'] - geometry['scroll_after']) <= 1, geometry
            assert page.locator('#basket-save').evaluate('form => [...new FormData(form)]') == original
            assert get_basket(state['engine'], state['location'], state['basket_id'])['row_version'] == original_version
        else:
            failures.append('D-71: preview needs shared read dialog')
        if page.locator('#korb-weitere > summary').count():
            page.locator('#korb-weitere > summary').click()
        expect(page.locator('#basket-demand [name="_csrf"]')).to_have_value('b3-test-csrf')
        expect(page.locator('#basket-demand [name="row_version"]')).to_have_value(str(original_version))
        page.locator('#demand_food').fill('invalid-uuid')
        page.locator('#need_quantity').fill('3.25')
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.locator('#basket-demand button').click()
        assert rejected.value.status == 400
        expect(page.locator('#demand_food')).to_have_value('invalid-uuid')
        expect(page.locator('#need_quantity')).to_have_value('3.25')
        expect(page.locator('#demand_food-error')).to_be_visible()
        assert get_basket(state['engine'], state['location'], state['basket_id'])['row_version'] == original_version
        capture('demand-error')

        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
        visit(shopping_url, 'shopping-readonly')
        expect(page.locator('.shopping-manual-table input')).to_have_count(0)
        unit = page.locator('.shopping-manual-table td[data-label="Einheit"]')
        if unit.inner_text().strip():
            failures.append('P-41: missing optional unit has placeholder')
        assert unit.evaluate('el => getComputedStyle(el, "::before").content') in ('none', 'normal', '"Einheit"')
        if width == 390:
            expect(unit).not_to_be_visible()
    assert not failures, failures
