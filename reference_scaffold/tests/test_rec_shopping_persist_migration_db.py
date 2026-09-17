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
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from cafeteria.component_assignment_store import replace_component_links
from cafeteria.component_catalog_store import AdminScope
from cafeteria.workflow_copy_store import copy_previous_week
from test_component_metadata_master_lock_db import (  # noqa: F401
    APP_PASSWORD,
    PERMISSIONS,
    ROOT,
    SCHEMA,
    _role_engine,
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

_VS_SPEC = importlib.util.spec_from_file_location(
    'rec_shopping_persist_schema_validator', ROOT / 'database' / 'validate_schema.py'
)
assert _VS_SPEC is not None and _VS_SPEC.loader is not None
validate_schema = importlib.util.module_from_spec(_VS_SPEC)
_VS_SPEC.loader.exec_module(validate_schema)

SHOPPING_TABLES = (
    'shopping_lists', 'shopping_list_revisions',
    'shopping_list_manual_items', 'shopping_list_line_status',
)
SHOPPING_SEQUENCES = (
    'shopping_lists_id_seq', 'shopping_list_revisions_id_seq', 'shopping_list_manual_items_id_seq',
)
SHOPPING_FUNCTIONS = (
    'cafeteria.shopping_list_revision_protect_v34()', 'cafeteria.shopping_list_scope_protect_v34()',
)
ACL_PROBE_TABLES = ('menu_item_components', 'recipe_revisions', 'menu_weeks')
FUNCTION_GRANTEES = ('public', 'cafeteria_app', 'cafeteria_backup', 'cafeteria_auth_issuer')
EXPECTED_NEW_OBJECTS = {
    *(('relation:r', f'cafeteria.{name}') for name in SHOPPING_TABLES),
    *(('relation:S', f'cafeteria.{name}') for name in SHOPPING_SEQUENCES),
    *(('function', name) for name in SHOPPING_FUNCTIONS),
}
# S3: exakte Nicht-Owner-ACL der neuen Objekte (Owner-Einträge ausgenommen).
EXPECTED_NEW_OBJECT_ACL = {
    *(
        ('relation:r', f'cafeteria.{table}', 'cafeteria_app', privilege, False)
        for table in ('shopping_lists', 'shopping_list_manual_items', 'shopping_list_line_status')
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
    ),
    ('relation:r', 'cafeteria.shopping_list_revisions', 'cafeteria_app', 'SELECT', False),
    ('relation:r', 'cafeteria.shopping_list_revisions', 'cafeteria_app', 'INSERT', False),
    *(
        ('relation:r', f'cafeteria.{table}', 'cafeteria_backup', 'SELECT', False)
        for table in SHOPPING_TABLES
    ),
    *(
        ('relation:S', f'cafeteria.{sequence}', 'cafeteria_backup', 'SELECT', False)
        for sequence in SHOPPING_SEQUENCES
    ),
}
_GRANT_BLOCK_BEGIN = '-- Schema34 shopping list grants begin.'
_GRANT_BLOCK_END = '-- Schema34 shopping list grants end.'
_REVISION_HASH = "encode(pg_catalog.sha256(convert_to(CAST(:snapshot_json AS jsonb)::text,'UTF8')),'hex')"


def _permissions_sql_without_shopping_block() -> str:
    """Der aktuelle permissions.sql-Text ohne den v34-Block (für den v33-Zwischenstand).

    Ohne diesen Schnitt schlägt permissions.sql an den noch nicht existierenden
    shopping_*-Tabellen fehl, bevor Migration 0031 gelaufen ist.
    """
    original = PERMISSIONS.read_text(encoding='utf-8')
    start = original.index(_GRANT_BLOCK_BEGIN)
    end = original.index(_GRANT_BLOCK_END) + len(_GRANT_BLOCK_END)
    return original[:start] + original[end + 1:]


def _cafeteria_acl(connection) -> set[tuple[Any, ...]]:
    """ACL-Katalog aller cafeteria-Objekte: (Art, Objekt, Grantee, Recht, grantable, Owner?)."""
    rows = connection.execute(text(
        '''
        SELECT 'schema', ns.nspname, COALESCE(role.rolname,'PUBLIC'), acl.privilege_type,
               acl.is_grantable, acl.grantee=ns.nspowner
        FROM pg_namespace ns
        CROSS JOIN LATERAL aclexplode(COALESCE(ns.nspacl, acldefault('n', ns.nspowner))) acl
        LEFT JOIN pg_roles role ON role.oid=acl.grantee
        WHERE ns.nspname='cafeteria'
        UNION ALL
        SELECT 'relation:' || rel.relkind::text, 'cafeteria.' || rel.relname, COALESCE(role.rolname,'PUBLIC'),
               acl.privilege_type, acl.is_grantable, acl.grantee=rel.relowner
        FROM pg_class rel
        CROSS JOIN LATERAL aclexplode(COALESCE(
            rel.relacl,
            acldefault(CASE WHEN rel.relkind='S' THEN 's'::"char" ELSE 'r'::"char" END, rel.relowner)
        )) acl
        LEFT JOIN pg_roles role ON role.oid=acl.grantee
        WHERE rel.relnamespace='cafeteria'::regnamespace AND rel.relkind IN ('r','p','v','m','S')
        UNION ALL
        SELECT 'column', 'cafeteria.' || rel.relname || '.' || att.attname, COALESCE(role.rolname,'PUBLIC'),
               acl.privilege_type, acl.is_grantable, acl.grantee=rel.relowner
        FROM pg_attribute att
        JOIN pg_class rel ON rel.oid=att.attrelid
        CROSS JOIN LATERAL aclexplode(att.attacl) acl
        LEFT JOIN pg_roles role ON role.oid=acl.grantee
        WHERE rel.relnamespace='cafeteria'::regnamespace AND att.attnum>0
          AND NOT att.attisdropped AND att.attacl IS NOT NULL
        UNION ALL
        SELECT 'function',
               'cafeteria.' || proc.proname || '(' || pg_get_function_identity_arguments(proc.oid) || ')',
               COALESCE(role.rolname,'PUBLIC'),
               acl.privilege_type, acl.is_grantable, acl.grantee=proc.proowner
        FROM pg_proc proc
        CROSS JOIN LATERAL aclexplode(COALESCE(proc.proacl, acldefault('f', proc.proowner))) acl
        LEFT JOIN pg_roles role ON role.oid=acl.grantee
        WHERE proc.pronamespace='cafeteria'::regnamespace
        '''
    )).tuples().all()
    return set(rows)


def _execute_surface(connection) -> dict[str, list[str]]:
    return {
        grantee: connection.execute(text(
            '''
            SELECT proc.oid::regprocedure::text FROM pg_proc proc
            WHERE proc.pronamespace='cafeteria'::regnamespace
              AND has_function_privilege(:grantee, proc.oid, 'EXECUTE')
            ORDER BY 1
            '''
        ), {'grantee': grantee}).scalars().all()
        for grantee in FUNCTION_GRANTEES
    }


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


def _seed_shopping_list(connection, ids, menu_week_id: int | None = None) -> int:
    return connection.execute(text("""INSERT INTO cafeteria.shopping_lists(
        location_id,menu_week_id,title,created_by,updated_by)
        VALUES(:location,:week,'Wochenliste',:actor,:actor) RETURNING id"""), {
            **ids, 'week': menu_week_id,
        }).scalar_one()


def _seed_revision(connection, ids, shopping_list_id: int) -> int:
    snapshot = json.dumps({'inputs': [], 'result': {'lines': []}})
    return connection.execute(text("""INSERT INTO cafeteria.shopping_list_revisions(
        shopping_list_id,revision_number,policy,snapshot_json,content_hash_sha256,computed_by)
        VALUES(:list,1,'leaf',CAST(:snapshot AS jsonb),
        encode(pg_catalog.sha256(convert_to(CAST(:snapshot AS jsonb)::text,'UTF8')),'hex'),:actor)
        RETURNING id"""), {
            'list': shopping_list_id, 'snapshot': snapshot, 'actor': ids['actor'],
        }).scalar_one()


def _shopping_context(owner_engine) -> dict[str, Any]:
    """Standort, Woche, Akteur, Einheit sowie je eine bestehende Zeile aller vier Tabellen."""
    ids: dict[str, Any] = dict(_seed_scope_probe(owner_engine))
    actor = make_actor(owner_engine)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with owner_engine.begin() as connection:
        ids['unit'] = connection.execute(text(
            "SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'"
        )).scalar_one()
        ids['list'] = _seed_shopping_list(connection, ids, ids['week'])
        ids['revision'] = _seed_revision(connection, ids, ids['list'])
        ids['other_list'] = _seed_shopping_list(connection, ids)
        ids['other_revision'] = _seed_revision(connection, ids, ids['other_list'])
        ids['list_public_id'], = connection.execute(text(
            'SELECT public_id FROM cafeteria.shopping_lists WHERE id=:list'
        ), ids).one()
        ids['revision_public_id'], = connection.execute(text(
            'SELECT public_id FROM cafeteria.shopping_list_revisions WHERE id=:revision'
        ), ids).one()
        ids['manual_item'], ids['manual_item_public_id'] = connection.execute(text("""INSERT INTO
            cafeteria.shopping_list_manual_items(shopping_list_id,sort_order,item_text,created_by,updated_by)
            VALUES(:list,1,'Servietten',:actor,:actor) RETURNING id,public_id"""), ids).one()
        connection.execute(text("""INSERT INTO cafeteria.shopping_list_line_status(
            shopping_list_id,line_key,revision_id,checked_quantity,checked_by)
            VALUES(:list,'food:milk:l',:revision,'2.000000 L',:actor)"""), ids)
    return ids


def _insert_statement(
    table: str,
    values: dict[str, Any],
    *,
    overriding: bool = False,
    expressions: dict[str, str] | None = None,
) -> str:
    rendered = dict(expressions or {})
    columns = list(values) + [column for column in rendered if column not in values]
    placeholders = [rendered.get(column, f':{column}') for column in columns]
    override = ' OVERRIDING SYSTEM VALUE' if overriding else ''
    return (
        f'INSERT INTO cafeteria.{table}({",".join(columns)}){override} '
        f'VALUES({",".join(placeholders)})'
    )


def _rejections(engine, cases) -> list[tuple[str, object]]:
    """Führt jeden Fall in einer eigenen Transaktion aus; liefert Abweichungen von
    (SQLSTATE, diag.constraint_name) oder angenommene Zeilen."""
    mismatches: list[tuple[str, object]] = []
    for label, statement, values, sqlstate, constraint in cases:
        try:
            with engine.begin() as connection:
                connection.execute(text(statement), values)
        except DBAPIError as error:
            actual = (error.orig.sqlstate, error.orig.diag.constraint_name)
            if actual != (sqlstate, constraint):
                mismatches.append((label, actual))
        else:
            mismatches.append((label, 'accepted'))
    return mismatches


def test_v33_upgrade_preserves_rows_publication_hash_acl_and_fresh_contract(pg16, tmp_path):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    assert (plan[-1].version, plan[-1].path.name) == (34, '0031_v33_to_v34.sql')
    for migration in plan:
        if migration.version <= 33:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))

    scratch = tmp_path / 'permissions_v33_without_shopping.sql'
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
        acl_before = _cafeteria_acl(connection)
        surface_before = _execute_surface(connection)
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

    # ACL direkt nach der Migration, bewusst OHNE erneutes permissions.sql (Review P2-4).
    with pg16.connect() as connection:
        acl_migrated = _cafeteria_acl(connection)
        surface_migrated = _execute_surface(connection)
        new_function_privileges = {
            (function, grantee): connection.execute(text(
                "SELECT has_function_privilege(:grantee, CAST(:function AS regprocedure), 'EXECUTE')"
            ), {'grantee': grantee, 'function': function}).scalar_one()
            for function in SHOPPING_FUNCTIONS
            for grantee in FUNCTION_GRANTEES
        }
    before_objects = {row[:2] for row in acl_before}
    assert {row for row in acl_migrated if row[:2] in before_objects} == acl_before
    new_objects = {row[:2] for row in acl_migrated} - before_objects
    assert new_objects == EXPECTED_NEW_OBJECTS
    assert {
        row[:5] for row in acl_migrated if row[:2] in new_objects and not row[5]
    } == EXPECTED_NEW_OBJECT_ACL
    assert surface_migrated == surface_before
    assert new_function_privileges == dict.fromkeys(new_function_privileges, False)

    with pg16.connect() as connection:
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

    # Verhalten der Migrations-ACL auf der migrierten DB (ohne permissions.sql).
    migrated_app = _role_engine('cafeteria_app', APP_PASSWORD)
    try:
        with migrated_app.begin() as connection:
            list_id = _seed_shopping_list(connection, ids, week)
            shopping_revision_id = _seed_revision(connection, ids, list_id)
        with pytest.raises(DBAPIError) as error:
            with migrated_app.begin() as connection:
                connection.execute(text(
                    "UPDATE cafeteria.shopping_list_revisions SET policy='prepared' WHERE id=:id"
                ), {'id': shopping_revision_id})
        assert error.value.orig.sqlstate == '42501'
    finally:
        migrated_app.dispose()

    # Der Bootstrap-Grantblock ändert an der migrierten DB nichts.
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert _cafeteria_acl(connection) == acl_migrated

    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        acl_fresh = _cafeteria_acl(connection)
    assert {row for row in acl_fresh if row[:2] in new_objects} == \
        {row for row in acl_migrated if row[:2] in new_objects}
    probe_names = {f'cafeteria.{name}' for name in ACL_PROBE_TABLES}

    def probe(acl):
        return {row for row in acl if row[1] in probe_names}

    assert probe(acl_fresh) == probe(acl_migrated) == probe(acl_before)


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
        # Eine bestehende Einkaufsliste referenziert die Quellwoche der v33-Pfade.
        shopping_list_id = _seed_shopping_list(connection, ids, ids['week'])
        _seed_revision(connection, ids, shopping_list_id)
        lists_before = connection.execute(text(
            'SELECT to_jsonb(l)::text FROM cafeteria.shopping_lists l ORDER BY id'
        )).all()

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
        lists_after = connection.execute(text(
            'SELECT to_jsonb(l)::text FROM cafeteria.shopping_lists l ORDER BY id'
        )).all()
    assert copied == 1
    assert lists_after == lists_before


