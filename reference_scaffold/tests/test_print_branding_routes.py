"""One active brand serves editor preview, activation preflight and active output."""
from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import text

from cafeteria.branding import change_branding
from cafeteria.admin.week_pdf import ASSETS
from cafeteria.branding_assets import normalize_logo
from cafeteria.branding_config import default_config as brand_defaults
from cafeteria.print_templates import read_templates
from test_branding_store import _png
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login
from test_print_template_routes import database_engine, editor_app, fields  # noqa: F401


def activate_brand(app, engine):
    client, actor = _login(app, engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        authz = session['authz_version']
    logo = normalize_logo(_png())
    config = {**brand_defaults(), 'font_body': 'carlito', 'font_heading': 'fira', 'logo_sha256': logo.sha256}
    change_branding(engine, actor, authz, 0, 'save', name='Herbstmarke', config=config, logo=logo)
    change_branding(engine, actor, authz, 1, 'activate', revision_id=2)
    return client, actor, authz


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_draft_brand_isolation_pdf_identity_and_unchanged_historical_templates(editor_app, database_engine, family, profile):  # noqa: F811
    client, actor, authz = activate_brand(editor_app, database_engine)
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    editor = f'/admin/vorlagen/{family}?week={DAY}'
    active = f'/admin/{family}/preview/print?week={DAY}'
    preview = f'/admin/vorlagen/{family}/vorschau.pdf?week={DAY}&revision=2'
    initial = client.get(active)
    assert initial.status_code == 200 and 'X-Brand-Revision' not in initial.headers
    page = client.get(editor)
    assert page.text.count('value="active_brand"') == 3
    assert client.post(editor, data=fields(font='active_brand', palette='active_brand', logo='active_brand')).status_code == 303
    shown = client.get(preview)
    assert shown.status_code == 200 and shown.headers['X-Brand-Revision'] == '2'
    assert shown.headers['Cache-Control'] == 'no-store'
    assert client.get(active).data == initial.data
    assert client.post(editor, data=fields('activate', 1, 2)).status_code == 303
    assert client.get(active).data == shown.data
    with database_engine.connect() as connection:
        stored = read_templates(connection, profile)
    change_branding(database_engine, actor, authz, 2, 'save', name='Wintermarke', config=brand_defaults())
    assert client.get(active).data == shown.data  # An unactivated brand cannot leak into PDFs.
    change_branding(database_engine, actor, authz, 3, 'activate', revision_id=3)
    new = client.get(active)
    assert new.status_code == 200 and new.headers['X-Brand-Revision'] == '3'
    assert new.data != shown.data and new.data == client.get(preview).data
    assert PdfReader(BytesIO(new.data)).metadata.subject == 'Dishboard Markenrevision 3'
    with database_engine.connect() as connection:
        assert read_templates(connection, profile) == stored
    assert client.post(editor, data=fields('restore', 2, 1)).status_code == 303
    assert client.post(editor, data=fields('activate', 3, 3)).status_code == 303
    assert client.get(active).data == initial.data


def test_brand_failure_never_replaces_active_template_or_hides_saved_input(editor_app, database_engine):  # noqa: F811
    client, _, _ = activate_brand(editor_app, database_engine)
    _save(database_engine, 'patient', _patient_values())
    editor = f'/admin/vorlagen/patienten?week={DAY}'
    assert client.post(editor, data=fields(font='active_brand')).status_code == 303
    with database_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.settings SET setting_value='{}'::jsonb WHERE setting_key='branding.v1'"))
    assert client.get(editor).status_code == 200
    assert 'Markeneinstellungen sind ungültig' in client.get(editor).text
    assert client.get(f'/admin/vorlagen/patienten/vorschau.pdf?week={DAY}&revision=2').status_code == 503
    assert client.post(editor, data=fields('activate', 1, 2)).status_code == 503
    assert client.get(f'/admin/patienten/preview/print?week={DAY}').status_code == 200  # Explicit default remains available.
    with database_engine.connect() as connection:
        assert read_templates(connection, 'patient')['active_revision'] == 1


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_standard_brand_logo_and_explicit_none_match_preview_fit_and_download(
    editor_app, database_engine, family, profile, tmp_path,  # noqa: F811
):
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    editor = f'/admin/vorlagen/{family}?week={DAY}'
    for revision, logo in ((2, 'active_brand'), (3, 'none')):
        assert 'Ohne individuelles Markenlogo erscheint das Südhang-Standardlogo.' in client.get(editor).text
        version = 2 * (revision - 2)
        assert client.post(editor, data=fields(version=version, font='active_brand',
                                              palette='active_brand', logo=logo)).status_code == 303
        preview = client.get(f'/admin/vorlagen/{family}/vorschau.pdf?week={DAY}&revision={revision}')
        assert preview.status_code == 200 and preview.headers['X-Brand-Revision'] == '1'
        reader = PdfReader(BytesIO(preview.data))
        assert len(reader.pages) == 1
        images = list(reader.pages[0].images)
        assert len(images) == (1 if logo == 'active_brand' else 0)
        if logo == 'active_brand':
            embedded = [item.get_object().get_data() for item in reader.pages[0]['/Resources']['/XObject'].values()
                        if item.get_object().get('/Subtype') == '/Image']
            assert embedded == [(ASSETS / 'img/weekly-print-logo.jpg').read_bytes()]
        assert client.post(editor, data=fields('activate', version + 1, revision)).status_code == 303
        download = client.get(f'/admin/{family}/preview/print?week={DAY}')
        assert download.status_code == 200 and download.data == preview.data
        (tmp_path / f'{family}-{logo}.pdf').write_bytes(download.data)
