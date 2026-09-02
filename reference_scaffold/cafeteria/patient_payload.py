from __future__ import annotations

import re
import unicodedata
from typing import Any

PROFILES = {'patient', 'staff_guest'}
PATIENT_OBJECT_KEYS = {
    'snapshot': frozenset({
        'schema_version', 'profile_code', 'channel', 'revision_id', 'location',
        'week_start', 'week_end', 'title', 'shared_note', 'days',
    }),
    'location': frozenset({'code', 'name'}),
    'day': frozenset({'date', 'weekday', 'state', 'notice', 'services'}),
    'service': frozenset({'meal_code', 'meal_name', 'options'}),
    'option': frozenset({
        'external_id', 'type_code', 'type_name', 'title', 'description',
        'components', 'labels', 'allergens', 'origins', 'note',
        'allergen_review_status',
    }),
    'label': frozenset({'code', 'name'}),
    'allergen': frozenset({'code', 'name', 'presence'}),
    'origin': frozenset({'ingredient', 'country_code', 'text'}),
}
PATIENT_OPTIONAL_KEYS = {'service': frozenset({'service_state'})}
PATIENT_ALLOWED_COMPACT_KEYS = frozenset(
    key.replace('_', '')
    for keys in (*PATIENT_OBJECT_KEYS.values(), *PATIENT_OPTIONAL_KEYS.values())
    for key in keys
)
PATIENT_LABEL_CODES = frozenset({'VEGETARIAN', 'VEGAN', 'LACTOSE_FREE', 'GLUTEN_FREE'})
PATIENT_ALLERGEN_CODES = frozenset({
    'GLUTEN', 'CRUSTACEANS', 'EGGS', 'FISH', 'PEANUTS', 'SOY', 'MILK',
    'NUTS', 'CELERY', 'MUSTARD', 'SESAME', 'SULPHITES', 'LUPIN', 'MOLLUSCS',
})
PATIENT_WEEKDAYS = frozenset({
    'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag',
})
PATIENT_FIXED_VALUES = {
    ('snapshot', 'profile_code'): frozenset({'patient'}),
    ('snapshot', 'channel'): frozenset({'patienten'}),
    ('day', 'weekday'): PATIENT_WEEKDAYS,
    ('day', 'state'): frozenset({'open', 'closed'}),
    ('service', 'meal_code'): frozenset({'LUNCH', 'DINNER'}),
    ('service', 'meal_name'): frozenset({'Mittag', 'Abend'}),
    ('service', 'service_state'): frozenset({'open', 'closed', 'holiday', 'company_holiday'}),
    ('option', 'type_code'): frozenset({'MENU_1', 'VEGGIE'}),
    ('option', 'type_name'): frozenset({'Menü 1', 'Vegetarisch'}),
    ('option', 'allergen_review_status'): frozenset({'not_checked', 'checked'}),
    ('label', 'code'): PATIENT_LABEL_CODES,
    ('allergen', 'code'): PATIENT_ALLERGEN_CODES,
    ('allergen', 'presence'): frozenset({'contains', 'may_contain'}),
}
PATIENT_ISO_DATE_RE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
PATIENT_REVISION_RE = re.compile(r'^PAT-[0-9]{4}-KW(?:0[1-9]|[1-4][0-9]|5[0-3])-R[1-9][0-9]*$')
PATIENT_EXTERNAL_ID_RE = re.compile(
    r'^PATIENT-[0-9]{4}-[0-9]{2}-[0-9]{2}-(?:LUNCH|DINNER)-(?:1|2)$'
)
PATIENT_LOCATION_CODE_RE = re.compile(r'^[A-Z][A-Z_]{1,31}$')
PATIENT_COUNTRY_CODE_RE = re.compile(r'^[A-Z]{2}$')
PATIENT_STRUCTURAL_PATTERNS = {
    ('snapshot', 'revision_id'): PATIENT_REVISION_RE,
    ('snapshot', 'week_start'): PATIENT_ISO_DATE_RE,
    ('snapshot', 'week_end'): PATIENT_ISO_DATE_RE,
    ('location', 'code'): PATIENT_LOCATION_CODE_RE,
    ('day', 'date'): PATIENT_ISO_DATE_RE,
    ('option', 'external_id'): PATIENT_EXTERNAL_ID_RE,
    ('origin', 'country_code'): PATIENT_COUNTRY_CODE_RE,
}
PATIENT_MONTH = (
    r'(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)'
)
PATIENT_WEEK_TITLE_RE = re.compile(
    rf'^(?:[1-9]|[12][0-9]|3[01])\. {PATIENT_MONTH} bis '
    rf'(?:[1-9]|[12][0-9]|3[01])\. {PATIENT_MONTH}$'
)
PATIENT_OPERATIONAL_NOTE_RE = re.compile(
    r'^(?:ausgabe(?: (?:ab|bis))?|serviert um|therapie um|mitternacht) '
    r'(?:[01][0-9]|2[0-3])[.:][0-5][0-9] uhr$'
)
PATIENT_LATIN_ASCII_FOLDS = (
    ('ı', 'i'), ('æ', 'ae'), ('œ', 'oe'), ('ø', 'o'), ('å', 'a'),
    ('ł', 'l'), ('đ', 'd'), ('ð', 'd'), ('þ', 'th'),
)
PATIENT_SENSITIVE_STEMS = (
    'preis', 'price', 'pricing', 'kosten', 'kostet', 'gebuhr', 'gebuehr',
    'tarif', 'zuschlag', 'pauschal', 'entgelt', 'selbstzahl', 'eigenanteil',
    'verrechn', 'berechn', 'inklusiv', 'inkludier', 'inbegriffen', 'cost',
    'charg', 'amount', 'currenc', 'bill', 'payabl', 'payment', 'includ', 'cout',
    'supplement', 'montant', 'factur', 'payant', 'paiement', 'prezz', 'importo',
    'pagat', 'compres', 'chf', 'rappen', 'franken', 'stutz', 'rappli', 'raeppli',
    'frankli', 'fraenkli', 'betrag', 'wahrung', 'waehrung', 'zahlung',
)
PATIENT_SENSITIVE_EXACT = frozenset({
    'betrag', 'betrage', 'bezahlt', 'bezahlung', 'zahlung', 'zahlbar', 'wahrung',
    'waehrung', 'intern', 'interne', 'internen', 'interner', 'internes',
    'internal', 'extern', 'externe', 'externen', 'externer', 'externes',
    'external', 'fee', 'fees', 'rate', 'rates', 'rated', 'rating', 'paid',
    'prix', 'frais', 'devise', 'monnaie', 'paye', 'inclus', 'incluse',
    'incluses', 'compris', 'comprise', 'valuta', 'incluso', 'inclusa', 'gratis',
    'chf', 'fr', 'frs', 'sfr', 'rp', 'rappen', 'franken', 'stutz', 'rappli',
    'raeppli', 'frankli', 'fraenkli', 'eur', 'euro', 'euros', 'usd', 'gbp',
    'cad', 'aud', 'jpy', 'cny', 'sek', 'nok', 'dkk',
})
PATIENT_MAX_SEMANTIC_FORM_LENGTH = 64
PATIENT_UNSAFE_BIDI_CLASSES = frozenset({'LRE', 'RLE', 'LRO', 'RLO', 'PDF', 'LRI', 'RLI', 'FSI', 'PDI'})


