"""MP-REC-SHOPPING-PERSIST shared guard and read paths; callers import every public name from ``shopping_list_store``.

``_transaction`` re-checks the original actor (active, unchanged ``authz_version``, draft role; writes hold ``FOR SHARE``
on the user) and the active location, and maps SQLSTATEs without database details. ``get_shopping_list`` renders any
revision of a list from that revision's own immutable snapshot, including the food/unit display names captured by
``compute_revision``; only the newest revision carries a check status, an older one reads ``not_current``.
Validation errors name the offending input in ``field`` when it is known.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from .component_catalog_store import ComponentCatalogConfigurationError, resolve_single_active_location_connection
from .recipe_types import RecipeValidationError
from .recipe_values import recipe_text

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
    """Base class; messages never carry database details. ``field`` names the offending input, if known."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class ShoppingListValidationError(ShoppingListError):
    """Invalid input, including SQLSTATE 22xxx/23502/23503/23514 (those without ``field``)."""
class ShoppingListNotFoundError(ShoppingListError):
    """List, revision, line, item or location not visible in the scope."""
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


def _text(value: object, maximum: int, *, field: str, multiline: bool = False, required: bool = True) -> str | None:
    try:
        return recipe_text(value, maximum, multiline=multiline, required=required)
    except RecipeValidationError as error:
        raise ShoppingListValidationError(str(error), field=field) from error


def _uuid(value: object, field: str | None = None) -> str:
    if not isinstance(value, str):
        raise ShoppingListValidationError('UUID erforderlich.', field=field)
    try:
        return str(UUID(value))
    except ValueError:
        raise ShoppingListValidationError('Ungültige UUID.', field=field) from None


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ShoppingListValidationError(f'{label} muss eine positive Ganzzahl sein.')
    return value


def _decimal_str(value: Decimal | None) -> str | None:
    return format(value, 'f') if value is not None else None


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


def _revision_view(connection: Connection, list_id: int, revision: Mapping[str, object], *, is_latest: bool) -> dict[str, object]:
    snapshot = connection.execute(
        text('SELECT snapshot_json FROM cafeteria.shopping_list_revisions WHERE id=:id'), {'id': revision['id']},
    ).scalar_one()
    by_key: dict[str, int] = {}
    if is_latest:  # a check status belongs to the newest revision only; older receipts never show one
        by_key = dict(connection.execute(
            text('SELECT line_key, revision_id FROM cafeteria.shopping_list_line_status WHERE shopping_list_id=:id'),
            {'id': list_id},
        ).tuples().all())
    lines: list[dict[str, object]] = []
    incomplete: list[dict[str, object]] = []
    for raw in snapshot['result']['lines']:
        status = 'not_current'
        if is_latest:
            checked_on = by_key.get(raw['line_key'])
            status = 'open' if checked_on is None else ('checked' if checked_on == revision['id'] else 'changed_open')
        target = incomplete if raw['completeness'] == 'incomplete' else lines
        target.append({'food_name': None, 'ingredient_text': None, 'unit_name': None, **raw, 'checked_status': status})
    return {
        'public_id': str(revision['public_id']), 'revision_number': revision['revision_number'],
        'policy': revision['policy'], 'computed_at': revision['computed_at'], 'is_latest': is_latest,
        'inputs': snapshot['inputs'], 'lines': lines, 'incomplete_lines': incomplete,
    }


def get_shopping_list(
    engine: Engine, scope: ShoppingScope, public_id: str, *, revision_public_id: str | None = None,
) -> dict[str, object]:
    """Head, revision list, manual items and ``selected_revision`` (the newest one, or ``revision_public_id``)."""
    wanted = _uuid(revision_public_id, 'revision') if revision_public_id is not None else None
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
            text('SELECT id, public_id, revision_number, policy, computed_at, computed_by '
                 'FROM cafeteria.shopping_list_revisions WHERE shopping_list_id=:id ORDER BY revision_number DESC'),
            {'id': head['id']},
        ).mappings().all()
        manual_items = connection.execute(
            text('''SELECT m.public_id, m.sort_order, m.item_text, m.quantity, u.code AS unit_code, m.checked, m.row_version
                    FROM cafeteria.shopping_list_manual_items m LEFT JOIN cafeteria.measurement_units u ON u.id=m.unit_id
                    WHERE m.shopping_list_id=:id ORDER BY m.sort_order'''),
            {'id': head['id']},
        ).mappings().all()
        chosen = next((row for row in revisions if wanted is None or str(row['public_id']) == wanted), None)
        if wanted is not None and chosen is None:
            raise ShoppingListNotFoundError('Revision nicht gefunden.')
        selected = None if chosen is None else _revision_view(connection, head['id'], chosen, is_latest=chosen is revisions[0])
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


