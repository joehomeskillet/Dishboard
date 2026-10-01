"""UI-DELTA settings: visible guidance, native forms, explicit missing cost values."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

from cafeteria.branding_config import contrast
from test_admin_cost_routes import FOOD_ID, cost_layout_site  # noqa: F401
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _page, site  # noqa: F401
from test_ui_master_tokens_browser import _hex


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_settings_delta(site, tmp_path, width, height, touch):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': width, 'height': height}, has_touch=touch)
    failures = []

    def capture(label):
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        if page.locator('main details, main summary').count():
            failures.append(label + ': content accordion')
        for control in page.locator('main .ui-sem-control:visible, .brand-history-row:visible').all():
            rendered = control.evaluate(VISIBILITY)
            if rendered['pseudos'] or not (
                rendered['icons'] == 1 and not rendered['text'] or
                rendered['icons'] == 0 and bool(rendered['text'])
            ):
                failures.append((label, rendered))

    try:
        assert page.goto('/admin/design/marke').status == 200
        capture('branding')
        if not page.locator('#brand-upload-hint').is_visible():
            failures.append('D-94: upload guidance hidden')
        if page.locator('main a[href^="/admin/design/marke?revision=1"]').count() != 1:
            failures.append('R-57: duplicate active revision entry')
        original_primary = page.locator('#brand-primary').input_value()
        status_count = page.locator('.admin-page-header .admin-statusbar-item').count()
        before = page.locator('#brand-save [name="version"]').input_value()
        page.locator('#brand-name').fill('Fehlerentwurf bleibt')
        page.locator('#brand-primary').fill('#zzzzzz')
        page.locator('#brand-save').evaluate('form => { form.noValidate = true; }')
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.get_by_role('button', name='Speichern', exact=True).click()
        assert rejected.value.status == 400
        expect(page.locator('#brand-name')).to_have_value('Fehlerentwurf bleibt')
        expect(page.locator('#brand-primary')).to_have_value('#zzzzzz')
        expect(page.locator('#brand-save [name="version"]')).to_have_value(before)
        capture('branding-error')
        page.locator('#brand-primary').fill(original_primary)
        page.get_by_role('button', name='Speichern', exact=True).click()
        expect(page.locator('#brand-name')).to_have_value('Fehlerentwurf bleibt')
        expect(page.locator('.admin-page-header .admin-statusbar-item')).to_have_count(status_count)
        capture('branding-draft')
        active_link = page.locator('.brand-history-row[href*="revision=1"]')
        if active_link.get_attribute('href').endswith('#brand-more'):
            active_link.click()
            expect(page.locator('.brand-history-row[aria-current="true"]')).to_contain_text('Südhang Standard')
            assert page.url.endswith('revision=1#brand-more')
            assert page.evaluate('scrollY') > 0
            selected_link = page.locator('.brand-history-row[aria-current="true"]')
            for interaction in ('hover', 'focus'):
                getattr(selected_link, interaction)()
                colors = selected_link.evaluate('el => ({text: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor})')
                assert contrast(_hex(colors['text']), _hex(colors['background'])) >= 4.5, colors
            capture('branding-selection')
        else:
            failures.append('N-41: revision navigation loses context')
        assert page.goto('/admin/design/darstellung').status == 200
        capture('display')
        for selector in ('#admin-density-hint', '#admin-content-width-hint', '#display-reset-btn'):
            if not page.locator(selector).is_visible():
                failures.append(selector + ': hidden guidance/action')
        page.locator('#admin-density').select_option('comfortable')
        page.get_by_role('button', name='Vorschau', exact=True).click()
        expect(page.locator('#admin-density')).to_have_value('comfortable')
        capture('display-preview')
        assert page.goto('/admin/import-preview').status == 200
        capture('csv')
        if not page.get_by_text('Cafeteria und Patientenplan verwenden getrennte Formate.', exact=False).is_visible():
            failures.append('D-89: CSV format guidance hidden')
        expect(page.locator('#file')).to_have_attribute('name', 'file')
        expect(page.locator('#file')).to_have_attribute('required', '')
    finally:
        page.context.close()
    assert not failures, failures


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_cost_delta(cost_layout_site, tmp_path, width, height, touch):  # noqa: F811
    chromium, origin = cost_layout_site
    failures = []
    with chromium.new_context(viewport={'width': width, 'height': height}, has_touch=touch) as context:
        page = context.new_page()
        for state in ('empty', 'incomplete', 'complete', 'zero', 'missing'):
            assert page.goto(origin + '/__cost_layout__/' + state).status == 200
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'cost-{state}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for control in page.locator('main .ui-sem-control:visible').all():
                rendered = control.evaluate(VISIBILITY)
                assert not rendered['pseudos'], rendered
                assert (rendered['icons'] == 1 and not rendered['text']) or (
                    rendered['icons'] == 0 and bool(rendered['text'])
                ), rendered
            if page.locator('main details, main summary').count():
                failures.append(state + ': content accordion')
            if not page.locator('#menu_revision_public_id').is_visible():
                failures.append(state + ': optional revision hidden')
            if state == 'empty':
                continue
            if page.locator('.cost-lines [data-label="Zutat"]').first.inner_text().count(FOOD_ID) != 1:
                failures.append(state + ': missing visible ingredient ID')
            if state in ('incomplete', 'missing'):
                if page.locator('.cost-lines [data-label="Betrag"]').first.inner_text() != 'Nicht berechenbar':
                    failures.append(state + ': missing amount not specific')
                expect(page.locator('.cost-lines .admin-status--warning')).to_have_count(6)
            if state == 'missing' and page.locator('.cost-lines [data-label="Menge"]').first.inner_text() != 'Ohne Mengenangabe':
                failures.append('P-24: missing quantity not specific')
            if state == 'zero':
                expect(page.locator('.cost-lines [data-label="Betrag"]').first).to_have_text('0.00 CHF')
                expect(page.locator('.cost-lines [data-label="Menge"]').first).to_have_text('0 G')
    assert not failures, failures
