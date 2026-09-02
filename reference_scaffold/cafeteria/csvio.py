from __future__ import annotations

import csv
import importlib.util
import io
import re
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import BinaryIO

BASE_HEADERS = [
    'schema_version', 'profil', 'datum', 'wochentag', 'mahlzeit', 'menueart',
    'external_id', 'titel', 'beschreibung', 'beilagen', 'labels',
    'allergene_enthaelt', 'allergene_spuren', 'herkunft', 'hinweis',
    'zustand', 'zustand_text',
]
PATIENT_HEADERS = BASE_HEADERS
CAFETERIA_HEADERS = BASE_HEADERS + ['preis_mitarbeitende_chf', 'preis_externe_chf']
MAX_UPLOAD_BYTES = 1_000_000
STATE_CODES = {
    'offen': 'open',
    'geschlossen': 'closed',
    'feiertag': 'holiday',
    'betriebsferien': 'company_holiday',
}
MONTH_NAMES = (
    '',
    'Januar',
    'Februar',
    'März',
    'April',
    'Mai',
    'Juni',
    'Juli',
    'August',
    'September',
    'Oktober',
    'November',
    'Dezember',
)


@cache
def _validator() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / 'csv' / 'validate_menu_csv.py'
    spec = importlib.util.spec_from_file_location('dishboard_menu_csv_validator', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('CSV-Validator konnte nicht geladen werden.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _excel_safe(value: object) -> str:
    text_value = '' if value is None else str(value)
    return "'" + text_value if text_value.startswith(('=', '+', '-', '@', '\t', '\r')) else text_value


def snapshot_to_csv(snapshot: dict) -> bytes:
    profile = snapshot.get('profile_code')
    if profile not in {'patient', 'staff_guest'}:
        raise ValueError('Unbekanntes Snapshot-Profil.')
    headers = PATIENT_HEADERS if profile == 'patient' else CAFETERIA_HEADERS
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=';', lineterminator='\r\n')
    writer.writeheader()
    for day in snapshot.get('days', []):
        for service in day.get('services', []):
            for option in service.get('options', []):
                contains = [a['code'] for a in option.get('allergens', []) if a.get('presence') == 'contains']
                traces = [a['code'] for a in option.get('allergens', []) if a.get('presence') == 'may_contain']
                row = {
                    'schema_version': '2', 'profil': profile, 'datum': day.get('date', ''),
                    'wochentag': day.get('weekday', ''), 'mahlzeit': service.get('meal_code', ''),
                    'menueart': option.get('type_code', ''), 'external_id': option.get('external_id', ''),
                    'titel': option.get('title', ''), 'beschreibung': option.get('description', ''),
                    'beilagen': '|'.join(option.get('components', [])),
                    'labels': '|'.join(label['code'] for label in option.get('labels', [])),
                    'allergene_enthaelt': '|'.join(contains), 'allergene_spuren': '|'.join(traces),
                    'herkunft': '|'.join(f"{origin['ingredient']}={origin['country_code']}" for origin in option.get('origins', [])),
                    'hinweis': option.get('note', ''), 'zustand': 'offen', 'zustand_text': '',
                }
                if profile == 'staff_guest':
                    costs = option['prices']
                    row['preis_mitarbeitende_chf'] = f"{costs['internal_rappen'] / 100:.2f}"
                    row['preis_externe_chf'] = f"{costs['external_rappen'] / 100:.2f}"
                writer.writerow({key: _excel_safe(value) for key, value in row.items()})
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


def _column_for_error(message: str, headers: list[str]) -> int:
    formula_match = re.search(r' in ([^ ]+) ist unzulässig', message)
    if formula_match and formula_match.group(1) in headers:
        return headers.index(formula_match.group(1)) + 1
    mappings = (
        ('schema_version', 'schema_version'),
        ('profil', 'profil'),
        ('datum', 'datum'),
        ('wochentag', 'wochentag'),
        ('zustand_text', 'zustand_text'),
        ('zustand', 'zustand'),
        ('mahlzeit', 'mahlzeit'),
        ('menueart', 'menueart'),
        ('external_id', 'external_id'),
        ('titel', 'titel'),
        ('Kostenfeld', 'preis_mitarbeitende_chf'),
    )
    for marker, header in mappings:
        if marker in message and header in headers:
            return headers.index(header) + 1
    if 'Header entspricht nicht' in message:
        expected = PATIENT_HEADERS if 'preis_mitarbeitende_chf' not in headers else CAFETERIA_HEADERS
        for index, header in enumerate(headers):
            if index >= len(expected) or header != expected[index]:
                return index + 1
        return min(len(headers), len(expected)) + 1
    if 'Kostenspalten' in message:
        for index, header in enumerate(headers):
            if re.search(r'preis|price|chf|rappen|kosten', header, re.I):
                return index + 1
    return 1


def _issues(errors: list[str], headers: list[str], profile: str | None) -> list[dict[str, object]]:
    issues = []
    for error in errors:
        line_match = re.match(r'Zeile (\d+): (.*)', error)
        line = int(line_match.group(1)) if line_match else 1
        message = line_match.group(2) if line_match else error
        column = _column_for_error(message, headers)
        if profile == 'patient' and ('Kostenspalten' in message or 'Header entspricht nicht' in message):
            message = 'Unzulässige Spalte im Patientenformat.'
        issues.append({'line': line, 'column': column, 'message': message})
    return issues


def _read_upload(stream: BinaryIO) -> tuple[str | None, list[dict[str, object]]]:
    payload = stream.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        return None, [{'line': 1, 'column': 1, 'message': 'CSV-Datei ist zu gross.'}]
    try:
        return payload.decode('utf-8-sig'), []
    except UnicodeDecodeError:
        return None, [{'line': 1, 'column': 1, 'message': 'CSV-Datei muss UTF-8 sein.'}]


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split('|') if part.strip()]


