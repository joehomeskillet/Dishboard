from __future__ import annotations

# ruff: noqa: F401, F811
import pytest
from test_smoke import app as smoke_app_fixture, pytestmark as smoke_pytestmark


pytestmark = smoke_pytestmark


def _channel_status(payload: dict, channel: str) -> dict:
    return {item['channel']: item for item in payload['channels']}[channel]


def test_status_payload_reflects_active_channel_states_and_revisions(
    smoke_app_fixture,
):
    client = smoke_app_fixture.test_client()
    smoke_app_fixture.config['DEMO_TODAY'] = '2026-09-01'
    response = client.get('/api/v1/status')

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'

    payload = response.get_json()
    assert payload['service'] == 'dishboard'
    assert payload['api_version'] == '1.0.0'

    cafeteria = _channel_status(payload, 'cafeteria')
    patienten = _channel_status(payload, 'patienten')
    assert cafeteria['published'] is True
    assert patienten['published'] is True
    assert cafeteria['revision_id'] == 'CAF-2026-KW36-R1'
    assert patienten['revision_id'] == 'PAT-2026-KW36-R1'
    assert cafeteria['today_state'] == 'open'
    assert patienten['today_state'] == 'open'
    assert payload['fhir']['version'] == '5.0.0'
    assert payload['docs']['openapi'] == '/api/v1/openapi.json'
    assert payload['docs']['swagger_ui'] == '/api/v1/docs'


def test_today_for_cafeteria_shows_kichererbsen_curry_and_prices(
    smoke_app_fixture,
):
    smoke_app_fixture.config['DEMO_TODAY'] = '2026-09-01'
    client = smoke_app_fixture.test_client()
    response = client.get('/api/v1/published/cafeteria/today')

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'public, max-age=60, stale-if-error=86400'
    assert response.headers['X-Snapshot-Revision'] == 'CAF-2026-KW36-R1'

    payload = response.get_json()
    assert payload['channel'] == 'cafeteria'
    assert payload['profile_code'] == 'staff_guest'
    assert payload['date'] == '2026-09-01'
    day_services = payload['day'].get('services', [])
    option_titles = [option['title'] for service in day_services for option in service.get('options', [])]
    assert 'Kichererbsen-Curry' in option_titles
    assert all('prices' in option for service in day_services for option in service.get('options', []))


def test_today_for_patienten_shows_dinner_without_prices(
    smoke_app_fixture,
):
    smoke_app_fixture.config['DEMO_TODAY'] = '2026-09-06'
    client = smoke_app_fixture.test_client()
    response = client.get('/api/v1/published/patienten/today')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'public, max-age=60, stale-if-error=86400'
    assert response.headers['X-Snapshot-Revision'] == 'PAT-2026-KW36-R1'

    payload = response.get_json()
    assert payload['channel'] == 'patienten'
    assert payload['profile_code'] == 'patient'
    assert payload['date'] == '2026-09-06'
    service_codes = {service['meal_code'] for service in payload['day']['services']}
    assert 'DINNER' in service_codes
    assert 'CHF' not in body
    assert 'price' not in body.lower()
    option_titles = [
        option['title']
        for service in payload['day']['services']
        for option in service.get('options', [])
    ]
    assert 'Pastetli mit Brätkügeli' in option_titles

    for service in payload['day']['services']:
        for option in service['options']:
            assert 'prices' not in option


def test_days_route_returns_patient_day_2026_09_03(smoke_app_fixture):
    smoke_app_fixture.config['DEMO_TODAY'] = '2026-09-01'
    response = smoke_app_fixture.test_client().get('/api/v1/published/patienten/days/2026-09-03')
    payload = response.get_json()

    assert response.status_code == 200
    assert response.headers['X-Snapshot-Revision'] == 'PAT-2026-KW36-R1'
    assert payload['date'] == '2026-09-03'
    service_titles = [option['title'] for service in payload['day']['services'] for option in service['options']]
    assert 'Schweinsragout Tessiner Art' in service_titles


def test_days_route_rejects_invalid_date(smoke_app_fixture):
    response = smoke_app_fixture.test_client().get('/api/v1/published/patienten/days/2026-13-01')

    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload['error'] == 'invalid_date'
    assert 'detail' in payload


def test_days_route_returns_404_for_missing_snapshot(smoke_app_fixture):
    response = smoke_app_fixture.test_client().get('/api/v1/published/patienten/days/2031-01-06')

    assert response.status_code == 404
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload['error'] == 'no_published_menu'


@pytest.mark.parametrize(
    'path',
    (
        '/api/v1/status',
        '/api/v1/published/cafeteria/today',
        '/api/v1/published/patienten/days/2026-09-03',
    ),
)
def test_query_parameters_are_rejected(smoke_app_fixture, path: str):
    response = smoke_app_fixture.test_client().get(f'{path}?preview=1')
    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'

    payload = response.get_json()
    assert payload['error'] == 'query_parameters_not_allowed'
    assert 'detail' in payload
