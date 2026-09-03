from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.workflow_partial_store import persist_menu_item
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
    _payload,
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


def test_preview_is_last_saved_without_publication_fallback(
    client, database_engine: Engine, app: Flask,
) -> None:
    missing = client.get(f'/admin/patienten/preview?week={DAY}')
    assert missing.status_code == 404
    saved = client.post('/admin/patienten/menu', data=_menu_form(title='Gespeicherter Titel'))
    assert saved.status_code == 303
    preview = client.get(f'/admin/patienten/preview?week={DAY}')
    body = preview.get_data(as_text=True)
    assert preview.status_code == 200
    assert preview.headers['Cache-Control'] == 'no-store'
    assert 'PREVIEW' in body
    assert 'data-preview="last-saved"' in body
    assert 'Gespeicherter Titel' in body
    assert 'profile=patient' not in body
    published_snapshot = json.loads(
        (ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json').read_text(encoding='utf-8')
    )
    published_snapshot['title'] = 'LIVE-SNAPSHOT-TITEL'
    with database_engine.begin() as connection:
        week_id = connection.execute(text('SELECT id FROM cafeteria.menu_weeks')).scalar_one()
        actor_id = _session_actor_id(client)
        connection.execute(text(
            "UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:id"
        ), {'id': week_id})
        connection.execute(text(
            '''
            INSERT INTO cafeteria.publication_revisions(
                menu_week_id, revision_number, revision_code, snapshot_json, published_by,
                profile_id, location_id, week_start
            )
            SELECT :week_id, 1, 'PAT-2026-KW36-R1', CAST(:snapshot AS jsonb), :actor_id,
                   w.profile_id, w.location_id, w.week_start
            FROM cafeteria.menu_weeks w WHERE w.id=:week_id
            '''
        ), {
            'week_id': week_id,
            'actor_id': actor_id,
            'snapshot': json.dumps(published_snapshot, ensure_ascii=False),
        })
    live = client.get(f'/admin/patienten/preview?week={DAY}')
    live_body = live.get_data(as_text=True)
    assert live.status_code == 200
    assert 'Gespeicherter Titel' in live_body
    assert 'LIVE-SNAPSHOT-TITEL' not in live_body
    assert 'data-workflow-state="published"' in live_body


@pytest.mark.parametrize('state', ('draft', 'ready', 'published', 'archived'))
def test_preview_allows_every_persisted_workflow_state(
    client, database_engine: Engine, app: Flask, state: str,
) -> None:
    user_id = _session_actor_id(client)
    persist_menu_item(
        app.extensions['cafeteria_db'],
        _scope(database_engine, user_id),
        WEEK,
        DAY,
        'LUNCH',
        'MENU_1',
        _payload(),
        0,
    )
    with database_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.menu_weeks SET workflow_state=:state'),
            {'state': state},
        )
    response = client.get(f'/admin/patienten/preview?week={DAY}')
    assert response.status_code == 200
    assert f'data-workflow-state="{state}"' in response.get_data(as_text=True)
    assert response.headers['Cache-Control'] == 'no-store'


def test_preview_rejects_profile_override(client, database_engine: Engine, app: Flask) -> None:
    client.post('/admin/patienten/menu', data=_menu_form())
    response = client.get(f'/admin/patienten/preview?week={DAY}&profile=staff_guest')
    assert response.status_code == 400
