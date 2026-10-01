"""UI-DELTA API management and Swagger authorization; D-119 remains open."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import browser  # noqa: F401
from test_ui_korrektur_tools_browser import _api_density_client
from test_ui_master_shell_browser import _page, site  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_api_delta_contract(site, monkeypatch, tmp_path, width, height, touch):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    failures = []

    def capture(page, label):
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True,
                        mask=[page.locator('[data-api-key-prefix]'), page.locator('[data-new-key-value]')])
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        if page.locator('main details, main summary').count():
            failures.append(label + ': inline content accordion')
        for control in page.locator('main a.ui-sem-control:visible, main button.ui-sem-control:visible').all():
            result = control.evaluate(VISIBILITY)
            assert not result['pseudos'], result
            assert (result['icons'] == 1 and not result['text']) or (
                result['icons'] == 0 and bool(result['text'])
            ), result

    page = _page(site, client, viewport={'width': width, 'height': height}, has_touch=touch)
    try:
        assert page.goto('/admin/api').status == 200
        capture(page, 'empty')
        if page.locator('main a[href="#api-key-label"]').count() != 1:
            failures.append('R-35: duplicate create navigation')
    finally:
        page.context.close()

    client = _api_density_client(site, monkeypatch)
    page = _page(site, client, viewport={'width': width, 'height': height}, has_touch=touch)
    try:
        assert page.goto('/admin/api').status == 200
        capture(page, 'keys')
        for state in ('active', 'expired', 'revoked'):
            row = page.locator(f'[data-key-state="{state}"]')
            if not row.locator('[data-api-key-prefix]').is_visible():
                failures.append(state + ': hidden metadata')
            expect(row.locator('form[method="post"]')).to_have_count(int(state == 'active'))
        for selector in ('[data-api-status]', '[data-api-help]', '[data-api-versions]'):
            if not page.locator(selector).is_visible():
                failures.append(selector + ': hidden technical context')
        active = page.locator('[data-key-state="active"] form')
        expect(active).to_have_attribute('data-confirm', 'Schlüssel wirklich widerrufen?')
        expect(active.locator('[name="_csrf"]')).to_have_count(1)
        if not active.get_by_role('button', name='Schlüssel Synthetischer active Testzugang widerrufen', exact=True).is_visible():
            failures.append('D-62: revoke action is hidden')
        # Baseline capture must also reach the native error path, after recording the obsolete wrapper.
        if page.locator('#api-create > summary').count():
            page.locator('#api-create > summary').click()
        page.get_by_label('Bezeichnung', exact=True).fill('Ungespeicherter Zugang')
        page.locator('#api-key-create').evaluate('form => { form.noValidate = true; }')
        page.locator('#api-key-expires').fill('2000-01-01')
        with page.expect_response(lambda response: response.request.method == 'POST') as response:
            page.locator('#api-key-create button[type="submit"]').click()
        assert response.value.status == 400
        expect(page.get_by_label('Bezeichnung', exact=True)).to_have_value('Ungespeicherter Zugang')
        expect(page.locator('#api-key-create [role="alert"]')).to_be_visible()
        capture(page, 'error')
        assert page.goto('/api/v1/docs').status == 200
        authorize = page.locator('button.authorize').first
        expect(authorize).to_be_visible()
        page.screenshot(path=str(tmp_path / 'swagger-contract-gap.png'), full_page=True)
        # D-119 remains measured; B-67 uses Swagger's supported plugin wrapper.
        (tmp_path / 'swagger-contract-gap.json').write_text(json.dumps({
            'authorize': authorize.evaluate(VISIBILITY),
            'operation_toggles': page.locator('.opblock-control-arrow, .expand-operation').count(),
        }, indent=2))
        assert authorize.evaluate(VISIBILITY)['icons'] == 0
        authorize.click()
        popup = page.locator('.dialog-ux')
        expect(popup).to_be_visible()
        popup.locator('input').fill('synthetic-browser-value')
        popup.get_by_role('button', name='Apply credentials', exact=True).click()
        expect(popup.get_by_role('button', name='Remove authorization', exact=True)).to_be_visible()
        popup.get_by_role('button', name='Close', exact=True).click()
        expect(authorize).to_have_text('Authorize (authorized)')
        assert authorize.evaluate(VISIBILITY)['icons'] == 0
        authorize.click()
        popup.get_by_role('button', name='Remove authorization', exact=True).click()
        popup.get_by_role('button', name='Close', exact=True).click()
        expect(authorize).to_have_text('Authorize')
    finally:
        page.context.close()
    assert not failures, failures
