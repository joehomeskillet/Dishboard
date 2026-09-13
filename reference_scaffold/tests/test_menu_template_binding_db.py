"""Provenance writes use the real app-role transaction and existing aggregate CAS."""
from dataclasses import replace
from datetime import timedelta
from time import monotonic, sleep, time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from sqlalchemy import text

from cafeteria.component_catalog_store import ComponentNotFoundError
from cafeteria.menu_template_binding import TemplateBindingValidationError, TemplateContext
from cafeteria.workflow import _draft_values, import_draft
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import PartialWorkflowConflictError, persist_menu_item
from cafeteria.workflow_store import load_draft_connection, persist_draft
from cafeteria.workflow_write_context import WriteConflictError
from cafeteria.workflow_review import _review_payload, get_component_review_token
from review_support import write_expectations
from test_workflow_partial_store_db import (  # noqa: F401
    WEEK, _full_values, _payload, _scope, workflow_database,
)


def make_template(engine, **changes):
    with engine.begin() as connection:
        return dict(connection.execute(text('''
            INSERT INTO cafeteria.dish_templates(title,profile_scope,active,recipe_id)
            VALUES(:title,:profile,:active,:recipe) RETURNING id,public_id::text,title,active,updated_at
        '''), {'title': 'Rösti', 'profile': 'common', 'active': True, 'recipe': None,
               **changes}).mappings().one())


def stored_state(engine):
    with engine.connect() as connection:
        return {table: tuple(connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY 1'
        )).scalars()) for table in ('dish_templates', 'menu_weeks', 'menu_services', 'menu_items',
                                   'menu_item_components', 'audit_events')}


def context_for(scope, template):
    return TemplateContext(scope.actor_id, scope.expected_authz_version, scope.location_id,
        template['public_id'], template['updated_at'].isoformat(), None, int(time()) + 3600,
        scope.profile_code, WEEK.isoformat(), WEEK.isoformat(), 'LUNCH', 'MENU_1', 0)


def save(db, payload, expected=0, **kwargs):
    return persist_menu_item(db.app, _scope(db), WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1',
                             payload, expected, **kwargs)


def test_create_preserve_archive_detach_and_no_archived_rebinding(workflow_database):  # noqa: F811
    db = workflow_database
    template = make_template(db.owner)
    payload = {**_payload(), 'dish_template_public_id': template['public_id']}
    assert save(db, payload) == 1
    with db.app.connect() as connection:
        draft = load_draft_connection(connection, 'patient', WEEK)
    option = draft['days'][0]['services'][0]['options'][0]
    assert option['dish_template'] == {key: template[key] for key in ('public_id', 'title', 'active')}
    assert 'dish_template' not in _draft_values(draft)['days'][0]['services'][0]['options'][0]
    with db.owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.dish_templates SET active=false WHERE id=:id'), template)
    assert save(db, {**payload, 'title': 'Freier Menütitel'}, 1) == 2
    assert save(db, _payload(), 2) == 3
    assert save(db, {**_payload(), 'dish_template_public_id': ''}, 3) == 4
    with db.owner.connect() as connection:
        assert connection.execute(text('SELECT dish_template_id FROM cafeteria.menu_items')).scalar_one() == template['id']
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='workflow.menu_saved'" )).scalar_one() == 4
    assert save(db, {**payload, 'dish_template_detach': '1'}, 4) == 5
    before = stored_state(db.owner)
    with pytest.raises(TemplateBindingValidationError, match='archiviert'):
        save(db, payload, 5)
    with pytest.raises(TemplateBindingValidationError, match='archiviert'):
        persist_menu_item(db.app, _scope(db), WEEK, '2026-09-01', 'LUNCH', 'MENU_1', payload, 0)
    assert stored_state(db.owner) == before


@pytest.mark.parametrize('kind', ('unknown', 'archived', 'profile'))
def test_invalid_new_template_is_atomic(workflow_database, kind):  # noqa: F811
    db = workflow_database
    template = make_template(db.owner, active=kind != 'archived', profile='staff_guest' if kind == 'profile' else 'common')
    public_id = str(uuid4()) if kind == 'unknown' else template['public_id']
    before = stored_state(db.owner)
    with pytest.raises(ComponentNotFoundError if kind == 'unknown' else TemplateBindingValidationError):
        save(db, {**_payload(), 'dish_template_public_id': public_id})
    assert stored_state(db.owner) == before


