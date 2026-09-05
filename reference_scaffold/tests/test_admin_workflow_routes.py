from __future__ import annotations

import datetime as dt
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import cafeteria
from flask import Blueprint, Flask
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria import roles
from cafeteria.admin import routes as admin_routes
from cafeteria.admin import workflow_routes
from cafeteria.admin import menu_collection_routes, week_management_routes  # noqa: F401 - complete shared blueprint
from cafeteria.admin.workflow_routes import ORIGIN_CONFLICT, profile_from_endpoint
from cafeteria.component_catalog_store import AdminScope, create_component, update_component
from cafeteria.security import csrf_token
from cafeteria.workflow_partial_store import persist_menu_item, persist_week_header

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)
WEEK = dt.date(2026, 8, 31)
DAY = WEEK.isoformat()
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


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


def _register(application: Flask) -> Flask:
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


def _login(app: Flask, database_engine: Engine, roles: list[str], csrf: str = 'workflow-csrf'):
    issuer_engine = app.extensions['cafeteria_auth_issuer_db']
    user_id = database.upsert_entra_user(
        issuer_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000001',
            'oid': '00000000-0000-0000-0000-000000000002',
            'sub': 'workflow-test-admin',
            'name': 'Küche',
            'preferred_username': 'workflow.admin@example.invalid',
        },
        roles,
    )
    with database_engine.begin() as connection:
        authz_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
            {'id': user_id},
        ).scalar_one()
    client = app.test_client()
    with client.session_transaction() as current:
        current['user'] = {'id': user_id, 'name': 'Küche'}
        current['authz_version'] = authz_version
        current['_csrf_token'] = csrf
    return client, user_id


def _session_actor_id(client) -> int:
    with client.session_transaction() as current:
        user = current.get('user')
    assert isinstance(user, dict)
    actor_id = user.get('id')
    assert type(actor_id) is int
    return actor_id


@pytest.fixture
def client(app: Flask, database_engine: Engine):
    client_obj, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    return client_obj


def _hidden(body: str, name: str, *, form_action: str | None = None) -> str:
    if form_action is not None:
        forms = re.findall(
            rf'<form\b(?=[^>]*\bmethod="post")(?=[^>]*\baction="{re.escape(form_action)}")'
            r'[^>]*>(.*?)</form>',
            body,
            re.S,
        )
        assert len(forms) == 1, f'Expected one POST form for {form_action}'
        body = forms[0]
    match = re.search(rf'name="{re.escape(name)}" value="([^"]*)"', body)
    assert match is not None
    return match.group(1)


def _overview_csrf(client, family: str = 'patienten') -> str:
    page = client.get(f'/admin/{family}?week={DAY}')
    assert page.status_code == 200
    form = re.search(
        rf'<form[^>]+action="/admin/{re.escape(family)}/header"[^>]*>(.*?)</form>',
        page.get_data(as_text=True),
        re.S,
    )
    assert form is not None
    return _hidden(form.group(1), '_csrf')


def _counts(engine: Engine) -> tuple[int, int, int]:
    with engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    'SELECT (SELECT count(*) FROM cafeteria.menu_items), '
                    '(SELECT count(*) FROM cafeteria.menu_weeks), '
                    '(SELECT count(*) FROM cafeteria.publication_revisions)'
                )
            ).one()
        )


def _payload(*, staff: bool = False) -> dict[str, object]:
    value: dict[str, object] = {
        'title': 'Kartoffelgratin',
        'description': '',
        'note': '',
        'allergen_mode': 'manual',
        'origin_mode': 'manual',
        'label_mode': 'manual',
        'assignments': [{'component_public_id': None, 'component_text': 'Blattsalat'}],
        'labels': [],
        'allergens': [],
        'origins': [{'ingredient': 'Kartoffel', 'country_code': 'CH', 'text': 'Kartoffel: CH'}],
    }
    if staff:
        value.update(internal_rappen=950, external_rappen=1450)
    return value


def _menu_form(**extra: str) -> dict[str, str]:
    form = {
        '_csrf': 'workflow-csrf',
        'week': DAY,
        'day': DAY,
        'meal': 'LUNCH',
        'option': 'MENU_1',
        'row_version': '0',
        'title': 'Kartoffelgratin',
        'allergen_mode': 'manual',
        'origin_mode': 'manual',
        'label_mode': 'manual',
    }
    form.update(extra)
    return form


