"""BF-T30: a saved edit must not silently replace the published server output."""
from __future__ import annotations

from io import BytesIO

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from pypdf import PdfReader
from sqlalchemy import Engine, text

from cafeteria.public import routes as public_routes
from test_admin_workflow_db import _patient_values, _staff_values
from test_admin_workflow_routes import DAY, WEEK
from test_bf_state_dimensions_browser import (  # noqa: F401
    FAMILIES, admin_app, admin_engine, bf_page, browser, javascript_enabled, live_server,
)
from test_ui_preview_browser import _publish_week, _save_week


def _edited_publication(app: Flask, engine: Engine, profile: str) -> tuple:
    # The existing admin fixture uses real routes/stores but omits the public blueprint.
    app.register_blueprint(public_routes.bp)
    values = (_staff_values if profile == 'staff_guest' else _patient_values)('Publizierte Woche')
    for day in values['days']:
        for service in day['services']:
            service['options'][0]['title'] = 'Publizierter Kürbisteller'
    _save_week(engine, profile, WEEK, values)
    publication = _publish_week(engine, profile, WEEK)
    with engine.connect() as connection:
        published = connection.execute(text(
            'SELECT revision_code,snapshot_json FROM cafeteria.publication_revisions',
        )).one()
    for day in values['days']:
        for service in day['services']:
            service['options'][0]['title'] = 'Geänderter Entwurfsteller'
    values['title'] = 'Überarbeitete Herbstwoche'
    _save_week(engine, profile, WEEK, values)
    return publication, published


@pytest.mark.parametrize('family,profile', FAMILIES)
def test_t30_saved_edit_preview_and_public_outputs_keep_separate_revisions(
    bf_page: Page, browser: Browser, live_server: str,  # noqa: F811
    admin_app: Flask, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    """Content isolation only; explicit draft identification has a separate gap test."""
    publication, published = _edited_publication(admin_app, admin_engine, profile)

    page = bf_page
    response = page.goto(f'/admin/{family}/preview?week={DAY}')
    assert response is not None and response.status == 200
    assert response.headers['cache-control'] == 'no-store'
    expect(page.locator('.preview-notice')).to_contain_text('gespeicherte Woche')
    expect(page.locator('.preview-grid')).to_contain_text('Geänderter Entwurfsteller')
    expect(page.locator('.preview-grid')).not_to_contain_text('Publizierter Kürbisteller')
    pdf_link = page.get_by_role('link', name='PDF der gewählten Woche öffnen')
    expect(pdf_link).to_have_attribute('href', f'/admin/{family}/preview/print?week={DAY}')
    pdf = page.context.request.get(pdf_link.get_attribute('href'))
    assert pdf.status == 200 and pdf.headers['content-type'].startswith('application/pdf')
    pdf_text = ' '.join(' '.join(
        sheet.extract_text() for sheet in PdfReader(BytesIO(pdf.body())).pages
    ).split())
    assert 'Geänderter Entwurfsteller' in pdf_text
    assert 'Publizierter Kürbisteller' not in pdf_text

    # Anonymous browser: public web and print resolve the real publication, without mocks.
    with browser.new_context(base_url=live_server) as public_context:
        public_page = public_context.new_page()
        week_path = 'wochenangebot' if family == 'cafeteria' else 'wochenplan'
        for path in (f'/{family}/{week_path}/', f'/druck/{family}/woche'):
            output = public_page.goto(path)
            assert output is not None and output.status == 200
            assert output.headers['x-snapshot-revision'] == publication['revision_id']
            expect(public_page.locator('main')).to_contain_text('Publizierter Kürbisteller')
            expect(public_page.locator('main')).not_to_contain_text('Geänderter Entwurfsteller')
    with admin_engine.connect() as connection:
        assert connection.execute(text(
            'SELECT revision_code,snapshot_json FROM cafeteria.publication_revisions',
        )).all() == [published]


# BF-Lücke: reference_scaffold/cafeteria/admin/workflow_routes.py:1120
# BF-Lücke: reference_scaffold/cafeteria/templates/admin/preview.html:9
@pytest.mark.parametrize('family,profile', FAMILIES)
def test_t30_changed_published_week_identifies_preview_as_draft(
    bf_page: Page, admin_app: Flask, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    _edited_publication(admin_app, admin_engine, profile)
    page = bf_page
    page.goto(f'/admin/{family}/preview?week={DAY}')
    expect(page.locator('.preview-grid')).to_contain_text('Geänderter Entwurfsteller')
    # The persisted workflow can remain "published"; the displayed draft must be named.
    # Fixture week title deliberately contains no "Entwurf", avoiding a false positive.
    expect(page.locator('.preview-heading')).to_contain_text('Entwurf')
