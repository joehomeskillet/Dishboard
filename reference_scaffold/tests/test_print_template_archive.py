"""Real PostgreSQL archive lifecycle and strict, mutation-free legacy reads."""
from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria.print_template_config import PrintTemplateValidationError, default_config
from cafeteria.print_templates import (
    SETTING_PREFIX, PrintTemplateConflictError, PrintTemplateStateError,
    change_template, read_templates,
)
from test_admin_workflow_routes import APP_PASSWORD, database_engine  # noqa: F401
from test_print_template_routes import editor_app, fields  # noqa: F401
from test_print_template_store import _actor

COPY_ID = 'a' * 32


def legacy_document() -> dict[str, Any]:
    # Deliberate v1 literal: never derive legacy fixtures from the current default.
    revision = {'id': 1, 'name': 'Standard', 'config': default_config(),
                'created_at': None, 'created_by': None, 'restored_from': None}
    return {
        'schema_version': 1, 'version': 3, 'active_template': 'standard', 'active_revision': 1,
        'templates': [
            {'id': 'standard', 'current_revision': 2, 'revisions': [
                revision, {**copy.deepcopy(revision), 'id': 2, 'name': 'Neuer Entwurf'},
            ]},
            {'id': COPY_ID, 'current_revision': 1, 'revisions': [
                {**copy.deepcopy(revision), 'name': 'Kopie'},
            ]},
        ],
    }


def seed(engine: Engine, profile: str, document: dict[str, Any]) -> None:
    with engine.begin() as connection:
        connection.execute(text('''
            INSERT INTO cafeteria.settings(setting_key, setting_value)
            VALUES (:key, CAST(:value AS jsonb))
        '''), {'key': SETTING_PREFIX + profile, 'value': json.dumps(document)})


def snapshot(engine: Engine) -> list[Any]:
    with engine.connect() as connection:
        return list(connection.execute(text('''
            SELECT id, setting_key, setting_value, updated_at, updated_by
            FROM cafeteria.settings ORDER BY id
        ''')))


@pytest.fixture
def runtime(database_engine: Engine):  # noqa: F811
    engine = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize('profile,family', [('staff_guest', 'cafeteria'), ('patient', 'patienten')])
def test_legacy_gets_preserve_raw_document_and_metadata(editor_app: Any, database_engine: Engine, runtime: Engine, profile: str, family: str) -> None:  # noqa: F811
    client, _, _ = _actor(editor_app, database_engine)
    original = legacy_document()
    seed(database_engine, profile, original)
    before = snapshot(database_engine)
    with runtime.connect() as connection:
        document = read_templates(connection, profile)
    assert document['schema_version'] == 2
    assert all(item['archived'] is False for item in document['templates'])
    assert document['templates'][0]['revisions'] == original['templates'][0]['revisions']
    for url in ['/admin/vorlagen?week=2026-08-31', f'/admin/vorlagen/{family}?week=2026-08-31&template={COPY_ID}&revision=1']:
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
    assert snapshot(database_engine) == before


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_atomic_upgrade_lifecycle_retains_history_and_active_pointer(editor_app: Any, database_engine: Engine, runtime: Engine, profile: str) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    original = legacy_document()
    seed(database_engine, profile, original)
    archived, _ = change_template(runtime, profile, actor, authz, 3, COPY_ID, 'archive', revision_id=1)
    assert archived['schema_version'] == 2 and archived['version'] == 4
    assert archived['templates'][1]['archived'] is True
    assert (archived['active_template'], archived['active_revision']) == ('standard', 1)
    assert [item['revisions'] for item in archived['templates']] == [item['revisions'] for item in original['templates']]
    before = snapshot(database_engine)
    for action in ['archive', 'activate', 'save', 'restore']:
        with pytest.raises(PrintTemplateConflictError):
            change_template(runtime, profile, actor, authz, 4, COPY_ID, action, revision_id=1, name='Verboten', config=default_config())
        assert snapshot(database_engine) == before
    copied, selected = change_template(runtime, profile, actor, authz, 4, COPY_ID, 'copy', revision_id=1, name='Neue Kopie')
    assert selected != COPY_ID and copied['templates'][-1]['archived'] is False
    assert copied['templates'][1] == archived['templates'][1]
    available, _ = change_template(runtime, profile, actor, authz, 5, COPY_ID, 'reactivate', revision_id=1)
    assert available['version'] == 6 and available['templates'][1]['archived'] is False
    assert available['templates'][1]['revisions'] == original['templates'][1]['revisions']
    before = snapshot(database_engine)
    with pytest.raises(PrintTemplateConflictError):
        change_template(runtime, profile, actor, authz, 6, COPY_ID, 'reactivate')
    assert snapshot(database_engine) == before
    with runtime.connect() as connection:
        assert read_templates(connection, 'patient' if profile == 'staff_guest' else 'staff_guest')['version'] == 0


@pytest.mark.parametrize('action,target,expected', [('archive', 'standard', 3), ('reactivate', COPY_ID, 3), ('archive', COPY_ID, 2)])
def test_failed_legacy_write_does_not_upgrade(editor_app: Any, database_engine: Engine, runtime: Engine, action: str, target: str, expected: int) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    seed(database_engine, 'patient', legacy_document())
    before = snapshot(database_engine)
    with pytest.raises(PrintTemplateConflictError):
        change_template(runtime, 'patient', actor, authz, expected, target, action, revision_id=2 if target == 'standard' else 1)
    assert snapshot(database_engine) == before