@pytest.mark.parametrize('change', ('version', 'archive', 'actor', 'authz', 'location', 'day', 'mode', 'expired', 'template'))
def test_original_context_conflicts_without_partial_writes(workflow_database, change):  # noqa: F811
    db = workflow_database
    template = make_template(db.owner)
    context = context_for(_scope(db), template)
    if change in ('version', 'archive'):
        with db.owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.dish_templates SET title=:title,active=:active WHERE id=:id'),
                               {**template, 'title': 'Geändert', 'active': change != 'archive'})
    else:
        fields = {'actor': {'actor_id': context.actor_id + 1}, 'authz': {'authz_version': context.authz_version + 1},
                  'location': {'location_id': context.location_id + 1}, 'day': {'day': '2026-09-01'},
                  'mode': {'expected_item_row_version': 1}, 'expired': {'expires_at': 1},
                  'template': {'template_public_id': str(uuid4())}}
        context = replace(context, **fields[change])
    before = stored_state(db.owner)
    with pytest.raises(WriteConflictError):
        save(db, {**_payload(), 'dish_template_public_id': template['public_id']}, template_context=context)
    assert stored_state(db.owner) == before


def test_signed_create_cas_rejects_double_submit(workflow_database):  # noqa: F811
    db = workflow_database
    template = make_template(db.owner)
    context = context_for(_scope(db), template)
    payload = {**_payload(), 'dish_template_public_id': template['public_id']}
    assert save(db, payload, template_context=context) == 1
    before = stored_state(db.owner)
    with pytest.raises(PartialWorkflowConflictError, match='bereits gespeichert'):
        save(db, payload, template_context=context)
    assert stored_state(db.owner) == before


def test_whole_draft_writer_copy_and_csv_replacement(workflow_database):  # noqa: F811
    db = workflow_database
    template = make_template(db.owner)
    assert save(db, _payload()) == 1
    values = _full_values('Vorlage')
    values['days'][0]['services'][0]['options'][0]['dish_template_public_id'] = template['public_id']
    with db.app.connect() as connection:
        draft = load_draft_connection(connection, 'patient', WEEK)
    persist_draft(db.app, 'patient', WEEK, expected_row_version=draft['row_version'], actor_id=db.actor_id,
                  values=values, **write_expectations(db.app, db.actor_id))
    with db.app.connect() as connection:
        draft = load_draft_connection(connection, 'patient', WEEK)
    assert draft['days'][0]['services'][0]['options'][0]['dish_template']['public_id'] == template['public_id']
    copy_previous_week(db.app, _scope(db), WEEK + timedelta(days=7), 0, source_row_version=draft['row_version'])
    with db.app.connect() as connection:
        copied = load_draft_connection(connection, 'patient', WEEK + timedelta(days=7))
    assert copied['days'][0]['services'][0]['options'][0]['dish_template']['public_id'] == template['public_id']
    import_draft(db.app, 'patient', WEEK, expected_row_version=draft['row_version'], actor_id=db.actor_id,
                 values=_full_values('CSV'), **write_expectations(db.app, db.actor_id))
    with db.app.connect() as connection:
        replaced = load_draft_connection(connection, 'patient', WEEK)
    assert replaced['days'][0]['services'][0]['options'][0]['dish_template'] is None


def test_provenance_only_keeps_public_bytes_and_review_fingerprint(workflow_database):  # noqa: F811
    db = workflow_database
    assert save(db, _payload()) == 1
    with db.app.connect() as connection:
        original = _draft_values(load_draft_connection(connection, 'patient', WEEK))
        item = connection.execute(text('SELECT id FROM cafeteria.menu_items')).scalar_one()
        review = _review_payload(connection, _scope(db), item)
    token = get_component_review_token(db.app, _scope(db), item)
    template = make_template(db.owner)
    assert save(db, {**_payload(), 'dish_template_public_id': template['public_id']}, 1) == 2
    # Existing review tokens include the mandatory item version; provenance adds no field.
    assert get_component_review_token(db.app, _scope(db), item) != token
    with db.app.connect() as connection:
        assert _review_payload(connection, _scope(db), item) == {**review, 'item_row_version': 2}
        assert _draft_values(load_draft_connection(connection, 'patient', WEEK)) == original