def candidate_components(
    engine: Engine, scope: ShoppingScope, *, date_from: date, date_to: date,
    menu_week_public_id: str | None = None,
) -> tuple[dict[str, object], ...]:
    if date_to < date_from:
        raise ShoppingListValidationError('date_to liegt vor date_from', field='date_to')
    params: dict[str, object] = {
        'location': scope.location_id, 'date_from': date_from, 'date_to': date_to,
    }
    week_sql = ''
    if menu_week_public_id is not None:
        week_sql = ' AND w.public_id=CAST(:week AS uuid)'
        params['week'] = _uuid(menu_week_public_id)
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
                WHERE w.location_id=:location AND srv.service_date BETWEEN :date_from AND :date_to
                  AND c.recipe_revision_id IS NOT NULL''' + week_sql + '''
                ORDER BY srv.service_date, mp.sort_order, it.sort_order, c.sort_order
            '''),
            params,
        ).mappings().all()
        event_rows = connection.execute(
            text('''
                SELECT e.public_id AS menu_item_public_id, e.title AS menu_item_title, e.event_date AS service_date,
                       d.sort_order, d.component_text, rr.public_id AS recipe_revision_public_id,
                       r.title AS recipe_title, d.target_quantity, tu.code AS target_quantity_unit_code
                FROM cafeteria.kitchen_events e
                JOIN cafeteria.kitchen_event_demand_items d ON d.event_id=e.id
                JOIN cafeteria.recipe_revisions rr ON rr.id=d.recipe_revision_id
                JOIN cafeteria.recipes r ON r.id=rr.recipe_id
                JOIN cafeteria.measurement_units tu ON tu.id=d.target_quantity_unit_id
                WHERE e.location_id=:location AND e.archived_at IS NULL
                  AND e.event_date BETWEEN :date_from AND :date_to
                ORDER BY e.event_date, d.sort_order
            '''),
            {'location': params['location'], 'date_from': params['date_from'], 'date_to': params['date_to']},
        ).mappings().all()
    menu = [{
        'component_id': f'{row["menu_item_public_id"]}:{row["sort_order"]}',
        'menu_item_public_id': str(row['menu_item_public_id']), 'menu_item_title': row['menu_item_title'],
        'service_date': row['service_date'], 'meal_period_code': row['meal_period_code'],
        'meal_period_display_name': row['meal_period_display_name'], 'component_text': row['component_text'],
        'recipe_revision_public_id': str(row['recipe_revision_public_id']), 'recipe_title': row['recipe_title'],
        'target_quantity': _decimal_str(row['target_quantity']) or row['declared_servings'],
        'target_quantity_unit_code': row['target_quantity_unit_code'] or row['declared_unit_code'],
        'source': 'menu',
    } for row in rows]
    events = [{
        'component_id': f'event:{row["menu_item_public_id"]}:{row["sort_order"]}',
        'menu_item_public_id': str(row['menu_item_public_id']), 'menu_item_title': row['menu_item_title'],
        'service_date': row['service_date'], 'meal_period_code': 'EVENT',
        'meal_period_display_name': 'Anlass', 'component_text': row['component_text'],
        'recipe_revision_public_id': str(row['recipe_revision_public_id']), 'recipe_title': row['recipe_title'],
        'target_quantity': _decimal_str(row['target_quantity']),
        'target_quantity_unit_code': row['target_quantity_unit_code'],
        'source': 'event',
    } for row in event_rows]
    return tuple(menu + events)
