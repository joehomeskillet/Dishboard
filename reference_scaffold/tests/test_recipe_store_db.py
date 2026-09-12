"""Actual PostgreSQL aggregate, identity, audit and cookbook contracts."""
from collections.abc import Mapping
from uuid import uuid4

import pytest
from sqlalchemy import text

from cafeteria import recipe_store as store
from cafeteria import master_data_store as masters
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeConflictError, RecipeValidationError
from test_master_data_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, make_actor, signed_in,
    STORAGE_PUBLIC_ID,
)
from test_master_data_db import master as master


def mutable(value):
    if isinstance(value, Mapping):
        return {key: mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [mutable(item) for item in value]
    return value


def line(name='Karotte', **changes):
    return {'line_public_id': None, 'group_label': None, 'ingredient_text': name,
            'food_public_id': None, 'quantity': '1', 'unit_code': 'G', 'note': None,
            'source_kind': 'manual', 'source_reference': None, 'fetched_at': None, **changes}


def payload(**changes):
    return {'title': 'Suppe', 'description': 'Erster Absatz\n\nZweiter Absatz', 'servings': '4',
            'servings_unit_code': 'PORTION', 'prep_minutes': 10, 'cook_minutes': None,
            'source': {'kind': 'manual', 'reference': None, 'url': None, 'note': None, 'fetched_at': None},
            'ingredients': [line()], 'steps': [{'instruction': 'Waschen\nDann kochen',
              'duration_minutes': 0, 'image_sha256': None}], 'tag_public_ids': [], 'images': [], **changes}


def target(row):
    return ObjectExpectation(row.public_id, row.row_version)


def complete_line(engine, actor, name='Karotte', **changes):
    """Explicit v27 fixture ingredient; generic draft payloads stay incomplete."""
    food = masters.create_food(engine, actor, {'name': name, 'base_unit_code': changes.get('unit_code', 'G'),
        'storage_location_public_ids': [STORAGE_PUBLIC_ID]})
    return line(name, food_public_id=food.public_id, **changes)


def snapshot(owner):
    tables = ('recipes', 'recipe_ingredients', 'recipe_steps', 'recipe_images', 'recipe_tags',
              'recipe_revisions', 'recipe_assets', 'cookbooks', 'cookbook_recipes', 'audit_events')
    with owner.connect() as current:
        return {table: current.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all()
                for table in tables}


def test_recipe_roundtrip_noop_cas_and_archive(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    row = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    read = store.get_recipe(engine, row.public_id)
    assert read.row_version == 1 and read.active
    assert read.payload['description'] == 'Erster Absatz\n\nZweiter Absatz'
    assert read.payload['ingredients'][0]['line_public_id']
    before = snapshot(owner)
    assert store.update_recipe(engine, actor, target(read), read.payload, expected_location_id=location) == row
    assert snapshot(owner) == before
    edited = mutable(read.payload)
    edited['title'] = 'Neue Suppe'
    changed = store.update_recipe(engine, actor, target(read), edited, expected_location_id=location)
    assert changed.row_version == 2
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError):
        store.update_recipe(engine, actor, target(read), edited, expected_location_id=location)
    assert snapshot(owner) == before
    archived = store.set_recipe_active(engine, actor, target(changed), active=False, expected_location_id=location)
    assert store.list_recipes(engine) == ()
    assert store.list_recipes(engine, include_archived=True)[0].public_id == row.public_id
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError):
        store.set_recipe_active(engine, actor, target(archived), active=False, expected_location_id=location)
    with pytest.raises(RecipeConflictError):
        original = store.get_dependency_preview(engine, target(archived), expected_location_id=location)
        store.freeze_revision(engine, actor, target(archived), expected_location_id=location,
                              expected_dependency_hash=original.dependency_hash_sha256)
    assert snapshot(owner) == before
    assert store.set_recipe_active(engine, actor, target(archived), active=True, expected_location_id=location).row_version == 4


def test_line_identity_survives_reorder_insert_edit_remove_and_revision(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    source = {'source_kind': 'url', 'source_reference': 'https://example.test/original', 'fetched_at': '2026-09-07T08:00:00+00:00'}
    recipe = store.create_recipe(engine, actor, payload(ingredients=[complete_line(engine, actor, 'Erste', **source),
        complete_line(engine, actor, 'Zweite')]), expected_location_id=location)
    read = store.get_recipe(engine, recipe.public_id)
    original = mutable(read.payload)
    preview = store.get_dependency_preview(engine, target(read), expected_location_id=location)
    revision = store.freeze_revision(engine, actor, target(read), expected_location_id=location,
                                     expected_dependency_hash=preview.dependency_hash_sha256)
    edited = mutable(original)
    first, second = edited['ingredients']
    first.update(ingredient_text='Geändert', quantity='2')
    edited['ingredients'] = [second, line('Neu'), first]
    changed = store.update_recipe(engine, actor, ObjectExpectation(recipe.public_id, revision.recipe_row_version), edited, expected_location_id=location)
    read = store.get_recipe(engine, recipe.public_id)
    assert read.payload['ingredients'][2]['line_public_id'] == original['ingredients'][0]['line_public_id']
    assert read.payload['ingredients'][2]['source_reference'] == source['source_reference']
    assert read.payload['ingredients'][1]['line_public_id'] not in {first['line_public_id'], second['line_public_id']}
    edited = mutable(read.payload)
    edited['ingredients'].pop(2)
    store.update_recipe(engine, actor, target(changed), edited, expected_location_id=location)
    assert len(store.get_recipe(engine, recipe.public_id).payload['ingredients']) == 2
    assert store.get_revision(engine, revision.public_id).snapshot['recipe']['ingredients'][0]['source_reference'] == source['source_reference']


@pytest.mark.parametrize('bad', ['foreign', 'unknown', 'duplicate', 'source'])
def test_rejects_wrong_line_identity_or_changed_provenance_atomically(master, bad):
    owner, engine, actor = master
    location = store.get_location(engine)
    first = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    second = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    read = store.get_recipe(engine, first.public_id)
    data = mutable(read.payload)
    if bad == 'foreign':
        data['ingredients'][0]['line_public_id'] = store.get_recipe(engine, second.public_id).payload['ingredients'][0]['line_public_id']
    elif bad == 'unknown':
        data['ingredients'][0]['line_public_id'] = str(uuid4())
    elif bad == 'duplicate':
        data['ingredients'].append(dict(data['ingredients'][0]))
    else:
        data['ingredients'][0]['source_reference'] = 'Rewritten'
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError if bad == 'source' else RecipeValidationError):
        store.update_recipe(engine, actor, target(read), data, expected_location_id=location)
    assert snapshot(owner) == before


