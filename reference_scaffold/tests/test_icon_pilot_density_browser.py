"""Measure real pilot lists with ten records; keep density failures actionable."""
from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria.component_catalog_store import create_component, update_component
from prepared_food_fixtures import create_food, create_recipe, execute
from test_admin_ux_browser import live_server
from test_admin_workflow_routes import _login, _scope
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server']

PILOTS = [
    ('components-cafeteria', '/admin/cafeteria/komponenten', '.component-row'),
    ('components-patienten', '/admin/patienten/komponenten', '.component-row'),
    ('recipes', '/admin/rezepte', '.recipe-row'),
]
MEASURE = '''({rows, component}) => {
    const box = node => node.getBoundingClientRect().toJSON();
    const style = node => {
        const s = getComputedStyle(node);
        return {fontSize: s.fontSize, fontWeight: s.fontWeight, lineHeight: s.lineHeight,
                fontFamily: s.fontFamily, color: s.color};
    };
    const main = box(document.querySelector('main'));
    const records = [...document.querySelectorAll(rows)].map(row => {
        const primary = row.querySelector(component ? 'a.admin-list-primary' : '.admin-list-primary');
        const secondary = row.querySelector('th .admin-list-secondary');
        const meta = row.querySelector('.admin-list-meta');
        const contentBoxes = [...row.children].map(box);
        const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (!node.textContent.trim() || node.parentElement.closest('.visually-hidden, [hidden]')) continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            contentBoxes.push(...[...range.getClientRects()].filter(r => r.width && r.height).map(r => r.toJSON()));
        }
        return {box: box(row), contentBoxes, display: getComputedStyle(row).display,
                computedHeight: getComputedStyle(row).height,
                primary: {text: primary.textContent.trim(), box: box(primary), ...style(primary)},
                secondary: secondary ? {text: secondary.textContent.trim(), box: box(secondary), ...style(secondary)} : null,
                meta: meta ? {text: meta.textContent.trim(), box: box(meta), ...style(meta)} : null};
    });
    const regions = [...document.querySelectorAll('.page-header, .admin-statusbar, form[role=search], #component-result-count, table thead')]
        .map(node => ({name: node.id || node.className || node.tagName, box: box(node),
                      marginTop: getComputedStyle(node).marginTop,
                      marginBottom: getComputedStyle(node).marginBottom}));
    const heightRules = [];
    const first = document.querySelector(rows);
    const readRules = (rules, source) => [...rules].forEach(rule => {
        if (rule instanceof CSSMediaRule && !matchMedia(rule.conditionText).matches) return;
        if (rule instanceof CSSStyleRule && rule.style.height && first.matches(rule.selectorText)) {
            heightRules.push({source, selector: rule.selectorText, height: rule.style.height});
        }
        if (rule.cssRules) readRules(rule.cssRules, source);
    });
    [...document.styleSheets].forEach(sheet => readRules(sheet.cssRules, sheet.href));
    const overflowingRows = records.flatMap((row, index) => row.contentBoxes.some(r =>
        r.top < row.box.top - 1 || r.bottom > row.box.bottom + 1
        || (records[index + 1] && r.bottom > records[index + 1].box.top + 1)) ? [index + 1] : []);
    return {body: box(document.body), main, rows: records, regions, heightRules, overflowingRows,
            viewport: {width: innerWidth, height: innerHeight, outerWidth, devicePixelRatio},
            scrollWidth: document.documentElement.scrollWidth, scrollY,
            firstOffset: records[0].box.top - main.top,
            completeVisible: records.filter((row, index) => !overflowingRows.includes(index + 1)
                && row.box.top >= Math.max(0, main.top) - 1 && row.box.bottom <= innerHeight + 1).length,
            naturalTwoLineNames: records.filter(row => row.secondary
                && row.secondary.box.top >= row.primary.box.bottom - 1).length};
}'''


