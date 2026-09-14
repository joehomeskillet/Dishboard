"""MP-REC-SHOPPING-PERSIST store: shopping lists, immutable compute revisions, manual items.

``line_key`` = ``sha256(json([status, unit_code, captured]))[:16] + ':' + readable`` (<= 300 chars,
right-trimmed): ``captured`` is the identity/unit/factor tuple ``AggregateLine`` merged on (or the
normalized free text of an incomplete row), ``readable`` the food public id or that text. A checked
row follows a recompute only with an unchanged quantity+unit signature; otherwise it keeps its old
revision and reads as ``changed_open``. Only ``set_line_checked(checked=False)`` deletes a row.

``_transaction`` re-checks the original actor (active, unchanged ``authz_version``, draft role; writes
hold ``FOR SHARE`` on the user) and the active location, and maps SQLSTATEs without database details.
``compute_revision`` (REPEATABLE READ) takes SHARE ROW EXCLUSIVE on ``shopping_list_line_status``
before its snapshot, ``set_line_checked`` ROW EXCLUSIVE and then the list row lock: a check never
lands on a superseded revision and a recompute never misses a committed check. No SECURITY DEFINER
verb, no audit write (the app holds only SELECT on ``audit_events``); revision reads reuse the
verified private reader ``recipe_reads._get_revision_connection``.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from .component_catalog_store import ComponentCatalogConfigurationError, resolve_single_active_location_connection
from .quantities import FoodFactors, QuantityError, Unit, parse_quantity
from .recipe_reads import _get_revision_connection
from .recipe_types import RecipeValidationError
from .recipe_values import recipe_text
from .shopping_aggregate import AggregateLine, IngredientNeed, RevisionNeed, aggregate

_POLICIES = ('leaf', 'prepared')
_LOCK_TIMEOUT = "SET LOCAL lock_timeout = '5s'"
_MODES = {
    'read': ('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY',),
    'write': (_LOCK_TIMEOUT,),
    'compute': ('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ', _LOCK_TIMEOUT,
                'LOCK TABLE cafeteria.shopping_list_line_status IN SHARE ROW EXCLUSIVE MODE'),
    'check': (_LOCK_TIMEOUT, 'LOCK TABLE cafeteria.shopping_list_line_status IN ROW EXCLUSIVE MODE'),
}
_ACTOR = '''SELECT u.disabled_at IS NULL AS active, u.authz_version, EXISTS (
    SELECT 1 FROM cafeteria.user_role_cache r JOIN cafeteria.application_roles a ON a.role_code=r.role_code AND a.active
    WHERE r.user_id=u.id AND r.role_code IN ('Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin')
) AS drafts FROM cafeteria.users u WHERE u.id=:actor'''


class ShoppingListError(ValueError):
    """Base class; messages never carry database details."""
class ShoppingListValidationError(ShoppingListError):
    """Invalid input, including SQLSTATE 22xxx/23502/23503/23514."""
class ShoppingListNotFoundError(ShoppingListError):
    """List, line, item or location not visible in the scope."""
class ShoppingListConflictError(ShoppingListError):
    """Original row_version CAS or SQLSTATE 23505/55000; reload before retrying."""
class ShoppingListRetryError(ShoppingListConflictError):
    """SQLSTATE 40001/40P01/55P03 (serialization, deadlock, lock timeout); the same request may be retried."""
class ShoppingListActorDeniedError(ShoppingListError):
    """Original actor missing, disabled or without a draft role."""
class ShoppingListStaleActorError(ShoppingListActorDeniedError):
    """Original actor's authz_version changed since the page was loaded."""
class ShoppingListUnavailableError(ShoppingListError):
    """Any other database or location configuration failure."""


@dataclass(frozen=True)
class ShoppingScope:
    """Original actor scope with ``AdminScope`` field names; location-wide, no profile (SDD 8.4)."""
    actor_id: int
    location_id: int
    expected_authz_version: int

    def __post_init__(self) -> None:
        for label in ('actor_id', 'location_id', 'expected_authz_version'):
            _positive(getattr(self, label), label)