def _normalise_decimal_digits(value: str) -> str:
    return ''.join(
        str(unicodedata.decimal(character)) if character.isdecimal() else character
        for character in value
    )


def _normalise_patient_text(value: str) -> str:
    normalised = _normalise_decimal_digits(unicodedata.normalize('NFKC', value))
    skeleton = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', normalised).casefold()
    for source, target in PATIENT_LATIN_ASCII_FOLDS:
        skeleton = skeleton.replace(source, target)
    return ''.join(
        ch for ch in unicodedata.normalize('NFKD', skeleton)
        if not unicodedata.category(ch).startswith('M')
    )


def _patient_ascii_skeleton(value: str) -> str | None:
    pieces: list[str] = []
    for character in value:
        if not character.isascii() and character.isalnum():
            return None
        pieces.append(character if character.isascii() else ' ')
    return ''.join(pieces)


def _patient_semantic_tokens(value: str) -> list[str]:
    return ''.join(
        ch if ch.isalnum() else ' '
        for ch in value
        if not unicodedata.category(ch).startswith('M')
    ).split()


def _patient_form_is_sensitive(form: str) -> bool:
    for safe_food_lexeme in ('preiselbeer', 'costine', 'aufbewahrung'):
        form = form.replace(safe_food_lexeme, '')
    ascii_il_skeleton = re.sub(r'[il]+', 'i', form)
    short_chf_skeleton = form.replace('i', '').replace('l', '')
    return (
        form in PATIENT_SENSITIVE_EXACT
        or form.startswith(('pric', 'surcharg'))
        or any(stem in form for stem in PATIENT_SENSITIVE_STEMS)
        or any(stem in ascii_il_skeleton for stem in ('price', 'pricing'))
        or len(form) <= 5 and short_chf_skeleton == 'chf'
    )


