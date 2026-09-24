"""Navigation supplement: real shell, independent Playwright lifecycle."""
import json
from pathlib import Path
from threading import Thread

import pytest
from flask import render_template_string
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from cafeteria.branding_config import contrast
from cafeteria.roles import require_capability

from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_ui_route_inventory import _factory

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
SHOTS = Path('/tmp/claude-0/-nvmetank1-projects-menuplan/2f4bbcec-0188-43ba-9334-2cbe2fa40c97/scratchpad/nav-shots')


@pytest.fixture
def nav_site(monkeypatch, tmp_path, database_engine):
    app = _factory(monkeypatch, tmp_path, database_engine)

    @app.get('/__nav__/<state>', endpoint='admin.nav_test')
    @require_capability('draft.read')
    def nav_state(state):
        return render_template_string('''{% extends 'admin/base_tabler.html' %}
          {% block sidebar %}
          {% set selection = area_nav.selected %}
          {% set selection.area = 'weeks' if state != 'empty' else '' %}
          {% set selection.item = 'cafeteria' if state == 'child' else '' %}
          {% include 'admin/_workflow_sidebar.html' %}
          {% endblock %}
          {% block content %}<h1>Navigation</h1><a href="#content">Inhalt</a>{% endblock %}
        ''', state=state, family='cafeteria', profile='staff_guest')

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            yield app, origin, database_engine, browser
        finally:
            browser.close()
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


def _page(site, role='Cafeteria.Admin', **options):
    app, origin, engine, browser = site
    client, _ = _login(app, engine, [role])
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    context = browser.new_context(base_url=origin, viewport={'width': 1440, 'height': 900},
                                  reduced_motion='reduce', **options)
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
    return context.new_page()


def _goto(page, state='child'):
    response = page.goto(f'/__nav__/{state}', wait_until='networkidle')
    assert response.status == 200
    page.evaluate('document.fonts.ready')