def _mapped(state: str) -> ShoppingListError:
    if state in ('40001', '40P01', '55P03'):
        return ShoppingListRetryError('Die Einkaufsliste wird gerade bearbeitet. Bitte erneut versuchen.')
    if state in ('23505', '55000'):
        return ShoppingListConflictError('Die Einkaufsliste wurde zwischenzeitlich geändert. Bitte neu laden.')
    if state.startswith('22') or state in ('23502', '23503', '23514'):
        return ShoppingListValidationError('Die Angaben sind ungültig.')
    return ShoppingListUnavailableError('Einkaufslisten sind derzeit nicht verfügbar.')


@contextmanager
def _transaction(engine: Engine, scope: ShoppingScope, mode: str = 'write') -> Iterator[Connection]:
    try:
        with engine.begin() as connection:
            for statement in _MODES[mode]:
                connection.execute(text(statement))
            actor = connection.execute(text(_ACTOR if mode == 'read' else _ACTOR + ' FOR SHARE OF u'),
                                       {'actor': scope.actor_id}).mappings().one_or_none()
            if actor is None or not actor['active']:
                raise ShoppingListActorDeniedError('Aktiver Benutzer erforderlich.')
            if actor['authz_version'] != scope.expected_authz_version:
                raise ShoppingListStaleActorError('Berechtigung wurde geändert. Bitte neu laden.')
            if not actor['drafts']:
                raise ShoppingListActorDeniedError('Einkaufslisten sind nicht erlaubt.')
            if resolve_single_active_location_connection(connection) != scope.location_id:
                raise ShoppingListNotFoundError('Standort nicht gefunden.')
            yield connection
    except ComponentCatalogConfigurationError:
        raise ShoppingListUnavailableError('Genau ein aktiver Standort ist erforderlich.') from None
    except DBAPIError as error:
        raise _mapped(getattr(error.orig, 'sqlstate', None) or '') from None


def _text(value: object, maximum: int, *, multiline: bool = False, required: bool = True) -> str | None:
    try:
        return recipe_text(value, maximum, multiline=multiline, required=required)
    except RecipeValidationError as error:
        raise ShoppingListValidationError(str(error)) from error


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise ShoppingListValidationError('UUID erforderlich.')
    try:
        return str(UUID(value))
    except ValueError:
        raise ShoppingListValidationError('Ungültige UUID.') from None


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ShoppingListValidationError(f'{label} muss eine positive Ganzzahl sein.')
    return value


def _decimal_str(value: Decimal | None) -> str | None:
    return format(value, 'f') if value is not None else None


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


def list_shopping_lists(engine: Engine, scope: ShoppingScope, *, include_archived: bool = False) -> tuple[dict[str, object], ...]:
    with _transaction(engine, scope, 'read') as connection:
        rows = connection.execute(
            text('''
                SELECT l.public_id, l.title, l.note, w.public_id AS menu_week_public_id, l.row_version,
                       l.archived_at, latest.public_id AS latest_revision_public_id,
                       latest.revision_number AS latest_revision_number, latest.computed_at AS latest_computed_at,
                       COALESCE(jsonb_array_length(latest.snapshot_json->'result'->'lines'), 0) AS total_lines,
                       COALESCE(checked.checked_count, 0) AS checked_count
                FROM cafeteria.shopping_lists l
                LEFT JOIN cafeteria.menu_weeks w ON w.id=l.menu_week_id
                LEFT JOIN LATERAL (
                    SELECT id, public_id, revision_number, computed_at, snapshot_json
                    FROM cafeteria.shopping_list_revisions r WHERE r.shopping_list_id=l.id
                    ORDER BY r.revision_number DESC LIMIT 1
                ) latest ON true
                LEFT JOIN LATERAL (
                    SELECT count(*) AS checked_count FROM cafeteria.shopping_list_line_status s
                    WHERE s.shopping_list_id=l.id AND s.revision_id=latest.id
                ) checked ON true
                WHERE l.location_id=:location AND (:archived OR l.archived_at IS NULL)
                ORDER BY l.created_at DESC, l.public_id
            '''),
            {'location': scope.location_id, 'archived': include_archived},
        ).mappings().all()
    return tuple({
        'public_id': str(row['public_id']), 'title': row['title'], 'note': row['note'],
        'menu_week_public_id': str(row['menu_week_public_id']) if row['menu_week_public_id'] else None,
        'row_version': row['row_version'], 'archived_at': row['archived_at'],
        'latest_revision_public_id': str(row['latest_revision_public_id']) if row['latest_revision_public_id'] else None,
        'latest_revision_number': row['latest_revision_number'], 'latest_computed_at': row['latest_computed_at'],
        'open_count': row['total_lines'] - row['checked_count'], 'checked_count': row['checked_count'],
    } for row in rows)


