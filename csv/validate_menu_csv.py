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
from collections.abc import Sequence
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
LABEL_CODES = {'VEGETARIAN', 'VEGAN', 'LACTOSE_FREE', 'GLUTEN_FREE'}
ALLERGEN_CODES = {
    'GLUTEN', 'CRUSTACEANS', 'EGGS', 'FISH', 'PEANUTS', 'SOY', 'MILK',
    'NUTS', 'CELERY', 'MUSTARD', 'SESAME', 'SULPHITES', 'LUPIN', 'MOLLUSCS',
}


def _parse_decimal(value: str) -> int:
    if not re.fullmatch(r'\d+\.\d{2}', value):
        raise ValueError('Format muss 0.00 sein')
    major, minor = value.split('.')
    cents = int(major) * 100 + int(minor)
    if cents <= 0:
        raise ValueError('Betrag muss grösser als null sein')
    return cents


def _column_number(headers: Sequence[str], field: str | None, fallback: int = 1) -> int:
    if field is None or field not in headers:
        return fallback
    return headers.index(field) + 1


def _pipe_parts(value: str) -> list[str]:
    return [part.strip() for part in value.split('|') if part.strip()]


def validate_text(text: str, source: str = '<stream>') -> dict:
    reader = csv.DictReader(io.StringIO(text), delimiter=';')
    headers = reader.fieldnames or []
    raw_rows = list(reader)
    errors: list[str] = []
    issues: list[dict[str, int | str]] = []
    warnings: list[str] = []
    rows: list[dict[str, str]] = []

    def add_error(
        message: str,
        *,
        line: int | None = None,
        field: str | None = None,
        column: int | None = None,
    ) -> None:
        errors.append(f'Zeile {line}: {message}' if line is not None else message)
        issues.append(
            {
                'line': line if line is not None else 1,
                'column': column if column is not None else _column_number(headers, field),
                'message': message,
            }
        )

    for line_number, raw_row in enumerate(raw_rows, start=2):
        if raw_row.get(None):
            add_error(
                'zusätzliche Zelle nach letzter Spalte.',
                line=line_number,
                column=len(headers) + 1,
            )
        row: dict[str, str] = {}
        for column, header in enumerate(headers, start=1):
            value = raw_row.get(header)
            if not isinstance(value, str):
                add_error(f'Spalte {column} fehlt.', line=line_number, column=column)
                row[header] = ''
            else:
                row[header] = value
        rows.append(row)

    if len(headers) != len(set(headers)):
        duplicate_column = next(
            (
                index
                for index, header in enumerate(headers, start=1)
                if header in headers[: index - 1]
            ),
            1,
        )
        add_error('Header enthält doppelte Spalten.', column=duplicate_column)
    if 'profil' not in headers:
        add_error('Pflichtspalte profil fehlt.')
        return {
            'source': source,
            'profile': None,
            'rows': len(rows),
            'headers': headers,
            'errors': errors,
            'issues': issues,
            'warnings': warnings,
            'valid': False,
        }

    profiles = {row.get('profil', '').strip() for row in rows if row.get('profil', '').strip()}
    profile = next(iter(profiles)) if len(profiles) == 1 else None
    if not rows:
        add_error('CSV enthält keine Datenzeilen.')
    if len(profiles) != 1 or profile not in PROFILES:
        add_error(
            'Alle Zeilen müssen genau dasselbe gültige Profil enthalten: patient oder staff_guest.',
            field='profil',
        )

    expected = PATIENT_HEADERS if profile == 'patient' else CAFETERIA_HEADERS if profile == 'staff_guest' else None
    if expected is not None and headers != expected:
        missing = [h for h in expected if h not in headers]
        extra = [h for h in headers if h not in expected]
        mismatch = next(
            (
                index
                for index, header in enumerate(headers)
                if index >= len(expected) or header != expected[index]
            ),
            min(len(headers), len(expected)),
        )
        add_error(
            f'Header entspricht nicht dem Profilformat. Fehlend={missing}; zusätzlich={extra}.',
            column=mismatch + 1,
        )

    if profile == 'patient':
        suspicious = [header for header in headers if PRICE_HEADER_PATTERN.search(header)]
        if suspicious:
            add_error(
                'Patienten-CSV enthält unzulässige Kostenspalten: ' + ', '.join(suspicious),
                field=suspicious[0],
            )

    seen_external: set[str] = set()
    slots: Counter[tuple[str, str, str]] = Counter()
    dates: dict[str, dt.date] = {}
    rows_by_date_meal: defaultdict[
        tuple[str, str],
        list[tuple[int, dict[str, str]]],
    ] = defaultdict(list)

    for line_number, row in enumerate(rows, start=2):
        for key, value in row.items():
            if value.startswith(DANGEROUS_PREFIXES):
                add_error(
                    f'Formel-/Befehlspräfix in {key} ist unzulässig.',
                    line=line_number,
                    field=key,
                )

        if row.get('schema_version') != '2':
            add_error('schema_version muss 2 sein.', line=line_number, field='schema_version')
        if row.get('profil') not in PROFILES:
            add_error('ungültiges profil.', line=line_number, field='profil')

        try:
            date_value = dt.date.fromisoformat(row.get('datum', ''))
            dates[row['datum']] = date_value
            expected_day = DAY_NAMES[date_value.isoweekday()]
            if row.get('wochentag') != expected_day:
                add_error(
                    f'wochentag muss {expected_day} sein.',
                    line=line_number,
                    field='wochentag',
                )
        except ValueError:
            add_error(
                'datum muss ISO-Format YYYY-MM-DD haben.',
                line=line_number,
                field='datum',
            )
            date_value = None

        state = row.get('zustand', '').strip()
        row['zustand'] = state
        row['zustand_text'] = row.get('zustand_text', '').strip()
        if state not in {'offen', 'geschlossen', 'feiertag', 'betriebsferien'}:
            add_error('zustand ist ungültig.', line=line_number, field='zustand')
        meal = row.get('mahlzeit', '')
        menu_type = row.get('menueart', '')
        if meal not in MEALS:
            add_error(
                'mahlzeit muss LUNCH oder DINNER sein.',
                line=line_number,
                field='mahlzeit',
            )
        if menu_type not in MENU_TYPES:
            add_error(
                'menueart muss MENU_1 oder VEGGIE sein.',
                line=line_number,
                field='menueart',
            )

        if date_value is not None:
            weekday = date_value.isoweekday()
            if profile == 'staff_guest' and (weekday > 5 or meal != 'LUNCH'):
                add_error(
                    'staff_guest erlaubt nur Montag bis Freitag und LUNCH.',
                    line=line_number,
                    field='mahlzeit',
                )
            if profile == 'patient' and meal not in {'LUNCH', 'DINNER'}:
                add_error(
                    'patient erlaubt nur LUNCH und DINNER.',
                    line=line_number,
                    field='mahlzeit',
                )

        slot = (row.get('datum', ''), meal, menu_type)
        slots[slot] += 1
        rows_by_date_meal[(row.get('datum', ''), meal)].append((line_number, row))

        if state != 'offen':
            if not row.get('zustand_text', '').strip():
                add_error(
                    'geschlossener Zustand braucht zustand_text.',
                    line=line_number,
                    field='zustand_text',
                )
            closed_fields = (
                'external_id', 'titel', 'beschreibung', 'beilagen', 'labels',
                'allergene_enthaelt', 'allergene_spuren', 'herkunft', 'hinweis',
                'preis_mitarbeitende_chf', 'preis_externe_chf',
            )
            populated = next(
                (field for field in closed_fields if row.get(field, '').strip()),
                None,
            )
            if populated is not None:
                add_error(
                    'geschlossene Zeile enthält unzulässige Menüwerte.',
                    line=line_number,
                    field=populated,
                )
            continue

        if not row.get('external_id', '').strip():
            add_error('external_id fehlt.', line=line_number, field='external_id')
        elif row['external_id'].strip() in seen_external:
            add_error('external_id ist doppelt.', line=line_number, field='external_id')
        else:
            seen_external.add(row['external_id'].strip())
        if not row.get('titel', '').strip():
            add_error('titel fehlt.', line=line_number, field='titel')

        labels = _pipe_parts(row.get('labels', ''))
        if len(labels) != len(set(labels)):
            add_error('labels enthält doppelte Codes.', line=line_number, field='labels')
        if any(code not in LABEL_CODES for code in labels):
            add_error('labels enthält unbekannten Code.', line=line_number, field='labels')

        allergen_fields = ('allergene_enthaelt', 'allergene_spuren')
        allergens_by_field = {
            field: _pipe_parts(row.get(field, '')) for field in allergen_fields
        }
        for field, codes in allergens_by_field.items():
            if len(codes) != len(set(codes)):
                add_error('Allergenliste enthält doppelte Codes.', line=line_number, field=field)
            if any(code not in ALLERGEN_CODES for code in codes):
                add_error('Allergenliste enthält unbekannten Code.', line=line_number, field=field)
        if set(allergens_by_field['allergene_enthaelt']) & set(
            allergens_by_field['allergene_spuren']
        ):
            for field in allergen_fields:
                add_error(
                    'Allergencode darf nur eine Präsenz haben.',
                    line=line_number,
                    field=field,
                )

        seen_origin_ingredients: set[str] = set()
        for declaration in _pipe_parts(row.get('herkunft', '')):
            if declaration.count('=') != 1:
                add_error(
                    'herkunft hat ungültiges Format.',
                    line=line_number,
                    field='herkunft',
                )
                continue
            ingredient, country_code = (part.strip() for part in declaration.split('=', 1))
            if not ingredient or re.fullmatch(r'[A-Z]{2}', country_code) is None:
                add_error(
                    'herkunft hat ungültiges Format.',
                    line=line_number,
                    field='herkunft',
                )
                continue
            normalized_ingredient = ingredient.casefold()
            if normalized_ingredient in seen_origin_ingredients:
                add_error(
                    'herkunft enthält eine doppelte Zutat.',
                    line=line_number,
                    field='herkunft',
                )
            seen_origin_ingredients.add(normalized_ingredient)

        if profile == 'staff_guest':
            parsed_costs: dict[str, int] = {}
            for field in ('preis_mitarbeitende_chf', 'preis_externe_chf'):
                try:
                    parsed_costs[field] = _parse_decimal(row.get(field, ''))
                except ValueError as exc:
                    add_error(
                        f'Kostenfeld ungültig: {exc}.',
                        line=line_number,
                        field=field,
                    )
            if (
                len(parsed_costs) == 2
                and parsed_costs['preis_externe_chf']
                < parsed_costs['preis_mitarbeitende_chf']
            ):
                add_error(
                    'externer Betrag darf nicht kleiner sein als Mitarbeitenden-Betrag.',
                    line=line_number,
                    field='preis_externe_chf',
                )

    for group in rows_by_date_meal.values():
        states = {row.get('zustand', '').strip() for _, row in group}
        notices = {row.get('zustand_text', '').strip() for _, row in group}
        if len(states) > 1:
            for line_number, _row in group:
                add_error(
                    'Menüzeilen eines Services brauchen denselben Zustand.',
                    line=line_number,
                    field='zustand',
                )
        if len(notices) > 1:
            for line_number, _row in group:
                add_error(
                    'Menüzeilen eines Services brauchen denselben Zustandshinweis.',
                    line=line_number,
                    field='zustand_text',
                )

    duplicates = [slot for slot, count in slots.items() if count > 1]
    if duplicates:
        add_error('Doppelte Menüslots: ' + ', '.join('/'.join(slot) for slot in duplicates[:8]))

    if dates:
        iso_weeks = {(value.isocalendar().year, value.isocalendar().week) for value in dates.values()}
        if len(iso_weeks) != 1:
            add_error('CSV darf nur eine ISO-Kalenderwoche enthalten.', field='datum')

    if profile == 'staff_guest' and rows:
        expected_dates = {value for value in dates.values() if value.isoweekday() <= 5}
        if len(rows) != 10 or len(expected_dates) != 5:
            add_error('Cafeteria-Beispiel muss fünf Werktage × zwei Menüarten enthalten.')
        for slot_key, group in rows_by_date_meal.items():
            if {row.get('menueart') for _, row in group} != MENU_TYPES:
                add_error(f'Slot {slot_key[0]}/{slot_key[1]} braucht MENU_1 und VEGGIE.')

    if profile == 'patient' and rows:
        if len(rows) != 28 or len(dates) != 7:
            add_error(
                'Patienten-Beispiel muss sieben Tage × zwei Mahlzeiten × zwei Menüarten enthalten.'
            )
        for date_text in dates:
            for meal in ('LUNCH', 'DINNER'):
                group = rows_by_date_meal[(date_text, meal)]
                if {row.get('menueart') for _, row in group} != MENU_TYPES:
                    add_error(f'Slot {date_text}/{meal} braucht MENU_1 und VEGGIE.')

    if len(rows) > 10_000:
        add_error('Mehr als 10 000 Datenzeilen sind nicht erlaubt.')

    return {
        'source': source,
        'profile': profile,
        'rows': len(rows),
        'headers': headers,
        'errors': errors,
        'issues': issues,
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
