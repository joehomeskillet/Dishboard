"""Real PostgreSQL preservation of step provenance and meaningful aggregate audit."""
import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from cafeteria import master_data_store as masters
from cafeteria import recipe_store as store
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeConflictError
from test_recipe_revision_immutable_db import png
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, mutable, target, snapshot,
)
from test_recipe_store_db import master as master


def audits(owner, public_id):
    with owner.connect() as current:
        return current.execute(text(
            'SELECT details FROM cafeteria.audit_events '
            'WHERE entity_public_id=CAST(:id AS uuid) ORDER BY id'
        ), {'id': public_id}).scalars().all()


@pytest.mark.parametrize('historical', [False, True])
def test_step_image_requires_its_provenance_in_current_aggregate(master, historical):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    attached = store.add_recipe_image(
        engine, actor, target(recipe), data=png(), content_type='image/png',
        source_url='https://example.test/licensed.png', source_license='CC0',
        fetched_at=datetime(2026, 9, 7, tzinfo=timezone.utc), expected_location_id=location,
    )
    data = mutable(store.get_recipe(engine, recipe.public_id).payload)
    data['steps'][0]['image_sha256'] = hashlib.sha256(png()).hexdigest()
    linked = store.update_recipe(engine, actor, target(attached), data, expected_location_id=location)
    if historical:
        frozen = store.freeze_revision(engine, actor, target(linked), expected_location_id=location)
        linked = ObjectExpectation(recipe.public_id, frozen.recipe_row_version)
    data['images'] = []
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError):
        store.update_recipe(engine, actor, target(linked), data, expected_location_id=location)
    assert snapshot(owner) == before
    read = store.get_recipe(engine, recipe.public_id)
    frozen = store.freeze_revision(engine, actor, target(read), expected_location_id=location) if not historical else frozen
    image = store.get_revision(engine, frozen.public_id).snapshot['recipe']['images'][0]
    assert image['source_url'] == 'https://example.test/licensed.png'
    assert image['source_license'] == 'CC0'
    assert datetime.fromisoformat(image['fetched_at']) == datetime(2026, 9, 7, tzinfo=timezone.utc)
    # Explicitly removing both references remains a valid ordinary edit.
    data['steps'][0]['image_sha256'] = None
    current = store.get_recipe(engine, recipe.public_id)
    store.update_recipe(engine, actor, target(current), data, expected_location_id=location)
    assert store.get_recipe(engine, recipe.public_id).payload['images'] == ()


@pytest.mark.parametrize('field,value', [
    ('title', 'Neue Suppe'), ('description', 'Neue Beschreibung\nZweite Zeile'),
    ('servings', '6.25'), ('servings_unit_code', 'G'),
    ('prep_minutes', 12), ('cook_minutes', 25),
    ('steps', [{'instruction': 'Anders kochen', 'duration_minutes': 3, 'image_sha256': None}]),
    ('tag_public_ids', None),
])
def test_recipe_audit_records_exact_changed_fields_and_noop(master, field, value):
    owner, engine, actor = master
    location = store.get_location(engine)
    if field == 'tag_public_ids':
        tag = masters.create_vocabulary(engine, 'tag', actor, code='REGIONAL', name='Regional')
        value = [tag.public_id]
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    original = mutable(store.get_recipe(engine, recipe.public_id).payload)
    changed = mutable(original)
    changed[field] = value
    before = audits(owner, recipe.public_id)
    result = store.update_recipe(engine, actor, target(recipe), changed, expected_location_id=location)
    after = audits(owner, recipe.public_id)
    actual = mutable(store.get_recipe(engine, recipe.public_id).payload)
    assert len(after) == len(before) + 1
    assert after[-1]['changes'] == {field: {'before': original[field], 'after': actual[field]}}
    assert after[-1]['row_version_before'] == recipe.row_version
    assert after[-1]['row_version_after'] == result.row_version == recipe.row_version + 1
    before_noop = snapshot(owner)
    assert store.update_recipe(engine, actor, target(result), actual, expected_location_id=location) == result
    assert snapshot(owner) == before_noop


def test_cookbook_audit_records_order_removal_and_header_changes(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    first = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    second = store.create_recipe(engine, actor, payload(title='Zweite'), expected_location_id=location)
    book = store.create_cookbook(engine, actor, name='Sammlung', expected_location_id=location)
    previous = []
    for ids in ([first.public_id, second.public_id], [second.public_id, first.public_id], [first.public_id], []):
        before = audits(owner, book.public_id)
        book = store.replace_cookbook_recipes(engine, actor, target(book), ids, expected_location_id=location)
        after = audits(owner, book.public_id)
        assert len(after) == len(before) + 1
        assert after[-1]['changes'] == {'recipe_public_ids': {'before': previous, 'after': ids}}
        before_noop = snapshot(owner)
        assert store.replace_cookbook_recipes(engine, actor, target(book), ids, expected_location_id=location) == book
        assert snapshot(owner) == before_noop
        previous = ids
    before = audits(owner, book.public_id)
    store.update_cookbook(engine, actor, target(book), name='Neu', description='Text', expected_location_id=location)
    after = audits(owner, book.public_id)
    assert len(after) == len(before) + 1
    assert after[-1]['changes'] == {
        'name': {'before': 'Sammlung', 'after': 'Neu'},
        'description': {'before': None, 'after': 'Text'},
    }
