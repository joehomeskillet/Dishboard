"""Browser contract for truthful page-header status bars."""
from __future__ import annotations

from flask import render_template_string
from playwright.sync_api import expect

from test_admin_workflow_routes import database_engine  # noqa: F401
from test_ui_master_components_browser import macro_site  # noqa: F401


def test_page_header_statusbar_semantics_variants_and_empty_values(macro_site):
    page, app, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    statusbar = page.locator('dl.admin-statusbar')
    expect(statusbar).to_have_count(1)
    expect(statusbar.locator('.admin-statusbar-item')).to_have_count(5)
    assert statusbar.locator('dt.admin-statusbar-label').all_inner_texts() == [
        'Status', 'Freigabe', 'Offene Angaben', 'Validierung', 'Fehlende Werte',
    ]
    assert statusbar.locator('.admin-statusbar-value-text').all_inner_texts() == [
        'Entwurf', 'Freigegeben', '2', 'Eingabe prüfen', '0',
    ]
    expect(statusbar.locator('.admin-statusbar-detail')).to_have_text('Heute geprüft')
    for variant in ('neutral', 'success', 'warning', 'danger'):
        expect(statusbar.locator(f'.admin-statusbar-item--{variant}').first).to_be_visible()
    expect(statusbar).not_to_contain_text('Wird ausgelassen')

    with app.app_context():
        omitted = render_template_string(
            """{% from 'admin/_macros.html' import page_header %}
            {{ page_header('Kompakt', status_items=[
              {'label': 'Leer', 'value': ''},
              {'label': 'Ohne Wert', 'value': none},
              {'label': '', 'value': 'Nicht beschriftet'}
            ]) }}"""
        )
        assert 'admin-statusbar' not in omitted

        capped = render_template_string(
            """{% from 'admin/_macros.html' import page_header %}
            {{ page_header('Kompakt', status_items=[
              {'label': 'A', 'value': '1'}, {'label': 'B', 'value': '2'},
              {'label': 'C', 'value': '3'}, {'label': 'D', 'value': '4'},
              {'label': 'E', 'value': '5'}, {'label': 'F', 'value': '6'}
            ]) }}"""
        )
        assert capped.count('admin-statusbar-item admin-statusbar-item--') == 5
        assert '>F<' not in capped and '>6<' not in capped


def test_page_header_statusbar_reflows_at_360_without_document_overflow(macro_site):
    page, _, _, _ = macro_site
    page.set_viewport_size({'width': 360, 'height': 800})
    page.goto('/__macro_components__', wait_until='networkidle')

    statusbar = page.locator('.admin-statusbar')
    expect(statusbar).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    bar_box = statusbar.bounding_box()
    assert bar_box is not None and bar_box['width'] <= 360
    for item in statusbar.locator('.admin-statusbar-item').all():
        box = item.bounding_box()
        assert box is not None and box['width'] <= bar_box['width'] + 1
