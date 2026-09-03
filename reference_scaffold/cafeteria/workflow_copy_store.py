from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from sqlalchemy import Connection, Engine, text

from .component_catalog_store import (
    AdminScope,
    ComponentCatalogValidationError,
    ComponentConflictError,
    ComponentNotFoundError,
    resolve_single_active_location_connection,
)
from .component_effects import rematerialize_auto_effects


def copy_previous_week(
    engine: Engine, scope: AdminScope, target_week_start: date, target_row_version: int
) -> int:
    _validate_request(scope, target_week_start, target_row_version)
    source_week_start = target_week_start - timedelta(days=7)
    with engine.begin() as connection:
        _require_scope(connection, scope)
        profile_id = _profile_id(connection, scope.profile_code)
        weeks = _lock_weeks(connection, scope.location_id, profile_id,
                            source_week_start, target_week_start)
        source = weeks.get(source_week_start)
        if source is None or str(source['workflow_state']) != 'draft':
            raise ComponentNotFoundError('Gespeicherte Vorwoche nicht gefunden.')
        target = _resolve_target(connection, scope, profile_id, target_week_start,
                                 target_row_version, source, weeks.get(target_week_start))
        source_id = int(source['id'])
        target_id = int(target['id'])
        _lock_services(connection, source_id, target_id)
        items = _lock_items(connection, source_id, target_id)
        if any(int(item['menu_week_id']) == target_id for item in items):
            raise ComponentConflictError('Zielwoche enthält bereits Menüs.')
        source_items = [item for item in items if int(item['menu_week_id']) == source_id]
        source_item_ids = [int(item['id']) for item in source_items]
        _lock_source_components(connection, scope, source_item_ids)
        _lock_source_links(connection, source_item_ids)
        children = _lock_source_children(connection, source_item_ids)
        _reject_active_publication(connection, target_id)
        _validate_prices(scope.profile_code, source_item_ids, children['prices'])
        result_version = (
            1 if bool(target['created'])
            else _update_existing_target(connection, target_id, source, scope.actor_id)
        )
        connection.execute(
            text('DELETE FROM cafeteria.menu_services WHERE menu_week_id=:week_id'),
            {'week_id': target_id},
        )
        _clone_tree(connection, scope, source_id, target_id)
        return result_version


def _validate_request(scope: AdminScope, target: date, version: int) -> None:
    if not isinstance(scope, AdminScope):
        raise ComponentCatalogValidationError('Ungültiger Admin-Scope.')
    if type(target) is not date or target.isoweekday() != 1:
        raise ComponentCatalogValidationError('Zielwoche muss ein ISO-Montag sein.')
    if type(version) is not int or version < 0:
        raise ComponentCatalogValidationError('Ungültige Zielversion.')


def _require_scope(connection: Connection, scope: AdminScope) -> None:
    if resolve_single_active_location_connection(connection) != scope.location_id:
        raise ComponentNotFoundError('Woche nicht gefunden.')


def _profile_id(connection: Connection, profile_code: str) -> int:
    value = connection.execute(
        text('SELECT id FROM cafeteria.offer_profiles WHERE code=:code'),
        {'code': profile_code},
    ).scalar_one_or_none()
    if value is None:
        raise ComponentNotFoundError('Woche nicht gefunden.')
    return int(value)


def _lock_weeks(
    connection: Connection, location_id: int, profile_id: int,
    source_start: date, target_start: date,
) -> dict[date, Mapping[str, object]]:
    rows = connection.execute(
        text(
            '''
            SELECT id, week_start, workflow_state, title, shared_note, row_version
            FROM cafeteria.menu_weeks
            WHERE location_id=:location_id AND profile_id=:profile_id
              AND week_start=ANY(CAST(:week_starts AS date[]))
            ORDER BY week_start FOR UPDATE
            '''
        ),
        {'location_id': location_id, 'profile_id': profile_id,
         'week_starts': [source_start, target_start]},
    ).mappings()
    return {row['week_start']: row for row in rows}  # type: ignore[misc]


