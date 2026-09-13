"""Schema31 -> 32 accompaniment migration, template verbs and privileges."""
# ruff: noqa: F401, F811
import hashlib
import json
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from test_component_metadata_master_lock_db import (
    PERMISSIONS, SCHEMA, app_engine, installed_pg16, pg16, seeded_pg16,
)
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor
from test_operations_settings_db import _INSERT_REVISION_SQL, _actor_id, _v19_snapshot, _v19_week
from test_rec_import_commit_migration_db import rows_and_sequences


PUBLIC_V32 = {'create_dish_template_v32', 'update_dish_template_v32'}
PRIVATE_V32 = {'dish_template_mutate_v32'}
GUARD_V32 = 'reject_direct_dish_template_update_v32'


def _v32_structure(connection):
    return (
        connection.execute(text("""SELECT table_name,column_name,data_type,is_nullable,column_default
            FROM information_schema.columns WHERE table_schema='cafeteria'
            AND (table_name,column_name) IN (('menu_items','accompaniment'),
                ('dish_templates','accompaniment_default')) ORDER BY table_name""")).all(),
        connection.execute(text("""SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid)
            FROM pg_constraint WHERE connamespace='cafeteria'::regnamespace
            AND conname IN ('menu_items_accompaniment_check',
                'dish_templates_accompaniment_default_check') ORDER BY conname""")).all(),
        connection.execute(text("""SELECT proname,pg_get_function_identity_arguments(oid),prosrc,
            prosecdef,proconfig,proacl FROM pg_proc WHERE pronamespace='cafeteria'::regnamespace
            AND proname LIKE '%dish_template%_v32' ORDER BY proname""")).all(),
    )


def _call_template(engine, ids, version, verb, payload, previous=None):
    with engine.begin() as connection:
        return connection.execute(
            text(
                f'SELECT cafeteria.{verb}_dish_template_v{version}('
                ':actor,:authz,:location,:target,:expected,CAST(:payload AS jsonb))'
            ),
            {
                **ids,
                'target': previous['public_id'] if previous else None,
                'expected': previous['updated_at'] if previous else None,
                'payload': json.dumps(payload),
            },
        ).scalar_one()


def _payload(**changes):
    return {
        'menu_type_code': 'MENU_1',
        'profile_scope': 'common',
        'title': 'Vorlage',
        'description': None,
        'recipe_public_id': None,
        **changes,
    }


def _assert_sqlstate(expected, callback):
    with pytest.raises(DBAPIError) as error:
        callback()
    assert error.value.orig.sqlstate == expected


def _execute(engine, statement, parameters=None):
    with engine.begin() as connection:
        return connection.execute(text(statement), parameters or {}).all()


def _acl_contract(connection):
    return (
        connection.execute(text("""SELECT c.relname,COALESCE(g.rolname,'PUBLIC'),a.privilege_type,
            a.is_grantable FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a
            LEFT JOIN pg_roles g ON g.oid=a.grantee WHERE n.nspname='cafeteria'
            AND c.relname IN ('dish_templates','menu_items') ORDER BY 1,2,3,4""")).all(),
        connection.execute(text("""SELECT c.relname,x.attname,COALESCE(g.rolname,'PUBLIC'),
            a.privilege_type,a.is_grantable FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute x ON x.attrelid=c.oid
            CROSS JOIN LATERAL aclexplode(x.attacl) a
            LEFT JOIN pg_roles g ON g.oid=a.grantee WHERE n.nspname='cafeteria'
            AND c.relname IN ('dish_templates','menu_items') AND x.attacl IS NOT NULL
            ORDER BY 1,2,3,4,5""")).all(),
        connection.execute(text(f"""SELECT p.proname,pg_get_function_identity_arguments(p.oid),
            pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,COALESCE(g.rolname,'PUBLIC'),
            a.privilege_type,a.is_grantable FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
            LEFT JOIN pg_roles g ON g.oid=a.grantee WHERE n.nspname='cafeteria'
            AND p.proname IN ('validate_menu_dish_scope_v26','dish_template_mutate_v26',
                'create_dish_template_v26','update_dish_template_v26','set_dish_template_active_v26',
                'dish_template_mutate_v32','create_dish_template_v32','update_dish_template_v32',
                '{GUARD_V32}') ORDER BY 1,2,6,7,8""")).all(),
    )