@pytest.mark.parametrize('case', ['v1_extra', 'v2_missing', 'v2_string', 'v2_active_archived', 'unknown', 'bool_schema'])
def test_corrupt_versions_fail_closed_on_read_and_write(editor_app: Any, database_engine: Engine, runtime: Engine, case: str) -> None:  # noqa: F811
    client, actor, authz = _actor(editor_app, database_engine)
    document = legacy_document()
    if case.startswith('v2'):
        document['schema_version'] = 2
        for item in document['templates']:
            item['archived'] = False
    if case == 'v1_extra':
        document['templates'][1]['archived'] = False
    elif case == 'v2_missing':
        del document['templates'][1]['archived']
    elif case == 'v2_string':
        document['templates'][1]['archived'] = 'false'
    elif case == 'v2_active_archived':
        document['templates'][0]['archived'] = True
    else:
        document['schema_version'] = True if case == 'bool_schema' else 3
    seed(database_engine, 'patient', document)
    before = snapshot(database_engine)
    with runtime.connect() as connection, pytest.raises(PrintTemplateStateError):
        read_templates(connection, 'patient')
    with pytest.raises(PrintTemplateStateError):
        change_template(runtime, 'patient', actor, authz, 3, COPY_ID, 'archive')
    for url in ['/admin/vorlagen?week=2026-08-31', '/admin/vorlagen/patienten?week=2026-08-31']:
        response = client.get(url)
        assert response.status_code == 503
        assert response.headers['Cache-Control'] == 'no-store'
    assert snapshot(database_engine) == before


def test_caps_archive_does_not_free_slot_or_append_revision(editor_app: Any, database_engine: Engine, runtime: Engine) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    document = legacy_document()
    revision = document['templates'][1]['revisions'][0]
    document['templates'][1]['revisions'] = [{**copy.deepcopy(revision), 'id': number} for number in range(1, 51)]
    document['templates'][1]['current_revision'] = 50
    for number in range(8):
        document['templates'].append({'id': f'{number:032x}', 'current_revision': 1, 'revisions': [copy.deepcopy(revision)]})
    seed(database_engine, 'patient', document)
    saved, _ = change_template(runtime, 'patient', actor, authz, 3, COPY_ID, 'archive', revision_id=50)
    assert len(saved['templates'][1]['revisions']) == 50
    before = snapshot(database_engine)
    with pytest.raises(PrintTemplateValidationError):
        change_template(runtime, 'patient', actor, authz, 4, COPY_ID, 'copy', name='Elfte')
    assert snapshot(database_engine) == before
    restored, _ = change_template(runtime, 'patient', actor, authz, 4, COPY_ID, 'reactivate', revision_id=50)
    assert len(restored['templates']) == 10 and len(restored['templates'][1]['revisions']) == 50


def test_first_invalid_archive_rolls_back_virtual_insert_and_exhaustion_is_safe(editor_app: Any, database_engine: Engine, runtime: Engine) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    before = snapshot(database_engine)
    with pytest.raises(PrintTemplateConflictError):
        change_template(runtime, 'patient', actor, authz, 0, 'standard', 'archive')
    assert snapshot(database_engine) == before
    document = legacy_document()
    document['version'] = 2**63 - 2
    seed(database_engine, 'patient', document)
    before = snapshot(database_engine)
    with pytest.raises(PrintTemplateConflictError):
        change_template(runtime, 'patient', actor, authz, 2**63 - 2, COPY_ID, 'archive')
    assert snapshot(database_engine) == before


def test_archive_routes_exact_fields_status_and_original_cas(editor_app: Any, database_engine: Engine) -> None:  # noqa: F811
    client, _, _ = _actor(editor_app, database_engine)
    seed(database_engine, 'patient', legacy_document())
    url = f'/admin/vorlagen/patienten?week=2026-08-31&template={COPY_ID}&revision=1'
    before = snapshot(database_engine)
    for extra in [{'surprise': 'x'}, {'_csrf': 'invalid'}]:
        assert client.post(url, data=fields('archive', 3, **extra)).status_code == 400
        assert snapshot(database_engine) == before
    response = client.post(url, data=fields('archive', 3))
    assert response.status_code == 303 and 'revision=1' in response.location
    response = client.get(response.location)
    assert response.status_code == 200 and b'Vorlage reaktivieren' in response.data
    assert b'name="action" value="save"' not in response.data
    assert b'name="action" value="activate"' not in response.data
    before = snapshot(database_engine)
    response = client.post(url, data=fields('reactivate', 3))
    assert response.status_code == 409 and b'name="version" value="3"' in response.data
    assert snapshot(database_engine) == before
    assert client.post(url, data=fields('reactivate', 4)).status_code == 303


def test_identical_save_keeps_existing_append_revision_semantics(editor_app: Any, database_engine: Engine, runtime: Engine) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    seed(database_engine, 'patient', legacy_document())
    saved, _ = change_template(runtime, 'patient', actor, authz, 3, COPY_ID, 'save', name='Kopie', config=default_config(), revision_id=1)
    assert saved['version'] == 4 and saved['templates'][1]['current_revision'] == 2
    assert saved['templates'][1]['revisions'][0] == legacy_document()['templates'][1]['revisions'][0]
    assert saved['templates'][1]['revisions'][1]['config'] == default_config()
