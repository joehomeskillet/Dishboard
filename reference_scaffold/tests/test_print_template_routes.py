"""Full factory HTTP contracts for editing, previewing and active weekly output."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

import cafeteria
from cafeteria.print_template_config import default_config
from cafeteria.print_templates import SETTING_PREFIX, read_templates
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.fixture
def editor_app(database_engine, monkeypatch, tmp_path: Path):  # noqa: F811
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    application = cafeteria.create_app()
    application.config.update(
        TESTING=True, SECRET_KEY='print-template-http-test', LAST_GOOD_DIR=str(tmp_path),
        DEMO_TODAY='2026-09-02', FRAME_ANCESTORS="'self'",
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    return application


def fields(action='save', version=0, revision=1, **extra):
    result = {'_csrf': 'workflow-csrf', 'action': action, 'version': str(version), 'revision': str(revision)}
    if action == 'save':
        result.update(name='Herbstvorlage', **default_config())
    result.update(extra)
    return result


def pdf_text(response):
    assert response.status_code == 200 and response.mimetype == 'application/pdf'
    return ' '.join(PdfReader(BytesIO(response.data)).pages[0].extract_text().split())


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_saved_preview_matches_activated_download_and_restore_needs_activation(editor_app, database_engine, family, profile):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    editor = f'/admin/vorlagen/{family}?week={DAY}'
    preview = f'/admin/vorlagen/{family}/vorschau.pdf?week={DAY}&revision=2'
    active = f'/admin/{family}/preview/print?week={DAY}'
    page = client.get(editor)
    assert page.status_code == 200
    assert 'name="header_text"' in page.text and '<iframe' in page.text
    assert page.headers['Cache-Control'] == 'no-store'
    assert "style-src 'self'; script-src 'self'" in page.headers['Content-Security-Policy']
    before = pdf_text(client.get(active))
    result = client.post(editor, data=fields(header_text='Guten Appetit', footer_text='Ihre Küche', font='fira'))
    assert result.status_code == 303
    assert pdf_text(client.get(active)) == before
    preview_response = client.get(preview)
    preview_body = pdf_text(preview_response)
    assert 'Guten Appetit' in preview_body and 'Ihre Küche' in preview_body
    assert preview_response.headers['X-Print-Template-Revision'] == 'standard:2'
    assert client.post(editor, data=fields('activate', 1, 2)).status_code == 303
    download = client.get(active)
    assert pdf_text(download) == preview_body
    assert download.data == preview_response.data
    assert download.headers['X-Print-Template-Revision'] == preview_response.headers['X-Print-Template-Revision']
    assert client.post(editor, data=fields('restore', 2, 1)).status_code == 303
    assert pdf_text(client.get(active)) == preview_body
    restored = client.get(f'/admin/vorlagen/{family}/vorschau.pdf?week={DAY}&revision=3')
    assert 'Guten Appetit' not in pdf_text(restored)
    assert client.post(editor, data=fields('activate', 3, 3)).status_code == 303
    assert pdf_text(client.get(active)) == before
    assert client.get(f'/admin/vorlagen/{family}/vorschau.pdf?week={DAY}&revision=2').headers['X-Print-Template-Revision'] == 'standard:2'
    # An active template never bypasses checks after later menu edits.
    changed = _staff_values() if profile == 'staff_guest' else _patient_values()
    for day in changed['days']:
        for service in day['services']:
            for option in service['options']:
                option['note'] = 'Vollständige Zubereitungshinweise. ' * 100
    _save(database_engine, profile, changed)
    assert client.get(active).status_code == 422
    with database_engine.connect() as connection:
        assert read_templates(connection, profile)['active_revision'] == 3


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_template_mutations_require_current_admin_but_active_pdf_remains_readable(editor_app, database_engine, role):  # noqa: F811
    client, _ = _login(editor_app, database_engine, [role])
    _save(database_engine, 'patient', _patient_values())
    path = f'/admin/vorlagen/patienten?week={DAY}'
    assert client.get(path).status_code == 403
    assert client.post(path, data=fields()).status_code == 403
    assert client.get(f'/admin/vorlagen/patienten/vorschau.pdf?week={DAY}').status_code == 403
    assert client.get(f'/admin/patienten/preview/print?week={DAY}').status_code == 200
    assert 'Vorlageneditor öffnen' not in client.get('/admin/vorlagen').text
    assert editor_app.test_client().get(path).status_code == 401


def test_missing_week_has_editable_empty_state_and_activation_refuses(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    path = f'/admin/vorlagen/patienten?week={DAY}'
    response = client.get(path)
    assert response.status_code == 200 and 'noch keine gespeicherten Menüs' in response.text
    assert '<iframe' not in response.text
    assert client.post(path, data=fields()).status_code == 303
    result = client.post(path, data=fields('activate', 1, 2))
    assert result.status_code == 400 and 'Aktivierung benötigt eine gespeicherte Woche' in result.text
    with database_engine.connect() as connection:
        assert read_templates(connection, 'patient')['active_revision'] == 1


def test_http_conflict_and_field_errors_preserve_unsaved_input(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    path = f'/admin/vorlagen/patienten?week={DAY}'
    assert client.post(path, data=fields(header_text='Erste Sitzung')).status_code == 303
    conflict = client.post(path, data=fields(header_text='Zweite Sitzung'))
    assert conflict.status_code == 409 and 'Zweite Sitzung</textarea>' in conflict.text
    assert 'name="version" value="0"' in conflict.text
    assert 'Aktuellen Stand neu laden' in conflict.text
    invalid = client.post(path, data=fields(version=1, revision=2, header_text='CHF 10'))
    assert invalid.status_code == 400 and 'Patientenvorlagen dürfen keine Kostenangaben enthalten' in invalid.text
    assert 'aria-invalid="true"' in invalid.text and 'CHF 10</textarea>' in invalid.text


def test_csrf_strict_form_query_types_and_changed_authority_block_writes(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    path = f'/admin/vorlagen/patienten?week={DAY}'
    valid = fields()
    for data in (
        {**valid, '_csrf': 'wrong'}, {**valid, 'actor_id': '1'}, {**valid, 'css': 'color:red'},
        {**valid, 'revision': '0'}, {**valid, 'revision': '-1'}, {**valid, 'version': 'false'},
        MultiDict([*valid.items(), ('font', 'fira')]), MultiDict([*valid.items(), ('_csrf', 'workflow-csrf')]),
    ):
        assert client.post(path, data=data).status_code == 400
    for suffix in ('&profile=staff_guest', '&week=2026-09-07', '&template=standard&template=standard', '&revision=1&revision=2', '&revision=999'):
        assert client.get(path + suffix).status_code == 400
    assert client.get('/admin/vorlagen/patienten?week=2026-09-01').status_code == 400
    assert client.get(path + '&template=missing').status_code == 404
    _login(editor_app, database_engine, ['Cafeteria.Editor'])
    assert client.post(path, data=valid).status_code == 401
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key LIKE :key'), {'key': SETTING_PREFIX + '%'}).scalar_one() == 0
