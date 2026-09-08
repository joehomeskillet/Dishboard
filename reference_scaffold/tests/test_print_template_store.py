"""Real runtime-role persistence, optimistic writes and draft/active revision isolation."""
from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria.print_template_config import PrintTemplateValidationError, default_config, default_layout
from cafeteria.print_templates import (
    SETTING_PREFIX, PrintTemplateConflictError, PrintTemplateStateError, active_template,
    _validate_document, change_template, default_document, read_templates, template_revision,
)
from cafeteria.admin.week_pdf import WeekPdfFitError
from test_admin_workflow_routes import APP_PASSWORD, WEEK, _login, app, database_engine  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values


def _actor(application, engine):
    client, actor = _login(application, engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        return client, actor, session['authz_version']


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_drafts_copy_activation_restore_and_existing_settings_are_separate(app, database_engine, profile):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    with database_engine.begin() as connection:
        connection.execute(text("INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES ('admin_density','\"comfortable\"')"))
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    try:
        with runtime.connect() as connection:
            default = read_templates(connection, profile)
            assert default['version'] == 0
            assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key LIKE :key'), {'key': SETTING_PREFIX + '%'}).scalar_one() == 0
        config = {**default_config(), 'header_text': 'Guten Appetit', 'palette': 'brand'}
        saved, selected = change_template(runtime, profile, actor, version, 0, 'standard', 'save', name='Herbst', config=config)
        assert saved['version'] == 1 and selected == 'standard'
        with runtime.connect() as connection:
            assert read_templates(connection, profile) == saved
            assert active_template(connection, profile) == (default_config(), 'standard:1')
        copied, copy_id = change_template(runtime, profile, actor, version, 1, 'standard', 'copy', name='Herbst Kopie', revision_id=2)
        assert copy_id != 'standard'
        assert template_revision(copied, copy_id)['config'] == config
        assert copied['active_template'] == 'standard' and copied['active_revision'] == 1
        active, _ = change_template(runtime, profile, actor, version, 2, copy_id, 'activate', revision_id=1, week=WEEK)
        with runtime.connect() as connection:
            assert active_template(connection, profile) == (config, f'{copy_id}:1')
        restored, _ = change_template(runtime, profile, actor, version, 3, 'standard', 'restore', revision_id=1)
        assert restored['active_template'] == copy_id and restored['active_revision'] == 1
        history = restored['templates'][0]['revisions']
        assert history[:2] == saved['templates'][0]['revisions']
        assert history[2]['id'] == 3 and history[2]['restored_from'] == 1
        assert history[2]['config'] == default_config()
        with runtime.connect() as connection:
            assert read_templates(connection, profile) == restored
            assert read_templates(connection, 'patient' if profile == 'staff_guest' else 'staff_guest')['version'] == 0
            assert connection.execute(text("SELECT setting_value FROM cafeteria.settings WHERE setting_key='admin_density'")).scalar_one() == 'comfortable'
    finally:
        runtime.dispose()


@pytest.mark.parametrize('action', ['save', 'copy', 'restore', 'activate'])
def test_stale_writes_preserve_other_session(app, database_engine, action):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    saved, _ = change_template(database_engine, 'patient', actor, version, 0, 'standard', 'save', name='Erste Sitzung', config=default_config())
    with pytest.raises(PrintTemplateConflictError):
        change_template(database_engine, 'patient', actor, version, 0, 'standard', action, name='Zweite Sitzung', config=default_config(), revision_id=1, week=WEEK)
    with database_engine.connect() as connection:
        assert read_templates(connection, 'patient') == saved


def test_concurrent_first_save_has_one_winner_and_no_duplicate_global_row(app, database_engine):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    barrier = Barrier(2)

    def save(name):
        barrier.wait(timeout=10)
        try:
            change_template(database_engine, 'patient', actor, version, 0, 'standard', 'save', name=name, config=default_config())
            return name
        except PrintTemplateConflictError:
            return 'conflict'

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(save, ['Erste Sitzung', 'Zweite Sitzung']))
    assert results.count('conflict') == 1
    with database_engine.connect() as connection:
        doc = read_templates(connection, 'patient')
        assert doc['version'] == 1
        assert template_revision(doc, 'standard')['name'] in results
        assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key=:key'), {'key': SETTING_PREFIX + 'patient'}).scalar_one() == 1


@pytest.mark.parametrize('change', ['version', 'disabled', 'role'])
def test_authority_rechecked_inside_store_before_initialization(app, database_engine, change):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    with database_engine.begin() as connection:
        if change == 'disabled':
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:id'), {'id': actor})
        elif change == 'role':
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor})
        else:
            version += 1
    with pytest.raises(PermissionError):
        change_template(database_engine, 'patient', actor, version, 0, 'standard', 'save', name='Entwurf', config=default_config())
    with database_engine.connect() as connection:
        assert read_templates(connection, 'patient')['version'] == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key LIKE :key'), {'key': SETTING_PREFIX + '%'}).scalar_one() == 0


