"""Bounded, lossless command normalization; source payloads stay separate."""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from .master_data_types import MasterDataNotFoundError, MasterDataValidationError
from .quantities import parse_factor


PROPOSAL_FIELDS = frozenset({'density_g_per_ml', 'piece_weight_g', 'category_code', 'allergens', 'labels'})


def plain(value: object, maximum: int = 120, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or any(unicodedata.category(c).startswith('C') or c in '<>' for c in value):
        raise MasterDataValidationError('Ungültige Textzeichen.')
    clean = ' '.join(unicodedata.normalize('NFC', value).split())
    if len(clean) > maximum or (required and not clean):
        raise MasterDataValidationError('Ungültige Textlänge.')
    return clean


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
        raise MasterDataNotFoundError('Objekt nicht gefunden.')
    return str(UUID(value))


def positive(value: object) -> int:
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise MasterDataValidationError('Ungültige Version.')
    return value


def code(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,15}', value):
        raise MasterDataValidationError('Ungültiger Fachcode.')
    return value


def factor(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, Decimal)):
        raise MasterDataValidationError('Ungültiger Umrechnungsfaktor.')
    try:
        return format(parse_factor(value), 'f')
    except ValueError:
        raise MasterDataValidationError('Ungültiger Umrechnungsfaktor.') from None


def bounded_list(value: object) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) > 64:
        raise MasterDataValidationError('Höchstens 64 Einträge erlaubt.')
    return list(value)


def normalize(payload: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or any(not isinstance(k, str) for k in payload):
        raise MasterDataValidationError('Ungültige Eingabefelder.')
    clean: dict[str, Any] = dict(payload)
    pin_fields = {'prepared_recipe_revision_public_id', 'prepared_recipe_content_hash_sha256'}
    if pin_fields & clean.keys():
        if not pin_fields <= clean.keys():
            raise MasterDataValidationError('Rezeptstand und Prüfsumme müssen gemeinsam angegeben werden.')
        revision, content_hash = (clean[key] for key in ('prepared_recipe_revision_public_id', 'prepared_recipe_content_hash_sha256'))
        if (revision is None) != (content_hash is None):
            raise MasterDataValidationError('Rezeptstand und Prüfsumme müssen gemeinsam angegeben werden.')
    for key, value in clean.items():
        if key in ('name', 'display_name'):
            clean[key] = plain(value)
        elif key in ('note', 'source_note', 'reason'):
            clean[key] = plain(value, 500, required=False)
        elif key == 'source_reference':
            clean[key] = plain(value, 200, required=False)
        elif key == 'source_url':
            clean[key] = plain(value, 2048, required=False)
            if clean[key] is not None and not re.match(r'^https?://', clean[key]):
                raise MasterDataValidationError('Ungültige Quellenadresse.')
        elif key in ('code', 'base_unit_code', 'category_code'):
            clean[key] = code(value)
        elif key in ('category_public_id', 'food_public_id'):
            clean[key] = identifier(value) if value is not None else None
        elif key == 'prepared_recipe_revision_public_id':
            clean[key] = identifier(value) if value is not None else None
        elif key == 'prepared_recipe_content_hash_sha256':
            if value is not None and (not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None):
                raise MasterDataValidationError('Ungültige Prüfsumme des Rezeptstands.')
        elif key in ('base_factor', 'density_g_per_ml', 'piece_weight_g'):
            clean[key] = factor(value)
        elif key in ('active', 'checked'):
            if type(value) is not bool:
                raise MasterDataValidationError('Ungültiger Status.')
        elif key == 'sort_order':
            if value is not None and (type(value) is not int or not 1 <= value <= 9999):
                raise MasterDataValidationError('Ungültige Reihenfolge.')
        elif key in ('tags', 'storage_locations'):
            clean[key] = sorted({identifier(item) for item in bounded_list(value)})
        elif key == 'storage_location_public_ids':
            items = [identifier(item) for item in bounded_list(value)]
            if not items or len(items) != len(set(items)):
                raise MasterDataValidationError('Mindestens einen Lagerort und keine doppelten Zuordnungen auswählen.')
            clean[key] = sorted(items)
        elif key == 'labels':
            clean[key] = sorted({code(item) for item in bounded_list(value)})
        elif key == 'allergens':
            entries: dict[str, str] = {}
            for item in bounded_list(value):
                if not isinstance(item, Mapping) or set(item) != {'code', 'presence'}:
                    raise MasterDataValidationError('Ungültige Allergendeklaration.')
                name, presence = code(item['code']), item['presence']
                if presence not in ('contains', 'may_contain') or (name in entries and entries[name] != presence):
                    raise MasterDataValidationError('Widersprüchliche Allergendeklaration.')
                entries[name] = presence
            clean[key] = [{'code': name, 'presence': presence} for name, presence in sorted(entries.items())]
        elif key == 'fields':
            entries_list = bounded_list(value)
            if not entries_list or any(not isinstance(item, str) or item not in PROPOSAL_FIELDS for item in entries_list):
                raise MasterDataValidationError('Vorschlagsfelder ausdrücklich auswählen.')
            clean[key] = sorted(set(entries_list))
        elif key == 'food_row_version':
            clean[key] = positive(value)
        elif key == 'fetched_at':
            if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
                raise MasterDataValidationError('Abrufzeit mit Zeitzone erforderlich.')
            clean[key] = value.isoformat() if isinstance(value, datetime) else None
        elif key == 'payload':
            clean[key] = proposal_payload(value)
    return clean


def proposal_payload(value: object) -> object:
    keys = 0
    def visit(item: object, depth: int) -> object:
        nonlocal keys
        if depth > 5:
            raise MasterDataValidationError('Vorschlag ist zu tief verschachtelt.')
        if isinstance(item, Mapping):
            keys += len(item)
            if keys > 200 or any(not isinstance(k, str) for k in item):
                raise MasterDataValidationError('Vorschlag hat zu viele Felder.')
            return {k: visit(v, depth + 1) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(v, depth + 1) for v in item]
        if isinstance(item, Decimal):
            if not item.is_finite():
                raise MasterDataValidationError('Nichtendliche Vorschlagszahl.')
            return format(item, 'f')
        if item is None or type(item) in (str, int, bool):
            return item
        raise MasterDataValidationError('Vorschlag muss verlustfreies JSON sein.')
    if not isinstance(value, Mapping):
        raise MasterDataValidationError('Vorschlag muss ein Objekt sein.')
    result = visit(value, 0)
    if len(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()) > 65536:
        raise MasterDataValidationError('Vorschlag überschreitet 64 KiB.')
    return result
