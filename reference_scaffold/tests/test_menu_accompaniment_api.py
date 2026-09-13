from __future__ import annotations

import datetime as dt

import httpx
from flask import Flask

from cafeteria.api.openapi import build_openapi
from cafeteria.api.v1_routes import bp as api_v1_bp
from cafeteria.api_keys import API_KEY_SCOPES, create_api_key
from cafeteria.workflow_partial_store import persist_menu_item
import dishboard_mcp.server as mcp_server
from test_mcp_server import invoke_tool
from test_workflow_partial_store_db import (
    WEEK,
    WorkflowDatabase,
    _payload,
    _scope,
    workflow_database,
)

__all__ = ['workflow_database']


def _authorization(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _keyed_app(db: WorkflowDatabase) -> tuple[Flask, str]:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='menu-accompaniment-api-test-secret')
    app.extensions['cafeteria_db'] = db.app
    app.register_blueprint(api_v1_bp)
    _, token = create_api_key(
        db.app,
        actor_id=db.actor_id,
        label='Beilagen-API-Test',
        scopes=API_KEY_SCOPES,
        channels=('patienten',),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=30),
    )
    return app, token


def test_weeks_stays_summary_and_preview_emits_pair_only_for_selection(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    persist_menu_item(
        db.app,
        scope,
        WEEK,
        WEEK.isoformat(),
        'LUNCH',
        'MENU_1',
        {**_payload(), 'accompaniment_code': 'soup'},
        0,
    )
    persist_menu_item(
        db.app,
        scope,
        WEEK,
        WEEK.isoformat(),
        'LUNCH',
        'VEGGIE',
        _payload(title='Kartoffelgratin'),
        0,
    )
    app, token = _keyed_app(db)
    client = app.test_client()
    headers = _authorization(token)

    weeks_response = client.get('/api/v1/weeks/patienten', headers=headers)
    assert weeks_response.status_code == 200
    assert 'accompaniment_code' not in weeks_response.get_data(as_text=True)
    assert 'accompaniment_name' not in weeks_response.get_data(as_text=True)

    preview_response = client.get(
        f'/api/v1/weeks/patienten/{WEEK.isoformat()}/preview',
        headers=headers,
    )
    assert preview_response.status_code == 200
    options = preview_response.get_json()['days'][0]['services'][0]['options']
    by_type = {option['type_code']: option for option in options}
    assert by_type['MENU_1']['accompaniment_code'] == 'soup'
    assert by_type['MENU_1']['accompaniment_name'] == 'Suppe'
    assert 'accompaniment_code' not in by_type['VEGGIE']
    assert 'accompaniment_name' not in by_type['VEGGIE']

    option_schema = build_openapi()['components']['schemas']['Option']
    for option in options:
        assert set(option_schema['required']) <= set(option)
        assert set(option) <= set(option_schema['properties'])
        for field, property_schema in option_schema['properties'].items():
            if field in option and 'enum' in property_schema:
                assert option[field] in property_schema['enum']


def test_mcp_week_preview_passes_accompaniment_snapshot_through_unchanged() -> None:
    snapshot = {
        'schema_version': 2,
        'profile_code': 'patient',
        'channel': 'patienten',
        'week_start': '2026-08-31',
        'days': [
            {
                'date': '2026-08-31',
                'services': [
                    {
                        'meal_code': 'LUNCH',
                        'options': [
                            {
                                'external_id': 'PATIENT-2026-08-31-LUNCH-1',
                                'accompaniment_code': 'soup',
                                'accompaniment_name': 'Suppe',
                            }
                        ],
                    }
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/weeks/patienten/2026-08-31/preview':
            return httpx.Response(200, json=snapshot)
        return httpx.Response(500, json={'error': 'unexpected_path'})

    with httpx.Client(
        base_url='https://dishboard.example',
        headers={'Authorization': 'Bearer test'},
        transport=httpx.MockTransport(handler),
    ) as client:
        server = mcp_server.build_server(client)
        result = invoke_tool(
            server,
            'get_week_preview',
            {'channel': 'patienten', 'week_start': '2026-08-31'},
        )

    assert result == snapshot
