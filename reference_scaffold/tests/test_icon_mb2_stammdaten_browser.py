"""MB2 keeps creation, row actions and native archive confirmation reachable."""
from __future__ import annotations

import pytest
import json
import hashlib
from playwright.sync_api import expect, sync_playwright

from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_master_data_routes import create
from test_ui_route_inventory import _prepare_inventory_entities
from test_admin_screens_preview_browser import screen_app, screen_server, database_engine  # noqa: F401


@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [390, 1440])
def test_mb2_row_actions_filter_and_create(admin_app, admin_engine, live_server, tmp_path,  # noqa: F811
                                         javascript, width):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    prepared = _prepare_inventory_entities(admin_app, admin_engine, actor)
    create(client, 'kategorien', name='MB2 Kategorie', code='MB2', sort_order='1')
    evidence = tmp_path
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
                    expect(page.locator('.admin-filter-dialog')).to_have_count(1)
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
                    expect(page.locator('.component-secondary-actions')).to_have_attribute('open', '')
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
                        page.locator('.component-secondary-actions form [data-semantic="actions.activate"]').click()
                    assert response.value.status == 303
                    page.goto(f'/admin/{family}/komponenten')
                    page.locator('[data-semantic="view.filter"]').click()
                    expect(page.locator('#f-cat')).to_be_visible()
                    expect(page.locator('#f-status')).to_be_visible()
                    page.locator('.admin-filter-dialog [data-read-detail-close]').click()
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
                    if name == 'cookbooks':
                        expect(page.locator('.cookbook-list [data-semantic="actions.more"]')).to_have_count(0)
                        for book in page.locator('.cookbook-list tbody tr').all():
                            expect(book.locator('[data-semantic="actions.open"]')).to_be_visible()
                            expect(book.locator('[data-semantic="actions.edit"]')).to_be_visible()
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


@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Editor'])
@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_direct_actions_across_wp3_surfaces(
    screen_app, screen_server, database_engine, tmp_path, role, width, javascript,  # noqa: F811
):
    screen_app.config['LOCAL_AUTH_ENABLED'] = True
    _, actor = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    prepared = _prepare_inventory_entities(screen_app, database_engine, actor)
    client, _ = _login(screen_app, database_engine, [role])
    cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    routes = {
        'rezepte': '/admin/rezepte', 'kochbuecher': '/admin/kochbuecher',
        'api': '/admin/api', 'components': '/admin/cafeteria/komponenten',
        'patient-components': '/admin/patienten/komponenten',
        'grundlagen': '/admin/grundlagen', 'screens': '/admin/screens',
        'vorlagen': '/admin/vorlagen', 'weeks': '/admin/cafeteria/wochen',
        'patient-weeks': '/admin/patienten/wochen', 'local_users': '/admin/benutzer',
        **{endpoint.rsplit('.', 1)[1]: prepared['endpoint_paths'][endpoint]
           for endpoint in (
               'admin.recipe_view', 'admin.recipe_revisions', 'admin.component_detail',
               'admin.dish_templates_list', 'admin.dish_template_edit',
               'admin.shopping_lists_index', 'admin.shopping_list_detail',
               'admin.inventory_home', 'admin.order_home',
           )},
    }
    captures = []
    with sync_playwright() as playwright:
        with playwright.chromium.launch(args=['--no-sandbox']) as browser:
            with browser.new_context(base_url=screen_server, java_script_enabled=javascript,
                                     has_touch=width == 390, reduced_motion='reduce',
                                     viewport={'width': width, 'height': 844 if width == 390 else 900}) as context:
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': screen_server}])
                page = context.new_page()
                posts = []
                page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
                for name, path in routes.items():
                    response = page.goto(path)
                    if role == 'Cafeteria.Editor' and name in {'api', 'local_users'}:
                        assert response.status == 403
                        continue
                    assert response.status == 200, (name, path, response.status)
                    expect(page.locator('main [data-semantic="actions.more"]')).to_have_count(0)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    actions = []
                    for action in page.locator('main .admin-row-actions > .ui-sem-control:visible').all():
                        label = action.get_attribute('aria-label')
                        assert label, (name, action.evaluate('el => el.outerHTML'))
                        classes = action.get_attribute('class') or ''
                        # Alt: every control in .admin-row-actions had to_have_text('').
                        # Neu: hub and section links show a destination label.
                        # Row object actions stay icon-only (Icon-first §5.4).
                        if 'ui-sem-control--icon-only' in classes:
                            expect(action).to_have_text('')
                        else:
                            assert action.inner_text().strip(), (name, label)
                        expect(action).to_have_attribute('data-ui-tooltip', label)
                        box = action.bounding_box()
                        assert box['width'] >= (44 if width == 390 else 36) and box['height'] >= (44 if width == 390 else 36), (name, label, box)
                        assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1
                        if not action.is_disabled():
                            action.focus()
                            expect(action).to_be_focused()
                        href = action.get_attribute('href')
                        if href and not href.startswith('#'):
                            result = context.request.get(href)
                            assert result.status == 200, (name, href, result.status)
                        actions.append({'name': label, 'href': href, 'key': action.get_attribute('data-semantic')})
                    page.mouse.move(0, 0)
                    page.keyboard.press('Escape')
                    screenshot = tmp_path / f'{name}-{role}-{width}.png'
                    page.screenshot(path=str(screenshot), full_page=width != 390)
                    captures.append({'surface': name, 'route': path, 'role': role,
                                     'viewport': page.viewport_size, 'javascript': javascript, 'actions': actions,
                                     'screenshot': screenshot.name,
                                     'screenshot_sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()})
                assert not posts
    (tmp_path / 'surfaces.json').write_text(json.dumps(captures, ensure_ascii=False, indent=2))
