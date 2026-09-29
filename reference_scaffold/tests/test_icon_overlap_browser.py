"""D23: real HTTP hit areas, including touch, native forms and sticky focus."""
from __future__ import annotations

import json
from datetime import date
from threading import Thread

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from test_admin_workflow_routes import database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import (
    MENU, _factory, _invalid_action, _prepare_inventory_entities, _role_clients,
)


@pytest.fixture
def overlap_site(monkeypatch, tmp_path, database_engine):  # noqa: F811
    from cafeteria.admin import calendar_event_routes, calendar_routes

    monkeypatch.setattr(calendar_routes, 'effective_today', lambda: date(2026, 9, 29))
    monkeypatch.setattr(calendar_event_routes, 'effective_today', lambda: date(2026, 9, 29))
    app = _factory(monkeypatch, tmp_path, database_engine)
    clients, user = _role_clients(app, database_engine)
    prepared = _prepare_inventory_entities(app, database_engine, user)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    cookie = clients['Cafeteria.Admin'].get_cookie(app.config['SESSION_COOKIE_NAME'])
    try:
        yield origin, {'name': cookie.key, 'value': cookie.value, 'url': origin}, prepared
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


PAIR = """([a, b]) => {
    const rect = e => {
        const r = e.getBoundingClientRect();
        return {x:r.x, y:r.y, right:r.right, bottom:r.bottom, width:r.width, height:r.height};
    };
    const owns = (e, x, y) => e.contains(document.elementFromPoint(x, y));
    const ra = rect(a), rb = rect(b);
    const left = Math.max(ra.x, rb.x), right = Math.min(ra.right, rb.right);
    const top = Math.max(ra.y, rb.y), bottom = Math.min(ra.bottom, rb.bottom);
    const area = Math.max(0, right-left) * Math.max(0, bottom-top);
    const x = (left+right)/2, y = (top+bottom)/2;
    return {a:ra, b:rb, area, scroll:scrollY,
        centers:[owns(a,ra.x+ra.width/2,ra.y+ra.height/2),
                 owns(b,rb.x+rb.width/2,rb.y+rb.height/2)],
        intersection: area ? [owns(a,x,y), owns(b,x,y)] : null};
}"""


def _settle(page):
    # Browser callbacks do not run in a No-JS context. Give focusin's rendering
    # frame time to run when JS is enabled; the following hit assertion is final.
    page.wait_for_timeout(50)