def test_template_create_race_has_one_receipt_and_one_conflict(workflow_database):  # noqa: F811
    db = workflow_database
    template = make_template(db.owner)
    scope = _scope(db)
    context = context_for(scope, template)
    barrier = Barrier(2)
    def submit():
        barrier.wait()
        try:
            return persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1',
                {**_payload(), 'dish_template_public_id': template['public_id']}, 0, template_context=context)
        except PartialWorkflowConflictError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        assert sorted(str(f.result(timeout=10)) for f in futures) == ['1', 'conflict']
    with db.owner.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='workflow.menu_saved'")).scalar_one() == 1


@pytest.mark.parametrize('archive_first', (True, False))
def test_original_recipe_head_is_locked_even_without_selected_revision(workflow_database, monkeypatch, archive_first):  # noqa: F811
    from cafeteria import workflow_partial_store as partial
    from test_menu_recipe_choices_reader import create_recipe
    db = workflow_database
    recipe = create_recipe(db.owner, db.actor_id, 'Ursprüngliches Rezept')
    template = make_template(db.owner, recipe=recipe)
    with db.owner.connect() as connection:
        public_id = connection.execute(text('SELECT public_id::text FROM cafeteria.recipes WHERE id=:id'), {'id': recipe}).scalar_one()
    context = replace(context_for(_scope(db), template), recipe_public_id=public_id, recipe_active=True)
    payload = {**_payload(), 'dish_template_public_id': template['public_id']}
    assert not any(row.get('recipe_revision_public_id') for row in payload['assignments'])
    before = stored_state(db.owner)
    held, writer_ready, archive_ready, release = Event(), Event(), Event(), Event()
    pids = {}
    original_prepare, original_templates = partial.prepare_bindings, partial.lock_templates

    def prepare(connection, *args, **kwargs):
        pids['writer'] = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
        writer_ready.set()
        return original_prepare(connection, *args, **kwargs)

    def templates(connection, *args, **kwargs):
        if not archive_first:
            held.set()
            assert release.wait(10)
        return original_templates(connection, *args, **kwargs)

    def write():
        try:
            return save(db, payload, template_context=context)
        except WriteConflictError:
            return 'conflict'

    def archive():
        with db.owner.begin() as connection:
            pids['archive'] = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            archive_ready.set()
            connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:id'), {'id': recipe})
            if archive_first:
                held.set()
                assert release.wait(10)

    monkeypatch.setattr(partial, 'prepare_bindings', prepare)
    monkeypatch.setattr(partial, 'lock_templates', templates)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(archive if archive_first else write)
        try:
            if not held.wait(5):
                first.result(timeout=1)
                pytest.fail('First transaction did not reach its held-lock checkpoint')
            second = pool.submit(write if archive_first else archive)
            assert (writer_ready if archive_first else archive_ready).wait(5)
            waiting = pids['writer' if archive_first else 'archive']
            blocking = pids['archive' if archive_first else 'writer']
            deadline = monotonic() + 3
            observed = False
            with db.owner.connect() as connection:
                while monotonic() < deadline:
                    observed = blocking in connection.execute(
                        text('SELECT pg_blocking_pids(:pid)'), {'pid': waiting}).scalar_one()
                    if observed:
                        break
                    sleep(0.01)
            if not observed and second.done():
                second.result(timeout=1)
            assert observed, 'Expected the original recipe-head lock to block the concurrent transaction'
        finally:
            release.set()
        first_result, second_result = first.result(timeout=10), second.result(timeout=10)
    assert (second_result if archive_first else first_result) == ('conflict' if archive_first else 1)
    if archive_first:
        assert stored_state(db.owner) == before
    else:
        with db.owner.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='workflow.menu_saved'")).scalar_one() == 1
