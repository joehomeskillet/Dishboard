"""Recipe-bound summary pagination through the real PostgreSQL reader."""
from dataclasses import FrozenInstanceError, fields
from uuid import uuid4

import pytest
from flask import session
from sqlalchemy import event, text
from werkzeug.exceptions import Forbidden, Unauthorized

from cafeteria import recipe_store as store
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeNotFoundError, RecipeValidationError
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, mutable, target,
    snapshot, signed_in, complete_line,
)
from test_recipe_store_db import master as master


def test_summary_pagination_archive_and_immutable_original_metadata(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(ingredients=[complete_line(engine, actor)]), expected_location_id=location)
    revisions = []
    for number in range(1, 4):
        current = store.get_recipe(engine, recipe.public_id)
        data = mutable(current.payload)
        data['title'] = f'Rezept {number}'
        changed = store.update_recipe(engine, actor, target(current), data, expected_location_id=location)
        preview = store.get_dependency_preview(engine, target(changed), expected_location_id=location)
        revisions.append(store.freeze_revision(engine, actor, target(changed), expected_location_id=location,
                                                expected_dependency_hash=preview.dependency_hash_sha256))
    store.set_recipe_active(engine, actor, ObjectExpectation(recipe.public_id, revisions[-1].recipe_row_version),
                            active=False, expected_location_id=location)
    before = snapshot(owner)
    summaries = store.list_revisions(engine, recipe.public_id)
    assert isinstance(summaries, tuple)
    assert [row.public_id for row in summaries] == [row.public_id for row in reversed(revisions)]
    assert [row.revision_number for row in summaries] == [3, 2, 1]
    assert store.list_revisions(engine, recipe.public_id, limit=2) == summaries[:2]
    assert store.list_revisions(engine, recipe.public_id, limit=2, offset=2) == summaries[2:]
    assert store.list_revisions(engine, recipe.public_id, offset=3) == ()
    for summary in summaries:
        detail = store.get_revision(engine, summary.public_id)
        assert {field.name for field in fields(summary)} == {
            'public_id', 'recipe_public_id', 'revision_number', 'content_hash_sha256', 'created_at', 'created_by'}
        assert all(getattr(summary, field.name) == getattr(detail, field.name) for field in fields(summary))
        with pytest.raises(FrozenInstanceError):
            summary.revision_number = 999
    assert snapshot(owner) == before


def test_empty_missing_foreign_parent_and_read_only_snapshot(master):
    owner, engine, actor = master
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=store.get_location(engine))
    before = snapshot(owner)
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        assert store.list_revisions(engine, recipe.public_id) == ()
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY' in statements
    revision_queries = [sql for sql in statements if 'recipe_revisions' in sql]
    assert len(revision_queries) == 1
    assert 'snapshot_json' not in revision_queries[0] and '*' not in revision_queries[0]
    with pytest.raises(RecipeNotFoundError):
        store.list_revisions(engine, str(uuid4()), offset=100)
    assert snapshot(owner) == before
    with owner.begin() as current:
        current.execute(text('UPDATE cafeteria.locations SET active=false'))
        current.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Anderes Haus',true)"))
    before = snapshot(owner)
    with pytest.raises(RecipeNotFoundError):
        store.list_revisions(engine, recipe.public_id)
    assert snapshot(owner) == before


@pytest.mark.parametrize('options', [dict(limit=0), dict(limit=501), dict(limit=True),
                                    dict(limit=1.5), dict(offset=-1), dict(offset=True), dict(offset='0')])
def test_invalid_pagination_preserves_database(master, options):
    owner, engine, actor = master
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=store.get_location(engine))
    before = snapshot(owner)
    with pytest.raises(RecipeValidationError):
        store.list_revisions(engine, recipe.public_id, **options)
    assert snapshot(owner) == before


def test_reader_requires_current_read_capability(master, monkeypatch):
    from cafeteria import roles
    owner, engine, actor = master
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=store.get_location(engine))
    before = snapshot(owner)
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'recipe.write'})
    with pytest.raises(Forbidden):
        store.list_revisions(engine, recipe.public_id)
    session.clear()
    with pytest.raises(Unauthorized):
        store.list_revisions(engine, recipe.public_id)
    with owner.begin() as current:
        current.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    with signed_in(engine, actor):
        with pytest.raises(Unauthorized):
            store.list_revisions(engine, recipe.public_id)
    assert snapshot(owner) == before
