#!/usr/bin/env python3
"""Erzeugt getrennte Küchen-CSV-Beispiele aus den Demo-Snapshots."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DEFAULT / 'csv'))
sys.path.insert(0, str(ROOT_DEFAULT / 'tools'))

from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402
from validate_menu_csv import CAFETERIA_HEADERS, PATIENT_HEADERS  # noqa: E402


def join_codes(values: list[dict], key: str = 'code') -> str:
    return '|'.join(str(value[key]) for value in values)


def export(snapshot: dict, path: Path, headers: list[str]) -> None:
    rows = []
    for day in snapshot['days']:
        for service in day.get('services', []):
            for option in service.get('options', []):
                contains = [item for item in option.get('allergens', []) if item.get('presence') == 'contains']
                traces = [item for item in option.get('allergens', []) if item.get('presence') == 'may_contain']
                row = {
                    'schema_version': '2',
                    'profil': snapshot['profile_code'],
                    'datum': day['date'],
                    'wochentag': day['weekday'],
                    'mahlzeit': service['meal_code'],
                    'menueart': option['type_code'],
                    'external_id': option['external_id'],
                    'titel': option['title'],
                    'beschreibung': option.get('description', ''),
                    'beilagen': '|'.join(option.get('components', [])),
                    'labels': join_codes(option.get('labels', [])),
                    'allergene_enthaelt': join_codes(contains),
                    'allergene_spuren': join_codes(traces),
                    'herkunft': '|'.join(f"{origin['ingredient']}={origin['country_code']}" for origin in option.get('origins', [])),
                    'hinweis': option.get('note', ''),
                    'zustand': 'offen',
                    'zustand_text': '',
                }
                if snapshot['profile_code'] == 'staff_guest':
                    costs = option['prices']
                    row['preis_mitarbeitende_chf'] = f"{costs['internal_rappen'] / 100:.2f}"
                    row['preis_externe_chf'] = f"{costs['external_rappen'] / 100:.2f}"
                rows.append(row)

    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter=';', lineterminator='\r\n')
        writer.writeheader()
        writer.writerows(rows)


def empty_template(path: Path, headers: list[str]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        csv.writer(handle, delimiter=';', lineterminator='\r\n').writerow(headers)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT_DEFAULT)
    args = parser.parse_args()
    csv_dir = args.root.resolve() / 'csv'
    export(cafeteria_snapshot(), csv_dir / 'menu_cafeteria_example.csv', CAFETERIA_HEADERS)
    export(patient_snapshot(), csv_dir / 'menu_patient_example.csv', PATIENT_HEADERS)
    empty_template(csv_dir / 'menu_cafeteria_template.csv', CAFETERIA_HEADERS)
    empty_template(csv_dir / 'menu_patient_template.csv', PATIENT_HEADERS)
    print('Vier profilgetrennte CSV-Dateien erzeugt.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