def create_shopping_list(
    engine: Engine, scope: ShoppingScope, *, title: str, note: str | None = None, menu_week_public_id: str | None = None,
) -> str:
    title = _text(title, 120)
    note = _text(note, 2000, multiline=True, required=False)
    with _transaction(engine, scope) as connection:
        week_id = None
        if menu_week_public_id is not None:  # the schema does not tie the week to the list's location
            week_id = connection.execute(
                text('SELECT id FROM cafeteria.menu_weeks WHERE public_id=CAST(:id AS uuid) AND location_id=:location'),
                {'id': _uuid(menu_week_public_id), 'location': scope.location_id},
            ).scalar_one_or_none()
            if week_id is None:
                raise ShoppingListValidationError('Woche gehört nicht zum Standort.')
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


def get_shopping_list(engine: Engine, scope: ShoppingScope, public_id: str) -> dict[str, object]:
    with _transaction(engine, scope, 'read') as connection:
        head = connection.execute(
            text('SELECT id, public_id, title, note, row_version, archived_at, '
                 '(SELECT public_id FROM cafeteria.menu_weeks WHERE id=shopping_lists.menu_week_id) AS menu_week_public_id '
                 'FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid) AND location_id=:location'),
            {'id': _uuid(public_id), 'location': scope.location_id},
        ).mappings().one_or_none()
        if head is None:
            raise ShoppingListNotFoundError('Einkaufsliste nicht gefunden.')
        revisions = connection.execute(
            text('SELECT public_id, revision_number, policy, computed_at, computed_by '
                 'FROM cafeteria.shopping_list_revisions WHERE shopping_list_id=:id ORDER BY revision_number DESC'),
            {'id': head['id']},
        ).mappings().all()
        manual_items = connection.execute(
            text('''SELECT m.public_id, m.sort_order, m.item_text, m.quantity, u.code AS unit_code, m.checked, m.row_version
                    FROM cafeteria.shopping_list_manual_items m LEFT JOIN cafeteria.measurement_units u ON u.id=m.unit_id
                    WHERE m.shopping_list_id=:id ORDER BY m.sort_order'''),
            {'id': head['id']},
        ).mappings().all()
        selected = None
        if revisions:
            latest = revisions[0]
            row = connection.execute(
                text('SELECT id, snapshot_json FROM cafeteria.shopping_list_revisions WHERE public_id=:id'),
                {'id': latest['public_id']},
            ).mappings().one()
            statuses = connection.execute(
                text('SELECT line_key, revision_id FROM cafeteria.shopping_list_line_status WHERE shopping_list_id=:id'),
                {'id': head['id']},
            ).mappings().all()
            by_key = {status['line_key']: status['revision_id'] for status in statuses}
            lines, incomplete = [], []
            for raw in row['snapshot_json']['result']['lines']:
                revision_id = by_key.get(raw['line_key'])
                checked_status = 'open' if revision_id is None else ('checked' if revision_id == row['id'] else 'changed_open')
                target = incomplete if raw['completeness'] == 'incomplete' else lines
                target.append({**raw, 'checked_status': checked_status})
            selected = {
                'public_id': str(latest['public_id']), 'revision_number': latest['revision_number'],
                'policy': latest['policy'], 'computed_at': latest['computed_at'],
                'inputs': row['snapshot_json']['inputs'], 'lines': lines, 'incomplete_lines': incomplete,
            }
    return {
        'public_id': str(head['public_id']), 'title': head['title'], 'note': head['note'],
        'row_version': head['row_version'], 'archived_at': head['archived_at'],
        'menu_week_public_id': str(head['menu_week_public_id']) if head['menu_week_public_id'] else None,
        'revisions': tuple({
            'public_id': str(row['public_id']), 'revision_number': row['revision_number'], 'policy': row['policy'],
            'computed_at': row['computed_at'], 'computed_by': row['computed_by'],
        } for row in revisions),
        'selected_revision': selected,
        'manual_items': tuple({
            'public_id': str(row['public_id']), 'sort_order': row['sort_order'], 'item_text': row['item_text'],
            'quantity': _decimal_str(row['quantity']), 'unit_code': row['unit_code'], 'checked': row['checked'],
            'row_version': row['row_version'],
        } for row in manual_items),
    }


