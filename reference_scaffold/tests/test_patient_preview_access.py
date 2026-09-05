from __future__ import annotations

import re

import pytest
from flask import Flask
from sqlalchemy import Engine, text

from test_admin_workflow_db import _patient_values, _save_reviewed
from test_admin_workflow_routes import DAY, _login
from test_rendered_ui import admin_app, admin_engine  # noqa: F401


@pytest.mark.parametrize('state', ('incomplete', 'review_open'))
def test_patient_preview_link_remains_available_when_publication_is_blocked(
    admin_app: Flask, admin_engine: Engine, state: str,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _save_reviewed(admin_engine, 'patient', _patient_values())
    with admin_engine.begin() as connection:
        if state == 'incomplete':
            connection.execute(text(
                'DELETE FROM cafeteria.menu_items WHERE id=(SELECT min(id) FROM cafeteria.menu_items)'
            ))
        else:
            connection.execute(text(
                "UPDATE cafeteria.menu_items SET allergen_review_status='not_checked' "
                'WHERE id=(SELECT min(id) FROM cafeteria.menu_items)'
            ))

    overview = client.get(f'/admin/patienten?week={DAY}')
    assert overview.status_code == 200
    body = overview.get_data(as_text=True)
    assert f'data-status="{state}"' in body
    links = [
        link for link in re.finditer(r'<a\b([^>]*)>(.*?)</a>', body, re.S)
        if re.sub(r'<[^>]*>', '', link.group(2)).strip() == 'Vorschau'
    ]
    assert len(links) == 1
    link = links[0]
    attributes = dict(re.findall(r'([a-z-]+)="([^"]*)"', link.group(1)))
    assert attributes['href'] == f'/admin/patienten/preview?week={DAY}'
    assert 'disabled' not in attributes['class'].split()
    assert 'aria-disabled' not in attributes
    assert re.search(r'\sdisabled(?:\s|=|$)', link.group(1)) is None
    assert attributes['target'] == '_blank'
    assert attributes['rel'] == 'noopener'

    preview = client.get(attributes['href'])
    assert preview.status_code == 200
    preview_body = preview.get_data(as_text=True)
    assert 'data-preview="last-saved"' in preview_body
    assert f'data-week="{DAY}"' in preview_body
    assert 'data-profile="patient"' in preview_body
