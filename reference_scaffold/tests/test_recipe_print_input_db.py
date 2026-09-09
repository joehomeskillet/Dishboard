"""Selected immutable revision/assets share the caller's active-location transaction."""
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from werkzeug.exceptions import Unauthorized

from cafeteria import recipe_store as store
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_reads import recipe_print_input
from cafeteria.recipe_types import RecipeNotFoundError, RecipeValidationError
from cafeteria.recipe_types import RevisionResult
from prepared_food_fixtures import legacy_freeze
from prepared_food_fixtures import create_food, create_recipe, freeze
from prepared_food_fixtures import prepared as prepared
from cafeteria.auth.local_users import ActorExpectation
from cafeteria.recipe_reads import _get_recipe_asset_connection
from test_recipe_revision_immutable_db import png
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, mutable, target, snapshot,
    signed_in,
)
from test_recipe_store_db import master as master


def freeze_image(engine, actor, *, owner=None):
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    attached = store.add_recipe_image(engine, actor, target(recipe), data=png(),
                                     content_type='image/png', expected_location_id=location)
    data = mutable(store.get_recipe(engine, recipe.public_id).payload)
    digest = data['images'][0]['sha256']
    data['steps'][0]['image_sha256'] = digest
    updated = store.update_recipe(engine, actor, target(attached), data, expected_location_id=location)
    revision = (RevisionResult(**legacy_freeze(owner,
        {'actor': actor.user_id, 'authz': actor.authz_version, 'location': location},
        {'public_id': updated.public_id, 'row_version': updated.row_version})) if owner is not None
        else store.freeze_revision(engine, actor, target(updated), expected_location_id=location))
    return recipe.public_id, revision, digest


def test_original_assets_survive_current_edits_and_archive_on_one_connection(master):
    owner, engine, actor = master
    recipe_id, frozen, digest = freeze_image(engine, actor, owner=owner)
    original = store.get_revision(engine, frozen.public_id)
    current = mutable(store.get_recipe(engine, recipe_id).payload)
    current.update(title='Neuer Entwurf', images=[])
    current['steps'][0]['image_sha256'] = None
    edited = store.update_recipe(engine, actor, ObjectExpectation(recipe_id, frozen.recipe_row_version),
                                 current, expected_location_id=store.get_location(engine))
    store.set_recipe_active(engine, actor, target(edited), active=False,
                            expected_location_id=store.get_location(engine))
    before = snapshot(owner)
    seen = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        seen.append(connection)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        with engine.begin() as connection:
            revision, assets = recipe_print_input(connection, recipe_id, frozen.public_id)
            assert seen and all(item is connection for item in seen)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert revision == original
    assert set(assets) == {digest} and assets[digest].data == png()
    assert assets[digest] == store.get_recipe_asset(engine, recipe_id, digest)
    assert snapshot(owner) == before


def test_revision_must_belong_to_selected_recipe_and_active_location(master):
    owner, engine, actor = master
    recipe_id, frozen, _ = freeze_image(engine, actor, owner=owner)
    other = store.create_recipe(engine, actor, payload(title='Anderes Rezept'),
                                expected_location_id=store.get_location(engine))
    for selected, revision in ((other.public_id, frozen.public_id), (recipe_id, str(uuid4()))):
        with engine.begin() as connection, pytest.raises(RecipeNotFoundError):
            recipe_print_input(connection, selected, revision)
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Anderes Haus',true)"))
    with engine.begin() as connection, pytest.raises(RecipeNotFoundError):
        recipe_print_input(connection, recipe_id, frozen.public_id)


@pytest.mark.parametrize('bad', [None, True, [], '', 'no-uuid', 'a' * 200])
@pytest.mark.parametrize('field', ['recipe', 'revision'])
def test_selection_uuid_boundary_rejects_malformed_values(master, bad, field):
    _, engine, _ = master
    identifiers = [str(uuid4()), str(uuid4())]
    identifiers[0 if field == 'recipe' else 1] = bad
    with engine.begin() as connection, pytest.raises(RecipeValidationError):
        recipe_print_input(connection, *identifiers)


def test_public_engine_readers_keep_readonly_transactions_and_current_capability(master):
    owner, engine, actor = master
    recipe_id, frozen, digest = freeze_image(engine, actor, owner=owner)
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        revision = store.get_revision(engine, frozen.public_id)
        asset = store.get_recipe_asset(engine, recipe_id, digest)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert statements.count('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY') == 2
    assert revision.public_id == frozen.public_id and asset.data == png()
    with owner.begin() as connection:
        connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), {'actor': actor.user_id})
    with signed_in(engine, actor):
        with pytest.raises(Unauthorized):
            store.get_revision(engine, frozen.public_id)
        with pytest.raises(Unauthorized):
            store.get_recipe_asset(engine, recipe_id, digest)


def test_prepared_child_photo_is_selected_by_child_identity_not_parent_or_global_hash(prepared):
    owner, engine, ids = prepared
    actor = ActorExpectation(ids['actor'], ids['authz'])
    raw = create_food(engine, ids, 'Gemüse')
    child = create_recipe(engine, ids, [raw], name='Fotografierte Zubereitung')
    with signed_in(engine, actor):
        attached = store.add_recipe_image(engine, actor, ObjectExpectation(child['public_id'], child['row_version']),
            data=png(), content_type='image/png', expected_location_id=ids['location'])
    child_revision = freeze(engine, ids, {'public_id': child['public_id'], 'row_version': attached.row_version})
    food = create_food(engine, ids, 'Vorbereitete Zutat', pin=child_revision)
    root = freeze(engine, ids, create_recipe(engine, ids, [food]))
    before = snapshot(owner)
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'))
            revision, images = recipe_print_input(connection, root['recipe_public_id'], root['public_id'])
            assert len(images) == 1 and next(iter(images.values())).data == png()
            digest = next(iter(images))
            assert revision.snapshot['recipe']['images'] == ()
            assert revision.prepared_revisions[0].snapshot['recipe']['images'][0]['sha256'] == digest
            with pytest.raises(RecipeNotFoundError):
                _get_recipe_asset_connection(connection, ids['location'], root['recipe_public_id'], digest)
    assert snapshot(owner) == before