def test_cookbook_assignment_noop_order_and_archive(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    first = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    second = store.create_recipe(engine, actor, payload(title='Zweite'), expected_location_id=location)
    book = store.create_cookbook(engine, actor, name='Sammlung', expected_location_id=location)
    assigned = store.replace_cookbook_recipes(engine, actor, target(book), [second.public_id, first.public_id], expected_location_id=location)
    assert store.get_cookbook(engine, book.public_id).recipe_public_ids == (second.public_id, first.public_id)
    before = snapshot(owner)
    assert store.replace_cookbook_recipes(engine, actor, target(assigned), [second.public_id, first.public_id], expected_location_id=location) == assigned
    assert snapshot(owner) == before
    archived = store.set_cookbook_active(engine, actor, target(assigned), active=False, expected_location_id=location)
    assert store.list_cookbooks(engine) == ()
    with pytest.raises(RecipeConflictError):
        store.replace_cookbook_recipes(engine, actor, target(archived), [], expected_location_id=location)
    assert store.list_cookbooks(engine, include_archived=True)[0].public_id == book.public_id


@pytest.mark.parametrize('kind', ['food', 'unit', 'tag'])
def test_archived_refs_remain_only_on_original_logical_association(master, kind):
    owner, engine, actor = master
    location = store.get_location(engine)
    data = payload()
    if kind == 'food':
        reference = masters.create_food(engine, actor, {'name': 'Karotte', 'base_unit_code': 'G',
            'storage_location_public_ids': [STORAGE_PUBLIC_ID]})
        data['ingredients'][0]['food_public_id'] = reference.public_id
    elif kind == 'unit':
        reference = masters.create_unit(engine, actor, code='BOX', display_name='Box', dimension='count', base_factor='2')
        data['ingredients'][0]['unit_code'] = 'BOX'
    else:
        reference = masters.create_vocabulary(engine, 'tag', actor, code='REGIONAL', name='Regional')
        data['tag_public_ids'] = [reference.public_id]
    recipe = store.create_recipe(engine, actor, data, expected_location_id=location)
    if kind == 'food':
        masters.set_food_active(engine, actor, target(reference), active=False)
    elif kind == 'unit':
        masters.set_unit_active(engine, actor, target(reference), active=False)
    else:
        masters.set_vocabulary_active(engine, 'tag', actor, target(reference), active=False)
    read = store.get_recipe(engine, recipe.public_id)
    before = snapshot(owner)
    assert store.update_recipe(engine, actor, target(read), read.payload, expected_location_id=location) == recipe
    assert snapshot(owner) == before
    edited = mutable(read.payload)
    if kind == 'tag':
        with pytest.raises(RecipeConflictError):
            store.create_recipe(engine, actor, data, expected_location_id=location)
    else:
        replacement = dict(edited['ingredients'][0], line_public_id=None)
        edited['ingredients'].append(replacement)
        with pytest.raises(RecipeConflictError):
            store.update_recipe(engine, actor, target(read), edited, expected_location_id=location)
    assert snapshot(owner) == before


def test_read_calls_preserve_database_and_duplicate_titles_are_valid(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    first = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    second = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    before = snapshot(owner)
    assert {row.public_id for row in store.list_recipes(engine, search='Suppe')} == {first.public_id, second.public_id}
    assert store.get_recipe(engine, first.public_id).public_id == first.public_id
    assert store.list_cookbooks(engine) == ()
    assert snapshot(owner) == before


def test_full_sixty_four_line_and_step_boundary(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    data = payload(ingredients=[line(str(index)) for index in range(64)],
                   steps=[{'instruction': str(index), 'duration_minutes': None, 'image_sha256': None} for index in range(64)])
    recipe = store.create_recipe(engine, actor, data, expected_location_id=location)
    read = store.get_recipe(engine, recipe.public_id)
    assert len(read.payload['ingredients']) == len(read.payload['steps']) == 64
    for field in ('ingredients', 'steps'):
        invalid = mutable(read.payload)
        invalid[field].append(invalid[field][0])
        before = snapshot(owner)
        with pytest.raises(RecipeValidationError):
            store.update_recipe(engine, actor, target(read), invalid, expected_location_id=location)
        assert snapshot(owner) == before
