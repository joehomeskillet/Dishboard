from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool
from werkzeug.datastructures import MultiDict

from cafeteria import db as database
from cafeteria.admin.workflow_routes import REVIEW_HINT
from test_admin_workflow_routes import (
    APP_PASSWORD,
    BACKUP_PASSWORD,
    DATABASE_URL,
    ISSUER_PASSWORD,
    ROOT,
    _drop_schema,
    _hidden,
    _login,
    _register,
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


def _create_fields() -> MultiDict[str, str]:
    return MultiDict([
        ('_csrf', 'workflow-csrf'),
        ('category', 'side'),
        ('name', 'Kartoffelstock'),
        ('origin_country_code', 'CH'),
        ('target_scope', 'current'),
        ('label_code', 'VEGAN'),
        ('allergen_code', 'GLUTEN'),
        ('allergen_presence', 'contains'),
    ])


def _create_csrf(client, family: str) -> str:
    page = client.get(f'/admin/{family}/komponenten')
    assert page.status_code == 200
    return _hidden(page.get_data(as_text=True), '_csrf')


def test_component_create_update_archive_unarchive_exact_forms(client, database_engine: Engine) -> None:
    fields = _create_fields()
    fields['_csrf'] = _create_csrf(client, 'patienten')
    created = client.post('/admin/patienten/komponenten', data=fields)
    assert created.status_code == 303
    location = created.headers['Location']
    detail = client.get(location, follow_redirects=False)
    assert detail.status_code == 200
    assert REVIEW_HINT in detail.get_data(as_text=True)
    body = detail.get_data(as_text=True)
    assert 'data-profile-scope="patient"' in body
    detail_csrf = _hidden(body, '_csrf')
    version = _hidden(body, 'row_version')
    public_id = body.split('data-public-id="', 1)[1].split('"', 1)[0]
    updated = client.post(f'/admin/patienten/komponenten/{public_id}', data=MultiDict([
        ('_csrf', detail_csrf),
        ('category', 'side'),
        ('name', 'Kartoffelstock'),
        ('origin_country_code', 'CH'),
        ('row_version', version),
        ('label_code', 'VEGAN'),
        ('allergen_code', 'GLUTEN'),
        ('allergen_presence', 'contains'),
    ]))
    assert updated.status_code == 303
    with_target = client.post(f'/admin/patienten/komponenten/{public_id}', data=MultiDict([
        ('_csrf', detail_csrf),
        ('category', 'side'),
        ('name', 'Kartoffelstock'),
        ('origin_country_code', 'CH'),
        ('row_version', version),
        ('target_scope', 'common'),
    ]))
    assert with_target.status_code == 400
    shown = client.get(f'/admin/patienten/komponenten/{public_id}')
    version = _hidden(shown.get_data(as_text=True), 'row_version')
    archived = client.post(
        f'/admin/patienten/komponenten/{public_id}/archive',
        data={'_csrf': detail_csrf, 'row_version': version},
    )
    assert archived.status_code == 303
    shown = client.get(f'/admin/patienten/komponenten/{public_id}')
    assert 'data-active="0"' in shown.get_data(as_text=True)
    version = _hidden(shown.get_data(as_text=True), 'row_version')
    restored = client.post(
        f'/admin/patienten/komponenten/{public_id}/unarchive',
        data={'_csrf': detail_csrf, 'row_version': version},
    )
    assert restored.status_code == 303
    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_components')).scalar_one()
        deleted = connection.execute(
            text('SELECT count(*) FROM cafeteria.menu_components WHERE active')
        ).scalar_one()
    assert count == 1
    assert deleted == 1


def test_component_create_rejects_duplicate_and_profile_keys(client, database_engine: Engine) -> None:
    token = _create_csrf(client, 'patienten')
    duplicate = _create_fields()
    duplicate['_csrf'] = token
    duplicate.add('category', 'meat')
    mismatched = MultiDict([
        ('_csrf', token),
        ('category', 'side'),
        ('name', 'Reis'),
        ('origin_country_code', 'CH'),
        ('target_scope', 'current'),
        ('allergen_code', 'GLUTEN'),
        ('allergen_code', 'MILK'),
        ('allergen_presence', 'contains'),
    ])
    profiled = _create_fields()
    profiled['_csrf'] = token
    profiled.add('profile', 'staff_guest')
    scoped = _create_fields()
    scoped['_csrf'] = token
    scoped.add('profile_scope', 'patient')
    internal = _create_fields()
    internal['_csrf'] = token
    internal.add('id', '1')
    before = None
    with database_engine.connect() as connection:
        before = connection.execute(text('SELECT count(*) FROM cafeteria.menu_components')).scalar_one()
    assert client.post('/admin/patienten/komponenten', data=duplicate).status_code == 400
    assert client.post('/admin/patienten/komponenten', data=mismatched).status_code == 400
    assert client.post('/admin/patienten/komponenten', data=profiled).status_code == 400
    assert client.post('/admin/patienten/komponenten', data=scoped).status_code == 400
    assert client.post('/admin/patienten/komponenten', data=internal).status_code == 400
    with database_engine.connect() as connection:
        after = connection.execute(text('SELECT count(*) FROM cafeteria.menu_components')).scalar_one()
    assert after == before


def test_component_detail_uses_public_id_and_masks_unknown(client) -> None:
    fields = _create_fields()
    fields['_csrf'] = _create_csrf(client, 'cafeteria')
    created = client.post('/admin/cafeteria/komponenten', data=fields)
    public_id = created.headers['Location'].rsplit('/', 1)[-1]
    found = client.get(f'/admin/cafeteria/komponenten/{public_id}')
    missing = client.get('/admin/cafeteria/komponenten/00000000-0000-0000-0000-000000000099')
    other = client.get(f'/admin/patienten/komponenten/{public_id}')
    assert found.status_code == 200
    assert 'data-profile-scope="staff_guest"' in found.get_data(as_text=True)
    assert missing.status_code == 404
    assert other.status_code == 404
