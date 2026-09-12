from __future__ import annotations

import re
from datetime import date, timedelta
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.admin import workflow_routes
from cafeteria.security import csrf_token

from test_admin_workflow_routes import (
    APP_PASSWORD,
    BACKUP_PASSWORD,
    DATABASE_URL,
    ISSUER_PASSWORD,
    ROOT,
    _drop_schema,
    _login,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def _register(application: Flask) -> Flask:
    from cafeteria.admin import api_routes  # noqa: F401

    auth = Blueprint('auth', __name__)
    auth.add_url_rule('/logout', endpoint='logout', view_func=lambda: '')
    signage = Blueprint('signage', __name__)
    signage.add_url_rule('/preview/cafeteria', endpoint='cafeteria_week', view_func=lambda: '')
    signage.add_url_rule('/preview/patient', endpoint='patient_week', view_func=lambda: '')
    application.register_blueprint(auth)
    application.register_blueprint(signage)
    application.register_blueprint(workflow_routes.bp)
    application.context_processor(lambda: {'csrf_token': csrf_token})
    return application


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
def admin_client(app: Flask, database_engine: Engine):
    return _login(app, database_engine, ['Cafeteria.Admin'])[0]


@pytest.fixture
def editor_client(app: Flask, database_engine: Engine):
    return _login(app, database_engine, ['Cafeteria.Editor'])[0]


def _create_form(csrf: str = 'workflow-csrf') -> dict[str, str]:
    return {
        '_csrf': csrf,
        'label': 'Integrations-Test',
        'scopes': 'preview.read',
        'channels': 'cafeteria',
        'expires_at': (date.today() + timedelta(days=30)).isoformat(),
    }


def test_admin_sees_api_page_with_links_and_status(admin_client) -> None:
    response = admin_client.get('/admin/api')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '/api/v1/docs' in body
    assert '/api/v1/openapi.json' in body
    assert '/fhir/metadata' in body
    assert 'data-api-status' in body


def test_editor_gets_403(editor_client) -> None:
    assert editor_client.get('/admin/api').status_code == 403


def test_create_shows_plaintext_once(admin_client) -> None:
    created = admin_client.post('/admin/api/keys', data=_create_form(), follow_redirects=True)
    body = created.get_data(as_text=True)
    assert created.status_code == 200
    assert 'data-new-key' in body
    assert re.search(r'dbk_[A-Za-z0-9_-]{32}', body)
    assert 'Dieser Schlüssel wird nur einmal angezeigt.' in body
    second = admin_client.get('/admin/api')
    assert second.status_code == 200
    assert 'data-new-key' not in second.get_data(as_text=True)


def test_revoke_changes_status(admin_client) -> None:
    admin_client.post('/admin/api/keys', data=_create_form(), follow_redirects=True)
    overview = admin_client.get('/admin/api')
    match = re.search(r'data-key-id="([^"]+)"', overview.get_data(as_text=True))
    assert match is not None
    public_id = match.group(1)
    revoked = admin_client.post(
        f'/admin/api/keys/{public_id}/revoke',
        data={'_csrf': 'workflow-csrf'},
        follow_redirects=True,
    )
    assert revoked.status_code == 200
    body = revoked.get_data(as_text=True)
    assert f'data-key-id="{public_id}"' in body
    assert 'data-key-state="revoked"' in body
    assert 'data-status="revoked"' in body


def test_csrf_failure_returns_400(admin_client) -> None:
    response = admin_client.post('/admin/api/keys', data=_create_form(csrf='invalid'))
    assert response.status_code == 400


def test_query_parameters_return_400(admin_client) -> None:
    assert admin_client.get('/admin/api?debug=1').status_code == 400


def test_page_render_contract(admin_client) -> None:
    body = admin_client.get('/admin/api').get_data(as_text=True)
    assert 'data-page="api"' in body
    assert 'table[data-api-keys]' not in body
    assert 'data-api-keys' in body
    assert 'id="api-key-create"' in body
    assert '/api/v1/docs' in body
    assert '/api/v1/openapi.json' in body
    assert '/fhir/metadata' in body
    assert re.search(r'<script[^>]*>[^<]+</script>', body, re.I) is None
    assert 'style=' not in body
