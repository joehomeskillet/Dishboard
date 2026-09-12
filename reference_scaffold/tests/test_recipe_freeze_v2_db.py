"""Original dependency previews and atomic SQL27 through the public service."""
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from werkzeug.exceptions import Forbidden, Unauthorized

from cafeteria import recipe_reads, recipe_store as store, roles
from cafeteria.auth.local_users import ActorExpectation
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_commands import freeze_command
from cafeteria.recipe_types import RecipeConflictError, RecipeValidationError
from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, create_food, create_recipe,
    update_food, food_payload, freeze, execute, state,
)
from prepared_food_fixtures import prepared as prepared
from test_master_data_db import signed_in


@pytest.mark.parametrize('bad', [None, False, [], '', '0' * 63, '0' * 65, 'A' * 64, '0' * 63 + '\n'])
def test_freeze_rejects_invalid_original_hash_before_database(bad):
    with pytest.raises(RecipeValidationError):
        freeze_command(None, ActorExpectation(1, 1), ObjectExpectation(str(uuid4()), 1), 1, bad)


@pytest.mark.parametrize('target,location', [(None, 1), (ObjectExpectation('bad', 1), 1),
    (ObjectExpectation(str(uuid4()), True), 1), (ObjectExpectation(str(uuid4()), 1), False)])
def test_preview_rejects_invalid_original_target_before_database(target, location):
    with pytest.raises(RecipeValidationError):
        recipe_reads.get_dependency_preview(None, target, expected_location_id=location)


def selection(recipe):
    return ObjectExpectation(recipe['public_id'], recipe['row_version'])


def full_state(owner):
    with owner.connect() as connection:
        tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='cafeteria' ORDER BY tablename")).scalars()
        result = {name: connection.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{name} t ORDER BY to_jsonb(t)::text')).all()
                  for name in tables}
        result['sequences'] = connection.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='cafeteria' ORDER BY sequencename")).all()
        return result


def test_public_preview_is_immutable_readonly_and_freeze_has_exact_one_audit(prepared):
    owner, engine, ids = prepared
    recipe = create_recipe(engine, ids, [create_food(engine, ids)])
    actor = ActorExpectation(ids['actor'], ids['authz'])
    statements = []
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)
    with signed_in(engine, actor):
        before = full_state(owner)
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            preview = store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
        assert preview.complete and preview.issues == ()
        assert statements.count('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY') == 1
        assert sum('recipe_dependency_preview_v27' in sql for sql in statements) == 1
        assert full_state(owner) == before
        with pytest.raises(FrozenInstanceError):
            preview.complete = False
        with pytest.raises(TypeError):
            preview.snapshot['recipe']['title'] = 'Changed'
        with pytest.raises(AttributeError):
            preview.snapshot['recipe']['ingredients'].append({})
        revision = store.freeze_revision(engine, actor, selection(recipe), expected_location_id=ids['location'],
                                         expected_dependency_hash=preview.dependency_hash_sha256)
        assert revision.recipe_row_version == recipe['row_version'] + 1
        assert store.get_revision(engine, revision.public_id).snapshot == preview.snapshot
    with owner.connect() as connection:
        audits = connection.execute(text("SELECT details FROM cafeteria.audit_events WHERE action='recipe.freeze'")).scalars().all()
        assert len(audits) == 1 and audits[0]['dependency_hash_sha256'] == preview.dependency_hash_sha256
        assert audits[0]['content_hash_sha256'] == revision.content_hash_sha256
        assert connection.execute(text('SELECT count(*) FROM cafeteria.recipe_revisions')).scalar_one() == 1


@pytest.mark.parametrize('change', ['name', 'factor', 'storage_name', 'storage_assignment', 'unit_name', 'pin'])
def test_original_dependency_changes_reject_without_partial_freeze(prepared, change):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Basis')
    child = freeze(engine, ids, create_recipe(engine, ids, [raw]))
    food = create_food(engine, ids, 'Zutat')
    recipe = create_recipe(engine, ids, [food])
    actor = ActorExpectation(ids['actor'], ids['authz'])
    with signed_in(engine, actor):
        original = store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        if change in {'name', 'factor', 'pin'}:
            data = food_payload(ids, 'Neu' if change == 'name' else 'Zutat', pin=child if change == 'pin' else None)
            if change == 'factor':
                data['density_g_per_ml'] = '1.2'
            update_food(engine, ids, food, data)
        elif change == 'storage_assignment':
            storage = execute(engine, "SELECT cafeteria.create_storage_location_v21(:actor,:authz,:location,NULL,NULL,'{\"code\":\"OTHER\",\"name\":\"Anderes Lager\"}')", ids)
            update_food(engine, ids, food, food_payload(ids | {'storage': storage['public_id']}, 'Zutat'))
        else:
            with owner.begin() as connection:
                if change == 'storage_name':
                    connection.execute(text("UPDATE cafeteria.storage_locations SET name='Umbenannt' WHERE public_id=CAST(:id AS uuid)"), {'id': ids['storage']})
                else:
                    connection.execute(text("UPDATE cafeteria.measurement_units SET display_name='Anderes Gramm' WHERE code='G'"))
        before = full_state(owner)
        with pytest.raises(RecipeConflictError):
            store.freeze_revision(engine, actor, selection(recipe), expected_location_id=ids['location'],
                                  expected_dependency_hash=original.dependency_hash_sha256)
        assert full_state(owner) == before
        current = store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        assert current.dependency_hash_sha256 != original.dependency_hash_sha256


@pytest.mark.parametrize('ingredients', [[], [None]])
def test_incomplete_draft_preview_is_visible_and_freeze_rejects(prepared, ingredients):
    owner, engine, ids = prepared
    recipe = create_recipe(engine, ids, ingredients)
    actor = ActorExpectation(ids['actor'], ids['authz'])
    with signed_in(engine, actor):
        original = full_state(owner)
        preview = store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        assert not preview.complete and [(issue.field, issue.code) for issue in preview.issues] == [('ingredients', 'incomplete')]
        with pytest.raises(RecipeValidationError):
            store.freeze_revision(engine, actor, selection(recipe), expected_location_id=ids['location'],
                                  expected_dependency_hash=preview.dependency_hash_sha256)
        assert full_state(owner) == original


def test_preview_requires_current_read_and_freeze_current_write_before_sql(prepared, monkeypatch):
    owner, engine, ids = prepared
    recipe = create_recipe(engine, ids, [create_food(engine, ids)])
    actor = ActorExpectation(ids['actor'], ids['authz'])
    with signed_in(engine, actor):
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
        preview = store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        before = full_state(owner)
        with pytest.raises(Forbidden):
            store.freeze_revision(engine, actor, selection(recipe), expected_location_id=ids['location'],
                                  expected_dependency_hash=preview.dependency_hash_sha256)
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'recipe.write'})
        with pytest.raises(Forbidden):
            store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        from flask import session
        session.clear()
        with pytest.raises(Unauthorized):
            store.get_dependency_preview(engine, selection(recipe), expected_location_id=ids['location'])
        assert full_state(owner) == before