def test_bootstrap_and_v31_upgrade_have_identical_acl_contract(pg16):
    plan = database.migration_plan(SCHEMA)
    for migration in plan[:-1]:
        database._execute_migration(pg16, migration)
    with pg16.begin() as connection:
        connection.execute(text("""GRANT SELECT,INSERT,UPDATE,DELETE ON
            cafeteria.dish_templates,cafeteria.menu_items TO cafeteria_app"""))
        connection.execute(text("""GRANT SELECT ON
            cafeteria.dish_templates,cafeteria.menu_items TO cafeteria_backup"""))
    database._execute_migration(pg16, plan[-1])
    with pg16.connect() as connection:
        migrated = _acl_contract(connection)

    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert _acl_contract(connection) == migrated


def test_app_row_locks_and_menu_scope_survive_while_direct_template_dml_is_denied(
    seeded_pg16,
    app_engine,
):
    owner, engine = seeded_pg16, app_engine
    ids = _seed_scope_probe(owner)
    actor = make_actor(owner)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with owner.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.locations SET active=false WHERE id=:other_location'), ids,
        )
    created = _call_template(engine, ids, 26, 'create', _payload(title='ACL guard'))
    with owner.connect() as connection:
        template_id = connection.execute(text(
            'SELECT id FROM cafeteria.dish_templates WHERE public_id=:id'
        ), {'id': created['public_id']}).scalar_one()
        trigger_contract = connection.execute(text(f"""SELECT t.tgenabled,p.proname,
            NOT p.prosecdef,p.proconfig,p.proowner=c.relowner,
            pg_get_userbyid(c.relowner)<>'cafeteria_app' FROM pg_trigger t
            JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_class c ON c.oid=t.tgrelid
            WHERE NOT t.tgisinternal AND c.oid='cafeteria.dish_templates'::regclass
            AND p.proname='{GUARD_V32}'""")).one_or_none()
        assert trigger_contract == (
            'O', GUARD_V32, True, ['search_path=pg_catalog, cafeteria, pg_temp'], True, True,
        )

    lock_query = ("SELECT d.id FROM cafeteria.dish_templates d "
                  "WHERE d.id=ANY(CAST(:ids AS bigint[])) ORDER BY d.id FOR {mode} OF d")
    for mode in ('SHARE', 'KEY SHARE', 'NO KEY UPDATE', 'UPDATE'):
        assert _execute(engine, lock_query.format(mode=mode), {'ids': []}) == []
        assert len(_execute(engine, lock_query.format(mode=mode), {'ids': [template_id]})) == 1

    with engine.begin() as connection:
        connection.execute(text(
            'UPDATE cafeteria.menu_items SET dish_template_id=:template WHERE id=:item'
        ), {'template': template_id, 'item': ids['item']})
        inserted = connection.execute(text("""INSERT INTO cafeteria.menu_items(
            service_id,menu_type_id,external_id,title,sort_order,dish_template_id)
            SELECT service_id,(SELECT id FROM cafeteria.menu_types WHERE code='VEGGIE'),
                'ACC-ACL-INSERT','Trigger insert',2,:template
            FROM cafeteria.menu_items WHERE id=:item RETURNING id"""), {
                'template': template_id, 'item': ids['item'],
            }).scalar_one()
        connection.execute(text(
            'UPDATE cafeteria.menu_items SET service_id=service_id WHERE id=:item'
        ), {'item': inserted})

    denied = (
        ('42501', 'UPDATE cafeteria.dish_templates SET title=title WHERE id=:id',
         {'id': template_id}),
        ('42501', 'UPDATE cafeteria.dish_templates SET id=DEFAULT WHERE false', {}),
        ('42501', 'UPDATE cafeteria.dish_templates SET id=DEFAULT WHERE id=:id',
         {'id': template_id}),
        ('428C9', 'UPDATE cafeteria.dish_templates SET id=id WHERE id=:id',
         {'id': template_id}),
        ('42501', "INSERT INTO cafeteria.dish_templates(title) VALUES('direkt')", {}),
        ('42501', 'DELETE FROM cafeteria.dish_templates WHERE id=:id', {'id': template_id}),
        ('42501', 'ALTER TABLE cafeteria.dish_templates DISABLE TRIGGER ALL', {}),
    )
    for expected, statement, parameters in denied:
        _assert_sqlstate(expected, lambda s=statement, p=parameters: _execute(engine, s, p))

    locker = engine.connect()
    transaction = locker.begin()
    try:
        locker.execute(text(
            'SELECT id FROM cafeteria.dish_templates WHERE id=:id FOR UPDATE'
        ), {'id': template_id}).all()
        _assert_sqlstate(
            '55P03',
            lambda: _call_template(engine, ids, 32, 'update', _payload(title='blocked'), created),
        )
    finally:
        transaction.rollback()
        locker.close()
    released = _call_template(engine, ids, 32, 'update', _payload(title='released'), created)
    inactive = _execute(engine, """SELECT cafeteria.set_dish_template_active_v26(
        :actor,:authz,:location,:target,:expected,CAST(:payload AS jsonb))""", {
            **ids, 'target': released['public_id'], 'expected': released['updated_at'],
            'payload': json.dumps({'active': False}),
        })[0][0]
    assert inactive['active'] is False


