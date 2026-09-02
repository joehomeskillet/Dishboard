from __future__ import annotations

import datetime as dt
import csv
import html
import io
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria.admin import routes as admin_routes
from cafeteria.csvio import snapshot_to_csv, validate_upload
from cafeteria.db import init_database
from cafeteria.security import csrf_token
from cafeteria.workflow_snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


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
        SECRET_KEY='csv-import-test-secret',
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
        current['_csrf_token'] = 'csv-import-csrf'
    return client


def _example(name: str) -> bytes:
    return (ROOT / 'csv' / name).read_bytes()


def _preview(client, payload: bytes, filename: str = 'menu.csv'):
    return client.post(
        '/admin/import-preview',
        data={
            '_csrf': 'csv-import-csrf',
            'file': (io.BytesIO(payload), filename),
        },
        content_type='multipart/form-data',
    )


def _token(response) -> str:
    match = re.search(r'name="import_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match is not None
    return html.unescape(match.group(1))


def test_patient_preview_is_required_and_does_not_write_or_expose_cost_vocabulary(
    client,
    database_engine: Engine,
) -> None:
    response = _preview(client, _example('menu_patient_example.csv'))
    body = response.get_data(as_text=True)

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert response.status_code == 200
    assert 'Bereit zum Import' in body
    assert 'name="import_token"' in body
    assert re.search(r'CHF|Intern|Extern|0\.00|price|rappen|kosten|cost', body, re.I) is None
    assert count == 0


def test_patient_import_persists_complete_grid_without_prices(client, database_engine: Engine) -> None:
    preview = _preview(client, _example('menu_patient_example.csv'))

    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id),
                       count(DISTINCT c.menu_item_id)
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                LEFT JOIN cafeteria.menu_item_components c ON c.menu_item_id=i.id
                '''
            )
        ).one()
    assert response.status_code == 303
    assert response.headers['Location'].endswith('/admin/patienten')
    assert tuple(shape) == (14, 28, 0, 28)


def test_cafeteria_import_persists_five_lunches_and_both_prices(
    client,
    database_engine: Engine,
) -> None:
    preview = _preview(client, _example('menu_cafeteria_example.csv'))
    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id),
                       min(pr.internal_rappen), max(pr.external_rappen)
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                '''
            )
        ).one()
        meals = connection.execute(
            text(
                '''
                SELECT DISTINCT mp.code
                FROM cafeteria.menu_services s
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                '''
            )
        ).scalars().all()
    assert response.status_code == 303
    assert tuple(shape[:3]) == (5, 10, 10)
    assert shape[3] > 0
    assert shape[4] >= shape[3]
    assert meals == ['LUNCH']


def test_invalid_patient_header_reports_position_without_import_action_or_write(
    client,
    database_engine: Engine,
) -> None:
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    lines = source.splitlines()
    invalid = ('\n'.join([lines[0] + ';preis_mitarbeitende_chf', *[line + ';10.00' for line in lines[1:]]])).encode()

    response = _preview(client, invalid)
    body = response.get_data(as_text=True)

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert response.status_code == 200
    assert 'Zeile 1' in body
    assert 'Spalte 18' in body
    assert 'name="import_token"' not in body
    assert count == 0


def test_invalid_title_reports_exact_line_and_column(client, database_engine: Engine) -> None:
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    invalid = source.replace(';Pouletgeschnetzeltes Paprika;', ';;', 1).encode()

    response = _preview(client, invalid)

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Zeile 2' in body
    assert 'Spalte 8' in body
    assert 'name="import_token"' not in body
    assert count == 0


def test_import_rejects_tampered_token_and_missing_csrf_without_partial_write(
    client,
    database_engine: Engine,
) -> None:
    preview = _preview(client, _example('menu_cafeteria_example.csv'))
    token = _token(preview)

    csrf_rejected = client.post('/admin/import', data={'import_token': token})
    token_rejected = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': token + 'tampered'},
    )

    with database_engine.connect() as connection:
        count = connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one()
    assert csrf_rejected.status_code == 400
    assert token_rejected.status_code == 400
    assert count == 0


