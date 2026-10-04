"""Sidebar brand, readable navigation and real-route visual evidence."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_nav_browser import _page, nav_site  # noqa: F401
from test_admin_workflow_routes import database_engine  # noqa: F401

EVIDENCE = Path('/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/'
                '.claude/state/claude-session-2026-09-29/audit/SIDEBAR')
ROUTE = '/admin/cafeteria?week=2026-09-28'


def _load(page):
    response = page.goto(ROUTE, wait_until='networkidle')
    assert response.status == 200
    page.evaluate('document.fonts.ready')


def _metrics(page):
    return page.evaluate('''() => {
      const rect = el => { const r = el.getBoundingClientRect();
        return {x:r.x, y:r.y, width:r.width, height:r.height}; };
      const logo = document.querySelector('.admin-logo');
      const image = logo.getBoundingClientRect();
      const sidebar = document.querySelector('.admin-sidebar');
      const style = getComputedStyle(sidebar);
      return {viewport:{width:innerWidth, height:innerHeight},
        locale:document.documentElement.lang, sidebar:rect(sidebar),
        main:rect(document.querySelector('main')), logo:{...rect(logo),
          naturalWidth:logo.naturalWidth, naturalHeight:logo.naturalHeight,
          fit:getComputedStyle(logo).objectFit,
          painted:document.elementFromPoint(image.x + image.width / 2,
            image.y + image.height / 2) === logo},
        minimumInset:parseFloat(style.getPropertyValue('--app-space-3')),
        overflow:document.documentElement.scrollWidth > innerWidth,
      };
    }''')


def _record(page, directory, name):
    # DOM nodes are deliberately not serialized; record only measurable text/boxes.
    metrics = _metrics(page)
    metrics['labels'] = page.locator('.admin-nav:visible .nav-link-title').evaluate_all('''els =>
      els.map(el => ({text:el.textContent.trim(), width:el.clientWidth,
        scrollWidth:el.scrollWidth, height:el.getBoundingClientRect().height,
        whiteSpace:getComputedStyle(el).whiteSpace,
        textOverflow:getComputedStyle(el).textOverflow}))''')
    page.screenshot(path=str(directory / f'{name}.png'))
    (directory / f'{name}.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')


def test_sidebar_reference_matrix(nav_site):  # noqa: F811 - imported pytest fixture
    app = nav_site[0]
    original_locale = app.config['UI_LOCALE']
    try:
        for locale in ('de', 'en'):
            app.config['UI_LOCALE'] = locale
            for role in ('Cafeteria.Admin', 'Cafeteria.Editor'):
                page = _page(nav_site, role=role)
                try:
                    _load(page)
                    phase = 'after' if page.locator('.admin-brand-mark').count() else 'before'
                    directory = EVIDENCE / phase
                    directory.mkdir(parents=True, exist_ok=True)
                    name = f'{role.split(".")[-1].lower()}-{locale}'
                    for width, height in ((1440, 900), (1280, 800)):
                        page.set_viewport_size({'width': width, 'height': height})
                        _record(page, directory, f'{name}-{width}x{height}-expanded')
                    page.set_viewport_size({'width': 1440, 'height': 900})
                    page.locator('[data-admin-nav-toggle]').click()
                    _record(page, directory, f'{name}-1440x900-collapsed')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    _record(page, directory, f'{name}-390x844-closed')
                    page.get_by_role('button', name='Menü', exact=True).click()
                    expect(page.locator('#sidebar-menu')).to_be_visible()
                    _record(page, directory, f'{name}-390x844-open')
                finally:
                    page.context.close()
    finally:
        app.config['UI_LOCALE'] = original_locale


@pytest.mark.parametrize('viewport', [(1440, 900), (1280, 800), (1024, 768),
                                      (768, 1024), (390, 844), (1920, 1080)])
@pytest.mark.parametrize('touch', [False, True])
def test_sidebar_brand_geometry_and_navigation(nav_site, viewport, touch):  # noqa: F811
    page = _page(nav_site, has_touch=touch)
    try:
        page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
        _load(page)
        logo = page.locator('.admin-logo')
        expect(logo).to_have_js_property('complete', True)
        metrics = _metrics(page)
        image = metrics['logo']
        assert image['naturalWidth'] > 0 and image['naturalHeight'] > 0
        ratio = image['naturalWidth'] / image['naturalHeight']
        assert abs(image['width'] / image['height'] / ratio - 1) <= .01, image
        sidebar = metrics['sidebar']
        assert image['x'] - sidebar['x'] >= metrics['minimumInset'], metrics
        assert sidebar['x'] + sidebar['width'] - image['x'] - image['width'] >= metrics['minimumInset']
        assert image['y'] - sidebar['y'] >= metrics['minimumInset'], metrics
        assert image['fit'] == 'contain'
        assert not metrics['overflow'], metrics
        if viewport[0] < 992:
            toggle = page.get_by_role('button', name='Menü', exact=True)
            assert toggle.inner_text().strip() == ''
            expect(toggle.locator('.navbar-toggler-icon')).to_have_count(1)
            toggle.click()
            expect(page.locator('.admin-brand > span')).to_be_visible()
            assert _metrics(page)['logo']['painted']
            assert _metrics(page)['main']['y'] == metrics['main']['y']
            before = page.locator('.admin-brand').bounding_box()
            page.locator('#sidebar-menu .admin-nav').evaluate('el => el.scrollTop = el.scrollHeight')
            assert page.locator('.admin-brand').bounding_box() == before
            assert _metrics(page)['logo']['painted']
            page.locator('#sidebar-menu .admin-nav').evaluate('el => el.scrollTop = 0')
        nav = page.locator('.admin-nav:visible')
        labels = nav.locator('.nav-link-title').evaluate_all('''els => els.map(el => ({
          text:el.textContent, width:el.clientWidth, scrollWidth:el.scrollWidth,
          overflow:getComputedStyle(el).textOverflow, whiteSpace:getComputedStyle(el).whiteSpace
        }))''')
        assert all(row['width'] >= row['scrollWidth'] and row['overflow'] != 'ellipsis'
                   and row['whiteSpace'] == 'normal' for row in labels), labels
        parent = nav.locator('.admin-nav-area.active > .nav-link')
        child = nav.locator('.admin-nav-subitems [aria-current="page"]')
        expect(child).to_have_text('Cafeteria')
        assert child.bounding_box()['x'] > parent.bounding_box()['x']
        assert child.evaluate('el => getComputedStyle(el).boxShadow') != 'none'
        heights = nav.locator('.admin-nav-subitems a').evaluate_all(
            'els => els.map(el => el.getBoundingClientRect().height)')
        assert all(height >= (44 if touch else 36) for height in heights), heights
        logout = page.locator('.admin-logout-btn:visible')
        expect(logout).to_have_text('Abmelden')
        expect(logout.locator('svg')).to_have_count(0)
        assert logout.evaluate("el => el.form.method === 'post' && !!el.form.querySelector('[name=_csrf]')")
        child.focus()
        page.keyboard.press('Tab')
        page.keyboard.press('Shift+Tab')
        assert float(child.evaluate('el => getComputedStyle(el).outlineWidth')[:-2]) >= 2
        if viewport[0] < 992:
            page.keyboard.press('Escape')
            expect(toggle).to_be_focused()
    finally:
        page.context.close()


def test_sidebar_nojs_mobile_brand_and_navigation(nav_site):  # noqa: F811
    page = _page(nav_site, java_script_enabled=False, has_touch=True)
    try:
        page.set_viewport_size({'width': 390, 'height': 844})
        response = page.goto(ROUTE)
        assert response.status == 200
        summary = page.locator('.admin-nojs-nav > summary')
        expect(page.locator('button.navbar-toggler')).to_be_hidden()
        expect(summary).to_be_visible()
        summary.click()
        expect(page.locator('.admin-brand > span')).to_be_visible()
        assert _metrics(page)['logo']['painted']
        before = page.locator('.admin-brand').bounding_box()
        page.locator('.admin-nojs-nav .admin-nav').evaluate('el => el.scrollTop = el.scrollHeight')
        assert page.locator('.admin-brand').bounding_box() == before
        assert _metrics(page)['logo']['painted']
        page.locator('.admin-nojs-nav .admin-nav').evaluate('el => el.scrollTop = 0')
        expect(page.locator('.admin-nojs-nav [aria-current="page"]')).to_have_text('Cafeteria')
        expect(page.locator('.admin-nojs-nav .admin-logout-btn')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        directory = EVIDENCE / ('after' if page.locator('.admin-brand-mark').count() else 'before')
        directory.mkdir(parents=True, exist_ok=True)
        _record(page, directory, 'admin-de-390x844-nojs-open')
    finally:
        page.context.close()


def test_sidebar_restricted_role_and_collapsed_brand(nav_site):  # noqa: F811
    settings = {}
    for role in ('Cafeteria.Admin', 'Cafeteria.Editor'):
        page = _page(nav_site, role=role)
        try:
            _load(page)
            page.locator('[data-admin-nav-toggle]').click()
            image = _metrics(page)['logo']
            assert image['height'] >= 18 and image['painted'], image
            assert abs(image['width'] / image['height'] /
                       (image['naturalWidth'] / image['naturalHeight']) - 1) <= .01
            brand = page.locator('.admin-brand-mark').bounding_box()
            assert 0 < brand['x'] < brand['x'] + brand['width'] < 128
            page.locator('#sidebar-menu .admin-nav-area > .nav-link').last.click()
            flyout = page.locator('#admin-nav-flyout')
            expect(flyout).to_be_visible()
            settings[role] = flyout.locator('a').all_inner_texts()
            assert flyout.locator('.nav-link-title').evaluate_all(
                'els => els.every(el => el.scrollWidth <= el.clientWidth)')
            directory = EVIDENCE / 'after'
            directory.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(directory / f'{role.split(".")[-1].lower()}-settings-flyout.png'))
        finally:
            page.context.close()
    assert len(settings['Cafeteria.Editor']) < len(settings['Cafeteria.Admin'])
    assert [label.strip() for label in settings['Cafeteria.Editor']] == ['Daten importieren', 'Schnittstellen']


def test_sidebar_delayed_fonts_and_logo_keep_geometry(nav_site):  # noqa: F811
    page = _page(nav_site)
    try:
        pending = []
        released = False
        def hold(route):
            if released:
                route.continue_()
            else:
                pending.append(route)

        page.route('**/*.woff2', hold)
        page.route('**/suedhang-logo*.png', hold)
        page.goto(ROUTE, wait_until='domcontentloaded')
        page.wait_for_function('document.fonts.status === "loading"')
        selectors = '.admin-brand, .admin-brand-mark, #sidebar-menu .nav-link, main'
        measure = '''els => els.map(el => {const r = el.getBoundingClientRect();
          return [r.x, r.y, r.width, el.tagName === 'MAIN' ? 0 : r.height];})'''
        before = page.locator(selectors).evaluate_all(measure)
        assert any(route.request.url.endswith('.woff2') for route in pending)
        assert any('suedhang-logo' in route.request.url for route in pending)
        released = True
        for route in pending:
            route.continue_()
        page.evaluate('''async () => {
          await document.fonts.ready;
          const logo = document.querySelector('.admin-logo');
          await logo.decode();
        }''')
        after = page.locator(selectors).evaluate_all(measure)
        assert len(before) == len(after)
        assert all(abs(a - b) <= 1 for first, second in zip(before, after)
                   for a, b in zip(first, second)), (before, after)
    finally:
        page.context.close()
