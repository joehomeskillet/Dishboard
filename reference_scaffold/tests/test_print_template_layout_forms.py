"""Native layout forms keep stored revisions and explicit render failures usable."""
from __future__ import annotations

import pytest

from cafeteria.print_template_config import default_layout
from cafeteria.print_templates import default_document, template_revision
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login, database_engine  # noqa: F401
from test_print_template_archive import seed, snapshot
from test_print_template_routes import editor_app  # noqa: F401


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_stored_layout_reports_unsupported_renderer_without_500(editor_app, database_engine, family, profile):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    document = default_document()
    document['schema_version'] = 3
    template_revision(document, 'standard')['config']['layout'] = default_layout(profile)
    seed(database_engine, profile, document)
    before = snapshot(database_engine)
    message = 'neuen PDF-Renderer'
    editor = client.get(f'/admin/vorlagen/{family}?week={DAY}&revision=1')
    assert editor.status_code == 200 and message in editor.text
    assert '<iframe' not in editor.text
    assert 'name="revision" value="1"' in editor.text
    assert 'name="version" value="0"' in editor.text
    for path in (f'/admin/vorlagen/{family}/vorschau.pdf', f'/admin/{family}/preview/print'):
        response = client.get(f'{path}?week={DAY}')
        assert response.status_code == 422 and message in response.text
    assert snapshot(database_engine) == before
