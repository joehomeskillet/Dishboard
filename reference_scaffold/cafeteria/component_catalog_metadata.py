from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, text


AllergenPresence = Literal['contains', 'may_contain']
AllergenInput = tuple[str, AllergenPresence]
_LABEL_CODE = re.compile(r'[A-Z0-9_]{2,32}')
_ALLERGEN_CODE = re.compile(r'[A-Z0-9_]{1,32}')
_PRESENCES = frozenset({'contains', 'may_contain'})
_CATEGORIES = ('meat', 'side', 'vegetable', 'sauce', 'dessert', 'other')
_COUNTRY_PATTERN = re.compile(r'[A-Z]{2}')
_MAX_METADATA_ENTRIES = 64


class MetadataValidationError(ValueError):
    pass


class MetadataContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedMetadata:
    label_codes: tuple[str, ...]
    allergens: tuple[AllergenInput, ...]


@dataclass(frozen=True)
class ResolvedMetadata:
    labels: tuple[tuple[int, str], ...]
    allergens: tuple[tuple[int, str, AllergenPresence], ...]
    current_label_ids: tuple[int, ...]
    current_allergens: tuple[tuple[int, AllergenPresence], ...]

    @property
    def desired_label_ids(self) -> tuple[int, ...]:
        return tuple(row[0] for row in self.labels)

    @property
    def desired_allergens(self) -> tuple[tuple[int, AllergenPresence], ...]:
        return tuple((row[0], row[2]) for row in self.allergens)

    @property
    def changed(self) -> bool:
        return (
            self.desired_label_ids != self.current_label_ids
            or self.desired_allergens != self.current_allergens
        )


def normalize_metadata(label_codes: object, allergens: object) -> NormalizedMetadata:
    labels = _normalize_label_codes(label_codes)
    allergen_pairs = _normalize_allergens(allergens)
    return NormalizedMetadata(labels, allergen_pairs)


