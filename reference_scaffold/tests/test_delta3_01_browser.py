"""UI-DELTA D-03/DX-T01/06/08/22/42 on actual operations pages."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_delta_renderer_browser import VISIBILITY, assert_stable

EVIDENCE = Path('/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/.claude/state/'
                'claude-session-2026-09-29/audit/DELTA/DELTA-3-01')
GEOMETRY = '''() => {
  const boxes = {};
  for (const selector of ['.page-wrapper', '.navbar-vertical', '#operations-overview',
                          '#operations-overview tbody tr:first-child',
                          '#operations-overview tbody tr:last-child']) {
    const r = document.querySelector(selector).getBoundingClientRect();
    boxes[selector] = {x:r.x, y:r.y, width:r.width, height:r.height};
  }
  return {boxes, scroll: {x:scrollX, y:scrollY},
          documentScroll:document.scrollingElement.scrollTop,
          internalScroll:document.querySelector('.page-wrapper').scrollTop,
          scrollbar:innerWidth-document.documentElement.clientWidth};
}'''


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('coarse', [False, True])
def test_operations_read_dialog_and_static_fields(
    browser, live_server, admin_app, admin_engine, width, coarse,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    with browser.new_context(base_url=live_server, has_touch=coarse,
                             viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda req: posts.append(req.method) if req.method == 'POST' else None)
        assert page.goto('/admin/bereiche-zeiten').status == 200
        page.evaluate('document.fonts.ready')
        phase = os.environ.get('DELTA_CAPTURE_PHASE', 'after')
        stem = f'{phase}-{width}-{"coarse" if coarse else "fine"}'
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        page.screenshot(path=str(EVIDENCE / f'{stem}.png'))
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        expect(page.locator('main details')).to_have_count(0)
        expect(page.locator('#staff_guest-slot_1_LUNCH_notice')).to_be_visible()
        expect(page.locator('#weekend-editor input[type=checkbox]')).to_be_visible()
        expect(page.locator('#saved-exceptions')).to_contain_text('Keine gespeicherten Ausnahmen')
        expect(page.locator('a[href="#exception-load"]')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        fields = page.locator('#schedule-staff_guest')
        fields.locator('[name=slot_1_LUNCH_notice]').fill('Hinweis A&B - unverändert')
        form_state = fields.evaluate('f => [...new FormData(f)]')
        measurements = []
        for profile, count in [('staff_guest', 7), ('patient', 14)]:
            trigger = page.locator(f'#schedule-detail-{profile}-trigger')
            dialog = page.locator(f'#schedule-detail-{profile}')
            trigger.scroll_into_view_if_needed()
            trigger.focus()
            before = page.evaluate(GEOMETRY)
            visible = trigger.evaluate(VISIBILITY)
            assert visible['icons'] == 1 and visible['text'] == '', visible
            assert trigger.bounding_box()['height'] == (44 if coarse else 36), trigger.evaluate('''el => ({
                coarse:matchMedia('(pointer: coarse)').matches, height:getComputedStyle(el).height,
                token:getComputedStyle(el).getPropertyValue('--app-control-min-height')})''')
            trigger.press('Enter')
            expect(dialog).to_be_visible()
            expect(dialog.locator('h2')).to_be_focused()
            expect(dialog.locator('li')).to_have_count(count)
            expect(dialog).to_contain_text('Wochenvorgaben gelten für neue Ausgaben.')
            expect(dialog).to_contain_text('Zeiten nicht eingetragen')
            during = page.evaluate(GEOMETRY)
            assert_stable(before, during)
            close = dialog.locator('[data-read-detail-close]')
            expect(close).to_have_count(1)
            assert close.evaluate(VISIBILITY)['icons'] == 0
            assert close.evaluate(VISIBILITY)['text'] == 'Schliessen'
            page.screenshot(path=str(EVIDENCE / f'{stem}-{profile}-dialog.png'))
            page.keyboard.press('Escape')
            expect(dialog).to_be_hidden()
            expect(trigger).to_be_focused()
            after = page.evaluate(GEOMETRY)
            assert_stable(before, after)
            assert before['scroll'] == during['scroll'] == after['scroll']
            measurements.append({'profile': profile, 'before': before, 'during': during, 'after': after})
        assert fields.evaluate('f => [...new FormData(f)]') == form_state
        assert not posts
        template = Path(__file__).resolve().parents[1] / 'cafeteria/templates/admin/operations.html'
        (EVIDENCE / f'{stem}.json').write_text(json.dumps({
            'viewport': page.viewport_size, 'coarse': coarse, 'browser': browser.version,
            'template_sha256': hashlib.sha256(template.read_bytes()).hexdigest(),
            'measurements': measurements,
        }, ensure_ascii=False, indent=2))
