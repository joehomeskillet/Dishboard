"""UI-DELTA ingredient and stock consumers preserve native state and recovery."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria import roles
from delta_browser_evidence import capture_delta
from test_bf_error_paths_browser import _movements, _stock
from test_delta_renderer_browser import VISIBILITY
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_db import STORAGE_PUBLIC_ID
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, create, installed_pg16, pg16, seeded_pg16, snapshot,
)
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_food_stock_delta(b3, master_server, browser, monkeypatch, tmp_path,  # noqa: F811
                         width, height, touch, javascript):
    _, owner, client, _ = b3
    base, cookie = master_server
    failures = []
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.set_default_timeout(5000)

        def capture(label):
            capture_delta(page, tmp_path / f'{label}.png', touch)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if page.locator('main details, main summary').count():
                failures.append(label + ': content accordion')
            for control in page.locator('main .ui-sem-control:visible').all():
                rendered = control.evaluate(VISIBILITY)
                if rendered['pseudos'] or not (
                    rendered['icons'] == 1 and not rendered['text'] or
                    rendered['icons'] == 0 and bool(rendered['text'])
                ):
                    failures.append((label, rendered))

        def visit(path, label):
            assert page.goto(base + path).status == 200
            capture(label)

        def expose_for_baseline():
            # Only after recording the old UI: reach native fields for before evidence.
            summaries = page.locator('main details:not([open]) > summary')
            while summaries.count():
                summaries.first.click()

        visit('/admin/lager', 'stock-empty')
        visit('/admin/grundlagen/zutaten/neu', 'food-new')
        food = create(client, name='Delta-Zutat', base_unit_code='G')
        food_id = food.rsplit('/', 1)[1]
        visit(food, 'food')
        if page.locator('#food-core-form .admin-form-footer a').count():
            failures.append('R-13: duplicate cancel')
        expose_for_baseline()
        form = page.locator('#food-core-form')
        version = form.locator('[name="row_version"]').input_value()
        token = form.locator('[name="_form_context"]').input_value()
        page.locator('#density_g_per_ml').fill('-1')
        with page.expect_response(lambda r: r.request.method == 'POST') as invalid:
            form.get_by_role('button', name='Speichern', exact=True).click()
        assert invalid.value.status == 400
        expect(form.locator('[name="row_version"]')).to_have_value(version)
        expect(form.locator('[name="_form_context"]')).to_have_value(token)
        expect(page.locator('#density_g_per_ml')).to_have_value('-1')
        capture('food-error')
        visit(food, 'food-before-price')
        expose_for_baseline()
        page.locator('#valid_from').fill('2026-09-01')
        page.locator('#unit_price').fill('2.50')
        with page.expect_response(lambda r: r.request.method == 'POST') as price:
            page.get_by_role('button', name='Preis speichern', exact=True).click()
        assert price.value.status == 303, page.locator('#price-error').inner_text()
        expect(page.locator('[data-label="Preis"]')).to_contain_text('2.5')
        if page.locator('[data-label="Gültig bis"]').inner_text() != 'Unbefristet':
            failures.append('P-23: open-ended price needs explicit text')
        capture('food-price')
        with monkeypatch.context() as read_only:
            read_only.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
            visit(food, 'food-readonly')
            expect(page.locator('main form[method="post"]')).to_have_count(0)
        lager = '/admin/lager?food_public_id=' + food_id + '&storage_public_id=' + STORAGE_PUBLIC_ID
        visit(lager, 'stock-unknown')
        expect(page.locator('[data-label="Bestand"]')).to_have_text('Nicht erfasst')
        page.locator('.lager-row-action a').click()
        if not page.url.endswith('#lager-move'):
            failures.append('N-42: selection lacks detail anchor')
        capture('stock-selected')
        expose_for_baseline()
        page.locator('#counted_quantity').fill('ungültig')
        before = _movements(owner)
        with page.expect_response(lambda r: r.request.method == 'POST') as count_error:
            page.locator('#lager-count-form button').click()
        assert count_error.value.status == 400
        assert _movements(owner) == before
        expect(page.locator('#counted_quantity')).to_have_value('ungültig')
        capture('stock-error')
        page.locator('#counted_quantity').fill('0')
        with page.expect_response(lambda r: r.request.method == 'POST') as counted:
            page.locator('#lager-count-form button').click()
        assert counted.value.status == 303
        assert _stock(owner, food_id, STORAGE_PUBLIC_ID) == 0
        expect(page.locator('[data-label="Bestand"]')).not_to_contain_text('Nicht erfasst')
        expect(page.locator('[data-label="Bestand"]')).to_contain_text('0')
        capture('stock-zero')
        visit(food, 'food-before-conflict')
        expose_for_baseline()
        page.locator('#name').fill('Erhaltener Entwurf')
        page.locator('#note').fill('\nUnverlorene Notiz')
        original = form.evaluate('el => Array.from(new FormData(el).entries())')
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEW','Neu',true)"))
        before = snapshot(owner)
        with page.expect_response(lambda r: r.request.method == 'POST') as conflict:
            form.get_by_role('button', name='Speichern', exact=True).click()
        assert conflict.value.status == 409
        assert snapshot(owner) == before
        expect(page.locator('main form')).to_have_count(0)
        recovery = page.get_by_role('region', name='Ursprüngliche Eingaben', exact=True)
        assert recovery.evaluate(
            'el => Array.from(el.querySelectorAll("input[type=hidden]"), i => [i.name, i.value])',
        ) == original
        expect(page.get_by_label('Notiz', exact=True)).to_have_value('\nUnverlorene Notiz')
        capture('location-conflict')
        for link in page.locator('main .ui-sem-control').all():
            if link.evaluate(VISIBILITY)['icons']:
                failures.append('B-30: recovery must be text')
    assert not failures, failures
