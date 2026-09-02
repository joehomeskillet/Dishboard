#!/usr/bin/env python3
"""Validiert die zwei bewusst getrennten Küchen-CSV-Formate."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_HEADERS = [
    'schema_version', 'profil', 'datum', 'wochentag', 'mahlzeit', 'menueart',
    'external_id', 'titel', 'beschreibung', 'beilagen', 'labels',
    'allergene_enthaelt', 'allergene_spuren', 'herkunft', 'hinweis',
    'zustand', 'zustand_text',
]
PATIENT_HEADERS = BASE_HEADERS
CAFETERIA_HEADERS = BASE_HEADERS + ['preis_mitarbeitende_chf', 'preis_externe_chf']
PROFILES = {'patient', 'staff_guest'}
MEALS = {'LUNCH', 'DINNER'}
MENU_TYPES = {'MENU_1', 'VEGGIE'}
DAY_NAMES = {
    1: 'Montag', 2: 'Dienstag', 3: 'Mittwoch', 4: 'Donnerstag',
    5: 'Freitag', 6: 'Samstag', 7: 'Sonntag',
}
PRICE_HEADER_PATTERN = re.compile(r'(preis|price|chf|rappen|kosten)', re.I)
DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _parse_decimal(value: str) -> int:
    if not re.fullmatch(r'\d+\.\d{2}', value):
        raise ValueError('Format muss 0.00 sein')
    major, minor = value.split('.')
    cents = int(major) * 100 + int(minor)
    if cents <= 0:
        raise ValueError('Betrag muss grösser als null sein')
    return cents


def validate_text(text: str, source: str = '<stream>') -> dict:
    reader = csv.DictReader(io.StringIO(text), delimiter=';')
    headers = reader.fieldnames or []
    raw_rows = list(reader)
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, str]] = []

    for line_number, raw_row in enumerate(raw_rows, start=2):
        prefix = f'Zeile {line_number}: '
        if raw_row.get(None):
            errors.append(prefix + 'zusätzliche Zelle nach letzter Spalte.')
        row: dict[str, str] = {}
        for column, header in enumerate(headers, start=1):
            value = raw_row.get(header)
            if not isinstance(value, str):
                errors.append(prefix + f'Spalte {column} fehlt.')
                row[header] = ''
            else:
                row[header] = value
        rows.append(row)

    if len(headers) != len(set(headers)):
        errors.append('Header enthält doppelte Spalten.')
    if 'profil' not in headers:
        errors.append('Pflichtspalte profil fehlt.')
        return {'source': source, 'profile': None, 'rows': len(rows), 'errors': errors, 'warnings': warnings, 'valid': False}

    profiles = {row.get('profil', '').strip() for row in rows if row.get('profil', '').strip()}
    profile = next(iter(profiles)) if len(profiles) == 1 else None
    if not rows:
        errors.append('CSV enthält keine Datenzeilen.')
    if len(profiles) != 1 or profile not in PROFILES:
        errors.append('Alle Zeilen müssen genau dasselbe gültige Profil enthalten: patient oder staff_guest.')

    expected = PATIENT_HEADERS if profile == 'patient' else CAFETERIA_HEADERS if profile == 'staff_guest' else None
    if expected is not None and headers != expected:
        missing = [h for h in expected if h not in headers]
        extra = [h for h in headers if h not in expected]
        errors.append(f'Header entspricht nicht dem Profilformat. Fehlend={missing}; zusätzlich={extra}.')

    if profile == 'patient':
        suspicious = [header for header in headers if PRICE_HEADER_PATTERN.search(header)]
        if suspicious:
            errors.append('Patienten-CSV enthält unzulässige Kostenspalten: ' + ', '.join(suspicious))

    seen_external: set[str] = set()
    slots: Counter[tuple[str, str, str]] = Counter()
    dates: dict[str, dt.date] = {}
    rows_by_date_meal: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for line_number, row in enumerate(rows, start=2):
        prefix = f'Zeile {line_number}: '
        for key, value in row.items():
            if value.startswith(DANGEROUS_PREFIXES):
                errors.append(prefix + f'Formel-/Befehlspräfix in {key} ist unzulässig.')

        if row.get('schema_version') != '2':
            errors.append(prefix + 'schema_version muss 2 sein.')
        if row.get('profil') not in PROFILES:
            errors.append(prefix + 'ungültiges profil.')

        try:
            date_value = dt.date.fromisoformat(row.get('datum', ''))
            dates[row['datum']] = date_value
            expected_day = DAY_NAMES[date_value.isoweekday()]
            if row.get('wochentag') != expected_day:
                errors.append(prefix + f'wochentag muss {expected_day} sein.')
        except ValueError:
            errors.append(prefix + 'datum muss ISO-Format YYYY-MM-DD haben.')
            date_value = None

        state = row.get('zustand', '')
        if state not in {'offen', 'geschlossen', 'feiertag', 'betriebsferien'}:
            errors.append(prefix + 'zustand ist ungültig.')
        meal = row.get('mahlzeit', '')
        menu_type = row.get('menueart', '')
        if meal not in MEALS:
            errors.append(prefix + 'mahlzeit muss LUNCH oder DINNER sein.')
        if menu_type not in MENU_TYPES:
            errors.append(prefix + 'menueart muss MENU_1 oder VEGGIE sein.')

        if date_value is not None:
            weekday = date_value.isoweekday()
            if profile == 'staff_guest' and (weekday > 5 or meal != 'LUNCH'):
                errors.append(prefix + 'staff_guest erlaubt nur Montag bis Freitag und LUNCH.')
            if profile == 'patient' and meal not in {'LUNCH', 'DINNER'}:
                errors.append(prefix + 'patient erlaubt nur LUNCH und DINNER.')

        slot = (row.get('datum', ''), meal, menu_type)
        slots[slot] += 1
        rows_by_date_meal[(row.get('datum', ''), meal)].append(row)

        if state != 'offen':
            if not row.get('zustand_text', '').strip():
                errors.append(prefix + 'geschlossener Zustand braucht zustand_text.')
            closed_fields = (
                'external_id', 'titel', 'beschreibung', 'beilagen', 'labels',
                'allergene_enthaelt', 'allergene_spuren', 'herkunft', 'hinweis',
                'preis_mitarbeitende_chf', 'preis_externe_chf',
            )
            if any(row.get(field, '').strip() for field in closed_fields):
                errors.append(prefix + 'geschlossene Zeile enthält unzulässige Menüwerte.')
            continue

        if not row.get('external_id', '').strip():
            errors.append(prefix + 'external_id fehlt.')
        elif row['external_id'] in seen_external:
            errors.append(prefix + 'external_id ist doppelt.')
        else:
            seen_external.add(row['external_id'])
        if not row.get('titel', '').strip():
            errors.append(prefix + 'titel fehlt.')

        for declaration in [part.strip() for part in row.get('herkunft', '').split('|') if part.strip()]:
            if declaration.count('=') != 1:
                errors.append(prefix + 'herkunft hat ungültiges Format.')
                continue
            ingredient, country_code = (part.strip() for part in declaration.split('=', 1))
            if not ingredient or re.fullmatch(r'[A-Z]{2}', country_code) is None:
                errors.append(prefix + 'herkunft hat ungültiges Format.')

        if profile == 'staff_guest':
            try:
                internal = _parse_decimal(row.get('preis_mitarbeitende_chf', ''))
                external = _parse_decimal(row.get('preis_externe_chf', ''))
                if external < internal:
                    errors.append(prefix + 'externer Betrag darf nicht kleiner sein als Mitarbeitenden-Betrag.')
            except ValueError as exc:
                errors.append(prefix + f'Kostenfeld ungültig: {exc}.')

    duplicates = [slot for slot, count in slots.items() if count > 1]
    if duplicates:
        errors.append('Doppelte Menüslots: ' + ', '.join('/'.join(slot) for slot in duplicates[:8]))

    if dates:
        iso_weeks = {(value.isocalendar().year, value.isocalendar().week) for value in dates.values()}
        if len(iso_weeks) != 1:
            errors.append('CSV darf nur eine ISO-Kalenderwoche enthalten.')

    if profile == 'staff_guest' and rows:
        expected_dates = {value for value in dates.values() if value.isoweekday() <= 5}
        if len(rows) != 10 or len(expected_dates) != 5:
            errors.append('Cafeteria-Beispiel muss fünf Werktage × zwei Menüarten enthalten.')
        for slot_key, group in rows_by_date_meal.items():
            if {row.get('menueart') for row in group} != MENU_TYPES:
                errors.append(f'Slot {slot_key[0]}/{slot_key[1]} braucht MENU_1 und VEGGIE.')

    if profile == 'patient' and rows:
        if len(rows) != 28 or len(dates) != 7:
            errors.append('Patienten-Beispiel muss sieben Tage × zwei Mahlzeiten × zwei Menüarten enthalten.')
        for date_text in dates:
            for meal in ('LUNCH', 'DINNER'):
                group = rows_by_date_meal[(date_text, meal)]
                if {row.get('menueart') for row in group} != MENU_TYPES:
                    errors.append(f'Slot {date_text}/{meal} braucht MENU_1 und VEGGIE.')

    if len(rows) > 10_000:
        errors.append('Mehr als 10 000 Datenzeilen sind nicht erlaubt.')

    return {
        'source': source,
        'profile': profile,
        'rows': len(rows),
        'headers': headers,
        'errors': errors,
        'warnings': warnings,
        'valid': not errors,
    }


def validate_file(path: Path) -> dict:
    return validate_text(path.read_text(encoding='utf-8-sig'), str(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = validate_file(args.csv_file)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Profil: {result['profile'] or '-'} · Zeilen: {result['rows']} · gültig: {result['valid']}")
        for error in result['errors']:
            print('[FEHLER] ' + error)
        for warning in result['warnings']:
            print('[WARNUNG] ' + warning)
    return 0 if result['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
