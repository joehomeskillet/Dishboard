"""Menu provenance and the original, transient source/target expectations."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from time import time
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text

from .component_catalog_store import (
    AdminScope, ComponentCatalogValidationError, ComponentNotFoundError,
)
from .workflow_write_context import WriteConflictError


class TemplateBindingValidationError(ComponentCatalogValidationError):
    field_name = 'dish_template_public_id'


@dataclass(frozen=True)
class TemplateContext:
    actor_id: int
    authz_version: int
    location_id: int
    template_public_id: str
    expected_updated_at: str
    recipe_public_id: str | None
    expires_at: int
    profile: str | None = None
    week: str | None = None
    day: str | None = None
    meal: str | None = None
    option: str | None = None
    expected_item_row_version: int | None = None
    recipe_active: bool | None = None

    def require_source(self, scope: AdminScope) -> None:
        if (self.actor_id, self.authz_version, self.location_id) != (
                scope.actor_id, scope.expected_authz_version, scope.location_id):
            raise WriteConflictError('Berechtigung oder aktiver Standort wurde zwischenzeitlich geändert.')
        if self.expires_at <= time():
            raise WriteConflictError('Der Vorschlag ist abgelaufen. Bitte erneut einplanen.')
        if self.recipe_public_id and type(self.recipe_active) is not bool:
            raise WriteConflictError('Der Vorschlag ist veraltet. Bitte erneut einplanen.')

    def require_target(self, scope: AdminScope, week: date, day: str, meal: str,
                       option: str, expected: int) -> None:
        self.require_source(scope)
        if (self.profile, self.week, self.day, self.meal, self.option,
                self.expected_item_row_version) != (
                scope.profile_code, week.isoformat(), day, meal, option, expected) or expected != 0:
            raise WriteConflictError('Das Ziel des Vorschlags wurde geändert. Bitte erneut einplanen.')


def template_public_id(value: object) -> str | None:
    if value in (None, ''):
        return None
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError) as error:
        raise TemplateBindingValidationError('Gerichtvorlage muss eine gültige UUID sein.') from error
    return value


def validate_template_fields(payload: Mapping[str, Any]) -> None:
    if 'dish_template_public_id' in payload:
        template_public_id(payload['dish_template_public_id'])
    if 'dish_template_detach' in payload and payload['dish_template_detach'] != '1':
        raise TemplateBindingValidationError('Vorlagenbezug lösen ausdrücklich bestätigen.')


def lock_templates(connection: Connection, scope: AdminScope,
                   public_ids: Sequence[str] = (), ids: Sequence[int] = (),
                   ) -> dict[int, dict[str, Any]]:
    """After recipe-head locks, before aggregate locks; never discover a new lock later."""
    rows = connection.execute(text('''
        SELECT d.id,d.public_id::text,d.title,d.description,d.active,d.profile_scope,d.updated_at,
               r.public_id::text AS recipe_public_id,r.location_id AS recipe_location_id,
               r.active AS recipe_active
        FROM cafeteria.dish_templates d LEFT JOIN cafeteria.recipes r ON r.id=d.recipe_id
        WHERE d.id=ANY(CAST(:ids AS bigint[]))
           OR d.public_id=ANY(CAST(:public_ids AS uuid[]))
        ORDER BY d.id FOR SHARE OF d
    '''), {'ids': list(ids), 'public_ids': list(public_ids)}).mappings()
    result = {int(row['id']): dict(row) for row in rows}
    # Templates are global; an associated recipe supplies their location boundary.
    if any(row['recipe_location_id'] not in (None, scope.location_id) for row in result.values()):
        raise ComponentNotFoundError('Gerichtvorlage nicht gefunden.')
    if not set(public_ids) <= {row['public_id'] for row in result.values()}:
        raise ComponentNotFoundError('Gerichtvorlage nicht gefunden.')
    return result


def resolve_template_binding(scope: AdminScope, payload: Mapping[str, Any],
                             current: Mapping[str, Any] | None,
                             templates: Mapping[int, Mapping[str, Any]],
                             context: TemplateContext | None = None) -> int | None:
    validate_template_fields(payload)
    old = current.get('dish_template_id') if current else None
    public_id = template_public_id(payload.get('dish_template_public_id'))
    if context is not None and (
            context.template_public_id != public_id or payload.get('dish_template_detach')):
        raise WriteConflictError('Die Vorlage des Vorschlags wurde geändert. Bitte erneut einplanen.')
    if payload.get('dish_template_detach') == '1':
        return None
    if public_id is None:
        return int(old) if old is not None else None
    row = next((row for row in templates.values() if row['public_id'] == public_id), None)
    if row is None:
        raise WriteConflictError('Der Vorlagenbezug wurde zwischenzeitlich geändert.')
    if context is not None:
        require_template_source(row, scope, context)
    if row['id'] != old:
        if not row['active']:
            raise TemplateBindingValidationError('Diese Gerichtvorlage ist archiviert.')
        if row['profile_scope'] not in ('common', scope.profile_code):
            raise TemplateBindingValidationError('Diese Gerichtvorlage passt nicht zum Bereich.')
    return int(row['id'])


def require_template_source(row: Mapping[str, Any], scope: AdminScope,
                            context: TemplateContext) -> None:
    context.require_source(scope)
    if (row['public_id'] != context.template_public_id
            or row['updated_at'].isoformat() != context.expected_updated_at
            or row['recipe_public_id'] != context.recipe_public_id
            or row['recipe_active'] != context.recipe_active
            or not row['active'] or row['profile_scope'] not in ('common', scope.profile_code)):
        raise WriteConflictError('Die Gerichtvorlage wurde geändert oder archiviert. Bitte erneut einplanen.')


def require_empty_template_target(connection: Connection, scope: AdminScope,
                                  context: TemplateContext) -> None:
    """Read-only early check; the final writer repeats CAS under its aggregate locks."""
    context.require_target(scope, date.fromisoformat(context.week or ''), context.day or '',
                           context.meal or '', context.option or '', 0)
    occupied = connection.execute(text('''
        SELECT EXISTS(SELECT 1 FROM cafeteria.menu_items i
        JOIN cafeteria.menu_services s ON s.id=i.service_id
        JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
        JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
        JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
        JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
        WHERE w.location_id=:location AND p.code=:profile AND w.week_start=:week
          AND s.service_date=:day AND mp.code=:meal AND mt.code=:option)
    '''), {'location': scope.location_id, 'profile': context.profile, 'week': context.week,
           'day': context.day, 'meal': context.meal, 'option': context.option}).scalar_one()
    if occupied:
        raise WriteConflictError('Dieses Menü wurde bereits gespeichert. Bestehendes Menü ausdrücklich öffnen.')