def positive_integer(value: object, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise MetadataValidationError(f'Ungültiges Feld: {field_name}.')
    return value


def category(value: object) -> str:
    if type(value) is not str or value not in _CATEGORIES:
        raise MetadataValidationError('Ungültige Kategorie.')
    return value


def component_name(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise MetadataValidationError('Name darf nicht leer sein.')
    return value.strip()


def origin_country_code(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise MetadataValidationError('Ungültiges Herkunftsland.')
    if not value.strip():
        return None
    if _COUNTRY_PATTERN.fullmatch(value) is None:
        raise MetadataValidationError('Herkunftsland muss ein ISO-Ländercode sein.')
    return value


def escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def public_component(
    row: Mapping[str, object],
    metadata: tuple[list[dict[str, str]], list[dict[str, str]]],
) -> dict[str, object]:
    return {
        'public_id': str(row['public_id']),
        'profile_scope': str(row['profile_scope']),
        'category': str(row['category']),
        'name': str(row['name']),
        'origin_country_code': row['origin_country_code'],
        'active': bool(row['active']),
        'row_version': int(row['row_version']),
        'usage_count': int(row['usage_count']),
        'labels': metadata[0],
        'allergens': metadata[1],
    }


def resolve_metadata(
    connection: Connection,
    component_id: int,
    metadata: NormalizedMetadata,
) -> ResolvedMetadata:
    requested_labels = set(metadata.label_codes)
    requested_allergens = {code for code, _presence in metadata.allergens}
    master_rows = connection.execute(text(
        '''SELECT master_kind, master_id, code, active
           FROM cafeteria.lock_component_metadata_masters(
               CAST(:label_codes AS text[]), CAST(:allergen_codes AS text[])
           )'''
    ), {
        'label_codes': list(metadata.label_codes),
        'allergen_codes': [code for code, _presence in metadata.allergens],
    }).mappings().all()
    masters: dict[tuple[str, str], object] = {}
    for row in master_rows:
        kind = str(row['master_kind'])
        code = str(row['code'])
        if kind not in {'label', 'allergen'}:
            raise MetadataContractError('Unbekannte Metadaten-Masterart.')
        key = (kind, code)
        if key in masters:
            raise MetadataContractError('Doppelter Metadaten-Mastervertrag.')
        expected = requested_labels if kind == 'label' else requested_allergens
        if code not in expected:
            raise MetadataContractError('Unerwarteter Metadaten-Mastervertrag.')
        masters[key] = row
    returned_labels = {code for kind, code in masters if kind == 'label'}
    returned_allergens = {code for kind, code in masters if kind == 'allergen'}
    if returned_labels != requested_labels:
        raise MetadataValidationError('Unbekanntes Ernährungslabel.')
    if returned_allergens != requested_allergens:
        raise MetadataValidationError('Unbekanntes Allergen.')

    current_label_ids = tuple(int(value) for value in connection.execute(text(
        '''SELECT label_id FROM cafeteria.component_labels
           WHERE component_id=:component_id ORDER BY label_id'''
    ), {'component_id': component_id}).scalars())
    current_allergens = tuple(
        (int(row.allergen_id), str(row.presence))
        for row in connection.execute(text(
            '''SELECT allergen_id, presence FROM cafeteria.component_allergens
               WHERE component_id=:component_id ORDER BY allergen_id, presence'''
        ), {'component_id': component_id})
    )

    desired_labels: list[tuple[int, str]] = []
    for code in metadata.label_codes:
        master = masters[('label', code)]
        label_id = int(master['master_id'])
        if not bool(master['active']) and label_id not in current_label_ids:
            raise MetadataValidationError('Inaktives Ernährungslabel kann nicht hinzugefügt werden.')
        desired_labels.append((label_id, code))

    desired_allergens: list[tuple[int, str, AllergenPresence]] = []
    for code, presence in metadata.allergens:
        master = masters[('allergen', code)]
        allergen_id = int(master['master_id'])
        if not bool(master['active']) and (allergen_id, presence) not in current_allergens:
            raise MetadataValidationError('Inaktives Allergen kann nicht hinzugefügt oder geändert werden.')
        desired_allergens.append((allergen_id, code, presence))

    desired_labels.sort(key=lambda row: row[0])
    desired_allergens.sort(key=lambda row: (row[0], row[2]))
    return ResolvedMetadata(
        tuple(desired_labels), tuple(desired_allergens), current_label_ids, current_allergens
    )


def replace_metadata(
    connection: Connection,
    component_id: int,
    metadata: ResolvedMetadata,
) -> None:
    if not metadata.changed:
        return
    connection.execute(
        text('DELETE FROM cafeteria.component_labels WHERE component_id=:component_id'),
        {'component_id': component_id},
    )
    if metadata.labels:
        connection.execute(
            text('''INSERT INTO cafeteria.component_labels(component_id, label_id)
                    VALUES (:component_id, :master_id)'''),
            [
                {'component_id': component_id, 'master_id': row[0]}
                for row in metadata.labels
            ],
        )
    connection.execute(
        text('DELETE FROM cafeteria.component_allergens WHERE component_id=:component_id'),
        {'component_id': component_id},
    )
    if metadata.allergens:
        connection.execute(
            text('''INSERT INTO cafeteria.component_allergens(
                        component_id, allergen_id, presence
                    ) VALUES (:component_id, :master_id, :presence)'''),
            [
                {'component_id': component_id, 'master_id': row[0], 'presence': row[2]}
                for row in metadata.allergens
            ],
        )


def load_public_metadata(
    connection: Connection,
    component_ids: Sequence[int],
) -> dict[int, tuple[list[dict[str, str]], list[dict[str, str]]]]:
    if not component_ids:
        return {}
    ids = list(component_ids)
    result = {component_id: ([], []) for component_id in ids}
    label_rows = connection.execute(text(
        '''SELECT cl.component_id, dl.code, dl.display_name
           FROM cafeteria.component_labels cl
           JOIN cafeteria.dietary_labels dl ON dl.id=cl.label_id
           WHERE cl.component_id=ANY(CAST(:component_ids AS bigint[]))
           ORDER BY cl.component_id, dl.code, dl.display_name'''
    ), {'component_ids': ids}).mappings()
    for row in label_rows:
        result[int(row['component_id'])][0].append(
            {'code': str(row['code']), 'name': str(row['display_name'])}
        )
    allergen_rows = connection.execute(text(
        '''SELECT ca.component_id, a.code, a.display_name, ca.presence
           FROM cafeteria.component_allergens ca
           JOIN cafeteria.allergens a ON a.id=ca.allergen_id
           WHERE ca.component_id=ANY(CAST(:component_ids AS bigint[]))
           ORDER BY ca.component_id, a.code, ca.presence, a.display_name'''
    ), {'component_ids': ids}).mappings()
    for row in allergen_rows:
        result[int(row['component_id'])][1].append({
            'code': str(row['code']),
            'name': str(row['display_name']),
            'presence': str(row['presence']),
        })
    return result


def _normalize_label_codes(value: object) -> tuple[str, ...]:
    if not _is_sequence(value):
        raise MetadataValidationError('Ungültige Ernährungslabels.')
    if len(value) > _MAX_METADATA_ENTRIES:
        raise MetadataValidationError('Zu viele Ernährungslabels.')
    labels: list[str] = []
    seen: set[str] = set()
    for code in value:
        if type(code) is not str or _LABEL_CODE.fullmatch(code) is None:
            raise MetadataValidationError('Ungültiges Ernährungslabel.')
        if code in seen:
            raise MetadataValidationError('Doppeltes Ernährungslabel.')
        seen.add(code)
        labels.append(code)
    return tuple(sorted(labels))


def _normalize_allergens(value: object) -> tuple[AllergenInput, ...]:
    if not _is_sequence(value):
        raise MetadataValidationError('Ungültige Allergene.')
    if len(value) > _MAX_METADATA_ENTRIES:
        raise MetadataValidationError('Zu viele Allergene.')
    allergens: list[AllergenInput] = []
    seen: set[str] = set()
    for pair in value:
        if not _is_sequence(pair) or len(pair) != 2:
            raise MetadataValidationError('Ungültiges Allergen.')
        code, presence = pair
        if type(code) is not str or _ALLERGEN_CODE.fullmatch(code) is None:
            raise MetadataValidationError('Ungültiges Allergen.')
        if type(presence) is not str or presence not in _PRESENCES:
            raise MetadataValidationError('Ungültige Allergen-Präsenz.')
        if code in seen:
            raise MetadataValidationError('Doppeltes Allergen.')
        seen.add(code)
        allergens.append((code, presence))
    return tuple(sorted(allergens))


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