def _seed_records(app, engine, component):
    _, actor = _login(app, engine, ['Cafeteria.Admin'])
    scope = _scope(engine, actor, 'staff_guest')
    ids = {'actor': actor, 'authz': scope.expected_authz_version, 'location': scope.location_id}
    storage = execute(engine, '''SELECT cafeteria.create_storage_location_v21(
        :actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))''', ids,
        {'code': 'DENSITY', 'name': 'Pilotlager', 'sort_order': 1})
    ids['storage'] = storage['public_id']
    names = []
    for index in range(1, 11):
        food = create_food(engine, ids, f'Gemüse {index:02d}')
        name = f'Pilot {"Baustein" if component else "Rezept"} {index:02d}'
        names.append(name)
        if component:
            row = create_component(engine, scope, 'side', name, 'CH', 'common', [], [])
            update_component(engine, scope, row['public_id'], {
                'category': 'side', 'name': name, 'origin_country_code': 'CH',
                'label_codes': [], 'allergens': [], 'food_public_id': food['public_id'],
            }, row['row_version'])
        else:
            create_recipe(engine, ids, [food], name=name, quantity='100')
    return names


@pytest.mark.parametrize('slug,path,row_selector', PILOTS)
@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Editor'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('width,zoom', [(1440, 1), (390, 1), (1440, 2)])
def test_pilot_density_real_records_filtering_and_native_forms(
    admin_app, admin_engine, browser, live_server, tmp_path,
    slug, path, row_selector, role, javascript, width, zoom,
):
    component = slug.startswith('components')
    names = _seed_records(admin_app, admin_engine, component)
    client, _ = _login(admin_app, admin_engine, [role])
    if role == 'Cafeteria.Editor':
        assert client.get('/admin/benutzer').status_code == 403
    options = dict(base_url=live_server, java_script_enabled=javascript, reduced_motion='reduce')
    if zoom == 2:
        context = browser.browser_type.launch_persistent_context(
            str(tmp_path / 'chrome-profile'), channel='chromium', headless=True, no_viewport=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'], **options,
        )
        page = context.pages[0]
    else:
        context = browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844}, **options)
        page = context.new_page()
    try:
        if zoom == 2:
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
        cookie = client.get_cookie('session')
        assert cookie is not None
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
        writes = []
        page.on('request', lambda request: writes.append(request.method) if request.method not in ('GET', 'HEAD') else None)
        response = page.goto(path, wait_until='networkidle')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        expect(page.locator(row_selector)).to_have_count(10)
        metrics = page.evaluate(MEASURE, {'rows': row_selector, 'component': component})
        metrics.update(slug=slug, role=role, javascript=javascript, zoom=zoom,
                       recipeTwoLineCoverage='not applicable: actual template has name and a separate yield column' if not component else None)
        metrics['headerDensityFinding'] = metrics['firstOffset'] > 220 if width == 1440 and zoom == 1 else None
        name = f'{slug}-{role.rsplit(".", 1)[1]}-{width}-{zoom}x-js{javascript}'
        if zoom == 2:
            cdp = context.new_cdp_session(page)
            try:
                proof = cdp.send('Page.getLayoutMetrics')
                assert proof['cssVisualViewport']['zoom'] == 2
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
                metrics['nativeZoom'] = proof
                png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                    'format': 'png', 'captureBeyondViewport': False,
                })['data'], validate=True)
                (tmp_path / f'{name}.png').write_bytes(png)
                assert int.from_bytes(png[16:20], 'big') == 1440
            finally:
                cdp.detach()
        else:
            page.screenshot(path=str(tmp_path / f'{name}.png'))
        (tmp_path / f'{name}.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
        assert metrics['scrollY'] == 0
        assert metrics['scrollWidth'] <= metrics['viewport']['width'] + 1, metrics
        for row in metrics['rows']:
            assert (row['primary']['fontSize'], row['primary']['fontWeight']) == ('14px', '600')
            if row['secondary']:
                assert (row['secondary']['fontSize'], row['secondary']['fontWeight']) == ('13px', '400')
            if row['meta']:
                assert (row['meta']['fontSize'], row['meta']['fontWeight']) == ('13px', '400')
        if component:
            assert metrics['naturalTwoLineNames'] == 10, metrics
        # Exercise native GET filtering and POST form reachability before the density assertion.
        search = page.get_by_role('search')
        expect(search).to_have_attribute('method', 'get')
        expect(search).to_have_attribute('action', path)
        field = search.locator('[name="q"]' if component else '[name="text"]')
        field.fill(names[-1])
        search.get_by_role('button', name='Suchen', exact=True).press('Enter')
        expect(page.locator(row_selector)).to_have_count(1)
        expect(page.locator(row_selector)).to_contain_text(names[-1])
        assert parse_qs(urlsplit(page.url).query)['q' if component else 'text'] == [names[-1]]
        search.get_by_role('link', name='Zurücksetzen', exact=True).click()
        expect(page.locator(row_selector)).to_have_count(10)
        primary_selector = 'a.admin-list-primary' if component else '.admin-list-primary'
        first_name = page.locator(row_selector).first.locator(primary_selector).inner_text()
        edit = page.locator(row_selector).first.locator('[data-semantic="actions.edit"]')
        expect(edit).to_have_count(1)
        edit.focus()
        expect(edit).to_be_focused()
        edit.press('Enter')
        form = page.locator('#component-form' if component else '#recipe-editor')
        expect(form).to_be_visible()
        expect(form).to_have_attribute('method', 'post')
        expect(form.locator('input[name="_csrf"]')).to_have_count(1)
        expect(form.locator('[name="name"]' if component else '[name="title"]')).to_have_value(first_name.strip())
        assert not writes
        assert not metrics['overflowingRows'], f'Cells or visible text escape rows: {metrics["overflowingRows"]}'
        if width == 1440 and zoom == 1:
            assert metrics['completeVisible'] >= 8, metrics
            assert metrics['firstOffset'] <= 220, metrics
    finally:
        context.close()


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_long_component_names_remain_contained_at_mobile_and_native_zoom(
    admin_app, admin_engine, browser, live_server, tmp_path, family,
):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, actor, 'staff_guest' if family == 'cafeteria' else 'patient')
    names = [f'{prefix} Karottengemüse mit Kräutersauce, gebratenen Kartoffeln und saisonalen Beilagen'
             for prefix in ('A', 'B')]
    for name in names:
        create_component(admin_engine, scope, 'side', name, 'CH', 'common', ['VEGAN'], [])
    cookie = client.get_cookie('session')
    assert cookie is not None
    for javascript in (True, False):
        for width, zoom in ((360, 1), (390, 1), (1440, 2)):
            options = dict(base_url=live_server, java_script_enabled=javascript, reduced_motion='reduce')
            if zoom == 2:
                context = browser.browser_type.launch_persistent_context(
                    str(tmp_path / f'long-profile-{javascript}'), channel='chromium', headless=True,
                    no_viewport=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'], **options,
                )
                page = context.pages[0]
            else:
                context = browser.new_context(viewport={'width': width, 'height': 844}, **options)
                page = context.new_page()
            try:
                if zoom == 2:
                    page.goto('chrome://settings/appearance')
                    page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
                    assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
                context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                assert page.goto(f'/admin/{family}/komponenten', wait_until='networkidle').status == 200
                page.evaluate('document.fonts.ready')
                expect(page.locator('.component-row')).to_have_count(2)
                measured = page.evaluate(MEASURE, {'rows': '.component-row', 'component': True})
                assert [row['primary']['text'] for row in measured['rows']] == names
                assert not measured['overflowingRows'], measured
                assert measured['scrollWidth'] <= measured['viewport']['width'] + 1
                for row in measured['rows']:
                    assert (row['primary']['fontSize'], row['primary']['fontWeight']) == ('14px', '600')
                for category in page.locator('.category').all():
                    expect(category).to_have_attribute('data-label', 'Kategorie')
                for usage in page.locator('.usage').all():
                    expect(usage).to_have_attribute('data-label', 'Verwendung')
                name = f'long-components-{family}-{width}-{zoom}x-js{javascript}'
                if zoom == 2:
                    cdp = context.new_cdp_session(page)
                    try:
                        measured['nativeZoom'] = cdp.send('Page.getLayoutMetrics')
                        assert measured['nativeZoom']['cssVisualViewport']['zoom'] == 2
                        assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                        png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                            'format': 'png', 'captureBeyondViewport': False,
                        })['data'], validate=True)
                        (tmp_path / f'{name}.png').write_bytes(png)
                        assert int.from_bytes(png[16:20], 'big') == 1440
                    finally:
                        cdp.detach()
                else:
                    page.screenshot(path=str(tmp_path / f'{name}.png'), full_page=True)
                (tmp_path / f'{name}.json').write_text(json.dumps(measured, ensure_ascii=False, indent=2))
            finally:
                context.close()