def _snapshot(profile: str, closures: dict[tuple[int, str], tuple[str, str]] | None = None) -> dict:
    week_start = dt.date(2026, 8, 31)
    day_count = 7 if profile == 'patient' else 5
    meals = ('LUNCH', 'DINNER') if profile == 'patient' else ('LUNCH',)
    days = []
    for offset in range(day_count):
        services = []
        service_date = (week_start + dt.timedelta(days=offset)).isoformat()
        for meal_code in meals:
            state, notice = (closures or {}).get((offset, meal_code), ('open', ''))
            options = []
            for type_code, title in (('MENU_1', 'Kartoffelgratin'), ('VEGGIE', 'Gemüseteller')):
                option: dict[str, object] = {
                    'type_code': type_code,
                    'title': title,
                    'components': ['Blattsalat'],
                }
                if profile == 'staff_guest':
                    option['internal_rappen'] = 950
                    option['external_rappen'] = 1450
                options.append(option)
            services.append(
                {
                    'meal_code': meal_code,
                    'service_state': state,
                    'notice': notice,
                    'options': options,
                }
            )
        days.append({'date': service_date, 'services': services})
    return build_snapshot(
        profile,
        {
            'week_start': week_start.isoformat(),
            'location': {'code': 'KIRCHLINDACH', 'name': 'Südhang'},
            'title': 'Herbstküche',
            'shared_note': '',
            'days': days,
        },
        f"{'PAT' if profile == 'patient' else 'CAF'}-2026-KW36-R1",
    )


@pytest.mark.parametrize(
    ('profile', 'closures', 'expected_rows', 'has_cost_columns'),
    (
        (
            'patient',
            {(0, 'LUNCH'): ('closed', 'Mittagsservice geschlossen'),
             (0, 'DINNER'): ('holiday', 'Abendservice entfällt')},
            28,
            False,
        ),
        (
            'staff_guest',
            {(2, 'LUNCH'): ('closed', 'Cafeteria geschlossen')},
            10,
            True,
        ),
    ),
)
def test_csv_roundtrip_preserves_two_rows_and_notice_for_each_closed_service(
    profile: str,
    closures: dict[tuple[int, str], tuple[str, str]],
    expected_rows: int,
    has_cost_columns: bool,
) -> None:
    """Skipping empty options loses a closure and breaks fixed grid cardinality."""
    exported = snapshot_to_csv(_snapshot(profile, closures))
    decoded = exported.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded), delimiter=';')
    rows = list(reader)

    assert len(rows) == expected_rows
    assert ('preis_mitarbeitende_chf' in (reader.fieldnames or [])) is has_cost_columns
    if profile == 'patient':
        assert re.search(
            r'\b(?:CHF|Intern|Extern|Preis|price|rappen|kosten|cost)\b|0\.00',
            decoded,
            re.I,
        ) is None
    for (offset, meal_code), (state, notice) in closures.items():
        service_date = (dt.date(2026, 8, 31) + dt.timedelta(days=offset)).isoformat()
        closed_rows = [
            row for row in rows
            if row['datum'] == service_date and row['mahlzeit'] == meal_code
        ]
        assert [row['menueart'] for row in closed_rows] == ['MENU_1', 'VEGGIE']
        assert {row['zustand'] for row in closed_rows} == {
            {'closed': 'geschlossen', 'holiday': 'feiertag'}[state]
        }
        assert {row['zustand_text'] for row in closed_rows} == {notice}
        assert all(row['external_id'] == '' and row['titel'] == '' for row in closed_rows)

    imported = validate_upload(io.BytesIO(exported))
    assert imported['valid'] is True
    values = imported['values']
    for (offset, meal_code), (state, notice) in closures.items():
        service = next(
            item for item in values['days'][offset]['services'] if item['meal_code'] == meal_code
        )
        assert service['service_state'] == state
        assert service['notice'] == notice


def test_ragged_extra_csv_cell_is_a_positioned_issue_not_server_error(client) -> None:
    """Calling startswith on DictReader's None:list ragged cell used to raise."""
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    lines = source.splitlines()
    lines[1] += ';CHF-ATTACK'

    response = _preview(client, '\n'.join(lines).encode())
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Zeile 2' in body
    assert 'Spalte 18' in body
    assert 'name="import_token"' not in body
    assert 'CHF-ATTACK' not in body
    assert re.search(r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost', body, re.I) is None


def test_malformed_origin_is_a_positioned_issue_not_server_error(client) -> None:
    """Letting malformed origin reach rsplit('=', 1) used to raise ValueError."""
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(source), delimiter=';')
    rows = list(reader)
    rows[0]['herkunft'] = 'PouletCH'
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(
        buffer,
        fieldnames=reader.fieldnames,
        delimiter=';',
        lineterminator='\n',
    )
    writer.writeheader()
    writer.writerows(rows)

    response = _preview(client, buffer.getvalue().encode())
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Zeile 2' in body
    assert 'Spalte 14' in body
    assert 'name="import_token"' not in body