def candidate_components(engine: Engine, scope: ShoppingScope, *, menu_week_public_id: str) -> tuple[dict[str, object], ...]:
    with _transaction(engine, scope, 'read') as connection:
        rows = connection.execute(
            text('''
                SELECT it.public_id AS menu_item_public_id, it.title AS menu_item_title, srv.service_date,
                       mp.code AS meal_period_code, mp.display_name AS meal_period_display_name,
                       c.sort_order, c.component_text, rr.public_id AS recipe_revision_public_id, r.title AS recipe_title,
                       c.target_quantity, tu.code AS target_quantity_unit_code,
                       rr.snapshot_json->'recipe'->>'servings' AS declared_servings,
                       rr.snapshot_json->'recipe'->>'servings_unit_code' AS declared_unit_code
                FROM cafeteria.menu_weeks w
                JOIN cafeteria.menu_services srv ON srv.menu_week_id=w.id
                JOIN cafeteria.meal_periods mp ON mp.id=srv.meal_period_id
                JOIN cafeteria.menu_items it ON it.service_id=srv.id
                JOIN cafeteria.menu_item_components c ON c.menu_item_id=it.id
                JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
                JOIN cafeteria.recipes r ON r.id=rr.recipe_id
                LEFT JOIN cafeteria.measurement_units tu ON tu.id=c.target_quantity_unit_id
                WHERE w.location_id=:location AND w.public_id=CAST(:week AS uuid) AND c.recipe_revision_id IS NOT NULL
                ORDER BY srv.service_date, mp.sort_order, it.sort_order, c.sort_order
            '''),
            {'location': scope.location_id, 'week': _uuid(menu_week_public_id)},
        ).mappings().all()
    return tuple({
        'component_id': f'{row["menu_item_public_id"]}:{row["sort_order"]}',
        'menu_item_public_id': str(row['menu_item_public_id']), 'menu_item_title': row['menu_item_title'],
        'service_date': row['service_date'], 'meal_period_code': row['meal_period_code'],
        'meal_period_display_name': row['meal_period_display_name'], 'component_text': row['component_text'],
        'recipe_revision_public_id': str(row['recipe_revision_public_id']), 'recipe_title': row['recipe_title'],
        'target_quantity': _decimal_str(row['target_quantity']) or row['declared_servings'],
        'target_quantity_unit_code': row['target_quantity_unit_code'] or row['declared_unit_code'],
    } for row in rows)


def _resolve_selected_components(connection: Connection, location_id: int, component_ids: Sequence[str]) -> list[Mapping[str, object]]:
    if not component_ids:
        raise ShoppingListValidationError('Mindestens ein Baustein muss ausgewählt werden.')
    items, sorts = [], []
    for value in component_ids:
        if not isinstance(value, str) or ':' not in value:
            raise ShoppingListValidationError('Ungültige Bausteinauswahl.')
        item, _, sort_order = value.rpartition(':')
        if not sort_order.isdigit():
            raise ShoppingListValidationError('Ungültige Bausteinauswahl.')
        items.append(_uuid(item))
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
        raise ShoppingListValidationError('Auswahl enthält einen nicht gebundenen oder fremden Baustein.')
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


def _line_key(line: AggregateLine) -> str:
    captured = [format(value, 'f') if isinstance(value, Decimal) else value for value in line.captured]
    digest = hashlib.sha256(json.dumps([line.status, line.unit_code, captured], sort_keys=True).encode('utf-8')).hexdigest()[:16]
    if line.food_public_id is not None:
        readable = line.food_public_id
    else:
        raw = line.captured[1] if len(line.captured) > 1 and isinstance(line.captured[1], str) else ''
        readable = ' '.join(unicodedata.normalize('NFC', raw).split()) or 'freitext'
    return f'{digest}:{readable}'[:300].rstrip()


