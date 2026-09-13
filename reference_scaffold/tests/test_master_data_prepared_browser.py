"""Native desktop/mobile forms for exact recipe pins and required storage."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_master_data_prepared_db import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, prepared, seeded_pg16, snapshot, preparation_choice, create,
)
from test_master_data_browser import master_server, targets  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height,javascript', [
    (1440, 1100, True), (390, 1100, False),
    (1440, 900, True), (390, 844, True), (390, 844, False),
])
def test_native_storage_and_preparation_selection_survives_save_and_reload(
        prepared, master_server, browser, width, height, javascript, tmp_path):  # noqa: F811
    _, owner, _, _, _, frozen = prepared
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/admin/grundlagen/zutaten/neu')
        expect(page.get_by_role('heading', level=1)).to_have_text('Zutat anlegen')
        primary = page.get_by_role('button', name='Zutat speichern', exact=True)
        expect(primary).to_have_count(1)
        assert primary.evaluate('button => button.form.id') == 'food-core-form'
        posts = []
        page.on('request', lambda request: posts.append(request.method) if request.method == 'POST' else None)
        primary.click()
        expect(page.get_by_label('Name', exact=True)).to_be_focused()
        assert page.get_by_label('Name', exact=True).evaluate('input => input.validity.valueMissing')
        assert not posts
        page.get_by_label('Name', exact=True).fill('Hummus vorbereitet Browser')
        page.get_by_label('Testlager', exact=True).check()
        page.get_by_label('Zubereitung aus einem Rezept', exact=False).select_option(preparation_choice(frozen))
        box = primary.bounding_box()
        output = Path(os.environ.get('MASTER_DATA_EVIDENCE_DIR', str(tmp_path)))
        output.mkdir(parents=True, exist_ok=True)
        output.chmod(0o700)
        viewport = output / f'prepared-before-save-{width}x{height}-js-{javascript}.png'
        page.screenshot(path=str(viewport))
        viewport.chmod(0o600)
        assert box is not None and 0 <= box['y'] and box['y'] + box['height'] <= 1100
        expect(primary).to_be_in_viewport(ratio=1)
        controls = page.locator('#food-core-form').locator('input:not([type="hidden"]), select, textarea, a[href], button')
        controls.first.focus()
        for index in range(controls.count()):
            field = controls.nth(index)
            expect(field).to_be_focused()
            expect(field).to_be_in_viewport()
            # Native textarea focus reveals its first line, including after resizing.
            # Check that this focused part receives hits rather than the save bar.
            assert field.evaluate('''element => {
                const box = element.getBoundingClientRect();
                return element.contains(document.elementFromPoint(
                    box.x + box.width / 2, box.y + Math.min(16, box.height / 2)));
            }''')
            if index < controls.count() - 1:
                field_box = field.bounding_box()
                bar_box = page.locator('.grundlagen-core-actions').bounding_box()
                assert field_box['y'] + field_box['height'] <= bar_box['y']
                page.keyboard.press('Tab')
        page.set_viewport_size({'width': width, 'height': 600})
        assert page.locator('.grundlagen-core-actions').evaluate(
            'element => getComputedStyle(element).position') == 'static'
        page.set_viewport_size({'width': width, 'height': height})
        primary.click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Zutat bearbeiten')
        path = urlsplit(page.url).path
        expect(page.get_by_label('Zubereitung aus einem Rezept', exact=False)).to_have_value(preparation_choice(frozen))
        expect(page.get_by_label('Testlager', exact=True)).to_be_checked()
        expect(page.get_by_role('link', name='Rezeptverlauf', exact=True)).to_have_attribute(
            'href', '/admin/rezepte/' + str(frozen['recipe_public_id']) + '/revisionen')
        expect(page.get_by_text('Kein Bestand erfasst', exact=True)).to_be_visible()
        targets(page)
        before = snapshot(owner)
        page.reload()
        expect(page.get_by_label('Zubereitung aus einem Rezept', exact=False)).to_have_value(preparation_choice(frozen))
        page.get_by_text('Rezeptauswahl', exact=True).click()
        page.get_by_label('Festgeschriebenes Rezept suchen', exact=True).fill('Hummus')
        page.get_by_role('button', name='Suchen', exact=True).click()
        expect(page.get_by_label('Festgeschriebenes Rezept suchen', exact=True)).to_have_value('Hummus')
        expect(page.get_by_label('Zubereitung aus einem Rezept', exact=False)).to_have_value(preparation_choice(frozen))
        assert urlsplit(page.url).path == path and snapshot(owner) == before
        targets(page)
        page.get_by_label('Name', exact=True).focus()
        page.keyboard.press('Tab')
        expect(page.get_by_label('Basiseinheit', exact=True)).to_be_focused()
        assert not errors
        page.get_by_role('heading', level=1).click()
        page.evaluate('window.scrollTo(0, 0)')
        screenshot = output / f'prepared-food-{width}x{height}-js-{javascript}.png'
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        viewport = output / f'prepared-food-{width}x{height}-js-{javascript}-viewport.png'
        page.screenshot(path=str(viewport))
        viewport.chmod(0o600)
        page.get_by_role('link', name='Lagerorte verwalten', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Grundlagen')
        expect(page.get_by_role('heading', name='Lagerorte', exact=True)).to_be_visible()
        assert snapshot(owner) == before


@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_original_storage_and_prepared_pin_are_visible_after_location_change(
        prepared, master_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, owner, client, _, _, frozen = prepared
    path = create(client, name='Hummus ursprünglicher Standort', prepared_recipe_choice=preparation_choice(frozen))
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        form = page.locator('#food-core-form')
        original = form.evaluate('el => Array.from(new FormData(el).entries())')
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEW','Neuer Standort',true)"))
        before = snapshot(owner)
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Zutat speichern', exact=True).click()
        assert outcome.value.status == 409
        expect(page.get_by_role('heading', level=1)).to_have_text('Ursprüngliche Eingaben')
        returned = page.get_by_role('region', name='Ursprüngliche Eingaben', exact=True)
        assert returned.evaluate(
            'el => Array.from(el.querySelectorAll("input[type=hidden]"), input => [input.name, input.value])',
        ) == original
        assert page.locator('main form').count() == 0
        expected = [('Lagerort · ursprüngliche Referenz', dict(original)['storage_location_public_ids']),
                    ('Zubereitung · ursprünglicher Rezeptstand', preparation_choice(frozen))]
        for label, value in expected:
            control = page.get_by_label(label, exact=True)
            expect(control).to_be_visible()
            expect(control).to_have_attribute('readonly', '')
            assert value in control.input_value()
            control.focus()
            page.keyboard.press('Control+A')
            assert value in control.evaluate('el => el.value.slice(el.selectionStart, el.selectionEnd)')
        assert page.locator('main button[type="submit"]').count() == 0
        assert snapshot(owner) == before
        targets(page)
        output = Path(os.environ.get('MASTER_DATA_EVIDENCE_DIR', str(tmp_path)))
        output.mkdir(parents=True, exist_ok=True)
        output.chmod(0o700)
        page.get_by_role('heading', level=1).click()
        page.evaluate('window.scrollTo(0, 0)')
        screenshot = output / f'prepared-location-conflict-{width}-js-{javascript}.png'
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        viewport = output / f'prepared-location-conflict-{width}-js-{javascript}-viewport.png'
        page.screenshot(path=str(viewport))
        viewport.chmod(0o600)
