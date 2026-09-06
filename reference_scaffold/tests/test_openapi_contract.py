from __future__ import annotations

from collections.abc import Iterable
import re

from flask import Flask

from cafeteria.api import routes as api_routes
from cafeteria.api.openapi import build_openapi
from cafeteria.api.v1_routes import bp as api_v1_routes


def _build_test_app() -> Flask:
    app = Flask('api-openapi-contract')
    app.register_blueprint(api_routes.bp)
    app.register_blueprint(api_v1_routes)
    return app


def _normalize_path(rule: str) -> str:
    normalized = re.sub(r'<[^:>]+:channel>', '{channel}', rule)
    normalized = normalized.replace('/cafeteria', '/{channel}')
    normalized = normalized.replace('/patienten', '/{channel}')
    normalized = normalized.replace('<date>', '{date}')
    return normalized


def _collect_refs(node: object) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == '$ref' and isinstance(value, str):
                yield value
            else:
                yield from _collect_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _collect_refs(item)


def test_openapi_contract_has_api_v1_paths():
    app = _build_test_app()
    documented_paths = set(build_openapi()['paths'])
    api_v1_rules = {
        _normalize_path(rule.rule)
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith('/api/v1')
    }
    assert documented_paths.issuperset(api_v1_rules)


def test_openapi_documented_paths_exist():
    app = _build_test_app()
    documented_paths = set(build_openapi()['paths'])
    api_v1_rules = {
        _normalize_path(rule.rule)
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith('/api/v1')
    }
    ignored = {'/api/v1/openapi.json', '/api/v1/docs'}
    for path in documented_paths:
        if not path.startswith('/api/v1'):
            continue
        if path in ignored:
            continue
        assert path in api_v1_rules


def test_openapi_refs_resolve():
    spec = build_openapi()
    components = spec['components']['schemas']
    refs = {_ for _ in _collect_refs(spec)}
    for ref in refs:
        if not ref.startswith('#/components/schemas/'):
            continue
        assert ref.split('/')[-1] in components


SCHEMA_2_EXAMPLE = {
    'schema_version': 2,
    'area_name': 'Schülerinnen und Schüler',
    'days': [{
        'date': '2026-08-31', 'weekday': 'Montag', 'state': 'open', 'notice': '',
        'services': [{
            'meal_code': 'LUNCH', 'meal_name': 'Mittag', 'service_state': 'open', 'notice': '',
            'service_start': '11:30', 'service_end': '13:30', 'options': [],
        }],
    }],
}


def test_openapi_documents_the_optional_area_name_and_serving_times():
    schemas = build_openapi()['components']['schemas']
    snapshot, service = schemas['Snapshot'], schemas['Service']
    area = snapshot['properties']['area_name']
    assert area['type'] == 'string' and area['minLength'] == 1 and area['maxLength'] == 80
    assert 'area_name' not in snapshot['required']
    assert snapshot['properties']['schema_version'] == {'type': 'integer', 'minimum': 1}
    for field in ('service_start', 'service_end'):
        assert service['properties'][field]['pattern'] == '^([01][0-9]|2[0-3]):[0-5][0-9]$'
        assert field not in service['required']
    assert 'LUNCH' in snapshot['properties']['days']['description']
    for node in (area, service['properties']['service_start'], service['properties']['service_end']):
        assert node['description'].endswith('.')


def test_schema_2_example_matches_the_documented_shape():
    schemas = build_openapi()['components']['schemas']
    snapshot, service = schemas['Snapshot'], schemas['Service']
    area = SCHEMA_2_EXAMPLE['area_name']
    assert snapshot['properties']['schema_version']['minimum'] <= SCHEMA_2_EXAMPLE['schema_version']
    assert snapshot['properties']['area_name']['minLength'] <= len(area) <= snapshot['properties']['area_name']['maxLength']
    example_service = SCHEMA_2_EXAMPLE['days'][0]['services'][0]
    for field in ('service_start', 'service_end'):
        assert re.fullmatch(service['properties'][field]['pattern'], example_service[field])
    assert set(service['required']) <= set(example_service)
    assert example_service['meal_code'] in service['properties']['meal_code']['enum']


def test_schema_1_snapshot_stays_valid_without_the_new_keys():
    schemas = build_openapi()['components']['schemas']
    legacy_service = {'meal_code': 'LUNCH', 'meal_name': 'Mittag', 'options': []}
    assert set(schemas['Service']['required']) <= set(legacy_service)
    assert not set(schemas['Snapshot']['required']) & {'area_name'}


def test_openapi_json_contract_if_registered():
    app = _build_test_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    if '/api/v1/openapi.json' not in rules:
        return
    response = app.test_client().get('/api/v1/openapi.json')
    assert response.get_json() == build_openapi()