def _resolve_target(
    connection: Connection, scope: AdminScope, profile_id: int, target_start: date,
    expected: int, source: Mapping[str, object], target: Mapping[str, object] | None,
) -> dict[str, object]:
    if target is not None:
        if expected == 0 or int(target['row_version']) != expected:
            raise ComponentConflictError('Zielwoche wurde zwischenzeitlich geändert.')
        return {**target, 'created': False}
    if expected > 0:
        raise ComponentNotFoundError('Zielwoche nicht gefunden.')
    inserted = connection.execute(
        text(
            '''
            INSERT INTO cafeteria.menu_weeks(
                location_id, profile_id, week_start, workflow_state, title, shared_note,
                created_by, updated_by
            ) VALUES (
                :location_id, :profile_id, :week_start, 'draft', :title, :shared_note,
                :actor_id, :actor_id
            )
            ON CONFLICT (location_id, profile_id, week_start) DO NOTHING
            RETURNING id, week_start, workflow_state, title, shared_note, row_version
            '''
        ),
        {'location_id': scope.location_id, 'profile_id': profile_id,
         'week_start': target_start, 'title': source['title'],
         'shared_note': source['shared_note'], 'actor_id': scope.actor_id},
    ).mappings().one_or_none()
    if inserted is None:
        connection.execute(
            text(
                '''SELECT id FROM cafeteria.menu_weeks
                   WHERE location_id=:location_id AND profile_id=:profile_id
                     AND week_start=:week_start FOR UPDATE'''
            ),
            {'location_id': scope.location_id, 'profile_id': profile_id,
             'week_start': target_start},
        ).one()
        raise ComponentConflictError('Zielwoche wurde zwischenzeitlich erstellt.')
    return {**inserted, 'created': True}


def _lock_services(connection: Connection, source_id: int,
                   target_id: int) -> list[Mapping[str, object]]:
    return list(connection.execute(text('''
                SELECT s.id, s.menu_week_id, s.service_date, s.meal_period_id,
                       s.service_state, s.notice
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                WHERE s.menu_week_id=ANY(CAST(:week_ids AS bigint[]))
                ORDER BY w.week_start, s.service_date, s.meal_period_id, s.id
                FOR UPDATE OF s
                '''), {'week_ids': [source_id, target_id]}).mappings())


def _lock_items(connection: Connection, source_id: int,
                target_id: int) -> list[Mapping[str, object]]:
    return list(connection.execute(text('''
                SELECT i.id, s.menu_week_id, i.service_id, i.menu_type_id,
                       mt.code AS type_code, mp.code AS meal_code, s.service_date,
                       i.dish_template_id, i.title, i.description, i.note, i.sort_order,
                       i.allergen_mode, i.origin_mode, i.label_mode
                FROM cafeteria.menu_items i
                JOIN cafeteria.menu_services s ON s.id=i.service_id
                JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                WHERE s.menu_week_id=ANY(CAST(:week_ids AS bigint[]))
                ORDER BY i.id FOR UPDATE OF i
                '''), {'week_ids': [source_id, target_id]}).mappings())


def _lock_source_components(
    connection: Connection, scope: AdminScope, item_ids: list[int]
) -> dict[str, Mapping[str, object]]:
    public_ids = list(connection.execute(text('''
                SELECT DISTINCT c.public_id::text
                FROM cafeteria.menu_item_components mic
                JOIN cafeteria.menu_components c ON c.id=mic.component_id
                WHERE mic.menu_item_id=ANY(CAST(:item_ids AS bigint[]))
                ORDER BY c.public_id::text
                '''), {'item_ids': item_ids}).scalars())
    rows = list(connection.execute(text('''
                SELECT id, public_id::text AS public_id, name, row_version, active
                FROM cafeteria.menu_components
                WHERE public_id=ANY(CAST(:public_ids AS uuid[]))
                  AND location_id=:location_id
                  AND profile_scope IN ('common', :profile_code)
                ORDER BY id FOR SHARE
                '''), {'public_ids': public_ids, 'location_id': scope.location_id,
                       'profile_code': scope.profile_code}).mappings())
    by_public_id = {str(row['public_id']): row for row in rows}
    if set(public_ids) != set(by_public_id):
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    if any(not bool(row['active']) for row in rows):
        raise ComponentConflictError('Archivierte Komponente kann nicht kopiert werden.')
    return by_public_id


def _lock_source_links(connection: Connection,
                       item_ids: list[int]) -> list[Mapping[str, object]]:
    return list(connection.execute(text('''
                SELECT mic.menu_item_id, mic.sort_order, mic.component_text,
                       c.public_id::text AS component_public_id
                FROM cafeteria.menu_item_components mic
                LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id
                WHERE mic.menu_item_id=ANY(CAST(:item_ids AS bigint[]))
                ORDER BY mic.menu_item_id, mic.sort_order FOR SHARE OF mic
                '''), {'item_ids': item_ids}).mappings())


