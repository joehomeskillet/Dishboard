"""Native desktop/mobile forms for exact recipe pins and required storage."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_master_data_prepared_db import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, prepared, seeded_pg16, snapshot, preparation_choice,
)
from test_master_data_browser import master_server, targets  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_native_storage_and_preparation_selection_survives_save_and_reload(
        prepared, master_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, owner, _, _, _, frozen = prepared
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/admin/grundlagen/zutaten/neu')
        expect(page.get_by_role('heading', level=1)).to_have_text('Zutat anlegen')
        page.get_by_label('Name', exact=True).fill('Hummus vorbereitet Browser')
        page.get_by_label('Testlager', exact=True).check()
        page.get_by_label('Zubereitung aus einem Rezept', exact=False).select_option(preparation_choice(frozen))
        primary = page.get_by_role('button', name='Zutat anlegen', exact=True)
        box = primary.bounding_box()
        assert box is not None and box['y'] + box['height'] <= 1100
        primary.click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Zutat bearbeiten')
        path = urlsplit(page.url).path
        expect(page.get_by_label('Zubereitung aus einem Rezept', exact=False)).to_have_value(preparation_choice(frozen))
        expect(page.get_by_label('Testlager', exact=True)).to_be_checked()
        expect(page.get_by_role('link', name='Rezeptverlauf öffnen')).to_have_attribute(
            'href', '/admin/rezepte/' + str(frozen['recipe_public_id']) + '/revisionen')
        expect(page.get_by_text('Kein Bestand erfasst', exact=True)).to_be_visible()
        targets(page)
        before = snapshot(owner)
        page.reload()
        expect(page.get_by_label('Zubereitung aus einem Rezept', exact=False)).to_have_value(preparation_choice(frozen))
        page.get_by_text('Rezeptauswahl eingrenzen', exact=True).click()
        page.get_by_label('Festgeschriebenes Rezept suchen', exact=True).fill('Hummus')
        page.get_by_role('button', name='Rezeptauswahl suchen', exact=True).click()
        expect(page.get_by_label('Festgeschriebenes Rezept suchen', exact=True)).to_have_value('Hummus')
        expect(page.get_by_label('Zubereitung aus einem Rezept', exact=False)).to_have_value(preparation_choice(frozen))
        assert urlsplit(page.url).path == path and snapshot(owner) == before
        targets(page)
        page.keyboard.press('Tab')
        assert page.locator(':focus').count() == 1
        assert not errors
        output = Path(os.environ.get('MASTER_DATA_EVIDENCE_DIR', str(tmp_path)))
        output.mkdir(parents=True, exist_ok=True)
        output.chmod(0o700)
        screenshot = output / f'prepared-food-{width}-js-{javascript}.png'
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        page.get_by_role('link', name='Lagerorte verwalten', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Grundlagen')
        expect(page.get_by_role('heading', name='Lagerorte', exact=True)).to_be_visible()
        assert snapshot(owner) == before
