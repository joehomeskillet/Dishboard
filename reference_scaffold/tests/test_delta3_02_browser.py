"""UI-DELTA menu notes: read-only dialogs, direct navigation, stable geometry."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login, _payload
from test_delta_renderer_browser import VISIBILITY, assert_stable
from test_menu_collection import _save, _scope

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/delta3/DELTA-3-02'
GEOMETRY = '''() => {
  const boxes = {};
  for (const selector of ['.page-wrapper', '.navbar-vertical', '.menu-toolbar',
                          '#menu-list', '#menu-review-summary']) {
    const r = document.querySelector(selector).getBoundingClientRect();
    boxes[selector] = {x:r.x, y:r.y, width:r.width, height:r.height};
  }
  return {boxes, scroll:{x:scrollX,y:scrollY}, documentScroll:document.scrollingElement.scrollTop,
          internalScroll:document.querySelector('.page-wrapper').scrollTop};
}'''


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('coarse', [False, True])
def test_menu_notes_dialog_navigation_and_no_duplicate_actions(
    admin_app, admin_engine, live_server, browser, width, coarse,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    for family, profile in [('cafeteria', 'staff_guest'), ('patienten', 'patient')]:
        payload = _payload(staff=profile == 'staff_guest')
        payload.update(description='Beschreibung <b>kein HTML</b>', note='Hinweis & Vorsicht')
        _save(admin_engine, _scope(client, admin_engine, profile), title='Menü <&> - 0', payload=payload)
    cookie = client.get_cookie('session')
    with browser.new_context(base_url=live_server, has_touch=coarse,
                             viewport={'width': width, 'height': 900},
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.method) if request.method == 'POST' else None)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        measurements = []
        for family in ['cafeteria', 'patienten']:
            assert page.goto(f'/admin/{family}/menues').status == 200
            page.evaluate('document.fonts.ready')
            stem = f'{os.environ.get("DELTA_CAPTURE_PHASE", "after")}-{family}-{width}-{"coarse" if coarse else "fine"}'
            page.screenshot(path=str(EVIDENCE / f'{stem}.png'))
            assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
            expect(page.locator('main details')).to_have_count(0)
            toolbar = page.locator('.menu-toolbar').bounding_box()
            assert page.locator('#menu-review-summary').bounding_box()['y'] >= toolbar['y'] + toolbar['height']
            for view in ['list', 'cards']:
                page.get_by_role('tab', name='Liste' if view == 'list' else 'Karten', exact=True).click()
                trigger = page.locator(f'#menu-{view} [data-read-detail]')
                dialog = page.locator('#' + trigger.get_attribute('data-read-detail'))
                trigger.scroll_into_view_if_needed()
                trigger.focus()
                before = page.evaluate(GEOMETRY)
                assert trigger.evaluate(VISIBILITY)['text'] == ''
                assert trigger.evaluate(VISIBILITY)['icons'] == 1
                assert trigger.bounding_box()['height'] >= (44 if coarse else 36)
                trigger.press('Enter')
                expect(dialog).to_be_visible()
                expect(dialog.locator('h2')).to_be_focused()
                expect(dialog).to_contain_text('Beschreibung <b>kein HTML</b>')
                expect(dialog.locator('b')).to_have_count(0)
                expect(dialog).to_contain_text('Hinweis & Vorsicht')
                during = page.evaluate(GEOMETRY)
                assert_stable(before, during)
                close = dialog.locator('[data-read-detail-close]')
                expect(close).to_have_count(1)
                assert close.evaluate(VISIBILITY)['icons'] == 0
                assert close.evaluate(VISIBILITY)['text'] == 'Schliessen'
                page.screenshot(path=str(EVIDENCE / f'{stem}-{view}-dialog.png'))
                page.keyboard.press('Escape')
                expect(trigger).to_be_focused()
                after = page.evaluate(GEOMETRY)
                assert_stable(before, after)
                assert 'Menü <&> - 0' in trigger.get_attribute('aria-label')
                assert 'Beschreibung' in trigger.get_attribute('aria-label')
                assert 'Menü <&> - 0' in trigger.get_attribute('data-ui-tooltip')
                measurements.append({'family': family, 'view': view, 'before': before,
                                     'during': during, 'after': after})
            page.goto(f'/admin/{family}/menues?q=KeinTreffer')
            expect(page.locator('main [data-semantic="view.reset"]')).to_have_count(1)
            expect(page.locator('main [data-semantic="navigation.weekplan"]')).to_have_count(1)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not posts
        (EVIDENCE / f'measurements-{width}-{coarse}.json').write_text(json.dumps({
            'browser': browser.version, 'viewport': page.viewport_size, 'coarse': coarse,
            'measurements': measurements}, ensure_ascii=False, indent=2))
