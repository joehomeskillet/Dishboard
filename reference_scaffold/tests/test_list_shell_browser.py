"""Real list edges, including wrappers, singleton catalogs and calendar state."""
from __future__ import annotations

import json
from datetime import date

from playwright.sync_api import sync_playwright

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.order_basket_store import create_basket
from cafeteria.shopping_list_store import ShoppingScope
from cafeteria.supplier_store import create_supplier
from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login, _scope
from test_ui_list_family_browser import _hook, _mount_public_targets
from test_ui_route_inventory import _prepare_inventory_entities


ROW_METRICS = """el => {
    const s = getComputedStyle(el), box = el.getBoundingClientRect();
    return {bottom: s.borderBottomWidth, style: s.borderBottomStyle,
            shadow: s.boxShadow, radius: s.borderRadius,
            height: box.height, paddingX: s.paddingLeft, paddingY: s.paddingTop};
}"""


def test_real_list_edges_and_calendar_state(admin_app, admin_engine, live_server, tmp_path):  # noqa: F811
    _mount_public_targets(admin_app)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _prepare_inventory_entities(admin_app, admin_engine, actor)
    scope = _scope(admin_engine, actor)
    second_supplier = create_supplier(admin_engine, ActorExpectation(actor, scope.expected_authz_version),
                                      {'code': 'EDGE', 'name': 'Zweiter Listenlieferant'})
    create_basket(admin_engine, ShoppingScope(actor, scope.location_id, scope.expected_authz_version),
                  second_supplier.public_id)
    cookie = client.get_cookie('session')
    assert cookie is not None
    pages = (
        ('review-cafeteria', '/admin/cafeteria/wochen/pruefung?week=2026-08-31',
         '[aria-label="Ausgabeangaben"] > [role="listitem"] > .admin-list-row'),
        ('review-patienten', '/admin/patienten/wochen/pruefung?week=2026-08-31',
         '[aria-label="Ausgabeangaben"] > [role="listitem"] > .admin-list-row'),
        ('bestellung', '/admin/bestellung', '.order-list > [role="listitem"] > .admin-list-row'),
        ('benutzer', '/admin/benutzer', '[data-account-row] > .admin-list-row'),
        ('vorlagen', '/admin/vorlagen?week=2026-08-31', 'li.print-tpl-row:visible'),
    )
    measurements, failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for width, height in ((1440, 900), (390, 844)):
                with browser.new_context(base_url=live_server, viewport={'width': width, 'height': height}) as context:
                    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                    page = context.new_page()
                    for name, path, selector in pages:
                        assert page.goto(path, wait_until='networkidle').status == 200
                        if name == 'vorlagen':
                            _hook(page, 'catalog', '')
                            assert page.locator('.output-area-panels .card').count() == 0
                            catalogs = page.locator('.output-area-panels .admin-list')
                            assert catalogs.count() == 2
                            assert catalogs.evaluate_all("""els => els.every(el => {
                                const s = getComputedStyle(el);
                                return s.borderBottomWidth === '1px' && s.boxShadow === 'none';
                            })""")
                            catalogs.first.screenshot(path=str(tmp_path / f'template-catalog-{width}.png'))
                        rows = page.locator(selector)
                        assert rows.count() > 0, name
                        for index in range(rows.count()):
                            row = rows.nth(index)
                            metrics = row.evaluate(ROW_METRICS)
                            # The final row meets the shell edge; only intervening edges are separators.
                            last = row.evaluate("""el => {
                                const item = el.closest('[role=listitem]') || el;
                                return !item.nextElementSibling;
                            }""")
                            if not last and (metrics['bottom'] != '1px' or metrics['style'] != 'solid'):
                                failures.append((name, width, index, metrics))
                            assert metrics['shadow'] == 'none', (name, width, metrics)
                            assert metrics['radius'] == '0px', (name, width, metrics)
                            measurements.append(dict(page=name, width=width, row=index, **metrics))
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
                        page.screenshot(path=str(tmp_path / f'{name}-{width}.png'), full_page=True)
                        if name == 'vorlagen':
                            screen_rows = page.locator('.print-screen-row')
                            assert screen_rows.count() > 1
                            for index in range(screen_rows.count() - 1):
                                metrics = screen_rows.nth(index).evaluate(ROW_METRICS)
                                measurements.append(dict(page='screen-templates', width=width, row=index, **metrics))
                                if metrics['bottom'] != '1px' or metrics['style'] != 'solid':
                                    failures.append(('screen-templates', width, index, metrics))
                                assert metrics['shadow'] == 'none'
                            action_edges = page.locator('.print-screen-row .admin-row-actions').evaluate_all(
                                'els => els.map(el => el.getBoundingClientRect().right)')
                            assert max(action_edges) - min(action_edges) < 1, (width, action_edges)
                            screen_rows.first.scroll_into_view_if_needed()
                            page.screenshot(path=str(tmp_path / f'screen-templates-{width}.png'))
                        if name in ('bestellung', 'vorlagen'):
                            shells = page.locator('.admin-list:visible')
                            assert shells.count() >= (2 if name == 'bestellung' else 4)
                            assert shells.evaluate_all("""els => els.every(el => {
                                const s = getComputedStyle(el);
                                return s.borderBottomWidth === '1px' && s.borderBottomStyle === 'solid'
                                    && s.borderRadius === '8px' && s.boxShadow === 'none';
                            })""")
                            assert page.locator(
                                '.admin-list > .admin-list-row:last-child, '
                                '.admin-list > [role=listitem]:last-child > .admin-list-row').evaluate_all(
                                    "els => els.every(el => getComputedStyle(el).borderBottomWidth === '0px')")
                    # A state outline is not a decorative shadow on ordinary list rows.
                    today = date.today()
                    assert page.goto(f'/admin/kuechenkalender?jump={today:%Y-%m}', wait_until='networkidle').status == 200
                    if width == 1440:
                        today_cell = page.locator('td.kitchen-cal-day-today')
                        assert today_cell.count() == 1
                        assert 'inset' in today_cell.evaluate('el => getComputedStyle(el).boxShadow')
                        shadows = page.locator('td.kitchen-cal-day:not(.kitchen-cal-day-today)').evaluate_all(
                            "els => [...new Set(els.map(el => getComputedStyle(el).boxShadow))]")
                        # Tabler paints table-cell accents with a transparent inset shadow.
                        assert all(value == 'none' or value.startswith('rgba(0, 0, 0, 0) ')
                                   for value in shadows), shadows
                        measurements.append(dict(page='calendar', width=width, ordinary_shadows=shadows))
                    page.screenshot(path=str(tmp_path / f'calendar-{width}.png'))
        finally:
            browser.close()
    (tmp_path / 'list-shell-measurements.json').write_text(
        json.dumps(measurements, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not failures, failures
