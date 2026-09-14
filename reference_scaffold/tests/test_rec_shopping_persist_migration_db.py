"""Schema33 -> 34 shopping list persistence migration and exact database contract."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from cafeteria.component_assignment_store import replace_component_links
from cafeteria.component_catalog_store import AdminScope
from cafeteria.workflow_copy_store import copy_previous_week
from test_component_metadata_master_lock_db import (  # noqa: F401
    PERMISSIONS,
    ROOT,
    SCHEMA,
    app_engine,
    installed_pg16,
    pg16,
    seeded_pg16,
)
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor
from test_operations_settings_db import (
    _INSERT_REVISION_SQL,
    _actor_id,
    _v19_snapshot,
    _v19_week,
)
from test_rec_import_commit_migration_db import rows_and_sequences


_VP_SPEC = importlib.util.spec_from_file_location(
    'rec_shopping_persist_package_validator', ROOT / 'tools' / 'validate_package.py'
)
assert _VP_SPEC is not None and _VP_SPEC.loader is not None
validate_package = importlib.util.module_from_spec(_VP_SPEC)
_VP_SPEC.loader.exec_module(validate_package)

SHOPPING_TABLES = (
    'shopping_lists', 'shopping_list_revisions',
    'shopping_list_manual_items', 'shopping_list_line_status',
)
ACL_PROBE_TABLES = ('menu_item_components', 'recipe_revisions', 'menu_weeks')
_GRANT_BLOCK_BEGIN = '-- Schema34 shopping list grants begin.'
_GRANT_BLOCK_END = '-- Schema34 shopping list grants end.'


def _permissions_sql_without_shopping_block() -> str:
    """Der aktuelle permissions.sql-Text ohne den v34-Block (fuer den v33-Zwischenstand).

    Ohne diesen Schnitt schlaegt permissions.sql an den noch nicht existierenden
    shopping_*-Tabellen fehl, bevor Migration 0031 gelaufen ist.
    """
    original = PERMISSIONS.read_text(encoding='utf-8')
    start = original.index(_GRANT_BLOCK_BEGIN)
    end = original.index(_GRANT_BLOCK_END) + len(_GRANT_BLOCK_END)
    return original[:start] + original[end + 1:]


def _table_acl(connection, table_names: tuple[str, ...]):
    return connection.execute(
        text(
            '''
            SELECT table_class.relname, COALESCE(role.rolname,'PUBLIC'), acl.privilege_type
            FROM pg_class table_class
            CROSS JOIN LATERAL aclexplode(
                COALESCE(table_class.relacl, acldefault('r', table_class.relowner))
            ) acl
            LEFT JOIN pg_roles role ON role.oid = acl.grantee
            WHERE table_class.relnamespace = 'cafeteria'::regnamespace
              AND table_class.relname = ANY(:tables)
            ORDER BY 1, 2, 3
            '''
        ),
        {'tables': list(table_names)},
    ).all()


def _insert_recipe_revision(connection, ids):
    recipe_id = connection.execute(text("""INSERT INTO cafeteria.recipes(
        location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
        VALUES(:location,:actor,:actor,'Einkaufstest',4,
        (SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'),'manual')
        RETURNING id"""), ids).scalar_one()
    return connection.execute(text("""INSERT INTO cafeteria.recipe_revisions(
        location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
        VALUES(:location,:recipe,1,'{}',
        encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor) RETURNING id"""), {
            **ids,
            'recipe': recipe_id,
        }).scalar_one()


def _seed_shopping_list(connection, ids) -> int:
    return connection.execute(text("""INSERT INTO cafeteria.shopping_lists(
        location_id,title,created_by,updated_by)
        VALUES(:location,'Wochenliste',:actor,:actor) RETURNING id"""), ids).scalar_one()


def _seed_revision(connection, ids, shopping_list_id: int) -> int:
    snapshot = json.dumps({'inputs': [], 'result': {'lines': []}})
    return connection.execute(text("""INSERT INTO cafeteria.shopping_list_revisions(
        shopping_list_id,revision_number,policy,snapshot_json,content_hash_sha256,computed_by)
        VALUES(:list,1,'leaf',CAST(:snapshot AS jsonb),
        encode(pg_catalog.sha256(convert_to(CAST(:snapshot AS text),'UTF8')),'hex'),:actor) RETURNING id"""), {
            'list': shopping_list_id, 'snapshot': snapshot, 'actor': ids['actor'],
        }).scalar_one()


def test_v33_upgrade_preserves_rows_publication_hash_acl_and_fresh_contract(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    assert (plan[-1].version, plan[-1].path.name) == (34, '0031_v33_to_v34.sql')
    for migration in plan:
        if migration.version <= 33:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))

    scratch_dir = Path(os.environ.get('CLAUDE_SANDBOX_SCRATCHPAD', '/tmp'))
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch = scratch_dir / 'permissions_v33_without_shopping.sql'
    scratch.write_text(_permissions_sql_without_shopping_block(), encoding='utf-8')
    database._execute_script(pg16, str(scratch))

    ids = _seed_scope_probe(pg16)
    actor = make_actor(pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    week = _v19_week(pg16, _actor_id(pg16))
    snapshot = _v19_snapshot(pg16, 'CAF-2026-KW36-SHOPPING-R1')
    with pg16.begin() as connection:
        revision_id = _insert_recipe_revision(connection, ids)
        unit_id = connection.execute(text(
            "SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'"
        )).scalar_one()
        connection.execute(text("""INSERT INTO cafeteria.menu_item_components(
            menu_item_id,sort_order,component_text,recipe_revision_id,
            target_quantity,target_quantity_unit_id)
            VALUES(:item,1,'Gebunden mit Zielmenge',:revision,8.000000,:unit)"""), {
                **ids, 'revision': revision_id, 'unit': unit_id,
            })
        connection.execute(text(
            "UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:week"
        ), {'week': week})
        connection.execute(text(_INSERT_REVISION_SQL), {
            'week_id': week,
            'revision_number': 1,
            'revision_code': snapshot['revision_id'],
            'snapshot': json.dumps(snapshot),
            'actor': _actor_id(pg16),
        })
        acl_before = _table_acl(connection, ACL_PROBE_TABLES)
        publication_before = connection.execute(text("""SELECT to_jsonb(r)::text
            FROM cafeteria.publication_revisions r ORDER BY id""")).all()
        active_pub_before = connection.execute(text("""SELECT to_jsonb(a)::text
            FROM cafeteria.active_publications a ORDER BY revision_db_id""")).all()
        ledger_before = connection.execute(text("""SELECT version,name,checksum_sha256,
            application_version FROM cafeteria.schema_migrations ORDER BY version""")).all()

    rows_and_seqs_before = rows_and_sequences(pg16)
    before_rows, before_seqs = rows_and_seqs_before
    unaffected_tables = {name for name in before_rows if name != 'schema_migrations'}

    assert database.run_migrations(pg16, SCHEMA) == plan
    database._execute_script(pg16, str(PERMISSIONS))

    with pg16.connect() as connection:
        acl_after = _table_acl(connection, ACL_PROBE_TABLES)
        assert acl_after == acl_before

        publication_after = connection.execute(text("""SELECT to_jsonb(r)::text
            FROM cafeteria.publication_revisions r ORDER BY id""")).all()
        active_pub_after = connection.execute(text("""SELECT to_jsonb(a)::text
            FROM cafeteria.active_publications a ORDER BY revision_db_id""")).all()
        assert publication_after == publication_before
        assert active_pub_after == active_pub_before

        assert connection.execute(text("""SELECT version,name,checksum_sha256,
            application_version FROM cafeteria.schema_migrations
            WHERE version<=33 ORDER BY version""")).all() == ledger_before
        assert connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one() == 34

        mig34 = connection.execute(text("""SELECT name,checksum_sha256,application_version
            FROM cafeteria.schema_migrations WHERE version=34""")).one()
        assert mig34[0] == '0031_v33_to_v34.sql'
        expected_sha = hashlib.sha256(
            (SCHEMA.parent / 'migrations' / '0031_v33_to_v34.sql').read_bytes()
        ).hexdigest()
        assert mig34[1] == expected_sha
        assert mig34[1] == validate_package.MIGRATION_CHECKSUMS['0031_v33_to_v34.sql']
        assert mig34[2] == 'dishboard-schema-v34'

        target_quantity_row = connection.execute(text("""SELECT target_quantity,
            target_quantity_unit_id FROM cafeteria.menu_item_components
            WHERE menu_item_id=:item AND sort_order=1"""), ids).one()
        assert target_quantity_row == (Decimal('8.000000'), unit_id)

    after_rows, after_seqs = rows_and_sequences(pg16)
    assert {k: v for k, v in after_rows.items() if k in unaffected_tables} == \
        {k: v for k, v in before_rows.items() if k in unaffected_tables}
    before_seq_names = {name for name, _ in before_seqs}
    assert {pair for pair in after_seqs if pair[0] in before_seq_names} == set(before_seqs)
    assert set(after_rows) - unaffected_tables - {'schema_migrations'} == set(SHOPPING_TABLES)
    for table_name in SHOPPING_TABLES:
        assert after_rows[table_name] == []

    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        fresh_acl = _table_acl(connection, ACL_PROBE_TABLES)
    assert fresh_acl == acl_after


def test_v33_app_paths_run_unchanged_against_v34(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    scope = AdminScope(ids['actor'], ids['location'], 'patient', ids['authz'])
    with seeded_pg16.begin() as connection:
        connection.execute(text(
            'UPDATE cafeteria.locations SET active=false WHERE id=:other_location'
        ), ids)
        item_version = connection.execute(text(
            'SELECT row_version FROM cafeteria.menu_items WHERE id=:item'
        ), ids).scalar_one()

    assignment = {'component_public_id': None, 'component_text': 'Ohne Rezept'}
    new_version = replace_component_links(app_engine, scope, ids['item'], [assignment], item_version)
    assert new_version > item_version

    with seeded_pg16.connect() as connection:
        source_week_version = connection.execute(text(
            'SELECT row_version FROM cafeteria.menu_weeks WHERE id=:week'
        ), ids).scalar_one()
    copy_previous_week(
        app_engine, scope, date(2026, 9, 14), 0, source_row_version=source_week_version,
    )
    with seeded_pg16.connect() as connection:
        copied = connection.execute(text("""SELECT count(*) FROM cafeteria.menu_item_components link
            JOIN cafeteria.menu_items item ON item.id=link.menu_item_id
            JOIN cafeteria.menu_services service ON service.id=item.service_id
            JOIN cafeteria.menu_weeks week ON week.id=service.menu_week_id
            WHERE week.week_start=DATE '2026-09-14'""")).scalar_one()
    assert copied == 1


def test_shopping_lists_manual_items_and_line_status_allow_app_crud(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)

    with app_engine.begin() as connection:
        list_id = connection.execute(text("""INSERT INTO cafeteria.shopping_lists(
            location_id,menu_week_id,title,note,created_by,updated_by)
            VALUES(:location,:week,'Wocheneinkauf','Bitte Bio wenn moeglich',:actor,:actor)
            RETURNING id"""), ids).scalar_one()
        row_version = connection.execute(text(
            'SELECT row_version FROM cafeteria.shopping_lists WHERE id=:id'
        ), {'id': list_id}).scalar_one()
        assert row_version == 1
        connection.execute(text("""UPDATE cafeteria.shopping_lists
            SET note='Aktualisiert',updated_by=:actor WHERE id=:id"""), {**ids, 'id': list_id})
        bumped_version = connection.execute(text(
            'SELECT row_version FROM cafeteria.shopping_lists WHERE id=:id'
        ), {'id': list_id}).scalar_one()
        assert bumped_version == 2

        snapshot = json.dumps({'inputs': [], 'result': {'lines': []}})
        revision_id = connection.execute(text("""INSERT INTO cafeteria.shopping_list_revisions(
            shopping_list_id,revision_number,policy,snapshot_json,content_hash_sha256,computed_by)
            VALUES(:list,1,'leaf',CAST(:snapshot AS jsonb),
            encode(pg_catalog.sha256(convert_to(CAST(:snapshot AS text),'UTF8')),'hex'),:actor) RETURNING id"""), {
                'list': list_id, 'snapshot': snapshot, 'actor': ids['actor'],
            }).scalar_one()

        item_id = connection.execute(text("""INSERT INTO cafeteria.shopping_list_manual_items(
            shopping_list_id,sort_order,item_text,quantity,unit_id,created_by,updated_by)
            SELECT :list,1,'Servietten',NULL,NULL,:actor,:actor RETURNING id"""), {
                'list': list_id, 'actor': ids['actor'],
            }).scalar_one()
        connection.execute(text("""UPDATE cafeteria.shopping_list_manual_items
            SET checked=true,updated_by=:actor WHERE id=:id"""), {**ids, 'id': item_id})
        connection.execute(text(
            'DELETE FROM cafeteria.shopping_list_manual_items WHERE id=:id'
        ), {'id': item_id})

        connection.execute(text("""INSERT INTO cafeteria.shopping_list_line_status(
            shopping_list_id,line_key,revision_id,checked_quantity,checked_by)
            VALUES(:list,'food:milk:l',:revision,'2.000000 L',:actor)
            ON CONFLICT (shopping_list_id,line_key) DO UPDATE
                SET revision_id=EXCLUDED.revision_id,checked_quantity=EXCLUDED.checked_quantity,
                    checked_by=EXCLUDED.checked_by"""), {
                'list': list_id, 'revision': revision_id, 'actor': ids['actor'],
            })
        connection.execute(text(
            'DELETE FROM cafeteria.shopping_list_line_status WHERE shopping_list_id=:list'
        ), {'list': list_id})

    # DELETE ist fuer cafeteria_app gegrantet (S3), aber die append-only Revision (nie
    # loeschbar) haelt shopping_list_revisions_shopping_list_id_fkey (RESTRICT) davor:
    # eine Liste mit mindestens einer Berechnungsrevision kann nie geloescht werden.
    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text('DELETE FROM cafeteria.shopping_lists WHERE id=:id'), {'id': list_id})
    assert error.value.orig.sqlstate == '23503'
    assert error.value.orig.diag.constraint_name == 'shopping_list_revisions_shopping_list_id_fkey'


def test_shopping_list_revisions_reject_app_update_and_delete_by_acl(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)
        revision_id = _seed_revision(connection, ids, list_id)

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text(
                "UPDATE cafeteria.shopping_list_revisions SET policy='prepared' WHERE id=:id"
            ), {'id': revision_id})
    assert error.value.orig.sqlstate == '42501'

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text(
                'DELETE FROM cafeteria.shopping_list_revisions WHERE id=:id'
            ), {'id': revision_id})
    assert error.value.orig.sqlstate == '42501'


def test_shopping_list_revision_immutable_trigger_rejects_owner_update_and_delete(seeded_pg16):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)
        revision_id = _seed_revision(connection, ids, list_id)

    with pytest.raises(DBAPIError) as error:
        with seeded_pg16.begin() as connection:
            connection.execute(text(
                "UPDATE cafeteria.shopping_list_revisions SET policy='prepared' WHERE id=:id"
            ), {'id': revision_id})
    assert error.value.orig.sqlstate == '55000'

    with pytest.raises(DBAPIError) as error:
        with seeded_pg16.begin() as connection:
            connection.execute(text(
                'DELETE FROM cafeteria.shopping_list_revisions WHERE id=:id'
            ), {'id': revision_id})
    assert error.value.orig.sqlstate == '55000'


def test_content_hash_check_rejects_wrong_hash(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.shopping_list_revisions(
                shopping_list_id,revision_number,policy,snapshot_json,content_hash_sha256,computed_by)
                VALUES(:list,1,'leaf','{"inputs":[],"result":{}}'::jsonb,repeat('0',64),:actor)"""), {
                    'list': list_id, 'actor': ids['actor'],
                })
    assert error.value.orig.sqlstate == '23514'
    assert error.value.orig.diag.constraint_name == 'shopping_list_revisions_content_hash_sha256_check'


@pytest.mark.parametrize(
    ('table', 'columns', 'values', 'sqlstate', 'constraint'),
    [
        (
            'shopping_lists', 'location_id,title,created_by,updated_by',
            ':bogus,\'Liste\',:actor,:actor', '23503', 'shopping_lists_location_id_fkey',
        ),
        (
            'shopping_lists', 'location_id,title,row_version,created_by,updated_by',
            ':location,\'Liste\',0,:actor,:actor', '23514', 'shopping_lists_row_version_check',
        ),
    ],
)
def test_shopping_lists_check_and_fk_negatives(
    seeded_pg16, app_engine, table, columns, values, sqlstate, constraint,  # noqa: F811
):
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version, bogus=-1)
    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(
                text(f'INSERT INTO cafeteria.{table}({columns}) VALUES({values})'), ids,
            )
    assert error.value.orig.sqlstate == sqlstate
    assert error.value.orig.diag.constraint_name == constraint


def test_shopping_list_revisions_check_and_unique_negatives(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)

    # snapshot_json und der Hash referenzieren jeweils denselben CAST(:snap AS jsonb)-Wert,
    # damit die kanonische jsonb-Textform (Postgres fuegt z. B. Leerzeichen nach ':'/','
    # ein) nie von Hand nachgebildet werden muss.
    insert_revision_sql = text("""INSERT INTO cafeteria.shopping_list_revisions(
        shopping_list_id,revision_number,policy,snapshot_json,content_hash_sha256,computed_by)
        VALUES(:list,:revision_number,:policy,CAST(:snap AS jsonb),
        encode(pg_catalog.sha256(convert_to(CAST(:snap AS jsonb)::text,'UTF8')),'hex'),:actor)""")

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(insert_revision_sql, {
                'list': list_id, 'revision_number': 1, 'policy': 'unknown',
                'snap': '{"inputs":[],"result":{}}', 'actor': ids['actor'],
            })
    assert error.value.orig.sqlstate == '23514'
    assert error.value.orig.diag.constraint_name == 'shopping_list_revisions_policy_check'

    with app_engine.begin() as connection:
        connection.execute(insert_revision_sql, {
            'list': list_id, 'revision_number': 1, 'policy': 'leaf',
            'snap': '{"inputs":[],"result":{}}', 'actor': ids['actor'],
        })
    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(insert_revision_sql, {
                'list': list_id, 'revision_number': 1, 'policy': 'prepared',
                'snap': '{"inputs":[],"result":{"x":1}}', 'actor': ids['actor'],
            })
    assert error.value.orig.sqlstate == '23505'
    assert error.value.orig.diag.constraint_name == \
        'shopping_list_revisions_shopping_list_id_revision_number_key'


def test_shopping_list_manual_items_check_fk_and_unique_negatives(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version, bogus_unit=-1)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)
    ids['list'] = list_id

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.shopping_list_manual_items(
                shopping_list_id,sort_order,item_text,quantity,unit_id,created_by,updated_by)
                VALUES(:list,1,'Mehl',2,NULL,:actor,:actor)"""), ids)
    assert error.value.orig.sqlstate == '23514'
    assert error.value.orig.diag.constraint_name == 'shopping_list_manual_items_check'

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.shopping_list_manual_items(
                shopping_list_id,sort_order,item_text,quantity,unit_id,created_by,updated_by)
                VALUES(:list,1,'Mehl',2,:bogus_unit,:actor,:actor)"""), ids)
    assert error.value.orig.sqlstate == '23503'
    assert error.value.orig.diag.constraint_name == 'shopping_list_manual_items_unit_id_fkey'

    with app_engine.begin() as connection:
        connection.execute(text("""INSERT INTO cafeteria.shopping_list_manual_items(
            shopping_list_id,sort_order,item_text,created_by,updated_by)
            VALUES(:list,1,'Servietten',:actor,:actor)"""), ids)
    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.shopping_list_manual_items(
                shopping_list_id,sort_order,item_text,created_by,updated_by)
                VALUES(:list,1,'Zweite Zeile',:actor,:actor)"""), ids)
    assert error.value.orig.sqlstate == '23505'
    assert error.value.orig.diag.constraint_name == \
        'shopping_list_manual_items_shopping_list_id_sort_order_key'


def test_shopping_list_line_status_fk_and_pk_negatives(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version, bogus_revision=-1)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)
        revision_id = _seed_revision(connection, ids, list_id)
    ids.update(list=list_id, revision=revision_id)

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.shopping_list_line_status(
                shopping_list_id,line_key,revision_id,checked_quantity,checked_by)
                VALUES(:list,'food:milk:l',:bogus_revision,'2.000000 L',:actor)"""), ids)
    assert error.value.orig.sqlstate == '23503'
    assert error.value.orig.diag.constraint_name == 'shopping_list_line_status_revision_id_fkey'

    with app_engine.begin() as connection:
        connection.execute(text("""INSERT INTO cafeteria.shopping_list_line_status(
            shopping_list_id,line_key,revision_id,checked_quantity,checked_by)
            VALUES(:list,'food:milk:l',:revision,'2.000000 L',:actor)"""), ids)
    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.shopping_list_line_status(
                shopping_list_id,line_key,revision_id,checked_quantity,checked_by)
                VALUES(:list,'food:milk:l',:revision,'3.000000 L',:actor)"""), ids)
    assert error.value.orig.sqlstate == '23505'
    assert error.value.orig.diag.constraint_name == 'shopping_list_line_status_pkey'


def test_validate_schema_reports_live_schema_34(pg16):  # noqa: F811
    environment = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(ROOT / 'database' / 'validate_schema.py'), '--live'],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    status = json.loads(result.stdout)
    assert status['artifact_check'] == 'passed'
    assert status['schema_version'] == status['live_schema_version'] == 34
    assert status['baseline_migration_equivalent'] is True
    assert len(status['migration_checksums']['0031_v33_to_v34.sql']) == hashlib.sha256().digest_size * 2
