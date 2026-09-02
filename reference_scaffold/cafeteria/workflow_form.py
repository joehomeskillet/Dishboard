from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from .workflow import (
    MENU_TYPES,
    PROFILE_DAYS,
    PROFILE_MEALS,
    SERVICE_STATES,
    WorkflowValidationError,
)

OPTIONAL_OPTION_SUFFIXES = frozenset({
    'labels',
    'allergen_contains',
    'allergen_may_contain',
    'origins',
    'allergen_reviewed',
})
MULTI_VALUE_OPTION_SUFFIXES = frozenset({
    'labels',
    'allergen_contains',
    'allergen_may_contain',
})


@dataclass(frozen=True)
class ParsedDraft:
    week_start: date
    row_version: int
    values: dict[str, Any]


def _field_names(profile_code: str) -> set[str]:
    names = {'_csrf', 'week_start', 'row_version', 'title', 'shared_note'}
    for day_index in range(PROFILE_DAYS[profile_code]):
        for meal_code in PROFILE_MEALS[profile_code]:
            service = f'service_{day_index}_{meal_code}'
            names |= {f'{service}_state', f'{service}_notice'}
            for type_code in MENU_TYPES:
                option = f'{service}_{type_code}'
                names |= {
                    f'{option}_title',
                    f'{option}_components',
                }
                if profile_code == 'staff_guest':
                    names |= {f'{option}_internal_rappen', f'{option}_external_rappen'}
    return names


def _optional_field_names(profile_code: str) -> set[str]:
    names = set()
    for day_index in range(PROFILE_DAYS[profile_code]):
        for meal_code in PROFILE_MEALS[profile_code]:
            service = f'service_{day_index}_{meal_code}'
            for type_code in MENU_TYPES:
                option = f'{service}_{type_code}'
                names |= {f'{option}_{suffix}' for suffix in OPTIONAL_OPTION_SUFFIXES}
    return names


def _form_value(form: Mapping[str, str], key: str) -> str:
    if hasattr(form, 'getlist'):
        return ','.join(str(value) for value in form.getlist(key))
    return str(form[key])


def _single_values(profile_code: str, form: Mapping[str, str]) -> dict[str, str]:
    multi_value_fields = {
        field
        for field in _optional_field_names(profile_code)
        if any(field.endswith(f'_{suffix}') for suffix in MULTI_VALUE_OPTION_SUFFIXES)
    }
    if hasattr(form, 'getlist'):
        for key in form:
            if len(form.getlist(key)) != 1 and key not in multi_value_fields:
                raise WorkflowValidationError(
                    f'Formularfeld mehrfach gesendet: {key}',
                    field_name=key,
                )
    return {key: _form_value(form, key) for key in form}


