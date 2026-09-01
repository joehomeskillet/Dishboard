from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from cafeteria.api import routes as api_routes  # noqa: E402
from cafeteria.db import validate_snapshot_payload  # noqa: E402
from cafeteria.public import routes as public_routes  # noqa: E402
from cafeteria.signage import routes as signage_routes  # noqa: E402
from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402


PUBLIC_QUERY_PATHS = (
    '/',
    '/cafeteria/heute/',
    '/cafeteria/wochenangebot/',
    '/patienten/heute/',
    '/patienten/wochenplan/',
    '/druck/cafeteria/woche',
    '/druck/patienten/woche',
    '/cafeteria/legende/',
    '/api/v1/published/cafeteria',
    '/api/v1/published/patienten',
    '/signage/cafeteria/tag',
    '/signage/cafeteria/woche',
    '/signage/patienten/tag',
    '/signage/patienten/woche',
)


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    application = Flask(
        'public-contracts',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
    )
    application.config.update(
        TESTING=True,
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-01',
        LAST_GOOD_DIR=str(ROOT / '.test-last-good'),
    )
    application.extensions['cafeteria_db'] = object()
    application.add_template_filter(lambda value: value, 'date_long')
    application.add_template_filter(lambda value: value, 'date_short')
    application.add_template_filter(lambda value: int(value) / 100, 'chf')
    application.add_template_filter(lambda value: 36, 'iso_week')
    application.register_blueprint(public_routes.bp)
    application.register_blueprint(api_routes.bp)
    application.register_blueprint(signage_routes.bp)

    snapshots = {
        'staff_guest': cafeteria_snapshot(),
        'patient': patient_snapshot(),
    }

    def fake_active_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        return deepcopy(snapshots[profile_code])

    monkeypatch.setattr(public_routes, 'active_snapshot', fake_active_snapshot)
    return application


@pytest.mark.parametrize('path', PUBLIC_QUERY_PATHS)
def test_public_endpoints_reject_every_query_parameter(app: Flask, path: str) -> None:
    response = app.test_client().get(f'{path}?preview=1')

    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('path', PUBLIC_QUERY_PATHS)
@pytest.mark.parametrize('query_string', ('&&', '&', '=', '&&preview', 'date=2026-09-04'))
def test_public_endpoints_reject_raw_query_string_sequences(
    app: Flask,
    path: str,
    query_string: str,
) -> None:
    response = app.test_client().get(path, query_string=query_string)

    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize(
    'path',
    (
        '/cafeteria/heute/',
        '/cafeteria/wochenangebot/',
        '/patienten/heute/',
        '/patienten/wochenplan/',
        '/druck/cafeteria/woche',
        '/druck/patienten/woche',
        '/api/v1/published/cafeteria',
        '/api/v1/published/patienten',
        '/signage/cafeteria/tag',
        '/signage/cafeteria/woche',
        '/signage/patienten/tag',
        '/signage/patienten/woche',
    ),
)
def test_no_snapshot_returns_explicit_non_cacheable_failure(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    def no_snapshot(
        _engine: object,
        _profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> None:
        return None

    monkeypatch.setattr(public_routes, 'active_snapshot', no_snapshot)

    response = app.test_client().get(path)

    assert response.status_code == 404
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('demo_today', ('2026-09-05', '2026-09-06'))
def test_cafeteria_weekend_is_closed_without_patient_or_friday_fallback(
    app: Flask,
    demo_today: str,
) -> None:
    app.config['DEMO_TODAY'] = demo_today
    response = app.test_client().get('/signage/cafeteria/tag')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Cafeteria' in body
    assert 'geschlossen' in body
    assert 'Gebratenes Zanderfilet' not in body
    assert 'Falafel-Teller' not in body
    assert 'Griessbrei mit Zwetschgenkompott' not in body
    assert 'Pastetli mit Brätkügeli' not in body


@pytest.mark.parametrize(
    ('path', 'revision'),
    (
        ('/cafeteria/heute/', 'CAF-2026-KW36-R1'),
        ('/cafeteria/wochenangebot/', 'CAF-2026-KW36-R1'),
        ('/patienten/heute/', 'PAT-2026-KW36-R1'),
        ('/patienten/wochenplan/', 'PAT-2026-KW36-R1'),
        ('/signage/cafeteria/tag', 'CAF-2026-KW36-R1'),
        ('/signage/cafeteria/woche', 'CAF-2026-KW36-R1'),
        ('/signage/patienten/tag', 'PAT-2026-KW36-R1'),
        ('/signage/patienten/woche', 'PAT-2026-KW36-R1'),
    ),
)
def test_day_and_week_responses_expose_their_profile_revision(
    app: Flask,
    path: str,
    revision: str,
) -> None:
    response = app.test_client().get(path)

    assert response.status_code == 200
    assert response.headers['X-Snapshot-Revision'] == revision


def test_demo_snapshots_pass_payload_validation() -> None:
    validate_snapshot_payload('patient', patient_snapshot())
    validate_snapshot_payload('staff_guest', cafeteria_snapshot())


@pytest.mark.parametrize(
    ('key', 'value'),
    (
        ('cost', 1250),
        ('billing_label', 'Intern'),
    ),
)
def test_patient_snapshot_rejects_price_keys(key: str, value: object) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(
    'title',
    (
        'Intern Preis 12.50',
        'Extern',
        'CHF',
        '0.00',
    ),
)
def test_patient_snapshot_rejects_price_values(title: str) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0]['title'] = title

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


def test_patient_snapshot_rejects_intern_label() -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0]['labels'] = [
        {'code': 'BILLING', 'name': 'Intern'},
    ]

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


def test_patient_snapshot_allows_menu_text_and_opening_time() -> None:
    snapshot = deepcopy(patient_snapshot())
    option = snapshot['days'][0]['services'][0]['options'][0]
    option['title'] = 'Internationale Gemüsepfanne'
    option['note'] = 'Ausgabe bis 11.30 Uhr'

    validate_snapshot_payload('patient', snapshot)


def test_patient_api_and_signage_never_use_cafeteria_payload(app: Flask) -> None:
    client = app.test_client()
    api_response = client.get('/api/v1/published/patienten')
    signage = client.get('/signage/patienten/woche').get_data(as_text=True)

    assert api_response.json['profile_code'] == 'patient'
    assert 'prices' not in api_response.get_data(as_text=True)
    assert 'CHF' not in signage
    assert 'Kichererbsen-Curry' not in signage
    assert 'Pastetli mit Brätkügeli' in signage
