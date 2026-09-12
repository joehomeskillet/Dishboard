"""Actual PostgreSQL blocking and changed-pre-read refusal on the guarded writers."""
# ruff: noqa: F401, F811
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import component_assignment_store as assignments
from cafeteria.component_catalog_store import ComponentConflictError
from cafeteria.workflow_review import get_component_review_token, review_component
from cafeteria.workflow_review_context import get_week_review, review_week_context
from cafeteria.workflow_write_context import WriteConflictError, WritePermissionError
from test_menu_recipe_bindings_db import scope_and_revision, state, assignment
from test_recipe_menu_binding_db import binding, app_engine, seeded_pg16, installed_pg16, pg16
from test_workflow_copy_store_db import _blocked_pair


@pytest.mark.parametrize('writer', ['assignment', 'week_context'])
@pytest.mark.parametrize('target', ['actor', 'role'])
def test_real_writer_holds_original_actor_and_role_locks(binding, writer, target):
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    context = get_week_review(engine, scope, date(2026, 9, 7))
    guarded, release = Event(), Event()

    def after_guard(_conn, _cursor, statement, _params, _ctx, _many):
        if 'begin_menu_binding_write_v26' in statement and not guarded.is_set():
            guarded.set()
            assert release.wait(10)

    def write():
        if writer == 'assignment':
            return assignments.replace_component_links(engine, scope, ids['item'], [assignment(revision)], 1)
        return review_week_context(engine, scope, date(2026, 9, 7), context['token'])

    event.listen(engine, 'after_cursor_execute', after_guard)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(write)
            assert guarded.wait(10)
            try:
                with pytest.raises(DBAPIError) as rejected:
                    with owner.begin() as connection:
                        connection.execute(text("SET LOCAL lock_timeout='250ms'"))
                        connection.execute(text(
                            'UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'
                            if target == 'actor' else "UPDATE cafeteria.application_roles SET active=false "
                            "WHERE role_code='Cafeteria.Publisher'"), ids)
                assert rejected.value.orig.sqlstate == '55P03'
                assert not future.done()
            finally:
                release.set()
            future.result(timeout=10)
    finally:
        release.set()
        event.remove(engine, 'after_cursor_execute', after_guard)
    if writer == 'assignment':
        assert state(owner, ids)[0][1] == 2
    else:
        assert get_week_review(engine, scope, date(2026, 9, 7))['receipt'] is not None


@pytest.mark.parametrize('change', ['authz', 'disabled'])
def test_week_context_original_get_expectation_cannot_be_refreshed(binding, change):
    owner, engine, ids = binding
    scope, _ = scope_and_revision(owner, ids)
    context = get_week_review(engine, scope, date(2026, 9, 7))
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:actor'
            if change == 'authz' else 'UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'), ids)
    with pytest.raises((WriteConflictError, WritePermissionError)):
        review_week_context(engine, scope, date(2026, 9, 7), context['token'])
    assert get_week_review(engine, scope, date(2026, 9, 7)) == context


def test_changed_catalog_food_pointer_conflicts_without_inverse_head_lock(binding, monkeypatch):
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    with owner.begin() as connection:
        component = str(connection.execute(text('UPDATE cafeteria.menu_components SET food_id=:location_food '
            'WHERE id=:exact RETURNING public_id'), ids).scalar_one())
        new_food = connection.execute(text('''INSERT INTO cafeteria.foods(location_id,created_by,updated_by,
            name,base_unit_id) SELECT :location,:actor,:actor,'Neue Zutat',id
            FROM cafeteria.measurement_units WHERE code='G' RETURNING id'''), ids).scalar_one()
        connection.execute(text('''INSERT INTO cafeteria.food_storage_locations(
            location_id,food_id,storage_location_id) VALUES(:location,:food,:storage)'''),
            {**ids, 'food': new_food, 'storage': ids['location_storage']})
    before = state(owner, ids)
    prepared, release = Event(), Event()
    original = assignments.prepare_bindings
    locked_foods = []

    def capture(_conn, _cursor, statement, params, _ctx, _many):
        if 'lock_component_foods_v26' in statement:
            locked_foods.append(list(params['ids']))

    def pause(*args, **kwargs):
        result = original(*args, **kwargs)
        prepared.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(assignments, 'prepare_bindings', pause)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(assignments.replace_component_links, engine, scope, ids['item'],
                [{**assignment(revision), 'component_public_id': component, 'component_text': None}], 1)
            assert prepared.wait(10)
            try:
                with owner.begin() as connection:
                    connection.execute(text('UPDATE cafeteria.menu_components SET food_id=:food WHERE id=:exact'),
                                       {**ids, 'food': new_food})
            finally:
                release.set()
            with pytest.raises(ComponentConflictError, match='zwischenzeitlich'):
                future.result(timeout=10)
    finally:
        release.set()
        event.remove(engine, 'before_cursor_execute', capture)
    assert state(owner, ids) == before
    assert locked_foods == [[ids['location_food']]]


@pytest.mark.parametrize('first_name', ['binding', 'review'])
def test_binding_and_review_real_blocking_has_one_cas_winner(binding, first_name):
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    token = get_component_review_token(engine, scope, ids['item'])
    second_engine = create_engine(engine.url, poolclass=NullPool)
    calls = {
        'binding': (engine, lambda: assignments.replace_component_links(
            engine, scope, ids['item'], [assignment(revision)], 1)),
        'review': (second_engine, lambda: review_component(second_engine, scope, ids['item'], token, 1)),
    }
    second_name = 'review' if first_name == 'binding' else 'binding'
    try:
        first, second = _blocked_pair(SimpleNamespace(owner=owner), calls[first_name][0],
            calls[second_name][0], '/* assignment_week_lock */', '/* assignment_week_lock */',
            calls[first_name][1], calls[second_name][1])
    finally:
        second_engine.dispose()
    assert first == ('ok', 2)
    assert second[0] == 'error' and isinstance(second[1], ComponentConflictError)
    saved = state(owner, ids)
    assert saved[0][1:] == (2, 'not_checked' if first_name == 'binding' else 'checked')
    assert len(saved[2]) == (1 if first_name == 'binding' else 0)
    assert len(saved[1]) == (1 if first_name == 'binding' else 0)