def test_schema31_upgrade_preserves_nonempty_data_defaults_and_fresh_contract(pg16):
    plan = database.migration_plan(SCHEMA)
    assert (plan[-1].version, plan[-1].path.name) == (32, '0029_v31_to_v32.sql')
    for migration in plan[:-1]:
        database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))

    actor = _actor_id(pg16)
    week = _v19_week(pg16, actor)
    snapshot = _v19_snapshot(pg16, 'CAF-2026-KW36-ACC-R1')
    with pg16.begin() as connection:
        connection.execute(
            text("INSERT INTO cafeteria.dish_templates(title) VALUES('Bestehende Vorlage')")
        )
        connection.execute(
            text("UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:week"),
            {'week': week},
        )
        connection.execute(
            text(_INSERT_REVISION_SQL),
            {
                'week_id': week,
                'revision_number': 1,
                'revision_code': snapshot['revision_id'],
                'snapshot': json.dumps(snapshot),
                'actor': actor,
            },
        )
        historical_ledger = connection.execute(text(
            'SELECT version,name,checksum_sha256,application_version '
            'FROM cafeteria.schema_migrations ORDER BY version'
        )).all()
        snapshot_bytes = connection.execute(text(
            'SELECT snapshot_json::text FROM cafeteria.publication_revisions WHERE menu_week_id=:week'
        ), {'week': week}).scalar_one()
    before = rows_and_sequences(pg16)

    assert database.run_migrations(pg16, SCHEMA) == plan
    with pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.menu_items WHERE accompaniment<>\'none\''
        )).scalar_one() == 0
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.dish_templates WHERE accompaniment_default<>\'none\''
        )).scalar_one() == 0
        constraints = connection.execute(text("""SELECT conname FROM pg_constraint
            WHERE connamespace='cafeteria'::regnamespace AND conname IN
            ('menu_items_accompaniment_check','dish_templates_accompaniment_default_check')
            ORDER BY conname""")).scalars().all()
        assert constraints == [
            'dish_templates_accompaniment_default_check',
            'menu_items_accompaniment_check',
        ]
        assert connection.execute(text(
            'SELECT version,name FROM cafeteria.schema_migrations ORDER BY version DESC LIMIT 1'
        )).one() == (32, '0029_v31_to_v32.sql')
        assert connection.execute(text(
            'SELECT version,name,checksum_sha256,application_version '
            'FROM cafeteria.schema_migrations WHERE version<=31 ORDER BY version'
        )).all() == historical_ledger
        assert connection.execute(text(
            'SELECT snapshot_json::text FROM cafeteria.publication_revisions WHERE menu_week_id=:week'
        ), {'week': week}).scalar_one() == snapshot_bytes
        for table, rows in before[0].items():
            if table == 'schema_migrations':
                query = ('SELECT to_jsonb(t)::text FROM cafeteria.schema_migrations t '
                         'WHERE version<=31 ORDER BY to_jsonb(t)::text')
            elif table == 'menu_items':
                query = ("SELECT (to_jsonb(t)-'accompaniment')::text FROM cafeteria.menu_items t "
                         "ORDER BY (to_jsonb(t)-'accompaniment')::text")
            elif table == 'dish_templates':
                query = ("SELECT (to_jsonb(t)-'accompaniment_default')::text "
                         "FROM cafeteria.dish_templates t "
                         "ORDER BY (to_jsonb(t)-'accompaniment_default')::text")
            else:
                query = (f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t '
                         'ORDER BY to_jsonb(t)::text')
            assert connection.execute(text(query)).all() == rows
        migrated = _v32_structure(connection)
    assert rows_and_sequences(pg16)[1] == before[1]

    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert _v32_structure(connection) == migrated


