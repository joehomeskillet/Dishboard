from __future__ import annotations

import cafeteria.admin.workflow_routes  # noqa: F401
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

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


def _drop_schema(engine) -> None:
    # Demo seed cannot be re-applied over published revisions; start and end from an empty schema.
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


@pytest.fixture(scope='module')
def app():
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
    _drop_schema(engine)
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
    yield application
    _drop_schema(engine)
    engine.dispose()


def test_metadata(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()
    resp = client.get('/fhir/metadata')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == 'application/fhir+json; charset=utf-8'
    assert resp.headers['Cache-Control'] == 'public, max-age=300'
    data = resp.get_json()
    assert data['resourceType'] == 'CapabilityStatement'


def test_search_nutrition_product(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()

    # ohne channel
    resp = client.get('/fhir/NutritionProduct')
    assert resp.status_code == 200
    assert 'X-Snapshot-Revision' in resp.headers
    data = resp.get_json()
    assert data['resourceType'] == 'Bundle'

    # mit channel
    resp_pat = client.get('/fhir/NutritionProduct?channel=patienten')
    assert resp_pat.status_code == 200
    data_pat = resp_pat.get_json()

    # mit date filter
    resp_date = client.get('/fhir/NutritionProduct?channel=patienten&date=2026-09-01')
    assert resp_date.status_code == 200
    data_date = resp_date.get_json()
    assert len(data_date['entry']) < len(data_pat['entry'])

    # unbekannter Parameter
    resp_bad = client.get('/fhir/NutritionProduct?foo=bar')
    assert resp_bad.status_code == 400
    assert resp_bad.headers['Cache-Control'] == 'no-store'
    assert resp_bad.get_json()['resourceType'] == 'OperationOutcome'


def test_read_nutrition_product(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()

    # get a product id from search
    search_resp = client.get('/fhir/NutritionProduct?channel=patienten').get_json()
    product_id = search_resp['entry'][0]['resource']['id']

    resp = client.get(f'/fhir/NutritionProduct/{product_id}')
    assert resp.status_code == 200
    assert resp.headers['Cache-Control'] == 'public, max-age=60, stale-if-error=86400'
    data = resp.get_json()
    assert data['id'] == product_id

    # 404
    resp_404 = client.get('/fhir/NutritionProduct/not-a-product')
    assert resp_404.status_code == 404


def test_composition_read_and_document(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()

    # search comp
    search_resp = client.get('/fhir/Composition?channel=patienten').get_json()
    comp_id = search_resp['entry'][0]['resource']['id']

    # read comp
    resp = client.get(f'/fhir/Composition/{comp_id}')
    assert resp.status_code == 200

    # read document
    resp_doc = client.get(f'/fhir/Composition/{comp_id}/$document')
    assert resp_doc.status_code == 200
    data = resp_doc.get_json()
    assert data['resourceType'] == 'Bundle'
    assert data['type'] == 'document'


def test_patient_rule_on_http_bodies(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()

    # patient search
    pat_search_body = client.get('/fhir/NutritionProduct?channel=patienten').get_data(as_text=True)

    # read one patient product
    search_resp = client.get('/fhir/NutritionProduct?channel=patienten').get_json()
    product_id = search_resp['entry'][0]['resource']['id']
    pat_read_body = client.get(f'/fhir/NutritionProduct/{product_id}').get_data(as_text=True)

    # patient comp doc
    comp_search = client.get('/fhir/Composition?channel=patienten').get_json()
    comp_id = comp_search['entry'][0]['resource']['id']
    pat_doc_body = client.get(f'/fhir/Composition/{comp_id}/$document').get_data(as_text=True)

    forbidden_terms = ['preis', 'price', 'chf', 'rappen', 'kosten', 'money', 'currency', 'intern', 'extern', '0.00']

    bodies = [pat_search_body, pat_read_body, pat_doc_body]
    for body in bodies:
        lower_body = body.lower()
        for term in forbidden_terms:
            assert term not in lower_body, f"Forbidden term '{term}' found in HTTP body"
