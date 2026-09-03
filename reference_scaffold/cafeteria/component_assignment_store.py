from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from .component_catalog_store import (
    AdminScope,
    ComponentConflictError,
    ComponentNotFoundError,
    resolve_single_active_location_connection,
)
from .component_effects import (
    AutoOriginConflictError as AutoOriginConflictError,
    effective_rows,
    public_effects,
    rematerialize_auto_effects,
)


_ASSIGNMENT_KEYS = frozenset({'component_public_id', 'component_text'})
_MAX_ASSIGNMENTS = 32_767


class ComponentAssignmentValidationError(ValueError):
    pass


class ComponentAssignmentConflictError(ComponentConflictError):
    pass


class StaleItemError(ComponentAssignmentConflictError):
    pass


@dataclass(frozen=True)
class _Assignment:
    public_id: str | None
    component_text: str | None


def assign_component(
    engine: Engine,
    scope: AdminScope,
    item_id: int,
    component_public_id: str | None,
    component_text: str | None,
    expected_item_row_version: int,
) -> int:
    assignment = _normalize_assignments(
        [
            {
                'component_public_id': component_public_id,
                'component_text': component_text,
            }
        ]
    )[0]
    return _mutate_links(
        engine, scope, item_id, [assignment], expected_item_row_version, append=True
    )


def replace_component_links(
    engine: Engine,
    scope: AdminScope,
    item_id: int,
    assignments: Sequence[Mapping[str, object]],
    expected_item_row_version: int,
) -> int:
    normalized = _normalize_assignments(assignments)
    return _mutate_links(
        engine, scope, item_id, normalized, expected_item_row_version, append=False
    )


def replace_component_links_connection(
    connection: Connection,
    scope: AdminScope,
    item_id: int,
    assignments: Sequence[Mapping[str, object]],
) -> None:
    normalized = _normalize_assignments(assignments)
    _replace_component_links_connection(connection, scope, _positive(item_id, 'item_id'), normalized)


def resolve_component_effects(
    engine: Engine, scope: AdminScope, item_id: int
) -> dict[str, object]:
    clean_item_id = _positive(item_id, 'item_id')
    with engine.begin() as connection:
        _require_location(connection, scope)
        item = _find_scoped_item(connection, scope, clean_item_id)
        return public_effects(effective_rows(connection, clean_item_id, item))


