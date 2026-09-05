from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.api.v1_routes import bp as api_v1_bp
from cafeteria.api_keys import API_KEY_SCOPES, create_api_key, revoke_api_key
from cafeteria.workflow import load_draft

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)
WEEK = dt.date(2026, 8, 31)
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


def _role_database_url(role_name: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role_name,
        password=password,
    ).render_as_string(hide_password=False)


@pytest.fixture
def database_engines() -> Iterator[tuple[Engine, Engine]]:
    assert DATABASE_URL is not None
    owner_engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(owner_engine)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        yield owner_engine, app_engine
    finally:
        app_engine.dispose()
        _drop_schema(owner_engine)
        owner_engine.dispose()


@pytest.fixture
def app(database_engines: tuple[Engine, Engine]) -> Flask:
    owner_engine, app_engine = database_engines
    application = Flask(__name__)
    application.config.update(SECRET_KEY='api-keyed-test-secret')
    application.extensions['cafeteria_db'] = app_engine
    application.extensions['cafeteria_auth_issuer_db'] = owner_engine
    application.register_blueprint(api_v1_bp)
    return application


def _login(app: Flask, owner_engine: Engine) -> tuple[FlaskClient, int]:
    user_id = database.upsert_entra_user(
        owner_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000001',
            'oid': '00000000-0000-0000-0000-000000000071',
            'sub': 'api-keyed-admin',
            'name': 'API Admin',
            'preferred_username': 'api-keyed-admin@example.invalid',
        },
        ['Cafeteria.Admin'],
    )
    with owner_engine.connect() as connection:
        authz_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
            {'id': user_id},
        ).scalar_one()
    client = app.test_client()
    with client.session_transaction() as current:
        current['user'] = {'id': user_id, 'name': 'API Admin'}
        current['authz_version'] = authz_version
    return client, user_id


def _authorization(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _prepare_api_data(
    app: Flask,
    database_engines: tuple[Engine, Engine],
) -> tuple[FlaskClient, int, str, str, str]:
    owner_engine, app_engine = database_engines
    client, admin_id = _login(app, owner_engine)
    load_draft(owner_engine, 'staff_guest', WEEK, actor_id=admin_id)
    load_draft(owner_engine, 'patient', WEEK, actor_id=admin_id)
    with owner_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.menu_weeks SET title=:title WHERE week_start=:week_start'),
            {'title': 'Wochenplan', 'week_start': WEEK},
        )
        patient_row_version = connection.execute(
            text(
                '''
                SELECT w.row_version
                FROM cafeteria.menu_weeks w
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                WHERE p.code='patient' AND w.week_start=:week_start
                '''
            ),
            {'week_start': WEEK},
        ).scalar_one()
    record, token = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='API Vorschau',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )
    revoked_record, revoked_token = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='Widerrufen',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )
    assert revoke_api_key(app_engine, actor_id=admin_id, public_id=revoked_record.public_id)
    return client, int(patient_row_version), record.public_id, token, revoked_token


def test_key_authentication_rejects_missing_malformed_and_revoked_credentials(
    app: Flask,
    database_engines: tuple[Engine, Engine],
) -> None:
    client, _, _, _, revoked_token = _prepare_api_data(app, database_engines)

    for headers in ({}, {'Authorization': 'bearer invalid'}, _authorization(revoked_token)):
        response = client.get('/api/v1/keys/me', headers=headers)
        assert response.status_code == 401
        assert response.get_json()['error'] == 'unauthorized'
        assert response.headers['WWW-Authenticate'] == 'Bearer realm="dishboard-api"'
        assert response.headers['Cache-Control'] == 'no-store'


def test_key_identity_updates_last_used_and_rejects_query_parameters(
    app: Flask,
    database_engines: tuple[Engine, Engine],
) -> None:
    client, _, public_id, token, _ = _prepare_api_data(app, database_engines)
    owner_engine, _ = database_engines
    with owner_engine.connect() as connection:
        assert connection.execute(
            text('SELECT last_used_at FROM cafeteria.api_keys WHERE public_id=:public_id'),
            {'public_id': public_id},
        ).scalar_one() is None

    response = client.get('/api/v1/keys/me', headers=_authorization(token))

    assert response.status_code == 200
    assert response.get_json() == {
        'expires_at': None,
        'label': 'API Vorschau',
        'public_id': public_id,
        'scopes': ['preview.read'],
    }
    assert response.headers['Cache-Control'] == 'no-store'
    with owner_engine.connect() as connection:
        assert connection.execute(
            text('SELECT last_used_at FROM cafeteria.api_keys WHERE public_id=:public_id'),
            {'public_id': public_id},
        ).scalar_one() is not None

    query_response = client.get('/api/v1/keys/me?extra=1', headers=_authorization(token))
    assert query_response.status_code == 400
    assert query_response.get_json()['error'] == 'query_parameters_not_allowed'
    assert query_response.headers['Cache-Control'] == 'no-store'


def test_keyed_weeks_and_read_only_patient_preview(
    app: Flask,
    database_engines: tuple[Engine, Engine],
) -> None:
    client, row_version, _, token, _ = _prepare_api_data(app, database_engines)
    owner_engine, _ = database_engines
    headers = _authorization(token)

    weeks_response = client.get('/api/v1/weeks/cafeteria', headers=headers)
    assert weeks_response.status_code == 200
    assert weeks_response.headers['Cache-Control'] == 'no-store'
    assert weeks_response.get_json() == {
        'channel': 'cafeteria',
        'weeks': [
            {
                'status': 'empty',
                'title': 'Wochenplan',
                'week_end': '2026-09-06',
                'week_start': '2026-08-31',
                'workflow_state': 'draft',
            },
        ],
    }

    preview_response = client.get(
        f'/api/v1/weeks/patienten/{WEEK.isoformat()}/preview',
        headers=headers,
    )
    preview_body = preview_response.get_data(as_text=True).lower()
    assert preview_response.status_code == 200
    assert preview_response.headers['Cache-Control'] == 'no-store'
    assert preview_response.headers['X-Draft-Row-Version'] == str(row_version)
    assert preview_response.get_json()['channel'] == 'patienten'
    assert '"prices"' not in preview_body
    assert 'chf' not in preview_body
    assert 'rappen' not in preview_body
    assert 'kosten' not in preview_body

    invalid_response = client.get(
        '/api/v1/weeks/patienten/2026-09-01/preview',
        headers=headers,
    )
    assert invalid_response.status_code == 400
    assert invalid_response.get_json()['error'] == 'invalid_week_start'
    assert invalid_response.headers['Cache-Control'] == 'no-store'

    with owner_engine.connect() as connection:
        week_count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one()
    missing_response = client.get(
        '/api/v1/weeks/patienten/2030-01-07/preview',
        headers=headers,
    )
    assert missing_response.status_code == 404
    assert missing_response.get_json()['error'] == 'week_not_found'
    assert missing_response.headers['Cache-Control'] == 'no-store'
    with owner_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == week_count
