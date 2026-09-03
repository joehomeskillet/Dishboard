from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from .workflow import (
    MENU_TYPES,
    PROFILE_DAYS,
    PROFILE_MEALS,
    SERVICE_STATES,
    WorkflowValidationError,
)

_MODES = frozenset({'auto', 'manual'})
_ALLERGEN_PRESENCES = frozenset({'contains', 'may_contain'})
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_COUNTRY_CODE = re.compile(r'[A-Z]{2}')
_CHF = re.compile(r'\d+(?:[.,]\d+)?')

_MENU_REQUIRED = frozenset(
    '_csrf week day meal option row_version title allergen_mode origin_mode label_mode'.split()
)
_MENU_OPTIONAL = frozenset('description note'.split())
_MENU_REPEATED = frozenset(
    'component_public_id component_text allergen_code allergen_presence '
    'origin_ingredient origin_country_code label_code'.split()
)

_WEEKDAYS = (
    'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag',
    'Freitag', 'Samstag', 'Sonntag',
)
_MEAL_NAMES = {'LUNCH': 'Mittag', 'DINNER': 'Abend'}
_OPTION_NAMES = {'MENU_1': 'Menü 1', 'VEGGIE': 'Vegetarisch'}


@dataclass(frozen=True)
class ParsedWeekHeader:
    week_start: date
    expected_week_row_version: int
    payload: dict[str, object]


@dataclass(frozen=True)
class ParsedService:
    week_start: date
    day: str
    meal: str
    expected_service_row_version: int
    payload: dict[str, object]


@dataclass(frozen=True)
class ParsedMenuItem:
    week_start: date
    day: str
    meal: str
    option: str
    expected_item_row_version: int
    payload: dict[str, object]


def _values(form: Mapping[str, object], key: str) -> list[str]:
    getlist = getattr(form, 'getlist', None)
    if callable(getlist):
        values = list(getlist(key))
    else:
        value = form[key]
        values = list(value) if isinstance(value, (list, tuple)) else [value]
    if any(type(value) is not str for value in values):
        raise WorkflowValidationError(
            f'Formularfeld ist ungültig: {key}',
            field_name=key,
        )
    return values


def _validate_shape(
    form: Mapping[str, object],
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    repeated: frozenset[str] = frozenset(),
) -> None:
    keys = set(form.keys())
    non_string = next((key for key in keys if type(key) is not str), None)
    if non_string is not None:
        raise WorkflowValidationError('Formularfeldname ist ungültig.')
    unexpected = keys - required - optional - repeated
    if unexpected:
        field_name = sorted(unexpected)[0]
        raise WorkflowValidationError(
            f'Unzulässiges Formularfeld: {field_name}',
            field_name=field_name,
        )
    missing = required - keys
    if missing:
        field_name = sorted(missing)[0]
        raise WorkflowValidationError(
            f'Fehlendes Formularfeld: {field_name}',
            field_name=field_name,
        )
    for key in sorted(keys - repeated):
        if len(_values(form, key)) != 1:
            raise WorkflowValidationError(
                f'Formularfeld mehrfach gesendet: {key}',
                field_name=key,
            )


def _scalar(form: Mapping[str, object], key: str) -> str:
    return _values(form, key)[0]


def _repeated(form: Mapping[str, object], key: str) -> list[str]:
    return _values(form, key) if key in form else []


def _version(form: Mapping[str, object]) -> int:
    value = _scalar(form, 'row_version')
    if re.fullmatch(r'\d+', value) is None:
        raise WorkflowValidationError(
            'Versionsnummer muss eine nichtnegative ganze Zahl sein.',
            field_name='row_version',
        )
    return int(value, 10)


def _week(form: Mapping[str, object]) -> date:
    value = _scalar(form, 'week')
    if _ISO_DATE.fullmatch(value) is None:
        raise WorkflowValidationError('Woche muss YYYY-MM-DD sein.', field_name='week')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise WorkflowValidationError('Woche ist ungültig.', field_name='week') from error
    if parsed.isoweekday() != 1:
        raise WorkflowValidationError('Woche muss an einem Montag beginnen.', field_name='week')
    return parsed


