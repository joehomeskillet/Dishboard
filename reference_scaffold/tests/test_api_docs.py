from __future__ import annotations

import os
import re

import pytest

DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

CSP_DOCS = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; frame-ancestors 'none'"
)
STATIC_REF = re.compile(
    r'<(?:link[^>]*\brel=["\']stylesheet["\'][^>]*\bhref|script[^>]*\bsrc)=["\']([^"\']+)["\']',
    re.I,
)
INLINE_SCRIPT = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>.*?</script>', re.I | re.S)
STYLE_ATTR = re.compile(r'\sstyle=')

if DATABASE_URL:
    os.environ['DATABASE_URL'] = DATABASE_URL
    os.environ['DEMO_MODE'] = 'true'
    os.environ['SEED_DEMO'] = 'true'
    os.environ['DEMO_TODAY'] = '2026-09-01'
    os.environ['SESSION_COOKIE_SECURE'] = 'false'
    os.environ['SESSION_REDIS_URL'] = ''
    os.environ['FLASK_SECRET_KEY'] = 'test-only-secret'
    os.environ['POSTGRES_AUTH_ISSUER_PASSWORD'] = ISSUER_PASSWORD

    from cafeteria import create_app
    from cafeteria.config import Config
    from cafeteria.db import init_database


@pytest.fixture(scope='module')
def app():
    cfg = Config()
    init_database(
        cfg.DATABASE_URL,
        cfg.SCHEMA_PATH,
        cfg.SEED_PATH,
        demo_seed_path=cfg.DEMO_SEED_PATH,
        permissions_path=cfg.PERMISSIONS_PATH,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
        seed_demo=True,
    )
    application = create_app()
    application.config.update(TESTING=True)
    return application


def test_docs_page_renders_swagger_ui(app):
    client = app.test_client()
    response = client.get('/api/v1/docs')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="swagger-ui"' in body
    assert response.headers.get('Content-Security-Policy') == CSP_DOCS
    for match in STATIC_REF.findall(body):
        assert match.startswith('/static/'), match
    assert not INLINE_SCRIPT.search(body)
    assert not STYLE_ATTR.search(body)


@pytest.mark.parametrize('path', ['/api/v1/docs', '/api/v1/openapi.json'])
def test_query_parameters_rejected(app, path):
    response = app.test_client().get(f'{path}?x=1')
    assert response.status_code == 400
    assert response.get_json() == {'error': 'query_parameters_not_allowed'}
    assert response.headers.get('Cache-Control') == 'no-store'


def test_openapi_json_returns_spec(app):
    response = app.test_client().get('/api/v1/openapi.json')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['openapi'] == '3.1.0'
    assert response.headers.get('Cache-Control') == 'public, max-age=300'


@pytest.mark.parametrize(
    'asset',
    [
        'swagger-ui.css',
        'swagger-ui-bundle.js',
        'LICENSE',
    ],
)
def test_vendor_assets_served(app, asset):
    response = app.test_client().get(f'/static/vendor/swagger-ui/{asset}')
    assert response.status_code == 200
    assert response.data
