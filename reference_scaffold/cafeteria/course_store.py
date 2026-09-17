"""Shared soup/dessert per service, with optional per-menu exceptions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from .component_catalog_store import AdminScope
from .workflow_partial_store import (
    PartialWorkflowNotFoundError,
    PartialWorkflowValidationError,
    resolve_week_ref,
)
from .workflow_write_context import write_transaction

COURSE_KINDS = ('soup', 'dessert')
COURSE_LABELS = {'soup': 'Suppe', 'dessert': 'Dessert'}
_UNPLANNED = {
    'state': 'unplanned',
    'title': None,
    'recipe_public_id': None,
    'recipe_revision_public_id': None,
}


def unplanned() -> dict[str, Any]:
    return dict(_UNPLANNED)


def effective_course(shared: Mapping[str, Any] | None, exception: Mapping[str, Any] | None) -> dict[str, Any]:
    """Variant exception replaces shared; not-offered never falls back to shared."""
    if exception is not None:
        return dict(exception)
    if shared is not None:
        return dict(shared)
    return unplanned()


def snapshot_course(view: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Public/signage projection: omit unplanned; never invent a positive label."""
    if view is None or view.get('state') in (None, 'unplanned'):
        return None
    state = str(view['state'])
    if state == 'not_offered':
        return {'state': 'not_offered', 'title': ''}
    title = str(view.get('title') or '').strip()
    if state != 'planned' or not title:
        return None
    payload = {'state': 'planned', 'title': title}
    recipe = view.get('recipe_public_id')
    if recipe:
        payload['recipe_public_id'] = str(recipe)
    return payload


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as error:
        raise PartialWorkflowValidationError(f'Ungültige {field}.') from error


def _latest_revision(connection: Connection, location_id: int, recipe_public_id: str) -> Mapping[str, Any]:
    row = connection.execute(text('''
        SELECT rr.id, rr.public_id, r.public_id AS recipe_public_id,
               COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
        FROM cafeteria.recipes r
        JOIN cafeteria.recipe_revisions rr ON rr.recipe_id=r.id
        WHERE r.location_id=:location AND r.public_id=CAST(:recipe AS uuid)
        ORDER BY rr.revision_number DESC LIMIT 1
    '''), {'location': location_id, 'recipe': _uuid(recipe_public_id, 'Rezeptangabe')}).mappings().one_or_none()
    if row is None:
        raise PartialWorkflowValidationError('Rezeptrevision nicht gefunden.')
    return row


