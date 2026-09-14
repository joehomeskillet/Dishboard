"""Schema32 -> 33 target portions migration and exact database contract."""
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
from test_rec_import_commit_migration_db import rows_and_sequences

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


_VP_SPEC = importlib.util.spec_from_file_location(
    'rec_plan_portions_package_validator', ROOT / 'tools' / 'validate_package.py'
)
assert _VP_SPEC is not None and _VP_SPEC.loader is not None
validate_package = importlib.util.module_from_spec(_VP_SPEC)
_VP_SPEC.loader.exec_module(validate_package)


TARGET_CHECK = 'menu_item_components_target_quantity_check'
TARGET_FK = 'menu_item_components_target_quantity_unit_id_fkey'
TARGET_INDEX = 'menu_item_components_target_quantity_unit_idx'


def _target_contract(connection):
    return (
        connection.execute(text("""SELECT column_name,data_type,udt_name,is_nullable,
            numeric_precision,numeric_scale,ordinal_position FROM information_schema.columns
            WHERE table_schema='cafeteria' AND table_name='menu_item_components'
            AND column_name IN ('target_quantity','target_quantity_unit_id')
            ORDER BY ordinal_position""")).all(),
        connection.execute(text("""SELECT conname,contype,pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='cafeteria.menu_item_components'::regclass
            AND conname IN (:check_name,:fk_name) ORDER BY conname"""), {
                'check_name': TARGET_CHECK,
                'fk_name': TARGET_FK,
            }).all(),
        connection.execute(text("""SELECT indexname,indexdef FROM pg_indexes
            WHERE schemaname='cafeteria' AND tablename='menu_item_components'
            AND indexname=:index_name"""), {'index_name': TARGET_INDEX}).all(),
        connection.execute(text("""SELECT COALESCE(role.rolname,'PUBLIC'),acl.privilege_type,
            acl.is_grantable FROM pg_class table_class
            CROSS JOIN LATERAL aclexplode(COALESCE(
                table_class.relacl,acldefault('r',table_class.relowner)
            )) acl LEFT JOIN pg_roles role ON role.oid=acl.grantee
            WHERE table_class.oid='cafeteria.menu_item_components'::regclass
            ORDER BY 1,2,3""")).all(),
        connection.execute(text("""SELECT attribute.attname,COALESCE(role.rolname,'PUBLIC'),
            acl.privilege_type,acl.is_grantable FROM pg_attribute attribute
            CROSS JOIN LATERAL aclexplode(attribute.attacl) acl
            LEFT JOIN pg_roles role ON role.oid=acl.grantee
            WHERE attribute.attrelid='cafeteria.menu_item_components'::regclass
            AND attribute.attnum>0 AND NOT attribute.attisdropped
            AND attribute.attacl IS NOT NULL ORDER BY 1,2,3,4""")).all(),
    )


def _app_surface(connection):
    tables = connection.execute(text("""SELECT tablename FROM pg_tables
        WHERE schemaname='cafeteria' ORDER BY tablename""")).scalars().all()
    executable = connection.execute(text("""SELECT p.oid::regprocedure::text
        FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace
        AND has_function_privilege('cafeteria_app',p.oid,'EXECUTE')
        ORDER BY p.oid::regprocedure::text""")).scalars().all()
    
    # P3-4d: Tabellenrechte aller drei App-Rollen
    table_rights = {}
    for role in ('cafeteria_app', 'cafeteria_backup', 'cafeteria_auth_issuer'):
        rights = connection.execute(text("""
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema='cafeteria' AND grantee=:role
            ORDER BY table_name, privilege_type
        """), {'role': role}).all()
        table_rights[role] = rights
        
    return tables, executable, table_rights


