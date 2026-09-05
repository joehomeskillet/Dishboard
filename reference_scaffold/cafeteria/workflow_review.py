from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from .component_assignment_store import (
    StaleItemError,
    _find_scoped_item,
    _lock_scoped_item,
    _positive,
    _require_location,
)
from .component_catalog_store import AdminScope, ComponentNotFoundError
from .component_effects import effective_rows, public_effects, rematerialize_auto_effects
from .workflow_publication import require_expected_active_location


_TOKEN_KEYS = frozenset(
    {
        'item_row_version',
        'allergen_mode',
        'origin_mode',
        'label_mode',
        'components',
        'labels',
        'allergens',
        'origins',
    }
)
_COMPONENT_KEYS = frozenset(
    {
        'sort_order',
        'component_public_id',
        'component_text',
        'stored_component_row_version',
        'current_component_row_version',
    }
)
_ROW_KEYS = {
    'labels': frozenset({'code', 'name'}),
    'allergens': frozenset({'code', 'name', 'presence'}),
    'origins': frozenset({'ingredient', 'country_code', 'text'}),
}
_TOKEN_PATTERN = re.compile(r'sha256:[0-9a-f]{64}')


def _positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f'{label} muss eine positive Ganzzahl sein.')
    return value


def _database_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise RuntimeError(f'Datenbankwert {label} ist ungültig.')
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f'{label} muss Text sein.')
    return value


