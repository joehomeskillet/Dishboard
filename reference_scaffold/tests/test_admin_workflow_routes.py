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

from cafeteria.admin import routes as admin_routes
from cafeteria.db import init_database
from cafeteria.security import csrf_token

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)
WEEK_START = dt.date(2026, 8, 31)


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
def client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as current:
        current['user'] = {'id': 1, 'name': 'Küche'}
        current['roles'] = ['Cafeteria.Admin']
        current['_csrf_token'] = 'workflow-csrf'
    return client


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
        r'\b(CHF|Rappen|Intern|Extern|0\.00)\b|prices|price-row|signage-price|admin-price',
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
    assert 'Unzulässiges Formularfeld' in response.get_data(as_text=True)
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
