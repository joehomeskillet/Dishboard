"""Scoped pre-read, sorted head locks and aggregate-state recheck for menu writers.

Prepare after the original actor guard and BEFORE Week/Service/Item locks. Recheck
after those aggregate locks, before any mutation. A changed pre-read is a conflict;
this module never acquires a newly discovered head after an aggregate lock.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import Connection, RootTransaction, text

from .component_assignment_contract import Assignment
from .component_catalog_store import AdminScope, ComponentConflictError, ComponentNotFoundError
from .workflow_write_context import actor_parameters, begin_write


@dataclass
class BindingState:
    connection: Connection
    transaction: RootTransaction
    scope: AdminScope
    item_ids: tuple[int, ...]
    weeks: tuple[date, ...]
    create_weeks: tuple[date, ...]
    items: list[dict[str, Any]]
    links: list[dict[str, Any]]
    components: dict[str, dict[str, Any]]
    recipes: dict[str, dict[str, Any]]
    foods: dict[int, dict[str, Any]]
    checked: bool = field(default=False, init=False)

    def recheck(self) -> None:
        self.require_transaction()
        ids = sorted(int(row['id']) for row in self.components.values())
        locked = _components(self.connection, self.scope, ids=ids, lock=True)
        if (locked != self.components or _items(self.connection, self.scope, self.item_ids,
                                               self.weeks) != self.items):
            raise ComponentConflictError('Menü oder Komponenten wurden zwischenzeitlich geändert.')
        current_links = _links(self.connection, [int(row['id']) for row in self.items], lock=True)
        if current_links != self.links:
            raise ComponentConflictError('Komponentenzuweisungen wurden zwischenzeitlich geändert.')
        self.checked = True

    def require_transaction(self) -> None:
        if not self.transaction.is_active or self.connection.get_transaction() is not self.transaction:
            raise ComponentConflictError('Bindungskontext gehört nicht zur laufenden Transaktion.')

    def require_item(self, connection: Connection, scope: AdminScope, item_id: int) -> None:
        self.require_transaction()
        if not self.checked or self.connection is not connection or self.scope != scope:
            raise ComponentConflictError('Geprüfter Bindungskontext fehlt.')
        if any(int(row['id']) == item_id for row in self.items):
            return
        # A caller may insert a new item only into its prepared week, after recheck.
        rows = _items(connection, scope, (item_id,), ())
        if (len(rows) != 1 or rows[0]['row_version'] != 1
                or rows[0]['week_start'] not in self.create_weeks):
            raise ComponentConflictError('Menü gehört nicht zum vorbereiteten Schreibvorgang.')

    def old_links(self, item_id: int) -> list[dict[str, Any]]:
        return [row for row in self.links if int(row['menu_item_id']) == item_id]


def _items(connection: Connection, scope: AdminScope, ids: Sequence[int],
           weeks: Sequence[date]) -> list[dict[str, Any]]:
    rows = connection.execute(text('''
        SELECT i.id,i.public_id::text,i.row_version,i.service_id,w.id AS week_id,w.week_start
        FROM cafeteria.menu_items i JOIN cafeteria.menu_services s ON s.id=i.service_id
        JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
        JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
        WHERE w.location_id=:location AND p.code=:profile
          AND (i.id=ANY(CAST(:ids AS bigint[])) OR w.week_start=ANY(CAST(:weeks AS date[])))
        ORDER BY i.id
    '''), {'location': scope.location_id, 'profile': scope.profile_code,
           'ids': list(ids), 'weeks': list(weeks)}).mappings()
    return [dict(row) for row in rows]


def _links(connection: Connection, item_ids: Sequence[int], *, lock: bool = False
           ) -> list[dict[str, Any]]:
    statement = '''
        SELECT l.menu_item_id,l.sort_order,l.component_id,l.component_text,l.component_row_version,
               l.recipe_revision_id,c.public_id::text AS component_public_id,
               r.public_id::text AS recipe_revision_public_id,r.content_hash_sha256
        FROM cafeteria.menu_item_components l
        LEFT JOIN cafeteria.menu_components c ON c.id=l.component_id
        LEFT JOIN cafeteria.recipe_revisions r ON r.id=l.recipe_revision_id
        WHERE l.menu_item_id=ANY(CAST(:ids AS bigint[])) ORDER BY l.menu_item_id,l.sort_order
    '''
    if lock:
        statement += ' FOR UPDATE OF l'
    return [dict(row) for row in connection.execute(text(statement),
                                                   {'ids': list(item_ids)}).mappings()]


def _components(connection: Connection, scope: AdminScope, *, ids: Sequence[int] = (),
                public_ids: Sequence[str] = (), lock: bool = False
                ) -> dict[str, dict[str, Any]]:
    statement = '''
        SELECT c.id,c.public_id::text,c.name,c.row_version,c.active,c.food_id
        FROM cafeteria.menu_components c
        WHERE c.location_id=:location AND c.profile_scope IN ('common',:profile)
          AND (c.id=ANY(CAST(:ids AS bigint[])) OR c.public_id=ANY(CAST(:public_ids AS uuid[])))
        ORDER BY c.id
    '''
    if lock:
        statement += ' FOR SHARE OF c'
    rows = connection.execute(text(statement), {'location': scope.location_id,
        'profile': scope.profile_code, 'ids': list(ids), 'public_ids': list(public_ids)}).mappings()
    return {str(row['public_id']): dict(row) for row in rows}


def prepare_bindings(
    connection: Connection, scope: AdminScope, assignments: Sequence[Assignment], *,
    item_ids: Sequence[int] = (), weeks: Sequence[date] = (),
    create_weeks: Sequence[date] = (),
) -> BindingState:
    begin_write(connection, scope)
    transaction = connection.get_transaction()
    if transaction is None:
        raise ComponentConflictError('Schreibtransaktion fehlt.')
    items = _items(connection, scope, item_ids, weeks)
    if not set(item_ids) <= {int(row['id']) for row in items}:
        raise ComponentNotFoundError('Menü nicht gefunden.')
    links = _links(connection, [int(row['id']) for row in items])
    old_components = sorted({int(row['component_id']) for row in links if row['component_id']})
    wanted_components = sorted({row.component_public_id for row in assignments if row.component_public_id})
    components = _components(connection, scope, ids=old_components, public_ids=wanted_components)
    if (not set(wanted_components) <= set(components)
            or not set(old_components) <= {int(row['id']) for row in components.values()}):
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    revision_uuids = sorted({row.recipe_revision_public_id for row in assignments
                             if row.recipe_revision_public_id})
    revision_ids = {int(row['recipe_revision_id']) for row in links if row['recipe_revision_id']}
    requested = list(connection.execute(text('''
        SELECT id,public_id::text FROM cafeteria.recipe_revisions
        WHERE location_id=:location AND public_id=ANY(CAST(:ids AS uuid[])) ORDER BY id
    '''), {'location': scope.location_id, 'ids': revision_uuids}).mappings())
    if set(revision_uuids) != {str(row['public_id']) for row in requested}:
        raise ComponentNotFoundError('Rezeptrevision nicht gefunden.')
    revision_ids.update(int(row['id']) for row in requested)
    food_ids = sorted({int(row['food_id']) for row in components.values() if row['food_id']})
    params = actor_parameters(scope)
    food_rows = connection.execute(text(
        'SELECT * FROM cafeteria.lock_component_foods_v26(:actor,:authz,:location,CAST(:ids AS bigint[]))'
    ), {**params, 'ids': food_ids}).mappings()
    foods = {int(row['food_id']): dict(row) for row in food_rows}
    recipe_rows = connection.execute(text(
        'SELECT * FROM cafeteria.lock_menu_recipe_revisions_v26(:actor,:authz,:location,CAST(:ids AS bigint[]))'
    ), {**params, 'ids': sorted(revision_ids)}).mappings()
    recipes = {str(row['revision_public_id']): dict(row) for row in recipe_rows}
    return BindingState(connection, transaction, scope, tuple(item_ids), tuple(weeks),
                        tuple(sorted(set(weeks) | set(create_weeks))),
                        items, links, components, recipes, foods)


def payloads_from_links(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, object]]:
    return [{'component_public_id': row['component_public_id'],
             'component_text': None if row['component_public_id'] else row['component_text'],
             'recipe_revision_public_id': row['recipe_revision_public_id']} for row in rows]
