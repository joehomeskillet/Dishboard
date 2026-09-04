from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.workflow_partial_store import persist_week_header
from test_admin_workflow_routes import (
    APP_PASSWORD,
    BACKUP_PASSWORD,
    DATABASE_URL,
    DAY,
    ISSUER_PASSWORD,
    ROOT,
    WEEK,
    _drop_schema,
    _login,
    _menu_form,
    _overview_csrf,
    _register,
    _session_actor_id,
    _scope,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


@pytest.fixture
def app(database_engine: Engine, tmp_path: Path) -> Flask:
    application = Flask(
        __name__,
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
    )
    application.config.update(
        SECRET_KEY='workflow-test-secret',
        LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-02',
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    return _register(application)


@pytest.fixture
def client(app: Flask, database_engine: Engine):
    client_obj, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    return client_obj


def test_week_families_expose_fixed_profiles_and_grids(client) -> None:
    cafeteria = client.get(f'/admin/cafeteria?week={DAY}')
    patienten = client.get(f'/admin/patienten?week={DAY}')
    cafeteria_body = cafeteria.get_data(as_text=True)
    patient_body = patienten.get_data(as_text=True)
    assert cafeteria.status_code == 200
    assert patienten.status_code == 200
    assert 'data-profile="staff_guest"' in cafeteria_body
    assert 'data-profile="patient"' in patient_body
    assert cafeteria_body.count('data-meal="LUNCH"') == 10
    assert 'data-meal="DINNER"' not in cafeteria_body
    assert patient_body.count('data-meal="LUNCH"') == 14
    assert patient_body.count('data-meal="DINNER"') == 14
    assert 'Samstag und Sonntag: Cafeteria geschlossen.' in cafeteria_body
    assert cafeteria.headers['Cache-Control'] == 'no-store'


def test_patient_menu_rejects_price_fields_without_write(client, database_engine: Engine) -> None:
    form = _menu_form(
        _csrf=_overview_csrf(client),
        internal_chf='9.50',
        external_chf='14.50',
    )
    response = client.post('/admin/patienten/menu', data=form)
    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_item_prices')).scalar_one()
        items = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert response.status_code == 400
    assert count == 0
    assert items == 0


def test_cafeteria_menu_persists_rappen_from_chf(client, database_engine: Engine) -> None:
    form = _menu_form(
        _csrf=_overview_csrf(client, 'cafeteria'),
        internal_chf='9.50',
        external_chf='14.50',
    )
    response = client.post('/admin/cafeteria/menu', data=form)
    assert response.status_code == 303
    with database_engine.connect() as connection:
        row = connection.execute(
            text('SELECT internal_rappen, external_rappen FROM cafeteria.menu_item_prices')
        ).one()
    assert tuple(row) == (950, 1450)


def test_header_and_service_partial_persistence(client, database_engine: Engine) -> None:
    token = _overview_csrf(client)
    header = client.post('/admin/patienten/header', data={
        '_csrf': token,
        'week': DAY,
        'row_version': '0',
        'title': 'Herbstküche',
        'shared_note': 'Frisch',
    })
    assert header.status_code == 303
    loaded = client.get(f'/admin/patienten/header?week={DAY}')
    assert loaded.status_code == 200
    assert 'Herbstküche' in loaded.get_data(as_text=True)
    service = client.post('/admin/patienten/service', data={
        '_csrf': token,
        'week': DAY,
        'day': DAY,
        'meal': 'LUNCH',
        'row_version': '0',
        'service_state': 'open',
        'notice': '',
    })
    assert service.status_code == 303
    shown = client.get(f'/admin/patienten/service?week={DAY}&day={DAY}&meal=LUNCH')
    assert shown.status_code == 200
    assert 'open' in shown.get_data(as_text=True)
    missing = client.get('/admin/patienten/header?week=2026-09-14')
    assert missing.status_code == 404


def test_stale_header_is_409_without_mutation(client, database_engine: Engine, app: Flask) -> None:
    user_id = _session_actor_id(client)
    persist_week_header(
        app.extensions['cafeteria_db'],
        _scope(database_engine, user_id),
        WEEK,
        {'title': 'Alt', 'shared_note': ''},
        0,
    )
    before = None
    with database_engine.connect() as connection:
        before = connection.execute(
            text('SELECT title, row_version FROM cafeteria.menu_weeks')
        ).one()
    response = client.post('/admin/patienten/header', data={
        '_csrf': _overview_csrf(client),
        'week': DAY,
        'row_version': '9',
        'title': 'Neu',
        'shared_note': '',
    })
    with database_engine.connect() as connection:
        after = connection.execute(
            text('SELECT title, row_version FROM cafeteria.menu_weeks')
        ).one()
    assert response.status_code == 409
    assert after == before
