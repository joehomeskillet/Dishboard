"""D22: direct right-edge actions keep tooltips inside the viewport."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from test_ui_korrektur_tools_browser import _api_density_client, _goto
from test_ui_master_shell_browser import _page, site
from test_admin_workflow_routes import database_engine
from test_rendered_ui import browser

__all__ = ['site', 'database_engine', 'browser']


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('coarse', [False, True], ids=['fine', 'coarse'])
@pytest.mark.parametrize('trigger', ['hover', 'focus'])
def test_api_tooltips_stay_inside_viewport(site, monkeypatch, tmp_path, width, coarse, trigger):
    client = _api_density_client(site, monkeypatch)
    page = _page(site, client, has_touch=coarse,
                 viewport={'width': width, 'height': 844 if width == 390 else 900})
    measurements = []
    errors, posts = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
    try:
        _goto(page, '/admin/api')
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        expect(page.locator('#api-technical > summary')).to_have_count(0)
        expect(page.locator('[data-api-help]')).to_be_visible()
        for key_state in ('active', 'expired', 'revoked'):
            key_row = page.locator(f'[data-key-state="{key_state}"]')
            label = f'Synthetischer {key_state} Testzugang'
            group = key_row.get_by_role('group', name=f'Aktionen für {label}', exact=True)
            expect(group).to_have_count(int(key_state == 'active'))
            expect(key_row.locator('.ui-sem-actions, [data-semantic="actions.more"]')).to_have_count(0)
            metadata = key_row.locator('.admin-api-key-details')
            expect(metadata.locator('summary')).to_have_count(0)
            expect(metadata).to_be_visible()
            expect(key_row.locator('[data-api-key-prefix]')).to_be_visible()
            expect(key_row.locator('form[action$="/revoke"]')).to_have_count(int(key_state == 'active'))
        row = page.locator('[data-key-state="active"]')
        revoke = row.locator('form[action$="/revoke"]')
        revoke_action = revoke.locator('button[type="submit"]')
        expect(revoke_action).to_be_visible()
        expect(revoke_action).to_have_text('Widerrufen')
        expect(revoke_action.locator('svg')).to_have_count(0)
        expect(revoke_action).to_have_accessible_name('Schlüssel Synthetischer active Testzugang widerrufen')

        def capture(stage):
            state = page.evaluate('''() => ({
                width: innerWidth, height: innerHeight, scrollX,
                clientWidth: document.documentElement.clientWidth,
                viewportRight: Math.min(innerWidth, document.documentElement.getBoundingClientRect().right),
                body: document.body.getBoundingClientRect().toJSON(),
                scrollWidth: document.documentElement.scrollWidth,
                tips: [...document.querySelectorAll('.ui-sem-tooltip.show')].map(tip => {
                    const control = [...document.querySelectorAll('[data-ui-tooltip]')]
                        .find(el => (el.getAttribute('aria-describedby') || '').split(/\\s+/).includes(tip.id));
                    const instance = control && window.tabler.Tooltip.getInstance(control);
                    const inner = getComputedStyle(tip.querySelector('.tooltip-inner'));
                    return {box: tip.getBoundingClientRect().toJSON(), text: tip.textContent,
                        control: control?.getBoundingClientRect().toJSON(),
                        placement: instance?._popper?.state.placement,
                        rects: instance?._popper?.state.rects,
                        overflow: instance?._popper?.state.modifiersData.preventOverflow,
                        arrow: instance?._popper?.state.modifiersData.arrow,
                        styles: instance?._popper?.state.styles.popper,
                        modifiers: instance?._popper?.state.options.modifiers.map(({name, options}) => ({name, options})),
                        boundary: instance?._config.boundary,
                        container: tip.parentElement.tagName,
                        maxWidth: inner.maxWidth, whiteSpace: inner.whiteSpace,
                        overflowWrap: inner.overflowWrap};
                })
            })''')
            measurements.append({'stage': stage, **state})
            (tmp_path / 'geometry.json').write_text(json.dumps(measurements, indent=2))
            page.screenshot(path=str(tmp_path / f'{stage}.png'), full_page=False,
                            mask=[row.locator('[data-api-key-prefix]')])
            assert state['tips'], state
            assert state['scrollWidth'] <= state['width'] + 1, state
            for tip in state['tips']:
                box = tip['box']
                assert 0 <= box['left'] < box['right'] <= state['width'], state
                assert box['right'] <= state['viewportRight'], state
                assert 0 <= box['top'] < box['bottom'] <= state['height'], state

        def explain(control):
            page.mouse.move(0, 0)
            control.evaluate('el => el.blur()')
            if trigger == 'hover':
                control.hover()
            else:
                control.focus()
                expect(control).to_be_focused()
            tip = page.get_by_role('tooltip', name=control.get_attribute('aria-label'), exact=True)
            expect(tip).to_be_visible()
            assert tip.get_attribute('id') in control.get_attribute('aria-describedby').split()
            return tip

        # UI-DELTA: metadata needs no control; tooltip geometry belongs to the direct action.
        explain(revoke_action)
        page.evaluate('window.scrollTo(0, scrollY)')
        capture('action-first-focus')
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        if trigger == 'focus':
            expect(revoke_action).to_be_focused()
        else:
            expect(revoke_action).not_to_be_focused()
        assert not revoke_action.get_attribute('aria-describedby')
        explain(revoke_action)
        capture('row-action')
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        if trigger == 'focus':
            expect(revoke_action).to_be_focused()
        else:
            expect(revoke_action).not_to_be_focused()
        expect(revoke.locator('details, summary')).to_have_count(0)
        assert not revoke_action.get_attribute('aria-describedby')
        assert not posts and not errors
    finally:
        page.context.close()