def test_patient_preview_runs_full_payload_validation_before_any_mutation(
    client,
    database_engine: Engine,
) -> None:
    """Removing workflow preflight would mark a semantically tainted file importable."""
    source = _example('menu_patient_example.csv').decode('utf-8-sig')
    tainted = source.replace(
        ';Pouletgeschnetzeltes Paprika;',
        ';CHF Intern Extern 0.00 Rappen;',
        1,
    ).encode()

    response = _preview(client, tainted)
    body = response.get_data(as_text=True)

    with database_engine.connect() as connection:
        weeks = connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one()
    assert response.status_code == 200
    assert 'name="import_token"' not in body
    assert 'Patienten-CSV ist ungültig.' in body
    assert re.search(
        r'\b(?:CHF|Intern|Extern|Preis|price|rappen|kosten|cost)\b|0\.00',
        body,
        re.I,
    ) is None
    assert weeks == 0


def test_preview_token_binds_profile_week_and_missing_week_version_then_rejects_stale_commit(
    client,
    database_engine: Engine,
) -> None:
    """A text-only token lets a preview overwrite a draft created after preview."""
    preview = _preview(client, _example('menu_patient_example.csv'))
    token = _token(preview)
    serializer = URLSafeTimedSerializer('csv-import-test-secret', salt='dishboard-csv-import-v1')
    payload = serializer.loads(bytes.fromhex(token).decode('ascii'))

    assert payload['profile_code'] == 'patient'
    assert payload['week_start'] == '2026-08-31'
    assert payload['expected_row_version'] == 0
    assert isinstance(payload['text'], str)

    assert client.get('/admin/patienten').status_code == 200
    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': token},
    )

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT w.row_version, w.title, count(i.id)
                FROM cafeteria.menu_weeks w
                LEFT JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
                LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                GROUP BY w.id
                '''
            )
        ).one()
    assert response.status_code == 409
    assert tuple(shape) == (1, None, 0)


def test_import_week_creation_and_persistence_roll_back_together_on_database_error(
    client,
    database_engine: Engine,
) -> None:
    """Creating week in load_draft commits it before later item persistence can fail."""
    preview = _preview(client, _example('menu_patient_example.csv'))
    with database_engine.begin() as connection:
        connection.execute(
            text(
                '''
                CREATE FUNCTION cafeteria.fail_second_import_item() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.sort_order = 2 THEN
                        RAISE EXCEPTION 'forced import failure';
                    END IF;
                    RETURN NEW;
                END
                $$
                '''
            )
        )
        connection.execute(
            text(
                '''
                CREATE TRIGGER fail_second_import_item
                BEFORE INSERT ON cafeteria.menu_items
                FOR EACH ROW EXECUTE FUNCTION cafeteria.fail_second_import_item()
                '''
            )
        )

    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                '''
                SELECT (SELECT count(*) FROM cafeteria.menu_weeks),
                       (SELECT count(*) FROM cafeteria.menu_services),
                       (SELECT count(*) FROM cafeteria.menu_items)
                '''
            )
        ).one()
    assert response.status_code == 500
    assert tuple(counts) == (0, 0, 0)


@pytest.mark.parametrize(
    'delete_statement',
    (
        "DELETE FROM cafeteria.dietary_labels WHERE code='VEGETARIAN'",
        "DELETE FROM cafeteria.allergens WHERE code='MILK'",
    ),
)
def test_missing_reference_row_rolls_back_complete_import_as_bad_request(
    client,
    database_engine: Engine,
    delete_statement: str,
) -> None:
    """INSERT SELECT with zero rows used to commit an incomplete draft silently."""
    preview = _preview(client, _example('menu_patient_example.csv'))
    with database_engine.begin() as connection:
        connection.execute(text(delete_statement))

    response = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                '''
                SELECT (SELECT count(*) FROM cafeteria.menu_weeks),
                       (SELECT count(*) FROM cafeteria.menu_services),
                       (SELECT count(*) FROM cafeteria.menu_items),
                       (SELECT count(*) FROM cafeteria.menu_item_labels)
                '''
            )
        ).one()
    assert response.status_code == 400
    assert tuple(counts) == (0, 0, 0, 0)