def _lock_source_children(
    connection: Connection, item_ids: list[int]
) -> dict[str, list[Mapping[str, object]]]:
    queries = {
        'labels': '''SELECT menu_item_id, label_id FROM cafeteria.menu_item_labels
                     WHERE menu_item_id=ANY(CAST(:ids AS bigint[]))
                     ORDER BY menu_item_id, label_id FOR SHARE''',
        'allergens': '''SELECT menu_item_id, allergen_id, presence
                        FROM cafeteria.menu_item_allergens
                        WHERE menu_item_id=ANY(CAST(:ids AS bigint[]))
                        ORDER BY menu_item_id, allergen_id, presence FOR SHARE''',
        'origins': '''SELECT menu_item_id, ingredient, country_code, declaration_text
                      FROM cafeteria.origin_declarations
                      WHERE menu_item_id=ANY(CAST(:ids AS bigint[]))
                      ORDER BY menu_item_id, ingredient FOR SHARE''',
        'prices': '''SELECT menu_item_id, internal_rappen, external_rappen, currency
                     FROM cafeteria.menu_item_prices
                     WHERE menu_item_id=ANY(CAST(:ids AS bigint[]))
                     ORDER BY menu_item_id FOR SHARE''',
    }
    return {
        name: list(connection.execute(text(sql), {'ids': item_ids}).mappings())
        for name, sql in queries.items()
    }


def _reject_active_publication(connection: Connection, target_id: int) -> None:
    active = connection.execute(
        text(
            '''SELECT id FROM cafeteria.publication_revisions
               WHERE menu_week_id=:week_id AND withdrawn_at IS NULL
               ORDER BY id'''
        ),
        {'week_id': target_id},
    ).first()
    if active is not None:
        raise ComponentConflictError('Zielwoche ist aktiv publiziert.')


def _validate_prices(profile_code: str, item_ids: list[int],
                     prices: list[Mapping[str, object]]) -> None:
    priced = {int(row['menu_item_id']) for row in prices}
    if profile_code == 'patient' and prices:
        raise ComponentConflictError('Patientenmenü enthält unzulässige Preise.')
    if profile_code == 'staff_guest' and priced != set(item_ids):
        raise ComponentConflictError('Cafeteria-Menü hat keine vollständigen Preise.')


def _update_existing_target(connection: Connection, target_id: int,
                            source: Mapping[str, object], actor_id: int) -> int:
    return int(
        connection.execute(
            text(
                '''UPDATE cafeteria.menu_weeks
                   SET workflow_state='draft', title=:title, shared_note=:shared_note,
                       updated_by=:actor_id
                   WHERE id=:week_id RETURNING row_version'''
            ),
            {'week_id': target_id, 'title': source['title'],
             'shared_note': source['shared_note'], 'actor_id': actor_id},
        ).scalar_one()
    )


def _clone_tree(
    connection: Connection,
    scope: AdminScope,
    source_id: int,
    target_id: int,
) -> None:
    params = {
        'source_id': source_id,
        'target_id': target_id,
        'location_id': scope.location_id,
        'profile_code': scope.profile_code,
        'external_prefix': 'PATIENT' if scope.profile_code == 'patient' else 'STAFF-GUEST',
    }
    connection.execute(text(
        '''
        INSERT INTO cafeteria.menu_services(
            menu_week_id, service_date, meal_period_id, service_state, notice
        )
        SELECT :target_id, s.service_date + 7, s.meal_period_id, s.service_state, s.notice
        FROM cafeteria.menu_services s WHERE s.menu_week_id=:source_id
        ORDER BY s.service_date, s.meal_period_id, s.id
        '''
    ), params)
    connection.execute(text(
        '''
        INSERT INTO cafeteria.menu_items(
            service_id, menu_type_id, dish_template_id, external_id, title, description,
            note, allergen_review_status, sort_order, allergen_mode, origin_mode, label_mode
        )
        SELECT target_service.id, source_item.menu_type_id, source_item.dish_template_id,
               :external_prefix || '-' || to_char(target_service.service_date, 'YYYY-MM-DD')
               || '-' || meal.code || '-' || CASE kind.code WHEN 'MENU_1' THEN '1' ELSE '2' END,
               source_item.title, source_item.description, source_item.note, 'not_checked',
               source_item.sort_order, source_item.allergen_mode, source_item.origin_mode,
               source_item.label_mode
        FROM cafeteria.menu_items source_item
        JOIN cafeteria.menu_services source_service ON source_service.id=source_item.service_id
        JOIN cafeteria.menu_services target_service
          ON target_service.menu_week_id=:target_id
         AND target_service.service_date=source_service.service_date + 7
         AND target_service.meal_period_id=source_service.meal_period_id
        JOIN cafeteria.meal_periods meal ON meal.id=source_service.meal_period_id
        JOIN cafeteria.menu_types kind ON kind.id=source_item.menu_type_id
        WHERE source_service.menu_week_id=:source_id ORDER BY source_item.id
        '''
    ), params)
    connection.execute(text(
        '''
        INSERT INTO cafeteria.menu_item_components(
            menu_item_id, sort_order, component_text, component_id, component_row_version
        )
        SELECT target_item.id, link.sort_order,
               CASE WHEN link.component_id IS NULL THEN link.component_text ELSE current.name END,
               current.id, current.row_version
        FROM cafeteria.menu_item_components link
        JOIN cafeteria.menu_items source_item ON source_item.id=link.menu_item_id
        JOIN cafeteria.menu_services source_service ON source_service.id=source_item.service_id
        JOIN cafeteria.menu_services target_service
          ON target_service.menu_week_id=:target_id
         AND target_service.service_date=source_service.service_date + 7
         AND target_service.meal_period_id=source_service.meal_period_id
        JOIN cafeteria.menu_items target_item
          ON target_item.service_id=target_service.id
         AND target_item.menu_type_id=source_item.menu_type_id
        LEFT JOIN cafeteria.menu_components previous ON previous.id=link.component_id
        LEFT JOIN cafeteria.menu_components current
          ON current.public_id=previous.public_id AND current.location_id=:location_id
         AND current.profile_scope IN ('common', :profile_code)
        WHERE source_service.menu_week_id=:source_id
        ORDER BY source_item.id, link.sort_order
        '''
    ), params)
    _clone_manual_rows(connection, params)
    target_items = connection.execute(text(
        '''SELECT i.id, i.allergen_mode, i.origin_mode, i.label_mode
           FROM cafeteria.menu_items i JOIN cafeteria.menu_services s ON s.id=i.service_id
           WHERE s.menu_week_id=:target_id ORDER BY i.id'''
    ), params).mappings()
    for item in target_items:
        if 'auto' in (item['allergen_mode'], item['origin_mode'], item['label_mode']):
            rematerialize_auto_effects(connection, int(item['id']), item)


