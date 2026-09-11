"""Atomic confirmed recipe-import commits; one TX, no recipe-store loop."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from werkzeug.exceptions import Forbidden

from cafeteria import master_data_store as masters
from cafeteria import recipe_import_store as store
from cafeteria import recipe_store as recipes
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeConflictError, RecipeValidationError
from test_master_data_db import (  # noqa: F401
    STORAGE_PUBLIC_ID, app_engine, installed_pg16, make_actor, master, pg16, seeded_pg16,
    signed_in,
)
from test_recipe_import import json_bytes, parse, recipe
from test_recipe_store_db import payload as recipe_payload


def snapshot(owner):
    tables = (
        'recipe_import_batches', 'recipe_import_candidates', 'recipes',
        'recipe_ingredients', 'audit_events', 'publication_revisions',
        'publication_lifecycle_events',
    )
    with owner.connect() as current:
        return {
            table: current.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all()
            for table in tables
        }


def audits(owner, action: str) -> int:
    with owner.connect() as current:
        return current.execute(
            text('SELECT count(*) FROM cafeteria.audit_events WHERE action=:action'),
            {'action': action},
        ).scalar_one()


def food_for(engine, actor, name: str):
    return masters.create_food(engine, actor, {
        'name': name, 'base_unit_code': 'KG',
        'storage_location_public_ids': [STORAGE_PUBLIC_ID],
    })


def mapped_row(candidate, *, decision='create_new', food_id=None, target=None, version=None):
    edited = dict(store.thaw(candidate.candidate_payload))
    ingredients = [dict(store.thaw(item)) for item in edited.get('ingredients') or []]
    if ingredients and food_id is not None:
        ingredients[0]['food_public_id'] = food_id
    edited['ingredients'] = ingredients
    return {
        'row_number': candidate.row_number,
        'candidate_payload': edited,
        'duplicate_decision': decision,
        'target_recipe_public_id': target,
        'target_row_version': version,
    }


def prepare(engine, actor, *, titles=('Kartoffelsuppe',), decisions=None, foods=None,
            acknowledge=True, extra_rows=None):
    location = recipes.get_location(engine)
    titles = list(titles)
    decisions = list(decisions or ['create_new'] * len(titles))
    preview = parse(json_bytes(*[recipe(title) for title in titles]))
    payload = store.payload_from_preview(preview, annotations=('unreviewed',))
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    rows = extra_rows
    if rows is None:
        rows = []
        for candidate, decision, title in zip(batch.candidates, decisions, titles, strict=True):
            food_id = None
            if decision == 'create_new':
                item = foods.pop(0) if foods else food_for(engine, actor, f'Zutat {title}')
                food_id = item.public_id
            rows.append(mapped_row(candidate, decision=decision, food_id=food_id))
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': list(batch.annotations), 'rows': rows},
        expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    if acknowledge:
        store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'action': 'acknowledge'}, expected_location_id=location,
        )
        batch = store.get_batch(engine, created.public_id)
    return batch, location


def commit(engine, actor, batch, location):
    return store.commit_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'candidate_hash_sha256': batch.candidate_hash_sha256},
        expected_location_id=location,
    )


def test_publisher_and_admin_commit_create_new_file_source(master):  # noqa: F811
    owner, engine, actor = master
    before_pub = snapshot(owner)['publication_revisions']
    batch, location = prepare(engine, actor)
    creates = audits(owner, 'recipe.create')
    imports = audits(owner, 'recipe.import')
    result = commit(engine, actor, batch, location)
    loaded = store.get_batch(engine, result.public_id)
    assert loaded.status == 'imported'
    assert result.row_version == batch.row_version + 1
    assert len(loaded.imported_result) == 1
    recipe_id = loaded.imported_result[0]['recipe_public_id']
    created = recipes.get_recipe(engine, recipe_id)
    assert created.row_version == 1
    assert created.payload['source']['kind'] == 'file_import'
    assert created.payload['source']['reference'] == loaded.candidates[0].origin_ref
    assert loaded.source_sha256 in (created.payload['source']['note'] or '')
    assert created.payload['ingredients'][0]['source_reference'] == loaded.candidates[0].origin_ref
    assert audits(owner, 'recipe.create') == creates + 1
    assert audits(owner, 'recipe.import') == imports + 1
    with owner.connect() as current:
        commits = current.execute(text(
            "SELECT count(*) FROM cafeteria.audit_events "
            "WHERE action='recipe.import_batch' AND details->>'action'='commit'"
        )).scalar_one()
        reviews = current.execute(text(
            "SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE '%allergen%review%'"
        )).scalar_one()
    assert commits == 1
    assert reviews == 0
    assert snapshot(owner)['publication_revisions'] == before_pub
    admin = make_actor(owner, 'Cafeteria.Admin')
    with signed_in(engine, admin):
        second, loc = prepare(engine, admin, titles=('Adminsuppe',))
        done = commit(engine, admin, second, loc)
    assert store.get_batch(engine, done.public_id).status == 'imported'


def test_editor_without_recipe_import_is_denied(master):  # noqa: F811
    owner, engine, actor = master
    batch, location = prepare(engine, actor)
    before = snapshot(owner)
    editor = make_actor(owner, 'Cafeteria.Editor')
    with signed_in(engine, editor):
        with pytest.raises(Forbidden):
            commit(engine, editor, batch, location)
    with pytest.raises(DBAPIError) as error:
        with owner.begin() as current:
            current.execute(text(
                'SELECT cafeteria.commit_recipe_import_batch_v29('
                ':actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),'
                'CAST(:payload AS jsonb))'
            ), {
                'actor': editor.user_id, 'authz': editor.authz_version, 'location': location,
                'target': batch.public_id, 'version': batch.row_version,
                'payload': store._dump({'candidate_hash_sha256': batch.candidate_hash_sha256}),
            })
    assert error.value.orig.sqlstate == 'P1902'
    assert snapshot(owner) == before


def test_last_row_error_rolls_back_recipes_versions_and_audits(master):  # noqa: F811
    owner, engine, actor = master
    location = recipes.get_location(engine)
    titles = ('Erste', 'Zweite', 'Dritte')
    preview = parse(json_bytes(*[recipe(title) for title in titles]))
    payload = store.payload_from_preview(preview, annotations=('unreviewed',))
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    first = food_for(engine, actor, 'Zutat 1')
    second = food_for(engine, actor, 'Zutat 2')
    rows = [
        mapped_row(batch.candidates[0], food_id=first.public_id),
        mapped_row(batch.candidates[1], food_id=second.public_id),
        mapped_row(batch.candidates[2], food_id=None),
    ]
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': ['unreviewed'], 'rows': rows},
        expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    before = snapshot(owner)
    with pytest.raises(RecipeValidationError, match='unvollständig'):
        commit(engine, actor, batch, location)
    assert snapshot(owner) == before
    assert store.get_batch(engine, batch.public_id).status == 'draft'


def test_replay_is_conflict_and_skip_checks_exact_target(master):  # noqa: F811
    owner, engine, actor = master
    location = recipes.get_location(engine)
    existing = recipes.create_recipe(engine, actor, recipe_payload(), expected_location_id=location)
    origin = recipes.get_recipe(engine, existing.public_id).payload['source']
    titles = ('Neu', 'Vorhanden')
    preview = parse(json_bytes(*[recipe(title) for title in titles]))
    payload = store.payload_from_preview(preview, annotations=('unreviewed',))
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    fresh = food_for(engine, actor, 'Neue Zutat')
    rows = [
        mapped_row(batch.candidates[0], food_id=fresh.public_id),
        mapped_row(
            batch.candidates[1], decision='skip_existing',
            target=existing.public_id, version=existing.row_version,
        ),
    ]
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': ['unreviewed'], 'rows': rows},
        expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    first = commit(engine, actor, batch, location)
    loaded = store.get_batch(engine, first.public_id)
    assert loaded.status == 'imported'
    skipped = recipes.get_recipe(engine, existing.public_id)
    assert skipped.row_version == existing.row_version
    assert skipped.payload['source'] == origin
    after = snapshot(owner)
    with pytest.raises(RecipeConflictError, match='nicht mehr bearbeitbar'):
        store.commit_batch(
            engine, actor, ObjectExpectation(loaded.public_id, loaded.row_version),
            {'candidate_hash_sha256': loaded.candidate_hash_sha256},
            expected_location_id=location,
        )
    assert snapshot(owner) == after


def _skip_batch(engine, actor, location, target, version):
    preview = parse(json_bytes(recipe('Skip-Ziel')))
    payload = store.payload_from_preview(preview, annotations=('unreviewed',))
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': ['unreviewed'], 'rows': [mapped_row(
            batch.candidates[0], decision='skip_existing', target=target, version=version,
        )]},
        expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    return store.get_batch(engine, created.public_id)


def test_skip_stale_archived_and_foreign_write_nothing(master):  # noqa: F811
    owner, engine, actor = master
    location = recipes.get_location(engine)
    stale = recipes.create_recipe(
        engine, actor, recipe_payload(title='Stale'), expected_location_id=location,
    )
    archived = recipes.create_recipe(
        engine, actor, recipe_payload(title='Archiv'), expected_location_id=location,
    )
    missing = recipes.create_recipe(
        engine, actor, recipe_payload(title='Fremd'), expected_location_id=location,
    )
    recipes.update_recipe(
        engine, actor, ObjectExpectation(stale.public_id, stale.row_version),
        recipe_payload(title='Geändert'), expected_location_id=location,
    )
    recipes.set_recipe_active(
        engine, actor, ObjectExpectation(archived.public_id, archived.row_version),
        active=False, expected_location_id=location,
    )
    cases = [
        _skip_batch(engine, actor, location, stale.public_id, stale.row_version),
        _skip_batch(engine, actor, location, archived.public_id, archived.row_version),
        _skip_batch(engine, actor, location, missing.public_id, missing.row_version),
    ]
    with owner.begin() as current:
        current.execute(text(
            'UPDATE cafeteria.recipe_import_candidates SET target_recipe_public_id='
            "'00000000-0000-0000-0000-000000000099' "
            'WHERE batch_id=(SELECT id FROM cafeteria.recipe_import_batches '
            'WHERE public_id=CAST(:id AS uuid))'
        ), {'id': cases[2].public_id})
    cases[2] = store.get_batch(engine, cases[2].public_id)
    for batch in cases:
        before = snapshot(owner)
        with pytest.raises(RecipeConflictError, match='geprüfte Ziel'):
            commit(engine, actor, batch, location)
        assert snapshot(owner) == before
        assert store.get_batch(engine, batch.public_id).status == 'draft'


def test_unresolved_stays_draft_and_url_ai_keep_origin(master):  # noqa: F811
    owner, engine, actor = master
    location = recipes.get_location(engine)
    preview = parse(json_bytes(recipe('Unvollständig')))
    payload = store.payload_from_preview(preview, annotations=('unreviewed',))
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': ['unreviewed'], 'rows': [
            mapped_row(batch.candidates[0], food_id=None),
        ]},
        expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    before = snapshot(owner)
    with pytest.raises(RecipeValidationError, match='unvollständig'):
        commit(engine, actor, batch, location)
    assert snapshot(owner) == before
    assert store.get_batch(engine, batch.public_id).status == 'draft'

    url_preview = parse(json_bytes(recipe('URL-Suppe')))
    url_payload = store.payload_from_preview(url_preview, adapter_kind='url')
    url_payload['source_url'] = 'https://example.invalid/rezept'
    url_payload['source_filename'] = None
    url_payload['source_sha256'] = None
    url_payload['content_type'] = None
    original = dict(url_payload['rows'][0]['original_payload'])
    original['source'] = {
        'kind': 'url', 'reference': 'https://example.invalid/rezept',
        'url': 'https://example.invalid/rezept', 'note': None,
        'fetched_at': url_preview.fetched_at,
    }
    for ingredient in original['ingredients']:
        ingredient['source_kind'] = 'url'
        ingredient['source_reference'] = 'https://example.invalid/rezept'
    url_payload['rows'][0]['original_payload'] = original
    url_created = store.create_batch(engine, actor, url_payload, expected_location_id=location)
    url_batch = store.get_batch(engine, url_created.public_id)
    url_food = food_for(engine, actor, 'URL-Zutat')
    store.update_batch(
        engine, actor, ObjectExpectation(url_batch.public_id, url_batch.row_version),
        {'action': 'save', 'annotations': ['unreviewed'], 'rows': [
            mapped_row(url_batch.candidates[0], food_id=url_food.public_id),
        ]},
        expected_location_id=location,
    )
    url_batch = store.get_batch(engine, url_created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(url_batch.public_id, url_batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    url_batch = store.get_batch(engine, url_created.public_id)
    commit(engine, actor, url_batch, location)
    url_loaded = store.get_batch(engine, url_batch.public_id)
    url_recipe = recipes.get_recipe(engine, url_loaded.imported_result[0]['recipe_public_id'])
    assert url_recipe.payload['source']['kind'] == 'url'
    assert url_recipe.payload['source']['url'] == 'https://example.invalid/rezept'
    assert url_recipe.payload['source']['reference'] == 'https://example.invalid/rezept'

    ai_preview = parse(json_bytes(recipe('AI-Suppe')))
    ai_payload = store.payload_from_preview(ai_preview, adapter_kind='ai_assisted')
    ai_payload['source_note'] = 'Modellauszug geprüft'
    ai_payload['source_filename'] = None
    ai_payload['source_sha256'] = None
    ai_payload['content_type'] = None
    ai_original = dict(ai_payload['rows'][0]['original_payload'])
    ai_original['source'] = {
        'kind': 'ai_assisted', 'reference': 'model:test',
        'url': None, 'note': 'Modellauszug geprüft',
        'fetched_at': ai_preview.fetched_at,
    }
    for ingredient in ai_original['ingredients']:
        ingredient['source_kind'] = 'ai_assisted'
        ingredient['source_reference'] = 'model:test'
    ai_payload['rows'][0]['original_payload'] = ai_original
    ai_created = store.create_batch(engine, actor, ai_payload, expected_location_id=location)
    ai_batch = store.get_batch(engine, ai_created.public_id)
    ai_food = food_for(engine, actor, 'AI-Zutat')
    store.update_batch(
        engine, actor, ObjectExpectation(ai_batch.public_id, ai_batch.row_version),
        {'action': 'save', 'annotations': ['unreviewed'], 'rows': [
            mapped_row(ai_batch.candidates[0], food_id=ai_food.public_id),
        ]},
        expected_location_id=location,
    )
    ai_batch = store.get_batch(engine, ai_created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(ai_batch.public_id, ai_batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    ai_batch = store.get_batch(engine, ai_created.public_id)
    commit(engine, actor, ai_batch, location)
    ai_loaded = store.get_batch(engine, ai_batch.public_id)
    ai_recipe = recipes.get_recipe(engine, ai_loaded.imported_result[0]['recipe_public_id'])
    assert ai_recipe.payload['source']['kind'] == 'ai_assisted'
    assert ai_recipe.payload['source']['note'] == 'Modellauszug geprüft'
    assert ai_recipe.payload['source']['reference'] == 'model:test'
