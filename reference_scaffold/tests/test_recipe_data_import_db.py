"""Import the reviewed linked dish drafts through Foundations and recipe batches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

WORKTREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE / 'tools'))
import build_recipe_draft_import as importer  # noqa: E402
import recipe_draft_apply as applyer  # noqa: E402

from cafeteria import master_data_store as masters  # noqa: E402
from cafeteria import recipe_import_store as import_store  # noqa: E402
from cafeteria import recipe_store as recipes  # noqa: E402
from test_master_data_db import (  # noqa: E402,F401
    app_engine, installed_pg16, make_actor, master, pg16, seeded_pg16, signed_in,
)

DRAFT_PATH = WORKTREE / 'demo' / 'linked_recipe_drafts.json'
IMPORT_PATH = WORKTREE / 'demo' / 'linked_recipe_drafts_import.json'
TARGET_STORAGE = {'Trockenlager', 'Kühlraum', 'Tiefkühler'}


def load_import() -> dict:
    draft = importer.load_draft(DRAFT_PATH)
    return importer.translate_draft(draft, draft_path=DRAFT_PATH)


def snapshot(owner):
    tables = (
        'storage_locations', 'foods', 'food_storage_locations', 'recipes', 'recipe_ingredients',
        'recipe_import_batches', 'audit_events', 'publication_revisions',
    )
    with owner.connect() as current:
        return {
            table: current.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all()
            for table in tables
        }


def storage_names(engine):
    return {
        item.name
        for item in masters.list_vocabulary(engine, 'storage_location', include_archived=True, limit=200)
    }


def audit_count(owner, action: str) -> int:
    with owner.connect() as current:
        return current.execute(
            text('SELECT count(*) FROM cafeteria.audit_events WHERE action=:action'),
            {'action': action},
        ).scalar_one()


def allergen_reviews(owner) -> int:
    with owner.connect() as current:
        return current.execute(
            text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE '%allergen%review%'")
        ).scalar_one()


def run_apply(engine, actor, document):
    with signed_in(engine, actor):
        return applyer.apply_import(document, engine, actor, dry_run=False)


def attach_local_credentials(owner, actor, username='recipe.importer'):
    with owner.begin() as current:
        current.execute(
            text('''INSERT INTO cafeteria.local_credentials(user_id,username,password_hash)
                    VALUES(:user_id,:username,:password_hash)'''),
            {
                'user_id': actor.user_id,
                'username': username,
                'password_hash': generate_password_hash(username),
            },
        )
        return current.execute(
            text('SELECT public_id,authz_version FROM cafeteria.users WHERE id=:user_id'),
            {'user_id': actor.user_id},
        ).one()


def user_count(owner) -> int:
    with owner.connect() as current:
        return current.execute(text('SELECT count(*) FROM cafeteria.users')).scalar_one()


def test_apply_cli_requires_explicit_actor(monkeypatch, capsys):
    monkeypatch.delenv('RECIPE_IMPORT_ALLOW_FIXTURE_ACTOR', raising=False)
    monkeypatch.setattr(sys, 'argv', ['build_recipe_draft_import.py', '--apply', '--output', str(IMPORT_PATH)])
    assert importer.main() == 2
    assert '--actor-user' in capsys.readouterr().err


def test_resolve_import_actor_by_username_and_public_id_without_inserting_user(master):  # noqa: F811
    owner, engine, _fixture_actor = master
    admin = make_actor(owner, 'Cafeteria.Admin')
    account = attach_local_credentials(owner, admin)
    before = user_count(owner)
    by_username = importer.resolve_import_actor(engine, 'recipe.importer')
    by_public_id = importer.resolve_import_actor(engine, str(account.public_id))
    assert by_username == by_public_id
    assert by_username.user_id == admin.user_id
    assert by_username.authz_version == account.authz_version
    assert user_count(owner) == before


def test_resolve_import_actor_rejects_unknown_user_without_mutation(master):  # noqa: F811
    owner, engine, _actor = master
    before = snapshot(owner)
    with pytest.raises(importer.ActorResolutionError, match='nicht gefunden'):
        importer.resolve_import_actor(engine, 'missing.importer')
    assert snapshot(owner) == before


def test_apply_cli_unknown_actor_exits_before_migrations(master, monkeypatch, capsys):  # noqa: F811
    owner, engine, _actor = master
    migrations: list[str] = []
    monkeypatch.setattr('sqlalchemy.create_engine', lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        'cafeteria.db.run_migrations',
        lambda *_args, **_kwargs: migrations.append('called'),
    )
    monkeypatch.setattr(
        sys,
        'argv',
        ['build_recipe_draft_import.py', '--apply', '--database-url', 'postgresql://unused',
         '--actor-user', 'missing.importer'],
    )
    before = snapshot(owner)
    assert importer.main() == 2
    assert 'nicht gefunden' in capsys.readouterr().err
    assert migrations == []
    assert snapshot(owner) == before


def test_resolve_import_actor_rejects_missing_import_capabilities(master):  # noqa: F811
    owner, engine, _actor = master
    editor = make_actor(owner, 'Cafeteria.Editor')
    attach_local_credentials(owner, editor, 'recipe.editor')
    before = snapshot(owner)
    with pytest.raises(importer.ActorResolutionError, match='Berechtigungen'):
        importer.resolve_import_actor(engine, 'recipe.editor')
    assert snapshot(owner) == before


def test_apply_cli_unauthorized_actor_exits_before_migrations(master, monkeypatch, capsys):  # noqa: F811
    owner, engine, _actor = master
    editor = make_actor(owner, 'Cafeteria.Editor')
    attach_local_credentials(owner, editor, 'recipe.editor')
    migrations: list[str] = []
    monkeypatch.setattr('sqlalchemy.create_engine', lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        'cafeteria.db.run_migrations',
        lambda *_args, **_kwargs: migrations.append('called'),
    )
    monkeypatch.setattr(
        sys,
        'argv',
        ['build_recipe_draft_import.py', '--apply', '--database-url', 'postgresql://unused',
         '--actor-user', 'recipe.editor'],
    )
    before = snapshot(owner)
    assert importer.main() == 2
    assert 'Berechtigungen' in capsys.readouterr().err
    assert migrations == []
    assert snapshot(owner) == before


def test_linked_draft_import_full_pipeline(master, monkeypatch):  # noqa: F811
    owner, engine, fixture_actor = master
    attach_local_credentials(owner, fixture_actor)
    actor = importer.resolve_import_actor(engine, 'recipe.importer')
    monkeypatch.setattr(
        applyer,
        'write_import',
        lambda *_args, **_kwargs: pytest.fail('apply_import wrote back without --write-back'),
    )
    before_users = user_count(owner)
    document = load_import()
    before_pub = snapshot(owner)['publication_revisions']
    before = snapshot(owner)
    summary = run_apply(engine, actor, document)
    after = snapshot(owner)
    assert summary['storage_locations'] == 3
    assert summary['foods'] == 100
    assert TARGET_STORAGE <= storage_names(engine)
    foods = masters.list_foods(engine, limit=200)
    assert len(foods) >= 100
    assert all(item.storage_locations for item in foods if item.name in {row['name'] for row in document['foods']})
    recipe_count = len(after['recipes']) - len(before['recipes'])
    assert recipe_count == 61
    imports = audit_count(owner, 'recipe.import')
    assert imports == 61
    loaded = document
    assert len(loaded['resolved']['food_keys']) == 100
    assert len(loaded['resolved']['recipe_keys']) == 61
    assert loaded['resolved']['batch_public_ids']['preparation']
    assert loaded['resolved']['batch_public_ids']['dish']
    titles = {item['title'] for item in document['dish_mappings']}
    imported_titles = {
        recipes.get_recipe(engine, recipe_id).payload['title']
        for recipe_id in loaded['resolved']['recipe_keys'].values()
    }
    assert titles <= imported_titles
    occurrences = sum(len(item['source_occurrences']) for item in document['dish_mappings'])
    assert occurrences == 76
    for recipe in document['recipes']:
        recipe_id = loaded['resolved']['recipe_keys'][recipe['key']]
        row = recipes.get_recipe(engine, recipe_id)
        expected_version = 2 if recipe['batch_group'] == 'preparation' else 1
        assert row.row_version == expected_version
        assert row.payload['source']['kind'] == 'ai_assisted'
        assert row.payload['source']['note']
        assert 'unreviewed' not in row.payload
    for batch_id in loaded['resolved']['batch_public_ids'].values():
        batch = import_store.get_batch(engine, batch_id)
        assert batch.adapter_kind == 'ai_assisted'
        assert set(batch.annotations) >= {'unreviewed', 'proposed_not_measured', 'allergen_not_checked'}
    pinned = [item for item in document['foods'] if item.get('preparation_recipe_key')]
    assert len(pinned) == 29
    for item in pinned:
        food = masters.get_food(engine, loaded['resolved']['food_keys'][item['key']])
        assert food.prepared_recipe is not None
        assert food.allergen_review_status == 'not_checked'
    assert snapshot(owner)['publication_revisions'] == before_pub
    assert allergen_reviews(owner) == 0
    assert user_count(owner) == before_users


def test_linked_draft_import_replay_is_idempotent(master):  # noqa: F811
    owner, engine, fixture_actor = master
    attach_local_credentials(owner, fixture_actor)
    actor = importer.resolve_import_actor(engine, 'recipe.importer')
    document = load_import()
    run_apply(engine, actor, document)
    before = snapshot(owner)
    again = run_apply(engine, actor, load_import())
    assert snapshot(owner) == before
    assert all(item['status'] == 'skipped' for item in again['batches'])


def test_linked_draft_import_invalid_row_rolls_back_batch(master):  # noqa: F811
    from cafeteria.master_data_types import ObjectExpectation
    from cafeteria.recipe_types import RecipeValidationError

    owner, engine, actor = master
    document = load_import()
    prep = [item for item in document['recipes'] if item['batch_group'] == 'preparation'][:1]
    isolated = json.loads(json.dumps(document))
    isolated['resolved'] = {'storage_keys': {}, 'food_keys': {}, 'recipe_keys': {}, 'batch_public_ids': {}}
    with signed_in(engine, actor):
        applyer.ensure_storage(engine, actor, isolated)
        food_ids = applyer.ensure_foods(engine, actor, isolated, isolated['resolved']['storage_keys'])
        location = recipes.get_location(engine)
        rows = []
        for index, recipe in enumerate(prep, start=1):
            payload = applyer.resolve_payload(
                recipe['recipe_payload'], recipe['ingredient_food_keys'], food_ids,
            )
            rows.append({
                'row_number': index,
                'source_line': None,
                'original_payload': payload,
                'parse_errors': [],
                'candidate_payload': payload,
                'duplicate_decision': 'undecided',
                'target_recipe_public_id': None,
                'target_row_version': None,
            })
        payload = applyer.batch_payload('preparation', rows, isolated['meta'])
        created = import_store.create_batch(engine, actor, payload, expected_location_id=location)
        batch = import_store.get_batch(engine, created.public_id)
        mapped = applyer.mapped_rows(prep, food_ids)
        mapped[0]['candidate_payload']['ingredients'][-1]['food_public_id'] = None
        import_store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'action': 'save', 'annotations': list(isolated['meta']['annotations']), 'rows': mapped},
            expected_location_id=location,
        )
        batch = import_store.get_batch(engine, created.public_id)
        import_store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'action': 'acknowledge'}, expected_location_id=location,
        )
        batch = import_store.get_batch(engine, created.public_id)
        before = snapshot(owner)
        with pytest.raises(RecipeValidationError, match='unvollständig'):
            import_store.commit_batch(
                engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
                {'candidate_hash_sha256': batch.candidate_hash_sha256},
                expected_location_id=location,
            )
        assert snapshot(owner) == before
        assert import_store.get_batch(engine, batch.public_id).status == 'draft'


def test_translate_draft_rejects_unknown_unit_codes():
    draft = importer.load_draft(DRAFT_PATH)
    food_key = draft['foods'][0]['key']
    bad_food = json.loads(json.dumps(draft))
    bad_food['foods'][0]['base_unit_code'] = 'NOPE'
    with pytest.raises(ValueError, match='NOPE') as food_error:
        importer.translate_draft(bad_food, draft_path=DRAFT_PATH)
    assert f'foods[{food_key}].base_unit_code' in str(food_error.value)
    assert str(DRAFT_PATH) in str(food_error.value)

    recipe_key = draft['recipes'][0]['key']
    bad_ingredient = json.loads(json.dumps(draft))
    bad_ingredient['recipes'][0]['ingredients'][0]['unit_code'] = 'XYZ'
    with pytest.raises(ValueError, match='XYZ') as ingredient_error:
        importer.translate_draft(bad_ingredient, draft_path=DRAFT_PATH)
    assert f'recipes[{recipe_key}].ingredients[0].unit_code' in str(ingredient_error.value)
    assert str(DRAFT_PATH) in str(ingredient_error.value)


def test_linked_draft_import_conflict_aborts_before_pins(master, monkeypatch):  # noqa: F811
    _owner, engine, actor = master
    document = load_import()
    batch_id = '11111111-1111-1111-1111-111111111111'
    pin_calls: list[str] = []

    def replay_conflict(*args, **_kwargs):
        return {
            'status': 'conflict',
            'group': args[3],
            'public_id': batch_id,
            'message': 'Importstapel existiert bereits.',
        }

    def refuse_pin(*args, **kwargs):
        pin_calls.append('called')
        raise AssertionError('pin_prepared_foods must not run after batch conflict')

    monkeypatch.setattr(applyer, 'ensure_storage', lambda *args, **kwargs: {'k': 'storage'})
    monkeypatch.setattr(applyer, 'ensure_foods', lambda *args, **kwargs: {'f': 'food'})
    monkeypatch.setattr(applyer, 'commit_group', replay_conflict)
    monkeypatch.setattr(applyer, 'pin_prepared_foods', refuse_pin)
    with pytest.raises(applyer.BatchImportError, match=batch_id) as caught:
        run_apply(engine, actor, document)
    assert pin_calls == []
    assert caught.value.summary['prepared_pins'] == []
    failed = applyer.failed_batches(caught.value.summary)
    assert failed == [caught.value.summary['batches'][0]]
    assert failed[0]['status'] == 'conflict'
    assert failed[0]['group'] == 'preparation'
    assert failed[0]['public_id'] == batch_id
    assert 'status=conflict' in str(caught.value)
    assert len(caught.value.summary['batches']) == 1