def _row_view(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return unplanned()
    return {
        'state': row['planning_state'],
        'title': row['title'],
        'recipe_public_id': str(row['recipe_public_id']) if row['recipe_public_id'] else None,
        'recipe_revision_public_id': str(row['revision_public_id']) if row['revision_public_id'] else None,
    }


def load_service_courses(connection: Connection, service_id: int) -> dict[str, dict[str, Any]]:
    rows = connection.execute(text('''
        SELECT c.course_kind, c.planning_state, rr.public_id AS revision_public_id,
               r.public_id AS recipe_public_id,
               COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
        FROM cafeteria.menu_service_courses c
        LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
        LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
        WHERE c.service_id=:service
    '''), {'service': service_id}).mappings().all()
    by_kind = {row['course_kind']: _row_view(row) for row in rows}
    return {kind: by_kind.get(kind, unplanned()) for kind in COURSE_KINDS}


def load_item_exceptions(connection: Connection, item_ids: Sequence[int]) -> dict[int, dict[str, dict[str, Any]]]:
    if not item_ids:
        return {}
    rows = connection.execute(text('''
        SELECT e.menu_item_id, e.course_kind, e.planning_state, rr.public_id AS revision_public_id,
               r.public_id AS recipe_public_id,
               COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
        FROM cafeteria.menu_item_course_exceptions e
        LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=e.recipe_revision_id
        LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
        WHERE e.menu_item_id=ANY(CAST(:ids AS bigint[]))
    '''), {'ids': list(item_ids)}).mappings().all()
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(int(row['menu_item_id']), {})[str(row['course_kind'])] = _row_view(row)
    return result


def load_week_courses(
    engine: Engine, location_id: int, week_start: date, profile_code: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Map (day-iso, meal) → shared courses plus exceptions keyed by menu type."""
    with engine.connect() as connection:
        return load_week_courses_connection(connection, location_id, week_start, profile_code)


def load_week_courses_connection(
    connection: Connection, location_id: int, week_start: date, profile_code: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    services = connection.execute(text('''
        SELECT s.id AS service_id, s.service_date, mp.code AS meal_code
        FROM cafeteria.menu_services s
        JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
        JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
        JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
        WHERE w.location_id=:location AND w.week_start=:week AND p.code=:profile
    '''), {'location': location_id, 'week': week_start, 'profile': profile_code}).mappings().all()
    packed: dict[tuple[str, str], dict[str, Any]] = {}
    ids = [int(row['service_id']) for row in services]
    by_service_shared: dict[int, dict[str, dict[str, Any]]] = {}
    by_service_exc: dict[int, dict[str, dict[str, dict[str, Any]]]] = {}
    if ids:
        for row in connection.execute(text('''
            SELECT c.service_id, c.course_kind, c.planning_state, rr.public_id AS revision_public_id,
                   r.public_id AS recipe_public_id,
                   COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
            FROM cafeteria.menu_service_courses c
            LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
            LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
            WHERE c.service_id=ANY(CAST(:ids AS bigint[]))
        '''), {'ids': ids}).mappings():
            by_service_shared.setdefault(int(row['service_id']), {})[str(row['course_kind'])] = _row_view(row)
        for row in connection.execute(text('''
            SELECT i.service_id, mt.code AS option_code, e.course_kind, e.planning_state,
                   rr.public_id AS revision_public_id, r.public_id AS recipe_public_id,
                   COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
            FROM cafeteria.menu_item_course_exceptions e
            JOIN cafeteria.menu_items i ON i.id=e.menu_item_id
            JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
            LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=e.recipe_revision_id
            LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
            WHERE i.service_id=ANY(CAST(:ids AS bigint[]))
        '''), {'ids': ids}).mappings():
            by_service_exc.setdefault(int(row['service_id']), {}).setdefault(str(row['option_code']), {})[
                str(row['course_kind'])
            ] = _row_view(row)
    for service in services:
        sid = int(service['service_id'])
        shared_rows = by_service_shared.get(sid, {})
        packed[(service['service_date'].isoformat(), str(service['meal_code']))] = {
            'shared': {kind: shared_rows.get(kind, unplanned()) for kind in COURSE_KINDS},
            'exceptions': by_service_exc.get(sid, {}),
        }
    return packed


def attach_courses_to_draft(
    connection: Connection, location_id: int, week_start: date, profile_code: str, draft: dict[str, Any],
) -> None:
    """Annotate a loaded draft in place. Persist paths ignore the extra keys."""
    packed = load_week_courses_connection(connection, location_id, week_start, profile_code)
    for day in draft.get('days') or ():
        for service in day.get('services') or ():
            key = (str(day['date']), str(service['meal_code']))
            block = packed.get(key, {'shared': {kind: unplanned() for kind in COURSE_KINDS}, 'exceptions': {}})
            shared = block['shared']
            service['shared_courses'] = shared
            soup = snapshot_course(shared['soup'])
            dessert = snapshot_course(shared['dessert'])
            if soup is not None:
                service['soup'] = soup
            if dessert is not None:
                service['dessert'] = dessert
            exceptions = block['exceptions']
            for option in service.get('options') or ():
                option_exc = exceptions.get(str(option.get('type_code') or ''), {})
                for kind in COURSE_KINDS:
                    override = snapshot_course(option_exc.get(kind))
                    if override is not None:
                        option[f'{kind}_override'] = override


def _resolve_revision(
    connection: Connection, location_id: int, payload: Mapping[str, Any], *, field: str,
) -> int:
    recipe = payload.get('recipe_public_id') or payload.get('recipe_revision_public_id')
    if not recipe:
        raise PartialWorkflowValidationError(f'{field} braucht ein Rezept.')
    if payload.get('recipe_revision_public_id') and not payload.get('recipe_public_id'):
        row = connection.execute(text('''
            SELECT rr.id FROM cafeteria.recipe_revisions rr
            JOIN cafeteria.recipes r ON r.id=rr.recipe_id
            WHERE rr.public_id=CAST(:id AS uuid) AND r.location_id=:location
        '''), {'id': _uuid(str(recipe), 'Rezeptrevision'), 'location': location_id}).scalar_one_or_none()
        if row is None:
            raise PartialWorkflowValidationError('Rezeptrevision nicht gefunden.')
        return int(row)
    return int(_latest_revision(connection, location_id, str(recipe))['id'])


def _upsert_shared(
    connection: Connection, *, location_id: int, service_id: int, actor_id: int,
    kind: str, payload: Mapping[str, Any],
) -> None:
    state = str(payload.get('state') or 'unplanned')
    if state not in ('unplanned', 'planned', 'not_offered'):
        raise PartialWorkflowValidationError('Ungültiger Gangstatus.')
    if kind not in COURSE_KINDS:
        raise PartialWorkflowValidationError('Ungültiger Gang.')
    if state == 'unplanned':
        connection.execute(text(
            'DELETE FROM cafeteria.menu_service_courses WHERE service_id=:service AND course_kind=:kind'
        ), {'service': service_id, 'kind': kind})
        return
    revision_id = None
    if state == 'planned':
        revision_id = _resolve_revision(connection, location_id, payload, field=COURSE_LABELS[kind])
    connection.execute(text('''
        INSERT INTO cafeteria.menu_service_courses(
            location_id, service_id, course_kind, planning_state, recipe_revision_id, created_by, updated_by)
        VALUES (:location, :service, :kind, :state, :revision, :actor, :actor)
        ON CONFLICT (service_id, course_kind) DO UPDATE
        SET planning_state=EXCLUDED.planning_state, recipe_revision_id=EXCLUDED.recipe_revision_id,
            updated_by=EXCLUDED.updated_by, updated_at=clock_timestamp(),
            row_version=cafeteria.menu_service_courses.row_version + 1
    '''), {
        'location': location_id, 'service': service_id, 'kind': kind, 'state': state,
        'revision': revision_id, 'actor': actor_id,
    })


def persist_service_courses(
    engine: Engine, scope: AdminScope, week_start: date, day: str, meal: str, *,
    soup: Mapping[str, Any], dessert: Mapping[str, Any],
    exceptions: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Atomically write shared soup+dessert and named menu exceptions for one service."""
    if meal not in ('LUNCH', 'DINNER'):
        raise PartialWorkflowValidationError('Ungültige Mahlzeit.')
    service_date = date.fromisoformat(day)
    with write_transaction(engine, scope) as connection:
        week = resolve_week_ref(connection, scope, week_start, for_update=True)
        service = connection.execute(text('''
            SELECT s.id FROM cafeteria.menu_services s
            JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
            WHERE s.menu_week_id=:week AND s.service_date=:day AND mp.code=:meal
            FOR UPDATE OF s
        '''), {'week': week.week_id, 'day': service_date, 'meal': meal}).scalar_one_or_none()
        if service is None:
            raise PartialWorkflowNotFoundError('Ausgabe nicht gefunden. Zuerst Ausgabeangaben oder ein Menü speichern.')
        service_id = int(service)
        _upsert_shared(connection, location_id=scope.location_id, service_id=service_id,
                       actor_id=scope.actor_id, kind='soup', payload=soup)
        _upsert_shared(connection, location_id=scope.location_id, service_id=service_id,
                       actor_id=scope.actor_id, kind='dessert', payload=dessert)
        if exceptions is None:
            return
        connection.execute(text('''
            DELETE FROM cafeteria.menu_item_course_exceptions e
            USING cafeteria.menu_items i
            WHERE e.menu_item_id=i.id AND i.service_id=:service
        '''), {'service': service_id})
        for item in exceptions:
            option = str(item.get('option') or '')
            kind = str(item.get('kind') or '')
            if kind not in COURSE_KINDS:
                raise PartialWorkflowValidationError('Ungültiger Gang.')
            state = str(item.get('state') or 'inherit')
            if state == 'inherit':
                continue
            menu_item = connection.execute(text('''
                SELECT i.id FROM cafeteria.menu_items i
                JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
                WHERE i.service_id=:service AND mt.code=:option
                FOR UPDATE OF i
            '''), {'service': service_id, 'option': option}).scalar_one_or_none()
            if menu_item is None:
                raise PartialWorkflowNotFoundError('Menüvariante nicht gefunden.')
            revision_id = None
            if state == 'planned':
                revision_id = _resolve_revision(
                    connection, scope.location_id, item, field=COURSE_LABELS[kind],
                )
            elif state != 'not_offered':
                raise PartialWorkflowValidationError('Ungültige Menüabweichung.')
            connection.execute(text('''
                INSERT INTO cafeteria.menu_item_course_exceptions(
                    menu_item_id, course_kind, planning_state, recipe_revision_id, created_by, updated_by)
                VALUES (:item, :kind, :state, :revision, :actor, :actor)
            '''), {
                'item': int(menu_item), 'kind': kind, 'state': state,
                'revision': revision_id, 'actor': scope.actor_id,
            })


def capture_week_courses(connection: Connection, week_id: int) -> dict[str, Any]:
    """Preserve shared courses and exceptions across a full CSV replace of schema 2/3."""
    shared = [dict(row) for row in connection.execute(text('''
        SELECT s.service_date::text AS day, mp.code AS meal, c.course_kind, c.planning_state,
               r.public_id::text AS recipe_public_id
        FROM cafeteria.menu_service_courses c
        JOIN cafeteria.menu_services s ON s.id=c.service_id
        JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
        LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
        LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
        WHERE s.menu_week_id=:week
    '''), {'week': week_id}).mappings()]
    exceptions = [dict(row) for row in connection.execute(text('''
        SELECT s.service_date::text AS day, mp.code AS meal, mt.code AS option, e.course_kind,
               e.planning_state, r.public_id::text AS recipe_public_id
        FROM cafeteria.menu_item_course_exceptions e
        JOIN cafeteria.menu_items i ON i.id=e.menu_item_id
        JOIN cafeteria.menu_services s ON s.id=i.service_id
        JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
        JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
        LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=e.recipe_revision_id
        LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
        WHERE s.menu_week_id=:week
    '''), {'week': week_id}).mappings()]
    return {'shared': shared, 'exceptions': exceptions}


def restore_week_courses(
    engine: Engine, scope: AdminScope, week_start: date, captured: Mapping[str, Any],
) -> None:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in captured.get('shared') or ():
        key = (str(row['day']), str(row['meal']))
        slot = grouped.setdefault(key, {
            'soup': {'state': 'unplanned'}, 'dessert': {'state': 'unplanned'}, 'exceptions': [],
        })
        payload = {'state': row['planning_state']}
        if row.get('recipe_public_id'):
            payload['recipe_public_id'] = row['recipe_public_id']
        slot[str(row['course_kind'])] = payload
    for row in captured.get('exceptions') or ():
        key = (str(row['day']), str(row['meal']))
        slot = grouped.setdefault(key, {
            'soup': {'state': 'unplanned'}, 'dessert': {'state': 'unplanned'}, 'exceptions': [],
        })
        item = {
            'option': row['option'], 'kind': row['course_kind'], 'state': row['planning_state'],
        }
        if row.get('recipe_public_id'):
            item['recipe_public_id'] = row['recipe_public_id']
        slot['exceptions'].append(item)
    for (day, meal), slot in grouped.items():
        persist_service_courses(
            engine, scope, week_start, day, meal,
            soup=slot['soup'], dessert=slot['dessert'], exceptions=slot['exceptions'],
        )


def clone_week_courses(
    connection: Connection, *, source_week_id: int, target_week_id: int,
    location_id: int, actor_id: int,
) -> None:
    connection.execute(text('''
        INSERT INTO cafeteria.menu_service_courses(
            location_id, service_id, course_kind, planning_state, recipe_revision_id,
            created_by, updated_by)
        SELECT :location_id, ts.id, c.course_kind, c.planning_state, c.recipe_revision_id,
               :actor_id, :actor_id
        FROM cafeteria.menu_service_courses c
        JOIN cafeteria.menu_services ss ON ss.id=c.service_id
        JOIN cafeteria.menu_services ts
          ON ts.menu_week_id=:target_id
         AND ts.service_date=ss.service_date + 7
         AND ts.meal_period_id=ss.meal_period_id
        WHERE ss.menu_week_id=:source_id
        ORDER BY ts.id, c.course_kind
    '''), {
        'location_id': location_id, 'actor_id': actor_id,
        'source_id': source_week_id, 'target_id': target_week_id,
    })
    connection.execute(text('''
        INSERT INTO cafeteria.menu_item_course_exceptions(
            menu_item_id, course_kind, planning_state, recipe_revision_id, created_by, updated_by)
        SELECT ti.id, e.course_kind, e.planning_state, e.recipe_revision_id, :actor_id, :actor_id
        FROM cafeteria.menu_item_course_exceptions e
        JOIN cafeteria.menu_items si ON si.id=e.menu_item_id
        JOIN cafeteria.menu_services ss ON ss.id=si.service_id
        JOIN cafeteria.menu_services ts
          ON ts.menu_week_id=:target_id
         AND ts.service_date=ss.service_date + 7
         AND ts.meal_period_id=ss.meal_period_id
        JOIN cafeteria.menu_items ti
          ON ti.service_id=ts.id AND ti.menu_type_id=si.menu_type_id
        WHERE ss.menu_week_id=:source_id
        ORDER BY ti.id, e.course_kind
    '''), {
        'actor_id': actor_id, 'source_id': source_week_id, 'target_id': target_week_id,
    })


def parse_course_form(form: Mapping[str, Any]) -> dict[str, Any]:
    def _state(name: str) -> str:
        value = str(form.get(name) or 'unplanned').strip()
        if value not in ('unplanned', 'planned', 'not_offered', 'inherit'):
            raise PartialWorkflowValidationError('Ungültiger Gangstatus.')
        return value

    def _payload(prefix: str) -> dict[str, Any]:
        state = _state(f'{prefix}_state')
        if state == 'inherit':
            raise PartialWorkflowValidationError('Ungültiger Gangstatus.')
        payload: dict[str, Any] = {'state': state}
        recipe = str(form.get(f'{prefix}_recipe') or '').strip()
        if state == 'planned':
            payload['recipe_public_id'] = recipe
        return payload

    exceptions = []
    for option in ('MENU_1', 'VEGGIE'):
        for kind in COURSE_KINDS:
            prefix = f'{option}_{kind}'
            if f'{prefix}_state' not in form:
                continue
            state = _state(f'{prefix}_state')
            item: dict[str, Any] = {'option': option, 'kind': kind, 'state': state}
            recipe = str(form.get(f'{prefix}_recipe') or '').strip()
            if state == 'planned':
                item['recipe_public_id'] = recipe
            exceptions.append(item)
    return {
        'soup': _payload('soup'),
        'dessert': _payload('dessert'),
        'exceptions': exceptions,
    }
