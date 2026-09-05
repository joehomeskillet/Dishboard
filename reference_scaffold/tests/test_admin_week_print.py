from __future__ import annotations

import re
from io import BytesIO

import pytest
from flask import Flask
from pypdf import PdfReader
from sqlalchemy import Engine, text

from cafeteria.workflow_store import load_draft_connection

from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _login
from test_rendered_ui import admin_app, admin_engine  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_print_requires_auth_and_exact_saved_week(
    admin_app: Flask, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    path = f'/admin/{family}/preview/print?week={DAY}'
    assert admin_app.test_client().get(path).status_code == 401
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    assert client.get(path).status_code == 404
    values = _staff_values('Nur gespeicherte Druckwoche') if profile == 'staff_guest' else _patient_values('Nur gespeicherte Druckwoche')
    _save(admin_app.extensions['cafeteria_db'], profile, values)
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.mimetype == 'application/pdf'
    assert response.headers['Content-Disposition'] == f'inline; filename="wochenplan-{family}-{DAY}.pdf"'
    reader = PdfReader(BytesIO(response.data))
    assert len(reader.pages) == 1
    body = reader.pages[0].extract_text()
    assert 'Nur gespeicherte Druckwoche' in body
    assert ('31. August 2026 bis 04. September 2026' if profile == 'staff_guest' else '31. August 2026 bis 06. September 2026') in body
    assert client.get(f'/admin/{family}/preview/print?week=2026-09-07').status_code == 404
    preview = client.get(f'/admin/{family}/preview?week={DAY}').get_data(as_text=True)
    assert path in preview
    for suffix in ('&profile=patient', '&profile_scope=common', '&week=2026-09-07'):
        assert client.get(path + suffix).status_code == 400
    assert client.get(f'/admin/{family}/preview/print?week=2026-09-01').status_code == 400
    with admin_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
    assert client.get(path).status_code == 503


def test_print_metadata_closed_slots_and_patient_isolation(
    admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _patient_values()
    option = values['days'][0]['services'][0]['options'][0]
    option.update(
        title='<b>Kartoffelgratin</b>', description='Mit frischen Kräutern', note='Hinweis zur Zubereitung',
        allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}, {'code': 'EGGS', 'name': 'Eier', 'presence': 'may_contain'}],
        labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}], origins=[{'ingredient': 'Kartoffeln', 'country_code': 'CH', 'text': 'Kartoffeln: CH'}],
        allergen_review_status='not_checked',
    )
    values['days'][-1]['services'][-1].update(service_state='closed', notice='Küche geschlossen')
    _save(admin_app.extensions['cafeteria_db'], 'patient', values)
    with admin_engine.connect() as connection:
        before = load_draft_connection(connection, 'patient', WEEK)
    response = client.get(f'/admin/patienten/preview/print?week={DAY}')
    assert response.status_code == 200
    body = ' '.join(PdfReader(BytesIO(response.data)).pages[0].extract_text().split())
    assert '<b>Kartoffelgratin</b>' in body
    assert 'Mit frischen Kräutern' in body and 'Hinweis zur Zubereitung' in body
    assert 'Kartoffeln: CH' in body and 'Enthält: Milch' in body and 'Kann enthalten: Eier' in body
    assert 'Allergenprüfung offen' in body and 'Allergenangaben nicht erfasst' in body
    assert body.count('Küche geschlossen') == 1
    assert re.search(r'\b(?:preise?|chf|rappen|kosten|prices?|cafeteria)\b', body, re.I) is None
    with admin_engine.connect() as connection:
        assert load_draft_connection(connection, 'patient', WEEK) == before


def test_print_overflow_is_actionable_and_does_not_change_draft(
    admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _patient_values()
    for day in values['days']:
        for service in day['services']:
            for option in service['options']:
                option['note'] = 'Sehr ausführliche Rezepturbeschreibung. ' * 40
    _save(admin_app.extensions['cafeteria_db'], 'patient', values)
    with admin_engine.connect() as connection:
        before = load_draft_connection(connection, 'patient', WEEK)
    response = client.get(f'/admin/patienten/preview/print?week={DAY}')
    assert response.status_code == 422
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'A4-Seite' in response.get_data(as_text=True)
    assert 'speichern' in response.get_data(as_text=True)
    with admin_engine.connect() as connection:
        assert load_draft_connection(connection, 'patient', WEEK) == before
