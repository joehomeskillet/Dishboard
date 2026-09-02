from __future__ import annotations

import datetime as dt
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.admin import routes as admin_routes
from cafeteria.security import csrf_token

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)
WEEK_START = dt.date(2026, 8, 31)
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
def client(app: Flask, database_engine: Engine):
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
        ['Cafeteria.Admin'],
    )
    with database_engine.begin() as connection:
        authz_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
            {'id': user_id},
        ).scalar_one()
    client_obj = app.test_client()
    with client_obj.session_transaction() as current:
        current['user'] = {'id': user_id, 'name': 'Küche'}
        current['authz_version'] = authz_version
        current['_csrf_token'] = 'workflow-csrf'
    return client_obj


def _patient_form() -> dict[str, str]:
    form = {
        '_csrf': 'workflow-csrf',
        'week_start': WEEK_START.isoformat(),
        'row_version': '1',
        'title': 'Herbstküche',
        'shared_note': 'Frisch gekocht',
    }
    for day_index in range(7):
        for meal_code in ('LUNCH', 'DINNER'):
            service = f'service_{day_index}_{meal_code}'
            form[f'{service}_state'] = 'open'
            form[f'{service}_notice'] = ''
            for type_code, title in (
                ('MENU_1', 'Kartoffelgratin'),
                ('VEGGIE', 'Gemüseteller'),
            ):
                option = f'{service}_{type_code}'
                form[f'{option}_title'] = title
                form[f'{option}_components'] = 'Blattsalat'
    return form


def _staff_form() -> dict[str, str]:
    form = {
        '_csrf': 'workflow-csrf',
        'week_start': WEEK_START.isoformat(),
        'row_version': '1',
        'title': 'Cafeteria Herbst',
        'shared_note': 'Mittagsangebot',
    }
    for day_index in range(5):
        service = f'service_{day_index}_LUNCH'
        form[f'{service}_state'] = 'open'
        form[f'{service}_notice'] = ''
        for type_code, title in (('MENU_1', 'Tagesmenü'), ('VEGGIE', 'Vegetarisch')):
            option = f'{service}_{type_code}'
            form[f'{option}_title'] = title
            form[f'{option}_components'] = 'Salat'
            form[f'{option}_internal_rappen'] = '950'
            form[f'{option}_external_rappen'] = '1450'
    return form


def test_patient_editor_html_contains_no_cost_vocabulary(client) -> None:
    response = client.get('/admin/patienten')
    body = response.get_data(as_text=True)

    forbidden = re.compile(
        r'\b(CHF|Rappen|Intern|Extern|0\.00)\b|preise?|prices|kosten|cost|price-row|signage-price|admin-price',
        re.I,
    )
    assert response.status_code == 200
    assert forbidden.search(body) is None
    assert body.count('name="week_start"') == 1
    assert len(re.findall(r'name="service_[0-6]_LUNCH_state"', body)) == 7
    assert len(re.findall(r'name="service_[0-6]_DINNER_state"', body)) == 7
    assert len(
        re.findall(
            r'name="service_[0-6]_(?:LUNCH|DINNER)_(?:MENU_1|VEGGIE)_title"',
            body,
        )
    ) == 28


def test_patient_post_rejects_cost_field_before_database_write(client, database_engine: Engine) -> None:
    assert client.get('/admin/patienten').status_code == 200
    form = _patient_form()
    form['internal_rappen'] = '900'

    response = client.post('/admin/patienten/save', data=form)

    with database_engine.connect() as connection:
        item_count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert response.status_code == 400
    assert response.get_data(as_text=True).count('Patientenformular ist ungültig.') == 1
    assert item_count == 0


