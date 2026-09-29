"""MB2 keeps creation, row actions and native archive confirmation reachable."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_master_data_routes import create
from test_ui_route_inventory import _prepare_inventory_entities


@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [390, 1440])
def test_mb2_row_actions_filter_and_create(admin_app, admin_engine, live_server, tmp_path,  # noqa: F811
                                         javascript, width):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    prepared = _prepare_inventory_entities(admin_app, admin_engine, actor)
    create(client, 'kategorien', name='MB2 Kategorie', code='MB2', sort_order='1')
    evidence = Path(__file__).resolve().parents[2] / '.claude/evidence/icon-mb2-0926'
    evidence.mkdir(parents=True, exist_ok=True)
    cookie = client.get_cookie('session')
    with sync_playwright() as playwright:
        with playwright.chromium.launch(args=['--no-sandbox']) as browser:
            with browser.new_context(base_url=live_server, java_script_enabled=javascript,
                                     viewport={'width': width, 'height': 900}) as context:
                context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                page = context.new_page()
                page.on('dialog', lambda dialog: dialog.accept())
                for family in ('cafeteria', 'patienten'):
                    page.goto(f'/admin/{family}/komponenten')
                    expect(page.locator('.admin-filter-more')).to_have_count(1)
                    expect(page.locator('#f-cat')).to_be_hidden()
                    expect(page.locator('#f-status')).to_be_hidden()
                    expect(page.locator('#create-component > summary')).to_be_hidden()
                    page.screenshot(path=str(evidence / f'{family}-{width}-{javascript}.png'), full_page=True)
                    row = page.locator('.component-row').first
                    expect(row.locator('[data-semantic="actions.edit"]')).to_be_visible()
                    expect(row.locator('[data-semantic="actions.more"]')).to_have_count(0)
                    archive = row.locator('[data-semantic="actions.archive"]')
                    expect(archive).to_be_visible()
                    archive.click()
                    page.locator('.component-secondary-actions > summary').click()
                    form = page.locator('.component-secondary-actions form')
                    expect(form).to_have_attribute('method', 'post')
                    assert form.get_attribute('action').endswith('/archive')
                    assert form.locator('[name="_csrf"]').input_value()
                    assert form.locator('[name="row_version"]').input_value()
                    with page.expect_response(lambda response: response.request.method == 'POST') as response:
                        form.locator('[data-semantic="actions.archive"]').click()
                    assert response.value.status == 303
                    page.locator('.component-secondary-actions > summary').click()
                    with page.expect_response(lambda response: response.request.method == 'POST') as response:
                        page.locator('.component-secondary-actions [data-semantic="actions.activate"]').click()
                    assert response.value.status == 303
                    page.goto(f'/admin/{family}/komponenten')
                    page.locator('.admin-filter-more summary').click()
                    expect(page.locator('#f-cat')).to_be_visible()
                    expect(page.locator('#f-status')).to_be_visible()
                    page.locator('.page-header [data-semantic="actions.add"]').click()
                    expect(page.locator('#c-name')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.screenshot(path=str(tmp_path / f'{family}-{width}-{javascript}.png'), full_page=True)
                operation_pages = {
                    'cookbooks': '/admin/kochbuecher',
                    **{endpoint.rsplit('.', 1)[1]: prepared['endpoint_paths'][endpoint]
                       for endpoint in ('admin.inventory_home', 'admin.cost_home', 'admin.order_home',
                                        'admin.order_basket', 'admin.shopping_list_detail')},
                }
                for name, path in operation_pages.items():
                    response = page.goto(path)
                    assert response.status == 200
                    expect(page.get_by_role('heading', level=1)).to_be_visible()
                    expect(page.locator('dl.admin-statusbar')).to_have_count(0)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.screenshot(path=str(evidence / f'{name}-{width}-{javascript}.png'), full_page=True)
                for kind in ('foods', 'units', 'categories', 'tags', 'storage_locations'):
                    page.goto('/admin/grundlagen?kind=' + kind)
                    rows = page.locator('.grundlagen-list .admin-list-row')
                    assert rows.count()
                    for row in rows.all():
                        expect(row.locator('[data-semantic="actions.edit"]')).to_be_visible()
                        expect(row.locator('[data-semantic="actions.open"]')).to_have_count(0)
                    page.screenshot(path=str(evidence / f'{kind}-{width}-{javascript}.png'), full_page=True)
                    expect(rows.locator('[data-semantic="actions.more"]')).to_have_count(0)
                    archive = rows.locator('[data-semantic="actions.archive"]').first
                    if archive.count():
                        expect(archive).to_be_visible()
                        archive.click()
                        expect(page.locator('#master-status')).to_be_visible()
                        expect(page.locator('#master-status')).to_have_attribute('method', 'post')
                        assert page.locator('#master-status [name="_form_context"]').input_value()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