def _patient_tokens_contain_sensitive_lexeme(tokens: list[str]) -> bool:
    if any(_patient_form_is_sensitive(token) for token in tokens):
        return True
    for start in range(len(tokens)):
        joined = tokens[start]
        for token in tokens[start + 1:]:
            joined += token
            if len(joined) > PATIENT_MAX_SEMANTIC_FORM_LENGTH:
                break
            if _patient_form_is_sensitive(joined):
                return True
    return False


def _patient_text_is_forbidden(value: str, *, allow_operational_time: bool = False) -> bool:
    if any(
        unicodedata.category(ch) == 'Cf' or unicodedata.bidirectional(ch) in PATIENT_UNSAFE_BIDI_CLASSES
        for ch in value
    ):
        return True
    if any(character.isnumeric() and not character.isdecimal() for character in value):
        return True
    nfkc_text = unicodedata.normalize('NFKC', value)
    if any(unicodedata.category(ch) == 'Sc' for text in (value, nfkc_text) for ch in text):
        return True
    ascii_text = _patient_ascii_skeleton(_normalise_patient_text(value))
    if ascii_text is None:
        return True
    if any(character.isnumeric() for character in ascii_text):
        operational_note = _normalise_decimal_digits(nfkc_text).casefold()
        return not (allow_operational_time and PATIENT_OPERATIONAL_NOTE_RE.fullmatch(operational_note))
    return _patient_tokens_contain_sensitive_lexeme(_patient_semantic_tokens(ascii_text))