def test_patient_save_requires_csrf_and_then_persists_full_grid(client, database_engine: Engine) -> None:
    assert client.get('/admin/patienten').status_code == 200
    form = _patient_form()
    del form['_csrf']
    rejected = client.post('/admin/patienten/save', data=form)

    form['_csrf'] = 'workflow-csrf'
    saved = client.post('/admin/patienten/save', data=form)

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id)
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                '''
            )
        ).one()
    assert rejected.status_code == 400
    assert saved.status_code == 303
    assert tuple(shape) == (14, 28, 0)


def test_profile_publish_routes_activate_only_requested_channel(client, database_engine: Engine) -> None:
    assert client.get('/admin/patienten').status_code == 200
    form = _patient_form()
    response = client.post('/admin/patienten/publish', data=form)

    with database_engine.connect() as connection:
        active = connection.execute(
            text('SELECT profile_code FROM cafeteria.active_publications ORDER BY profile_code')
        ).scalars().all()
    assert response.status_code == 303
    assert active == ['patient']


def test_cafeteria_editor_is_five_lunches_with_cost_fields_and_weekend_notice(client) -> None:
    response = client.get('/admin/cafeteria')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert len(re.findall(r'name="service_[0-4]_LUNCH_state"', body)) == 5
    assert '_DINNER_' not in body
    assert len(re.findall(r'name="service_[0-4]_LUNCH_(?:MENU_1|VEGGIE)_internal_rappen"', body)) == 10
    assert len(re.findall(r'name="service_[0-4]_LUNCH_(?:MENU_1|VEGGIE)_external_rappen"', body)) == 10
    assert 'Samstag und Sonntag: Cafeteria geschlossen.' in body


def test_cafeteria_closed_lunch_does_not_require_dish_or_cost_input(
    client,
    database_engine: Engine,
) -> None:
    assert client.get('/admin/cafeteria').status_code == 200
    form = _staff_form()
    service = 'service_2_LUNCH'
    form[f'{service}_state'] = 'closed'
    form[f'{service}_notice'] = 'Cafeteria geschlossen'
    for type_code in ('MENU_1', 'VEGGIE'):
        option = f'{service}_{type_code}'
        form[f'{option}_title'] = ''
        form[f'{option}_components'] = ''
        form[f'{option}_internal_rappen'] = ''
        form[f'{option}_external_rappen'] = ''

    response = client.post('/admin/cafeteria/save', data=form)

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id)
                FROM cafeteria.menu_services s
                LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                '''
            )
        ).one()
    assert response.status_code == 303
    assert tuple(shape) == (5, 8, 8)


@pytest.mark.parametrize(
    ('field_name', 'field_value'),
    (
        ('internal_rappen', '1250'),
        ('PRI⁦CE', 'CHF Intern Extern 0.00'),
        ('unitPrice', 'CHF'),
    ),
)
def test_patient_form_error_never_reflects_sensitive_field_or_value(
    client,
    field_name: str,
    field_value: str,
) -> None:
    """Including the unexpected key in abort text leaks attacker-controlled vocabulary."""
    assert client.get('/admin/patienten').status_code == 200
    form = _patient_form()
    form[field_name] = field_value

    response = client.post('/admin/patienten/save', data=form)
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert field_name not in body
    assert field_value not in body
    assert re.search(r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost', body, re.I) is None


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


def test_patient_validation_error_renders_at_field_and_preserves_safe_input(client) -> None:
    assert client.get('/admin/patienten').status_code == 200
    form = _patient_form()
    form['title'] = ''
    retained_field = 'service_6_DINNER_VEGGIE_components'
    form[retained_field] = 'Blattsalat\nWurzelgemüse'

    response = client.post('/admin/patienten/save', data=form)
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'Patientenformular ist ungültig.' in body
    assert 'id="patient-title_error"' in body
    assert re.search(r'<input[^>]+id="patient-title"[^>]+autofocus', body)
    assert 'Blattsalat\nWurzelgemüse' in body
    assert 'role="alert"' in body


def test_cafeteria_validation_error_is_adjacent_and_preserves_submitted_values(client) -> None:
    assert client.get('/admin/cafeteria').status_code == 200
    form = _staff_form()
    field_name = 'service_0_LUNCH_MENU_1_external_rappen'
    form[field_name] = '900'

    response = client.post('/admin/cafeteria/save', data=form)
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert f'id="{field_name}_error"' in body
    assert re.search(rf'<input[^>]+id="{field_name}"[^>]+value="900"[^>]+autofocus', body)
    assert 'Cafeteria Herbst' in body
    assert 'role="alert"' in body


def _workflow_state(database_engine: Engine, profile_code: str) -> tuple[object, ...]:
    with database_engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    '''
                    SELECT w.row_version,
                           w.workflow_state,
                           (SELECT count(*) FROM cafeteria.menu_items),
                           (SELECT count(*) FROM cafeteria.publication_revisions)
                    FROM cafeteria.menu_weeks w
                    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                    WHERE p.code=:profile_code AND w.week_start=:week_start
                    '''
                ),
                {'profile_code': profile_code, 'week_start': WEEK_START},
            ).one()
        )


