"""Real PostgreSQL proofs for the persisted draft-to-template import boundary."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

WORKTREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE / 'tools'))
import import_dish_templates as importer  # noqa: E402

from cafeteria import dish_template_store as templates  # noqa: E402
from cafeteria import recipe_import_store as batches  # noqa: E402
from cafeteria import recipe_store as recipes  # noqa: E402
from cafeteria.master_data_types import ObjectExpectation  # noqa: E402
from test_master_data_db import (  # noqa: E402,F401
    app_engine, installed_pg16, make_actor, master, pg16, seeded_pg16, signed_in,
)
from test_recipe_data_import_db import (  # noqa: E402
    applyer, attach_local_credentials, load_import, run_apply, snapshot,
)
from test_dish_template_routes import (  # noqa: E402
    foreign_recipe, snapshot as template_snapshot,
)

USERNAME = 'dish.template.importer'


def domain_snapshot(owner):
    with owner.connect() as connection:
        domains = connection.execute(text('''SELECT
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM cafeteria.menu_items t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM cafeteria.menu_components t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM cafeteria.food_allergens t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM cafeteria.food_labels t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM cafeteria.food_tags t)
        ''')).one()
    return snapshot(owner), template_snapshot(owner), tuple(domains)


@pytest.fixture
def imported(master):  # noqa: F811
    owner, engine, actor = master
    attach_local_credentials(owner, actor, USERNAME)
    document = load_import()
    run_apply(engine, actor, document)
    return owner, engine, actor, document


def run(engine, document, *, dry_run=False, username=USERNAME):
    return importer.import_templates(
        document, engine, actor_user=username, profile_scope='common', dry_run=dry_run,
    )


def dish_payload(document, index=-1):
    mapping = document['dish_mappings'][index]
    return {
        'title': mapping['title'], 'description': importer.DESCRIPTION, 'profile_scope': 'common',
        'menu_type_code': None, 'recipe_public_id': document['resolved']['recipe_keys'][mapping['recipe_key']],
    }


def test_dry_run_apply_and_replay_exactly_32_native_templates(imported):
    owner, engine, actor, document = imported
    before = domain_snapshot(owner)
    # Persisted batches, never caller-supplied UUIDs, establish every binding.
    untrusted = deepcopy(document)
    untrusted['resolved'] = {'recipe_keys': {'ignored': str(uuid4())}, 'batch_public_ids': {'dish': str(uuid4())}}
    dry = run(engine, untrusted, dry_run=True)
    assert (dry['planned'], dry['created'], dry['skipped']) == (32, 0, 0)
    assert domain_snapshot(owner) == before
    result = run(engine, untrusted)
    assert (result['planned'], result['created'], result['skipped']) == (32, 32, 0)
    with signed_in(engine, actor):
        native = templates.list_templates(engine)
        assert len(native) == 32
        for row in native:
            mapping = next(item for item in document['dish_mappings'] if item['title'] == row.title)
            assert row.recipe_public_id == document['resolved']['recipe_keys'][mapping['recipe_key']]
            assert row.active and row.profile_scope == 'common' and row.menu_type_code is None
            assert row.description == importer.DESCRIPTION
    after = domain_snapshot(owner)
    assert len(after[1]['audit_events']) == len(before[1]['audit_events']) + 32
    assert {k: v for k, v in after[0].items() if k != 'audit_events'} == {
        k: v for k, v in before[0].items() if k != 'audit_events'
    }
    assert after[2] == before[2]
    replay = run(engine, untrusted)
    assert (replay['planned'], replay['created'], replay['skipped']) == (0, 0, 32)
    assert domain_snapshot(owner) == after


@pytest.mark.parametrize('damage', ['missing_batch', 'wrong_reference', 'missing_mapping', 'duplicate_mapping'])
def test_document_conflicts_write_nothing(imported, damage):
    owner, engine, _, document = imported
    if damage == 'missing_batch':
        document['meta']['source_draft_sha256'] = '0' * 64
    elif damage == 'wrong_reference':
        dishes = [row for row in document['recipes'] if row['batch_group'] == 'dish']
        index = document['recipes'].index(dishes[0])
        document['recipes'][index], document['recipes'][index + 1] = dishes[1], dishes[0]
    elif damage == 'missing_mapping':
        document['dish_mappings'].pop()
    else:
        document['dish_mappings'].append(document['dish_mappings'][0])
    before = domain_snapshot(owner)
    with pytest.raises(importer.TemplateImportError):
        run(engine, document)
    assert domain_snapshot(owner) == before


def test_duplicate_imported_batch_is_ambiguous(imported):
    owner, engine, actor, document = imported
    group = [row for row in document['recipes'] if row['batch_group'] == 'dish']
    rows = applyer.mapped_rows(group, document['resolved']['food_keys'])
    rows = [dict(row, original_payload=row['candidate_payload'], parse_errors=[], source_line=None) for row in rows]
    with signed_in(engine, actor):
        location = recipes.get_location(engine)
        created = batches.create_batch(
            engine, actor, applyer.batch_payload('dish', rows, document['meta']), expected_location_id=location,
        )
        loaded = batches.get_batch(engine, created.public_id)
        batches.update_batch(
            engine, actor, ObjectExpectation(loaded.public_id, loaded.row_version),
            {'action': 'acknowledge'}, expected_location_id=location,
        )
        loaded = batches.get_batch(engine, created.public_id)
        batches.commit_batch(
            engine, actor, ObjectExpectation(loaded.public_id, loaded.row_version),
            {'candidate_hash_sha256': loaded.candidate_hash_sha256}, expected_location_id=location,
        )
    before = domain_snapshot(owner)
    with pytest.raises(importer.TemplateImportError, match='mehrdeutig'):
        run(engine, document)
    assert domain_snapshot(owner) == before


@pytest.mark.parametrize('damage', ['archived', 'description', 'scope', 'duplicate', 'title'])
def test_existing_template_conflicts_preflight_all_rows(imported, damage):
    owner, engine, actor, document = imported
    with signed_in(engine, actor):
        payload = dish_payload(document)
        if damage == 'description':
            payload['description'] = 'Manuell geprüft'
        if damage == 'scope':
            payload['profile_scope'] = 'patient'
        if damage == 'title':
            payload['title'] = 'Geänderter Titel'
        location = recipes.get_location(engine)
        created = templates.create_template(engine, actor, payload, expected_location_id=location)
        if damage == 'duplicate':
            templates.create_template(engine, actor, payload, expected_location_id=location)
        if damage == 'archived':
            row = templates.get_template(engine, created['public_id'])
            templates.set_template_active(
                engine, actor, row.public_id, row.updated_at, active=False, expected_location_id=location,
            )
    before = domain_snapshot(owner)
    with pytest.raises(importer.TemplateImportError, match='widerspricht'):
        run(engine, document)
    assert domain_snapshot(owner) == before


@pytest.mark.parametrize('damage', ['archived', 'foreign', 'wrong_uuid'])
def test_recipe_targets_fail_closed_before_any_template(imported, damage):
    owner, engine, actor, document = imported
    with signed_in(engine, actor):
        if damage == 'archived':
            row = recipes.get_recipe(engine, dish_payload(document)['recipe_public_id'])
            recipes.set_recipe_active(
                engine, actor, ObjectExpectation(row.public_id, row.row_version), active=False,
                expected_location_id=recipes.get_location(engine),
            )
        else:
            target = foreign_recipe(owner, actor) if damage == 'foreign' else str(uuid4())
            batch_id = document['resolved']['batch_public_ids']['dish']
            # Synthetic corruption only, using the test owner; production app cannot mutate this history.
            with owner.begin() as connection:
                connection.execute(text('ALTER TABLE cafeteria.recipe_import_batches DISABLE TRIGGER recipe_import_batches_protect'))
                connection.execute(text('''UPDATE cafeteria.recipe_import_batches
                    SET imported_result=jsonb_set(imported_result,'{31,recipe_public_id}',to_jsonb(CAST(:target AS text)))
                    WHERE public_id=CAST(:batch AS uuid)'''), {'target': target, 'batch': batch_id})
                connection.execute(text('ALTER TABLE cafeteria.recipe_import_batches ENABLE TRIGGER recipe_import_batches_protect'))
    before = domain_snapshot(owner)
    with pytest.raises(ValueError):
        run(engine, document)
    assert domain_snapshot(owner) == before


@pytest.mark.parametrize('dry_run', [True, False])
def test_unauthorized_actor_has_no_read_plan_or_writes(imported, dry_run):
    owner, engine, _, document = imported
    viewer = make_actor(owner, 'Cafeteria.Editor')
    attach_local_credentials(owner, viewer, 'dish.viewer')
    before = domain_snapshot(owner)
    with pytest.raises(ValueError, match='Berechtigungen'):
        run(engine, document, username='dish.viewer', dry_run=dry_run)
    assert domain_snapshot(owner) == before


def test_cli_read_only_input_and_explicit_common(imported, monkeypatch, tmp_path, capsys):
    from cafeteria import config

    owner, engine, _, document = imported
    path = tmp_path / 'read-only-import.json'
    data = json.dumps(document, ensure_ascii=False)
    path.write_text(data, encoding='utf-8')
    path.chmod(0o444)
    monkeypatch.setattr(config, 'Config', lambda: SimpleNamespace(DATABASE_URL=engine.url))
    args = ['--input', str(path), '--actor-user', USERNAME, '--profile-scope', 'common']
    before = domain_snapshot(owner)
    assert importer.main([*args, '--dry-run']) == 0
    assert json.loads(capsys.readouterr().out)['planned'] == 32
    assert domain_snapshot(owner) == before
    assert importer.main([*args, '--apply']) == 0
    assert json.loads(capsys.readouterr().out)['created'] == 32
    after = domain_snapshot(owner)
    assert importer.main([*args, '--apply']) == 0
    assert json.loads(capsys.readouterr().out)['skipped'] == 32
    assert domain_snapshot(owner) == after and path.read_text(encoding='utf-8') == data
    with pytest.raises(SystemExit):
        importer.main(['--actor-user', USERNAME, '--dry-run'])
    assert domain_snapshot(owner) == after


def test_concurrent_import_lock_fails_closed(imported):
    owner, engine, _, document = imported
    before = domain_snapshot(owner)
    with engine.begin() as guard:
        guard.execute(text('SELECT pg_advisory_xact_lock(190912, 29)'))
        with pytest.raises(importer.TemplateImportError, match='läuft bereits'):
            run(engine, document)
    assert domain_snapshot(owner) == before