def _origins(value: str) -> list[dict[str, str]]:
    origins = []
    for declaration in _split(value):
        ingredient, country_code = declaration.rsplit('=', 1)
        origins.append(
            {
                'ingredient': ingredient.strip(),
                'country_code': country_code.strip(),
                'text': declaration,
            }
        )
    return origins


def _option(row: dict[str, str], profile: str) -> dict[str, object]:
    option: dict[str, object] = {
        'type_code': row['menueart'],
        'external_id': row['external_id'].strip(),
        'title': row['titel'].strip(),
        'description': row['beschreibung'].strip(),
        'components': _split(row['beilagen']),
        'labels': [{'code': code, 'name': code} for code in _split(row['labels'])],
        'allergens': [
            {'code': code, 'name': code, 'presence': presence}
            for field, presence in (
                ('allergene_enthaelt', 'contains'),
                ('allergene_spuren', 'may_contain'),
            )
            for code in _split(row[field])
        ],
        'origins': _origins(row['herkunft']),
        'note': row['hinweis'].strip(),
        'allergen_review_status': 'not_checked',
    }
    if profile == 'staff_guest':
        option['internal_rappen'] = int(Decimal(row['preis_mitarbeitende_chf']) * 100)
        option['external_rappen'] = int(Decimal(row['preis_externe_chf']) * 100)
    return option


def _week_title(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    return (
        f'{week_start.day}. {MONTH_NAMES[week_start.month]} bis '
        f'{week_end.day}. {MONTH_NAMES[week_end.month]}'
    )


def _draft_values(profile: str, rows: list[dict[str, str]]) -> tuple[date, dict[str, object]]:
    dates = [date.fromisoformat(row['datum']) for row in rows]
    week_start = min(dates) - timedelta(days=min(dates).isoweekday() - 1)
    row_map = {
        (row['datum'], row['mahlzeit'], row['menueart']): row
        for row in rows
        if row['zustand'] == 'offen'
    }
    days = []
    day_count = 7 if profile == 'patient' else 5
    meals = ('LUNCH', 'DINNER') if profile == 'patient' else ('LUNCH',)
    for offset in range(day_count):
        service_date = (week_start + timedelta(days=offset)).isoformat()
        services = []
        for meal_code in meals:
            matching = [
                row for row in rows if row['datum'] == service_date and row['mahlzeit'] == meal_code
            ]
            state_row = matching[0]
            state = STATE_CODES[state_row['zustand']]
            options = []
            if state == 'open':
                options = [
                    _option(row_map[(service_date, meal_code, type_code)], profile)
                    for type_code in ('MENU_1', 'VEGGIE')
                ]
            else:
                options = [
                    {'type_code': type_code, 'title': '', 'components': []}
                    for type_code in ('MENU_1', 'VEGGIE')
                ]
                if profile == 'staff_guest':
                    for option in options:
                        option['internal_rappen'] = ''
                        option['external_rappen'] = ''
            services.append(
                {
                    'meal_code': meal_code,
                    'service_state': state,
                    'notice': state_row['zustand_text'].strip(),
                    'options': options,
                }
            )
        days.append({'date': service_date, 'services': services})
    return week_start, {'title': _week_title(week_start), 'shared_note': '', 'days': days}


def validate_upload(stream: BinaryIO) -> dict[str, object]:
    text_value, read_issues = _read_upload(stream)
    if text_value is None:
        return {
            'profile': None,
            'rows': 0,
            'headers': [],
            'issues': read_issues,
            'valid': False,
        }
    validated = _validator().validate_text(text_value, '<upload>')
    reader = csv.DictReader(io.StringIO(text_value), delimiter=';')
    rows = list(reader)
    headers = reader.fieldnames or []
    profile = validated['profile']
    result: dict[str, object] = {
        'profile': profile,
        'rows': len(rows),
        'headers': headers,
        'issues': _issues(validated['errors'], headers, profile),
        'valid': bool(validated['valid']),
        'text': text_value,
    }
    if validated['valid']:
        week_start, values = _draft_values(profile, rows)
        result['week_start'] = week_start
        result['values'] = values
    return result
