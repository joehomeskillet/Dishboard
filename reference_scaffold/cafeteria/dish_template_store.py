"""Dish-template writers call the frozen v26 SQL verbs; CAS is updated_at."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .auth.local_users import ActorExpectation
from .recipe_commands import ERRORS
from .recipe_reads import get_location
from .recipe_types import (
    RecipeConflictError, RecipeNotFoundError, RecipeUnavailableError, RecipeValidationError,
)
from .recipe_values import identifier, positive

P = ParamSpec('P')
T = TypeVar('T')
SQL = {
    'create': (
        'SELECT cafeteria.create_dish_template_v26(:actor,:authz,:location,'
        'CAST(:target AS uuid),CAST(:expected AS timestamptz),CAST(:payload AS jsonb))'
    ),
    'update': (
        'SELECT cafeteria.update_dish_template_v26(:actor,:authz,:location,'
        'CAST(:target AS uuid),CAST(:expected AS timestamptz),CAST(:payload AS jsonb))'
    ),
    'active': (
        'SELECT cafeteria.set_dish_template_active_v26(:actor,:authz,:location,'
        'CAST(:target AS uuid),CAST(:expected AS timestamptz),CAST(:payload AS jsonb))'
    ),
}
LIST = '''SELECT d.public_id::text AS public_id, d.updated_at, d.active, d.title, d.description,
    d.profile_scope, mt.code AS menu_type_code, r.public_id::text AS recipe_public_id,
    r.title AS recipe_title
    FROM cafeteria.dish_templates d
    LEFT JOIN cafeteria.menu_types mt ON mt.id=d.menu_type_id
    LEFT JOIN cafeteria.recipes r ON r.id=d.recipe_id
    WHERE (:archived OR d.active)
      AND (d.recipe_id IS NULL OR r.location_id=:location)
    ORDER BY lower(d.title), d.public_id'''


@dataclass(frozen=True)
class DishTemplate:
    public_id: str
    updated_at: datetime
    active: bool
    title: str
    description: str | None
    profile_scope: str
    menu_type_code: str | None
    recipe_public_id: str | None
    recipe_title: str | None


def _safe(function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except SQLAlchemyError as exc:
            original = getattr(exc, 'orig', None)
            message = getattr(getattr(original, 'diag', None), 'message_primary', None)
            error = ERRORS.get(getattr(original, 'sqlstate', ''), RecipeUnavailableError)
            raise error(message or 'Gerichtvorlage derzeit nicht möglich.') from None
    return wrapped


def _payload(values: Mapping[str, object]) -> dict[str, object]:
    allowed = {'menu_type_code', 'profile_scope', 'title', 'description', 'recipe_public_id'}
    if set(values) != allowed:
        raise RecipeValidationError('Ungültige Vorlagenfelder.')
    return dict(values)


@_safe
def _call(
    engine: Engine, verb: str, actor: ActorExpectation, location: int,
    payload: Mapping[str, object], *, target: str | None, expected: datetime | None,
) -> dict[str, Any]:
    if not isinstance(actor, ActorExpectation):
        raise RecipeValidationError('Originalakteur erforderlich.')
    if verb == 'create' and (target is not None or expected is not None):
        raise RecipeValidationError('Ungültige neue Gerichtvorlage.')
    if verb != 'create' and (target is None or expected is None):
        raise RecipeValidationError('Ursprünglicher Stand erforderlich.')
    values = {
        'actor': positive(actor.user_id), 'authz': positive(actor.authz_version),
        'location': positive(location),
        'target': None if target is None else identifier(target),
        'expected': expected,
        'payload': json.dumps(payload, ensure_ascii=False, allow_nan=False),
    }
    with engine.begin() as current:
        return dict(current.execute(text(SQL[verb]), values).scalar_one())


def list_templates(engine: Engine, *, include_archived: bool = False) -> tuple[DishTemplate, ...]:
    location = get_location(engine)
    with engine.connect() as current:
        rows = current.execute(text(LIST), {'location': location, 'archived': include_archived}).mappings()
        return tuple(DishTemplate(
            public_id=str(row['public_id']), updated_at=row['updated_at'], active=bool(row['active']),
            title=str(row['title']), description=row['description'],
            profile_scope=str(row['profile_scope']), menu_type_code=row['menu_type_code'],
            recipe_public_id=row['recipe_public_id'], recipe_title=row['recipe_title'],
        ) for row in rows)


def get_template(engine: Engine, public_id: str) -> DishTemplate:
    identifier(public_id)
    for row in list_templates(engine, include_archived=True):
        if row.public_id == public_id:
            return row
    raise RecipeNotFoundError('Unbekannte Gerichtvorlage.')


def create_template(
    engine: Engine, actor: ActorExpectation, payload: Mapping[str, object], *,
    expected_location_id: int, target: str | None = None, expected: datetime | None = None,
) -> dict[str, Any]:
    if get_location(engine) != expected_location_id:
        raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.')
    return _call(engine, 'create', actor, expected_location_id, _payload(payload),
                 target=target, expected=expected)


def update_template(
    engine: Engine, actor: ActorExpectation, public_id: str, expected: datetime,
    payload: Mapping[str, object], *, expected_location_id: int,
) -> dict[str, Any]:
    if get_location(engine) != expected_location_id:
        raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.')
    return _call(engine, 'update', actor, expected_location_id, _payload(payload),
                 target=public_id, expected=expected)


def set_template_active(
    engine: Engine, actor: ActorExpectation, public_id: str, expected: datetime, *,
    active: bool, expected_location_id: int,
) -> dict[str, Any]:
    if get_location(engine) != expected_location_id:
        raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.')
    return _call(engine, 'active', actor, expected_location_id, {'active': active},
                 target=public_id, expected=expected)


def parse_updated_at(raw: str) -> datetime:
    if not isinstance(raw, str) or not raw:
        raise RecipeValidationError('Ursprünglicher Stand erforderlich.')
    try:
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError as error:
        raise RecipeValidationError('Ursprünglicher Stand erforderlich.') from error
    return value


def as_uuid(raw: str) -> str:
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError, TypeError) as error:
        raise RecipeNotFoundError('Unbekannte Gerichtvorlage.') from error
