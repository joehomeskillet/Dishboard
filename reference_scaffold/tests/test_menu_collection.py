from __future__ import annotations

from datetime import timedelta

import pytest
import cafeteria
from sqlalchemy import text

from cafeteria.admin import menu_collection_routes  # noqa: F401 - register routes
from cafeteria.admin.menu_collection_store import find_menus
from cafeteria.component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError, create_component,
)
from cafeteria.workflow_partial_store import persist_menu_item, persist_week_header
from test_admin_workflow_routes import (
    DATABASE_URL, WEEK, _login, _payload, _session_actor_id,
    app as app, client as client, database_engine as database_engine,
)

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='Isolierte PostgreSQL-Testdatenbank fehlt.')


def test_app_factory_registers_collection_once(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    for _ in range(2):
        application = cafeteria.create_app()
        rules = [rule.endpoint for rule in application.url_map.iter_rules()]
        assert rules.count('admin.menu_collection') == 1


def _scope(client, engine, profile='patient'):
    with engine.connect() as connection:
        location = connection.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    return AdminScope(_session_actor_id(client), location, profile)


def _save(engine, scope, *, week=WEEK, title='Gespeichertes Menü', payload=None):
    with engine.connect() as connection:
        exists = connection.execute(text(
            'SELECT 1 FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id '
            'WHERE w.location_id=:location AND p.code=:profile AND w.week_start=:week'
        ), {'location': scope.location_id, 'profile': scope.profile_code, 'week': week}).scalar_one_or_none()
    if not exists:
        persist_week_header(engine, scope, week, {'title': 'Testwoche', 'shared_note': ''}, 0)
    values = _payload(staff=scope.profile_code == 'staff_guest') if payload is None else payload
    values['title'] = title
    persist_menu_item(engine, scope, week, week.isoformat(), 'LUNCH', 'MENU_1', values, 0)


def test_collection_scopes_profile_location_and_never_writes(client, database_engine):
    patient = _scope(client, database_engine)
    staff = _scope(client, database_engine, 'staff_guest')
    _save(database_engine, patient, title='Patienten exklusiv')
    _save(database_engine, staff, title='Cafeteria exklusiv')
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        other = connection.execute(text(
            "INSERT INTO cafeteria.locations(code,name,active) VALUES ('OTHER','Andere Küche',true) RETURNING id"
        )).scalar_one()
    _save(database_engine, AdminScope(patient.actor_id, other, 'patient'),
          week=WEEK + timedelta(days=7), title='Anderer Standort')
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=(id=:id)'), {'id': patient.location_id})
        before = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()
        items_before = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_items ORDER BY id')).all()
    patient_page = client.get('/admin/patienten/menues')
    body = patient_page.get_data(as_text=True)
    assert patient_page.status_code == 200
    assert patient_page.headers['Cache-Control'] == 'no-store'
    assert 'Patienten exklusiv' in body
    assert 'Cafeteria exklusiv' not in body and 'Anderer Standort' not in body
    assert 'CHF' not in body and 'price' not in body and 'rappen' not in body
    assert 'Allergenangaben nicht erfasst' in body
    assert '/admin/patienten/menu?week=2026-08-31' in body
    staff_body = client.get('/admin/cafeteria/menues').get_data(as_text=True)
    assert 'Cafeteria exklusiv' in staff_body and 'Patienten exklusiv' not in staff_body
    with database_engine.connect() as connection:
        assert before == connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()
        assert items_before == connection.execute(text('SELECT id,row_version FROM cafeteria.menu_items ORDER BY id')).all()


@pytest.mark.parametrize('query', ['%', '_', '\\'])
def test_search_treats_wildcards_as_literal_and_searches_components(client, database_engine, query):
    scope = _scope(client, database_engine)
    payload = _payload()
    payload['assignments'] = [{'component_public_id': None, 'component_text': 'Beilage ' + query}]
    _save(database_engine, scope, title='Komponententreffer', payload=payload)
    _save(database_engine, scope, week=WEEK + timedelta(days=7), title='Titel ' + query)
    _save(database_engine, scope, week=WEEK + timedelta(days=14), title='Ohne Suchzeichen')
    response = client.get('/admin/patienten/menues', query_string={'q': query})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Komponententreffer' in body and 'Titel ' + query in body
    assert 'Ohne Suchzeichen' not in body


def test_pagination_keeps_duplicate_titles_as_individual_occurrences(client, database_engine):
    scope = _scope(client, database_engine)
    for offset in range(26):
        _save(database_engine, scope, week=WEEK + timedelta(weeks=offset), title='Wiederkehrendes Menü')
    first, has_next = find_menus(database_engine, scope)
    second, second_has_next = find_menus(database_engine, scope, page=2)
    assert len(first) == 24 and has_next
    assert len(second) == 2 and not second_has_next
    assert not ({row['id'] for row in first} & {row['id'] for row in second})
    assert first[0]['service_date'] > first[-1]['service_date'] > second[0]['service_date']
    body = client.get('/admin/patienten/menues?q=Wiederkehrendes&page=2').get_data(as_text=True)
    assert body.count('data-menu-id=') == 2 and 'page=1' in body and 'page=3' not in body
    assert 'q=Wiederkehrendes' in body


def test_metadata_is_escaped_and_stale_component_review_is_visible(client, database_engine):
    scope = _scope(client, database_engine)
    component = create_component(database_engine, scope, 'side', 'Beilage', None, 'current', [], [])
    payload = _payload()
    payload.update(
        description='<b>Beschreibung</b>', note='<script>Hinweis</script>',
        assignments=[{'component_public_id': str(component['public_id']), 'component_text': None}],
        allergens=[{'code': 'GLUTEN', 'presence': 'contains'}, {'code': 'MILK', 'presence': 'may_contain'}],
        labels=['VEGETARIAN'],
    )
    _save(database_engine, scope, payload=payload)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.menu_components SET row_version=row_version+1'))
        connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))
    response = client.get('/admin/patienten/menues')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '&lt;b&gt;Beschreibung&lt;/b&gt;' in body
    assert '&lt;script&gt;Hinweis&lt;/script&gt;' in body
    assert 'Enthält: ' in body and 'Kann enthalten: ' in body
    assert 'Kartoffel: CH' in body and 'Vegetarisch' in body
    assert 'Komponenten geändert · Erneute Prüfung erforderlich' in body


