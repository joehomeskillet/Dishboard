"""Admin shell uses the full working width beside the sidebar on every page."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401
from test_recipe_routes import create
from test_recipe_freeze_v2_browser import native_full_page_capture
from test_rendered_ui import _page as _rendered_page, app as public_app, browser  # noqa: F401
from test_ui_master_shell_browser import _cookie, _goto, _hex, _page, contrast, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

DESKTOP = ((1280, 900), (1440, 900), (1920, 1080), (2560, 1440))
COMPACT = ((1024, 768), (768, 1024), (390, 844), (320, 844), (720, 450))
EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/shell-acceptance-0913'
LONG_TITLE = ('Sommergemüse mit Kräuterkartoffeln und hausgemachter Zitronensauce '
              'für die Gemeinschaftsküche am Sonntag')
SHELL_METRICS = '''() => {
  const main = document.querySelector('main.admin-main');
  const box = document.querySelector('.page-body > .container-xl');
  const cs = getComputedStyle(box);
  const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const containers = [...document.querySelectorAll(
    '.admin-page-header .container-xl, .page-body > .container-xl'
  )].map(el => el.getBoundingClientRect());
  return {
    maxWidth: cs.maxWidth,
    contentWidth: box.getBoundingClientRect().width - pad,
    expected: main.clientWidth - pad,
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
    edges: containers.map(rect => ({x: rect.x, width: rect.width})),
    detailsOpen: [...document.querySelectorAll('main details')].map(el => el.open),
  };
}'''


def _recipe_edit_path(client) -> str:
    # Incomplete drafts return 400 on /revisionen; the edit page shares the same shell.
    return urlsplit(create(client, title=LONG_TITLE)).path


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_admin_pages_use_full_working_width(site, tmp_path: Path, javascript):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    recipe_path = _recipe_edit_path(client)
    routes = (
        ('darstellung', '/admin/design/darstellung'),
        ('menues', '/admin/cafeteria/menues'),
        ('cafeteria', '/admin/cafeteria'),
        ('rezept', recipe_path),
        ('rezeptansicht', recipe_path + '/ansicht'),
        ('menueditor', f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'),
    )
    page = _page(site, client, viewport={'width': 1440, 'height': 900}, java_script_enabled=javascript)
    try:
        for width, height in DESKTOP:
            page.set_viewport_size({'width': width, 'height': height})
            for name, path in routes:
                _goto(page, path)
                metrics = page.evaluate(SHELL_METRICS)
                assert metrics['maxWidth'] == 'none', (name, width, metrics)
                assert abs(metrics['contentWidth'] - metrics['expected']) <= 1, (name, width, metrics)
                assert not metrics['overflow'], (name, width, metrics)
                xs = [edge['x'] for edge in metrics['edges']]
                widths = [edge['width'] for edge in metrics['edges']]
                assert len(xs) >= 2, (name, path, metrics['edges'])
                assert max(xs) - min(xs) <= 1, (name, width, metrics['edges'])
                assert max(widths) - min(widths) <= 1, (name, width, metrics['edges'])
                if name == 'rezeptansicht':
                    _capture_shell(page, f'long-title-{width}x{height}-js{javascript}', title=LONG_TITLE)
                page.screenshot(
                    path=str(tmp_path / f'fullwidth-{name}-{width}x{height}.png'),
                    full_page=True,
                )
        for width, height in COMPACT:
            page.set_viewport_size({'width': width, 'height': height})
            for name, path in routes:
                _goto(page, path)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (
                    name, width, height,
                )
                if name == 'rezeptansicht':
                    _capture_shell(page, f'long-title-{width}x{height}-js{javascript}', title=LONG_TITLE)
                page.screenshot(
                    path=str(tmp_path / f'fullwidth-{name}-{width}x{height}.png'),
                    full_page=True,
                )
    finally:
        page.context.close()


def _capture_shell(page, name, *, title=None, native=False, viewport_only=False):
    metrics = page.evaluate(SHELL_METRICS)
    assert not metrics['overflow'], metrics
    expect(page.locator('.admin-area-tabs')).to_have_count(0)
    if title:
        heading = page.get_by_role('heading', level=1)
        expect(heading).to_have_text(title)
        assert heading.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
    glyphs = page.locator('.admin-sidebar use, .admin-page-header use, .admin-compact-toolbar use')
    visible = []
    for glyph in glyphs.all():
        if glyph.evaluate('el => el.closest("svg").getClientRects().length > 0'):
            assert glyph.evaluate('el => el.getBBox().width > 0'), glyph.get_attribute('href')
            assert glyph.evaluate('el => el.closest("svg").getAttribute("aria-hidden")') == 'true'
            visible.append(glyph.get_attribute('href'))
    assert visible
    for control in page.locator('.navbar-toggler:visible, .admin-nav:visible a, .admin-page-header .btn, .admin-compact-toolbar .btn').all():
        if control.is_visible():
            assert control.inner_text().strip()
            box = control.bounding_box()
            assert box and box['height'] >= 48 and box['width'] >= 44, box
    metrics.update(page.evaluate('''() => ({innerWidth, innerHeight, outerWidth, outerHeight,
        devicePixelRatio, cssZoom: getComputedStyle(document.documentElement).zoom,
        visualViewportHeight: visualViewport.height})'''))
    metrics['icons'] = visible
    metrics['capture_mode'] = 'native-viewport' if viewport_only else 'native-full-page' if native else 'full-page'
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f'{name}.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    if native and not viewport_only:
        native_full_page_capture(page, EVIDENCE / f'{name}.png')
    elif native:
        # Full-page capture lays out hidden details children in Chromium.
        # Capture the native viewport directly; Playwright clips it to CSS pixels.
        cdp = page.context.new_cdp_session(page)
        try:
            png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                'format': 'png', 'captureBeyondViewport': False,
            })['data'], validate=True)
        finally:
            cdp.detach()
        (EVIDENCE / f'{name}.png').write_bytes(png)
        assert int.from_bytes(png[16:20], 'big') == metrics['outerWidth']
        assert int.from_bytes(png[20:24], 'big') == round(metrics['visualViewportHeight'] * 2)
        after = page.evaluate(SHELL_METRICS)
        assert all(after[key] == metrics[key] for key in after)
    else:
        page.screenshot(path=str(EVIDENCE / f'{name}.png'), full_page=True)


def test_real_browser_zoom_keeps_shell_navigation_and_long_title(site, tmp_path):  # noqa: F811
    app, origin, engine, chromium = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    recipe_path = _recipe_edit_path(client)
    with TemporaryDirectory(prefix='shell-native-zoom-', dir=tmp_path) as profile:
        with chromium.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True, base_url=origin,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([_cookie(app, client, origin)])
            cdp = context.new_cdp_session(page)
            for name, route in (('week', '/admin/cafeteria'), ('view', recipe_path + '/ansicht'),
                                ('editor', recipe_path)):
                _goto(page, route)
                zoom = cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom']
                assert zoom == 2
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
                toggle = page.get_by_role('button', name='Menü', exact=True)
                toggle.focus()
                toggle.press('Enter')
                expect(page.locator('#sidebar-menu')).to_be_focused()
                page.keyboard.press('Tab')
                expect(page.locator('#sidebar-menu .admin-nav a').first).to_be_focused()
                page.keyboard.press('Escape')
                expect(toggle).to_be_focused()
                colors = toggle.evaluate('el => [getComputedStyle(el).color, getComputedStyle(el).backgroundColor]')
                assert contrast(*map(_hex, colors)) >= 4.5, colors
                glyph = toggle.locator('.navbar-toggler-icon')
                assert glyph.evaluate('el => el.getBoundingClientRect().width') >= 16
                assert contrast(_hex(glyph.evaluate('el => getComputedStyle(el).backgroundColor')),
                                _hex(colors[1])) >= 3
                _capture_shell(page, f'native-200-{name}', title=LONG_TITLE if name == 'view' else None,
                               native=True, viewport_only=name == 'editor')
                proof = cdp.send('Page.getLayoutMetrics')
                proof['focused_toggle'] = {'colors': colors, 'contrast': contrast(*map(_hex, colors))}
                (EVIDENCE / f'native-200-{name}.cdp.json').write_text(json.dumps(proof, indent=2))


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_low_height_recipe_focus_and_save_remain_reachable(site, javascript):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    recipe_path = _recipe_edit_path(client)
    page = _page(site, client, viewport={'width': 390, 'height': 430}, java_script_enabled=javascript)
    try:
        _goto(page, recipe_path)
        toolbar = page.locator('[data-sticky-form="recipe-editor"]')
        expect(toolbar).to_have_css('position', 'static')
        title = page.get_by_label('Titel', exact=True)
        title.fill('')
        save = page.get_by_role('button', name='Rezept speichern', exact=True)
        requests = []
        page.on('request', lambda request: requests.append(request.method))
        save.click()
        expect(title).to_be_focused()
        expect(title).to_be_in_viewport()
        assert title.evaluate('el => !el.validity.valid && getComputedStyle(el).outlineStyle !== "none"')
        assert not any(method == 'POST' for method in requests)
        title.fill(LONG_TITLE)
        save.scroll_into_view_if_needed()
        save.focus()
        expect(save).to_be_focused()
        expect(save).to_be_in_viewport()
        assert save.evaluate('''el => {
            const r = el.getBoundingClientRect();
            return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
        }''')
        _capture_shell(page, f'low-height-focus-js{javascript}')
    finally:
        page.context.close()


def test_shell_styles_statusbar_variants_and_contextual_subnav(site):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    try:
        _goto(page, '/admin/cafeteria/menues')
        page.locator('.page-body > .container-xl').evaluate('''container => {
            container.insertAdjacentHTML('afterbegin', `
              <dl class="admin-statusbar" aria-label="Status">
                <div class="admin-statusbar-item admin-statusbar-item--neutral"><dt class="admin-statusbar-label">Bereich</dt><dd class="admin-statusbar-value">Cafeteria</dd></div>
                <div class="admin-statusbar-item admin-statusbar-item--success"><dt class="admin-statusbar-label">Status</dt><dd class="admin-statusbar-value">Betriebsbereit</dd></div>
                <div class="admin-statusbar-item admin-statusbar-item--warning"><dt class="admin-statusbar-label">Prüfung</dt><dd class="admin-statusbar-value">Hinweis offen</dd></div>
                <div class="admin-statusbar-item admin-statusbar-item--danger"><dt class="admin-statusbar-label">Fehler</dt><dd class="admin-statusbar-value">Speichern fehlgeschlagen</dd></div>
                <div class="admin-statusbar-item admin-statusbar-item--neutral"><dt class="admin-statusbar-label">Kontext</dt><dd class="admin-statusbar-value">KW 38</dd></div>
              </dl>`);
        }''')
        statusbar = page.locator('.admin-statusbar')
        expect(statusbar).to_have_css('display', 'grid')
        expect(statusbar.locator('.admin-statusbar-item')).to_have_count(5)
        variants = ('neutral', 'success', 'warning', 'danger')
        colors = []
        for variant in variants:
            item = statusbar.locator(f'.admin-statusbar-item--{variant}').first
            colors.append(item.evaluate('el => [getComputedStyle(el).color, getComputedStyle(el).backgroundColor]'))
        assert len({tuple(color) for color in colors}) == len(variants), colors
        # The real contextual sub-navigation of the active area, not an injected stand-in.
        subitems = page.locator('.admin-nav:visible .admin-nav-subitems')
        expect(subitems).to_have_count(1)
        expect(subitems.get_by_role('link', name='Zutaten', exact=True)).to_be_visible()
        assert subitems.evaluate('el => parseFloat(getComputedStyle(el).marginLeft) > 0')
        assert subitems.evaluate('el => getComputedStyle(el).borderLeftStyle') == 'solid'

        page.set_viewport_size({'width': 360, 'height': 800})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        boxes = statusbar.locator('.admin-statusbar-item').evaluate_all(
            'items => items.map(item => item.getBoundingClientRect())'
        )
        assert all(box['width'] <= statusbar.bounding_box()['width'] + 1 for box in boxes)
    finally:
        page.context.close()


def test_public_login_print_and_signage_do_not_inherit_admin_shell(public_app, browser):  # noqa: F811
    public_app.config['LOCAL_AUTH_ENABLED'] = True
    client = public_app.test_client()
    routes = (
        ('login', '/auth/local', 390, 844),
        ('public', '/cafeteria/wochenangebot/', 390, 844),
        ('public-desktop', '/patienten/wochenplan/', 1440, 900),
        ('print', '/druck/cafeteria/woche', 1440, 900),
        ('signage', '/signage/patienten/woche', 1920, 1080),
    )
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for name, route, width, height in routes:
        response = client.get(route)
        assert response.status_code == 200
        page = _rendered_page(browser, response.get_data(as_text=True), width, height)
        try:
            expect(page.locator('.dishboard-admin, .admin-sidebar, .admin-area-tabs, [data-sticky-form]')).to_have_count(0)
            expect(page.locator('link[href*="admin-tabler.css"]')).to_have_count(0)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if name == 'print':
                page.emulate_media(media='print')
                assert page.locator('.week-menu').count() > 0
            if name == 'signage':
                expect(page.locator('a, nav, form, button, input, select, textarea')).to_have_count(0)
            page.screenshot(path=str(EVIDENCE / f'isolation-{name}.png'), full_page=True)
        finally:
            page.close()