def test_v32_template_defaults_validation_cas_audit_v26_compatibility_and_acl(
    seeded_pg16,
    app_engine,
):
    owner, engine = seeded_pg16, app_engine
    ids = _seed_scope_probe(owner)
    actor = make_actor(owner)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with owner.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.locations SET active=false WHERE id=:other_location'),
            ids,
        )

    created = _call_template(engine, ids, 32, 'create', _payload())
    with owner.connect() as connection:
        assert connection.execute(text(
            'SELECT accompaniment_default FROM cafeteria.dish_templates WHERE public_id=:id'
        ), {'id': created['public_id']}).scalar_one() == 'none'

    salad = _call_template(
        engine,
        ids,
        32,
        'update',
        _payload(accompaniment_default='salad'),
        created,
    )
    retained = _call_template(engine, ids, 32, 'update', _payload(), salad)
    assert retained == salad
    with owner.connect() as connection:
        template = connection.execute(text(
            'SELECT accompaniment_default,updated_at FROM cafeteria.dish_templates WHERE public_id=:id'
        ), {'id': salad['public_id']}).one()
        assert template.accompaniment_default == 'salad'
        assert template.updated_at.timestamp() == pytest.approx(
            datetime.fromisoformat(salad['updated_at']).timestamp()
        )
        audit = connection.execute(text("""SELECT action,details FROM cafeteria.audit_events
            WHERE entity_public_id=:id AND action='dish_template.updated' ORDER BY id DESC LIMIT 1"""),
            {'id': salad['public_id']}).one()
        assert audit.action == 'dish_template.updated'
        assert audit.details['accompaniment_default'] == 'salad'
        assert connection.execute(text("""SELECT count(*) FROM cafeteria.audit_events
            WHERE entity_public_id=:id AND action='dish_template.updated'"""),
            {'id': salad['public_id']}).scalar_one() == 1

    _assert_sqlstate(
        'P1901',
        lambda: _call_template(
            engine, ids, 32, 'create', _payload(accompaniment_default='both')
        ),
    )
    _assert_sqlstate(
        'P1901',
        lambda: _call_template(engine, ids, 32, 'create', _payload(unknown='value')),
    )
    _assert_sqlstate(
        '55000',
        lambda: _call_template(
            engine,
            ids,
            32,
            'update',
            _payload(title='CAS stale', accompaniment_default='soup'),
            created,
        ),
    )

    changed_by_v26 = _call_template(
        engine,
        ids,
        26,
        'update',
        _payload(title='Alter Client'),
        salad,
    )
    with owner.connect() as connection:
        assert connection.execute(text(
            'SELECT title,accompaniment_default FROM cafeteria.dish_templates WHERE public_id=:id'
        ), {'id': changed_by_v26['public_id']}).one() == ('Alter Client', 'salad')

        rows = connection.execute(text("""SELECT p.proname,p.prosecdef,p.proconfig,
            p.proowner=n.nspowner AS same_owner,
            has_function_privilege('cafeteria_app',p.oid,'EXECUTE') AS app,
            has_function_privilege('cafeteria_backup',p.oid,'EXECUTE') AS backup,
            has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE') AS issuer,
            EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='cafeteria' AND p.proname IN
                ('dish_template_mutate_v32','create_dish_template_v32','update_dish_template_v32')
            ORDER BY p.proname""")).mappings().all()
        assert {row['proname'] for row in rows} == PUBLIC_V32 | PRIVATE_V32
        for row in rows:
            assert row['prosecdef'] and row['same_owner']
            assert row['proconfig'] == ['search_path=pg_catalog, cafeteria, pg_temp']
            assert row['app'] == (row['proname'] in PUBLIC_V32)
            assert not any(row[key] for key in ('backup', 'issuer', 'public'))
