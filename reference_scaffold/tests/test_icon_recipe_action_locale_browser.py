"""Localized recipe primary actions keep their role-specific native GET targets."""
from __future__ import annotations

import base64
import json
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store as store, roles
from test_master_data_db import signed_in
from test_recipe_images_browser import recipe_server  # noqa: F401
from test_recipe_revision_routes import (  # noqa: F401
    a3, app_engine, b3, edit, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import snapshot, target
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('state', ['writer', 'reader', 'archived'])
@pytest.mark.parametrize(('javascript', 'width', 'coarse'), [(True, 1440, False), (False, 390, True)])
def test_recipe_primary_action_uses_locale_and_native_target(
    a3, recipe_server, browser, monkeypatch, tmp_path, locale, state, javascript, width, coarse,  # noqa: F811
):
    app, owner, _, actor, public_id = a3
    app.config['UI_LOCALE'] = locale
    title = 'Suppe "A" & Kräuter'
    edit(a3, title=title)
    if state == 'archived':
        engine = app.extensions['cafeteria_db']
        with signed_in(engine, actor):
            row = store.get_recipe(engine, public_id)
            store.set_recipe_active(engine, actor, target(row), active=False,
                                    expected_location_id=store.get_location(engine))
    elif state == 'reader':
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = snapshot(owner)
    base, cookie = recipe_server
    editable = state == 'writer'
    action = 'edit' if editable else 'open'
    expected_name = (f'{title} bearbeiten' if editable else f'{title} öffnen') if locale == 'de' else (
        f'Edit {title}' if editable else f'Open {title}')
    destination = f'/admin/rezepte/{public_id}' + ('' if editable else '/ansicht')
    metrics = []
    with browser.new_context(viewport={'width': width, 'height': 844}, has_touch=coarse,
                             java_script_enabled=javascript, reduced_motion='reduce',
                             service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        posts, errors = [], []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        cdp = context.new_cdp_session(page)

        def capture(stage):
            pointer = page.evaluate('''() => ({
                coarse: matchMedia('(pointer: coarse), (any-pointer: coarse)').matches,
                fine: matchMedia('(pointer: fine)').matches, touch: navigator.maxTouchPoints,
                width: innerWidth, height: innerHeight, dpr: devicePixelRatio,
                overflow: document.documentElement.scrollWidth > innerWidth + 1,
                tooltips: [...document.querySelectorAll('[role="tooltip"]')].map(el => el.textContent),
            })''')
            assert pointer['coarse'] is coarse and pointer['fine'] is not coarse
            assert (pointer['touch'] > 0) is coarse and not pointer['overflow']
            image = cdp.send('Page.captureScreenshot', {
                'format': 'png', 'fromSurface': True, 'captureBeyondViewport': False,
            })
            raw = base64.b64decode(image['data'])
            assert raw[:8] == b'\x89PNG\r\n\x1a\n'
            assert int.from_bytes(raw[16:20], 'big') == round(pointer['width'] * pointer['dpr'])
            assert int.from_bytes(raw[20:24], 'big') == round(pointer['height'] * pointer['dpr'])
            (tmp_path / f'{stage}.png').write_bytes(raw)
            after = page.evaluate('''() => ({
                coarse: matchMedia('(pointer: coarse), (any-pointer: coarse)').matches,
                fine: matchMedia('(pointer: fine)').matches, touch: navigator.maxTouchPoints,
                tooltips: [...document.querySelectorAll('[role="tooltip"]')].map(el => el.textContent),
            })''')
            assert after == {key: pointer[key] for key in after}
            metrics.append({'stage': stage, **pointer, 'pointer_after': after})
            (tmp_path / 'metrics.json').write_text(json.dumps(metrics, indent=2))

        listing = '/admin/rezepte' + ('?archived=1' if state == 'archived' else '')
        response = page.goto(base + listing, wait_until='networkidle')
        assert response.status == 200
        row = page.locator('.recipe-row').filter(has=page.get_by_text(title, exact=True))
        expect(row).to_have_count(1)
        primary = row.locator(f'.admin-row-actions > a[data-semantic="actions.{action}"]')
        expect(primary).to_have_count(1)
        expect(primary).to_have_attribute('href', destination)
        expect(primary).to_have_attribute('data-semantic', f'actions.{action}')
        expect(primary).to_have_text('')
        expect(primary.locator('svg')).to_have_attribute('aria-hidden', 'true')
        expected_icon = 'edit' if editable else 'arrow-right'
        assert primary.locator('use').get_attribute('href').endswith(f'#tabler-{expected_icon}')
        glyph = primary.locator('use').evaluate('el => { const b=el.getBBox(); return [b.width,b.height]; }')
        assert all(value > 0 for value in glyph)
        size = 44 if coarse else 36
        box = primary.bounding_box()
        assert box is not None and box['width'] == size and box['height'] == size, box
        assert primary.get_attribute('title') is None
        assert row.locator('b').count() == 0  # Recipe metacharacters stay text, never markup.
        assert row.locator('.admin-row-actions > a[data-semantic="actions.edit"]').count() == int(editable)
        expect(row.locator('[data-semantic="actions.open"]')).to_be_visible()
        expect(row.locator('[data-semantic="actions.more"]')).to_have_count(0)
        expect(row.locator('[data-semantic="actions.snapshot"]')).to_have_count(int(editable))
        page.mouse.move(0, 0)
        for _ in range(60):
            page.keyboard.press('Tab')
            if primary.evaluate('el => el === document.activeElement'):
                break
        expect(primary).to_be_focused()
        assert primary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        if javascript:
            expect(page.get_by_role('tooltip')).to_have_text([expected_name])
            expect(page.get_by_role('tooltip')).to_be_visible()
        else:
            expect(page.get_by_role('tooltip')).to_have_count(0)
        capture('primary-focused')
        expect(primary).to_have_accessible_name(expected_name)
        expect(primary).to_have_attribute('data-ui-tooltip', expected_name)
        if javascript:
            expect(page.get_by_role('tooltip', name=expected_name, exact=True)).to_be_visible()
            primary.press('Escape')
            expect(page.get_by_role('tooltip')).to_have_count(0)
            expect(primary).to_be_focused()
        assert snapshot(owner) == before and not posts
        with page.expect_navigation(wait_until='networkidle') as navigation:
            primary.press('Enter')
        assert navigation.value.status == 200
        assert urlsplit(page.url).path == destination
        if editable:
            expect(page.locator('#recipe-editor')).to_be_visible()
            expect(page.locator('#recipe-editor input[name="title"]')).to_have_value(title)
        else:
            expect(page.locator('#recipe-editor')).to_have_count(0)
            expect(page.locator('#recipe-document')).to_be_visible()
            expect(page.locator('.page-header-subtitle')).to_have_text(title)
        capture('native-destination')
        assert not posts and not errors
    assert snapshot(owner) == before
