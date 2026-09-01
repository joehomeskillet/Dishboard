#!/usr/bin/env python3
"""Statische Prüfung der SQL-Baseline und der zwei Demo-Snapshots.

Eine laufende PostgreSQL-Instanz wird damit nicht ersetzt. Das Ergebnis trennt
bewusst statische Artefaktprüfung von Live-Ausführung.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'database' / 'schema.sql'
MIGRATION = ROOT / 'database' / 'migrations' / '0001_initial_postgresql.sql'
SEED = ROOT / 'database' / 'seed.sql'
CAF_JSON = ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json'
PAT_JSON = ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json'

FORBIDDEN_PATIENT_KEYS = {
    'price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen',
    'preis_intern', 'preis_extern', 'currency', 'chf', 'rappen',
}


def fail(message: str) -> None:
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


def forbidden_key_paths(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lower = key.lower()
            if (
                lower in FORBIDDEN_PATIENT_KEYS
                or re.search(r'(^|_)(price|preis)(_|$)', lower)
                or lower.endswith('_rappen')
            ):
                found.append(f'{path}.{key}')
            found.extend(forbidden_key_paths(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_key_paths(child, f'{path}[{index}]'))
    return found


def validate_snapshots() -> tuple[dict[str, Any], dict[str, Any]]:
    caf = json.loads(CAF_JSON.read_text(encoding='utf-8'))
    pat = json.loads(PAT_JSON.read_text(encoding='utf-8'))

    if caf.get('profile_code') != 'staff_guest':
        fail('Cafeteria-Snapshot hat falsches Profil.')
    if pat.get('profile_code') != 'patient':
        fail('Patienten-Snapshot hat falsches Profil.')
    if len(caf.get('days', [])) != 7 or len(pat.get('days', [])) != 7:
        fail('Beide Snapshots müssen sieben Kalendertage enthalten.')

    caf_services = [service for day in caf['days'] for service in day.get('services', [])]
    if len(caf_services) != 5:
        fail(f'Cafeteria-Snapshot hat {len(caf_services)} statt fünf Werktage.')
    if any(service.get('meal_code') != 'LUNCH' for service in caf_services):
        fail('Cafeteria-Snapshot enthält eine andere Mahlzeit als LUNCH.')
    if any(len(service.get('options', [])) != 2 for service in caf_services):
        fail('Cafeteria-Service ohne genau zwei Menükarten.')
    for service in caf_services:
        for option in service['options']:
            costs = option.get('prices')
            if not isinstance(costs, dict) or set(costs) != {'internal_rappen', 'external_rappen', 'currency'}:
                fail('Cafeteria-Menü ohne vollständige interne/externe Kostenstruktur.')

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

    return caf, pat


def main() -> int:
    try:
        sql = SCHEMA.read_text(encoding='utf-8')
        seed = SEED.read_text(encoding='utf-8')
        if SCHEMA.read_bytes() != MIGRATION.read_bytes():
            fail('SQL-Baseline und 0001_initial_postgresql.sql sind nicht byteidentisch.')

        tables = re.findall(r'^CREATE TABLE IF NOT EXISTS\s+([a-z_]+)', sql, re.M | re.I)
        required_tables = {
            'offer_profiles', 'menu_weeks', 'menu_services', 'menu_items',
            'menu_item_prices', 'publication_revisions', 'audit_events',
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
        ):
            if fragment not in sql:
                fail(f'Pflichtfragment fehlt: {fragment}')

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
        result = {
            'artifact_check': 'passed',
            'live_postgresql_executed': False,
            'tables': len(tables),
            'table_names': tables,
            'application_roles': len(expected_roles),
            'offer_profiles': 2,
            'allergens': 14,
            'cafeteria_services': sum(len(day['services']) for day in caf['days']),
            'patient_services': sum(len(day['services']) for day in pat['days']),
            'patient_menu_options': sum(len(service['options']) for day in pat['days'] for service in day['services']),
            'schema_sha256': hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'artifact_check': 'failed', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
