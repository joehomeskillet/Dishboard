"""Per-recipe image identity and immutable provenance on real PostgreSQL."""
import io
from datetime import datetime, timezone

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import recipe_store as store
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeConflictError, RecipeValidationError
from test_recipe_revision_immutable_db import png
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, mutable, target, snapshot, complete_line,
)
from test_recipe_store_db import master as master


ORIGIN = {'source_url': 'https://example.test/original.png', 'source_license': 'CC0',
          'fetched_at': datetime(2026, 9, 7, tzinfo=timezone.utc)}


def state(owner):
    result = snapshot(owner)
    with owner.connect() as connection:
        result['settings'] = connection.execute(text(
            'SELECT to_jsonb(s)::text FROM cafeteria.settings s ORDER BY to_jsonb(s)::text'
        )).all()
    return result


def attach(engine, actor, row, **changes):
    return store.add_recipe_image(
        engine, actor, target(row), data=png(), content_type='image/png',
        caption='Original', expected_location_id=store.get_location(engine),
        **(ORIGIN | changes),
    )


def setup_image(engine, actor, historical=False):
    location = store.get_location(engine)
    data = payload(ingredients=[complete_line(engine, actor)]) if historical else payload()
    row = store.create_recipe(engine, actor, data, expected_location_id=location)
    row = attach(engine, actor, row)
    if historical:
        preview = store.get_dependency_preview(engine, target(row), expected_location_id=location)
        revision = store.freeze_revision(engine, actor, target(row), expected_location_id=location,
                                         expected_dependency_hash=preview.dependency_hash_sha256)
        data = mutable(store.get_recipe(engine, row.public_id).payload)
        data['images'] = []
        row = store.update_recipe(engine, actor, ObjectExpectation(row.public_id, revision.recipe_row_version),
                                  data, expected_location_id=location)
    return row


@pytest.mark.parametrize('historical', [False, True], ids=['current', 'historical'])
@pytest.mark.parametrize('change', [
    {'source_url': 'https://example.test/other.png'},
    {'source_license': 'Changed license'},
    {'fetched_at': datetime(2026, 9, 8, tzinfo=timezone.utc)},
    {'source_url': None, 'source_license': None, 'fetched_at': None},
], ids=['url', 'license', 'timestamp', 'erased'])
def test_add_same_image_rejects_changed_provenance_atomically(master, historical, change):
    owner, engine, actor = master
    row = setup_image(engine, actor, historical)
    before = state(owner)
    with pytest.raises(RecipeConflictError):
        attach(engine, actor, row, **change)
    assert state(owner) == before


def test_current_identical_image_is_noop_including_version_audit_settings(master):
    owner, engine, actor = master
    row = setup_image(engine, actor)
    before = state(owner)
    assert attach(engine, actor, row) == row
    assert state(owner) == before
    assert len(store.get_recipe(engine, row.public_id).payload['images']) == 1


def test_add_cannot_change_current_caption_but_aggregate_can_edit_and_reorder(master):
    owner, engine, actor = master
    row = setup_image(engine, actor)
    location = store.get_location(engine)
    before = state(owner)
    with pytest.raises(RecipeConflictError):
        store.add_recipe_image(engine, actor, target(row), data=png(), content_type='image/png',
                               caption='Changed', expected_location_id=location, **ORIGIN)
    assert state(owner) == before
    stream = io.BytesIO()
    Image.new('RGB', (3, 2), (20, 30, 40)).save(stream, format='PNG')
    second = store.add_recipe_image(engine, actor, target(row), data=stream.getvalue(),
                                   content_type='image/png', caption='Second', expected_location_id=location)
    data = mutable(store.get_recipe(engine, row.public_id).payload)
    original_hash = data['images'][0]['sha256']
    data['images'][0]['caption'] = 'Changed'
    data['images'].reverse()
    edited = store.update_recipe(engine, actor, target(second), data, expected_location_id=location)
    read = store.get_recipe(engine, row.public_id)
    assert edited.row_version == second.row_version + 1
    assert [image['caption'] for image in read.payload['images']] == ['Second', 'Changed']
    assert read.payload['images'][1]['sha256'] == original_hash
    assert read.payload['images'][1]['source_license'] == 'CC0'


