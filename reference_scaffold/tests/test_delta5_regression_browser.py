"""DELTA-5: app-wide computed rendering, native exceptions and audit self-tests."""
from __future__ import annotations

from threading import Thread

import pytest
from flask import render_template_string
from playwright.sync_api import expect
from werkzeug.serving import make_server

from delta5_audit import PROBE, DocumentedFinding, admin_routes, write_json
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_delta_renderer_browser import PAGE, delta_site, source_revision  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory, _prepare_inventory_entities
from test_ui_semantics import semantic_app  # noqa: F401


@pytest.fixture
def regression_site(monkeypatch, tmp_path, database_engine):  # noqa: F811
    application = _factory(monkeypatch, tmp_path, database_engine)
    client, user_id = _login(application, database_engine, ['Cafeteria.Admin'])
    prepared = _prepare_inventory_entities(application, database_engine, user_id)
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cookie = client.get_cookie(application.config['SESSION_COOKIE_NAME'])
        assert cookie is not None
        yield application, f'http://127.0.0.1:{server.server_port}', cookie, prepared
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.xfail(strict=True, raises=DocumentedFinding, reason='DELTA-5 Befund B001/B002')
def test_admin_routes_exclusive_rendering(regression_site, browser, tmp_path, width, height, request):  # noqa: F811
    """DX-T10/18/22/23/29: every visual admin GET, including actual open dialogs."""
    application, base, cookie, prepared = regression_site
    rows = []
    request.addfinalizer(lambda: write_json(tmp_path / 'app-scan.json', dict(
        revision=source_revision(), browser=browser.version, viewport=[width, height], routes=rows)))
    client = application.test_client()
    client.set_cookie(cookie.key, cookie.value)
    with browser.new_context(viewport={'width': width, 'height': height},
                             has_touch=width == 390, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        for route in admin_routes(application, prepared):
            if route['waiting']:
                rows.append({**route, 'result': 'wartet auf L2'})
                continue
            if not route['paths']:
                rows.append({**route, 'result': 'nicht geprüft', 'reason': 'Fixture-Pfad fehlt'})
            for path in route['paths']:
                preflight = client.get(path)
                if preflight.status_code == 200 and (preflight.mimetype != 'text/html'
                    or preflight.headers.get('Content-Disposition', '').startswith('attachment')):
                    rows.append(dict(endpoint=route['endpoint'], path=path, result='nicht anwendbar',
                                     reason='Nichtinteraktive Datei', status=preflight.status_code))
                    continue
                response = page.goto(base + path, wait_until='load')
                entry = dict(endpoint=route['endpoint'], templates=route['templates'], path=path,
                             status=response.status, viewport=page.viewport_size, role='Cafeteria.Admin')
                if response.status != 200:
                    rows.append({**entry, 'result': 'fehlgeschlagen', 'reason': 'HTTP'})
                    continue
                if 'text/html' not in response.headers.get('content-type', ''):
                    rows.append({**entry, 'result': 'nicht anwendbar', 'reason': 'Nichtinteraktive Datei'})
                    continue
                page.evaluate('document.fonts.ready')
                states = [dict(state='default', **page.evaluate(PROBE))]
                toggle = page.locator('[data-bs-target="#sidebar-menu"]')
                if toggle.count() and toggle.is_visible():
                    toggle.click()
                    expect(page.locator('#sidebar-menu')).to_be_visible()
                    states.append(dict(state='sidebar-open', **page.evaluate(PROBE)))
                    # Restore the untouched document before probing read dialogs.
                    # Sidebar keyboard behaviour is tested separately below.
                    page.reload(wait_until='load')
                    page.evaluate('document.fonts.ready')
                targets = page.locator('[data-read-detail]').evaluate_all(
                    'els => [...new Set(els.filter(e => e.getClientRects().length)'
                    '.map(e => e.getAttribute("data-read-detail")))]')
                for target in targets:
                    trigger = page.locator('[data-read-detail]').all()
                    trigger = next((el for el in trigger
                                    if el.get_attribute('data-read-detail') == target and el.is_visible()), None)
                    if trigger is None:
                        continue
                    trigger.click()
                    dialog = page.locator('dialog[id]').all()
                    dialog = next((el for el in dialog if el.get_attribute('id') == target), None)
                    if dialog is None:
                        pytest.fail(f'No dialog for {path}: {target}')
                    expect(dialog).to_be_visible()
                    states.append(dict(state='dialog:' + target, **page.evaluate(PROBE)))
                    page.keyboard.press('Escape')
                    expect(dialog).to_be_hidden()
                findings = [{**finding, 'state': state['state']}
                            for state in states for finding in state['findings']]
                rows.append({**entry, 'result': 'fehlgeschlagen' if findings else 'bestanden',
                             'states': states, 'findings': findings})
    write_json(tmp_path / 'app-scan.json', dict(revision=source_revision(), browser=browser.version,
                                               viewport=[width, height], routes=rows))
    unchecked = [r for r in rows if r['result'] == 'nicht geprüft' or r.get('reason') == 'HTTP']
    if unchecked:
        pytest.fail(f'Unverified routes: {unchecked}')
    findings = [(r['path'], f['kind'], f['selector'], f.get('text'))
                for r in rows for f in r.get('findings', [])]
    known = {
        ('mixed', '#sidebar-menu > div:nth-child(3) > form:nth-child(3) > button:nth-child(2)', 'Abmelden'),
        ('mixed', 'body:nth-child(2) > div:nth-child(3) > aside:nth-child(1) > div:nth-child(1)'
         ' > button:nth-child(1)', 'Menü'),
    }
    unexpected = [f for f in findings if f[1:] not in known]
    if unexpected:
        pytest.fail(f'Undocumented product findings: {unexpected}')
    if findings:
        raise DocumentedFinding(findings)


@pytest.mark.parametrize('markup,kinds', [
    ('<button><svg><path/><path/></svg><span class="sr">Hidden</span></button>', []),
    ('<button><svg></svg>Save</button>', ['mixed']),
    ('<nav class="admin-segments"><a href="/section"><svg></svg>Section</a></nav>', ['mixed']),
    ('<button><svg></svg><svg></svg></button>', ['duplicate-icon']),
    ('<button class="chevron">Save</button>', ['mixed']),
    ('<button class="glyph"><svg></svg></button>', ['duplicate-icon']),
    ('<button class="label">Save</button>', []),
    ('<button><span class="background"></span>Save</button>', ['mixed']),
    ('<button><span class="navbar-toggler-icon"></span>Menu</button>', ['mixed']),
    ('<button><svg class="invisible"></svg>Save</button>', []),
    ('<details><summary>Notes</summary><p>Full text</p></details>', ['disclosure']),
    ('<aside class="admin-sidebar"><details><summary>Section</summary>Links</details></aside>', []),
    ('<aside class="admin-sidebar"><details><summary>Section</summary>'
     '<button><svg></svg>Hidden action</button></details></aside>', []),
    ('<aside class="admin-sidebar"><details open><summary>Section</summary>'
     '<button><svg></svg>Visible action</button></details></aside>', ['mixed']),
    ('<button aria-expanded="false" aria-controls="body">Notes</button><div id="body">Text</div>',
     ['disclosure']),
    ('<div role="combobox"><button aria-expanded="true" aria-controls="choices">Choose</button>'
     '<div id="choices" role="listbox">Choice</div></div>', []),
    ('<table><tr><td>—</td><td>-3</td><td>Apfel-Essig</td><td>0</td><td>false</td></tr></table>',
     ['placeholder']),
    ('<div class="admin-list-meta dash"></div>', ['placeholder']),
])
def test_visible_auditor_rejects_forbidden_output(browser, markup, kinds):  # noqa: F811
    """DX-T18/29/43: mutations must fail; SVG paths and hidden labels are not icons/text."""
    with browser.new_context() as context:
        page = context.new_page()
        page.set_content('''<style>svg {width:24px;height:24px}
            .sr {position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
            .invisible {visibility:hidden}
            .chevron::after {content:"";display:inline-block;border-top:5px solid;
                border-left:5px solid transparent;border-right:5px solid transparent}
            .glyph::before {content:"✓"} .label::after {content:" now"}
            .background {display:inline-block;width:20px;height:20px;
                background-image:url("data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\'/>")}
            .navbar-toggler-icon {display:inline-block;width:20px;height:2px;background:currentColor}
            .navbar-toggler-icon::before, .navbar-toggler-icon::after {content:"";
                display:block;width:20px;height:2px;background:currentColor}
            .dash::before {content:"—"}</style>''' + markup)
        result = page.evaluate(PROBE)
        assert sorted(f['kind'] for f in result['findings']) == sorted(kinds), result


def test_macro_caller_and_pseudo_are_independent_icon_sources(delta_site, browser):  # noqa: F811
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(delta_site[0])
        control = page.locator('#row-icon')
        control.evaluate('el => el.appendChild(el.querySelector("svg").cloneNode(true))')
        page.add_style_tag(content='#row-icon::after {content:"✓"}')
        result = page.evaluate(PROBE)
        item = next(c for c in result['controls'] if c['selector'] == '#row-icon')
        assert item['icons'] == 3 and item['text'] == '', item
        assert any(f['selector'] == '#row-icon' and f['kind'] == 'duplicate-icon'
                   for f in result['findings'])


@pytest.mark.parametrize('width', [1440, 390])
def test_sidebar_select_and_date_picker_remain_native(regression_site, browser, width):  # noqa: F811
    _, base, cookie, _ = regression_site
    with browser.new_context(viewport={'width': width, 'height': 900}, has_touch=width == 390,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + '/admin/bereiche-zeiten').status == 200
        if width == 390:
            toggle = page.locator('[data-bs-target="#sidebar-menu"]')
            toggle.click()
            expect(page.locator('#sidebar-menu')).to_be_visible()
            page.keyboard.press('Escape')
            expect(toggle).to_be_focused()
        select = page.locator('main select').first
        select.scroll_into_view_if_needed()
        values = select.locator('option:not([disabled])').evaluate_all('els => els.map(e => e.value)')
        assert len(values) >= 2
        for value in values[:2]:
            select.select_option(value)
            expect(select).to_have_value(value)
        date = page.locator('main input[type=date]').first
        date.fill('2026-10-03')
        expect(date).to_have_value('2026-10-03')
        date.press('ArrowUp')
        assert date.input_value() != '2026-10-03'
        assert date.evaluate('el => el.form !== null && el.validity.valid')
        page.goto(base + '/admin/kuechenkalender/anlass')
        time = page.locator('main input[type=time]').first
        time.fill('12:34')
        expect(time).to_have_value('12:34')
        time.press('ArrowUp')
        assert time.input_value() != '12:34'
        assert time.evaluate('el => el.form !== null && el.validity.valid')


@pytest.mark.parametrize('width', [1440, 390])
def test_english_long_renderer_content(delta_site, semantic_app, browser, width, tmp_path):  # noqa: F811
    """DX-T41: long D/P/R/B/N content and translated controls keep exclusive output."""
    semantic_app.config['UI_LOCALE'] = 'en'
    long_body = PAGE.split('<nav id="navigation">')[0] + '''
        {% from 'admin/_macros.html' import segment_switch %}
        {{ segment_switch(tabs, 'ingredients', label='Master data sections') }}
        {{ list_row(primary=name, meta=-3, status=false, markings=0,
            subtitle=name ~ ' detailed translated information',
            actions=read_detail_trigger('long-detail', 'ui.read_detail.review', name)) }}
        {{ list_row(primary=name ~ ' 2', actions=icon_button('actions.open', href='/object/2#read')) }}
        {{ icon_button('actions.save', mode='text', text='Save', aria_label=name, type='button') }}
        {% call read_detail_dialog('long-detail', 'Review notes', name) %}
        {% for n in range(80) %}<p>{{ name }}</p>{% endfor %}<p>End of long content</p>
        {% endcall %}</main></body></html>'''

    @semantic_app.get('/delta5-long')
    def long_page():
        return render_template_string(long_body, name='Very long translated content ' * 35,
            tabs=[dict(key=key, href='#' + key, label=label + ' with long translated section label')
                  for key, label in [('ingredients', 'Ingredients'), ('storage', 'Storage locations'),
                                     ('units', 'Units'), ('categories', 'Categories'), ('labels', 'Labels')]])

    with browser.new_context(viewport={'width': width, 'height': 844}) as context:
        page = context.new_page()
        page.goto(delta_site[0])
        page.locator('#review-trigger').click()
        expect(page.locator('[data-read-detail-close]')).to_have_text('Close')
        expect(page.locator('#review p').last).to_contain_text('Prüfhinweis 29')
        scan = page.evaluate(PROBE)
        assert not [f for f in scan['findings'] if f['kind'] in {'mixed', 'duplicate-icon', 'placeholder'}]
        response = page.goto(delta_site[0] + '/delta5-long')
        assert response.status == 200
        page.evaluate('document.fonts.ready')
        links = page.locator('nav[aria-label="Master data sections"] a')
        expect(links).to_have_count(5)
        boxes = [el.bounding_box() for el in links.all()]
        for link in links.all():
            link.hover()
            link.evaluate('el => el.focus({preventScroll:true})')
            for before, after in zip(boxes, [el.bounding_box() for el in links.all()], strict=True):
                assert all(abs(before[k] - after[k]) <= 1 for k in before)
        page.locator('#long-detail-trigger').click()
        expect(page.locator('[data-read-detail-close]')).to_have_text('Close')
        content = page.locator('#long-detail .ui-read-detail-content')
        content.evaluate('el => el.scrollTop = el.scrollHeight')
        page.screenshot(path=str(tmp_path / 'long-dialog.png'))
        write_json(tmp_path / 'long-dialog.json', page.evaluate('''() => ({
          viewport:{width:innerWidth,height:innerHeight},
          elements:[...document.querySelectorAll(`#long-detail, #long-detail header,
            #long-detail .ui-read-detail-content, #long-detail p:last-child`)].map(el => ({
              selector:el.className || el.tagName, rect:el.getBoundingClientRect().toJSON(),
              scrollTop:el.scrollTop, scrollHeight:el.scrollHeight, clientHeight:el.clientHeight}))
        })'''))
        content.locator('p').last.scroll_into_view_if_needed()
        expect(content.locator('p').last).to_be_in_viewport()
        scan = page.evaluate(PROBE)
        assert not scan['findings'], scan['findings']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.keyboard.press('Escape')
        page.goto(delta_site[0] + '/filters')
        page.locator('#catalog-trigger').click()
        expect(page.locator('[data-read-detail-close]')).to_have_text('Close')
        scan = page.evaluate(PROBE)
        assert not [f for f in scan['findings'] if f['kind'] in {'mixed', 'duplicate-icon', 'placeholder'}]


@pytest.mark.parametrize('width', [1440, 390])
def test_save_error_and_success_keep_exclusive_buttons(regression_site, browser, width):  # noqa: F811
    """DX-T27/40: actual native save, backend validation error and successful response."""
    _, base, cookie, _ = regression_site
    with browser.new_context(viewport={'width': width, 'height': 900}, has_touch=width == 390) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + '/admin/grundlagen/tags/neu')
        for state, name, expected_status in [('error', '   ', 400), ('success', 'DELTA5 Label', 303)]:
            page.locator('main [name=name]').fill(name)
            page.locator('main [name=code]').fill('DELTA5')
            with page.expect_response(lambda r: r.request.method == 'POST') as response:
                with page.expect_navigation(wait_until='load'):
                    page.locator('main [data-semantic="actions.save"]').click()
            assert response.value.status == expected_status
            if state == 'error':
                expect(page.locator('#master-error')).to_be_visible()
                expect(page.locator('main [name=code]')).to_have_value('DELTA5')
            else:
                expect(page.locator('main [name=name]')).to_have_value('DELTA5 Label')
            scan = page.evaluate(PROBE)
            findings = [f for f in scan['findings'] if page.locator(f['selector']).evaluate(
                'el => el.closest("main") !== null')]
            assert not findings, (state, findings)
