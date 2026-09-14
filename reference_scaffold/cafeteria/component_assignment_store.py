from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal

from sqlalchemy import Connection, Engine, text

from .component_assignment_contract import (
    Assignment,
    AssignmentValidationError as ComponentAssignmentValidationError,
    normalize_assignments,
)
from .component_binding_state import BindingState, payloads_from_links, prepare_bindings
from .workflow_write_context import record_item_write, write_transaction

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


class ComponentAssignmentConflictError(ComponentConflictError):
    pass


class StaleItemError(ComponentAssignmentConflictError):
    pass


def assign_component(
    engine: Engine,
    scope: AdminScope,
    item_id: int,
    component_public_id: str | None,
    component_text: str | None,
    expected_item_row_version: int,
    *,
    recipe_revision_public_id: str | None = None,
    target_quantity: str | None = None,
    target_quantity_unit_code: str | None = None,
) -> int:
    assignment = _normalize_assignments(
        [
            {
                'component_public_id': component_public_id,
                'component_text': component_text,
                'recipe_revision_public_id': recipe_revision_public_id,
                'target_quantity': target_quantity,
                'target_quantity_unit_code': target_quantity_unit_code,
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
    *,
    binding_state: BindingState,
) -> None:
    normalized = _normalize_assignments(assignments)
    _replace_component_links_connection(
        connection, scope, _positive(item_id, 'item_id'), normalized, binding_state,
    )


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
    assignments: Sequence[Assignment],
    expected_item_row_version: int,
    *,
    append: bool,
) -> int:
    clean_item_id = _positive(item_id, 'item_id')
    expected_version = _positive(expected_item_row_version, 'expected_item_row_version')
    with write_transaction(engine, scope) as connection:
        state = prepare_bindings(connection, scope, assignments, item_ids=[clean_item_id])
        item = _lock_scoped_item(connection, scope, clean_item_id)
        if item['row_version'] != expected_version:
            raise StaleItemError('Das Menü wurde zwischenzeitlich geändert.')
        state.recheck()
        target = list(assignments)
        if append:
            target = _normalize_assignments(payloads_from_links(state.old_links(clean_item_id))) + target
        _replace_component_links_connection(connection, scope, clean_item_id, target, state)
        rematerialize_auto_effects(connection, clean_item_id, item)
        version = int(
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
        record_item_write(connection, scope, clean_item_id, expected_version, version)
        return version


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
    assignments: Sequence[Assignment],
    state: BindingState,
) -> None:
    state.require_item(connection, scope, item_id)
    old = state.old_links(item_id)
    if any(row['recipe_revision_id'] is not None for row in old) and (
            not assignments or any(not row.recipe_field_present for row in assignments)):
        raise ComponentAssignmentConflictError(
            'Rezeptbezüge sind vorhanden. Bitte das vollständige Menüformular neu laden.'
        )
    by_public_id = state.components
    if any(row.component_public_id and row.component_public_id not in by_public_id
           or row.recipe_revision_public_id and row.recipe_revision_public_id not in state.recipes
           for row in assignments):
        raise ComponentAssignmentConflictError('Zuweisung gehört nicht zum vorbereiteten Schreibvorgang.')
    existing_counts = Counter(row['component_public_id'] for row in old if row['component_public_id'])
    requested_counts = Counter(row.component_public_id for row in assignments if row.component_public_id)
    for public_id, count in requested_counts.items():
        row = by_public_id[public_id]
        if bool(row['active']) and count > 1:
            raise ComponentAssignmentConflictError('Aktive Komponente ist doppelt zugewiesen.')
        if not bool(row['active']) and count > existing_counts[public_id]:
            raise ComponentAssignmentConflictError('Archivierte Komponente kann nicht neu zugewiesen werden.')
    old_recipes = Counter(row['recipe_revision_public_id'] for row in old if row['recipe_revision_public_id'])
    new_recipes = Counter(row.recipe_revision_public_id for row in assignments if row.recipe_revision_public_id)
    for public_id, count in new_recipes.items():
        if not state.recipes[public_id]['active'] and count > old_recipes[public_id]:
            raise ComponentAssignmentConflictError('Archiviertes Rezept kann nicht neu zugewiesen werden.')
    old_foods = Counter(by_public_id[row['component_public_id']]['food_id'] for row in old
                        if row['component_public_id'] and by_public_id[row['component_public_id']]['food_id'])
    new_foods = Counter(by_public_id[row.component_public_id]['food_id'] for row in assignments
                        if row.component_public_id and by_public_id[row.component_public_id]['food_id'])
    for food_id, count in new_foods.items():
        if not state.foods[food_id]['active'] and count > old_foods[food_id]:
            raise ComponentAssignmentConflictError('Archivierte Zutat kann nicht neu zugewiesen werden.')
    targets = _resolve_targets(connection, item_id, old, assignments, state)
    connection.execute(
        text('DELETE FROM cafeteria.menu_item_components WHERE menu_item_id=:item_id'),
        {'item_id': item_id},
    )
    rows = []
    for sort_order, (assignment, target) in enumerate(zip(assignments, targets, strict=True), 1):
        component = by_public_id.get(assignment.component_public_id or '')
        recipe = state.recipes.get(assignment.recipe_revision_public_id or '')
        target_quantity, target_quantity_unit_id = target
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
                'recipe_revision_id': int(recipe['revision_id']) if recipe is not None else None,
                'target_quantity': target_quantity,
                'target_quantity_unit_id': target_quantity_unit_id,
            }
        )
    if rows:
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_components(
                    menu_item_id, sort_order, component_text, component_id, component_row_version,
                    recipe_revision_id, target_quantity, target_quantity_unit_id
                ) VALUES (
                    :item_id, :sort_order, :component_text, :component_id, :component_version,
                    :recipe_revision_id, :target_quantity, :target_quantity_unit_id
                )
                '''
            ),
            rows,
        )


def _revision_servings_units(
    connection: Connection, state: BindingState
) -> dict[int, str | None]:
    revision_ids = sorted({int(row['revision_id']) for row in state.recipes.values()})
    if not revision_ids:
        return {}
    return {
        int(row['id']): row['unit_code']
        for row in connection.execute(
            text(
                '''
                SELECT id, snapshot_json->'recipe'->>'servings_unit_code' AS unit_code
                FROM cafeteria.recipe_revisions WHERE id=ANY(CAST(:ids AS bigint[]))
                '''
            ),
            {'ids': revision_ids},
        ).mappings()
    }


def _unit_ids_by_code(connection: Connection, assignments: Sequence[Assignment]) -> dict[str, int]:
    codes = sorted({
        row.target_quantity_unit_code for row in assignments
        if row.target_field_present and row.target_quantity_unit_code is not None
    })
    if not codes:
        return {}
    return {
        str(row['code']): int(row['id'])
        for row in connection.execute(
            text('SELECT id, code FROM cafeteria.measurement_units WHERE code=ANY(CAST(:codes AS text[]))'),
            {'codes': codes},
        ).mappings()
    }


def _identity_key(
    component_id: int | None, component_text: object, revision_id: int | None
) -> tuple[object, ...]:
    """Content identity of a component row: catalog component id or normalized text, plus revision."""
    if component_id is not None:
        return ('component', component_id, revision_id)
    return ('text', ' '.join(unicodedata.normalize('NFC', str(component_text)).split()), revision_id)


def _old_targets_by_identity(
    connection: Connection, item_id: int, old: Sequence[Mapping[str, object]]
) -> dict[tuple[object, ...], list[tuple[Decimal | None, int | None]]]:
    if not old:
        return {}
    rows = connection.execute(
        text(
            'SELECT component_id, component_text, recipe_revision_id, target_quantity, '
            'target_quantity_unit_id FROM cafeteria.menu_item_components WHERE menu_item_id=:item_id'
        ),
        {'item_id': item_id},
    ).mappings()
    targets: dict[tuple[object, ...], list[tuple[Decimal | None, int | None]]] = {}
    for row in rows:
        key = _identity_key(row['component_id'], row['component_text'], row['recipe_revision_id'])
        targets.setdefault(key, []).append((row['target_quantity'], row['target_quantity_unit_id']))
    return targets


def _resolve_targets(
    connection: Connection,
    item_id: int,
    old: Sequence[Mapping[str, object]],
    assignments: Sequence[Assignment],
    state: BindingState,
) -> list[tuple[Decimal | None, int | None]]:
    """Validate D3 and resolve each row's stored target quantity/unit.

    A row that carries the target keys is validated fresh (unit exists, matches the bound
    revision's declared servings unit, requires a bound revision). A row that omits both keys
    keeps a stored target only through content identity (catalog component id or normalized
    text, plus the bound revision), never through its position; see the loop for ambiguity.
    """
    old_targets = _old_targets_by_identity(connection, item_id, old)
    servings_units = _revision_servings_units(connection, state)
    unit_ids = _unit_ids_by_code(connection, assignments)
    keys: list[tuple[object, ...]] = []
    for assignment in assignments:
        component = state.components.get(assignment.component_public_id or '')
        recipe = state.recipes.get(assignment.recipe_revision_public_id or '')
        keys.append(_identity_key(
            int(component['id']) if component is not None else None,
            assignment.component_text,
            int(recipe['revision_id']) if recipe is not None else None,
        ))
    new_counts = Counter(keys)
    resolved: list[tuple[Decimal | None, int | None]] = []
    for assignment, key in zip(assignments, keys, strict=True):
        recipe = state.recipes.get(assignment.recipe_revision_public_id or '')
        if assignment.target_field_present:
            if assignment.target_quantity is None:
                resolved.append((None, None))
                continue
            if recipe is None:
                raise ComponentAssignmentValidationError(
                    'Zielmenge erfordert eine gebundene Rezeptrevision.'
                )
            unit_id = unit_ids.get(assignment.target_quantity_unit_code or '')
            if unit_id is None:
                raise ComponentAssignmentValidationError('Zieleinheit ist unbekannt.')
            expected_unit = servings_units.get(int(recipe['revision_id']))
            if assignment.target_quantity_unit_code != expected_unit:
                raise ComponentAssignmentValidationError(
                    'Zieleinheit muss der Ausbeuteeinheit der gebundenen Rezeptrevision entsprechen.'
                )
            resolved.append((Decimal(assignment.target_quantity), unit_id))
            continue
        # Carry only a unique match: exactly one old and one new row share this identity.
        # Duplicates could pair the wrong rows, so they drop the target instead of guessing;
        # a changed component or revision is a different identity and never carries.
        candidates = old_targets.get(key, [])
        if len(candidates) == 1 and new_counts[key] == 1:
            resolved.append(candidates[0])
        else:
            resolved.append((None, None))
    return resolved


def _normalize_assignments(value: object) -> list[Assignment]:
    return list(normalize_assignments(value))


def _positive(value: object, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ComponentAssignmentValidationError(f'{field_name} muss eine positive Ganzzahl sein.')
    return value


def _require_location(connection: Connection, scope: AdminScope) -> None:
    if resolve_single_active_location_connection(connection) != scope.location_id:
        raise ComponentNotFoundError('Standort nicht gefunden.')