def _scope(engine: Engine, user_id: int, profile: str = 'patient') -> AdminScope:
    with engine.connect() as connection:
        location_id = connection.execute(
            text('SELECT id FROM cafeteria.locations WHERE active ORDER BY id')
        ).scalar_one()
    return AdminScope(user_id, int(location_id), profile)  # type: ignore[arg-type]


def test_profile_from_endpoint_is_fixed() -> None:
    assert profile_from_endpoint('cafeteria') == 'staff_guest'
    assert profile_from_endpoint('patienten') == 'patient'


def test_app_factory_registers_workflow_and_csv_rules_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    application = cafeteria.create_app()
    rules = [rule.rule for rule in application.url_map.iter_rules()]
    assert rules.count('/admin/cafeteria') == 1
    assert rules.count('/admin/patienten') == 1
    assert rules.count('/admin/export/<profile_code>.csv') == 1


def test_unauthenticated_admin_is_401(app: Flask) -> None:
    response = app.test_client().get('/admin/cafeteria')
    assert response.status_code == 401
    assert response.headers['Cache-Control'] == 'no-store'


def test_editor_cannot_publish(app: Flask, database_engine: Engine) -> None:
    client_obj, _ = _login(app, database_engine, ['Cafeteria.Editor'])
    response = client_obj.post(
        '/admin/patienten/publish',
        data={'_csrf': 'workflow-csrf', 'week': DAY, 'row_version': '1'},
    )
    assert response.status_code == 403


def test_admin_post_uses_underscore_csrf_not_auth_spelling(client) -> None:
    token = _overview_csrf(client)
    rejected = client.post('/admin/patienten/header', data={
        'csrf_token': token,
        'week': DAY,
        'row_version': '0',
        'title': 'Herbstküche',
        'shared_note': '',
    })
    missing = client.post('/admin/patienten/header', data={
        'week': DAY,
        'row_version': '0',
        'title': 'Herbstküche',
        'shared_note': '',
    })
    saved = client.post('/admin/patienten/header', data={
        '_csrf': token,
        'week': DAY,
        'row_version': '0',
        'title': 'Herbstküche',
        'shared_note': '',
    })
    assert rejected.status_code == 400
    assert missing.status_code == 400
    assert saved.status_code == 303
    assert saved.headers['Cache-Control'] == 'no-store'


def test_query_and_body_profile_override_is_rejected(client, database_engine: Engine) -> None:
    before = _counts(database_engine)
    query = client.get(f'/admin/cafeteria?week={DAY}&profile=patient')
    body = client.post('/admin/patienten/menu?profile=staff_guest', data=_menu_form())
    form = _menu_form(profile='staff_guest')
    posted = client.post('/admin/patienten/menu', data=form)
    assert query.status_code == 400
    assert body.status_code == 400
    assert posted.status_code == 400
    assert _counts(database_engine) == before


def test_legacy_save_is_disabled(client) -> None:
    assert client.post('/admin/cafeteria/save', data=_menu_form()).status_code == 404
    assert client.post('/admin/patienten/save', data=_menu_form()).status_code == 404


