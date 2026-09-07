"""Immutable snapshots and original associated image bytes under real PostgreSQL."""
import hashlib
import io
from datetime import datetime, timezone

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import master_data_store as masters
from cafeteria import recipe_store as store
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeConflictError, RecipeNotFoundError, RecipeValidationError
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, line, mutable, target, snapshot,
)
from test_recipe_store_db import master as master


def png():
    stream = io.BytesIO()
    Image.new('RGB', (3, 2), (200, 100, 50)).save(stream, format='PNG')
    return stream.getvalue()


def test_freeze_explicit_identical_conflict_and_changed_food_snapshot(master):
    owner, engine, actor = master
    food = masters.create_food(engine, actor, {'name': 'Milch', 'base_unit_code': 'ML', 'density_g_per_ml': '1.03'})
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(ingredients=[line(food_public_id=food.public_id, unit_code='ML')]), expected_location_id=location)
    assert snapshot(owner)['recipe_revisions'] == []
    frozen = store.freeze_revision(engine, actor, target(recipe), expected_location_id=location)
    first = store.get_revision(engine, frozen.public_id)
    assert first.snapshot['foods'][0]['density_g_per_ml'] == '1.03'
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError):
        store.freeze_revision(engine, actor, ObjectExpectation(recipe.public_id, frozen.recipe_row_version), expected_location_id=location)
    assert snapshot(owner) == before
    masters.update_food(engine, actor, target(food), {'name': 'Milch', 'base_unit_code': 'ML', 'density_g_per_ml': '1.04'})
    second = store.freeze_revision(engine, actor, ObjectExpectation(recipe.public_id, frozen.recipe_row_version), expected_location_id=location)
    assert second.revision_number == 2 and second.recipe_row_version == frozen.recipe_row_version + 1
    assert second.content_hash_sha256 != first.content_hash_sha256
    assert store.get_revision(engine, first.public_id) == first
    with pytest.raises(TypeError):
        first.snapshot['recipe']['title'] = 'Changed'
    with owner.connect() as current:
        canonical = current.execute(text('SELECT snapshot_json::text FROM cafeteria.recipe_revisions WHERE public_id=CAST(:id AS uuid)'), {'id': first.public_id}).scalar_one()
    assert hashlib.sha256(canonical.encode()).hexdigest() == first.content_hash_sha256
    for statement in ('UPDATE cafeteria.recipe_revisions SET revision_number=99',
                      'DELETE FROM cafeteria.recipe_revisions', 'TRUNCATE cafeteria.recipe_revisions'):
        with pytest.raises(DBAPIError):
            with owner.begin() as current:
                current.execute(text(statement))
    assert store.get_revision(engine, first.public_id) == first


def test_image_caption_edit_preserves_original_source_and_rejects_source_erasure(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    attached = store.add_recipe_image(engine, actor, target(recipe), data=png(), content_type='image/png',
        source_url='https://example.test/licensed.png', source_license='CC0',
        fetched_at=datetime(2026, 9, 7, tzinfo=timezone.utc), expected_location_id=location)
    data = mutable(store.get_recipe(engine, recipe.public_id).payload)
    data['images'][0]['caption'] = 'Neue Bildunterschrift'
    edited = store.update_recipe(engine, actor, target(attached), data, expected_location_id=location)
    read = store.get_recipe(engine, recipe.public_id)
    assert read.payload['images'][0]['source_url'] == 'https://example.test/licensed.png'
    assert read.payload['images'][0]['caption'] == 'Neue Bildunterschrift'
    data = mutable(read.payload)
    data['images'][0].update(source_url=None, source_license=None, fetched_at=None)
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError):
        store.update_recipe(engine, actor, target(edited), data, expected_location_id=location)
    assert snapshot(owner) == before


def test_historical_image_stays_authorized_after_draft_removal_without_global_hash_lookup(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    unrelated = store.create_recipe(engine, actor, payload(title='Anderes Rezept'), expected_location_id=location)
    data = png()
    digest = hashlib.sha256(data).hexdigest()
    with_image = store.add_recipe_image(engine, actor, target(recipe), data=data, content_type='image/png', expected_location_id=location)
    frozen = store.freeze_revision(engine, actor, target(with_image), expected_location_id=location)
    edited = mutable(store.get_recipe(engine, recipe.public_id).payload)
    edited['images'] = []
    store.update_recipe(engine, actor, ObjectExpectation(recipe.public_id, frozen.recipe_row_version), edited, expected_location_id=location)
    asset = store.get_recipe_asset(engine, recipe.public_id, digest)
    assert asset.data == data and (asset.width, asset.height) == (3, 2)
    with pytest.raises(RecipeNotFoundError):
        store.get_recipe_asset(engine, unrelated.public_id, digest)
    before = snapshot(owner)
    stolen = payload(images=[{'sha256': digest, 'caption': None, 'source_url': None, 'source_license': None, 'fetched_at': None}])
    with pytest.raises(RecipeNotFoundError):
        store.update_recipe(engine, actor, target(unrelated), stolen, expected_location_id=location)
    assert snapshot(owner) == before
    attached = store.add_recipe_image(engine, actor, target(unrelated), data=data, content_type='image/png', expected_location_id=location)
    assert attached.row_version == unrelated.row_version + 1 and len(snapshot(owner)['recipe_assets']) == 1
    for statement in ('UPDATE cafeteria.recipe_assets SET width=4', 'DELETE FROM cafeteria.recipe_assets',
                      'TRUNCATE cafeteria.recipe_assets CASCADE'):
        with pytest.raises(DBAPIError):
            with owner.begin() as current:
                current.execute(text(statement))


@pytest.mark.parametrize('bad', ['corrupt', 'wrong_type', 'too_large', 'no_license', 'stale'])
def test_image_failure_has_no_asset_link_version_or_audit_effect(master, bad):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    data, content_type = png(), 'image/png'
    options = {}
    if bad == 'corrupt':
        data = data[:12]
    elif bad == 'wrong_type':
        content_type = 'image/jpeg'
    elif bad == 'too_large':
        data = data + b'x' * 1048576
    elif bad == 'no_license':
        options['source_url'] = 'https://example.test/photo.png'
    else:
        store.set_recipe_active(engine, actor, target(recipe), active=False, expected_location_id=location)
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError if bad == 'stale' else RecipeValidationError):
        store.add_recipe_image(engine, actor, target(recipe), data=data, content_type=content_type, expected_location_id=location, **options)
    assert snapshot(owner) == before