def _positive_integer(value: str, label: str, field_name: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as error:
        raise WorkflowValidationError(
            f'{label} muss eine ganze Zahl sein.',
            field_name=field_name,
        ) from error
    if parsed <= 0:
        raise WorkflowValidationError(
            f'{label} muss positiv sein.',
            field_name=field_name,
        )
    return parsed


def _parse_origins(value: str) -> list[dict[str, str]]:
    """Parse origin declarations from format 'Ingredient=CountryCode|...'"""
    origins = []
    if not value.strip():
        return origins

    for declaration in value.split('|'):
        declaration = declaration.strip()
        if not declaration:
            continue
        if declaration.count('=') != 1:
            raise ValueError('Herkunftsangabe ist ungültig.')
        ingredient, country_code = declaration.rsplit('=', 1)
        ingredient = ingredient.strip()
        country_code = country_code.strip()
        if not ingredient or re.fullmatch(r'[A-Z]{2}', country_code) is None:
            raise ValueError('Herkunftsangabe ist ungültig.')
        origins.append({
            'ingredient': ingredient,
            'country_code': country_code,
            'text': declaration,
        })
    return origins


def submitted_form_values(
    profile_code: str,
    form: Mapping[str, str],
) -> dict[str, str]:
    expected = _field_names(profile_code)
    optional_fields = _optional_field_names(profile_code)
    result = {key: _form_value(form, key) for key in expected if key in form}
    for key in form:
        if key in optional_fields and key not in result:
            result[key] = _form_value(form, key)
    return result


def parse_draft_form(profile_code: str, form: Mapping[str, str]) -> ParsedDraft:
    if profile_code not in PROFILE_MEALS:
        raise WorkflowValidationError('Unbekanntes Profil.')
    supplied = _single_values(profile_code, form)
    expected = _field_names(profile_code)
    optional_fields = _optional_field_names(profile_code)
    unexpected = set(supplied) - expected - optional_fields
    if unexpected:
        raise WorkflowValidationError(f'Unzulässiges Formularfeld: {sorted(unexpected)[0]}')
    missing = expected - set(supplied)
    if missing:
        field_name = sorted(missing)[0]
        raise WorkflowValidationError(
            f'Fehlendes Formularfeld: {field_name}',
            field_name=field_name,
        )
    try:
        week_start = date.fromisoformat(supplied['week_start'])
    except ValueError as error:
        raise WorkflowValidationError(
            'Wochenbeginn ist ungültig.',
            field_name='week_start',
        ) from error
    if week_start.isoweekday() != 1:
        raise WorkflowValidationError(
            'Wochenbeginn muss ein Montag sein.',
            field_name='week_start',
        )
    row_version = _positive_integer(
        supplied['row_version'],
        'Versionsnummer',
        'row_version',
    )
    if not supplied['title'].strip():
        raise WorkflowValidationError(
            'Wochentitel fehlt.',
            field_name='title',
        )
    days = []
    for day_index in range(PROFILE_DAYS[profile_code]):
        services = []
        for meal_code in PROFILE_MEALS[profile_code]:
            service_prefix = f'service_{day_index}_{meal_code}'
            state_field = f'{service_prefix}_state'
            notice_field = f'{service_prefix}_notice'
            service_state = supplied[state_field]
            if service_state not in SERVICE_STATES:
                raise WorkflowValidationError(
                    'Unzulässiger Schliessungsstatus.',
                    field_name=state_field,
                )
            notice = supplied[notice_field].strip()
            if service_state != 'open' and not notice:
                raise WorkflowValidationError(
                    'Geschlossene Mahlzeit braucht einen Hinweis.',
                    field_name=notice_field,
                )
            options = []
            for type_code in MENU_TYPES:
                option_prefix = f'{service_prefix}_{type_code}'
                title_field = f'{option_prefix}_title'
                components_field = f'{option_prefix}_components'
                labels_field = f'{option_prefix}_labels'
                allergen_contains_field = f'{option_prefix}_allergen_contains'
                allergen_may_contain_field = f'{option_prefix}_allergen_may_contain'
                origins_field = f'{option_prefix}_origins'
                allergen_reviewed_field = f'{option_prefix}_allergen_reviewed'

                title = supplied[title_field].strip()
                if service_state == 'open' and not title:
                    raise WorkflowValidationError(
                        'Offenes Menü braucht einen Titel.',
                        field_name=title_field,
                    )
                option: dict[str, Any] = {
                    'type_code': type_code,
                    'title': title,
                    'components': [
                        line.strip()
                        for line in supplied[components_field].splitlines()
                        if line.strip()
                    ],
                }

                # Parse labels (optional, comma-separated codes)
                labels_str = supplied.get(labels_field, '').strip()
                if labels_str:
                    label_codes = [code.strip() for code in labels_str.split(',') if code.strip()]
                    if label_codes:
                        option['labels'] = [{'code': code, 'name': code} for code in label_codes]

                # Parse allergens - optional
                allergen_contains_str = supplied.get(allergen_contains_field, '').strip()
                allergen_may_contain_str = supplied.get(allergen_may_contain_field, '').strip()
                allergens = []
                if allergen_contains_str:
                    contains_codes = [code.strip() for code in allergen_contains_str.split(',') if code.strip()]
                    for code in contains_codes:
                        allergens.append({'code': code, 'name': code, 'presence': 'contains'})
                if allergen_may_contain_str:
                    may_contain_codes = [code.strip() for code in allergen_may_contain_str.split(',') if code.strip()]
                    for code in may_contain_codes:
                        allergens.append({'code': code, 'name': code, 'presence': 'may_contain'})
                if allergens:
                    option['allergens'] = allergens

                # Parse origins - optional
                origins_str = supplied.get(origins_field, '').strip()
                if origins_str:
                    try:
                        option['origins'] = _parse_origins(origins_str)
                    except ValueError as error:
                        raise WorkflowValidationError(
                            str(error),
                            field_name=origins_field,
                        ) from error

                # "checked" is persisted canonically; retain the old UI value while forms migrate.
                allergen_reviewed = supplied.get(allergen_reviewed_field, '').lower() in {
                    'on',
                    'checked',
                    'reviewed',
                }
                option['allergen_review_status'] = 'checked' if allergen_reviewed else 'not_checked'

                if profile_code == 'staff_guest':
                    if service_state == 'open':
                        internal_field = f'{option_prefix}_internal_rappen'
                        external_field = f'{option_prefix}_external_rappen'
                        option['internal_rappen'] = _positive_integer(
                            supplied[internal_field],
                            'Mitarbeitendenbetrag',
                            internal_field,
                        )
                        option['external_rappen'] = _positive_integer(
                            supplied[external_field],
                            'Gästebetrag',
                            external_field,
                        )
                        if option['external_rappen'] < option['internal_rappen']:
                            raise WorkflowValidationError(
                                'Gästebetrag darf nicht kleiner als Mitarbeitendenbetrag sein.',
                                field_name=external_field,
                            )
                    else:
                        option['internal_rappen'] = supplied[f'{option_prefix}_internal_rappen']
                        option['external_rappen'] = supplied[f'{option_prefix}_external_rappen']
                options.append(option)
            services.append(
                {
                    'meal_code': meal_code,
                    'service_state': service_state,
                    'notice': notice,
                    'options': options,
                }
            )
        days.append(
            {
                'date': (week_start + timedelta(days=day_index)).isoformat(),
                'services': services,
            }
        )
    return ParsedDraft(
        week_start=week_start,
        row_version=row_version,
        values={
            'title': supplied['title'].strip(),
            'shared_note': supplied['shared_note'].strip(),
            'days': days,
        },
    )
