"""MP-REC-SHOPPING-PERSIST store: shopping lists, immutable compute revisions, manual items.

``line_key`` = ``sha256(json([status, unit_code, captured]))[:16] + ':' + readable`` (<= 300 chars,
right-trimmed): ``captured`` is the identity/unit/factor tuple ``AggregateLine`` merged on (or the
normalized free text of an incomplete row), ``readable`` the food public id or that text. A checked
row follows a recompute only with an unchanged quantity+unit signature; otherwise it keeps its old
revision and reads as ``changed_open``. Only ``set_line_checked(checked=False)`` deletes a row.

The shared actor/location guard ``_transaction``, the exceptions, ``ShoppingScope`` and the read paths
live in ``shopping_list_reads`` and are re-exported here. ``compute_revision`` (REPEATABLE READ) takes
SHARE ROW EXCLUSIVE on ``shopping_list_line_status`` before its snapshot, ``set_line_checked`` ROW
EXCLUSIVE and then the list row lock: a check never lands on a superseded revision and a recompute
never misses a committed check. Each result line captures the food/unit display names of its compute
(one query each), so a receipt never changes with later master data. Manual items are CAS-guarded for
every write. No SECURITY DEFINER verb, no audit write (the app holds only SELECT on ``audit_events``);
revision reads reuse the verified private reader ``recipe_reads._get_revision_connection``.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal
from typing import Mapping, Sequence

from sqlalchemy import Connection, Engine, text

from .quantities import FoodFactors, QuantityError, Unit, parse_quantity
from .recipe_reads import _get_revision_connection
from .shopping_aggregate import AggregateLine, IngredientNeed, RevisionNeed, aggregate
from .shopping_list_reads import (
    ShoppingListActorDeniedError, ShoppingListConflictError, ShoppingListError, ShoppingListNotFoundError,
    ShoppingListRetryError, ShoppingListStaleActorError, ShoppingListUnavailableError, ShoppingListValidationError,
    ShoppingScope, _decimal_str, _positive, _text, _transaction, _uuid, candidate_components, get_shopping_list,
    list_shopping_lists,
)

__all__ = (
    'ShoppingListActorDeniedError', 'ShoppingListConflictError', 'ShoppingListError', 'ShoppingListNotFoundError',
    'ShoppingListRetryError', 'ShoppingListStaleActorError', 'ShoppingListUnavailableError',
    'ShoppingListValidationError', 'ShoppingScope', 'add_manual_item', 'archive_shopping_list', 'candidate_components',
    'compute_revision', 'create_shopping_list', 'delete_manual_item', 'get_shopping_list', 'list_shopping_lists',
    'set_line_checked', 'set_manual_item_checked', 'update_manual_item',
)
_POLICIES = ('leaf', 'prepared')


def _lock_list(connection: Connection, scope: ShoppingScope, public_id: str,
               expected_row_version: int | None = None) -> Mapping[str, object]:
    row = connection.execute(
        text('SELECT id, row_version FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid) '
             'AND location_id=:location FOR UPDATE'),
        {'id': _uuid(public_id), 'location': scope.location_id},
    ).mappings().one_or_none()
    if row is None:
        raise ShoppingListNotFoundError('Einkaufsliste nicht gefunden.')
    if expected_row_version is not None and row['row_version'] != expected_row_version:
        raise ShoppingListConflictError('Die Einkaufsliste wurde zwischenzeitlich geändert.')
    return row


def create_shopping_list(
    engine: Engine, scope: ShoppingScope, *, title: str, note: str | None = None, menu_week_public_id: str | None = None,
) -> str:
    title = _text(title, 120, field='title')
    note = _text(note, 2000, multiline=True, required=False, field='note')
    with _transaction(engine, scope) as connection:
        week_id = None
        if menu_week_public_id is not None:  # the schema does not tie the week to the list's location
            week_id = connection.execute(
                text('SELECT id FROM cafeteria.menu_weeks WHERE public_id=CAST(:id AS uuid) AND location_id=:location'),
                {'id': _uuid(menu_week_public_id, 'menu_week_public_id'), 'location': scope.location_id},
            ).scalar_one_or_none()
            if week_id is None:
                raise ShoppingListValidationError('Woche gehört nicht zum Standort.', field='menu_week_public_id')
        public_id = connection.execute(
            text('''INSERT INTO cafeteria.shopping_lists(location_id, menu_week_id, title, note, created_by, updated_by)
                    VALUES (:location, :week, :title, :note, :actor, :actor) RETURNING public_id'''),
            {'location': scope.location_id, 'week': week_id, 'title': title, 'note': note, 'actor': scope.actor_id},
        ).scalar_one()
    return str(public_id)


def archive_shopping_list(engine: Engine, scope: ShoppingScope, public_id: str, *, expected_row_version: int) -> int:
    _positive(expected_row_version, 'expected_row_version')
    with _transaction(engine, scope) as connection:
        row = _lock_list(connection, scope, public_id, expected_row_version)
        return connection.execute(
            text('UPDATE cafeteria.shopping_lists SET archived_at=clock_timestamp(), updated_by=:actor '
                 'WHERE id=:id RETURNING row_version'),
            {'actor': scope.actor_id, 'id': row['id']},
        ).scalar_one()


def _resolve_selected_components(connection: Connection, location_id: int, component_ids: Sequence[str]) -> list[Mapping[str, object]]:
    if not component_ids:
        raise ShoppingListValidationError('Mindestens ein Baustein muss ausgewählt werden.', field='component_ids')
    items, sorts = [], []
    for value in component_ids:
        if not isinstance(value, str) or ':' not in value:
            raise ShoppingListValidationError('Ungültige Bausteinauswahl.', field='component_ids')
        item, _, sort_order = value.rpartition(':')
        if not sort_order.isdigit():
            raise ShoppingListValidationError('Ungültige Bausteinauswahl.', field='component_ids')
        items.append(_uuid(item, 'component_ids'))
        sorts.append(int(sort_order))
    rows = connection.execute(
        text('''
            WITH sel(item_public_id, sort_order, ord) AS (
                SELECT * FROM unnest(CAST(:items AS uuid[]), CAST(:sorts AS int[]), CAST(:ords AS int[]))
            )
            SELECT sel.ord, it.public_id AS menu_item_public_id, c.sort_order, c.component_text,
                   c.recipe_revision_id, c.target_quantity
            FROM sel
            JOIN cafeteria.menu_items it ON it.public_id=sel.item_public_id
            JOIN cafeteria.menu_services srv ON srv.id=it.service_id
            JOIN cafeteria.menu_weeks w ON w.id=srv.menu_week_id AND w.location_id=:location
            JOIN cafeteria.menu_item_components c ON c.menu_item_id=it.id AND c.sort_order=sel.sort_order
            WHERE c.recipe_revision_id IS NOT NULL
        '''),
        {'items': items, 'sorts': sorts, 'ords': list(range(len(items))), 'location': location_id},
    ).mappings().all()
    if len(rows) != len(items):
        raise ShoppingListValidationError('Auswahl enthält einen nicht gebundenen oder fremden Baustein.', field='component_ids')
    return sorted(rows, key=lambda row: row['ord'])


def _units_by_code(snapshot: Mapping[str, object]) -> dict[str, Unit]:
    return {
        unit['code']: Unit(unit['code'], unit['dimension'], Decimal(unit['base_factor']) if unit['base_factor'] is not None else None)
        for unit in snapshot['units']
    }


def _food_factors(entry: Mapping[str, object] | None) -> FoodFactors | None:
    if entry is None:
        return None
    density = Decimal(entry['density_g_per_ml']) if entry.get('density_g_per_ml') is not None else None
    piece = Decimal(entry['piece_weight_g']) if entry.get('piece_weight_g') is not None else None
    return FoodFactors(density, piece) if density is not None or piece is not None else None


def _revision_need(dto: object, target_servings: Decimal, by_public_id: Mapping[str, object], depth: int = 0) -> RevisionNeed:
    if depth > 8:
        raise ShoppingListValidationError('Zubereitungstiefe überschreitet die Grenze.')
    snapshot = dto.snapshot
    schema_version = int(snapshot['schema_version'])
    units = _units_by_code(snapshot)
    foods = {food['public_id']: food for food in snapshot['foods']}
    source_servings = Decimal(snapshot['recipe']['servings'])
    ingredients = []
    for row in snapshot['recipe']['ingredients']:
        food_id = row['food_public_id']
        quantity = Decimal(row['quantity']) if row['quantity'] is not None else None
        unit = units.get(row['unit_code']) if row['unit_code'] is not None else None
        entry = foods.get(food_id) if food_id is not None else None
        child = None
        if schema_version == 2 and entry is not None and entry.get('prepared_recipe') is not None:
            pin = entry['prepared_recipe']
            child_dto = by_public_id[pin['revision_public_id']]
            child_source = Decimal(child_dto.snapshot['recipe']['servings'])
            child = _revision_need(child_dto, child_source, by_public_id, depth + 1)
        ingredients.append(IngredientNeed(
            food_id, quantity, unit, _food_factors(entry), child, schema_version, row.get('ingredient_text') or '',
        ))
    return RevisionNeed(dto.public_id, dto.content_hash_sha256, source_servings, target_servings, tuple(ingredients))


def _free_text(line: AggregateLine) -> str:
    raw = line.captured[1] if len(line.captured) > 1 and isinstance(line.captured[1], str) else ''
    return ' '.join(unicodedata.normalize('NFC', raw).split())


def _line_key(line: AggregateLine) -> str:
    captured = [format(value, 'f') if isinstance(value, Decimal) else value for value in line.captured]
    digest = hashlib.sha256(json.dumps([line.status, line.unit_code, captured], sort_keys=True).encode('utf-8')).hexdigest()[:16]
    readable = line.food_public_id if line.food_public_id is not None else (_free_text(line) or 'freitext')
    return f'{digest}:{readable}'[:300].rstrip()


def _display_names(connection: Connection, location_id: int, lines: Sequence[AggregateLine]) -> tuple[dict[str, str], dict[str, str]]:
    """Food and unit display names as of this compute, captured into the immutable result (one query each)."""
    foods = connection.execute(
        text('SELECT public_id::text, name FROM cafeteria.foods WHERE location_id=:location AND public_id = ANY(CAST(:ids AS uuid[]))'),
        {'location': location_id, 'ids': sorted({line.food_public_id for line in lines if line.food_public_id})},
    ).tuples().all()
    units = connection.execute(
        text('SELECT code, display_name FROM cafeteria.measurement_units WHERE code = ANY(CAST(:codes AS text[]))'),
        {'codes': sorted({line.unit_code for line in lines if line.unit_code})},
    ).tuples().all()
    return dict(foods), dict(units)


def _line_signature(quantity: Decimal | None, unit_code: str) -> str:
    return f'{format(quantity, "f")} {unit_code}' if quantity is not None else 'incomplete'


def compute_revision(
    engine: Engine, scope: ShoppingScope, list_public_id: str, *, component_ids: Sequence[str], policy: str,
    expected_row_version: int,
) -> str:
    if policy not in _POLICIES:
        raise ShoppingListValidationError('Bedarfspolitik ist leaf oder prepared.', field='policy')
    _positive(expected_row_version, 'expected_row_version')
    with _transaction(engine, scope, 'compute') as connection:
        list_row = _lock_list(connection, scope, list_public_id, expected_row_version)
        selected = _resolve_selected_components(connection, scope.location_id, component_ids)
        needs, inputs = [], []
        for row in selected:
            revision_public_id = connection.execute(
                text('SELECT public_id FROM cafeteria.recipe_revisions WHERE id=:id'), {'id': row['recipe_revision_id']},
            ).scalar_one()
            dto = _get_revision_connection(connection, scope.location_id, str(revision_public_id))
            by_public_id = {child.public_id: child for child in dto.prepared_revisions}
            declared_servings = Decimal(dto.snapshot['recipe']['servings'])
            target_quantity = row.get('target_quantity')
            target_servings = Decimal(target_quantity) if target_quantity is not None else declared_servings
            needs.append(_revision_need(dto, target_servings, by_public_id))
            inputs.append({
                'menu_item_public_id': str(row['menu_item_public_id']), 'sort_order': row['sort_order'],
                'component_text': row['component_text'], 'recipe_revision_public_id': str(revision_public_id),
                'content_hash_sha256': dto.content_hash_sha256, 'source_servings': _decimal_str(declared_servings),
                'servings_unit_code': dto.snapshot['recipe']['servings_unit_code'],
                'target_servings': _decimal_str(target_servings),
            })
        lines = aggregate(tuple(needs), policy=policy, stop_prepared_food_ids=frozenset())
        food_names, unit_names = _display_names(connection, scope.location_id, lines)
        result_lines = [{
            'food_public_id': line.food_public_id, 'quantity': _decimal_str(line.quantity), 'unit_code': line.unit_code,
            'completeness': line.status, 'reason': line.reason, 'line_key': _line_key(line),
            'food_name': food_names.get(line.food_public_id) if line.food_public_id else None,
            'ingredient_text': None if line.food_public_id else (_free_text(line) or None),
            'unit_name': unit_names.get(line.unit_code),
        } for line in lines]
        snapshot = {'inputs': inputs, 'result': {'policy_stop_food_ids': [], 'lines': result_lines}}
        revision_number = connection.execute(
            text('SELECT COALESCE(MAX(revision_number), 0) + 1 FROM cafeteria.shopping_list_revisions WHERE shopping_list_id=:id'),
            {'id': list_row['id']},
        ).scalar_one()
        revision_row = connection.execute(
            text('''INSERT INTO cafeteria.shopping_list_revisions(
                        shopping_list_id, revision_number, policy, snapshot_json, content_hash_sha256, computed_by)
                    VALUES (:list, :number, :policy, CAST(:snapshot AS jsonb),
                            encode(digest(convert_to(CAST(:snapshot AS jsonb)::text, 'UTF8'), 'sha256'), 'hex'), :actor)
                    RETURNING public_id, id'''),
            {'list': list_row['id'], 'number': revision_number, 'policy': policy,
             'snapshot': json.dumps(snapshot), 'actor': scope.actor_id},
        ).mappings().one()
        existing = connection.execute(
            text('SELECT line_key, checked_quantity FROM cafeteria.shopping_list_line_status WHERE shopping_list_id=:id'),
            {'id': list_row['id']},
        ).mappings().all()
        existing_by_key = {row['line_key']: row['checked_quantity'] for row in existing}
        for line in result_lines:
            key = line['line_key']
            if key not in existing_by_key:
                continue
            signature = _line_signature(Decimal(line['quantity']) if line['quantity'] is not None else None, line['unit_code'])
            if existing_by_key[key] == signature:
                connection.execute(
                    text('UPDATE cafeteria.shopping_list_line_status SET revision_id=:revision '
                         'WHERE shopping_list_id=:id AND line_key=:key'),
                    {'revision': revision_row['id'], 'id': list_row['id'], 'key': key},
                )
        connection.execute(
            text('UPDATE cafeteria.shopping_lists SET updated_by=:actor WHERE id=:id'),
            {'actor': scope.actor_id, 'id': list_row['id']},
        )
    return str(revision_row['public_id'])


def set_line_checked(
    engine: Engine, scope: ShoppingScope, list_public_id: str, *, revision_public_id: str, line_key: str, checked: bool,
) -> None:
    if type(checked) is not bool:
        raise ShoppingListValidationError('checked muss boolesch sein.')
    with _transaction(engine, scope, 'check') as connection:
        list_row = _lock_list(connection, scope, list_public_id)
        latest = connection.execute(
            text('SELECT id, public_id, snapshot_json FROM cafeteria.shopping_list_revisions '
                 'WHERE shopping_list_id=:id ORDER BY revision_number DESC LIMIT 1'),
            {'id': list_row['id']},
        ).mappings().one_or_none()
        if latest is None or str(latest['public_id']) != _uuid(revision_public_id):
            raise ShoppingListValidationError('Nur Zeilen der neuesten Revision können abgehakt werden.')
        matches = [row for row in latest['snapshot_json']['result']['lines'] if row['line_key'] == line_key]
        if not matches:
            raise ShoppingListNotFoundError('Zeile nicht gefunden.')
        line = matches[0]
        if not checked:
            connection.execute(
                text('DELETE FROM cafeteria.shopping_list_line_status WHERE shopping_list_id=:id AND line_key=:key'),
                {'id': list_row['id'], 'key': line_key},
            )
            return
        signature = _line_signature(Decimal(line['quantity']) if line['quantity'] is not None else None, line['unit_code'])
        connection.execute(
            text('''INSERT INTO cafeteria.shopping_list_line_status(
                        shopping_list_id, line_key, revision_id, checked_quantity, checked_by)
                    VALUES (:id, :key, :revision, :signature, :actor)
                    ON CONFLICT (shopping_list_id, line_key) DO UPDATE
                    SET revision_id=EXCLUDED.revision_id, checked_quantity=EXCLUDED.checked_quantity,
                        checked_by=EXCLUDED.checked_by, checked_at=clock_timestamp()'''),
            {'id': list_row['id'], 'key': line_key, 'revision': latest['id'], 'signature': signature, 'actor': scope.actor_id},
        )


def _resolve_manual_unit(connection: Connection, quantity: str | None, unit_code: str | None) -> tuple[Decimal | None, int | None]:
    if (quantity is None) != (unit_code is None):
        raise ShoppingListValidationError('Menge und Einheit müssen gemeinsam angegeben werden.',
                                          field='quantity' if quantity is None else 'unit_code')
    if quantity is None:
        return None, None
    unit_id = connection.execute(
        text('SELECT id FROM cafeteria.measurement_units WHERE code=:code'), {'code': unit_code},
    ).scalar_one_or_none()
    if unit_id is None:
        raise ShoppingListValidationError('Einheit ist unbekannt.', field='unit_code')
    try:
        return parse_quantity(quantity), unit_id
    except QuantityError as error:
        raise ShoppingListValidationError(str(error), field='quantity') from error


def _lock_manual_item(
    connection: Connection, scope: ShoppingScope, list_public_id: str, item_public_id: str, expected_row_version: int,
) -> Mapping[str, object]:
    row = connection.execute(
        text('''SELECT m.id, m.shopping_list_id, m.row_version FROM cafeteria.shopping_list_manual_items m
                JOIN cafeteria.shopping_lists l ON l.id=m.shopping_list_id
                WHERE m.public_id=CAST(:item AS uuid) AND l.public_id=CAST(:list AS uuid) AND l.location_id=:location
                FOR UPDATE'''),
        {'item': _uuid(item_public_id), 'list': _uuid(list_public_id), 'location': scope.location_id},
    ).mappings().one_or_none()
    if row is None:
        raise ShoppingListNotFoundError('Position nicht gefunden.')
    if row['row_version'] != expected_row_version:
        raise ShoppingListConflictError('Die Position wurde zwischenzeitlich geändert.')
    return row


def add_manual_item(
    engine: Engine, scope: ShoppingScope, list_public_id: str, *, item_text: str,
    quantity: str | None = None, unit_code: str | None = None,
) -> str:
    item_text = _text(item_text, 200, field='item_text')
    with _transaction(engine, scope) as connection:
        list_id = _lock_list(connection, scope, list_public_id)['id']
        amount, unit_id = _resolve_manual_unit(connection, quantity, unit_code)
        sort_order = connection.execute(
            text('SELECT COALESCE(MAX(sort_order), 0) + 1 FROM cafeteria.shopping_list_manual_items WHERE shopping_list_id=:id'),
            {'id': list_id},
        ).scalar_one()
        public_id = connection.execute(
            text('''INSERT INTO cafeteria.shopping_list_manual_items(
                        shopping_list_id, sort_order, item_text, quantity, unit_id, created_by, updated_by)
                    VALUES (:list, :sort, :text, :quantity, :unit, :actor, :actor) RETURNING public_id'''),
            {'list': list_id, 'sort': sort_order, 'text': item_text, 'quantity': amount, 'unit': unit_id, 'actor': scope.actor_id},
        ).scalar_one()
    return str(public_id)


def update_manual_item(
    engine: Engine, scope: ShoppingScope, list_public_id: str, item_public_id: str, *, expected_row_version: int,
    item_text: str, quantity: str | None = None, unit_code: str | None = None,
) -> int:
    item_text = _text(item_text, 200, field='item_text')
    _positive(expected_row_version, 'expected_row_version')
    with _transaction(engine, scope) as connection:
        row = _lock_manual_item(connection, scope, list_public_id, item_public_id, expected_row_version)
        amount, unit_id = _resolve_manual_unit(connection, quantity, unit_code)
        return connection.execute(
            text('''UPDATE cafeteria.shopping_list_manual_items
                    SET item_text=:text, quantity=:quantity, unit_id=:unit, updated_by=:actor
                    WHERE id=:id RETURNING row_version'''),
            {'text': item_text, 'quantity': amount, 'unit': unit_id, 'actor': scope.actor_id, 'id': row['id']},
        ).scalar_one()


def set_manual_item_checked(
    engine: Engine, scope: ShoppingScope, list_public_id: str, item_public_id: str, *, expected_row_version: int, checked: bool,
) -> int:
    if type(checked) is not bool:
        raise ShoppingListValidationError('checked muss boolesch sein.')
    _positive(expected_row_version, 'expected_row_version')
    with _transaction(engine, scope) as connection:
        row = _lock_manual_item(connection, scope, list_public_id, item_public_id, expected_row_version)
        return connection.execute(
            text('UPDATE cafeteria.shopping_list_manual_items SET checked=:checked, updated_by=:actor WHERE id=:id '
                 'RETURNING row_version'),
            {'checked': checked, 'actor': scope.actor_id, 'id': row['id']},
        ).scalar_one()


def delete_manual_item(
    engine: Engine, scope: ShoppingScope, list_public_id: str, item_public_id: str, *, expected_row_version: int,
) -> None:
    _positive(expected_row_version, 'expected_row_version')
    with _transaction(engine, scope) as connection:
        row = _lock_manual_item(connection, scope, list_public_id, item_public_id, expected_row_version)
        connection.execute(text('DELETE FROM cafeteria.shopping_list_manual_items WHERE id=:id'), {'id': row['id']})