def _mutate_links(
    engine: Engine,
    scope: AdminScope,
    item_id: int,
    assignments: list[_Assignment],
    expected_item_row_version: int,
    *,
    append: bool,
) -> int:
    clean_item_id = _positive(item_id, 'item_id')
    expected_version = _positive(expected_item_row_version, 'expected_item_row_version')
    with engine.begin() as connection:
        item = _lock_scoped_item(connection, scope, clean_item_id)
        if item['row_version'] != expected_version:
            raise StaleItemError('Das Menü wurde zwischenzeitlich geändert.')
        target = assignments
        if append:
            target = _current_assignments(connection, clean_item_id) + assignments
        _replace_component_links_connection(connection, scope, clean_item_id, target)
        rematerialize_auto_effects(connection, clean_item_id, item)
        return int(
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.menu_items
                    SET allergen_review_status='not_checked'
                    WHERE id=:item_id
                    RETURNING row_version
                    '''
                ),
                {'item_id': clean_item_id},
            ).scalar_one()
        )


def _lock_scoped_item(
    connection: Connection, scope: AdminScope, item_id: int
) -> Mapping[str, object]:
    _require_location(connection, scope)
    owner = connection.execute(
        text(
            '''
            /* assignment_week_lock */
            SELECT w.id AS week_id, s.id AS service_id
            FROM cafeteria.menu_weeks w
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
            JOIN cafeteria.menu_items i ON i.service_id=s.id
            WHERE i.id=:item_id AND w.location_id=:location_id AND p.code=:profile_code
            FOR UPDATE OF w
            '''
        ),
        {
            'item_id': item_id,
            'location_id': scope.location_id,
            'profile_code': scope.profile_code,
        },
    ).mappings().one_or_none()
    if owner is None:
        raise ComponentNotFoundError('Menü nicht gefunden.')
    service_id = connection.execute(
        text(
            'SELECT id FROM cafeteria.menu_services '
            'WHERE id=:service_id AND menu_week_id=:week_id FOR UPDATE'
        ),
        {'service_id': owner['service_id'], 'week_id': owner['week_id']},
    ).scalar_one_or_none()
    if service_id is None:
        raise ComponentNotFoundError('Menü nicht gefunden.')
    item = connection.execute(
        text(
            '''
            SELECT id, row_version, allergen_mode, origin_mode, label_mode
            FROM cafeteria.menu_items
            WHERE id=:item_id AND service_id=:service_id
            FOR UPDATE
            '''
        ),
        {'item_id': item_id, 'service_id': service_id},
    ).mappings().one_or_none()
    if item is None:
        raise ComponentNotFoundError('Menü nicht gefunden.')
    return item


def _find_scoped_item(
    connection: Connection, scope: AdminScope, item_id: int
) -> Mapping[str, object]:
    item = connection.execute(
        text(
            '''
            SELECT i.id, i.row_version, i.allergen_mode, i.origin_mode, i.label_mode
            FROM cafeteria.menu_items i
            JOIN cafeteria.menu_services s ON s.id=i.service_id
            JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE i.id=:item_id AND w.location_id=:location_id AND p.code=:profile_code
            '''
        ),
        {
            'item_id': item_id,
            'location_id': scope.location_id,
            'profile_code': scope.profile_code,
        },
    ).mappings().one_or_none()
    if item is None:
        raise ComponentNotFoundError('Menü nicht gefunden.')
    return item


def _replace_component_links_connection(
    connection: Connection,
    scope: AdminScope,
    item_id: int,
    assignments: list[_Assignment],
) -> None:
    _require_location(connection, scope)
    _find_scoped_item(connection, scope, item_id)
    existing_ids = [
        int(value)
        for value in connection.execute(
            text(
                'SELECT component_id FROM cafeteria.menu_item_components '
                'WHERE menu_item_id=:item_id AND component_id IS NOT NULL'
            ),
            {'item_id': item_id},
        ).scalars()
    ]
    public_ids = sorted({value.public_id for value in assignments if value.public_id})
    requested = connection.execute(
        text(
            '''
            SELECT id, public_id::text AS public_id
            FROM cafeteria.menu_components
            WHERE public_id=ANY(CAST(:public_ids AS uuid[]))
              AND location_id=:location_id
              AND profile_scope IN ('common', :profile_code)
            '''
        ),
        {
            'public_ids': public_ids,
            'location_id': scope.location_id,
            'profile_code': scope.profile_code,
        },
    ).mappings().all()
    requested_ids = {str(row['public_id']): int(row['id']) for row in requested}
    if set(public_ids) != set(requested_ids):
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    union_ids = sorted(set(existing_ids) | set(requested_ids.values()))
    locked = connection.execute(
        text(
            '''
            /* assignment_component_lock */
            SELECT id, public_id::text AS public_id, name, row_version, active
            FROM cafeteria.menu_components
            WHERE id=ANY(CAST(:component_ids AS bigint[]))
            ORDER BY id FOR SHARE
            '''
        ),
        {'component_ids': union_ids},
    ).mappings().all()
    by_public_id = {str(row['public_id']): row for row in locked}
    if any(public_id not in by_public_id for public_id in public_ids):
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    existing_counts = Counter(existing_ids)
    requested_counts = Counter(
        int(by_public_id[value.public_id]['id'])
        for value in assignments
        if value.public_id is not None
    )
    for component_id, count in requested_counts.items():
        row = next(row for row in locked if int(row['id']) == component_id)
        if bool(row['active']) and count > 1:
            raise ComponentAssignmentConflictError('Aktive Komponente ist doppelt zugewiesen.')
        if not bool(row['active']) and count > existing_counts[component_id]:
            raise ComponentAssignmentConflictError('Archivierte Komponente kann nicht neu zugewiesen werden.')
    connection.execute(
        text(
            '''
            SELECT menu_item_id, sort_order
            FROM cafeteria.menu_item_components
            WHERE menu_item_id=:item_id
            ORDER BY menu_item_id, sort_order FOR UPDATE
            '''
        ),
        {'item_id': item_id},
    ).all()
    connection.execute(
        text('DELETE FROM cafeteria.menu_item_components WHERE menu_item_id=:item_id'),
        {'item_id': item_id},
    )
    rows = []
    for sort_order, assignment in enumerate(assignments, 1):
        component = by_public_id.get(assignment.public_id or '')
        rows.append(
            {
                'item_id': item_id,
                'sort_order': sort_order,
                'component_text': (
                    str(component['name']) if component is not None else assignment.component_text
                ),
                'component_id': int(component['id']) if component is not None else None,
                'component_version': (
                    int(component['row_version']) if component is not None else None
                ),
            }
        )
    if rows:
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_components(
                    menu_item_id, sort_order, component_text, component_id, component_row_version
                ) VALUES (
                    :item_id, :sort_order, :component_text, :component_id, :component_version
                )
                '''
            ),
            rows,
        )


def _current_assignments(connection: Connection, item_id: int) -> list[_Assignment]:
    rows = connection.execute(
        text(
            '''
            SELECT c.public_id::text AS public_id, mic.component_text
            FROM cafeteria.menu_item_components mic
            LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id
            WHERE mic.menu_item_id=:item_id ORDER BY mic.sort_order
            '''
        ),
        {'item_id': item_id},
    ).mappings()
    return [
        _Assignment(str(row['public_id']), None)
        if row['public_id'] is not None
        else _Assignment(None, str(row['component_text']))
        for row in rows
    ]


def _normalize_assignments(value: object) -> list[_Assignment]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ComponentAssignmentValidationError('Zuweisungen müssen eine Liste sein.')
    if len(value) > _MAX_ASSIGNMENTS:
        raise ComponentAssignmentValidationError('Zu viele Komponenten.')
    result = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != _ASSIGNMENT_KEYS:
            raise ComponentAssignmentValidationError('Komponentenzuweisung hat ungültige Felder.')
        public_id = raw['component_public_id']
        component_text = raw['component_text']
        if (public_id is None) == (component_text is None):
            raise ComponentAssignmentValidationError('Genau eine Komponente muss gesetzt sein.')
        if public_id is not None:
            if type(public_id) is not str:
                raise ComponentAssignmentValidationError('Komponenten-ID ist ungültig.')
            try:
                result.append(_Assignment(str(UUID(public_id)), None))
            except (ValueError, AttributeError) as error:
                raise ComponentAssignmentValidationError('Komponenten-ID ist ungültig.') from error
        else:
            if type(component_text) is not str or not component_text.strip(' '):
                raise ComponentAssignmentValidationError('Freitext-Komponente ist leer.')
            result.append(_Assignment(None, component_text))
    return result


def _positive(value: object, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ComponentAssignmentValidationError(f'{field_name} muss eine positive Ganzzahl sein.')
    return value


def _require_location(connection: Connection, scope: AdminScope) -> None:
    if resolve_single_active_location_connection(connection) != scope.location_id:
        raise ComponentNotFoundError('Standort nicht gefunden.')
