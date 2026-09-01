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
SEED = ROOT / 'database' / 'seed.sql'
CAF_JSON = ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json'
PAT_JSON = ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json'

FORBIDDEN_PATIENT_KEYS = {
    'price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen',
    'preis_intern', 'preis_extern', 'currency', 'chf', 'rappen',
    'cost', 'costs', 'amount', 'amounts', 'kosten', 'betrag', 'fee', 'tarif', 'tariff', 'charge',
}
FORBIDDEN_PATIENT_KEY_PARTS = {
    'price', 'prices', 'preis', 'preise', 'cost', 'costs', 'amount', 'amounts',
    'kosten', 'betrag', 'rappen', 'currency', 'chf', 'fee', 'tarif', 'tariff', 'charge',
}


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
    assert match is not None
    return match.group(1)


def normalize_patient_key(key: str) -> str:
    without_format_chars = ''.join(char for char in key if unicodedata.category(char) != 'Cf')
    snake_case = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', without_format_chars)
    return re.sub(r'[\W_]+', '_', snake_case, flags=re.UNICODE).strip('_').lower()


def forbidden_key_paths(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = normalize_patient_key(key)
            if (
                normalized in FORBIDDEN_PATIENT_KEYS
                or bool(set(normalized.split('_')) & FORBIDDEN_PATIENT_KEY_PARTS)
            ):
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

    from cafeteria.db import run_migrations

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
        if int(row['schema_version']) != 6:
            fail(f"Live-Schema-Version ist {row['schema_version']}, erwartet 6.")
        if int(row['revision_fn_count']) != 1:
            fail('Live-Datenbank hat nicht genau eine validate_publication_revision-Funktion.')
        return {
            'live_postgresql_executed': True,
            'server_version': row['server_version'],
            'live_schema_version': int(row['schema_version']),
        }
    finally:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
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
        seed = SEED.read_text(encoding='utf-8')
        baseline_checksum = hashlib.sha256(MIGRATION_0001.read_bytes()).hexdigest()
        if baseline_checksum != 'd1001f657858b4fec9a466517bf4117add8b28160dda7aebf7c43c21e6e6fff0':
            fail('0001_initial_postgresql.sql wurde nachträglich verändert.')

        tables = re.findall(r'^CREATE TABLE IF NOT EXISTS\s+([a-z_]+)', sql, re.M | re.I)
        required_tables = {
            'offer_profiles', 'menu_weeks', 'menu_services', 'menu_items',
            'menu_item_prices', 'publication_revisions', 'publication_lifecycle_events',
            'audit_events', 'local_credentials',
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
            'withdrawn_by',
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
            'schema_version': 6,
            'migration_checksums': {
                '0001_initial_postgresql.sql': baseline_checksum,
                '0002_profile_publication_and_local_auth.sql': hashlib.sha256(MIGRATION_0002.read_bytes()).hexdigest(),
                '0003_patient_key_and_withdrawal_contracts.sql': hashlib.sha256(MIGRATION_0003.read_bytes()).hexdigest(),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'artifact_check': 'failed', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