def _clone_manual_rows(connection: Connection, params: dict[str, object]) -> None:
    statements = (
        '''INSERT INTO cafeteria.menu_item_labels(menu_item_id, label_id)
           SELECT ti.id, value.label_id FROM cafeteria.menu_item_labels value
           JOIN cafeteria.menu_items si ON si.id=value.menu_item_id
           JOIN cafeteria.menu_services ss ON ss.id=si.service_id
           JOIN cafeteria.menu_services ts ON ts.menu_week_id=:target_id
             AND ts.service_date=ss.service_date + 7 AND ts.meal_period_id=ss.meal_period_id
           JOIN cafeteria.menu_items ti ON ti.service_id=ts.id AND ti.menu_type_id=si.menu_type_id
           WHERE ss.menu_week_id=:source_id AND si.label_mode='manual' ''',
        '''INSERT INTO cafeteria.menu_item_allergens(menu_item_id, allergen_id, presence)
           SELECT ti.id, value.allergen_id, value.presence FROM cafeteria.menu_item_allergens value
           JOIN cafeteria.menu_items si ON si.id=value.menu_item_id
           JOIN cafeteria.menu_services ss ON ss.id=si.service_id
           JOIN cafeteria.menu_services ts ON ts.menu_week_id=:target_id
             AND ts.service_date=ss.service_date + 7 AND ts.meal_period_id=ss.meal_period_id
           JOIN cafeteria.menu_items ti ON ti.service_id=ts.id AND ti.menu_type_id=si.menu_type_id
           WHERE ss.menu_week_id=:source_id AND si.allergen_mode='manual' ''',
        '''INSERT INTO cafeteria.origin_declarations(
               menu_item_id, ingredient, country_code, declaration_text)
           SELECT ti.id, value.ingredient, value.country_code, value.declaration_text
           FROM cafeteria.origin_declarations value
           JOIN cafeteria.menu_items si ON si.id=value.menu_item_id
           JOIN cafeteria.menu_services ss ON ss.id=si.service_id
           JOIN cafeteria.menu_services ts ON ts.menu_week_id=:target_id
             AND ts.service_date=ss.service_date + 7 AND ts.meal_period_id=ss.meal_period_id
           JOIN cafeteria.menu_items ti ON ti.service_id=ts.id AND ti.menu_type_id=si.menu_type_id
           WHERE ss.menu_week_id=:source_id AND si.origin_mode='manual' ''',
        '''INSERT INTO cafeteria.menu_item_prices(
               menu_item_id, internal_rappen, external_rappen, currency)
           SELECT ti.id, value.internal_rappen, value.external_rappen, value.currency
           FROM cafeteria.menu_item_prices value
           JOIN cafeteria.menu_items si ON si.id=value.menu_item_id
           JOIN cafeteria.menu_services ss ON ss.id=si.service_id
           JOIN cafeteria.menu_services ts ON ts.menu_week_id=:target_id
             AND ts.service_date=ss.service_date + 7 AND ts.meal_period_id=ss.meal_period_id
           JOIN cafeteria.menu_items ti ON ti.service_id=ts.id AND ti.menu_type_id=si.menu_type_id
           WHERE ss.menu_week_id=:source_id''',
    )
    for statement in statements:
        connection.execute(text(statement), params)
