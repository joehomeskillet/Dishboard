from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .patient_payload import validate_snapshot_payload

WEEKDAYS = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
MEAL_NAMES = {'LUNCH': 'Mittag', 'DINNER': 'Abend'}
TYPE_NAMES = {'MENU_1': 'Menü 1', 'VEGGIE': 'Vegetarisch'}


def external_id(profile_code: str, service_date: str, meal_code: str, type_code: str) -> str:
    suffix = '1' if type_code == 'MENU_1' else '2'
    prefix = 'PATIENT' if profile_code == 'patient' else 'STAFF-GUEST'
    return f'{prefix}-{service_date}-{meal_code}-{suffix}'


def _option(
    profile_code: str,
    service_date: str,
    meal_code: str,
    value: dict[str, Any],
) -> dict[str, Any]:
    type_code = str(value['type_code'])
    option = {
        'external_id': str(
            value.get('external_id')
            or external_id(profile_code, service_date, meal_code, type_code)
        ),
        'type_code': type_code,
        'type_name': TYPE_NAMES[type_code],
        'title': str(value['title']).strip(),
        'description': str(value.get('description', '')).strip(),
        'components': [str(component).strip() for component in value.get('components', []) if str(component).strip()],
        'labels': [dict(label) for label in value.get('labels', [])],
        'allergens': [dict(allergen) for allergen in value.get('allergens', [])],
        'origins': [dict(origin) for origin in value.get('origins', [])],
        'note': str(value.get('note', '')).strip(),
        'allergen_review_status': str(value.get('allergen_review_status', 'not_checked')),
    }
    if profile_code == 'staff_guest':
        option['prices'] = {
            'internal_rappen': value['internal_rappen'],
            'external_rappen': value['external_rappen'],
            'currency': 'CHF',
        }
    return option


def build_snapshot(
    profile_code: str,
    draft: dict[str, Any],
    revision_code: str,
) -> dict[str, Any]:
    week_start = date.fromisoformat(str(draft['week_start']))
    values_by_date = {str(day['date']): day for day in draft['days']}
    days: list[dict[str, Any]] = []
    for offset, weekday in enumerate(WEEKDAYS):
        service_date = (week_start + timedelta(days=offset)).isoformat()
        source_day = values_by_date.get(service_date, {'services': []})
        services = []
        for value in source_day.get('services', []):
            meal_code = str(value['meal_code'])
            state = str(value['service_state'])
            options = []
            if state == 'open':
                options = [
                    _option(profile_code, service_date, meal_code, option)
                    for option in value['options']
                ]
            services.append(
                {
                    'meal_code': meal_code,
                    'meal_name': MEAL_NAMES[meal_code],
                    'service_state': state,
                    'options': options,
                }
            )
        notice = next(
            (
                str(service['notice']).strip()
                for service in source_day.get('services', [])
                if str(service.get('notice', '')).strip()
            ),
            '',
        )
        days.append(
            {
                'date': service_date,
                'weekday': weekday,
                'state': 'open' if any(service['service_state'] == 'open' for service in services) else 'closed',
                'notice': notice,
                'services': services,
            }
        )
    snapshot = {
        'schema_version': 1,
        'profile_code': profile_code,
        'channel': 'patienten' if profile_code == 'patient' else 'cafeteria',
        'revision_id': revision_code,
        'location': dict(draft['location']),
        'week_start': week_start.isoformat(),
        'week_end': (week_start + timedelta(days=6)).isoformat(),
        'title': str(draft['title']).strip(),
        'shared_note': str(draft['shared_note']).strip(),
        'days': days,
    }
    validate_snapshot_payload(profile_code, snapshot)
    return snapshot
