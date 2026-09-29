"""Recipe icons retain native rows, readable navigation and archive safety text."""
from __future__ import annotations

import json
from io import BytesIO

import pytest
from PIL import Image
from playwright.sync_api import expect

from cafeteria import roles
from test_master_data_browser import master_server  # noqa: F401
from test_recipe_density_browser import reference
from test_recipe_images_browser import a3, recipe_server  # noqa: F401
from test_recipe_revision_routes import upload
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
        assert page.evaluate("matchMedia('(any-pointer: coarse)').matches") is (width == 390)
        (tmp_path / 'capture.json').write_text(json.dumps({
            'route': path, 'viewport': page.viewport_size, 'role': 'Cafeteria.Publisher',
            'state': state, 'javascript': javascript, 'coarse': width == 390,
            'capabilities': ['draft.read'] if state == 'readonly' else 'standard Publisher',
        }, indent=2))
        page.screenshot(path=str(tmp_path / f'editor-{state}-{width}-js{javascript}.png'), full_page=False)
        assert page.evaluate("matchMedia('(any-pointer: coarse)').matches") is (width == 390)
        expect(page.locator('[data-semantic="actions.more"]')).to_have_count(0)
        for link in page.locator('.admin-compact-toolbar .admin-row-actions a').all():
            expect(link).to_be_visible()
            expect(link).to_have_text('')
            assert link.get_attribute('aria-label')
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
            controls = row.locator(':scope > .admin-compact-line .admin-row-actions button')
            assert controls.count() == 4
            for control in controls.all():
                expect(control).to_be_visible()
                expect(control).to_have_text('')
                assert control.get_attribute('aria-label')
                box = control.bounding_box()
                assert box['width'] >= (44 if width == 390 else 36), control.evaluate('''el => ({
                    html: el.outerHTML, size: getComputedStyle(el).getPropertyValue('--ui-control-size'),
                    coarse: matchMedia('(any-pointer: coarse)').matches,
                    fine: matchMedia('(pointer: fine)').matches})''')
                assert box['height'] >= (44 if width == 390 else 36)
                assert box['x'] >= 0 and box['x'] + box['width'] <= width
        for name in ('Zutat 1 nach oben verschieben', 'Zutat 4 nach unten verschieben',
                     'Schritt 1 nach oben verschieben', 'Schritt 2 nach unten verschieben'):
            blocked = page.get_by_role('button', name=name, exact=True)
            expect(blocked).to_be_disabled()
            wrapper = blocked.locator('..')
            wrapper.press('Enter')
            expect(wrapper).to_be_focused()
            description = page.locator('#' + wrapper.get_attribute('aria-describedby'))
            assert description.inner_text().strip()
        assert not posts and snapshot(owner) == before
        page.keyboard.press('Escape')
        for section in ('ingredients', 'steps'):
            page.locator('#' + section + '-heading').scroll_into_view_if_needed()
            page.screenshot(path=str(tmp_path / f'editor-{section}-{width}-js{javascript}.png'),
                            full_page=False)
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
        page.get_by_label('Titel', exact=True).fill('')
        down = page.get_by_role('button', name='Zutat 1 nach unten verschieben', exact=True)
        expect(down).to_be_visible()
        expect(down).to_have_text('')
        expect(page.get_by_role('button', name='Zutat 1 entfernen', exact=True)).to_have_text('')
        with page.expect_navigation(wait_until='networkidle'):
            down.click()
        expect(page.locator('[name="ingredients.1.ingredient_text"]')).to_be_focused()
        expect(page.get_by_label('Beschreibung', exact=True)).to_have_value('Ungespeichert · vollständig erhalten')
        assert page.locator('[name="_form_context"]').input_value() == original['_form_context']
        assert page.locator('[name="row_version"]').input_value() == original['row_version']
        assert page.locator('[name="ingredients.1.line_public_id"]').input_value() == original['ingredients.0.line_public_id']
        assert len(posts) == 1 and '/admin/rezepte/formular?' in posts[0].url
        assert snapshot(owner) == before
        # Row commands bypass required-title validation and never persist the draft.
        for action in ('Zutat 2 nach oben verschieben', 'Zutat 1 davor einfügen', 'Zutat 1 entfernen',
                       'Schritt 1 nach unten verschieben', 'Schritt 2 nach oben verschieben',
                       'Schritt 1 davor einfügen', 'Schritt 1 entfernen'):
            with page.expect_navigation(wait_until='networkidle'):
                page.get_by_role('button', name=action, exact=True).press('Enter')
            expect(page.get_by_label('Titel', exact=True)).to_have_value('')
            expect(page.get_by_label('Beschreibung', exact=True)).to_have_value('Ungespeichert · vollständig erhalten')
            assert page.locator('[name="_form_context"]').input_value() == original['_form_context']
            assert page.locator('[name="row_version"]').input_value() == original['row_version']
            assert snapshot(owner) == before
        restored = form.evaluate('f => Object.fromEntries(new FormData(f))')
        for key, value in original.items():
            if key.startswith(('ingredients.', 'steps.')):
                assert restored[key] == value, key
        assert len(posts) == 8 and all('/admin/rezepte/formular?' in post.url for post in posts)
        page.on('dialog', lambda dialog: dialog.accept())
        page.goto(base + path, wait_until='networkidle')
        archive = page.locator('.admin-compact-toolbar [data-semantic="actions.archive"]')
        expect(archive).to_be_visible()
        expect(archive).to_have_text('')
        archive.click()
        confirm = page.get_by_role('button', name='Archivieren', exact=True)
        expect(confirm).to_have_text('Archivieren')
        cancel = page.get_by_role('link', name='Abbrechen', exact=True)
        expect(cancel).to_have_text('Abbrechen')
        expect(page.get_by_text('Archivieren erhält Zutaten, Bilder und gespeicherte Stände.', exact=False)).to_be_visible()
        page.screenshot(path=str(tmp_path / f'editor-confirmation-{width}-js{javascript}.png'), full_page=True)
        cancel.press('Enter')
        expect(page.locator('#recipe-editor')).to_be_visible()
        assert len(posts) == 8 and snapshot(owner) == before and not errors
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
def test_recipe_image_row_actions_keep_unsaved_metadata(
    a3, recipe_server, browser, tmp_path, width, javascript,  # noqa: F811
):
    _, owner, client, _, public_id = a3
    path = f'/admin/rezepte/{public_id}'
    assert upload(client, path + '/bilder').status_code == 303
    second = BytesIO()
    Image.new('RGB', (24, 18), 'blue').save(second, format='PNG')
    assert upload(client, path + '/bilder', content=second.getvalue()).status_code == 303
    before = snapshot(owner)
    base, cookie = recipe_server
    with browser.new_context(
        viewport={'width': width, 'height': 844 if width == 390 else 900},
        has_touch=width == 390, java_script_enabled=javascript, reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        assert page.goto(base + path).status == 200
        form = page.locator('#recipe-editor')
        original = form.evaluate('f => Object.fromEntries(new FormData(f))')
        page.get_by_label('Titel', exact=True).fill('')
        page.locator('[name="images.0.caption"]').fill('Ungespeicherte Bildunterschrift')
        expect(page.get_by_role('button', name='Bild 1 nach oben verschieben', exact=True)).to_be_disabled()
        expect(page.get_by_role('button', name='Bild 2 nach unten verschieben', exact=True)).to_be_disabled()
        expect(page.get_by_role('button', name='Bild 1 davor einfügen', exact=True)).to_have_count(0)
        for name, destination in [('Bild 1 nach unten verschieben', 1), ('Bild 2 nach oben verschieben', 0)]:
            control = page.get_by_role('button', name=name, exact=True)
            expect(control).to_be_visible()
            expect(control).to_have_text('')
            with page.expect_navigation(wait_until='networkidle'):
                control.press('Enter')
            assert page.locator(f'[name="images.{destination}.sha256"]').input_value() == original['images.0.sha256']
            expect(page.locator(f'[name="images.{destination}.caption"]')).to_have_value('Ungespeicherte Bildunterschrift')
            assert snapshot(owner) == before
        page.get_by_role('button', name='Bild 1 entfernen', exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(tmp_path / f'editor-images-{width}-js{javascript}.png'), full_page=False)
        (tmp_path / 'capture.json').write_text(json.dumps({
            'route': path, 'viewport': page.viewport_size, 'role': 'Cafeteria.Publisher',
            'javascript': javascript, 'coarse': width == 390,
        }, indent=2))
        with page.expect_navigation(wait_until='networkidle'):
            page.get_by_role('button', name='Bild 1 entfernen', exact=True).press('Enter')
        assert page.locator('[name="images.0.sha256"]').input_value() == original['images.1.sha256']
        expect(page.locator('[name="images.1.sha256"]')).to_have_count(0)
        expect(page.get_by_label('Titel', exact=True)).to_have_value('')
        assert page.locator('[name="_form_context"]').input_value() == original['_form_context']
        assert page.locator('[name="row_version"]').input_value() == original['row_version']
        assert len(posts) == 3 and all('/admin/rezepte/formular?' in post.url for post in posts)
        assert snapshot(owner) == before


@pytest.mark.parametrize('width', [390, 360])
def test_recipe_editor_servings_unit_select_fits_mobile_viewport(
    b3, master_server, browser, width, tmp_path,  # noqa: F811
):
    _, owner, client, _ = b3
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 844},
                             has_touch=True, reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/admin/rezepte/neu', wait_until='networkidle')
        page.evaluate('document.fonts.ready')

        # Form contract
        select = page.locator('#servings_unit_code')
        expect(select).to_be_visible()
        assert select.get_attribute('name') == 'servings_unit_code'
        options = select.locator('option').all_inner_texts()
        assert 'Keine Auswahl' in options
        assert any('Esslöffel' in opt for opt in options)

        # Page horizontal overflow check
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

        # Check for both "Keine Auswahl" and long unit "EL" ("Esslöffel (15 ml)")
        for option_value in ['', 'EL']:
            select.select_option(option_value)
            metrics = page.evaluate('''() => {
                const el = document.querySelector('#servings_unit_code');
                const style = window.getComputedStyle(el);
                const paddingLeft = parseFloat(style.paddingLeft) || 0;
                const paddingRight = parseFloat(style.paddingRight) || 0;
                const innerWidth = el.clientWidth - paddingLeft - paddingRight;

                const span = document.createElement('span');
                span.style.font = style.font;
                span.style.visibility = 'hidden';
                span.style.position = 'absolute';
                span.style.whiteSpace = 'nowrap';
                const selectedOpt = el.options[el.selectedIndex];
                span.textContent = selectedOpt ? selectedOpt.text : '';
                document.body.appendChild(span);
                const textWidth = span.getBoundingClientRect().width;
                span.remove();

                return {
                    text: selectedOpt ? selectedOpt.text : '',
                    textWidth: textWidth,
                    innerWidth: innerWidth,
                    clientWidth: el.clientWidth,
                    scrollWidth: el.scrollWidth,
                };
            }''')
            assert metrics['scrollWidth'] <= metrics['clientWidth'], (
                f"At {width}px, option '{metrics['text']}' scrollWidth {metrics['scrollWidth']} "
                f"exceeds clientWidth {metrics['clientWidth']}"
            )
            assert metrics['textWidth'] <= metrics['innerWidth'], (
                f"At {width}px, option '{metrics['text']}' textWidth {metrics['textWidth']:.1f}px "
                f"exceeds select innerWidth {metrics['innerWidth']:.1f}px (clientWidth={metrics['clientWidth']}px)"
            )
        assert not errors
