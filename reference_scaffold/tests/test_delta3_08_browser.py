"""UI-DELTA: menu fields remain static, native and visible before any edit click."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import WEEK, _login, _payload
from test_delta_renderer_browser import VISIBILITY
from test_menu_collection import _save, _scope

EVIDENCE = Path('/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/.claude/state/'
                'claude-session-2026-09-29/audit/DELTA/DELTA-3-08')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,coarse', [(1440, False), (1440, True), (390, False), (390, True)])
def test_static_menu_fields_keep_native_form_and_direct_actions(
    admin_app, admin_engine, live_server, browser, family, profile, width, coarse,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(description='Beschreibung A&B - 0', note='Hinweis bleibt',
                   allergens=[{'code': 'MILK', 'presence': 'may_contain'}])
    _save(admin_engine, _scope(client, admin_engine, profile), title='Menü A&B - 0', payload=payload)
    cookie = client.get_cookie('session')
    with browser.new_context(base_url=live_server, has_touch=coarse,
                             viewport={'width': width, 'height': 900},
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.method) if request.method == 'POST' else None)
        assert page.goto(f'/admin/{family}/menu?week={WEEK}&day={WEEK}&meal=LUNCH&option=MENU_1').status == 200
        page.evaluate('document.fonts.ready')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        # A red baseline captures the original state without accepting it as compliant.
        phase = 'before' if page.locator('main details').count() else 'after'
        stem = f'{phase}-{family}-{width}-{"coarse" if coarse else "fine"}'
        page.screenshot(path=str(EVIDENCE / f'{stem}.png'))
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        expect(page.locator('main details')).to_have_count(0)
        expect(page.locator('main [data-edit-row], main [data-finish-row]')).to_have_count(0)
        for selector in ['#f-desc', '#f-note', '#component-0-text', '#component-0-recipe',
                         '#allergen-mode-manual', '#origin-mode-manual', '#label-mode-manual',
                         '#accompaniment-hint', '#components-hint']:
            expect(page.locator(selector)).to_be_visible()
        expect(page.locator('#f-desc')).to_have_value('Beschreibung A&B - 0')
        expect(page.locator('#f-note')).to_have_value('Hinweis bleibt')
        expect(page.locator('#allergen-milk-presence')).to_have_value('may_contain')
        for field in ['week', 'day', 'meal', 'option', 'row_version']:
            expect(page.locator(f'form[data-menu-editor] [name="{field}"]')).to_have_count(1)
        form = page.locator('form[data-menu-editor]')
        saved = form.evaluate('f => [...new FormData(f)]')
        page.locator('#f-title').fill('Entwurf A&B - 0')
        page.locator('#component-0-text').fill('Ungespeicherte Beilage')
        expect(page.locator('[data-menu-editor-dirty-note]')).to_be_visible()
        expect(page.locator('#review [data-review-field="components"]')).to_contain_text('Blattsalat')
        expect(page.locator('#review [data-review-field="components"]')).not_to_contain_text('Ungespeicherte Beilage')
        draft = dict(form.evaluate('f => [...new FormData(f)]'))
        original = dict(saved)
        for field in ['_csrf', 'week', 'day', 'meal', 'option', 'row_version']:
            assert draft[field] == original[field]
        assert draft['title'] == 'Entwurf A&B - 0'
        assert draft['component_text'] == 'Ungespeicherte Beilage'
        controls = []
        for control in page.locator('main .btn:visible').all():
            visible = control.evaluate(VISIBILITY)
            assert bool(visible['text']) != bool(visible['icons']), visible
            controls.append({'name': control.get_attribute('aria-label'), **visible})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not posts
        page.locator('#sec-output-texts').scroll_into_view_if_needed()
        page.screenshot(path=str(EVIDENCE / f'{stem}-output-fields.png'))
        (EVIDENCE / f'{stem}.json').write_text(json.dumps({
            'browser': browser.version, 'viewport': page.viewport_size, 'coarse': coarse,
            'route': page.url, 'controls': controls,
            'field_names': [name for name, _ in saved], 'posts': len(posts),
        }, ensure_ascii=False, indent=2))