def test_duplicate_aggregate_hash_is_validation_error_with_no_partial_write(master):
    owner, engine, actor = master
    row = setup_image(engine, actor)
    data = mutable(store.get_recipe(engine, row.public_id).payload)
    data['title'] = 'Must not persist'
    data['images'].append(dict(data['images'][0], caption='Duplicate'))
    before = state(owner)
    with pytest.raises(RecipeValidationError):
        store.update_recipe(engine, actor, target(row), data, expected_location_id=store.get_location(engine))
    assert state(owner) == before


def test_historical_same_origin_can_reattach_with_new_caption_and_preserves_revision(master):
    owner, engine, actor = master
    row = setup_image(engine, actor, historical=True)
    before = state(owner)
    attached = store.add_recipe_image(engine, actor, target(row), data=png(), content_type='image/png',
        caption='Reattached', expected_location_id=store.get_location(engine), **ORIGIN)
    after = state(owner)
    assert attached.row_version == row.row_version + 1
    assert len(after['audit_events']) == len(before['audit_events']) + 1
    for table in ('recipe_revisions', 'recipe_assets', 'settings'):
        assert after[table] == before[table]
    image = store.get_recipe(engine, row.public_id).payload['images'][0]
    assert image['caption'] == 'Reattached' and image['source_license'] == 'CC0'


def test_same_bytes_in_two_recipes_keep_independent_provenance(master):
    owner, engine, actor = master
    first = setup_image(engine, actor)
    second = store.create_recipe(engine, actor, payload(title='Independent'),
                                 expected_location_id=store.get_location(engine))
    second = attach(engine, actor, second, source_license='Own permission')
    one = store.get_recipe(engine, first.public_id).payload['images'][0]
    two = store.get_recipe(engine, second.public_id).payload['images'][0]
    assert one['sha256'] == two['sha256']
    assert one['source_license'] == 'CC0' and two['source_license'] == 'Own permission'
    assert len(state(owner)['recipe_assets']) == 1
    before = state(owner)
    assert attach(engine, actor, second, source_license='Own permission') == second
    assert state(owner) == before


@pytest.mark.parametrize('historical', [False, True], ids=['current', 'historical'])
@pytest.mark.parametrize('field,value', [
    ('source_url', 'https://example.test/changed.png'),
    ('source_license', 'Changed'),
    ('fetched_at', '2026-09-08T00:00:00+00:00'),
])
def test_aggregate_cannot_rewrite_current_or_historical_image_origin(master, historical, field, value):
    owner, engine, actor = master
    row = setup_image(engine, actor)
    original_image = mutable(store.get_recipe(engine, row.public_id).payload['images'][0])
    if historical:
        location = store.get_location(engine)
        complete = mutable(store.get_recipe(engine, row.public_id).payload)
        complete['ingredients'] = [complete_line(engine, actor)]
        row = store.update_recipe(engine, actor, target(row), complete, expected_location_id=location)
        preview = store.get_dependency_preview(engine, target(row), expected_location_id=location)
        revision = store.freeze_revision(engine, actor, target(row), expected_location_id=location,
                                         expected_dependency_hash=preview.dependency_hash_sha256)
        data = mutable(store.get_recipe(engine, row.public_id).payload)
        data['images'] = []
        row = store.update_recipe(engine, actor, ObjectExpectation(row.public_id, revision.recipe_row_version),
                                  data, expected_location_id=store.get_location(engine))
    data = mutable(store.get_recipe(engine, row.public_id).payload)
    data['images'] = [dict(original_image, **{field: value})]
    before = state(owner)
    with pytest.raises(RecipeConflictError):
        store.update_recipe(engine, actor, target(row), data, expected_location_id=store.get_location(engine))
    assert state(owner) == before


def test_database_uniqueness_rejects_second_position_for_same_recipe_hash(master):
    owner, engine, actor = master
    setup_image(engine, actor)
    before = state(owner)
    with pytest.raises(DBAPIError) as failure:
        with owner.begin() as connection:
            connection.execute(text('''INSERT INTO cafeteria.recipe_images
                (location_id,recipe_id,sort_order,sha256,caption,source_url,source_license,fetched_at)
                SELECT location_id,recipe_id,2,sha256,caption,source_url,source_license,fetched_at
                FROM cafeteria.recipe_images'''))
    assert failure.value.orig.sqlstate == '23505'
    assert state(owner) == before