@pytest.mark.parametrize('query', [
    'profile=staff_guest', 'profile_scope=common', 'location_id=2',
    'page=0', 'page=-1', 'page=10001', 'page=1&page=2', 'q=a&q=b', 'q=' + 'a' * 201,
])
def test_invalid_search_and_scope_overrides_are_rejected(client, query):
    assert client.get('/admin/patienten/menues?' + query).status_code == 400


def test_collection_requires_capability_and_fails_closed_for_bad_location(app, client, database_engine):
    assert app.test_client().get('/admin/patienten/menues').status_code == 401
    denied, _ = _login(app, database_engine, [])
    assert denied.get('/admin/patienten/menues').status_code == 401
    allowed, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    scope = _scope(allowed, database_engine)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
    assert allowed.get('/admin/patienten/menues').status_code == 503
    with pytest.raises(ComponentCatalogConfigurationError):
        find_menus(database_engine, scope)


def test_empty_collection_has_navigation_and_empty_state(client):
    body = client.get('/admin/patienten/menues').get_data(as_text=True)
    assert 'Noch keine Menüs auf dieser Seite.' in body
    assert '/admin/patienten/menues" class="nav-link active" aria-current="page"' in body
    assert '/admin/patienten/komponenten' in body and 'Zum Wochenplan' in body
    for family in ('cafeteria', 'patienten'):
        overview = client.get('/admin/' + family).get_data(as_text=True)
        assert '/admin/' + family + '/menues' in overview
        assert '/admin/' + family + '/komponenten' in overview