def _patient_scalar_is_invalid(kind: str, key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return True
    fixed_values = PATIENT_FIXED_VALUES.get((kind, key))
    if fixed_values is not None:
        return value not in fixed_values
    pattern = PATIENT_STRUCTURAL_PATTERNS.get((kind, key))
    if pattern is not None:
        return pattern.fullmatch(value) is None
    if kind == 'snapshot' and key == 'title' and PATIENT_WEEK_TITLE_RE.fullmatch(value):
        return False
    return _patient_text_is_forbidden(
        value,
        allow_operational_time=kind == 'option' and key == 'note',
    )


def _patient_list_paths(value: Any, item_kind: str, path: str) -> list[str]:
    if not isinstance(value, list):
        return [path]
    found: list[str] = []
    for index, item in enumerate(value):
        item_path = f'{path}[{index}]'
        if item_kind == 'text':
            if not isinstance(item, str) or _patient_text_is_forbidden(item):
                found.append(item_path)
        else:
            found.extend(_patient_object_paths(item, item_kind, item_path))
    return found


def _patient_object_paths(value: Any, kind: str, path: str) -> list[str]:
    if not isinstance(value, dict):
        return [path]

    expected_keys = PATIENT_OBJECT_KEYS[kind]
    optional_keys = PATIENT_OPTIONAL_KEYS.get(kind, frozenset())
    allowed_keys = expected_keys | optional_keys
    actual_keys = set(value)
    found = [f'{path}.{key}' for key in sorted(expected_keys - actual_keys)]
    found.extend(f'{path}.{key}' for key in sorted(actual_keys - allowed_keys, key=str))

    for key in allowed_keys & actual_keys:
        child = value[key]
        child_path = f'{path}.{key}'
        if kind == 'snapshot' and key == 'schema_version':
            if type(child) is not int or child < 1:
                found.append(child_path)
        elif kind == 'snapshot' and key == 'location':
            found.extend(_patient_object_paths(child, 'location', child_path))
        elif kind == 'snapshot' and key == 'days':
            found.extend(_patient_list_paths(child, 'day', child_path))
        elif kind == 'day' and key == 'services':
            found.extend(_patient_list_paths(child, 'service', child_path))
        elif kind == 'service' and key == 'options':
            found.extend(_patient_list_paths(child, 'option', child_path))
        elif kind == 'option' and key == 'components':
            found.extend(_patient_list_paths(child, 'text', child_path))
        elif kind == 'option' and key == 'labels':
            found.extend(_patient_list_paths(child, 'label', child_path))
        elif kind == 'option' and key == 'allergens':
            found.extend(_patient_list_paths(child, 'allergen', child_path))
        elif kind == 'option' and key == 'origins':
            found.extend(_patient_list_paths(child, 'origin', child_path))
        elif _patient_scalar_is_invalid(kind, key, child):
            found.append(child_path)
    return found


def _normalize_patient_key(key: str) -> str:
    without_format_chars = ''.join(char for char in key if unicodedata.category(char) != 'Cf')
    return re.sub(r'[^A-Za-z0-9]+', '', without_format_chars).lower()


def _forbidden_patient_key_paths(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if _normalize_patient_key(key) not in PATIENT_ALLOWED_COMPACT_KEYS:
                found.append(f'{path}.{key}')
            found.extend(_forbidden_patient_key_paths(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_patient_key_paths(child, f'{path}[{index}]'))
    return found


def _forbidden_patient_paths(value: Any, path: str = '$') -> list[str]:
    return _patient_object_paths(value, 'snapshot', path)


def _validate_service_states(services: list[Any]) -> None:
    for service in services:
        if not isinstance(service, dict):
            raise ValueError('Service-Eintrag im Snapshot ist ungültig.')
        state = service.get('service_state', 'open')
        if state not in {'open', 'closed', 'holiday', 'company_holiday'}:
            raise ValueError('service_state muss open, closed, holiday oder company_holiday sein.')
        options = service.get('options')
        if not isinstance(options, list):
            raise ValueError('Jede Mahlzeit braucht ein Options-Array.')
        if state == 'open' and len(options) != 2:
            raise ValueError('Eine offene Mahlzeit braucht genau zwei Menüoptionen.')
        if state != 'open' and options:
            raise ValueError('Eine geschlossene Mahlzeit darf keine Gerichte enthalten.')


def validate_snapshot_payload(profile_code: str, snapshot: dict[str, Any]) -> None:
    if profile_code not in PROFILES:
        raise ValueError('Unbekanntes Profil.')
    if snapshot.get('profile_code') != profile_code:
        raise ValueError('Snapshot-Profil stimmt nicht mit dem angeforderten Kanal überein.')
    days = snapshot.get('days')
    if not isinstance(days, list) or len(days) != 7:
        raise ValueError('Snapshot muss sieben Tage enthalten.')
    if profile_code == 'patient':
        key_paths = _forbidden_patient_key_paths(snapshot)
        if key_paths:
            raise ValueError('Patienten-Snapshot enthält unzulässige Kostenschlüssel: ' + ', '.join(key_paths[:5]))
        paths = _forbidden_patient_paths(snapshot)
        if paths:
            raise ValueError('Patienten-Snapshot enthält unzulässige Kostenwerte: ' + ', '.join(paths[:5]))
        for day in days:
            services = day.get('services', [])
            meals = {service.get('meal_code') for service in services}
            if meals != {'LUNCH', 'DINNER'}:
                raise ValueError(f"Patiententag {day.get('date')} ist unvollständig.")
            _validate_service_states(services)
    else:
        services = [service for day in days for service in day.get('services', [])]
        if len(services) != 5 or any(service.get('meal_code') != 'LUNCH' for service in services):
            raise ValueError('Cafeteria-Snapshot muss fünf Mittagsservices enthalten.')
        _validate_service_states(services)
        for service in services:
            if service.get('service_state', 'open') != 'open':
                continue
            for option in service.get('options', []):
                costs = option.get('prices')
                if not isinstance(costs, dict) or not {'internal_rappen', 'external_rappen'} <= set(costs):
                    raise ValueError('Cafeteria-Menü ohne vollständige Kostenstruktur.')
                if type(costs.get('internal_rappen')) is not int or type(costs.get('external_rappen')) is not int:
                    raise ValueError('Cafeteria-Rappenbeträge müssen JSON-Ganzzahlen sein.')
