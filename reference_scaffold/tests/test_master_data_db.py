"""Real PostgreSQL contracts for the complete M-A release unit."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import subprocess
import sys

import pytest
from flask import Flask, session
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from cafeteria import master_data_store as store
from cafeteria.auth.local_users import ActorExpectation
from cafeteria.master_data_types import MasterDataConflictError, MasterDataValidationError, ObjectExpectation
from test_component_metadata_master_lock_db import (  # noqa: F401
    pg16, SCHEMA, PERMISSIONS, seeded_pg16, installed_pg16, app_engine,
)
from test_operations_settings_db import _actor_id, _v19_week, _v19_snapshot, _INSERT_REVISION_SQL


def test_ma_sql_installs_on_frozen_schema20(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 20:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    actor = _actor_id(pg16)
    week = _v19_week(pg16, actor)
    snapshot = _v19_snapshot(pg16, 'CAF-2026-KW36-R1')
    with pg16.begin() as c:
        c.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:id"), {'id': week})
        c.execute(text(_INSERT_REVISION_SQL), {'week_id': week, 'revision_number': 1,
            'revision_code': snapshot['revision_id'], 'snapshot': json.dumps(snapshot), 'actor': actor})
    preserved = ('users', 'user_role_cache', 'offer_profiles', 'menu_weeks', 'menu_services',
                 'menu_items', 'menu_item_prices', 'publication_revisions', 'audit_events')
    with pg16.connect() as c:
        before = {table: c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all()
                  for table in preserved}
    assert len(before['menu_services']) == 5 and len(before['menu_items']) == 10
    assert len(before['publication_revisions']) == 1 and before['users']
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        for table in preserved:
            assert c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all() == before[table]
        assert c.execute(text('SELECT count(*) FROM cafeteria.measurement_units')).scalar_one() == 9
        migrated = structure(c)
    with pg16.begin() as c:
        c.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        assert structure(c) == migrated


def test_full_live_schema_validator_checks_upgrade_and_fresh_catalog(pg16):  # noqa: F811
    result = subprocess.run([sys.executable, '-B', str(SCHEMA.parent / 'validate_schema.py'), '--live'],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout
    status = json.loads(result.stdout)
    assert status['live_postgresql_executed'] is True
    assert status['schema_version'] == 26 and status['tables'] == 52


def structure(c):
    return c.execute(text("""SELECT p.proname,pg_get_function_identity_arguments(p.oid),p.prosrc,p.prosecdef,p.proconfig,
        has_function_privilege('cafeteria_app',p.oid,'EXECUTE'),has_function_privilege('public',p.oid,'EXECUTE')
        FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace
        AND (p.proname LIKE 'master_%' OR p.proname LIKE '%_v21' OR p.proname LIKE 'protect_food%')
        ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)""")).all()


def make_actor(owner, role='Cafeteria.Publisher'):
    with owner.begin() as c:
        user = c.execute(text("INSERT INTO cafeteria.users(auth_provider,display_name) VALUES('local','Master fixture') RETURNING id")).scalar_one()
        c.execute(text("INSERT INTO cafeteria.user_role_cache(user_id,role_code,source) VALUES(:id,:role,'local')"),
                  {'id': user, 'role': role})
        version = c.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user}).scalar_one()
    return ActorExpectation(user, version)


@contextmanager
def signed_in(engine, actor):
    app = Flask(__name__)
    app.secret_key = 'isolated-master-data-fixture'
    app.extensions['cafeteria_db'] = engine
    with app.test_request_context():
        session['user'] = {'id': actor.user_id}
        session['authz_version'] = actor.authz_version
        yield


@pytest.fixture
def master(seeded_pg16, app_engine):  # noqa: F811
    actor = make_actor(seeded_pg16)
    with signed_in(app_engine, actor):
        yield seeded_pg16, app_engine, actor


def target(row):
    return ObjectExpectation(row.public_id, row.row_version)


def payload(name='Karotte'):
    return {'name': name, 'base_unit_code': 'G', 'note': ''}


def audit_count(owner):
    with owner.connect() as c:
        return c.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE 'masterdata.%'")).scalar_one()


def test_full_food_vocabulary_metadata_storage_and_proposal_roundtrip(master):
    owner, engine, actor = master
    category = store.create_vocabulary(engine, 'food_category', actor, code='VEG', name='Gemüse', sort_order=2)
    tag = store.create_vocabulary(engine, 'tag', actor, code='LOCAL', name='Regional')
    storage = store.create_vocabulary(engine, 'storage_location', actor, code='COOL', name='Kühlraum')
    data = {**payload(), 'category_public_id': category.public_id}
    food = store.create_food(engine, actor, data)
    initial = audit_count(owner)
    same = store.update_food(engine, actor, target(food), {**data, 'name': '  Karotte  '})
    assert same == food and audit_count(owner) == initial
    food = store.replace_food_tags(engine, actor, target(food), [tag.public_id])
    food = store.replace_food_metadata(engine, actor, target(food), allergens=[{'code': 'MILK', 'presence': 'may_contain'}], labels=['VEGETARIAN'])
    food = store.set_food_allergen_review(engine, actor, target(food), checked=True)
    review_audits = audit_count(owner)
    with pytest.raises(MasterDataConflictError):
        store.set_food_allergen_review(engine, actor, target(food), checked=True)
    assert audit_count(owner) == review_audits
    food = store.replace_food_storage_locations(engine, actor, target(food), [storage.public_id])
    read = store.get_food(engine, food.public_id)
    assert read.tags[0].public_id == tag.public_id and read.storage_locations[0].public_id == storage.public_id
    assert read.allergens == (('MILK', 'may_contain'),) and read.labels == ('VEGETARIAN',)
    assert read.allergen_review_status == 'checked'
    with pytest.raises(MasterDataConflictError, match='1 Zutaten'):
        store.set_vocabulary_active(engine, 'storage_location', actor, target(storage), active=False)
    proposal = store.create_proposal(engine, actor, source='off', source_reference='Fixture-1', fetched_at=datetime.now(timezone.utc),
        payload={'density_g_per_ml': '1.2', 'labels': ['VEGAN'], 'extra': 'Unbestätigt'}, source_note='Manuell geprüft')
    decision = store.accept_proposal(engine, actor, target(proposal), target(food), ['density_g_per_ml', 'labels'])
    assert decision.adopted == ('density_g_per_ml', 'labels') and decision.not_supported == ('extra',)
    assert decision.food_row_version_after == food.row_version + 1
    read = store.get_food(engine, food.public_id)
    assert read.density_g_per_ml == Decimal('1.2') and read.labels == ('VEGAN', 'VEGETARIAN')
    assert read.allergen_review_status == 'checked'
    assert store.get_proposal(engine, proposal.public_id).decision == decision
    with pytest.raises(MasterDataConflictError):
        store.accept_proposal(engine, actor, target(proposal), target(read), ['labels'])
    food = store.replace_food_storage_locations(engine, actor, target(read), [])
    archived = store.set_vocabulary_active(engine, 'storage_location', actor, target(storage), active=False)
    assert not store.get_vocabulary(engine, 'storage_location', storage.public_id).active
    store.set_vocabulary_active(engine, 'storage_location', actor, target(archived), active=True)
    assert store.list_foods(engine, category=category.public_id, tag=tag.public_id, search='Kar')[0].public_id == food.public_id


def food_and_audit_snapshot(owner, public_id):
    with owner.connect() as c:
        food = c.execute(text('SELECT to_jsonb(f) FROM cafeteria.foods f WHERE public_id=:id'),
                         {'id': public_id}).scalar_one()
        audits = c.execute(text("SELECT to_jsonb(a) FROM cafeteria.audit_events a "
                                "WHERE action LIKE 'masterdata.%' ORDER BY id")).scalars().all()
    return food, audits


@pytest.mark.parametrize('checked', [False, True])
def test_review_requires_transition_and_preserves_rejected_state(master, checked):
    owner, engine, actor = master
    food = store.create_food(engine, actor, payload())
    if not checked:
        food = store.set_food_allergen_review(engine, actor, target(food), checked=True)
    before, audits = food_and_audit_snapshot(owner, food.public_id)
    changed = store.set_food_allergen_review(engine, actor, target(food), checked=checked)
    after, changed_audits = food_and_audit_snapshot(owner, food.public_id)
    assert changed.row_version == before['row_version'] + 1 == after['row_version']
    assert after['allergen_review_status'] == ('checked' if checked else 'not_checked')
    assert after['updated_by'] == actor.user_id
    assert len(changed_audits) == len(audits) + 1
    assert changed_audits[:-1] == audits
    with pytest.raises(MasterDataConflictError):
        store.set_food_allergen_review(engine, actor, target(changed), checked=checked)
    assert food_and_audit_snapshot(owner, food.public_id) == (after, changed_audits)
    assert store.update_food(engine, actor, target(changed), payload()) == changed
    assert food_and_audit_snapshot(owner, food.public_id) == (after, changed_audits)


@pytest.mark.parametrize('kind', ['food_category', 'tag', 'storage_location'])
def test_vocabulary_noop_stale_and_archive_contract(master, kind):
    owner, engine, actor = master
    item = store.create_vocabulary(engine, kind, actor, code='TEST', name=' Test  Name ')
    count = audit_count(owner)
    assert store.update_vocabulary(engine, kind, actor, target(item), name='Test Name') == item
    assert audit_count(owner) == count
    changed = store.update_vocabulary(engine, kind, actor, target(item), name='Neu')
    assert changed.row_version == item.row_version + 1
    with pytest.raises(MasterDataConflictError):
        store.update_vocabulary(engine, kind, actor, target(item), name='Veraltet')
    archived = store.set_vocabulary_active(engine, kind, actor, target(changed), active=False)
    assert store.list_vocabulary(engine, kind) == ()
    assert store.list_vocabulary(engine, kind, include_archived=True)[0].public_id == item.public_id
    with pytest.raises(MasterDataConflictError):
        store.set_vocabulary_active(engine, kind, actor, target(archived), active=False)


def test_proposal_conflict_is_atomic_and_unchanged_decision_has_one_audit(master):
    owner, engine, actor = master
    food = store.create_food(engine, actor, {**payload(), 'density_g_per_ml': '1.2'})
    proposal = store.create_proposal(engine, actor, source='ai', source_reference='run-1', fetched_at=datetime.now(timezone.utc),
        payload={'density_g_per_ml': '2', 'piece_weight_g': '5'}, source_note='Prüfvorschlag')
    count = audit_count(owner)
    with pytest.raises(MasterDataConflictError):
        store.accept_proposal(engine, actor, target(proposal), target(food), ['density_g_per_ml', 'piece_weight_g'])
    assert audit_count(owner) == count
    assert store.get_food(engine, food.public_id).piece_weight_g is None
    assert store.get_proposal(engine, proposal.public_id).status == 'open'
    store.reject_proposal(engine, actor, target(proposal), reason='Falsche Dichte')
    other = store.create_proposal(engine, actor, source='supplier', source_reference='row-1', fetched_at=datetime.now(timezone.utc),
        payload={'density_g_per_ml': '1.20'}, source_note='Lieferant')
    count = audit_count(owner)
    decision = store.accept_proposal(engine, actor, target(other), target(food), ['density_g_per_ml'])
    assert decision.adopted == () and decision.unchanged == ('density_g_per_ml',)
    assert decision.food_row_version_before == decision.food_row_version_after == food.row_version
    assert audit_count(owner) == count + 1


@pytest.mark.parametrize('table', ['measurement_units','food_categories','foods','tags','food_tags','food_labels',
                                  'food_allergens','storage_locations','food_storage_locations','food_data_proposals'])
def test_application_has_read_but_no_direct_dml(master, table):
    owner, _, _ = master
    with owner.connect() as c:
        rights = c.execute(text("SELECT has_table_privilege('cafeteria_app',:table,'SELECT'), "
            "has_table_privilege('cafeteria_app',:table,'INSERT,UPDATE,DELETE,TRUNCATE'), "
            "has_table_privilege('cafeteria_auth_issuer',:table,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),
            {'table': 'cafeteria.' + table}).one()
        assert rights == (True, False, False)


def test_declared_unit_semantics_and_source_fields_are_immutable(master):
    owner, engine, actor = master
    unit = store.create_unit(engine, actor, code='DOS', display_name='Dose', dimension='count', base_factor='2')
    renamed = store.rename_unit(engine, actor, target(unit), display_name='Doppelpack')
    assert renamed.row_version == unit.row_version + 1
    for sql in ["UPDATE cafeteria.measurement_units SET base_factor=2 WHERE code='G'",
                "DELETE FROM cafeteria.measurement_units WHERE code='G'", 'TRUNCATE cafeteria.measurement_units CASCADE']:
        with pytest.raises(DBAPIError):
            with owner.begin() as c:
                c.execute(text(sql))
    assert store.get_unit(engine, unit.public_id).base_factor == Decimal(2)


def test_location_scope_is_enforced_by_service_and_composite_foreign_keys(master):
    owner, engine, actor = master
    food = store.create_food(engine, actor, payload())
    with owner.begin() as c:
        foreign = c.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('FOREIGN','Fremder Standort',false) RETURNING id")).scalar_one()
        category = c.execute(text("INSERT INTO cafeteria.food_categories(location_id,code,name) VALUES(:loc,'OTHER','Andere') RETURNING id,public_id"), {'loc':foreign}).one()
        tag = c.execute(text("INSERT INTO cafeteria.tags(location_id,code,name) VALUES(:loc,'OTHER','Andere') RETURNING id,public_id"), {'loc':foreign}).one()
        food_row = c.execute(text('SELECT id,location_id FROM cafeteria.foods WHERE public_id=CAST(:id AS uuid)'), {'id':food.public_id}).one()
    with pytest.raises(MasterDataValidationError):
        store.update_food(engine,actor,target(food),{**payload(),'category_public_id':str(category.public_id)})
    with pytest.raises(MasterDataValidationError):
        store.replace_food_tags(engine,actor,target(food),[str(tag.public_id)])
    for sql, params in [
        ('UPDATE cafeteria.foods SET category_id=:category WHERE id=:food', {'category':category.id,'food':food_row.id}),
        ('INSERT INTO cafeteria.food_tags(location_id,food_id,tag_id) VALUES(:loc,:food,:tag)',
         {'loc':food_row.location_id,'food':food_row.id,'tag':tag.id}),
    ]:
        with pytest.raises(DBAPIError):
            with owner.begin() as c:
                c.execute(text(sql),params)
    assert store.get_food(engine,food.public_id).row_version == food.row_version


def test_proposal_limits_source_immutability_and_unknown_fields(master):
    owner, engine, actor = master
    with pytest.raises(MasterDataValidationError):
        store.create_proposal(engine,actor,source='off',source_reference='oversize',fetched_at=datetime.now(timezone.utc),
            payload={'first':{str(i):'x' for i in range(100)},'second':{str(i):'x' for i in range(100)}})
    with owner.connect() as c:
        assert not c.execute(text('SELECT cafeteria.master_json_valid(CAST(:data AS jsonb))'),
            {'data':json.dumps({'a':{str(i):'x' for i in range(100)},'b':{str(i):'x' for i in range(100)}})}).scalar_one()
    proposal = store.create_proposal(engine,actor,source='supplier',source_reference='row-2',fetched_at=datetime.now(timezone.utc),
        payload={'future_nutrient':'Originalwert'},source_note='Lieferant')
    with pytest.raises(MasterDataValidationError):
        store.accept_proposal(engine, actor, target(proposal), None, ['labels'])
    record = store.get_proposal(engine,proposal.public_id)
    with pytest.raises(TypeError):
        record.payload['future_nutrient'] = 'Anders'
    assert store.list_proposals(engine,status='open')[0] == record
    with pytest.raises(DBAPIError):
        with owner.begin() as c:
            c.execute(text("UPDATE cafeteria.food_data_proposals SET payload='{}' WHERE public_id=CAST(:id AS uuid)"),{'id':proposal.public_id})
    result = store.reject_proposal(engine,actor,target(proposal))
    assert result.food_public_id is None
    with pytest.raises(DBAPIError):
        with owner.begin() as c:
            c.execute(text("UPDATE cafeteria.food_data_proposals SET source_note='Anders' WHERE public_id=CAST(:id AS uuid)"),{'id':proposal.public_id})
