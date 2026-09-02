from __future__ import annotations

import os

import pytest

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


def test_cafeteria_tuesday_has_costs(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    body = app.test_client().get('/cafeteria/heute/').get_data(as_text=True)
    assert 'Kichererbsen-Curry' in body
    assert 'CHF 11.00' in body
    assert 'CHF 16.60' in body


def test_patient_sunday_has_dinner_without_cost_tokens(app):
    app.config['DEMO_TODAY'] = '2026-09-06'
    response = app.test_client().get('/patienten/heute/')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Pastetli mit Brätkügeli' in body
    for token in ('CHF', '0.00', 'Intern', 'Extern'):
        assert token not in body


def test_cafeteria_sunday_is_closed_and_never_falls_back(app):
    app.config['DEMO_TODAY'] = '2026-09-06'
    response = app.test_client().get('/signage/cafeteria/tag')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Cafeteria' in body and 'geschlossen' in body
    assert 'Pastetli mit Brätkügeli' not in body
    assert 'Pouletbrust an Kräutersauce' not in body


def test_week_channels_do_not_mix(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()
    cafeteria = client.get('/signage/cafeteria/woche').get_data(as_text=True)
    patient = client.get('/signage/patienten/woche').get_data(as_text=True)
    assert 'Abend' not in cafeteria
    assert 'Ofen-Pouletschenkel' not in cafeteria
    assert 'Abend' in patient
    assert 'Ofen-Pouletschenkel' in patient
    assert 'CHF' not in patient


def test_day_and_week_use_same_revision(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()
    day = client.get('/signage/patienten/tag')
    week = client.get('/signage/patienten/woche')
    assert day.headers['X-Snapshot-Revision'] == 'PAT-2026-KW36-R1'
    assert week.headers['X-Snapshot-Revision'] == 'PAT-2026-KW36-R1'


def test_public_and_player_date_query_is_rejected(app):
    app.config['DEMO_TODAY'] = '2026-09-01'
    client = app.test_client()
    assert client.get('/cafeteria/heute/?date=2026-09-02').status_code == 400
    assert client.get('/signage/patienten/tag?date=2026-09-02').status_code == 400
    assert client.get('/api/v1/published/patienten?date=2026-09-02').status_code == 400
