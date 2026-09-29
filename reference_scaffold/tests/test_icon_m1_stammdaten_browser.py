"""Pilot lists retain navigation, state meaning and accessible symbol actions."""
from __future__ import annotations

import json
import re

from playwright.sync_api import expect, sync_playwright

from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_ui_list_family_browser import _measure
from test_ui_route_inventory import _prepare_inventory_entities


def test_stammdaten_icon_actions_names_and_list_states(admin_app, admin_engine, live_server, tmp_path):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _prepare_inventory_entities(admin_app, admin_engine, actor)
    cookie = client.get_cookie('session')
    paths = {
        'bausteine-cafeteria': '/admin/cafeteria/komponenten',
        'bausteine-patienten': '/admin/patienten/komponenten',
        'zutaten': '/admin/grundlagen?kind=foods',
        'einheiten': '/admin/grundlagen?kind=units',
        'kategorien': '/admin/grundlagen?kind=categories',
        'kennzeichnungen': '/admin/grundlagen?kind=tags',
        'lagerorte': '/admin/grundlagen?kind=storage_locations',
    }
    measurements = []
    touch_observed = False
    with sync_playwright() as playwright:
        with playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
            for width, touch in ((1440, False), (390, True)):
                with browser.new_context(base_url=live_server, viewport={'width': width, 'height': 844 if touch else 900},
                                         has_touch=touch) as context:
                    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                    page = context.new_page()
                    for slug, path in paths.items():
                        assert page.goto(path).status == 200
                        page.evaluate('document.fonts.ready')
                        coarse = page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches")
                        touch_observed = touch_observed or coarse
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        expect(page.locator('.page-header .btn')).to_have_count(1)
                        controls = page.locator('main .ui-sem-control').all()
                        for control in controls:
                            if control.is_visible():
                                assert control.inner_text().strip() == ''
                                assert control.get_attribute('aria-label')
                                assert control.get_attribute('data-ui-tooltip')
                                box = control.bounding_box()
                                assert box['height'] >= (44 if coarse else 36), {
                                    'page': slug, 'width': width, 'name': control.get_attribute('aria-label'),
                                    'coarse': page.evaluate("matchMedia('(any-pointer: coarse)').matches"),
                                    'size': control.evaluate("e => getComputedStyle(e).getPropertyValue('--ui-control-size')"),
                                    'box': box,
                                }
                                assert box['width'] >= (44 if coarse else 36)
                        data = _measure(page)
                        measurements.append({'page': slug, 'width': width, 'coarse': coarse, **data})
                        assert data['header']['withText'] == 0
                        for listing in data['lists']:
                            if listing['row'] is None:
                                assert listing['total'] == 0
                                continue
                            assert not listing['row']['card']
                            assert 1 <= listing['rowActions']['count'] <= 2
                            assert listing['rowActions']['withText'] == 0
                            if listing['primary']:
                                assert listing['primary']['fontSize'] == '14px'
                                assert listing['primary']['fontWeight'] == '600'
                        page.screenshot(path=str(tmp_path / f'{slug}-{width}.png'), full_page=True)
                        if slug.startswith('bausteine'):
                            expect(page.locator('.admin-statusbar')).to_have_count(0)
                            expect(page.locator('#f-status')).to_have_value('active')
                            expect(page.locator('.component-status')).to_have_count(0)
                            expect(page.locator('.component-row-name a')).to_have_count(0)
                            row = page.locator('.component-row').first
                            if row.count():
                                name = row.locator('.component-row-name > .admin-list-primary').inner_text()
                                edit = row.locator('[data-semantic="actions.edit"]')
                                expect(edit).to_have_accessible_name(f'{name} bearbeiten')
                                target = f'{path}/{row.get_attribute("data-public-id")}'
                                expect(edit).to_have_attribute('href', target)
                                edit.focus()
                                expect(edit).to_be_focused()
                                edit.press('Enter')
                                page.wait_for_url('**' + target)
                                expect(page.locator('#component-form')).to_be_visible()
                                save = page.locator('#component-form [data-semantic="actions.save"]')
                                expect(save).to_have_text('')
                                assert save.get_attribute('aria-label').endswith(' speichern')
                        else:
                            expect(page.locator('.grundlagen-list .card-header')).to_have_count(0)
                            expect(page.locator('.grundlagen-filter summary')).to_have_count(1)
                            expect(page.locator('.grundlagen-filter [data-semantic="view.filter"]')).to_have_count(1)
                            expect(page.locator('.grundlagen-filter')).to_contain_text('Aktiv')
                            expect(page.locator('.grundlagen-list .admin-list-status .admin-label')).to_have_count(0)
                            expect(page.locator('.grundlagen-list a.admin-list-primary, '
                                                '.grundlagen-list .admin-list-primary a')).to_have_count(0)
                            row = page.locator('.grundlagen-list .admin-list-row').first
                            if row.count():
                                name = row.locator('span.admin-list-primary').inner_text()
                                edit = row.locator('[data-semantic="actions.edit"]')
                                expect(edit).to_have_accessible_name(f'{name} bearbeiten')
                                expect(edit).to_have_attribute('href', re.compile(r'^/admin/grundlagen/[^/]+/[^/#?]+$'))
                                target = edit.get_attribute('href')
                                edit.focus()
                                expect(edit).to_be_focused()
                                edit.press('Enter')
                                page.wait_for_url('**' + target)
                            page.goto(path + '&archived=1')
                            for row in page.locator('.grundlagen-list .admin-list-row').all():
                                expect(row.locator('.admin-list-status .admin-label')).to_be_visible()
    assert touch_observed, 'Touch media query was not exercised.'
    (tmp_path / 'measurements.json').write_text(json.dumps(measurements, ensure_ascii=False, indent=2))