def test_first_save_matrix_and_virtual_slot(client, database_engine: Engine, app: Flask) -> None:
    virtual = client.get(f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    assert virtual.status_code == 200
    assert 'name="row_version" value="0"' in virtual.get_data(as_text=True)
    assert virtual.get_data(as_text=True).count('name="row_version"') == 1
    token = _hidden(virtual.get_data(as_text=True), '_csrf', form_action='/admin/patienten/menu')
    assert client.get(
        f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=DINNER&option=MENU_1'
    ).status_code == 404
    created = client.post('/admin/patienten/menu', data=_menu_form(_csrf=token))
    assert created.status_code == 303
    with database_engine.connect() as connection:
        version = connection.execute(text('SELECT row_version FROM cafeteria.menu_items')).scalar_one()
    assert version == 1
    assert client.post('/admin/patienten/menu', data=_menu_form(_csrf=token)).status_code == 409
    missing = _menu_form(_csrf=token, row_version='2', day='2026-09-01')
    assert client.post('/admin/patienten/menu', data=missing).status_code == 404
    stale = _menu_form(_csrf=token, row_version='9', title='Neu')
    assert client.post('/admin/patienten/menu', data=stale).status_code == 409
    updated = client.post('/admin/patienten/menu', data=_menu_form(_csrf=token, row_version='1', title='Update'))
    assert updated.status_code == 303
    with database_engine.connect() as connection:
        row = connection.execute(text('SELECT row_version, title FROM cafeteria.menu_items')).one()
    assert tuple(row) == (2, 'Update')


def test_copy_exact_prior_week_and_empty_source(client, database_engine: Engine, app: Flask) -> None:
    user_id = _session_actor_id(client)
    scope = _scope(database_engine, user_id)
    persist_week_header(app.extensions['cafeteria_db'], scope, WEEK, {'title': 'Vorwoche', 'shared_note': ''}, 0)
    target = WEEK + dt.timedelta(days=7)
    offered = client.get(f'/admin/patienten/copy?week={target.isoformat()}')
    assert offered.status_code == 200
    offered_body = offered.get_data(as_text=True)
    assert _hidden(offered_body, 'target_row_version') == '0'
    extra = client.post('/admin/patienten/copy', data={
        '_csrf': _hidden(offered_body, '_csrf'),
        'source_week': WEEK.isoformat(),
        'target_week': target.isoformat(),
        'target_row_version': '0',
        'source_row_version': '1',
    })
    assert extra.status_code == 400
    empty = client.post('/admin/patienten/copy', data={
        '_csrf': _hidden(offered_body, '_csrf'),
        'source_week': WEEK.isoformat(),
        'target_week': target.isoformat(),
        'target_row_version': '0',
    })
    assert empty.status_code == 303
    with database_engine.connect() as connection:
        items = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
        pubs = connection.execute(
            text('SELECT count(*) FROM cafeteria.publication_revisions')
        ).scalar_one()
    assert items == 0
    assert pubs == 0
    existing = client.get(f'/admin/patienten/copy?week={target.isoformat()}')
    assert existing.status_code == 200
    assert _hidden(existing.get_data(as_text=True), 'target_row_version') == '1'
    mismatch = client.post('/admin/patienten/copy', data={
        '_csrf': _hidden(existing.get_data(as_text=True), '_csrf'),
        'source_week': WEEK.isoformat(),
        'target_week': (target + dt.timedelta(days=7)).isoformat(),
        'target_row_version': '0',
    })
    assert mismatch.status_code == 400
    exists = client.post('/admin/patienten/copy', data={
        '_csrf': _hidden(existing.get_data(as_text=True), '_csrf'),
        'source_week': WEEK.isoformat(),
        'target_week': target.isoformat(),
        'target_row_version': '0',
    })
    assert exists.status_code == 409
    persist_menu_item(
        app.extensions['cafeteria_db'], scope, target, target.isoformat(),
        'LUNCH', 'MENU_1', _payload(), 0,
    )
    assert client.get(f'/admin/patienten/copy?week={target.isoformat()}').status_code == 409
    assert client.get('/admin/patienten/copy?week=2026-09-21').status_code == 404
    missing = client.post('/admin/patienten/copy', data={
        '_csrf': _hidden(existing.get_data(as_text=True), '_csrf'),
        'source_week': '2026-09-14',
        'target_week': '2026-09-21',
        'target_row_version': '1',
    })
    assert missing.status_code == 404


def test_review_token_is_single_use_and_server_resolved(
    client, database_engine: Engine, app: Flask,
) -> None:
    user_id = _session_actor_id(client)
    scope = _scope(database_engine, user_id)
    persist_menu_item(app.extensions['cafeteria_db'], scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(), 0)
    with database_engine.connect() as connection:
        item_id = connection.execute(text('SELECT id FROM cafeteria.menu_items')).scalar_one()
        origins_before = connection.execute(
            text(
                'SELECT ingredient, country_code, declaration_text FROM cafeteria.origin_declarations '
                'WHERE menu_item_id=:id ORDER BY ingredient'
            ),
            {'id': item_id},
        ).all()
        version = connection.execute(
            text('SELECT row_version FROM cafeteria.menu_items WHERE id=:id'),
            {'id': item_id},
        ).scalar_one()
    page = client.get(f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    page_body = page.get_data(as_text=True)
    token = _hidden(page_body, 'component_version')
    scoped_csrf = _hidden(page_body, '_csrf', form_action='/admin/patienten/menu/review')
    rejected = client.post('/admin/patienten/menu/review', data={
        '_csrf': scoped_csrf,
        'week': DAY,
        'day': DAY,
        'meal': 'LUNCH',
        'option': 'MENU_1',
        'row_version': str(version),
        'component_version': token,
        'item_id': str(item_id),
    })
    assert rejected.status_code == 400
    success = client.post('/admin/patienten/menu/review', data={
        '_csrf': scoped_csrf,
        'week': DAY,
        'day': DAY,
        'meal': 'LUNCH',
        'option': 'MENU_1',
        'row_version': str(version),
        'component_version': token,
    })
    assert success.status_code == 303
    repeat = client.post('/admin/patienten/menu/review', data={
        '_csrf': scoped_csrf,
        'week': DAY,
        'day': DAY,
        'meal': 'LUNCH',
        'option': 'MENU_1',
        'row_version': str(version),
        'component_version': token,
    })
    assert repeat.status_code == 409
    with database_engine.connect() as connection:
        origins_after = connection.execute(
            text(
                'SELECT ingredient, country_code, declaration_text FROM cafeteria.origin_declarations '
                'WHERE menu_item_id=:id ORDER BY ingredient'
            ),
            {'id': item_id},
        ).all()
        status = connection.execute(
            text('SELECT allergen_review_status FROM cafeteria.menu_items WHERE id=:id'),
            {'id': item_id},
        ).scalar_one()
    assert origins_after == origins_before
    assert status == 'checked'


def test_origin_conflict_is_controlled_409(client, database_engine: Engine, app: Flask) -> None:
    scoped_csrf = _overview_csrf(client)
    user_id = _session_actor_id(client)
    scope = _scope(database_engine, user_id)
    engine = app.extensions['cafeteria_db']
    potato = create_component(engine, scope, 'side', 'Kartoffel', 'CH', 'common', (), ())
    rice = create_component(engine, scope, 'side', 'Reis', 'DE', 'current', (), ())
    payload = _payload()
    payload['origin_mode'] = 'auto'
    payload['origins'] = []
    payload['assignments'] = [
        {'component_public_id': str(potato['public_id']), 'component_text': None},
        {'component_public_id': str(rice['public_id']), 'component_text': None},
    ]
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 0)
    update_component(
        engine,
        scope,
        str(rice['public_id']),
        {
            'category': 'side',
            'name': 'Kartoffel',
            'origin_country_code': 'DE',
            'label_codes': [],
            'allergens': [],
        },
        int(rice['row_version']),
    )
    before = _counts(database_engine)
    page = client.get(f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    body = page.get_data(as_text=True)
    assert page.status_code == 409
    assert ORIGIN_CONFLICT in body
    assert 'error-region' in body
    with database_engine.connect() as connection:
        version = connection.execute(text('SELECT row_version FROM cafeteria.menu_items')).scalar_one()
    posted = client.post('/admin/patienten/menu/review', data={
        '_csrf': scoped_csrf,
        'week': DAY,
        'day': DAY,
        'meal': 'LUNCH',
        'option': 'MENU_1',
        'row_version': str(version),
        'component_version': 'sha256:' + ('a' * 64),
    })
    assert posted.status_code == 409
    assert ORIGIN_CONFLICT in posted.get_data(as_text=True)
    assert _counts(database_engine) == before


def test_patient_csv_export_never_reflects_internal_validation_category(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_snapshot(*_args: object, **_kwargs: object) -> None:
        raise ValueError('Patienten-Snapshot enthält unzulässige Kostenwerte.')

    monkeypatch.setattr(admin_routes, 'active_snapshot', invalid_snapshot)
    response = client.get('/admin/export/patienten.csv')
    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'Keine publizierte Revision für dieses Profil.' in body
    assert re.search(r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost', body, re.I) is None


def test_publish_requires_exact_keys(client, database_engine: Engine) -> None:
    extra = client.post('/admin/patienten/publish', data={
        '_csrf': _overview_csrf(client),
        'week': DAY,
        'row_version': '1',
        'title': 'nope',
    })
    assert extra.status_code == 400
    assert _counts(database_engine) == (0, 0, 0)


def test_publish_prg_flashes_revision_in_live_region(
    client,
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}

    def publish_stub(engine: Engine, profile: str, week: dt.date, **kwargs: object):
        called.update(engine=engine, profile=profile, week=week, **kwargs)
        return {'revision_id': 'PAT-2026-KW36-R7'}

    monkeypatch.setattr(workflow_routes, 'publish_draft', publish_stub)
    response = client.post('/admin/patienten/publish', data={
        '_csrf': _overview_csrf(client),
        'week': DAY,
        'row_version': '7',
    })
    assert response.status_code == 303
    assert response.location.endswith(f'/admin/patienten?week={DAY}')
    page = client.get(response.location)
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'aria-live="polite"' in body
    assert 'PAT-2026-KW36-R7' in body
    assert called['engine'] is database_engine
    assert (called['profile'], called['week'], called['expected_row_version']) == (
        'patient', WEEK, 7,
    )
    with database_engine.connect() as connection:
        location_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.locations WHERE code='KIRCHLINDACH'")
            ).scalar_one()
        )
    assert called['expected_location_id'] == location_id


@pytest.mark.parametrize(
    ('error', 'status'),
    [
        (workflow_routes.WorkflowValidationError('invalid'), 400),
        (workflow_routes.NoResultFound(), 404),
        (workflow_routes.StaleDraftError('stale'), 409),
        (workflow_routes.PublicationConfigurationError('issuer'), 503),
    ],
)
def test_publish_maps_only_documented_error_statuses(
    client,
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
    status: int,
) -> None:
    before = _counts(database_engine)

    def reject(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(workflow_routes, 'publish_draft', reject)
    response = client.post('/admin/patienten/publish', data={
        '_csrf': _overview_csrf(client), 'week': DAY, 'row_version': '1',
    })
    assert response.status_code == status
    assert response.headers['Cache-Control'] == 'no-store'
    assert _counts(database_engine) == before


def test_scoped_csrf_rejects_location_cutover_without_mutation(
    client,
    database_engine: Engine,
) -> None:
    token = _overview_csrf(client)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(
            text("INSERT INTO cafeteria.locations(code, name) VALUES ('NORD', 'Nordküche')")
        )

    response = client.post('/admin/patienten/header', data={
        '_csrf': token, 'week': DAY, 'row_version': '0',
        'title': 'Darf nicht wechseln', 'shared_note': '',
    })
    assert response.status_code == 409
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0


def test_copy_uses_latest_saved_source_draft(
    client,
    database_engine: Engine,
    app: Flask,
) -> None:
    scope = _scope(database_engine, _session_actor_id(client))
    persist_week_header(app.extensions['cafeteria_db'], scope, WEEK, {
        'title': 'Bestätigte Quelle', 'shared_note': '',
    }, 0)
    target = WEEK + dt.timedelta(days=7)
    offered = client.get(f'/admin/patienten/copy?week={target.isoformat()}')
    body = offered.get_data(as_text=True)
    persist_week_header(app.extensions['cafeteria_db'], scope, WEEK, {
        'title': 'Nach Bestätigung geändert', 'shared_note': '',
    }, 1)

    response = client.post('/admin/patienten/copy', data={
        '_csrf': _hidden(body, '_csrf'),
        'source_week': WEEK.isoformat(),
        'target_week': target.isoformat(),
        'target_row_version': '0',
    })
    assert response.status_code == 303
    with database_engine.connect() as connection:
        title = connection.execute(
            text('SELECT title FROM cafeteria.menu_weeks WHERE week_start=:target'),
            {'target': target},
        ).scalar_one()
    assert title == 'Nach Bestätigung geändert'


def test_preview_uses_preview_read_capability(
    app: Flask,
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_obj, user_id = _login(app, database_engine, ['Cafeteria.Editor'])
    persist_week_header(
        app.extensions['cafeteria_db'], _scope(database_engine, user_id), WEEK,
        {'title': 'Vorschau', 'shared_note': ''}, 0,
    )
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'preview.read'})
    response = client_obj.get(f'/admin/patienten/preview?week={DAY}')
    assert response.status_code == 200


def test_zero_active_locations_are_503(client, database_engine: Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
    response = client.get('/admin/patienten')
    assert response.status_code == 503
    assert client.get('/admin/patienten/copy?week=2026-09-07').status_code == 503


def test_menu_post_error_rerenders_editor_with_values(
    client,
    database_engine: Engine,
) -> None:
    page = client.get(
        f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    )
    before = _counts(database_engine)
    response = client.post('/admin/cafeteria/menu', data=_menu_form(
        _csrf=_hidden(page.get_data(as_text=True), '_csrf', form_action='/admin/cafeteria/menu'),
        title='Wiederanzeige',
        internal_chf='ungueltig',
        external_chf='14.50',
    ))
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'error-region' in body
    assert 'name="title" value="Wiederanzeige"' in body
    assert 'name="internal_chf" inputmode="decimal" value="ungueltig"' in body
    assert 'aria-invalid="true" aria-describedby="err-int"' in body
    assert _counts(database_engine) == before


def test_menu_post_rejects_raw_session_csrf_without_mutation(
    client,
    database_engine: Engine,
) -> None:
    before = _counts(database_engine)

    response = client.post('/admin/patienten/menu', data=_menu_form())

    assert response.status_code == 400
    assert _counts(database_engine) == before
