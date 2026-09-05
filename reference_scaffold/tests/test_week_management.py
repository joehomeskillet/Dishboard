from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from cafeteria.admin import week_management_routes  # noqa: F401 - register routes
from cafeteria.admin.week_management_routes import find_weeks
from cafeteria.component_catalog_store import AdminScope, ComponentCatalogConfigurationError
from cafeteria.workflow_partial_store import persist_week_header
from test_admin_workflow_routes import (
    DATABASE_URL, WEEK, _login,
    app as app, client as client, database_engine as database_engine,
)
from test_menu_collection import _save, _scope

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='Isolierte PostgreSQL-Testdatenbank fehlt.')


def _form(client, family='patienten', **changes):
    body = client.get('/admin/' + family + '/wochen').get_data(as_text=True)
    token = re.search(r'name="_csrf" value="([^"]+)\.week-create\.([^"]+)"', body)
    assert token
    values = {
        '_csrf': token.group(1) + '.week-create.' + token.group(2),
        'week': WEEK.isoformat(), 'title': 'Neue Testwoche', 'shared_note': 'Wochenhinweis',
        'row_version': '0',
    }
    values.update(changes)
    return values


def test_create_empty_week_has_version_one_and_redirects(client, database_engine):
    response = client.post('/admin/patienten/wochen', data=_form(client))
    assert response.status_code == 303
    assert response.location.endswith('/admin/patienten?week=2026-08-31')
    with database_engine.connect() as connection:
        week = connection.execute(text('SELECT title,shared_note,row_version FROM cafeteria.menu_weeks')).one()
        assert tuple(week) == ('Neue Testwoche', 'Wochenhinweis', 1)
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 0
    body = client.get('/admin/patienten/wochen').get_data(as_text=True)
    assert 'data-status="empty"' in body and 'Neue Testwoche' in body
    assert '/admin/patienten/copy?week=2026-09-07' in body
    assert '/admin/patienten/preview?week=2026-08-31' in body


def test_duplicate_and_update_attempt_preserve_week_and_form(client, database_engine):
    values = _form(client)
    assert client.post('/admin/patienten/wochen', data=values).status_code == 303
    values['title'] = 'Nicht überschreiben'
    response = client.post('/admin/patienten/wochen', data=values)
    assert response.status_code == 409 and 'Nicht überschreiben' in response.get_data(as_text=True)
    values['row_version'] = '1'
    assert client.post('/admin/patienten/wochen', data=values).status_code == 400
    with database_engine.connect() as connection:
        assert tuple(connection.execute(text('SELECT title,row_version FROM cafeteria.menu_weeks')).one()) == ('Neue Testwoche', 1)


@pytest.mark.parametrize('change', [{'week': '2026-09-01'}, {'title': ''}, {'week': 'not-a-date'}, {'row_version': '-1'}])
def test_validation_preserves_inputs(client, database_engine, change):
    values = _form(client, shared_note='Hinweis behalten', **change)
    response = client.post('/admin/patienten/wochen', data=values)
    assert response.status_code == 400
    assert 'Hinweis behalten' in response.get_data(as_text=True)
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0


def test_scoped_csrf_and_overrides(client, database_engine):
    values = _form(client)
    assert client.post('/admin/cafeteria/wochen', data=values).status_code == 409
    assert client.post('/admin/patienten/wochen', data={**values, '_csrf': 'wrong'}).status_code == 400
    assert client.post('/admin/patienten/wochen', data={**values, 'profile': 'staff_guest'}).status_code == 400
    assert client.post('/admin/patienten/wochen?location_id=5', data=values).status_code == 400
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES ('NEXT','Andere Küche',true)"))
    assert client.post('/admin/patienten/wochen', data=values).status_code == 409


def test_scoped_list_pagination_status_and_get_never_writes(client, database_engine):
    scope = _scope(client, database_engine)
    for offset in range(13):
        persist_week_header(database_engine, scope, WEEK + timedelta(weeks=offset), {'title': f'Woche {offset}', 'shared_note': ''}, 0)
    _save(database_engine, scope, title='Unvollständiges Menü')
    persist_week_header(database_engine, _scope(client, database_engine, 'staff_guest'), WEEK, {'title': 'Andere Profilwoche', 'shared_note': ''}, 0)
    with database_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='archived' WHERE week_start=:week"), {'week': WEEK + timedelta(weeks=12)})
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        other = connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES ('OTHER','Andere Küche',true) RETURNING id")).scalar_one()
    persist_week_header(database_engine, AdminScope(scope.actor_id, other, 'patient'), WEEK, {'title': 'Andere Standortwoche', 'shared_note': ''}, 0)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=(id=:id)'), {'id': scope.location_id})
        before = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()
    first, has_next = find_weeks(database_engine, scope)
    second, last_has_next = find_weeks(database_engine, scope, 2)
    assert len(first) == 12 and has_next and len(second) == 1 and not last_has_next
    assert first[0]['week_start'] > first[-1]['week_start'] > second[0]['week_start']
    assert second[0]['status'] == 'incomplete'
    body = client.get('/admin/patienten/wochen').get_data(as_text=True)
    assert 'Archiviert' in body and 'page=2' in body and body.count('data-week-id=') == 12
    assert 'Andere Profilwoche' not in body and 'Andere Standortwoche' not in body
    assert 'CHF' not in body and 'rappen' not in body
    with database_engine.connect() as connection:
        assert before == connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()


@pytest.mark.parametrize('query', ['page=0', 'page=10001', 'page=1&page=2', 'profile=patient', 'location_id=1'])
def test_invalid_list_parameters(client, query):
    assert client.get('/admin/patienten/wochen?' + query).status_code == 400


def test_authorization_and_active_location_fail_closed(app, client, database_engine):
    assert app.test_client().get('/admin/patienten/wochen').status_code == 401
    assert app.test_client().post('/admin/patienten/wochen').status_code == 401
    denied, _ = _login(app, database_engine, [])
    assert denied.get('/admin/patienten/wochen').status_code == 401
    client, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    scope = _scope(client, database_engine)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
    assert client.get('/admin/patienten/wochen').status_code == 503
    with pytest.raises(ComponentCatalogConfigurationError):
        find_weeks(database_engine, scope)
