from __future__ import annotations

import csv
import io
from typing import BinaryIO

BASE_HEADERS = [
    'schema_version', 'profil', 'datum', 'wochentag', 'mahlzeit', 'menueart',
    'external_id', 'titel', 'beschreibung', 'beilagen', 'labels',
    'allergene_enthaelt', 'allergene_spuren', 'herkunft', 'hinweis',
    'zustand', 'zustand_text',
]
PATIENT_HEADERS = BASE_HEADERS
CAFETERIA_HEADERS = BASE_HEADERS + ['preis_mitarbeitende_chf', 'preis_externe_chf']


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


def validate_upload(stream: BinaryIO) -> dict:
    text_value = stream.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text_value), delimiter=';')
    rows = list(reader)
    headers = reader.fieldnames or []
    profiles = {row.get('profil', '').strip() for row in rows if row.get('profil', '').strip()}
    profile = next(iter(profiles)) if len(profiles) == 1 else None
    expected = PATIENT_HEADERS if profile == 'patient' else CAFETERIA_HEADERS if profile == 'staff_guest' else None
    errors: list[str] = []
    if expected is None:
        errors.append('Datei braucht genau ein Profil: patient oder staff_guest.')
    elif headers != expected:
        errors.append('Header entspricht nicht dem Profilformat.')
    if profile == 'patient' and any('preis' in header.lower() or 'chf' in header.lower() for header in headers):
        errors.append('Patienten-Datei enthält unzulässige Kostenspalten.')
    if len(rows) > 10_000:
        errors.append('Mehr als 10 000 Datenzeilen.')
    return {'profile': profile, 'rows': len(rows), 'headers': headers, 'errors': errors, 'valid': not errors}
