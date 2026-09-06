"""Native Chrome proves the three inherited fields and the real saved PDF viewer."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY
from test_print_branding_routes import activate_brand
from test_print_template_browser import _context, _targets, _wait_for_pdf_paint, browser, editor_server  # noqa: F401
from test_print_template_routes import database_engine, editor_app  # noqa: F401


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_brand_selection_saved_preview_and_activation(editor_app, editor_server, database_engine, browser,  # noqa: F811
                                                     width, family, profile, tmp_path: Path):
    client, _, _ = activate_brand(editor_app, database_engine)
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    with _context(browser, editor_server, client, width) as context:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        response = page.goto(f'/admin/vorlagen/{family}?week={DAY}')
        assert response is not None and response.status == 200
        for label in ('Druckschrift', 'Farbpalette', 'Logo'):
            page.get_by_label(label, exact=True).select_option('active_brand')
        page.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Revision 2', exact=True)).to_be_visible()
        for label in ('Druckschrift', 'Farbpalette', 'Logo'):
            expect(page.get_by_label(label, exact=True)).to_have_value('active_brand')
        frame = page.locator('iframe')
        expect(frame).to_be_visible()
        url = frame.get_attribute('src')
        assert url is not None
        preview = client.get(url)
        assert preview.status_code == 200 and preview.headers['X-Brand-Revision'] == '2'
        # Screenshot caret hiding leaves empty style attributes on inputs.
        # Check the actual application DOM before the browser-proof capture.
        _targets(page)
        frame.scroll_into_view_if_needed()
        _wait_for_pdf_paint(page, frame, tmp_path / f'brand-pdf-{family}-{width}.png')
        page.screenshot(path=str(tmp_path / f'brand-editor-{family}-{width}.png'), full_page=True)
        page.get_by_role('button', name='Revision 2 prüfen und aktivieren', exact=True).click()
        expect(page.get_by_text('Aktive Druckvorlage', exact=True)).to_be_visible()
        download = client.get(f'/admin/{family}/preview/print?week={DAY}')
        assert download.data == preview.data and download.headers['X-Brand-Revision'] == '2'
        assert not errors