def _exact_mapping(value: object, keys: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or frozenset(value) != keys:
        raise ValueError(f'{label} hat ungültige Felder.')
    return value


def _validate_components(value: object) -> None:
    if type(value) is not list:
        raise ValueError('components muss eine Liste sein.')
    ordering = []
    for raw in value:
        row = _exact_mapping(raw, _COMPONENT_KEYS, 'Komponente')
        ordering.append(_positive_integer(row['sort_order'], 'sort_order'))
        _string(row['component_text'], 'component_text')
        public_id = row['component_public_id']
        stored_version = row['stored_component_row_version']
        current_version = row['current_component_row_version']
        if public_id is None:
            if stored_version is not None or current_version is not None:
                raise ValueError('Freitext darf keine Komponenten-Version tragen.')
            continue
        canonical_id = _string(public_id, 'component_public_id')
        try:
            if str(UUID(canonical_id)) != canonical_id:
                raise ValueError
        except (ValueError, AttributeError) as error:
            raise ValueError('component_public_id ist nicht kanonisch.') from error
        _positive_integer(stored_version, 'stored_component_row_version')
        _positive_integer(current_version, 'current_component_row_version')
    if ordering != sorted(ordering) or len(ordering) != len(set(ordering)):
        raise ValueError('Komponenten sind nicht eindeutig sortiert.')


def _validate_rows(name: str, value: object) -> None:
    if type(value) is not list:
        raise ValueError(f'{name} muss eine Liste sein.')
    sort_fields = {
        'labels': ('code', 'name'),
        'allergens': ('code', 'presence', 'name'),
        'origins': ('ingredient', 'country_code', 'text'),
    }[name]
    ordering = []
    for raw in value:
        row = _exact_mapping(raw, _ROW_KEYS[name], name)
        for field in _ROW_KEYS[name]:
            _string(row[field], f'{name}.{field}')
        if name == 'allergens' and row['presence'] not in {'contains', 'may_contain'}:
            raise ValueError('Allergen-Präsenz ist ungültig.')
        ordering.append(tuple(row[field] for field in sort_fields))
    if ordering != sorted(ordering):
        raise ValueError(f'{name} sind nicht sortiert.')


def _validate_review_payload(value: object) -> Mapping[str, Any]:
    payload = _exact_mapping(value, _TOKEN_KEYS, 'Review-Token')
    _positive_integer(payload['item_row_version'], 'item_row_version')
    for mode in ('allergen_mode', 'origin_mode', 'label_mode'):
        if type(payload[mode]) is not str or payload[mode] not in {'auto', 'manual'}:
            raise ValueError(f'{mode} ist ungültig.')
    _validate_components(payload['components'])
    for name in ('labels', 'allergens', 'origins'):
        _validate_rows(name, payload[name])
    return payload


def _review_token(payload: object) -> str:
    validated = _validate_review_payload(payload)
    encoded = json.dumps(
        validated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def _review_open_connection(connection: Connection, item_id: int) -> bool:
    value = connection.execute(
        text(
            '''
            SELECT i.allergen_review_status <> 'checked' OR EXISTS (
                SELECT 1
                FROM cafeteria.menu_item_components mic
                JOIN cafeteria.menu_components c ON c.id=mic.component_id
                WHERE mic.menu_item_id=i.id
                  AND mic.component_row_version IS DISTINCT FROM c.row_version
            )
            FROM cafeteria.menu_items i
            WHERE i.id=:item_id
            '''
        ),
        {'item_id': item_id},
    ).scalar_one_or_none()
    if value is None:
        raise ComponentNotFoundError('Menü nicht gefunden.')
    if value:
        return True
    receipt_token = connection.execute(text('''
        SELECT a.details->>'reviewed_token'
        FROM cafeteria.audit_events a
        JOIN cafeteria.menu_items i ON i.public_id=a.entity_public_id
        WHERE i.id=:item_id AND a.action='workflow.menu_reviewed'
          AND a.entity_type='menu_item'
          AND a.details->>'reviewed_item_row_version'=i.row_version::text
        ORDER BY a.id DESC LIMIT 1
    '''), {'item_id': item_id}).scalar_one_or_none()
    if receipt_token is None:
        return True
    return receipt_token != _review_token(_review_payload(connection, None, item_id))


def review_open(engine: Engine, scope: AdminScope, item_id: int) -> bool:
    clean_item_id = _positive(item_id, 'item_id')
    with engine.begin() as connection:
        try:
            _require_location(connection, scope)
            _find_scoped_item(connection, scope, clean_item_id)
        except ComponentNotFoundError:
            raise ComponentNotFoundError('Menü nicht gefunden.') from None
        return _review_open_connection(connection, clean_item_id)


def _review_payload(
    connection: Connection,
    scope: AdminScope | None,
    item_id: int,
) -> dict[str, object]:
    item = (
        _find_scoped_item(connection, scope, item_id) if scope is not None else
        dict(connection.execute(text(
            'SELECT id,row_version,allergen_mode,origin_mode,label_mode '
            'FROM cafeteria.menu_items WHERE id=:item_id'
        ), {'item_id': item_id}).mappings().one())
    )
    components = [
        {
            'sort_order': int(row['sort_order']),
            'component_public_id': (
                str(row['component_public_id'])
                if row['component_public_id'] is not None
                else None
            ),
            'component_text': str(row['component_text']),
            'stored_component_row_version': (
                int(row['stored_component_row_version'])
                if row['stored_component_row_version'] is not None
                else None
            ),
            'current_component_row_version': (
                int(row['current_component_row_version'])
                if row['current_component_row_version'] is not None
                else None
            ),
        }
        for row in connection.execute(
            text(
                '''
                SELECT mic.sort_order, c.public_id::text AS component_public_id,
                       mic.component_text,
                       mic.component_row_version AS stored_component_row_version,
                       c.row_version AS current_component_row_version
                FROM cafeteria.menu_item_components mic
                LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id
                WHERE mic.menu_item_id=:item_id
                ORDER BY mic.sort_order
                '''
            ),
            {'item_id': item_id},
        ).mappings()
    ]
    effects = public_effects(effective_rows(connection, item_id, item))
    return {
        'item_row_version': _database_integer(item['row_version'], 'item_row_version'),
        'allergen_mode': str(item['allergen_mode']),
        'origin_mode': str(item['origin_mode']),
        'label_mode': str(item['label_mode']),
        'components': components,
        'labels': effects['labels'],
        'allergens': effects['allergens'],
        'origins': effects['origins'],
    }


def get_component_review_token(
    engine: Engine,
    scope: AdminScope,
    item_id: int,
) -> str:
    clean_item_id = _positive(item_id, 'item_id')
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            _require_location(connection, scope)
            return _review_token(_review_payload(connection, scope, clean_item_id))


def _lock_components_and_links(connection: Connection, item_id: int) -> None:
    component_ids = sorted(
        {
            int(value)
            for value in connection.execute(
                text(
                    'SELECT component_id FROM cafeteria.menu_item_components '
                    'WHERE menu_item_id=:item_id AND component_id IS NOT NULL'
                ),
                {'item_id': item_id},
            ).scalars()
        }
    )
    locked_ids = list(
        connection.execute(
            text(
                '''
                /* review_component_lock */
                SELECT id FROM cafeteria.menu_components
                WHERE id=ANY(CAST(:component_ids AS bigint[]))
                ORDER BY id FOR SHARE
                '''
            ),
            {'component_ids': component_ids},
        ).scalars()
    )
    if locked_ids != component_ids:
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    connection.execute(
        text(
            '''
            /* review_links_lock */
            SELECT menu_item_id, sort_order
            FROM cafeteria.menu_item_components
            WHERE menu_item_id=:item_id
            ORDER BY menu_item_id, sort_order FOR UPDATE
            '''
        ),
        {'item_id': item_id},
    ).all()


def review_component(
    engine: Engine,
    scope: AdminScope,
    item_id: int,
    component_version: str,
    expected_item_row_version: int,
) -> int:
    clean_item_id = _positive(item_id, 'item_id')
    expected_version = _positive(
        expected_item_row_version, 'expected_item_row_version'
    )
    if type(component_version) is not str or _TOKEN_PATTERN.fullmatch(component_version) is None:
        raise ValueError('component_version ist ungültig.')
    with engine.begin() as connection:
        require_expected_active_location(connection, scope.location_id, lock=True)
        _lock_scoped_item(connection, scope, clean_item_id)
        _lock_components_and_links(connection, clean_item_id)
        item = _find_scoped_item(connection, scope, clean_item_id)
        if _database_integer(item['row_version'], 'item_row_version') != expected_version:
            raise StaleItemError('Das Menü wurde zwischenzeitlich geändert.')
        if _review_token(_review_payload(connection, scope, clean_item_id)) != component_version:
            raise StaleItemError('Die Komponenten wurden zwischenzeitlich geändert.')
        connection.execute(
            text(
                '''
                UPDATE cafeteria.menu_item_components mic
                SET component_text=c.name, component_row_version=c.row_version
                FROM cafeteria.menu_components c
                WHERE mic.menu_item_id=:item_id AND c.id=mic.component_id
                '''
            ),
            {'item_id': clean_item_id},
        )
        rematerialize_auto_effects(connection, clean_item_id, item)
        new_version = int(
            connection.execute(
                text(
                    "UPDATE cafeteria.menu_items SET allergen_review_status='checked' "
                    'WHERE id=:item_id RETURNING row_version'
                ),
                {'item_id': clean_item_id},
            ).scalar_one()
        )
        connection.execute(
            text(
                '''
                UPDATE cafeteria.menu_weeks w SET updated_by=:actor_id
                FROM cafeteria.menu_services s, cafeteria.menu_items i
                WHERE i.id=:item_id AND s.id=i.service_id AND w.id=s.menu_week_id
                '''
            ),
            {'actor_id': scope.actor_id, 'item_id': clean_item_id},
        )
        reviewed_token = _review_token(_review_payload(connection, scope, clean_item_id))
        connection.execute(text('''
            SELECT cafeteria.record_menu_review(
                :actor, :location, :profile, :item_id, :source_version,
                :submitted_token, :reviewed_token
            )
        '''), {
            'actor': scope.actor_id, 'location': scope.location_id, 'profile': scope.profile_code,
            'item_id': clean_item_id, 'source_version': expected_version,
            'submitted_token': component_version, 'reviewed_token': reviewed_token,
        }).scalar_one()
        return new_version