def _insert_recipe_revision(connection, ids):
    recipe_id = connection.execute(text("""INSERT INTO cafeteria.recipes(
        location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
        VALUES(:location,:actor,:actor,'Portionstest',4,
        (SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'),'manual')
        RETURNING id"""), ids).scalar_one()
    return connection.execute(text("""INSERT INTO cafeteria.recipe_revisions(
        location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
        VALUES(:location,:recipe,1,'{}',
        encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor) RETURNING id"""), {
            **ids,
            'recipe': recipe_id,
        }).scalar_one()


def test_v32_upgrade_preserves_rows_publication_hash_acl_and_fresh_contract(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    # Seit 0031 ist 0030 nicht mehr das letzte Element im Gesamtplan (Schema34
    # Einkaufslisten); Version 33 bleibt hier ueber ihre eigene Nummer gesucht statt
    # ueber plan[-1] (Muster test_menu_accompaniment_migration_db.py).
    mig33 = next(migration for migration in plan if migration.version == 33)
    assert (mig33.version, mig33.path.name) == (33, '0030_v32_to_v33.sql')
    for migration in plan:
        if migration.version <= 32:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    # Seit 0031 grantet permissions.sql auch auf die erst mit Schema34 entstehenden
    # shopping_*-Tabellen; vor der eigenen Migration (hier nur bis 32) muss dieser Block
    # entfernt werden, sonst schlaegt das Skript an den fehlenden Tabellen fehl.
    permissions_text = PERMISSIONS.read_text(encoding='utf-8')
    begin_marker = '-- Schema34 shopping list grants begin.\n'
    end_marker = '-- Schema34 shopping list grants end.\n\n'
    prefix, rest = permissions_text.split(begin_marker, 1)
    permissions_v32 = prefix + rest.split(end_marker, 1)[1]
    permissions_scratch = Path(os.environ.get('CLAUDE_SANDBOX_SCRATCHPAD', '/tmp')) / \
        'permissions_v32_without_shopping.sql'
    permissions_scratch.parent.mkdir(parents=True, exist_ok=True)
    permissions_scratch.write_text(permissions_v32, encoding='utf-8')
    database._execute_script(pg16, str(permissions_scratch))

    ids = _seed_scope_probe(pg16)
    actor = make_actor(pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    week = _v19_week(pg16, _actor_id(pg16))
    snapshot = _v19_snapshot(pg16, 'CAF-2026-KW36-PORTIONS-R1')
    with pg16.begin() as connection:
        revision_id = _insert_recipe_revision(connection, ids)
        connection.execute(text("""INSERT INTO cafeteria.menu_item_components(
            menu_item_id,sort_order,component_text,recipe_revision_id)
            VALUES(:item,1,'Gebunden',:revision),(:item,2,'Ohne Rezept',NULL)"""), {
                **ids,
                'revision': revision_id,
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
        components_before = connection.execute(text("""SELECT to_jsonb(link)::text
            FROM cafeteria.menu_item_components link ORDER BY menu_item_id,sort_order""")).all()
        
        publication_before = connection.execute(text("""SELECT to_jsonb(r)::text
            FROM cafeteria.publication_revisions r ORDER BY id""")).all()
        active_pub_before = connection.execute(text("""SELECT to_jsonb(a)::text
            FROM cafeteria.active_publications a ORDER BY revision_db_id""")).all()
            
        ledger_before = connection.execute(text("""SELECT version,name,checksum_sha256,
            application_version FROM cafeteria.schema_migrations ORDER BY version""")).all()
        surface_before = _app_surface(connection)
        
        target_contract_before = _target_contract(connection)

    rows_and_seqs_before = rows_and_sequences(pg16)
    assert database.run_migrations(pg16, SCHEMA) == plan
    with pg16.connect() as connection:
        components_after = connection.execute(text("""SELECT
            (to_jsonb(link)-'target_quantity'-'target_quantity_unit_id')::text
            FROM cafeteria.menu_item_components link ORDER BY menu_item_id,sort_order""")).all()
        assert components_after == components_before
        
        publication_after = connection.execute(text("""SELECT to_jsonb(r)::text
            FROM cafeteria.publication_revisions r ORDER BY id""")).all()
        active_pub_after = connection.execute(text("""SELECT to_jsonb(a)::text
            FROM cafeteria.active_publications a ORDER BY revision_db_id""")).all()
        assert publication_after == publication_before
        assert active_pub_after == active_pub_before
            
        assert connection.execute(text("""SELECT version,name,checksum_sha256,
            application_version FROM cafeteria.schema_migrations
            WHERE version<=32 ORDER BY version""")).all() == ledger_before
        # Seit 0031 laeuft run_migrations() hier bis Schema34 (Einkaufslisten) durch;
        # max(version) und die App-Oberflaeche schliessen daher den neuen Stand mit ein.
        assert connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one() == 34

        mig33 = connection.execute(text("""SELECT name,checksum_sha256,application_version
            FROM cafeteria.schema_migrations WHERE version=33""")).one()
        assert mig33[0] == '0030_v32_to_v33.sql'
        expected_sha = hashlib.sha256((SCHEMA.parent / 'migrations' / '0030_v32_to_v33.sql').read_bytes()).hexdigest()
        assert mig33[1] == expected_sha
        assert mig33[1] == validate_package.MIGRATION_CHECKSUMS['0030_v32_to_v33.sql']

        after_surface = _app_surface(connection)
        # existing_tables muss auch Views (z. B. active_publications) abdecken: pg_tables
        # (surface_before[0]) kennt nur echte Tabellen, role_table_grants aber auch Views.
        existing_tables = set(surface_before[0]) | {
            row[0] for rights in surface_before[2].values() for row in rights
        }
        filtered_after_surface = (
            [name for name in after_surface[0] if name in existing_tables],
            after_surface[1],
            {
                role: [row for row in rights if row[0] in existing_tables]
                for role, rights in after_surface[2].items()
            },
        )
        assert filtered_after_surface == surface_before
        migrated_contract = _target_contract(connection)
        
        # Check ACL match
        assert migrated_contract[3] == target_contract_before[3]  # table acl
        assert migrated_contract[4] == target_contract_before[4]  # column acl
        
        # Seit 0031 laeuft run_migrations() hier bis Schema34 (Einkaufslisten) durch;
        # nur Tabellen/Sequenzen vergleichen, die bereits vor dieser Migration existierten
        # (Muster: bestehende Ausnahme fuer menu_item_components/schema_migrations erweitert).
        rows_and_seqs_after = rows_and_sequences(pg16)
        before_table_names = set(rows_and_seqs_before[0])
        assert {k: v for k, v in rows_and_seqs_after[0].items() if k in before_table_names and k not in ('menu_item_components', 'schema_migrations')} == {k: v for k, v in rows_and_seqs_before[0].items() if k not in ('menu_item_components', 'schema_migrations')}
        before_seq_names = {name for name, _ in rows_and_seqs_before[1]}
        assert [pair for pair in rows_and_seqs_after[1] if pair[0] in before_seq_names] == rows_and_seqs_before[1]
        
        # Verify existing rows have both new cols NULL
        new_cols = connection.execute(text("""SELECT target_quantity, target_quantity_unit_id 
            FROM cafeteria.menu_item_components""")).all()
        for row in new_cols:
            assert row[0] is None and row[1] is None

    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert _target_contract(connection) == migrated_contract


@pytest.mark.parametrize(
    ('quantity', 'unit', 'revision'),
    [
        (Decimal('2.500000'), None, 'bound'),
        (None, 'PORTION', 'bound'),
        (Decimal('0.000000'), 'PORTION', 'bound'),
        (Decimal('-1.000000'), 'PORTION', 'bound'),
        (Decimal('2.500000'), 'PORTION', None),
    ],
)
def test_target_quantity_check_rejects_incomplete_nonpositive_or_unbound_values(
    seeded_pg16,  # noqa: F811
    app_engine,  # noqa: F811
    quantity,
    unit,
    revision,
):
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        revision_id = _insert_recipe_revision(connection, ids)
        unit_id = connection.execute(text(
            "SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'"
        )).scalar_one()
    parameters = {
        'item': ids['item'],
        'quantity': quantity,
        'unit': unit_id if unit else None,
        'revision': revision_id if revision else None,
    }
    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.menu_item_components(
                menu_item_id,sort_order,component_text,recipe_revision_id,
                target_quantity,target_quantity_unit_id)
                VALUES(:item,1,'Ungültig',:revision,:quantity,:unit)"""), parameters)
    assert error.value.orig.sqlstate == '23514'
    assert error.value.orig.diag.constraint_name == TARGET_CHECK


def test_target_quantity_exact_fk_null_pair(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        revision_id = _insert_recipe_revision(connection, ids)
        unit_id = connection.execute(text(
            "SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'"
        )).scalar_one()

    with app_engine.begin() as connection:
        connection.execute(text("""INSERT INTO cafeteria.menu_item_components(
            menu_item_id,sort_order,component_text,recipe_revision_id)
            VALUES(:item,1,'Alter Writer ohne neue Spalten',NULL)"""), ids)
        assert connection.execute(text("""SELECT menu_item_id,sort_order,component_text,
            recipe_revision_id FROM cafeteria.menu_item_components
            WHERE menu_item_id=:item AND sort_order=1"""), ids).one() == (
                ids['item'], 1, 'Alter Writer ohne neue Spalten', None,
            )
        connection.execute(text("""INSERT INTO cafeteria.menu_item_components(
            menu_item_id,sort_order,component_text,recipe_revision_id,
            target_quantity,target_quantity_unit_id)
            VALUES(:item,2,'Exakt',:revision,2.500000,:unit)"""), {
                **ids,
                'revision': revision_id,
                'unit': unit_id,
            })
        quantity = connection.execute(text("""SELECT target_quantity
            FROM cafeteria.menu_item_components WHERE menu_item_id=:item AND sort_order=2"""),
            ids).scalar_one()
        assert quantity == Decimal('2.500000')
        assert format(quantity, 'f') == '2.500000'

    with pytest.raises(DBAPIError) as error:
        with app_engine.begin() as connection:
            connection.execute(text("""INSERT INTO cafeteria.menu_item_components(
                menu_item_id,sort_order,component_text,recipe_revision_id,
                target_quantity,target_quantity_unit_id)
                VALUES(:item,3,'Unbekannte Einheit',:revision,2.500000,-1)"""), {
                    **ids,
                    'revision': revision_id,
                })
    assert error.value.orig.sqlstate == '23503'
    assert error.value.orig.diag.constraint_name == TARGET_FK


def test_v33_store_and_copy_paths_preserve_target_quantity_when_absent_from_assignment(
    seeded_pg16, app_engine,  # noqa: F811
):
    """PP-STORE-Beleg: Speicher- und Kopierpfad kennen target_quantity jetzt und erhalten sie.

    Vor PP-STORE (siehe git-Historie dieses Tests) ersetzten ``replace_component_links``
    (component_assignment_store.py) und ``copy_previous_week`` (workflow_copy_store.py)
    Komponentenzeilen ueber DELETE + INSERT mit einer expliziten Spaltenliste ohne
    target_quantity/target_quantity_unit_id und verwarfen eine bestehende Zielmenge dabei
    still (Rollback-Beleg fuer den 0030-Kopf). Nach PP-STORE gilt die im Interface-Contract
    festgelegte Praesenzregel: fehlen beide Schluessel (``target_quantity``,
    ``target_quantity_unit_code``) im Assignment, bleibt eine bereits gespeicherte Zielmenge
    an der UNVERAENDERTEN Rezeptbindung erhalten (Store und Kopie). Der Rollback-Kopf in
    0030_v32_to_v33.sql bleibt unveraendert: die Migration selbst wird hier nicht angefasst,
    dieser Test dokumentiert nur den jetzigen App-Code-Stand.
    """
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    scope = AdminScope(ids['actor'], ids['location'], 'patient', ids['authz'])
    with seeded_pg16.begin() as connection:
        # master_location() requires exactly one active location; _seed_scope_probe leaves
        # other_location active too.
        connection.execute(text(
            'UPDATE cafeteria.locations SET active=false WHERE id=:other_location'
        ), ids)
        revision_id = _insert_recipe_revision(connection, ids)
        revision_public_id = str(connection.execute(text(
            'SELECT public_id FROM cafeteria.recipe_revisions WHERE id=:revision'
        ), {'revision': revision_id}).scalar_one())
        unit_id = connection.execute(text(
            "SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'"
        )).scalar_one()
        item_version = connection.execute(text(
            'SELECT row_version FROM cafeteria.menu_items WHERE id=:item'
        ), ids).scalar_one()

    binding_assignment = {
        'component_public_id': None,
        'component_text': 'Gebunden',
        'recipe_revision_public_id': revision_public_id,
    }
    # Real save path: binds the component via the current app code. The assignment
    # carries neither target_quantity nor target_quantity_unit_code (both keys absent).
    item_version = replace_component_links(
        app_engine, scope, ids['item'], [binding_assignment], item_version,
    )

    # Store a target quantity directly on the row (as the store's own write would after
    # a save that DOES carry the target keys), as only the owner/test engine does here.
    with seeded_pg16.begin() as connection:
        connection.execute(text("""UPDATE cafeteria.menu_item_components
            SET target_quantity=2.500000, target_quantity_unit_id=:unit
            WHERE menu_item_id=:item"""), {**ids, 'unit': unit_id})

    # Real save path again with the identical assignment (still no target keys): PP-STORE's
    # presence rule preserves the stored quantity because the bound revision is unchanged.
    item_version = replace_component_links(
        app_engine, scope, ids['item'], [binding_assignment], item_version,
    )
    with seeded_pg16.connect() as connection:
        saved = connection.execute(text("""SELECT recipe_revision_id,target_quantity,
            target_quantity_unit_id FROM cafeteria.menu_item_components
            WHERE menu_item_id=:item"""), ids).one()
    assert saved == (revision_id, Decimal('2.500000'), unit_id)

    # Re-apply a target quantity (idempotent, already set) and prove the real copy path
    # carries it over verbatim together with the bound revision.
    with seeded_pg16.begin() as connection:
        connection.execute(text("""UPDATE cafeteria.menu_item_components
            SET target_quantity=2.500000, target_quantity_unit_id=:unit
            WHERE menu_item_id=:item"""), {**ids, 'unit': unit_id})
        source_week_version = connection.execute(text(
            'SELECT row_version FROM cafeteria.menu_weeks WHERE id=:week'
        ), ids).scalar_one()

    target_week_start = date(2026, 9, 14)
    copy_previous_week(
        app_engine, scope, target_week_start, 0, source_row_version=source_week_version,
    )
    with seeded_pg16.connect() as connection:
        copied = connection.execute(text("""SELECT link.recipe_revision_id,link.target_quantity,
            link.target_quantity_unit_id
            FROM cafeteria.menu_item_components link
            JOIN cafeteria.menu_items item ON item.id=link.menu_item_id
            JOIN cafeteria.menu_services service ON service.id=item.service_id
            JOIN cafeteria.menu_weeks week ON week.id=service.menu_week_id
            WHERE week.week_start=:week_start"""), {'week_start': target_week_start}).one()
    assert copied == (revision_id, Decimal('2.500000'), unit_id)


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
    assert len(status['migration_checksums']['0030_v32_to_v33.sql']) == hashlib.sha256().digest_size * 2
