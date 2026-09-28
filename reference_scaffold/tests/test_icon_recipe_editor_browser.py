"""Recipe icons retain native rows, readable navigation and archive safety text."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

from cafeteria import roles
from test_master_data_browser import master_server  # noqa: F401
from test_recipe_density_browser import reference
from test_recipe_routes import (  # noqa: F401
    app_engine, b3, fields, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('state', ['active', 'readonly', 'archived'])
def test_recipe_editor_icons_preserve_native_state(
    b3, master_server, browser, monkeypatch, tmp_path, width, javascript, state,  # noqa: F811
):
    _, owner, client, _ = b3
    path = reference(client)
    if state == 'archived':
        assert client.post(path + '/status', data=fields(client, path + '/status')).status_code == 303
    elif state == 'readonly':
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = snapshot(owner)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             java_script_enabled=javascript, has_touch=width == 390,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.goto(base + path, wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(tmp_path / f'editor-{state}-{width}-js{javascript}.png'), full_page=True)
        more = page.locator('.admin-compact-toolbar .admin-compact-actions > summary')
        expect(more).to_have_text('', timeout=300)
        expect(more).to_have_accessible_name('Weitere Aktionen')
        for link in page.locator('nav[aria-label="Rezeptabschnitte"] a').all():
            assert link.inner_text().strip(), 'Section navigation must remain readable'
        form = page.locator('#recipe-editor')
        expect(form).to_have_attribute('method', 'post')
        assert form.get_attribute('action') == path
        if state != 'active':
            expect(form.locator('fieldset')).to_have_attribute('disabled', '')
            expect(page.locator('[data-recipe-toggle="step-details-0"]')).to_be_hidden()
            summary = page.locator('#step-details-0 > summary')
            expect(summary).to_have_text('')
            expect(summary).to_have_accessible_name('Details für Schritt 1')
            summary.press('Enter')
            expect(page.locator('#step-details-0')).not_to_have_attribute('open', '')
            summary.press('Space')
            expect(page.locator('[name="steps.0.instruction"]')).to_be_visible()
            expect(page.locator('[name="steps.0.instruction"]')).to_be_disabled()
            expect(page.get_by_role('button', name='Speichern', exact=True)).to_have_count(0)
            assert not posts and snapshot(owner) == before and not errors
            return

        original = form.evaluate('f => Object.fromEntries(new FormData(f))')
        assert original['_csrf'] and original['_form_context'] and original['row_version']
        for row in page.locator('[data-recipe-ingredient], [data-recipe-step]').all():
            controls = row.locator(':scope > .admin-compact-line button:visible, '
                                   ':scope > .admin-compact-line .admin-compact-actions > summary:visible, '
                                   ':scope > [data-recipe-details] > summary:visible')
            assert controls.count() <= 2
            for control in controls.all():
                expect(control).to_have_text('')
                assert control.get_attribute('aria-label')
        ingredient = page.locator('#ingredient-details-0')
        toggle = page.locator('[data-recipe-toggle="ingredient-details-0"]') if javascript else ingredient.locator(':scope > summary')
        before_toggle = form.evaluate('f => [...new FormData(f)]')
        toggle.press('Enter')
        expect(ingredient).to_have_attribute('open', '')
        toggle.press('Enter')
        expect(ingredient).not_to_have_attribute('open', '')
        assert form.evaluate('f => [...new FormData(f)]') == before_toggle
        assert not posts
        if not javascript:
            expect(page.locator('#step-details-0')).to_have_attribute('open', '')
            expect(page.locator('#step-details-0 > summary')).to_be_hidden()
            expect(page.locator('[name="steps.0.instruction"]')).to_be_visible()
        page.get_by_label('Beschreibung', exact=True).fill('Ungespeichert · vollständig erhalten')
        page.get_by_label('Mehr: Weitere Aktionen Zutat 1', exact=True).press('Enter')
        down = page.get_by_role('button', name='Zutat 1 nach unten verschieben', exact=True)
        expect(down).to_have_text('Nach unten')
        expect(page.get_by_role('button', name='Zutat 1 entfernen', exact=True)).to_have_text('Entfernen')
        with page.expect_navigation(wait_until='networkidle'):
            down.click()
        expect(page.locator('[name="ingredients.1.ingredient_text"]')).to_be_focused()
        expect(page.get_by_label('Beschreibung', exact=True)).to_have_value('Ungespeichert · vollständig erhalten')
        assert page.locator('[name="_form_context"]').input_value() == original['_form_context']
        assert page.locator('[name="row_version"]').input_value() == original['row_version']
        assert page.locator('[name="ingredients.1.line_public_id"]').input_value() == original['ingredients.0.line_public_id']
        assert len(posts) == 1 and '/admin/rezepte/formular?' in posts[0].url
        assert snapshot(owner) == before
        page.on('dialog', lambda dialog: dialog.accept())
        page.goto(base + path, wait_until='networkidle')
        more.press('Enter')
        archive = page.get_by_role('link', name='Archivieren', exact=True)
        expect(archive).to_have_text('Archivieren')
        archive.click()
        confirm = page.get_by_role('button', name='Archivieren', exact=True)
        expect(confirm).to_have_text('Archivieren')
        cancel = page.get_by_role('link', name='Abbrechen', exact=True)
        expect(cancel).to_have_text('Abbrechen')
        expect(page.get_by_text('Archivieren erhält Zutaten, Bilder und gespeicherte Stände.', exact=False)).to_be_visible()
        page.screenshot(path=str(tmp_path / f'editor-confirmation-{width}-js{javascript}.png'), full_page=True)
        cancel.press('Enter')
        expect(page.locator('#recipe-editor')).to_be_visible()
        assert len(posts) == 1 and snapshot(owner) == before and not errors
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
