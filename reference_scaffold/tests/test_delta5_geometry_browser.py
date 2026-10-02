"""DX-T35/36/42: actual D-03, D-04, N and filter transitions, retained protocols."""
from __future__ import annotations

from datetime import timedelta
from threading import Event
from time import monotonic, sleep

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import expect, sync_playwright
from flask import render_template_string

from delta5_audit import MEASURE, PROBE, DocumentedFinding, record_transition, write_json
from test_admin_workflow_routes import WEEK, _login, _payload
from test_delta_navigation_stability_browser import MEASURE as NAV_MEASURE, NAV, TABS, _differences
from test_delta_navigation_stability_browser import (  # noqa: F401
    app_engine, b3, installed_pg16, master_server, pg16, seeded_pg16,
)
from test_delta_renderer_browser import PAGE, assert_stable, delta_site, source_revision  # noqa: F401
from test_delta5_regression_browser import database_engine, regression_site  # noqa: F401
from test_master_data_routes import create
from test_menu_collection import _save, _scope
from test_rendered_ui import browser  # noqa: F401
from test_ui_semantics import semantic_app  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (1024, 768), (768, 1024),
                                        (390, 844), (1920, 1080)])
def test_all_segment_navigation_font_swap(delta_site, semantic_app, width, height, tmp_path):  # noqa: F811
    """Every shared segment consumer keeps rectangles while actual Fira HTTP requests wait."""
    groups = [
        ['Zutaten', 'Einheiten', 'Kategorien', 'Kennzeichnungen', 'Lagerorte'],
        ['Beide', 'Cafeteria', 'Patienten'],
        ['Alle lokalen Konten', 'Aktiv', 'Deaktiviert'],
        ['Aktiv', 'Mit Archivierten'],
        ['Ingredients', 'Units', 'Categories', 'Labels', 'Storage locations'],
        ['Very long translated section label with complete readable information', 'Other section'],
    ]
    with semantic_app.test_request_context():
        markup = render_template_string(PAGE.split('<nav id="navigation">')[0] + '''
            {% from 'admin/_macros.html' import segment_switch %}
            {% for labels in groups %}
            {{ segment_switch(links[loop.index0], '0', label='Segments ' ~ loop.index) }}
            {% endfor %}<p id="following">Following content</p></main></body></html>''',
            groups=groups, links=[[dict(key=str(i), href='#section-' + str(i), label=label)
                                   for i, label in enumerate(labels)] for labels in groups])
    with (sync_playwright() as pw,
          pw.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']) as font_browser,
          font_browser.new_context(viewport={'width': width, 'height': height}) as context):
        pending = []
        released = False
        context.route('**/delta6-segments', lambda route: route.fulfill(
            content_type='text/html', body=markup))
        context.route('**/*.woff2', lambda route: route.continue_() if released else pending.append(route))
        page = context.new_page()
        page.goto(delta_site[0] + '/delta6-segments', wait_until='domcontentloaded')
        expect(page.locator('.admin-segments')).to_have_count(len(groups))
        page.wait_for_function('document.fonts.status === "loading"')
        assert pending, 'No actual delayed Fira request'
        selectors = ['.admin-segments', '.admin-segments .nav-link', '#following']
        measure = '''selectors => selectors.flatMap(s => [...document.querySelectorAll(s)]
            .map(el => ({text:el.textContent.trim(), ...el.getBoundingClientRect().toJSON()})))'''
        before = page.evaluate(measure, selectors)
        released = True
        for route in pending:
            route.continue_()
        page.evaluate('document.fonts.ready')
        after = page.evaluate(measure, selectors)
        page.screenshot(path=str(tmp_path / 'segments-font-loaded.png'))
        write_json(tmp_path / 'all-segment-font-swap.json', dict(
            revision=source_revision(), viewport=[width, height], browser=font_browser.version,
            before=before, after=after))
        for left, right in zip(before, after, strict=True):
            assert all(left[axis] == right[axis] for axis in ('x', 'y', 'width', 'height')), (left, right)
        for link in page.locator('.admin-segments .nav-link').all():
            assert link.evaluate('el => el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def dialog_transition(page, trigger, selectors, purpose, tmp_path, version, javascript):
    trigger.scroll_into_view_if_needed()
    trigger.evaluate('el => el.focus({preventScroll:true})')
    samples = [dict(phase='before', measurement=page.evaluate(MEASURE, selectors))]
    dialog = page.locator('#' + trigger.get_attribute('data-read-detail'))
    try:
        trigger.press('Enter')
        expect(dialog).to_be_visible()
        if javascript:
            expect(dialog.locator('h2')).to_be_focused()
            assert dialog.evaluate('el => el.matches(":modal")')
        else:
            assert dialog.evaluate('el => el.matches(":target")')
        samples.append(dict(phase='during', measurement=page.evaluate(MEASURE, selectors)))
        expect(dialog.locator('details, summary')).to_have_count(0)
        expect(dialog.locator('[data-read-detail-close]')).to_have_count(1)
        visible = page.evaluate(PROBE)
        samples[-1]['rendering'] = visible
        assert not [f for f in visible['findings']
                    if f['kind'] in {'mixed', 'duplicate-icon', 'placeholder'}
                    and page.locator(f['selector']).evaluate(
                        '(el, id) => el.closest("dialog")?.id === id',
                        dialog.get_attribute('id'))], visible['findings']
        if purpose == 'D-03-Wochenvorgaben':
            expect(dialog).to_contain_text('Wochenvorgaben gelten für neue Ausgaben.')
            expect(dialog.locator('li')).to_have_count(14)
        if purpose == 'D-04-Prüfhinweise':
            expect(dialog).to_contain_text('Langer Hinweis & <vollständig>')
            expect(dialog.locator('.ui-read-detail-content')).to_contain_text('Ende des Hinweises')
        page.screenshot(path=str(tmp_path / (purpose + '-open.png')))
        dialog.locator('[data-read-detail-close]').click()
        expect(dialog).to_be_hidden()
        expect(trigger).to_be_in_viewport()
        if javascript:
            expect(trigger).to_be_focused()
        else:
            trigger.focus()
            expect(trigger).to_be_focused()
        samples.append(dict(phase='after', measurement=page.evaluate(MEASURE, selectors)))
        before = samples[0]['measurement']
        assert_stable(before, samples[1]['measurement'])
        after = samples[-1]['measurement']
        if javascript:
            assert_stable(before, after)
        else:
            # Decision 19:55: anchor return is intended; document-space boxes stay stable.
            adjustment = after['scroll']['y'] - before['scroll']['y']
            for name, box in before['boxes'].items():
                for axis, value in box.items():
                    adjusted = after['boxes'][name][axis] + (
                        adjustment if axis == 'y' and not before['fixed'][name] else 0)
                    assert abs(adjusted - value) <= 1, (name, axis, before, after)
            if trigger.evaluate('el => el.getBoundingClientRect().top + scrollY > innerHeight'):
                assert after['scroll']['y'] > 0
    finally:
        record_transition(tmp_path / purpose, purpose, samples, version, javascript=javascript)


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('scrollbars', ['classic', 'overlay'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_actual_dialog_and_tab_measurements(regression_site, tmp_path, width, height, scrollbars,  # noqa: F811
                                            javascript):
    application, base, cookie, _ = regression_site
    engine = application.extensions['cafeteria_db']
    client, _ = _login(application, engine, ['Cafeteria.Admin'])
    form = BeautifulSoup(client.get('/admin/grundlagen/zutaten/neu').text, 'html.parser')
    storage = form.select_one('input[name="storage_location_public_ids"][id]')['value']
    for n in range(24):
        create(client, name=f'DELTA5 lange Zutat {n:02d}', storage_location_public_ids=storage)
    for n in range(22):
        payload = _payload()
        payload.update(description='Langer Hinweis & <vollständig> ' + 'Weitere Information. ' * 55
                       + ' Ende des Hinweises', note='Warnung bleibt erhalten.')
        _save(engine, _scope(client, engine), week=WEEK + timedelta(days=7 * (n + 1)),
              title=f'DELTA5 Menü {n:02d}', payload=payload)
    args = ['--no-sandbox', '--disable-dev-shm-usage']
    if scrollbars == 'overlay':
        args.append('--enable-features=OverlayScrollbar')
    with sync_playwright() as pw:
        with pw.chromium.launch(args=args, ignore_default_args=['--hide-scrollbars']) as browser:
            with browser.new_context(viewport={'width': width, 'height': height}, has_touch=width == 390,
                                     java_script_enabled=javascript, reduced_motion='reduce') as context:
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                page = context.new_page()
                posts = []
                page.on('request', lambda r: posts.append(r.url) if r.method == 'POST' else None)
                assert page.goto(base + '/admin/bereiche-zeiten').status == 200
                page.evaluate('document.fonts.ready')
                page.evaluate('scrollTo(0, 120)')
                dialog_transition(page, page.locator('#schedule-detail-patient-trigger'),
                                  ['.page-wrapper', '.admin-sidebar', '#operations-overview',
                                   '#operations-overview tbody tr:first-child',
                                   '#operations-overview tbody tr:last-child'],
                                  'D-03-Wochenvorgaben', tmp_path, browser.version, javascript)
                assert page.goto(base + '/admin/patienten/menues').status == 200
                page.evaluate('document.fonts.ready')
                trigger = page.locator('#menu-list [data-read-detail]').nth(-2)
                trigger.scroll_into_view_if_needed()
                assert page.evaluate('scrollY') > 0
                dialog_transition(page, trigger,
                                  ['.page-wrapper', '.admin-sidebar', '.menu-toolbar',
                                   '#menu-list tbody tr:nth-last-child(2)',
                                   '#menu-list tbody tr:nth-last-child(1)'],
                                  'D-04-Prüfhinweise', tmp_path, browser.version, javascript)
                assert page.goto(base + '/admin/grundlagen').status == 200
                page.evaluate('document.fonts.ready')
                tabs = []
                before = page.evaluate(NAV_MEASURE)
                assert (before['scroll']['scrollbar'] > 0) == (scrollbars == 'classic'), before['scroll']
                try:
                    for label in TABS:
                        if label != TABS[0] or tabs:
                            page.locator(NAV).get_by_role('link', name=label, exact=True).click()
                            page.evaluate('document.fonts.ready')
                        current = page.evaluate(NAV_MEASURE)
                        tabs.append(dict(phase='selected:' + label, measurement=dict(
                            boxes={'navigation': current['nav'], 'sidebar': current['sidebar'],
                                   **{'tab:' + k: v for k, v in current['tabs'].items()}},
                            scroll={k:current['scroll'][k] for k in ('x', 'y')},
                            documentScroll=current['scroll']['top'],
                            internalScroll=current['scroll']['sidebarTop'],
                            scrollbar=current['scroll']['scrollbar'], viewport=current['viewport'])))
                        assert not _differences(before, current)
                finally:
                    record_transition(tmp_path / 'N-Stammdaten', 'N-Stammdaten', tabs,
                                      browser.version, javascript=javascript)
                trigger = page.locator('[data-read-detail][data-semantic="view.filter"]')
                dialog_transition(page, trigger, ['.page-wrapper', '.admin-sidebar', NAV,
                                  '.grundlagen-master', '.grundlagen-list .admin-list-row'],
                                  'Filterdialog', tmp_path, browser.version, javascript)
                assert not posts, posts


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_delayed_assets_and_section_data(b3, master_server, browser, monkeypatch, tmp_path,  # noqa: F811
                                         width, height):
    """DX-T37: measure actual navigation while font/sprite and section responses wait."""
    application, _, _, _ = b3
    base, cookie = master_server
    release = Event()
    font_requested = Event()
    requested = []
    static = application.view_functions['static']
    master = application.view_functions['admin.master_data_list']

    def delayed_static(filename):
        if filename.endswith(('.woff2', '.svg')):
            requested.append(filename)
            if filename.endswith('.woff2'):
                font_requested.set()
            release.wait(15)
        return static(filename=filename)

    def delayed_master(*args, **kwargs):
        sleep(0.3)
        return master(*args, **kwargs)

    monkeypatch.setitem(application.view_functions, 'static', delayed_static)
    with browser.new_context(viewport={'width': width, 'height': height}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        samples = []
        asset_differences = []
        font_usage = None
        assets = []
        page.on('response', lambda r: assets.append((r.url, r.status)) if '/static/' in r.url else None)
        try:
            page.goto(base + '/admin/grundlagen', wait_until='domcontentloaded')
            expect(page.locator(NAV)).to_be_visible()
            if not font_requested.wait(5):
                pytest.fail(f'Actual delayed font request missing: {requested}')
            page.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
            before = page.evaluate(NAV_MEASURE)
            samples.append(dict(phase='assets-pending', measurement=before))
            if not (any(p.endswith('.svg') for p in requested)
                    and any(p.endswith('.woff2') for p in requested)):
                pytest.fail(f'Actual font/sprite requests missing: {requested}')
            release.set()
            page.wait_for_load_state('networkidle')
            page.evaluate('document.fonts.ready')
            if not all(status == 200 for _, status in assets):
                pytest.fail(f'Asset request failed: {assets}')
            font_usage = page.locator(NAV).evaluate('''el => ({
                family:getComputedStyle(el).fontFamily,
                body:getComputedStyle(document.body).fontFamily,
                faces:[...document.fonts].map(f => ({family:f.family,status:f.status})),
                sheets:[...document.styleSheets].map(s => {
                  try {return {href:s.href,count:s.cssRules.length};}
                  catch(e) {return {href:s.href,error:e.name};}
                })
            })''')
            loaded = page.evaluate(NAV_MEASURE)
            samples.append(dict(phase='assets-loaded', measurement=loaded))
            asset_differences = _differences(before, loaded)
            monkeypatch.setitem(application.view_functions, 'admin.master_data_list', delayed_master)
            for label in ['Lagerorte', 'Zutaten']:
                start = monotonic()
                with page.expect_navigation():
                    page.locator(NAV).get_by_role('link', name=label, exact=True).click()
                elapsed = monotonic() - start
                if elapsed < 0.3:
                    pytest.fail(f'Section delay not observed: {elapsed}')
                page.evaluate('document.fonts.ready')
                current = page.evaluate(NAV_MEASURE)
                samples.append(dict(phase='delayed:' + label, measurement=current, seconds=elapsed))
                if _differences(loaded, current):
                    pytest.fail(f'New delayed-section geometry finding: {_differences(loaded, current)}')
            if asset_differences:
                raise DocumentedFinding(asset_differences)
        finally:
            release.set()
            write_json(tmp_path / 'delayed-assets.json', dict(
                revision=source_revision(), browser=browser.version,
                viewport={'width': width, 'height': height}, requested=requested,
                font_usage=font_usage, assets=assets, samples=samples,
                asset_differences=asset_differences))
