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


def test_openapi_json_contract_if_registered():
    app = _build_test_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    if '/api/v1/openapi.json' not in rules:
        return
    response = app.test_client().get('/api/v1/openapi.json')
    assert response.get_json() == build_openapi()
