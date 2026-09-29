"""A shared footer must not move a native click target before activation."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from test_admin_shared_patterns_browser import shared_site  # noqa: F401
from test_admin_workflow_routes import database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(390, 844), (1440, 900)])
@pytest.mark.parametrize('coarse', [False, True], ids=['mouse', 'touch'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('target_kind', ['summary', 'submit'])
def test_footer_preserves_pointer_target(shared_site, width, height, coarse,  # noqa: F811
                                        javascript, target_kind, tmp_path):
    chromium, origin, cookie = shared_site
    with chromium.new_context(viewport={'width': width, 'height': height}, has_touch=coarse,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([cookie])
        page = context.new_page()
        assert page.goto(origin + '/__shared_patterns__').status == 200
        assert page.evaluate('matchMedia("(pointer: coarse)").matches') is coarse
        footer = page.locator('.admin-form-footer')
        expect(footer).to_have_css('position', 'sticky' if javascript else 'static')
        page.locator('#allergen-milk-presence').focus()
        expect(footer).to_have_css('position', 'static')
        target = (page.locator('#optional > summary') if target_kind == 'summary'
                  else footer.get_by_role('button', name='Speichern', exact=True))
        target.scroll_into_view_if_needed()
        before = target.bounding_box()
        x, y = before['x'] + before['width'] / 2, before['y'] + before['height'] / 2
        assert target.evaluate('(el, p) => el.contains(document.elementFromPoint(p.x, p.y))',
                               {'x': x, 'y': y})
        touch = context.new_cdp_session(page) if coarse else None
        if touch:
            touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
        else:
            page.mouse.move(x, y)
            page.mouse.down()
        try:
            # Let deferred focus/scroll work run while the physical pointer is still down.
            if javascript:
                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            assert target.bounding_box() == before
            expect(footer).to_have_css('position', 'static')
            page.screenshot(path=str(tmp_path / 'pointer-held.png'))
        finally:
            if touch:
                touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            else:
                page.mouse.up()
        if target_kind == 'summary':
            expect(page.locator('#optional')).to_have_attribute('open', '')
            expect(footer).to_have_css('position', 'sticky' if javascript else 'static')
            note = page.get_by_label('Notiz', exact=True)
            note.focus()
            expect(note).to_be_focused()
            expect(footer).to_have_css('position', 'static')
            expect(note).to_be_in_viewport(ratio=1)
            assert note.evaluate('''el => {
                const r = el.getBoundingClientRect();
                return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
            }''')
        else:
            expect(page.locator('body')).to_contain_text('"intent"')
            assert json.loads(page.locator('body').inner_text())['intent'] == ['save']


@pytest.mark.parametrize('width,height', [(390, 844), (1440, 900)])
@pytest.mark.parametrize('coarse', [False, True], ids=['mouse', 'touch'])
def test_sticky_input_focus_waits_for_pointer_end(shared_site, width, height, coarse):  # noqa: F811
    chromium, origin, cookie = shared_site
    with chromium.new_context(viewport={'width': width, 'height': height}, has_touch=coarse,
                              reduced_motion='reduce') as context:
        context.add_cookies([cookie])
        page = context.new_page()
        assert page.goto(origin + '/__shared_patterns__?content=1').status == 200
        footer = page.locator('.admin-form-footer')
        expect(footer).to_have_css('position', 'sticky')
        note = page.get_by_label('Notiz', exact=True)
        note.evaluate('el => el.scrollIntoView({block: "center"})')
        before = note.bounding_box()
        x, y = before['x'] + before['width'] / 2, before['y'] + before['height'] / 2
        touch = context.new_cdp_session(page) if coarse else None
        if touch:
            touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
        else:
            page.mouse.move(x, y)
            page.mouse.down()
        try:
            page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            assert note.bounding_box() == before
            expect(footer).to_have_css('position', 'sticky')
        finally:
            if touch:
                touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            else:
                page.mouse.up()
        expect(note).to_be_focused()
        expect(footer).to_have_css('position', 'static')
        expect(note).to_be_in_viewport(ratio=1)


@pytest.mark.parametrize('width,height', [(390, 844), (1440, 900)])
def test_touch_cancel_restores_keyboard_footer_mode(shared_site, width, height):  # noqa: F811
    chromium, origin, cookie = shared_site
    with chromium.new_context(viewport={'width': width, 'height': height}, has_touch=True,
                              reduced_motion='reduce') as context:
        context.add_cookies([cookie])
        page = context.new_page()
        assert page.goto(origin + '/__shared_patterns__?content=1').status == 200
        footer = page.locator('.admin-form-footer')
        page.get_by_label('Notiz', exact=True).focus()
        expect(footer).to_have_css('position', 'static')
        summary = page.locator('#optional > summary')
        summary.scroll_into_view_if_needed()
        box = summary.bounding_box()
        touch = context.new_cdp_session(page)
        touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
            {'x': box['x'] + box['width'] / 2, 'y': box['y'] + box['height'] / 2}]})
        touch.send('Input.dispatchTouchEvent', {'type': 'touchCancel', 'touchPoints': []})
        summary.focus()
        expect(summary).to_be_focused()
        expect(footer).to_have_css('position', 'sticky')
        summary.press('Tab')
        expect(page.get_by_label('Notiz', exact=True)).to_be_focused()
        expect(footer).to_have_css('position', 'static')