def _slot(
    profile_code: str,
    form: Mapping[str, object],
    *,
    with_option: bool,
) -> tuple[date, date, str, str | None]:
    if profile_code not in PROFILE_DAYS:
        raise WorkflowValidationError('Unbekanntes Profil.', field_name='profile')
    week_start = _week(form)
    day_value = _scalar(form, 'day')
    if _ISO_DATE.fullmatch(day_value) is None:
        raise WorkflowValidationError('Tag muss YYYY-MM-DD sein.', field_name='day')
    try:
        service_day = date.fromisoformat(day_value)
    except ValueError as error:
        raise WorkflowValidationError('Tag ist ungültig.', field_name='day') from error
    day_index = (service_day - week_start).days
    if day_index not in range(PROFILE_DAYS[profile_code]):
        raise WorkflowValidationError('Tag liegt ausserhalb des Menürasters.', field_name='day')
    meal = _scalar(form, 'meal')
    if meal not in PROFILE_MEALS[profile_code]:
        raise WorkflowValidationError('Mahlzeit ist für dieses Profil ungültig.', field_name='meal')
    option = _scalar(form, 'option') if with_option else None
    if with_option and option not in MENU_TYPES:
        raise WorkflowValidationError('Menüoption ist ungültig.', field_name='option')
    return week_start, service_day, meal, option


def _context(service_day: date, meal: str, option: str) -> str:
    return f'{_WEEKDAYS[service_day.weekday()]}, {_MEAL_NAMES[meal]}, {_OPTION_NAMES[option]}'


def _item_error(context: str, detail: str, field_name: str) -> WorkflowValidationError:
    return WorkflowValidationError(f'{context}: {detail}', field_name=field_name)


def _paired(
    form: Mapping[str, object],
    left: str,
    right: str,
    context: str,
) -> tuple[list[str], list[str]]:
    left_values = _repeated(form, left)
    right_values = _repeated(form, right)
    if len(left_values) != len(right_values):
        raise _item_error(context, 'Zusammengehörige Felder sind unvollständig.', right)
    return left_values, right_values


def _assignments(form: Mapping[str, object], context: str) -> list[dict[str, str | None]]:
    public_ids, texts = _paired(form, 'component_public_id', 'component_text', context)
    result = []
    for public_id_raw, component_text in zip(public_ids, texts, strict=True):
        public_id = public_id_raw.strip()
        if public_id and component_text:
            raise _item_error(context, 'Komponente darf nur eine Auswahl enthalten.', 'component_text')
        if public_id:
            try:
                normalized_id = str(UUID(public_id))
            except (ValueError, AttributeError) as error:
                raise _item_error(context, 'Komponenten-ID ist ungültig.', 'component_public_id') from error
            result.append({'component_public_id': normalized_id, 'component_text': None})
            continue
        if component_text == '' or not component_text.strip(' '):
            raise _item_error(context, 'Freitext-Komponente ist leer.', 'component_text')
        result.append({'component_public_id': None, 'component_text': component_text})
    return result


def _manual_values(
    form: Mapping[str, object],
    mode: str,
    fields: tuple[str, ...],
    context: str,
) -> None:
    if mode == 'manual':
        return
    supplied = next((field for field in fields if field in form), None)
    if supplied is not None:
        raise _item_error(context, 'Feld ist nur im Modus manuell erlaubt.', supplied)


def _labels(form: Mapping[str, object], context: str) -> list[str]:
    result = []
    for raw in _repeated(form, 'label_code'):
        code = raw.strip()
        if not code:
            raise _item_error(context, 'Kennzeichnung ist leer.', 'label_code')
        result.append(code)
    return result


def _allergens(form: Mapping[str, object], context: str) -> list[dict[str, str]]:
    codes, presences = _paired(form, 'allergen_code', 'allergen_presence', context)
    result = []
    for raw_code, presence in zip(codes, presences, strict=True):
        code = raw_code.strip()
        if not code:
            raise _item_error(context, 'Allergen ist leer.', 'allergen_code')
        if presence not in _ALLERGEN_PRESENCES:
            raise _item_error(context, 'Allergen-Angabe ist ungültig.', 'allergen_presence')
        result.append({'code': code, 'presence': presence})
    return result


def _origins(form: Mapping[str, object], context: str) -> list[dict[str, str]]:
    ingredients, countries = _paired(
        form,
        'origin_ingredient',
        'origin_country_code',
        context,
    )
    result = []
    seen = set()
    for raw_ingredient, raw_country in zip(ingredients, countries, strict=True):
        ingredient = raw_ingredient.strip()
        country = raw_country.strip()
        if not ingredient:
            raise _item_error(context, 'Zutat für Herkunft fehlt.', 'origin_ingredient')
        if ingredient in seen:
            raise _item_error(
                context,
                f'Zutat {ingredient} ist doppelt erfasst.',
                'origin_ingredient',
            )
        if _COUNTRY_CODE.fullmatch(country) is None:
            raise _item_error(context, 'Ländercode muss zwei Grossbuchstaben haben.', 'origin_country_code')
        seen.add(ingredient)
        result.append({
            'ingredient': ingredient,
            'country_code': country,
            'text': f'{ingredient}: {country}',
        })
    return result