def test_navigation_screenshots(nav_site):
    page = _page(nav_site)
    _goto(page)
    SHOTS.mkdir(parents=True, exist_ok=True)
    enhanced = page.locator('[data-admin-nav-toggle]').count() > 0
    phase = 'after' if enhanced else 'before'
    page.screenshot(path=str(SHOTS / f'{phase}-expanded.png'))
    if enhanced:
        page.locator('[data-admin-nav-toggle]').click()
        page.screenshot(path=str(SHOTS / 'after-collapsed.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    page.get_by_role('button', name='Menü', exact=True).click()
    expect(page.locator('#sidebar-menu')).to_be_visible()
    page.screenshot(path=str(SHOTS / f'{phase}-mobile.png'))
    page.context.close()


def _style(locator, prop):
    return locator.evaluate('(el, prop) => getComputedStyle(el).getPropertyValue(prop)', prop)


def _hex(rgb):
    return '#' + ''.join(f'{int(n.strip()):02x}' for n in rgb[4:-1].split(','))


def test_flat_states_spacing_contrast_and_focus(nav_site):
    page = _page(nav_site)
    for state, count in [('empty', 0), ('parent', 1), ('child', 1)]:
        page.mouse.move(1000, 800)
        _goto(page, state)
        current = page.locator('#sidebar-menu [aria-current="page"]')
        expect(current).to_have_count(count)
        parents = page.locator('#sidebar-menu .admin-nav-area > .nav-link')
        for index, parent in enumerate(parents.all()):
            symbol = 'down' if index == 0 and state != 'empty' else 'right'
            assert parent.locator('.admin-nav-chevron use').get_attribute('href').endswith(f'#tabler-chevron-{symbol}')
        if count:
            assert _style(current, 'background-color') == 'rgb(49, 88, 91)'
            assert contrast(_hex(_style(current, 'color')), _hex(_style(current, 'background-color'))) >= 4.5
        if state == 'child':
            assert _style(parents.first, 'background-color') == 'rgba(0, 0, 0, 0)'
            assert _style(parents.first, 'box-shadow') == 'none'
        lists = page.locator('#sidebar-menu .admin-nav-subitems')
        expect(lists.locator('svg')).to_have_count(0)
        if lists.count():
            assert _style(lists, 'border-left-width') == '0px'
            assert _style(lists, 'box-shadow') == 'none'
            assert _style(lists, 'background-image') == 'none'
            assert float(_style(lists, 'row-gap')[:-2]) < float(_style(page.locator('#sidebar-menu .navbar-nav'), 'row-gap')[:-2])
            assert _style(lists.locator('.nav-link').first, 'font-size') == '14px'
            assert float(_style(lists.locator('.nav-link').first, 'font-size')[:-2]) < float(_style(parents.first, 'font-size')[:-2])
        for link in page.locator('#sidebar-menu .nav-link').all():
            assert link.bounding_box()['height'] >= 48
        inactive = parents.nth(1)
        base = _style(inactive, 'background-color')
        inactive.hover()
        assert _style(inactive, 'background-color') != base
        inactive.focus()
        page.keyboard.press('Tab')
        page.keyboard.press('Shift+Tab')
        assert float(_style(inactive, 'outline-width')[:-2]) >= 2
        assert _style(inactive, 'outline-color') == 'rgb(255, 255, 255)'
    metrics = {
        'parent_background': _style(parents.first, 'background-color'),
        'child_background': _style(current, 'background-color'),
        'child_contrast': contrast(_hex(_style(current, 'color')), _hex(_style(current, 'background-color'))),
        'group_gap': _style(page.locator('#sidebar-menu .navbar-nav'), 'row-gap'),
        'child_gap': _style(lists, 'row-gap'), 'indent': _style(lists, 'margin-left'),
    }
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / 'metrics.json').write_text(json.dumps(metrics, indent=2))
    page.context.close()


def test_icon_rail_keyboard_flyouts_persistence_and_resize(nav_site):
    page = _page(nav_site)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    _goto(page)
    toggle = page.locator('[data-admin-nav-toggle]')
    expect(toggle).to_have_attribute('aria-controls', 'sidebar-menu')
    toggle.click()
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    expect(toggle).to_have_attribute('aria-label', 'Navigation ausklappen')
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 72
    assert page.locator('main').bounding_box()['x'] == 72
    parents = page.locator('#sidebar-menu .admin-nav-area > .nav-link')
    assert _style(parents.first, 'background-color') == 'rgb(49, 88, 91)'
    expect(page.locator('#sidebar-menu .admin-nav-subitems')).to_be_hidden()
    for parent in parents.all():
        assert parent.get_attribute('aria-label') == parent.get_attribute('title')
        assert parent.locator('.nav-link-title').bounding_box()['width'] <= 1
        parent.focus()
        page.keyboard.press('Tab')
        page.keyboard.press('Shift+Tab')
        assert parent.evaluate('el => getComputedStyle(el, "::after").content') == '"' + parent.get_attribute('title') + '"'
        page.keyboard.press('Enter')
        flyout = page.locator('#admin-nav-flyout')
        expect(flyout).to_be_visible()
        expect(flyout.locator('a').first).to_be_focused()
        expect(parent).to_have_attribute('aria-expanded', 'true')
        expect(flyout.locator('svg')).to_have_count(0)
        if flyout.locator('[aria-current="page"]').count():
            assert _style(parent, 'background-color') == 'rgba(0, 0, 0, 0)'
            expect(flyout.locator('[aria-current="page"]')).to_have_count(1)
            page.screenshot(path=str(SHOTS / 'after-flyout.png'))
        assert flyout.bounding_box()['x'] == 72
        assert flyout.bounding_box()['height'] <= 804
        page.keyboard.press('Escape')
        expect(flyout).to_be_hidden()
        expect(parent).to_be_focused()
        expect(parent).to_have_attribute('aria-expanded', 'false')
    page.reload(wait_until='networkidle')
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 72
    parents.nth(1).click()
    page.locator('#admin-nav-flyout').get_by_role('link', name='Zutaten', exact=True).click()
    page.wait_for_url('**/admin/grundlagen')
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 72
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(toggle).to_be_hidden()
    page.get_by_role('button', name='Menü', exact=True).click()
    expect(page.locator('#sidebar-menu .admin-nav-subitems')).to_be_visible()
    expect(parents.first).not_to_have_attribute('role', 'button')
    page.keyboard.press('Escape')
    expect(page.get_by_role('button', name='Menü', exact=True)).to_be_focused()
    page.set_viewport_size({'width': 1440, 'height': 900})
    toggle.click()
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 248
    page.reload(wait_until='networkidle')
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 248
    assert errors == []
    page.context.close()


def test_no_js_full_sidebar_and_mobile_navigation(nav_site):
    page = _page(nav_site, java_script_enabled=False)
    response = page.goto('/__nav__/child')
    assert response.status == 200
    expect(page.locator('[data-admin-nav-toggle]')).to_be_hidden()
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 248
    expect(page.locator('#sidebar-menu .admin-nav-subitems')).to_be_visible()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.locator('details.admin-nojs-nav summary').click()
    expect(page.locator('details.admin-nojs-nav').get_by_role('link', name='Cafeteria', exact=True)).to_be_visible()
    page.context.close()


def test_long_label_and_reduced_role(nav_site):
    page = _page(nav_site, role='Cafeteria.Editor')
    _goto(page)
    expect(page.locator('.admin-user-role')).to_have_text('Küchenplanung')
    parent = page.locator('#sidebar-menu .admin-nav-area > .nav-link').last
    long_name = 'Sehr lange Navigationsbezeichnung ohne Zeilenumbruch'
    parent.evaluate('(el, text) => { el.title = text; el.querySelector(".nav-link-title").textContent = text; }', long_name)
    label = parent.locator('.nav-link-title')
    assert _style(label, 'white-space') == 'nowrap'
    assert _style(label, 'text-overflow') == 'ellipsis'
    assert label.evaluate('el => el.scrollWidth > el.clientWidth')
    assert parent.get_attribute('title') == long_name
    page.locator('[data-admin-nav-toggle]').click()
    parent.click()
    links = page.locator('#admin-nav-flyout a')
    assert [label.strip() for label in links.all_text_contents()] == ['Daten importieren', 'Schnittstellen']
    page.context.close()


def test_storage_denied_still_allows_navigation(nav_site):
    page = _page(nav_site)
    page.add_init_script('Object.defineProperty(window, "localStorage", {get() {throw new Error("disabled");}})')
    _goto(page)
    page.locator('[data-admin-nav-toggle]').click()
    assert page.locator('.admin-sidebar').bounding_box()['width'] == 72
    page.context.close()
