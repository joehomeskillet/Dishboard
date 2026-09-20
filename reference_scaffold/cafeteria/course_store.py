"""Shared soup/dessert per service, with optional per-menu exceptions."""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.engine import RowMapping

from .component_catalog_store import AdminScope
from .workflow_partial_store import (
    PartialWorkflowConflictError,
    PartialWorkflowNotFoundError,
    PartialWorkflowValidationError,
    resolve_week_ref,
)
from .workflow_write_context import write_transaction

_logger = logging.getLogger(__name__)

COURSE_KINDS = ('soup', 'dessert')
COURSE_LABELS = {'soup': 'Suppe', 'dessert': 'Dessert'}
_UNPLANNED = {
    'state': 'unplanned',
    'public_id': None,
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


def snapshot_course(view: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Public/signage projection: omit unplanned; never invent a positive label."""
    if view is None or view.get('state') in (None, 'unplanned'):
        return None
    state = str(view['state'])
    if state == 'not_offered':
        return {'state': 'not_offered', 'title': ''}
    title = str(view.get('title') or '').strip()
    if state != 'planned' or not title:
        return None
    payload: dict[str, Any] = {'state': 'planned', 'title': title}
    recipe = view.get('recipe_public_id')
    if recipe:
        payload['recipe_public_id'] = str(recipe)
    for field in ('allergens', 'labels', 'nutrition'):
        val = view.get(field)
        if val:
            payload[field] = val
    return payload


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as error:
        raise PartialWorkflowValidationError(f'Ungültige {field}.') from error


def _latest_revision(
    connection: Connection,
    location_id: int,
    recipe_public_id: str,
    *,
    retained_revision_id: int | None = None,
) -> Mapping[str, Any]:
    row = connection.execute(text('''
        SELECT rr.id, rr.public_id, r.public_id AS recipe_public_id,
               COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
        FROM cafeteria.recipes r
        JOIN cafeteria.recipe_revisions rr ON rr.recipe_id=r.id
        WHERE r.location_id=:location AND r.public_id=CAST(:recipe AS uuid)
          AND (r.active OR EXISTS (
              SELECT 1 FROM cafeteria.recipe_revisions retained
              WHERE retained.id=:retained_revision AND retained.recipe_id=r.id
          ))
        ORDER BY rr.revision_number DESC LIMIT 1
    '''), {
        'location': location_id,
        'recipe': _uuid(recipe_public_id, 'Rezeptangabe'),
        'retained_revision': retained_revision_id,
    }).mappings().one_or_none()
    if row is None:
        raise PartialWorkflowValidationError(
            'Rezeptangabe ist ungültig oder nicht zugänglich.'
        )
    return row


def _flags_from_snapshot(
    snapshot: object, row: Mapping[str, Any] | RowMapping | None = None,
) -> dict[str, Any]:
    if isinstance(snapshot, (bytes, bytearray, str)):
        try:
            snapshot = json.loads(snapshot)
        except (TypeError, ValueError, json.JSONDecodeError):
            if row:
                identifier = row.get('recipe_public_id') or row.get('revision_public_id') or 'unbekannt'
                _logger.warning(
                    'Defektes Snapshot-JSON für Rezept/Revision %s', identifier,
                )
            snapshot = None
    recipe = snapshot.get('recipe') if isinstance(snapshot, dict) else None
    if not isinstance(recipe, dict):
        recipe = snapshot if isinstance(snapshot, dict) else {}
    allergens = recipe.get('allergens')
    labels = recipe.get('labels')
    nutrition = recipe.get('nutrition')
    return {
        'allergens': allergens if isinstance(allergens, list) else None,
        'labels': labels if isinstance(labels, list) else None,
        'nutrition': nutrition if isinstance(nutrition, dict) else None,
    }


def _row_view(row: Mapping[str, Any] | RowMapping | None) -> dict[str, Any]:
    if row is None:
        return unplanned()
    flags = _flags_from_snapshot(row.get('snapshot_json'), row)
    view = {
        'state': row['planning_state'],
        'public_id': str(row['public_id']) if row.get('public_id') else None,
        'title': row['title'],
        'recipe_public_id': str(row['recipe_public_id']) if row['recipe_public_id'] else None,
        'recipe_revision_public_id': str(row['revision_public_id']) if row['revision_public_id'] else None,
        'allergens': flags['allergens'],
        'labels': flags['labels'],
        'nutrition': flags['nutrition'],
        'allergen_review_status': 'not_checked',
    }
    if row.get('row_version') is not None:
        view['row_version'] = int(row['row_version'])
    return view


def course_issue_flags(view: Mapping[str, Any] | None) -> dict[str, Any]:
    """Open items for one assignment. Missing data is never a positive label."""
    course = dict(view or unplanned())
    if course.get('state') != 'planned':
        return {
            'missing_allergens': False,
            'missing_nutrition': False,
            'positive_labels': (),
            'allergen_review_status': course.get('allergen_review_status') or 'not_checked',
        }
    allergens = course.get('allergens')
    nutrition = course.get('nutrition')
    labels = course.get('labels')
    return {
        'missing_allergens': not isinstance(allergens, list) or len(allergens) == 0,
        'missing_nutrition': not isinstance(nutrition, dict) or len(nutrition) == 0,
        'positive_labels': tuple(labels) if isinstance(labels, list) else (),
        'allergen_review_status': 'not_checked',
    }


def summarize_course_issues(
    packed: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Count shared soup/dessert once per assignment, not once per menu variant."""
    missing_allergens = 0
    missing_nutrition = 0
    affected = 0
    items: list[dict[str, Any]] = []
    for (day, meal), block in packed.items():
        shared = block.get('shared') or {}
        exceptions = block.get('exceptions') or {}
        for kind in COURSE_KINDS:
            course = shared.get(kind) or unplanned()
            flags = course_issue_flags(course)
            problems = [name for name in ('missing_allergens', 'missing_nutrition') if flags[name]]
            if problems:
                affected += 1
                if flags['missing_allergens']:
                    missing_allergens += 1
                if flags['missing_nutrition']:
                    missing_nutrition += 1
                items.append({
                    'day': day, 'meal': meal, 'kind': kind, 'scope': 'shared',
                    'option': None, 'title': course.get('title'),
                    'problems': tuple(problems),
                    'positive_labels': flags['positive_labels'],
                    'allergen_review_status': flags['allergen_review_status'],
                })
            for option, option_exc in exceptions.items():
                override = option_exc.get(kind)
                if not override:
                    continue
                flags = course_issue_flags(override)
                problems = [name for name in ('missing_allergens', 'missing_nutrition') if flags[name]]
                if not problems:
                    continue
                affected += 1
                if flags['missing_allergens']:
                    missing_allergens += 1
                if flags['missing_nutrition']:
                    missing_nutrition += 1
                items.append({
                    'day': day, 'meal': meal, 'kind': kind, 'scope': 'exception',
                    'option': option, 'title': override.get('title'),
                    'problems': tuple(problems),
                    'positive_labels': flags['positive_labels'],
                    'allergen_review_status': flags['allergen_review_status'],
                })
    return {
        'affected_assignments': affected,
        'missing_allergens': missing_allergens,
        'missing_nutrition': missing_nutrition,
        'items': items,
    }


def load_service_courses(connection: Connection, service_id: int) -> dict[str, dict[str, Any]]:
    rows = connection.execute(text('''
        SELECT c.course_kind, c.planning_state, c.public_id, c.row_version,
               rr.public_id AS revision_public_id,
               r.public_id AS recipe_public_id, rr.snapshot_json AS snapshot_json,
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
        SELECT e.menu_item_id, e.course_kind, e.planning_state, e.public_id, e.row_version,
               rr.public_id AS revision_public_id, r.public_id AS recipe_public_id,
               rr.snapshot_json AS snapshot_json,
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
            SELECT c.service_id, c.course_kind, c.planning_state, c.public_id, c.row_version,
                   rr.public_id AS revision_public_id, r.public_id AS recipe_public_id,
                   rr.snapshot_json AS snapshot_json,
                   COALESCE(rr.snapshot_json #>> '{recipe,title}', r.title) AS title
            FROM cafeteria.menu_service_courses c
            LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
            LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
            WHERE c.service_id=ANY(CAST(:ids AS bigint[]))
        '''), {'ids': ids}).mappings():
            by_service_shared.setdefault(int(row['service_id']), {})[str(row['course_kind'])] = _row_view(row)
        for row in connection.execute(text('''
            SELECT i.service_id, mt.code AS option_code, e.course_kind, e.planning_state,
                   e.public_id, e.row_version, rr.public_id AS revision_public_id,
                   r.public_id AS recipe_public_id, rr.snapshot_json AS snapshot_json,
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
            exceptions = block['exceptions']
            service['shared_courses'] = shared
            service['course_exceptions'] = exceptions
            soup = snapshot_course(shared['soup'])
            dessert = snapshot_course(shared['dessert'])
            if soup is not None:
                service['soup'] = soup
            if dessert is not None:
                service['dessert'] = dessert
            for option in service.get('options') or ():
                option_exc = exceptions.get(str(option.get('type_code') or ''), {})
                for kind in COURSE_KINDS:
                    override = snapshot_course(option_exc.get(kind))
                    if override is not None:
                        option[f'{kind}_override'] = override


def _course_import_error(payload: Mapping[str, Any], cause: Exception) -> PartialWorkflowValidationError:
    line = payload.get('line')
    if line:
        return PartialWorkflowValidationError(
            f'Zeile {line}: Rezeptangabe ist ungültig oder nicht zugänglich.'
        )
    if isinstance(cause, PartialWorkflowValidationError):
        return cause
    return PartialWorkflowValidationError('Rezeptangabe ist ungültig oder nicht zugänglich.')


def _resolve_revision(
    connection: Connection,
    location_id: int,
    payload: Mapping[str, Any],
    *,
    field: str,
    retained_revision_id: int | None = None,
) -> int:
    try:
        recipe = payload.get('recipe_public_id') or payload.get('recipe_revision_public_id')
        if not recipe:
            raise PartialWorkflowValidationError(f'{field} braucht ein Rezept.')
        if payload.get('recipe_revision_public_id') and not payload.get('recipe_public_id'):
            row = connection.execute(text('''
                SELECT rr.id FROM cafeteria.recipe_revisions rr
                JOIN cafeteria.recipes r ON r.id=rr.recipe_id
                WHERE rr.public_id=CAST(:id AS uuid) AND r.location_id=:location
                  AND (r.active OR EXISTS (
                      SELECT 1 FROM cafeteria.recipe_revisions retained
                      WHERE retained.id=:retained_revision AND retained.recipe_id=r.id
                  ))
            '''), {
                'id': _uuid(str(recipe), 'Rezeptrevision'),
                'location': location_id,
                'retained_revision': retained_revision_id,
            }).scalar_one_or_none()
            if row is None:
                raise PartialWorkflowValidationError(
                    'Rezeptangabe ist ungültig oder nicht zugänglich.'
                )
            return int(row)
        return int(_latest_revision(
            connection,
            location_id,
            str(recipe),
            retained_revision_id=retained_revision_id,
        )['id'])
    except PartialWorkflowValidationError as error:
        wrapped = _course_import_error(payload, error)
        if wrapped is error:
            raise
        raise wrapped from error


def _expected_course_version(value: int, label: str) -> int:
    if type(value) is not int or value < 0:
        raise PartialWorkflowValidationError(f'{label} ist ungültig.')
    return value


def _course_conflict(kind: str) -> PartialWorkflowConflictError:
    return PartialWorkflowConflictError(f'{COURSE_LABELS[kind]} wurde zwischenzeitlich geändert.')


def _check_course_identity(
    existing: Mapping[str, Any] | RowMapping | None,
    expected_version: int,
    expected_public_id: str,
    kind: str,
) -> None:
    if existing is None:
        if expected_version != 0 or expected_public_id:
            raise _course_conflict(kind)
        return
    if (int(existing['row_version']) != expected_version
            or str(existing['public_id']) != expected_public_id):
        raise _course_conflict(kind)


def _upsert_shared(
    connection: Connection, *, location_id: int, service_id: int, actor_id: int,
    kind: str, payload: Mapping[str, Any], expected_row_version: int | None = None,
    retained_revision_id: int | None = None,
) -> None:
    state = str(payload.get('state') or 'unplanned')
    if state not in ('unplanned', 'planned', 'not_offered'):
        raise PartialWorkflowValidationError('Ungültiger Gangstatus.')
    if kind not in COURSE_KINDS:
        raise PartialWorkflowValidationError('Ungültiger Gang.')
    existing = connection.execute(text('''
        SELECT id, public_id, row_version, recipe_revision_id FROM cafeteria.menu_service_courses
        WHERE service_id=:service AND course_kind=:kind FOR UPDATE
    '''), {'service': service_id, 'kind': kind}).mappings().one_or_none()
    if existing is not None and existing['recipe_revision_id'] is not None:
        retained_revision_id = int(existing['recipe_revision_id'])
    if expected_row_version is not None:
        expected = _expected_course_version(expected_row_version, f'{COURSE_LABELS[kind]}-Version')
        expected_public_id = str(payload.get('public_id') or '').strip()
        _check_course_identity(existing, expected, expected_public_id, kind)
        if state == 'unplanned':
            if existing is None:
                return
            connection.execute(text(
                'DELETE FROM cafeteria.menu_service_courses WHERE id=:id'
            ), {'id': int(existing['id'])})
            return
        revision_id = None
        if state == 'planned':
            revision_id = _resolve_revision(
                connection, location_id, payload, field=COURSE_LABELS[kind],
                retained_revision_id=retained_revision_id,
            )
        if existing is None:
            connection.execute(text('''
                INSERT INTO cafeteria.menu_service_courses(
                    location_id, service_id, course_kind, planning_state, recipe_revision_id,
                    created_by, updated_by)
                VALUES (:location, :service, :kind, :state, :revision, :actor, :actor)
            '''), {
                'location': location_id, 'service': service_id, 'kind': kind, 'state': state,
                'revision': revision_id, 'actor': actor_id,
            })
            return
        connection.execute(text('''
            UPDATE cafeteria.menu_service_courses
            SET planning_state=:state, recipe_revision_id=:revision,
                updated_by=:actor, updated_at=clock_timestamp(),
                row_version=row_version + 1
            WHERE id=:id
        '''), {
            'state': state, 'revision': revision_id, 'actor': actor_id, 'id': int(existing['id']),
        })
        return
    if state == 'unplanned':
        connection.execute(text(
            'DELETE FROM cafeteria.menu_service_courses WHERE service_id=:service AND course_kind=:kind'
        ), {'service': service_id, 'kind': kind})
        return
    revision_id = None
    if state == 'planned':
        revision_id = _resolve_revision(
            connection, location_id, payload, field=COURSE_LABELS[kind],
            retained_revision_id=retained_revision_id,
        )
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


def _upsert_exception(
    connection: Connection, *, location_id: int, menu_item_id: int, actor_id: int,
    kind: str, state: str, payload: Mapping[str, Any], expected_row_version: int | None,
    retained_revision_id: int | None = None,
) -> None:
    if kind not in COURSE_KINDS:
        raise PartialWorkflowValidationError('Ungültiger Gang.')
    existing = connection.execute(text('''
        SELECT id, public_id, row_version, recipe_revision_id FROM cafeteria.menu_item_course_exceptions
        WHERE menu_item_id=:item AND course_kind=:kind FOR UPDATE
    '''), {'item': menu_item_id, 'kind': kind}).mappings().one_or_none()
    if existing is not None and existing['recipe_revision_id'] is not None:
        retained_revision_id = int(existing['recipe_revision_id'])
    if state == 'inherit':
        if expected_row_version is not None:
            expected = _expected_course_version(
                expected_row_version, f'{COURSE_LABELS[kind]}-Version',
            )
            expected_public_id = str(payload.get('public_id') or '').strip()
            _check_course_identity(existing, expected, expected_public_id, kind)
            if existing is None:
                return
            connection.execute(text(
                'DELETE FROM cafeteria.menu_item_course_exceptions WHERE id=:id'
            ), {'id': int(existing['id'])})
        elif existing is not None:
            connection.execute(text(
                'DELETE FROM cafeteria.menu_item_course_exceptions WHERE id=:id'
            ), {'id': int(existing['id'])})
        return
    if state not in ('planned', 'not_offered'):
        raise PartialWorkflowValidationError('Ungültige Menüabweichung.')
    if expected_row_version is not None:
        expected = _expected_course_version(
            expected_row_version, f'{COURSE_LABELS[kind]}-Version',
        )
        expected_public_id = str(payload.get('public_id') or '').strip()
        _check_course_identity(existing, expected, expected_public_id, kind)
    revision_id = None
    if state == 'planned':
        revision_id = _resolve_revision(
            connection, location_id, payload, field=COURSE_LABELS[kind],
            retained_revision_id=retained_revision_id,
        )
    if expected_row_version is not None:
        if existing is None:
            connection.execute(text('''
                INSERT INTO cafeteria.menu_item_course_exceptions(
                    menu_item_id, course_kind, planning_state, recipe_revision_id, created_by, updated_by)
                VALUES (:item, :kind, :state, :revision, :actor, :actor)
            '''), {
                'item': menu_item_id, 'kind': kind, 'state': state,
                'revision': revision_id, 'actor': actor_id,
            })
            return
        connection.execute(text('''
            UPDATE cafeteria.menu_item_course_exceptions
            SET planning_state=:state, recipe_revision_id=:revision,
                updated_by=:actor, updated_at=clock_timestamp(),
                row_version=row_version + 1
            WHERE id=:id
        '''), {
            'state': state, 'revision': revision_id, 'actor': actor_id, 'id': int(existing['id']),
        })
        return
    if existing is None:
        connection.execute(text('''
            INSERT INTO cafeteria.menu_item_course_exceptions(
                menu_item_id, course_kind, planning_state, recipe_revision_id, created_by, updated_by)
            VALUES (:item, :kind, :state, :revision, :actor, :actor)
        '''), {
            'item': menu_item_id, 'kind': kind, 'state': state,
            'revision': revision_id, 'actor': actor_id,
        })
    else:
        connection.execute(text('''
            UPDATE cafeteria.menu_item_course_exceptions
            SET planning_state=:state, recipe_revision_id=:revision,
                updated_by=:actor, updated_at=clock_timestamp(),
                row_version=row_version + 1
            WHERE id=:id
        '''), {
            'state': state, 'revision': revision_id, 'actor': actor_id, 'id': int(existing['id']),
        })


def persist_service_courses_connection(
    connection: Connection, scope: AdminScope, week_start: date, day: str, meal: str, *,
    soup: Mapping[str, Any], dessert: Mapping[str, Any],
    exceptions: Sequence[Mapping[str, Any]] | None = None,
    soup_row_version: int | None = None,
    dessert_row_version: int | None = None,
    retained_shared_revisions: Mapping[str, int] | None = None,
    retained_exception_revisions: Mapping[tuple[str, str], int] | None = None,
) -> None:
    """Write shared soup+dessert on an open write connection (no nested transaction)."""
    if meal not in ('LUNCH', 'DINNER'):
        raise PartialWorkflowValidationError('Ungültige Mahlzeit.')
    service_date = date.fromisoformat(day)
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
                   actor_id=scope.actor_id, kind='soup', payload=soup,
                   expected_row_version=soup_row_version,
                   retained_revision_id=(retained_shared_revisions or {}).get('soup'))
    _upsert_shared(connection, location_id=scope.location_id, service_id=service_id,
                   actor_id=scope.actor_id, kind='dessert', payload=dessert,
                   expected_row_version=dessert_row_version,
                   retained_revision_id=(retained_shared_revisions or {}).get('dessert'))
    if exceptions is None:
        return
    for item in exceptions:
        option = str(item.get('option') or '')
        kind = str(item.get('kind') or '')
        if kind not in COURSE_KINDS:
            raise PartialWorkflowValidationError('Ungültiger Gang.')
        state = str(item.get('state') or 'inherit')
        menu_item = connection.execute(text('''
            SELECT i.id FROM cafeteria.menu_items i
            JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
            WHERE i.service_id=:service AND mt.code=:option
            FOR UPDATE OF i
        '''), {'service': service_id, 'option': option}).scalar_one_or_none()
        if menu_item is None:
            if state == 'inherit':
                continue
            raise PartialWorkflowNotFoundError('Menüvariante nicht gefunden.')
        expected_version = item.get('row_version')
        version = (
            _expected_course_version(int(expected_version), f'{COURSE_LABELS[kind]}-Version')
            if expected_version is not None and soup_row_version is not None
            else None
        )
        _upsert_exception(
            connection, location_id=scope.location_id, menu_item_id=int(menu_item),
            actor_id=scope.actor_id, kind=kind, state=state, payload=item,
            expected_row_version=version,
            retained_revision_id=(retained_exception_revisions or {}).get((option, kind)),
        )


def persist_service_courses(
    engine: Engine, scope: AdminScope, week_start: date, day: str, meal: str, *,
    soup: Mapping[str, Any], dessert: Mapping[str, Any],
    exceptions: Sequence[Mapping[str, Any]] | None = None,
    soup_row_version: int | None = None,
    dessert_row_version: int | None = None,
) -> None:
    """Atomically write shared soup+dessert and named menu exceptions for one service."""
    with write_transaction(engine, scope) as connection:
        persist_service_courses_connection(
            connection, scope, week_start, day, meal,
            soup=soup, dessert=dessert, exceptions=exceptions,
            soup_row_version=soup_row_version,
            dessert_row_version=dessert_row_version,
        )


def capture_week_courses(connection: Connection, week_id: int) -> dict[str, Any]:
    """Preserve shared courses and exceptions across a full CSV replace of schema 2/3."""
    shared = [dict(row) for row in connection.execute(text('''
        SELECT s.service_date::text AS day, mp.code AS meal, c.course_kind, c.planning_state,
               c.recipe_revision_id, r.public_id::text AS recipe_public_id
        FROM cafeteria.menu_service_courses c
        JOIN cafeteria.menu_services s ON s.id=c.service_id
        JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
        LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
        LEFT JOIN cafeteria.recipes r ON r.id=rr.recipe_id
        WHERE s.menu_week_id=:week
    '''), {'week': week_id}).mappings()]
    exceptions = [dict(row) for row in connection.execute(text('''
        SELECT s.service_date::text AS day, mp.code AS meal, mt.code AS option, e.course_kind,
               e.planning_state, e.recipe_revision_id, r.public_id::text AS recipe_public_id
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


def restore_week_courses_connection(
    connection: Connection, scope: AdminScope, week_start: date, captured: Mapping[str, Any],
) -> None:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    retained_shared: dict[tuple[str, str], dict[str, int]] = {}
    retained_exceptions: dict[tuple[str, str], dict[tuple[str, str], int]] = {}
    for row in captured.get('shared') or ():
        key = (str(row['day']), str(row['meal']))
        slot = grouped.setdefault(key, {
            'soup': {'state': 'unplanned'}, 'dessert': {'state': 'unplanned'}, 'exceptions': [],
        })
        payload = {'state': row['planning_state']}
        if row.get('recipe_public_id'):
            payload['recipe_public_id'] = row['recipe_public_id']
        if row.get('recipe_revision_id') is not None:
            retained_shared.setdefault(key, {})[str(row['course_kind'])] = int(
                row['recipe_revision_id']
            )
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
        if row.get('recipe_revision_id') is not None:
            retained_exceptions.setdefault(key, {})[
                (str(row['option']), str(row['course_kind']))
            ] = int(row['recipe_revision_id'])
        slot['exceptions'].append(item)
    for (day, meal), slot in grouped.items():
        persist_service_courses_connection(
            connection, scope, week_start, day, meal,
            soup=slot['soup'], dessert=slot['dessert'], exceptions=slot['exceptions'],
            retained_shared_revisions=retained_shared.get((day, meal)),
            retained_exception_revisions=retained_exceptions.get((day, meal)),
        )


def restore_week_courses(
    engine: Engine, scope: AdminScope, week_start: date, captured: Mapping[str, Any],
) -> None:
    with write_transaction(engine, scope) as connection:
        restore_week_courses_connection(connection, scope, week_start, captured)


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

    def _version(name: str) -> int:
        raw = form.get(name)
        if raw is None or str(raw).strip() == '':
            return 0
        try:
            value = int(raw)
        except (TypeError, ValueError) as error:
            raise PartialWorkflowValidationError(f'{name} ist ungültig.') from error
        if value < 0:
            raise PartialWorkflowValidationError(f'{name} ist ungültig.')
        return value

    def _payload(prefix: str) -> dict[str, Any]:
        state = _state(f'{prefix}_state')
        if state == 'inherit':
            raise PartialWorkflowValidationError('Ungültiger Gangstatus.')
        payload: dict[str, Any] = {
            'state': state,
            'public_id': str(form.get(f'{prefix}_public_id') or '').strip(),
        }
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
            item: dict[str, Any] = {
                'option': option, 'kind': kind, 'state': state,
                'public_id': str(form.get(f'{prefix}_public_id') or '').strip(),
                'row_version': _version(f'{prefix}_row_version'),
            }
            recipe = str(form.get(f'{prefix}_recipe') or '').strip()
            if state == 'planned':
                item['recipe_public_id'] = recipe
            exceptions.append(item)
    return {
        'soup': _payload('soup'),
        'dessert': _payload('dessert'),
        'exceptions': exceptions,
        'soup_row_version': _version('soup_row_version'),
        'dessert_row_version': _version('dessert_row_version'),
    }