def _separate(page, first, second):
    first.scroll_into_view_if_needed()
    _settle(page)
    result = page.evaluate(PAIR, [first.element_handle(), second.element_handle()])
    assert result['area'] == 0, result
    assert all(result['centers']), result
    return result


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('coarse', [False, True])
def test_sticky_and_swagger_controls_do_not_cover_other_targets(
    overlap_site, browser, tmp_path, width, height, coarse,  # noqa: F811
):
    origin, cookie, prepared = overlap_site
    findings = {}
    with browser.new_context(base_url=origin, viewport={'width': width, 'height': height},
                             has_touch=coarse, is_mobile=coarse, reduced_motion='reduce') as context:
        context.add_cookies([cookie])
        page = context.new_page()
        for route in [MENU, MENU.replace('cafeteria', 'patienten'), '/admin/kuechenkalender/anlass',
                      prepared['endpoint_paths']['admin.kitchen_event_edit'], '/api/v1/docs']:
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            if route == '/api/v1/docs':
                page.locator('.opblock-summary').first.wait_for()
            _settle(page)
            findings[route] = page.evaluate('''() => {
                const controls=[...document.querySelectorAll(
                    'main form input:not([type=hidden]), main form button, main form summary, '
                    +'main form a, .opblock-summary button')].filter(e =>
                        e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}));
                const failures=[];
                const max=Math.max(0,document.documentElement.scrollHeight-innerHeight);
                for(let y=0;y<=max;y+=20) {
                    scrollTo(0,y);
                    const boxes=controls.map(e=>e.getBoundingClientRect());
                    for(let a=0;a<controls.length;a++) for(let b=a+1;b<controls.length;b++) {
                        if(controls[a].contains(controls[b])||controls[b].contains(controls[a])) continue;
                        const ra=boxes[a],rb=boxes[b];
                        const left=Math.max(ra.left,rb.left,0),right=Math.min(ra.right,rb.right,innerWidth);
                        const top=Math.max(ra.top,rb.top,0),bottom=Math.min(ra.bottom,rb.bottom,innerHeight);
                        if(right<=left||bottom<=top) continue;
                        const hit=document.elementFromPoint((left+right)/2,(top+bottom)/2);
                        if(!controls[a].contains(hit)&&!controls[b].contains(hit)) continue;
                        failures.push({y,first:controls[a].getAttribute('aria-label')||controls[a].id||controls[a].textContent.trim().slice(0,60),
                            second:controls[b].getAttribute('aria-label')||controls[b].id||controls[b].textContent.trim().slice(0,60),
                            area:(right-left)*(bottom-top),hit:hit.tagName});
                        return failures;
                    }
                }
                return failures;
            }''')
        (tmp_path / 'covering-targets.json').write_text(json.dumps(findings, indent=2))
    assert not any(findings.values()), findings


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844), (1024, 768)])
@pytest.mark.parametrize('coarse', [False, True])
@pytest.mark.parametrize('javascript', [False, True])
def test_filters_tabs_and_calendar_have_distinct_hit_areas(
    overlap_site, browser, tmp_path, width, height, coarse, javascript,  # noqa: F811
):
    origin, cookie, _ = overlap_site
    evidence, failures = [], []
    with browser.new_context(base_url=origin, viewport={'width': width, 'height': height},
                             has_touch=coarse, is_mobile=coarse,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([cookie])
        page = context.new_page()
        for route, selector in [('/admin/einkaufslisten', '.shopping-filter a'),
                                ('/admin/vorlagen', '.output-area-tabs a')]:
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            assert page.evaluate("matchMedia('(pointer: coarse)').matches") == coarse
            pair = page.locator(selector)
            try:
                evidence.append(_separate(page, pair.nth(0), pair.nth(1)))
            except AssertionError as error:
                failures.append((route, str(error)))
            page.screenshot(path=str(tmp_path / f'{selector[1:].split()[0]}.png'))
        for profile in ('cafeteria', 'patient'):
            assert page.goto(f'/admin/kuechenkalender?year=2026&month=9&profiles={profile}').status == 200
            page.evaluate('document.fonts.ready')
            head = page.locator('.kitchen-cal-grid .kitchen-cal-day-head').filter(has_text='29').first
            if width >= 1024:
                plan = head.locator('..').locator('.kitchen-cal-plan')
                next_day = head.locator('xpath=ancestor::td/following-sibling::td[1]').locator('.kitchen-cal-day-head')
                try:
                    evidence.append(_separate(page, plan, next_day))
                except AssertionError as error:
                    failures.append((f'calendar/{profile}', str(error)))
            else:
                row = page.locator('.kitchen-cal-list-head').filter(has_text='29. September')
                evidence.append(_separate(page, row.locator('h2 a'), row.locator('.kitchen-cal-plan')))
            page.screenshot(path=str(tmp_path / f'calendar-{profile}.png'))
    (tmp_path / 'hit-areas.json').write_text(json.dumps({'evidence': evidence, 'failures': failures}, indent=2))
    assert not failures, failures


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('coarse', [False, True])
@pytest.mark.parametrize('javascript', [False, True])
def test_sticky_forms_keep_focused_targets_uncovered(
    overlap_site, browser, tmp_path, width, height, coarse, javascript,  # noqa: F811
):
    origin, cookie, prepared = overlap_site
    records = []
    with browser.new_context(base_url=origin, viewport={'width': width, 'height': height},
                             has_touch=coarse, is_mobile=coarse,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([cookie])
        page = context.new_page()
        routes = [MENU, MENU.replace('cafeteria', 'patienten'),
                  '/admin/kuechenkalender/anlass', prepared['endpoint_paths']['admin.kitchen_event_edit']]
        for index, route in enumerate(routes):
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            assert page.evaluate("matchMedia('(pointer: coarse)').matches") == coarse
            targets = page.locator('form[data-menu-editor] summary:visible, '
                                   'form[data-menu-editor] input:not([type=hidden]):visible, '
                                   '#kitchen-event-form summary:visible, #kitchen-event-form input:not([type=hidden]):visible')
            assert targets.count() > 0
            for target in targets.all():
                target.evaluate('e => { e.blur(); const r=e.getBoundingClientRect(); '
                                'scrollTo(0,scrollY+r.top-innerHeight+35); }')
                target.focus()
                _settle(page)
                record = target.evaluate('''e => {
                    const r=e.getBoundingClientRect();
                    return {name:e.id || e.textContent.trim().slice(0,80), scroll:scrollY,
                        hit:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)),
                        focused:document.activeElement===e};
                }''')
                records.append({'route': route, **record})
                assert record['focused'] and record['hit'], record
            page.screenshot(path=str(tmp_path / f'focus-{index}.png'))
        # Real invalid POST preserves the editor and its focus/hit contract.
        if javascript:
            page.goto(MENU)
            _invalid_action(prepared['invalid_cases'][0])(page)
            field = page.locator('[name=internal_chf]')
            field.focus()
            _settle(page)
            expect(field).to_be_focused()
            assert field.evaluate('e => { const r=e.getBoundingClientRect(); '
                                  'return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)); }')
    (tmp_path / 'focus.json').write_text(json.dumps(records, indent=2))
