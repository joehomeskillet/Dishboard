from __future__ import annotations

import datetime as dt
import html
import io
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria.admin import routes as admin_routes
from cafeteria.db import init_database
from cafeteria.security import csrf_token

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
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
        SECRET_KEY='csv-import-test-secret',
        LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-02',
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    auth = Blueprint('auth', __name__)
    auth.add_url_rule('/logout', endpoint='logout', view_func=lambda: '')
    signage = Blueprint('signage', __name__)
    signage.add_url_rule('/preview/cafeteria', endpoint='cafeteria_week', view_func=lambda: '')
    signage.add_url_rule('/preview/patient', endpoint='patient_week', view_func=lambda: '')
    application.register_blueprint(auth)
    application.register_blueprint(signage)
    application.register_blueprint(admin_routes.bp)

    @application.template_filter('date_short')
    def date_short(value: str) -> str:
        parsed = dt.date.fromisoformat(value)
        return f'{parsed.day}. {parsed.month}.'

    @application.template_filter('iso_week')
    def iso_week(value: str) -> int:
        return dt.date.fromisoformat(value).isocalendar().week

    @application.context_processor
    def inject_csrf() -> dict[str, object]:
        return {'csrf_token': csrf_token}

    return application


@pytest.fixture
def client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as current:
        current['user'] = {'id': 1, 'name': 'Küche'}
        current['roles'] = ['Cafeteria.Admin']
        current['_csrf_token'] = 'csv-import-csrf'
    return client


def _example(name: str) -> bytes:
    return (ROOT / 'csv' / name).read_bytes()


def _preview(client, payload: bytes, filename: str = 'menu.csv'):
    return client.post(
        '/admin/import-preview',
        data={
            '_csrf': 'csv-import-csrf',
            'file': (io.BytesIO(payload), filename),
        },
        content_type='multipart/form-data',
    )


def _token(response) -> str:
    match = re.search(r'name="import_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match is not None
    return html.unescape(match.group(1))


def test_patient_preview_is_required_and_does_not_write_or_expose_cost_vocabulary(
    client,
    database_engine: Engine,
) -> None:
    response = _preview(client, _example('menu_patient_example.csv'))
    body = response.get_data(as_text=True)

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert response.status_code == 200
    assert 'Bereit zum Import' in body
    assert 'name="import_token"' in body
    assert re.search(r'CHF|Intern|Extern|0\.00|price|rappen', body, re.I) is None
    assert count == 0


def test_patient_import_persists_complete_grid_without_prices(client, database_engine: Engine) -> None:
    preview = _preview(client, _example('menu_patient_example.csv'))

    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id),
                       count(DISTINCT c.menu_item_id)
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                LEFT JOIN cafeteria.menu_item_components c ON c.menu_item_id=i.id
                '''
            )
        ).one()
    assert response.status_code == 303
    assert response.headers['Location'].endswith('/admin/patienten')
    assert tuple(shape) == (14, 28, 0, 28)


def test_cafeteria_import_persists_five_lunches_and_both_prices(
    client,
    database_engine: Engine,
) -> None:
    preview = _preview(client, _example('menu_cafeteria_example.csv'))
    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id),
                       min(pr.internal_rappen), max(pr.external_rappen)
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                '''
            )
        ).one()
        meals = connection.execute(
            text(
                '''
                SELECT DISTINCT mp.code
                FROM cafeteria.menu_services s
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                '''
            )
        ).scalars().all()
    assert response.status_code == 303
    assert tuple(shape[:3]) == (5, 10, 10)
    assert shape[3] > 0
    assert shape[4] >= shape[3]
    assert meals == ['LUNCH']


def test_invalid_patient_header_reports_position_without_import_action_or_write(
    client,
    database_engine: Engine,
) -> None:
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    lines = source.splitlines()
    invalid = ('\n'.join([lines[0] + ';preis_mitarbeitende_chf', *[line + ';10.00' for line in lines[1:]]])).encode()

    response = _preview(client, invalid)
    body = response.get_data(as_text=True)

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert response.status_code == 200
    assert 'Zeile 1' in body
    assert 'Spalte 18' in body
    assert 'name="import_token"' not in body
    assert count == 0


def test_invalid_title_reports_exact_line_and_column(client, database_engine: Engine) -> None:
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    invalid = source.replace(';Pouletgeschnetzeltes Paprika;', ';;', 1).encode()

    response = _preview(client, invalid)

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Zeile 2' in body
    assert 'Spalte 8' in body
    assert 'name="import_token"' not in body
    assert count == 0


def test_import_rejects_tampered_token_and_missing_csrf_without_partial_write(
    client,
    database_engine: Engine,
) -> None:
    preview = _preview(client, _example('menu_cafeteria_example.csv'))
    token = _token(preview)

    csrf_rejected = client.post('/admin/import', data={'import_token': token})
    token_rejected = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': token + 'tampered'},
    )

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert csrf_rejected.status_code == 400
    assert token_rejected.status_code == 400
    assert count == 0
