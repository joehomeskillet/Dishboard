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
from typing import BinaryIO, cast

from . import patient_payload
from .workflow import validate_draft_values

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
STATE_NAMES = {value: key for key, value in STATE_CODES.items()}
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
            state = service.get('service_state', 'open')
            if state not in STATE_NAMES:
                raise ValueError('Snapshot enthält einen ungültigen Servicestatus.')
            options = service.get('options', [])
            if state != 'open':
                options = [{'type_code': type_code} for type_code in ('MENU_1', 'VEGGIE')]
            for option in options:
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
                    'hinweis': option.get('note', ''),
                    'zustand': STATE_NAMES[state],
                    'zustand_text': service.get('notice', '') if state != 'open' else '',
                }
                if profile == 'staff_guest' and state == 'open':
                    costs = option['prices']
                    internal = int(costs['internal_rappen'])
                    external = int(costs['external_rappen'])
                    row['preis_mitarbeitende_chf'] = f'{internal // 100}.{internal % 100:02d}'
                    row['preis_externe_chf'] = f'{external // 100}.{external % 100:02d}'
                writer.writerow({key: _excel_safe(value) for key, value in row.items()})
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


def _issues(
    exact_issues: list[dict[str, object]],
    *,
    patient_contract: bool,
) -> list[dict[str, object]]:
    issues = []
    for issue in exact_issues:
        message = str(issue['message'])
        if patient_contract:
            message = 'Patienten-CSV ist ungültig.'
        issues.append(
            {
                'line': cast(int, issue['line']),
                'column': cast(int, issue['column']),
                'message': message,
            }
        )
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
        if declaration.count('=') != 1:
            raise ValueError('Herkunftsangabe ist ungültig.')
        ingredient, country_code = declaration.rsplit('=', 1)
        if not ingredient.strip() or re.fullmatch(r'[A-Z]{2}', country_code.strip()) is None:
            raise ValueError('Herkunftsangabe ist ungültig.')
        origins.append(
            {
                'ingredient': ingredient.strip(),
                'country_code': country_code.strip(),
                'text': declaration,
            }
        )
    return origins


def _patient_semantic_issues(
    rows: list[dict[str, str]],
    headers: list[str],
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []

    def add(line: int, field: str) -> None:
        issues.append(
            {
                'line': line,
                'column': headers.index(field) + 1,
                'message': 'Patienten-CSV ist ungültig.',
            }
        )

    for line_number, row in enumerate(rows, start=2):
        if row['zustand'] == 'offen':
            external_id = row['external_id'].strip()
            if patient_payload.PATIENT_EXTERNAL_ID_RE.fullmatch(external_id) is None:
                add(line_number, 'external_id')
            fields = {
                'titel': [row['titel'].strip()],
                'beschreibung': [row['beschreibung'].strip()],
                'beilagen': _split(row['beilagen']),
                'herkunft': [origin['ingredient'] for origin in _origins(row['herkunft'])],
            }
            for field, values in fields.items():
                if any(
                    patient_payload._patient_text_is_forbidden(value)
                    for value in values
                    if value
                ):
                    add(line_number, field)
            note = row['hinweis'].strip()
            if note and patient_payload._patient_text_is_forbidden(
                note,
                allow_operational_time=True,
            ):
                add(line_number, 'hinweis')
        notice = row['zustand_text'].strip()
        if notice and patient_payload._patient_text_is_forbidden(notice):
            add(line_number, 'zustand_text')
    return issues


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
    headers = list(reader.fieldnames or [])
    profile = validated['profile']
    patient_contract = profile == 'patient' or any(
        isinstance(row.get('profil'), str) and row['profil'].strip() == 'patient'
        for row in rows
    )
    result: dict[str, object] = {
        'profile': profile,
        'rows': len(rows),
        'headers': headers,
        'issues': _issues(
            validated['issues'],
            patient_contract=patient_contract,
        ),
        'valid': bool(validated['valid']),
        'text': text_value,
    }
    if validated['valid']:
        if profile == 'patient':
            semantic_issues = _patient_semantic_issues(rows, headers)
            if semantic_issues:
                result['issues'] = semantic_issues
                result['valid'] = False
                return result
        try:
            week_start, values = _draft_values(profile, rows)
            validate_draft_values(str(profile), week_start, values)
        except (ArithmeticError, KeyError, TypeError, ValueError):
            result['issues'] = [
                {
                    'line': 1,
                    'column': 1,
                    'message': (
                        'Patienten-CSV ist ungültig.'
                        if patient_contract
                        else 'CSV-Inhalt ist ungültig.'
                    ),
                }
            ]
            result['valid'] = False
        else:
            result['week_start'] = week_start
            result['values'] = values
    return result