def test_shopping_lists_manual_items_and_line_status_allow_app_crud(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)

    with app_engine.begin() as connection:
        list_id = connection.execute(text("""INSERT INTO cafeteria.shopping_lists(
            location_id,menu_week_id,title,note,created_by,updated_by)
            VALUES(:location,:week,'Wocheneinkauf','Bitte Bio wenn möglich',:actor,:actor)
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

    # DELETE ist für cafeteria_app gegrantet (S3), aber die append-only Revision (nie
    # löschbar) hält shopping_list_revisions_shopping_list_id_fkey (RESTRICT) davor:
    # eine Liste mit mindestens einer Berechnungsrevision kann nie gelöscht werden.
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


def test_shopping_list_revision_immutable_trigger_rejects_owner_update_delete_and_truncate(seeded_pg16):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        list_id = _seed_shopping_list(connection, ids)
        revision_id = _seed_revision(connection, ids, list_id)

    for statement in (
        "UPDATE cafeteria.shopping_list_revisions SET policy='prepared' WHERE id=:id",
        'DELETE FROM cafeteria.shopping_list_revisions WHERE id=:id',
        # line_status referenziert die Revisionen; ohne Mit-Truncate bräche TRUNCATE schon an
        # der FK-Prüfung (0A000) ab, bevor der BEFORE-TRUNCATE-Trigger feuert.
        'TRUNCATE cafeteria.shopping_list_revisions, cafeteria.shopping_list_line_status',
    ):
        with pytest.raises(DBAPIError) as error:
            with seeded_pg16.begin() as connection:
                connection.execute(text(statement), {'id': revision_id})
        assert error.value.orig.sqlstate == '55000', statement
        assert error.value.orig.diag.message_primary == \
            'Einkaufslisten-Berechnungsrevisionen sind unveränderlich.', statement
    with seeded_pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.shopping_list_revisions WHERE id=:id'
        ), {'id': revision_id}).scalar_one() == 1


def test_shopping_list_scope_is_immutable_and_line_status_revision_is_list_scoped(seeded_pg16, app_engine):  # noqa: F811
    ids = _shopping_context(seeded_pg16)

    for engine in (app_engine, seeded_pg16):
        with pytest.raises(DBAPIError) as error:
            with engine.begin() as connection:
                connection.execute(text(
                    'UPDATE cafeteria.shopping_lists SET location_id=:other_location WHERE id=:list'
                ), ids)
        assert error.value.orig.sqlstate == '55000'
        assert error.value.orig.diag.message_primary == \
            'Der Standort einer Einkaufsliste ist unveränderlich.'
    with app_engine.begin() as connection:
        connection.execute(text("""UPDATE cafeteria.shopping_lists
            SET location_id=location_id,title='Umbenannt',updated_by=:actor WHERE id=:list"""), ids)
    with seeded_pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT location_id,title,row_version FROM cafeteria.shopping_lists WHERE id=:list'
        ), ids).one() == (ids['location'], 'Umbenannt', 2)

        # UNIQUE (id, shopping_list_id) ist nie als erste Verletzung erreichbar (PK-Index zuerst,
        # Revisionen unveränderlich); belegt wird, dass der Scope-FK genau darauf aufsetzt.
        assert connection.execute(text("""SELECT referenced.conname
            FROM pg_constraint fk
            JOIN pg_constraint referenced
              ON referenced.conindid=fk.conindid AND referenced.conrelid=fk.confrelid
            WHERE fk.conrelid='cafeteria.shopping_list_line_status'::regclass
              AND fk.conname='shopping_list_line_status_revision_id_fkey'""")).scalar_one() == \
            'shopping_list_revisions_id_shopping_list_id_key'

    base = {
        'shopping_list_id': ids['list'], 'line_key': 'food:salt:g',
        'revision_id': ids['revision'], 'checked_quantity': '1.000000 g', 'checked_by': ids['actor'],
    }
    cases = [
        (
            label, _insert_statement('shopping_list_line_status', values), values,
            '23503', 'shopping_list_line_status_revision_id_fkey',
        )
        for label, values in (
            ('Revision einer anderen Liste', {**base, 'revision_id': ids['other_revision']}),
            ('Liste passt nicht zur Revision', {**base, 'shopping_list_id': ids['other_list']}),
        )
    ]
    assert _rejections(app_engine, cases) == []


def test_shopping_lists_constraint_negatives_by_name(seeded_pg16, app_engine):  # noqa: F811
    ids = _shopping_context(seeded_pg16)
    table = 'shopping_lists'
    base = {
        'location_id': ids['location'], 'title': 'Liste',
        'created_by': ids['actor'], 'updated_by': ids['actor'],
    }
    title = 'shopping_lists_title_check'
    note = 'shopping_lists_note_check'
    specs = [
        ('PK doppelt', {**base, 'id': ids['list']}, True, '23505', 'shopping_lists_pkey'),
        ('public_id doppelt', {**base, 'public_id': ids['list_public_id']}, False, '23505',
         'shopping_lists_public_id_key'),
        ('Standort unbekannt', {**base, 'location_id': -1}, False, '23503', 'shopping_lists_location_id_fkey'),
        ('Woche unbekannt', {**base, 'menu_week_id': -1}, False, '23503', 'shopping_lists_menu_week_id_fkey'),
        ('created_by unbekannt', {**base, 'created_by': -1}, False, '23503', 'shopping_lists_created_by_fkey'),
        ('updated_by unbekannt', {**base, 'updated_by': -1}, False, '23503', 'shopping_lists_updated_by_fkey'),
        ('Titel leer', {**base, 'title': ''}, False, '23514', title),
        ('Titel nur Leerzeichen', {**base, 'title': '   '}, False, '23514', title),
        ('Titel führendes Leerzeichen', {**base, 'title': ' Liste'}, False, '23514', title),
        ('Titel folgendes Leerzeichen', {**base, 'title': 'Liste '}, False, '23514', title),
        ('Titel führender Tab', {**base, 'title': '\tListe'}, False, '23514', title),
        ('Titel folgender Zeilenumbruch', {**base, 'title': 'Liste\n'}, False, '23514', title),
        ('Titel folgendes CR', {**base, 'title': 'Liste\r'}, False, '23514', title),
        ('Titel nur Tab/Zeilenumbruch', {**base, 'title': '\t\r\n'}, False, '23514', title),
        ('Titel 121 Zeichen', {**base, 'title': 'T' * 121}, False, '23514', title),
        ('Note führendes Leerzeichen', {**base, 'note': ' Notiz'}, False, '23514', note),
        ('Note folgender Tab', {**base, 'note': 'Notiz\t'}, False, '23514', note),
        ('Note folgendes CRLF', {**base, 'note': 'Notiz\r\n'}, False, '23514', note),
        ('Note 2001 Zeichen', {**base, 'note': 'N' * 2001}, False, '23514', note),
        ('row_version 0', {**base, 'row_version': 0}, False, '23514', 'shopping_lists_row_version_check'),
        ('row_version negativ', {**base, 'row_version': -1}, False, '23514', 'shopping_lists_row_version_check'),
    ]
    cases = [
        (label, _insert_statement(table, values, overriding=overriding), values, sqlstate, constraint)
        for label, values, overriding, sqlstate, constraint in specs
    ]
    assert _rejections(app_engine, cases) == []

    with app_engine.begin() as connection:
        for values in (
            {**base, 'title': 'T' * 120, 'note': 'N' * 2000, 'menu_week_id': ids['week']},
            {**base, 'title': 'A', 'note': None},
            {**base, 'title': 'Wochen einkauf', 'note': 'Zeile 1\nZeile 2'},
        ):
            connection.execute(text(_insert_statement(table, values)), values)


def test_shopping_list_revisions_constraint_negatives_by_name(seeded_pg16, app_engine):  # noqa: F811
    ids = _shopping_context(seeded_pg16)
    table = 'shopping_list_revisions'
    valid_snapshot = json.dumps({'inputs': [], 'result': {'lines': []}})
    base = {
        'shopping_list_id': ids['list'], 'revision_number': 2, 'policy': 'leaf',
        'snapshot_json': valid_snapshot, 'computed_by': ids['actor'],
    }
    expressions = {'snapshot_json': 'CAST(:snapshot_json AS jsonb)', 'content_hash_sha256': _REVISION_HASH}
    snapshot = 'shopping_list_revisions_snapshot_json_check'
    specs: list[tuple[str, dict[str, Any], bool, dict[str, str], str, str]] = [
        ('PK doppelt', {**base, 'id': ids['revision'], 'revision_number': 5}, True, expressions,
         '23505', 'shopping_list_revisions_pkey'),
        ('public_id doppelt', {**base, 'public_id': ids['revision_public_id']}, False, expressions,
         '23505', 'shopping_list_revisions_public_id_key'),
        ('(Liste, revision_number) doppelt', {**base, 'revision_number': 1}, False, expressions,
         '23505', 'shopping_list_revisions_shopping_list_id_revision_number_key'),
        ('Liste unbekannt', {**base, 'shopping_list_id': -1}, False, expressions,
         '23503', 'shopping_list_revisions_shopping_list_id_fkey'),
        ('computed_by unbekannt', {**base, 'computed_by': -1}, False, expressions,
         '23503', 'shopping_list_revisions_computed_by_fkey'),
        ('revision_number 0', {**base, 'revision_number': 0}, False, expressions,
         '23514', 'shopping_list_revisions_revision_number_check'),
        ('revision_number negativ', {**base, 'revision_number': -1}, False, expressions,
         '23514', 'shopping_list_revisions_revision_number_check'),
        ('Policy fremd', {**base, 'policy': 'unknown'}, False, expressions,
         '23514', 'shopping_list_revisions_policy_check'),
        ('Policy Grossschreibung', {**base, 'policy': 'Leaf'}, False, expressions,
         '23514', 'shopping_list_revisions_policy_check'),
        *(
            (f'Snapshot {raw}', {**base, 'snapshot_json': raw}, False, expressions, '23514', snapshot)
            for raw in (
                '{}', '[]', '"inputs"', '["inputs", "result"]', '{"inputs": []}', '{"result": {}}',
                '{"inputs": {}, "result": {}}', '{"inputs": [], "result": []}',
                '{"inputs": null, "result": {}}', '{"inputs": [], "result": null}',
            )
        ),
        ('Hash falsch', base, False, {**expressions, 'content_hash_sha256': "repeat('0',64)"},
         '23514', 'shopping_list_revisions_content_hash_sha256_check'),
        # Hash über den Rohtext statt über die kanonische jsonb-Textform ({"inputs": [], ...}).
        ('Hash über nicht kanonischen Text',
         {**base, 'snapshot_json': '{"inputs":[],"result":{}}'}, False,
         {**expressions,
          'content_hash_sha256': """encode(pg_catalog.sha256(convert_to('{"inputs":[],"result":{}}','UTF8')),'hex')"""},
         '23514', 'shopping_list_revisions_content_hash_sha256_check'),
    ]
    cases = [
        (
            label, _insert_statement(table, values, overriding=overriding, expressions=rendered),
            values, sqlstate, constraint,
        )
        for label, values, overriding, rendered, sqlstate, constraint in specs
    ]
    assert _rejections(app_engine, cases) == []

    accepted = {
        **base,
        'snapshot_json': json.dumps({'inputs': [{'revision': 'r1'}], 'result': {'lines': [], 'incomplete': []}}),
        'policy': 'prepared',
    }
    with app_engine.begin() as connection:
        connection.execute(text(_insert_statement(table, accepted, expressions=expressions)), accepted)


def test_shopping_list_manual_items_constraint_negatives_by_name(seeded_pg16, app_engine):  # noqa: F811
    ids = _shopping_context(seeded_pg16)
    table = 'shopping_list_manual_items'
    base = {
        'shopping_list_id': ids['list'], 'sort_order': 2, 'item_text': 'Mehl',
        'created_by': ids['actor'], 'updated_by': ids['actor'],
    }
    with_unit = {**base, 'unit_id': ids['unit']}
    item_text = 'shopping_list_manual_items_item_text_check'
    quantity = 'shopping_list_manual_items_quantity_check'
    pairing = 'shopping_list_manual_items_quantity_unit_check'
    specs = [
        ('PK doppelt', {**base, 'id': ids['manual_item']}, True, '23505', 'shopping_list_manual_items_pkey'),
        ('public_id doppelt', {**base, 'public_id': ids['manual_item_public_id']}, False, '23505',
         'shopping_list_manual_items_public_id_key'),
        ('sort_order doppelt', {**base, 'sort_order': 1}, False, '23505',
         'shopping_list_manual_items_shopping_list_id_sort_order_key'),
        ('Liste unbekannt', {**base, 'shopping_list_id': -1}, False, '23503',
         'shopping_list_manual_items_shopping_list_id_fkey'),
        ('Einheit unbekannt', {**base, 'quantity': Decimal('2'), 'unit_id': -1}, False, '23503',
         'shopping_list_manual_items_unit_id_fkey'),
        ('created_by unbekannt', {**base, 'created_by': -1}, False, '23503',
         'shopping_list_manual_items_created_by_fkey'),
        ('updated_by unbekannt', {**base, 'updated_by': -1}, False, '23503',
         'shopping_list_manual_items_updated_by_fkey'),
        ('sort_order 0', {**base, 'sort_order': 0}, False, '23514', 'shopping_list_manual_items_sort_order_check'),
        ('sort_order negativ', {**base, 'sort_order': -1}, False, '23514',
         'shopping_list_manual_items_sort_order_check'),
        ('Text leer', {**base, 'item_text': ''}, False, '23514', item_text),
        ('Text nur Leerzeichen', {**base, 'item_text': ' '}, False, '23514', item_text),
        ('Text führendes Leerzeichen', {**base, 'item_text': ' Mehl'}, False, '23514', item_text),
        ('Text folgender Tab', {**base, 'item_text': 'Mehl\t'}, False, '23514', item_text),
        ('Text folgendes CRLF', {**base, 'item_text': 'Mehl\r\n'}, False, '23514', item_text),
        ('Text führender Zeilenumbruch', {**base, 'item_text': '\nMehl'}, False, '23514', item_text),
        ('Text 201 Zeichen', {**base, 'item_text': 'M' * 201}, False, '23514', item_text),
        ('Menge 0 mit Einheit', {**with_unit, 'quantity': Decimal('0')}, False, '23514', quantity),
        ('Menge negativ mit Einheit', {**with_unit, 'quantity': Decimal('-1')}, False, '23514', quantity),
        ('Menge rundet auf 0', {**with_unit, 'quantity': Decimal('0.0000001')}, False, '23514', quantity),
        ('Menge ohne Einheit', {**base, 'quantity': Decimal('2')}, False, '23514', pairing),
        ('Einheit ohne Menge', with_unit, False, '23514', pairing),
        ('row_version 0', {**base, 'row_version': 0}, False, '23514',
         'shopping_list_manual_items_row_version_check'),
    ]
    cases = [
        (label, _insert_statement(table, values, overriding=overriding), values, sqlstate, constraint)
        for label, values, overriding, sqlstate, constraint in specs
    ]
    assert _rejections(app_engine, cases) == []

    accepted = {**with_unit, 'item_text': 'M' * 200, 'quantity': Decimal('0.000001')}
    with app_engine.begin() as connection:
        connection.execute(text(_insert_statement(table, accepted)), accepted)
        stored = connection.execute(text("""SELECT quantity,unit_id FROM cafeteria.shopping_list_manual_items
            WHERE shopping_list_id=:list AND sort_order=2"""), ids).one()
    assert stored == (Decimal('0.000001'), ids['unit'])


def test_shopping_list_line_status_constraint_negatives_by_name(seeded_pg16, app_engine):  # noqa: F811
    ids = _shopping_context(seeded_pg16)
    table = 'shopping_list_line_status'
    base = {
        'shopping_list_id': ids['list'], 'line_key': 'food:salt:g', 'revision_id': ids['revision'],
        'checked_quantity': '1.000000 g', 'checked_by': ids['actor'],
    }
    line_key = 'shopping_list_line_status_line_key_check'
    checked_quantity = 'shopping_list_line_status_checked_quantity_check'
    revision_fk = 'shopping_list_line_status_revision_id_fkey'
    specs = [
        ('PK doppelt', {**base, 'line_key': 'food:milk:l'}, '23505', 'shopping_list_line_status_pkey'),
        ('Revision unbekannt', {**base, 'revision_id': -1}, '23503', revision_fk),
        ('Liste unbekannt', {**base, 'shopping_list_id': -1}, '23503', revision_fk),
        ('checked_by unbekannt', {**base, 'checked_by': -1}, '23503', 'shopping_list_line_status_checked_by_fkey'),
        ('line_key leer', {**base, 'line_key': ''}, '23514', line_key),
        ('line_key nur Leerzeichen', {**base, 'line_key': '  '}, '23514', line_key),
        ('line_key führender Tab', {**base, 'line_key': '\tfood:salt:g'}, '23514', line_key),
        ('line_key folgender Zeilenumbruch', {**base, 'line_key': 'food:salt:g\n'}, '23514', line_key),
        ('line_key 301 Zeichen', {**base, 'line_key': 'k' * 301}, '23514', line_key),
        ('Menge leer', {**base, 'checked_quantity': ''}, '23514', checked_quantity),
        ('Menge führendes Leerzeichen', {**base, 'checked_quantity': ' 1 g'}, '23514', checked_quantity),
        ('Menge folgendes CR', {**base, 'checked_quantity': '1 g\r'}, '23514', checked_quantity),
        ('Menge 101 Zeichen', {**base, 'checked_quantity': 'q' * 101}, '23514', checked_quantity),
    ]
    cases = [
        (label, _insert_statement(table, values), values, sqlstate, constraint)
        for label, values, sqlstate, constraint in specs
    ]
    assert _rejections(app_engine, cases) == []

    accepted = {**base, 'line_key': 'k' * 300, 'checked_quantity': 'q' * 100}
    with app_engine.begin() as connection:
        connection.execute(text(_insert_statement(table, accepted)), accepted)


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
    assert status['schema_version'] == status['live_schema_version'] == 41
    assert status['baseline_migration_equivalent'] is True
    migration_sha = hashlib.sha256(
        (SCHEMA.parent / 'migrations' / '0031_v33_to_v34.sql').read_bytes()
    ).hexdigest()
    assert status['migration_checksums']['0031_v33_to_v34.sql'] == migration_sha
    assert migration_sha == validate_package.MIGRATION_CHECKSUMS['0031_v33_to_v34.sql']


def test_validate_schema_live_guard_flags_disabled_shopping_trigger(installed_pg16):  # noqa: F811
    """Ein deaktivierter Schutz-Trigger auf einer Schema-34-Tabelle muss live als Fehler mit Triggername gemeldet werden."""
    table, trigger = 'shopping_lists', 'trg_shopping_lists_version'
    with installed_pg16.begin() as connection:
        connection.execute(text(f'ALTER TABLE cafeteria.{table} DISABLE TRIGGER {trigger}'))
    try:
        with installed_pg16.connect() as connection:
            mismatches = validate_schema.shopping_live_guard_mismatches(connection)
        assert any(item['object'] == f'trigger_enabled:{table}.{trigger}' for item in mismatches), mismatches
    finally:
        with installed_pg16.begin() as connection:
            connection.execute(text(f'ALTER TABLE cafeteria.{table} ENABLE TRIGGER {trigger}'))
    with installed_pg16.connect() as connection:
        assert validate_schema.shopping_live_guard_mismatches(connection) == []


def test_validate_schema_live_guard_flags_extra_shopping_column_acl(installed_pg16):  # noqa: F811
    """Ein zusätzliches Spaltenrecht auf einer Schema-34-Tabelle muss live als Fehler gemeldet werden."""
    with installed_pg16.begin() as connection:
        connection.execute(text('GRANT UPDATE (title) ON cafeteria.shopping_lists TO cafeteria_app'))
    try:
        with installed_pg16.connect() as connection:
            mismatches = validate_schema.shopping_live_guard_mismatches(connection)
        assert any(item['object'] == 'column_acl:shopping_lists.title' for item in mismatches), mismatches
    finally:
        with installed_pg16.begin() as connection:
            connection.execute(text('REVOKE UPDATE (title) ON cafeteria.shopping_lists FROM cafeteria_app'))
    with installed_pg16.connect() as connection:
        assert validate_schema.shopping_live_guard_mismatches(connection) == []


def test_validate_schema_live_guard_clean_state_is_empty(installed_pg16):  # noqa: F811
    """Ohne Manipulation meldet die Live-Prüfung für Trigger/ACL der Schema-34-Tabellen keine Abweichung."""
    with installed_pg16.connect() as connection:
        assert validate_schema.shopping_live_guard_mismatches(connection) == []


def test_validate_schema_disabled_trigger_flags_recipe_revisions_immutable(installed_pg16):  # noqa: F811
    """Ein deaktivierter Schutz-Trigger muss live als Fehler mit Triggername gemeldet werden."""
    table, trigger = 'recipe_revisions', 'recipe_revisions_immutable'
    with installed_pg16.begin() as connection:
        connection.execute(text(f'ALTER TABLE cafeteria.{table} DISABLE TRIGGER {trigger}'))
    try:
        with installed_pg16.connect() as connection:
            mismatches = validate_schema.disabled_trigger_mismatches(connection)
        assert any(item['object'] == f'trigger_enabled:{table}.{trigger}' for item in mismatches), mismatches
    finally:
        with installed_pg16.begin() as connection:
            connection.execute(text(f'ALTER TABLE cafeteria.{table} ENABLE TRIGGER {trigger}'))
    with installed_pg16.connect() as connection:
        assert validate_schema.disabled_trigger_mismatches(connection) == []


def test_validate_schema_disabled_trigger_clean_state_is_empty(installed_pg16):  # noqa: F811
    """Ohne Manipulation meldet die Live-Prüfung für alle Schutz-Trigger keine Abweichung."""
    with installed_pg16.connect() as connection:
        assert validate_schema.disabled_trigger_mismatches(connection) == []
