#!/usr/bin/env python3
"""Erzeugt Demo-Snapshots und seed_demo.sql aus einer gemeinsamen Datenquelle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from demo_snapshots import cafeteria_snapshot, patient_snapshot


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def json_dollar(value: dict[str, Any], tag: str) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    return f'${tag}${payload}${tag}$::jsonb'


def item_sql(profile: str, week_var: str, day: dict[str, Any], service: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.append(
        "INSERT INTO menu_services(menu_week_id, service_date, meal_period_id, service_state) "
        f"VALUES ({week_var}, {q(day['date'])}::date, (SELECT id FROM meal_periods WHERE code={q(service['meal_code'])}), 'open') "
        "RETURNING id INTO v_service;"
    )
    for order, option in enumerate(service['options'], start=1):
        lines.append(
            "INSERT INTO menu_items(service_id, menu_type_id, external_id, title, description, note, allergen_review_status, sort_order, created_by_dummy) "
            "VALUES (0,0,'','','','','not_checked',1,0);"
        )
        # Platzhalter wird direkt ersetzt; so bleibt die eigentliche SQL-Zeile übersichtlich.
        lines[-1] = (
            "INSERT INTO menu_items(service_id, menu_type_id, external_id, title, description, note, allergen_review_status, sort_order) "
            f"VALUES (v_service, (SELECT id FROM menu_types WHERE code={q(option['type_code'])}), "
            f"{q(option['external_id'])}, {q(option['title'])}, {q(option.get('description', ''))}, "
            f"{q(option.get('note', ''))}, {q(option.get('allergen_review_status', 'not_checked'))}, {order * 10}) "
            "RETURNING id INTO v_item;"
        )
        if profile == 'staff_guest':
            costs = option['prices']
            lines.append(
                "INSERT INTO menu_item_prices(menu_item_id, internal_rappen, external_rappen, currency) "
                f"VALUES (v_item, {int(costs['internal_rappen'])}, {int(costs['external_rappen'])}, 'CHF');"
            )
        for index, component in enumerate(option.get('components', []), start=1):
            lines.append(
                "INSERT INTO menu_item_components(menu_item_id, sort_order, component_text) "
                f"VALUES (v_item, {index * 10}, {q(component)});"
            )
        for label in option.get('labels', []):
            lines.append(
                "INSERT INTO menu_item_labels(menu_item_id, label_id) "
                f"SELECT v_item, id FROM dietary_labels WHERE code={q(label['code'])};"
            )
        for allergen in option.get('allergens', []):
            lines.append(
                "INSERT INTO menu_item_allergens(menu_item_id, allergen_id, presence) "
                f"SELECT v_item, id, {q(allergen['presence'])} FROM allergens WHERE code={q(allergen['code'])};"
            )
        for origin in option.get('origins', []):
            lines.append(
                "INSERT INTO origin_declarations(menu_item_id, ingredient, country_code, declaration_text) "
                f"VALUES (v_item, {q(origin['ingredient'])}, {q(origin['country_code'])}, {q(origin['text'])});"
            )
    return lines


def build_sql(caf: dict[str, Any], pat: dict[str, Any]) -> str:
    lines = [
        '-- Automatisch erzeugt durch tools/build_demo_seed.py',
        'BEGIN;',
        'SET search_path TO cafeteria, public;',
        '',
        'DO $seed$',
        'DECLARE',
        '    v_location bigint;',
        '    v_system bigint;',
        '    v_caf_week bigint;',
        '    v_pat_week bigint;',
        '    v_service bigint;',
        '    v_item bigint;',
        'BEGIN',
        "    SELECT id INTO v_location FROM locations WHERE code='KIRCHLINDACH';",
        "    SELECT id INTO v_system FROM users WHERE public_id='00000000-0000-0000-0000-000000000001'::uuid;",
        '',
        f"    DELETE FROM menu_weeks WHERE location_id=v_location AND week_start={q(caf['week_start'])}::date;",
        '',
        "    INSERT INTO menu_weeks(location_id, profile_id, week_start, workflow_state, title, shared_note, created_by, updated_by)",
        f"    VALUES (v_location, (SELECT id FROM offer_profiles WHERE code='staff_guest'), {q(caf['week_start'])}::date, 'published', {q(caf['title'])}, {q(caf['shared_note'])}, v_system, v_system)",
        '    RETURNING id INTO v_caf_week;',
    ]
    for day in caf['days']:
        for service in day['services']:
            lines.extend('    ' + line for line in item_sql('staff_guest', 'v_caf_week', day, service))
    lines.extend([
        '    INSERT INTO publication_revisions(menu_week_id, revision_number, revision_code, snapshot_json, published_by)',
        f"    VALUES (v_caf_week, 1, {q(caf['revision_id'])}, {json_dollar(caf, 'cafjson')}, v_system);",
        '',
        "    INSERT INTO menu_weeks(location_id, profile_id, week_start, workflow_state, title, shared_note, created_by, updated_by)",
        f"    VALUES (v_location, (SELECT id FROM offer_profiles WHERE code='patient'), {q(pat['week_start'])}::date, 'published', {q(pat['title'])}, {q(pat['shared_note'])}, v_system, v_system)",
        '    RETURNING id INTO v_pat_week;',
    ])
    for day in pat['days']:
        for service in day['services']:
            lines.extend('    ' + line for line in item_sql('patient', 'v_pat_week', day, service))
    lines.extend([
        '    INSERT INTO publication_revisions(menu_week_id, revision_number, revision_code, snapshot_json, published_by)',
        f"    VALUES (v_pat_week, 1, {q(pat['revision_id'])}, {json_dollar(pat, 'patjson')}, v_system);",
        'END;',
        '$seed$;',
        '',
        'COMMIT;',
        '',
    ])
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    caf = cafeteria_snapshot()
    pat = patient_snapshot()

    snapshot_dir = root / 'demo' / 'snapshots'
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / 'cafeteria_kw36.json').write_text(
        json.dumps(caf, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    (snapshot_dir / 'patienten_kw36.json').write_text(
        json.dumps(pat, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    (root / 'database' / 'seed_demo.sql').write_text(build_sql(caf, pat), encoding='utf-8')
    print('Demo-Snapshots und database/seed_demo.sql erzeugt.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