@pytest.mark.parametrize(
    ('profile_path', 'action_path', 'form_factory', 'profile_code', 'field_name', 'field_value'),
    (
        (
            '/admin/patienten',
            '/admin/patienten/save',
            _patient_form,
            'patient',
            'week_start',
            '2026-09-01',
        ),
        (
            '/admin/patienten',
            '/admin/patienten/publish',
            _patient_form,
            'patient',
            'row_version',
            'ungültig',
        ),
        (
            '/admin/cafeteria',
            '/admin/cafeteria/save',
            _staff_form,
            'staff_guest',
            'row_version',
            'ungültig',
        ),
        (
            '/admin/cafeteria',
            '/admin/cafeteria/publish',
            _staff_form,
            'staff_guest',
            'week_start',
            '2026-09-01',
        ),
    ),
)
def test_hidden_metadata_error_focuses_summary_and_keeps_draft_unchanged(
    client,
    database_engine: Engine,
    profile_path: str,
    action_path: str,
    form_factory,
    profile_code: str,
    field_name: str,
    field_value: str,
) -> None:
    assert client.get(profile_path).status_code == 200
    before = _workflow_state(database_engine, profile_code)
    form = form_factory()
    form[field_name] = field_value
    retained_title = f'Retained {profile_code} title'
    form['title'] = retained_title

    response = client.post(action_path, data=form)
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert re.search(
        r'<div class="form-error-summary" role="alert" tabindex="-1" autofocus>',
        body,
    )
    assert not re.search(r'<input[^>]+type="hidden"[^>]+autofocus', body)
    assert f'name="{field_name}" value="{field_value}"' in body
    assert retained_title in body
    assert _workflow_state(database_engine, profile_code) == before


@pytest.mark.parametrize(
    ('path', 'form_factory', 'field_name'),
    (
        (
            '/admin/patienten/publish',
            _patient_form,
            'service_0_LUNCH_MENU_1_title',
        ),
        (
            '/admin/cafeteria/publish',
            _staff_form,
            'service_0_LUNCH_MENU_1_title',
        ),
    ),
)
def test_overlong_publish_is_atomic_and_focuses_exact_field(
    client,
    database_engine: Engine,
    path: str,
    form_factory,
    field_name: str,
) -> None:
    profile_path = '/admin/patienten' if 'patienten' in path else '/admin/cafeteria'
    assert client.get(profile_path).status_code == 200
    form = form_factory()
    form[field_name] = 'G' * 37

    response = client.post(path, data=form)
    body = response.get_data(as_text=True)

    with database_engine.connect() as connection:
        persisted = connection.execute(
            text(
                '''
                SELECT count(i.id), count(r.id)
                FROM cafeteria.menu_items i
                FULL JOIN cafeteria.publication_revisions r ON FALSE
                '''
            )
        ).one()
    assert response.status_code == 400
    assert tuple(persisted) == (0, 0)
    assert f'id="{field_name}_error"' in body
    assert re.search(rf'<input[^>]+id="{field_name}"[^>]+autofocus', body)
    assert 'G' * 37 in body