def _price(value: str, context: str, field_name: str) -> int:
    normalized = value.strip()
    if _CHF.fullmatch(normalized) is None:
        raise _item_error(context, 'Preis muss als CHF-Betrag eingegeben werden.', field_name)
    fraction = re.split(r'[.,]', normalized, maxsplit=1)
    if len(fraction) == 2 and len(fraction[1]) > 2:
        raise _item_error(context, 'Preis darf höchstens zwei Nachkommastellen haben.', field_name)
    amount = Decimal(normalized.replace(',', '.'))
    if amount <= 0:
        raise _item_error(context, 'Preis muss grösser als 0 sein.', field_name)
    return int(amount * 100)


def parse_week_header_form(
    profile_code: str,
    form: Mapping[str, object],
) -> ParsedWeekHeader:
    if profile_code not in PROFILE_DAYS:
        raise WorkflowValidationError('Unbekanntes Profil.', field_name='profile')
    _validate_shape(
        form,
        frozenset({'_csrf', 'week', 'row_version', 'title', 'shared_note'}),
    )
    week_start = _week(form)
    title = _scalar(form, 'title').strip()
    if not title:
        raise WorkflowValidationError('Wochentitel fehlt.', field_name='title')
    return ParsedWeekHeader(
        week_start=week_start,
        expected_week_row_version=_version(form),
        payload={'title': title, 'shared_note': _scalar(form, 'shared_note').strip()},
    )


def parse_service_form(
    profile_code: str,
    form: Mapping[str, object],
) -> ParsedService:
    _validate_shape(
        form,
        frozenset({'_csrf', 'week', 'day', 'meal', 'row_version', 'service_state', 'notice'}),
    )
    week_start, service_day, meal, _ = _slot(profile_code, form, with_option=False)
    state = _scalar(form, 'service_state')
    notice = _scalar(form, 'notice').strip()
    if state not in SERVICE_STATES:
        raise WorkflowValidationError('Service-Status ist ungültig.', field_name='service_state')
    if state != 'open' and not notice:
        prefix = f'{_WEEKDAYS[service_day.weekday()]}, {_MEAL_NAMES[meal]}'
        raise WorkflowValidationError(
            f'{prefix}: Geschlossener Service braucht einen Hinweis.',
            field_name='notice',
        )
    return ParsedService(
        week_start=week_start,
        day=service_day.isoformat(),
        meal=meal,
        expected_service_row_version=_version(form),
        payload={'service_state': state, 'notice': notice},
    )


def parse_menu_item_form(
    profile_code: str,
    form: Mapping[str, object],
) -> ParsedMenuItem:
    required = _MENU_REQUIRED
    if profile_code == 'staff_guest':
        required |= frozenset({'internal_chf', 'external_chf'})
    _validate_shape(form, required, _MENU_OPTIONAL, _MENU_REPEATED)
    week_start, service_day, meal, option_value = _slot(profile_code, form, with_option=True)
    if option_value is None:
        raise WorkflowValidationError('Menüoption fehlt.', field_name='option')
    context = _context(service_day, meal, option_value)
    title = _scalar(form, 'title').strip()
    if not title:
        raise _item_error(context, 'Menütitel fehlt.', 'title')
    modes = {
        field: _scalar(form, field)
        for field in ('allergen_mode', 'origin_mode', 'label_mode')
    }
    for field, mode in modes.items():
        if mode not in _MODES:
            raise _item_error(context, 'Modus muss auto oder manual sein.', field)
    _manual_values(form, modes['allergen_mode'], ('allergen_code', 'allergen_presence'), context)
    _manual_values(form, modes['origin_mode'], ('origin_ingredient', 'origin_country_code'), context)
    _manual_values(form, modes['label_mode'], ('label_code',), context)
    payload: dict[str, Any] = {
        'title': title,
        'description': _scalar(form, 'description').strip() if 'description' in form else '',
        'note': _scalar(form, 'note').strip() if 'note' in form else '',
        **modes,
        'assignments': _assignments(form, context),
        'labels': _labels(form, context) if modes['label_mode'] == 'manual' else [],
        'allergens': _allergens(form, context) if modes['allergen_mode'] == 'manual' else [],
        'origins': _origins(form, context) if modes['origin_mode'] == 'manual' else [],
    }
    if profile_code == 'staff_guest':
        payload['internal_rappen'] = _price(_scalar(form, 'internal_chf'), context, 'internal_chf')
        payload['external_rappen'] = _price(_scalar(form, 'external_chf'), context, 'external_chf')
        if payload['external_rappen'] < payload['internal_rappen']:
            raise _item_error(
                context,
                'Externer Preis darf nicht kleiner als interner Preis sein.',
                'external_chf',
            )
    return ParsedMenuItem(
        week_start=week_start,
        day=service_day.isoformat(),
        meal=meal,
        option=option_value,
        expected_item_row_version=_version(form),
        payload=payload,
    )
