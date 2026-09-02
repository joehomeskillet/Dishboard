#!/usr/bin/env python3
"""Statische Prüfung der SQL-Baseline und der zwei Demo-Snapshots.

Eine laufende PostgreSQL-Instanz wird damit nicht ersetzt. Das Ergebnis trennt
bewusst statische Artefaktprüfung von Live-Ausführung.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'database' / 'schema.sql'
MIGRATION_0001 = ROOT / 'database' / 'migrations' / '0001_initial_postgresql.sql'
MIGRATION_0002 = ROOT / 'database' / 'migrations' / '0002_profile_publication_and_local_auth.sql'
MIGRATION_0003 = ROOT / 'database' / 'migrations' / '0003_patient_key_and_withdrawal_contracts.sql'
MIGRATION_0004 = ROOT / 'database' / 'migrations' / '0004_patient_key_lock_and_capability_contracts.sql'
MIGRATION_0005 = ROOT / 'database' / 'migrations' / '0005_least_privilege_identity_contracts.sql'
MIGRATION_0006 = ROOT / 'database' / 'migrations' / '0006_auth_issuer_and_local_login.sql'
MIGRATION_0007 = ROOT / 'database' / 'migrations' / '0007_auth_security_hardening.sql'
MIGRATION_0009 = ROOT / 'database' / 'migrations' / '0009_bootstrap_first_local_admin.sql'
MIGRATION_0008 = ROOT / 'database' / 'migrations' / '0008_auth_final_hardening.sql'
MIGRATION_0010 = ROOT / 'database' / 'migrations' / '0010_v12_to_v13.sql'
SEED = ROOT / 'database' / 'seed.sql'
CAF_JSON = ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json'
PAT_JSON = ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json'

FORBIDDEN_PATIENT_COMPACT_TOKENS = (
    'price', 'prices', 'preis', 'preise', 'cost', 'costs', 'amount', 'amounts',
    'kosten', 'betrag', 'rappen', 'currency', 'chf', 'fee', 'tarif', 'tariff', 'charge',
)
ALLOWED_PATIENT_COMPACT_KEYS = frozenset({
    'channel', 'days', 'date', 'notice', 'services', 'mealcode', 'mealname',
    'options', 'allergenreviewstatus', 'allergens', 'components', 'description',
    'externalid', 'labels', 'note', 'origins', 'title', 'typecode', 'typename',
    'code', 'name', 'presence', 'countrycode', 'ingredient', 'text', 'state',
    'weekday', 'location', 'profilecode', 'revisionid', 'schemaversion',
    'sharednote', 'weekend', 'weekstart', 'servicestate',
})


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def table_block(sql: str, name: str) -> str:
    match = re.search(
        rf'CREATE TABLE IF NOT EXISTS\s+{re.escape(name)}\s*\((.*?)\n\);',
        sql,
        re.S | re.I,
    )
    if not match:
        fail(f'Tabelle fehlt oder kann nicht gelesen werden: {name}')
    return match.group(1)


def normalize_patient_key(key: str) -> str:
    without_format_chars = ''.join(char for char in key if unicodedata.category(char) != 'Cf')
    return re.sub(r'[^A-Za-z0-9]+', '', without_format_chars).lower()


def patient_key_is_forbidden(key: str) -> bool:
    compact = normalize_patient_key(key)
    return compact not in ALLOWED_PATIENT_COMPACT_KEYS or any(
        token in compact for token in FORBIDDEN_PATIENT_COMPACT_TOKENS
    )


def forbidden_key_paths(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if patient_key_is_forbidden(key):
                found.append(f'{path}.{key}')
            found.extend(forbidden_key_paths(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_key_paths(child, f'{path}[{index}]'))
    return found


def run_live_check() -> dict[str, Any]:
    database_url = os.getenv('TEST_DATABASE_URL', '').strip()
    if not database_url:
        fail('TEST_DATABASE_URL fehlt für --live.')
    sys.path.insert(0, str(ROOT / 'reference_scaffold'))
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    from cafeteria.db import _execute_script, run_migrations

    catalog_queries = {
        'columns': '''
            SELECT table_name, ordinal_position, column_name, data_type, udt_name,
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema=:schema_name
            ORDER BY table_name, ordinal_position
        ''',
        'constraints': '''
            SELECT rel.relname, con.conname, con.contype, pg_get_constraintdef(con.oid, true)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid=con.conrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname=:schema_name
            ORDER BY rel.relname, con.conname
        ''',
        'indexes': '''
            SELECT tab.relname, idx.relname, pg_get_indexdef(i.indexrelid)
            FROM pg_index i
            JOIN pg_class tab ON tab.oid=i.indrelid
            JOIN pg_class idx ON idx.oid=i.indexrelid
            JOIN pg_namespace ns ON ns.oid=tab.relnamespace
            WHERE ns.nspname=:schema_name
            ORDER BY tab.relname, idx.relname
        ''',
        'functions': '''
            SELECT p.proname, pg_get_function_identity_arguments(p.oid), p.prokind,
                   p.prosecdef, p.proconfig, p.prosrc
            FROM pg_proc p
            JOIN pg_namespace ns ON ns.oid=p.pronamespace
            WHERE ns.nspname=:schema_name
            ORDER BY p.proname, pg_get_function_identity_arguments(p.oid)
        ''',
        'triggers': '''
            SELECT rel.relname, trg.tgname, pg_get_triggerdef(trg.oid, true)
            FROM pg_trigger trg
            JOIN pg_class rel ON rel.oid=trg.tgrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname=:schema_name AND NOT trg.tgisinternal
            ORDER BY rel.relname, trg.tgname
        ''',
        'views': '''
            SELECT viewname, definition FROM pg_views
            WHERE schemaname=:schema_name ORDER BY viewname
        ''',
    }

    def structure(schema_name: str) -> dict[str, list[tuple[Any, ...]]]:
        result: dict[str, list[tuple[Any, ...]]] = {}
        with engine.connect() as connection:
            for name, query in catalog_queries.items():
                rows = connection.execute(text(query), {'schema_name': schema_name}).tuples().all()
                result[name] = [
                    tuple(
                        value.replace(f'{schema_name}.', '<schema>.')
                        if isinstance(value, str)
                        else value
                        for value in row
                    )
                    for row in rows
                ]
        return result

    engine = create_engine(database_url, poolclass=NullPool, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
        run_migrations(engine, SCHEMA)
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    '''
                    SELECT
                        current_setting('server_version') AS server_version,
                        (SELECT max(version) FROM cafeteria.schema_migrations) AS schema_version,
                        (
                            SELECT count(*)
                            FROM pg_proc p
                            JOIN pg_namespace n ON n.oid = p.pronamespace
                            WHERE n.nspname='cafeteria'
                              AND p.proname='validate_publication_revision'
                        ) AS revision_fn_count
                    '''
                )
            ).mappings().one()
        if int(row['schema_version']) != 13:
            fail(f"Live-Schema-Version ist {row['schema_version']}, erwartet 13.")
        if int(row['revision_fn_count']) != 1:
            fail('Live-Datenbank hat nicht genau eine validate_publication_revision-Funktion.')
        migrated_structure = structure('cafeteria')
        with engine.begin() as connection:
            connection.execute(text('ALTER SCHEMA cafeteria RENAME TO cafeteria_migrated_contract'))
        _execute_script(engine, str(SCHEMA))
        baseline_structure = structure('cafeteria')
        for object_type, expected in migrated_structure.items():
            actual = baseline_structure[object_type]
            if actual != expected:
                fail(f'Schema-Baseline weicht bei {object_type} vom Migrationsergebnis ab.')
        return {
            'live_postgresql_executed': True,
            'server_version': row['server_version'],
            'live_schema_version': int(row['schema_version']),
            'baseline_migration_equivalent': True,
        }
    finally:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria_migrated_contract CASCADE'))
        engine.dispose()


def validate_snapshots() -> tuple[dict[str, Any], dict[str, Any]]:
    caf = json.loads(CAF_JSON.read_text(encoding='utf-8'))
    pat = json.loads(PAT_JSON.read_text(encoding='utf-8'))

    if caf.get('profile_code') != 'staff_guest':
        fail('Cafeteria-Snapshot hat falsches Profil.')
    if pat.get('profile_code') != 'patient':
        fail('Patienten-Snapshot hat falsches Profil.')
    if len(caf.get('days', [])) != 7 or len(pat.get('days', [])) != 7:
        fail('Beide Snapshots müssen sieben Kalendertage enthalten.')

    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    for snapshot in (caf, pat):
        week_start = date.fromisoformat(snapshot['week_start'])
        if snapshot.get('week_end') != (week_start + timedelta(days=6)).isoformat():
            fail('Snapshot-Wochenende stimmt nicht mit week_start überein.')
        for index, day in enumerate(snapshot['days']):
            if day.get('date') != (week_start + timedelta(days=index)).isoformat():
                fail('Snapshot-Kalendertage sind nicht lückenlos.')
            if day.get('weekday') != weekdays[index]:
                fail(f"Falscher Wochentag für {day.get('date')}.")

    caf_services = [service for day in caf['days'] for service in day.get('services', [])]
    if len(caf_services) != 5:
        fail(f'Cafeteria-Snapshot hat {len(caf_services)} statt fünf Werktage.')
    if any(service.get('meal_code') != 'LUNCH' for service in caf_services):
        fail('Cafeteria-Snapshot enthält eine andere Mahlzeit als LUNCH.')
    if any(len(service.get('options', [])) != 2 for service in caf_services):
        fail('Cafeteria-Service ohne genau zwei Menükarten.')
    for service in caf_services:
        if {option.get('type_code') for option in service.get('options', [])} != {'MENU_1', 'VEGGIE'}:
            fail('Cafeteria-Service ohne exakt MENU_1 und VEGGIE.')
        for option in service['options']:
            costs = option.get('prices')
            if not isinstance(costs, dict) or set(costs) != {'internal_rappen', 'external_rappen', 'currency'}:
                fail('Cafeteria-Menü ohne vollständige interne/externe Kostenstruktur.')
            if type(costs.get('internal_rappen')) is not int or type(costs.get('external_rappen')) is not int:
                fail('Cafeteria-Rappen müssen JSON-Ganzzahlen sein.')

    bad_paths = forbidden_key_paths(pat)
    if bad_paths:
        fail('Patienten-Snapshot enthält Kosten-Schlüssel: ' + ', '.join(bad_paths[:8]))
    patient_text = json.dumps(pat, ensure_ascii=False)
    for token in ('CHF', '0.00', 'Mitarbeitende 11.00', 'Externe 16.60'):
        if token.lower() in patient_text.lower():
            fail(f'Patienten-Snapshot enthält unzulässigen Inhalt: {token}')
    for day in pat['days']:
        services = day.get('services', [])
        if {service.get('meal_code') for service in services} != {'LUNCH', 'DINNER'}:
            fail(f"Patiententag {day.get('date')} hat nicht Mittag und Abend.")
        if any(len(service.get('options', [])) != 2 for service in services):
            fail(f"Patiententag {day.get('date')} hat keine zwei Optionen je Mahlzeit.")
        if any(
            {option.get('type_code') for option in service.get('options', [])} != {'MENU_1', 'VEGGIE'}
            for service in services
        ):
            fail(f"Patiententag {day.get('date')} hat nicht exakt MENU_1 und VEGGIE.")

    return caf, pat


def main() -> int:
    try:
        sql = SCHEMA.read_text(encoding='utf-8')
        migration_0002 = MIGRATION_0002.read_text(encoding='utf-8')
        migration_0003 = MIGRATION_0003.read_text(encoding='utf-8')
        migration_0005 = MIGRATION_0005.read_text(encoding='utf-8')
        migration_0006 = MIGRATION_0006.read_text(encoding='utf-8')
        migration_0007 = MIGRATION_0007.read_text(encoding='utf-8')
        migration_0008 = MIGRATION_0008.read_text(encoding='utf-8')
        migration_0010 = MIGRATION_0010.read_text(encoding='utf-8')
        seed = SEED.read_text(encoding='utf-8')
        immutable_migration_checksums = {
            MIGRATION_0001: 'd1001f657858b4fec9a466517bf4117add8b28160dda7aebf7c43c21e6e6fff0',
            MIGRATION_0002: '7f8696eb886a99d841ac82be1e4b3abf1b51080c18aac07ea5290325f3e5e863',
            MIGRATION_0003: 'eda9c5e851525367af62a3f056b3592a521d871f6ac818d4d50c18d8f720d1de',
            MIGRATION_0004: '7309069f1b52d41a756a315af8b6ccf0771afe113875a6c5f82d42775f74b066',
            MIGRATION_0005: 'b33bdfebe621adfca3da98c85a1b0e8316040c55cf62542eda138099362f1818',
            MIGRATION_0006: '60897aea8c7096f449a43a6cd2b79452f943cbbec75cc74a0bcf4514baaac233',
            MIGRATION_0007: 'a25d5b6ca71bc11c582eef6e90f792979a88aa86dcc444b7b1ab1db90967595f',
            MIGRATION_0008: '4311165d2dcd763cf9a462906d044000956eb11d16ac847ecf9351facae21e45',
            MIGRATION_0009: '1b988c75b7ef3f333045d738fa29cd210a367eeaf30825a3005873cafc3b65ed',
            MIGRATION_0010: '316e92589fe4d210150e10dc1575f767282542995ecb4020891194c68efbd346',
        }
        for migration_path, expected_checksum in immutable_migration_checksums.items():
            actual_checksum = hashlib.sha256(migration_path.read_bytes()).hexdigest()
            if actual_checksum != expected_checksum:
                fail(f'{migration_path.name} wurde nachträglich verändert.')
        baseline_checksum = immutable_migration_checksums[MIGRATION_0001]

        tables = re.findall(r'^CREATE TABLE IF NOT EXISTS\s+([a-z_]+)', sql, re.M | re.I)
        required_tables = {
            'offer_profiles', 'menu_weeks', 'menu_services', 'menu_items',
            'menu_item_prices', 'publication_revisions', 'publication_lifecycle_events',
            'audit_events', 'local_credentials', 'auth_capability_secrets', 'auth_capability_nonces',
            'menu_components', 'component_allergens', 'component_labels',
        }
        missing = required_tables - set(tables)
        if missing:
            fail('Pflichttabellen fehlen: ' + ', '.join(sorted(missing)))

        for fragment in (
            "code IN ('patient', 'staff_guest')",
            "code IN ('LUNCH', 'DINNER')",
            'validate_menu_service()',
            'validate_menu_item_price()',
            'validate_publication_revision()',
            'jsonb_has_patient_forbidden_key',
            'uq_publication_one_active_per_profile_week',
            'CREATE OR REPLACE VIEW active_publications',
            'authz_version',
            'protect_publication_revision()',
            'publication_lifecycle_events',
            'validate_menu_week()',
            'r.profile_id',
            "w.workflow_state = 'published'",
            'withdraw_publication_revision',
            'issue_publication_capability',
            'auth_capability_secrets',
            'FOR UPDATE OF w',
            'patient_key_is_forbidden',
            'withdrawn_by',
            'sync_entra_user',
            'ensure_auth_capability_state',
            'hard_reset_auth_capability_state',
            "interval '15 minutes'",
            'provision_local_user',
            'set_local_password',
            'disable_local_user',
            'record_local_login_lock',
            'trg_local_credentials_login_lock_audit',
            'REVOKE ALL ON SCHEMA cafeteria',
            'REVOKE CREATE ON SCHEMA public FROM PUBLIC',
            "profile_scope IN ('common', 'patient', 'staff_guest')",
            "category IN ('meat', 'side', 'vegetable', 'sauce', 'dessert', 'other')",
            'uq_menu_components_location_scope_name',
            "allergen_mode IN ('auto', 'manual')",
            "origin_mode IN ('auto', 'manual')",
            "label_mode IN ('auto', 'manual')",
        ):
            if fragment not in sql:
                fail(f'Pflichtfragment fehlt: {fragment}')
        if sql.count('CREATE OR REPLACE FUNCTION validate_publication_revision()') != 1:
            fail('validate_publication_revision muss genau einmal definiert sein.')

        for fragment in (
            'CREATE TABLE IF NOT EXISTS local_credentials',
            'jsonb_has_patient_forbidden_value',
            'trg_publication_immutable',
            "workflow_state <> 'published'",
            'publication_lifecycle_events',
            'v4-Entwurf darf nicht öffentlich bleiben',
            'JSON-Ganzzahlen',
            'validate_menu_week()',
        ):
            if fragment not in migration_0002:
                fail(f'Pflichtfragment in 0002 fehlt: {fragment}')

        for fragment in (
            'normalize_patient_key',
            'withdraw_publication_revision',
            'withdrawn_by',
            'Publikationsrevision kann nicht zurückgestuft werden',
            'SECURITY DEFINER',
        ):
            if fragment not in migration_0003:
                fail(f'Pflichtfragment in 0003 fehlt: {fragment}')

        migration_0004 = MIGRATION_0004.read_text(encoding='utf-8')
        for fragment in (
            'auth_capability_secrets',
            'issue_publication_capability',
            'public.hmac',
            'FOR UPDATE OF w',
            'patient_key_is_forbidden',
            '[^A-Za-z0-9]+',
            'Capability-Nonce wurde bereits verwendet',
        ):
            if fragment not in migration_0004:
                fail(f'Pflichtfragment in 0004 fehlt: {fragment}')

        for fragment in (
            'sync_entra_user',
            'ensure_auth_capability_state',
            'hard_reset_auth_capability_state',
            "interval '15 minutes'",
            'authz_version darf nicht zurückgesetzt werden',
            'REVOKE ALL ON cafeteria.users',
            'cafeteria.auth_capability_secrets',
        ):
            if fragment not in migration_0005:
                fail(f'Pflichtfragment in 0005 fehlt: {fragment}')

        for fragment in (
            'cafeteria_auth_issuer',
            'provision_local_user',
            'set_local_password',
            'disable_local_user',
            'sync_entra_user',
            'issue_publication_capability',
            'REVOKE ALL ON ALL TABLES',
            'Lokale Rollenliste enthält unbekannte, inaktive oder doppelte Rollen',
            'auth.local_role_granted',
            'auth.local_password_changed',
            'auth.local_user_disabled',
        ):
            if fragment not in migration_0006:
                fail(f'Pflichtfragment in 0006 fehlt: {fragment}')

        for fragment in (
            'Rolle cafeteria_auth_issuer muss vor Migration 0007 provisioniert sein',
            'resolve_auth_actor',
            'auth.entra_roles_changed',
            "'target_user_id'",
            'REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cafeteria',
            'provision_local_user(text, text, text, text, text[])',
            'set_local_password(text, text, text)',
            'disable_local_user(text, text)',
        ):
            if fragment not in migration_0007:
                fail(f'Pflichtfragment in 0007 fehlt: {fragment}')

        for fragment in (
            'record_local_login_lock',
            'SECURITY DEFINER',
            'trg_local_credentials_login_lock_audit',
            'REVOKE INSERT ON audit_events FROM cafeteria_app',
            'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE audit_events_id_seq FROM cafeteria_app',
            'REVOKE ALL ON SCHEMA cafeteria',
            'REVOKE CREATE ON SCHEMA public FROM PUBLIC',
        ):
            if fragment not in migration_0008:
                fail(f'Pflichtfragment in 0008 fehlt: {fragment}')

        migration_0009 = MIGRATION_0009.read_text(encoding='utf-8')
        for fragment in (
            'bootstrap_first_local_admin',
            'pg_advisory_xact_lock',
            'auth.local_admin_bootstrapped',
        ):
            if fragment not in migration_0009:
                fail(f'Pflichtfragment in 0009 fehlt: {fragment}')
                fail(f'Pflichtfragment in 0008 fehlt: {fragment}')

        for fragment in (
            'CREATE TABLE IF NOT EXISTS menu_components',
            'CREATE TABLE IF NOT EXISTS component_allergens',
            'CREATE TABLE IF NOT EXISTS component_labels',
            "SET allergen_mode='manual'",
            "SET origin_mode='manual'",
            "SET label_mode='manual'",
            "bool_or(mia.presence='contains')",
            'v13 conflicting legacy origin country codes',
            'uq_menu_components_location_scope_name',
            'menu_item_components_component_link_check',
        ):
            if fragment not in migration_0010:
                fail(f'Pflichtfragment in 0010 fehlt: {fragment}')
        if not migration_0010.startswith('BEGIN;') or not migration_0010.rstrip().endswith('COMMIT;'):
            fail('Migration 0010 hat keinen strikten BEGIN/COMMIT-Vertrag.')

        for name in ('menu_weeks', 'menu_services', 'menu_items', 'dish_templates'):
            block = table_block(sql, name).lower()
            if re.search(r'\b(price|preis|internal_rappen|external_rappen)\b', block):
                fail(f'Kostenfeld liegt am falschen Objekt: {name}')
        price_block = table_block(sql, 'menu_item_prices').lower()
        for field in ('internal_rappen', 'external_rappen', "currency char(3)"):
            if field not in price_block:
                fail(f'Kostenfeld fehlt in menu_item_prices: {field}')

        role_values = set(re.findall(r"\('?(Cafeteria\.[A-Za-z]+)'?,", seed))
        expected_roles = {'Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'}
        if role_values != expected_roles:
            fail(f'Rollen im Seed abweichend: {sorted(role_values)}')
        allergen_seed = seed.split('INSERT INTO allergens', 1)[1].split('ON CONFLICT (code)', 1)[0]
        allergens = re.findall(r"\('([A-Z_]+)',\s*'[^']+',\s*(\d+)\)", allergen_seed)
        allergen_rows = [(code, int(number)) for code, number in allergens]
        if len(allergen_rows) != 14:
            fail(f'Erwartet 14 Allergene, gefunden {len(allergen_rows)}.')

        caf, pat = validate_snapshots()
        live_info = {'live_postgresql_executed': False}
        if '--live' in sys.argv:
            live_info = run_live_check()
        result = {
            'artifact_check': 'passed',
            **live_info,
            'tables': len(tables),
            'table_names': tables,
            'application_roles': len(expected_roles),
            'offer_profiles': 2,
            'allergens': 14,
            'cafeteria_services': sum(len(day['services']) for day in caf['days']),
            'patient_services': sum(len(day['services']) for day in pat['days']),
            'patient_menu_options': sum(len(service['options']) for day in pat['days'] for service in day['services']),
            'schema_sha256': hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
            'schema_version': 13,
            'migration_checksums': {
                '0001_initial_postgresql.sql': baseline_checksum,
                '0002_profile_publication_and_local_auth.sql': hashlib.sha256(MIGRATION_0002.read_bytes()).hexdigest(),
                '0003_patient_key_and_withdrawal_contracts.sql': hashlib.sha256(MIGRATION_0003.read_bytes()).hexdigest(),
                '0004_patient_key_lock_and_capability_contracts.sql': hashlib.sha256(MIGRATION_0004.read_bytes()).hexdigest(),
                '0005_least_privilege_identity_contracts.sql': hashlib.sha256(MIGRATION_0005.read_bytes()).hexdigest(),
                '0006_auth_issuer_and_local_login.sql': hashlib.sha256(MIGRATION_0006.read_bytes()).hexdigest(),
                '0007_auth_security_hardening.sql': hashlib.sha256(MIGRATION_0007.read_bytes()).hexdigest(),
                '0008_auth_final_hardening.sql': hashlib.sha256(MIGRATION_0008.read_bytes()).hexdigest(),
                '0009_bootstrap_first_local_admin.sql': hashlib.sha256(MIGRATION_0009.read_bytes()).hexdigest(),
                '0010_v12_to_v13.sql': hashlib.sha256(MIGRATION_0010.read_bytes()).hexdigest(),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'artifact_check': 'failed', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