def test_overflow_activation_rolls_back_and_active_revision_survives(app, database_engine):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    values = _patient_values()
    for day in values['days']:
        for service in day['services']:
            for option in service['options']:
                option['note'] = 'Lange Rezeptur. ' * 80
    _save(database_engine, 'patient', values)
    saved, _ = change_template(database_engine, 'patient', actor, version, 0, 'standard', 'save', name='Neue Schrift', config={**default_config(), 'font': 'fira'})
    with pytest.raises(WeekPdfFitError):
        change_template(database_engine, 'patient', actor, version, 1, 'standard', 'activate', revision_id=2, week=WEEK)
    with database_engine.connect() as connection:
        assert read_templates(connection, 'patient') == saved


@pytest.mark.parametrize('value', [None, {}, {'schema_version': 999}])
def test_corrupt_stored_document_fails_closed_without_overwrite(app, database_engine, value):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    with database_engine.begin() as connection:
        connection.execute(text('INSERT INTO cafeteria.settings(setting_key, setting_value) VALUES (:key, CAST(:value AS jsonb))'), {'key': SETTING_PREFIX + 'patient', 'value': json.dumps(value)})
    with database_engine.connect() as connection, pytest.raises(PrintTemplateStateError):
        read_templates(connection, 'patient')
    with pytest.raises(PrintTemplateStateError):
        change_template(database_engine, 'patient', actor, version, 0, 'standard', 'save', name='Kopie', config=default_config())
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT setting_value FROM cafeteria.settings WHERE setting_key=:key'), {'key': SETTING_PREFIX + 'patient'}).scalar_one() == value


def test_revision_bound_never_prunes_active_or_existing_history(app, database_engine, monkeypatch):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    saved, _ = change_template(database_engine, 'patient', actor, version, 0, 'standard', 'save', name='Neue Revision', config=default_config())
    before = copy.deepcopy(saved)
    monkeypatch.setattr('cafeteria.print_templates.MAX_REVISIONS', 2)
    with pytest.raises(PrintTemplateValidationError):
        change_template(database_engine, 'patient', actor, version, 1, 'standard', 'restore', revision_id=1)
    with database_engine.connect() as connection:
        assert read_templates(connection, 'patient') == before


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('schema', [1, 2, 3])
def test_reader_preserves_legacy_configuration_and_source_structure(profile, schema):
    document = default_document()
    document['schema_version'] = schema
    if schema == 1:
        del document['templates'][0]['archived']
    before = json.dumps(document)
    loaded = _validate_document(document, profile)
    assert json.dumps(document) == before
    assert loaded['schema_version'] == max(schema, 2)
    assert loaded['templates'][0]['revisions'] == document['templates'][0]['revisions']
    assert 'layout' not in template_revision(loaded, 'standard')['config']


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('schema', [1, 2, 3, True, 3.0])
def test_layout_reader_requires_v3_envelope_and_preserves_revision(profile, schema):
    document = default_document()
    document['schema_version'] = schema
    if type(schema) is int and schema == 1:
        del document['templates'][0]['archived']
    template_revision(document, 'standard')['config']['layout'] = default_layout(profile)
    before = copy.deepcopy(document)
    if type(schema) is int and schema == 3:
        loaded = _validate_document(document, profile)
        assert loaded == document
        assert loaded is not document
    else:
        with pytest.raises(PrintTemplateStateError):
            _validate_document(document, profile)
    assert document == before


def test_patient_reader_rejects_cafeteria_price_binding():
    document = default_document()
    document['schema_version'] = 3
    template_revision(document, 'standard')['config']['layout'] = default_layout('staff_guest')
    with pytest.raises(PrintTemplateStateError):
        _validate_document(document, 'patient')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_v3_lifecycle_retains_legacy_history_without_downgrade(app, database_engine, profile):  # noqa: F811
    _, actor, version = _actor(app, database_engine)
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    config = {**default_config(), 'layout': default_layout(profile)}
    saved, _ = change_template(database_engine, profile, actor, version, 0, 'standard', 'save', name='Raster', config=config)
    assert saved['schema_version'] == 3
    assert saved['templates'][0]['revisions'][0] == default_document()['templates'][0]['revisions'][0]
    with pytest.raises(PrintTemplateValidationError, match='neuen PDF-Renderer'):
        change_template(database_engine, profile, actor, version, 1, 'standard', 'activate', revision_id=2, week=WEEK)
    with database_engine.connect() as connection:
        assert read_templates(connection, profile) == saved
        assert active_template(connection, profile) == (default_config(), 'standard:1')
    copied, copy_id = change_template(database_engine, profile, actor, version, 1, 'standard', 'copy', name='Kopie', revision_id=2)
    assert template_revision(copied, copy_id)['config'] == config
    archived, _ = change_template(database_engine, profile, actor, version, 2, copy_id, 'archive')
    reactivated, _ = change_template(database_engine, profile, actor, version, 3, copy_id, 'reactivate')
    restored, _ = change_template(database_engine, profile, actor, version, 4, 'standard', 'restore', revision_id=1)
    assert template_revision(restored, 'standard')['config'] == default_config()
    assert restored['templates'][0]['revisions'][:2] == saved['templates'][0]['revisions']
    legacy_save, _ = change_template(database_engine, profile, actor, version, 5, 'standard', 'save', name='Bisherige Felder', config=default_config())
    assert all(doc['schema_version'] == 3 for doc in (copied, archived, reactivated, restored, legacy_save))
    with database_engine.connect() as connection:
        assert read_templates(connection, profile) == legacy_save