def _line_signature(quantity: Decimal | None, unit_code: str) -> str:
    return f'{format(quantity, "f")} {unit_code}' if quantity is not None else 'incomplete'


def compute_revision(
    engine: Engine, scope: ShoppingScope, list_public_id: str, *, component_ids: Sequence[str], policy: str,
    expected_row_version: int,
) -> str:
    if policy not in _POLICIES:
        raise ShoppingListValidationError('Bedarfspolitik ist leaf oder prepared.')
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
        result_lines = [{
            'food_public_id': line.food_public_id, 'quantity': _decimal_str(line.quantity), 'unit_code': line.unit_code,
            'completeness': line.status, 'reason': line.reason, 'line_key': _line_key(line),
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
        raise ShoppingListValidationError('Menge und Einheit müssen gemeinsam angegeben werden.')
    if quantity is None:
        return None, None
    unit_id = connection.execute(
        text('SELECT id FROM cafeteria.measurement_units WHERE code=:code'), {'code': unit_code},
    ).scalar_one_or_none()
    if unit_id is None:
        raise ShoppingListValidationError('Einheit ist unbekannt.')
    try:
        return parse_quantity(quantity), unit_id
    except QuantityError as error:
        raise ShoppingListValidationError(str(error)) from error


def _lock_manual_item(connection: Connection, scope: ShoppingScope, list_public_id: str, item_public_id: str) -> Mapping[str, object]:
    row = connection.execute(
        text('''SELECT m.id, m.shopping_list_id, m.row_version FROM cafeteria.shopping_list_manual_items m
                JOIN cafeteria.shopping_lists l ON l.id=m.shopping_list_id
                WHERE m.public_id=CAST(:item AS uuid) AND l.public_id=CAST(:list AS uuid) AND l.location_id=:location
                FOR UPDATE'''),
        {'item': _uuid(item_public_id), 'list': _uuid(list_public_id), 'location': scope.location_id},
    ).mappings().one_or_none()
    if row is None:
        raise ShoppingListNotFoundError('Position nicht gefunden.')
    return row


def add_manual_item(
    engine: Engine, scope: ShoppingScope, list_public_id: str, *, item_text: str,
    quantity: str | None = None, unit_code: str | None = None,
) -> str:
    item_text = _text(item_text, 200)
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
    item_text = _text(item_text, 200)
    _positive(expected_row_version, 'expected_row_version')
    with _transaction(engine, scope) as connection:
        row = _lock_manual_item(connection, scope, list_public_id, item_public_id)
        if row['row_version'] != expected_row_version:
            raise ShoppingListConflictError('Die Position wurde zwischenzeitlich geändert.')
        amount, unit_id = _resolve_manual_unit(connection, quantity, unit_code)
        return connection.execute(
            text('''UPDATE cafeteria.shopping_list_manual_items
                    SET item_text=:text, quantity=:quantity, unit_id=:unit, updated_by=:actor
                    WHERE id=:id RETURNING row_version'''),
            {'text': item_text, 'quantity': amount, 'unit': unit_id, 'actor': scope.actor_id, 'id': row['id']},
        ).scalar_one()


def set_manual_item_checked(engine: Engine, scope: ShoppingScope, list_public_id: str, item_public_id: str, *, checked: bool) -> int:
    if type(checked) is not bool:
        raise ShoppingListValidationError('checked muss boolesch sein.')
    with _transaction(engine, scope) as connection:
        row = _lock_manual_item(connection, scope, list_public_id, item_public_id)
        return connection.execute(
            text('UPDATE cafeteria.shopping_list_manual_items SET checked=:checked, updated_by=:actor WHERE id=:id '
                 'RETURNING row_version'),
            {'checked': checked, 'actor': scope.actor_id, 'id': row['id']},
        ).scalar_one()


def delete_manual_item(engine: Engine, scope: ShoppingScope, list_public_id: str, item_public_id: str) -> None:
    with _transaction(engine, scope) as connection:
        row = _lock_manual_item(connection, scope, list_public_id, item_public_id)
        connection.execute(text('DELETE FROM cafeteria.shopping_list_manual_items WHERE id=:id'), {'id': row['id']})
