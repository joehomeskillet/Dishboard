"""Bound fixed SQL verbs and the outer recipe availability boundary."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .auth.local_users import ActorExpectation
from .component_catalog_store import ComponentCatalogConfigurationError
from .master_data_types import MutationResult, ObjectExpectation
from .recipe_types import (
    RecipeActorDeniedError, RecipeConfigurationError, RecipeConflictError,
    RecipeNotFoundError, RecipeStaleActorError, RecipeUnavailableError, RecipeValidationError,
)
from .recipe_values import identifier, positive

P = ParamSpec('P')
T = TypeVar('T')
ERRORS = {'P1901': RecipeValidationError, 'P1902': RecipeActorDeniedError,
          'P1903': RecipeStaleActorError, 'P1904': RecipeConfigurationError, '22023': RecipeNotFoundError,
          '55000': RecipeConflictError, '23505': RecipeConflictError, '42501': RecipeActorDeniedError}
SQL = {
    'create_recipe': 'SELECT cafeteria.create_recipe_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'update_recipe': 'SELECT cafeteria.update_recipe_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'set_recipe_active': 'SELECT cafeteria.set_recipe_active_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'freeze_recipe_revision': 'SELECT cafeteria.freeze_recipe_revision_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'add_recipe_image': 'SELECT cafeteria.add_recipe_image_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'create_cookbook': 'SELECT cafeteria.create_cookbook_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'update_cookbook': 'SELECT cafeteria.update_cookbook_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'set_cookbook_active': 'SELECT cafeteria.set_cookbook_active_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
    'replace_cookbook_recipes': 'SELECT cafeteria.replace_cookbook_recipes_v22(:actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))',
}


def safe(function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except ComponentCatalogConfigurationError:
            raise RecipeConfigurationError('Genau ein aktiver Standort ist erforderlich.') from None
        except SQLAlchemyError as exc:
            original = getattr(exc, 'orig', None)
            detail = getattr(getattr(original, 'diag', None), 'message_detail', '') or ''
            if detail == 'master_location':
                raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.') from None
            error = ERRORS.get(getattr(original, 'sqlstate', ''), RecipeUnavailableError)
            raise error('Rezeptaktion derzeit nicht möglich.') from None
    return wrapped


def command(engine: Engine, name: str, actor: ActorExpectation, target: ObjectExpectation | None,
            payload: Mapping[str, object], location: int) -> dict[str, Any]:
    if not isinstance(actor, ActorExpectation):
        raise RecipeValidationError('Originalakteur erforderlich.')
    values: dict[str, Any] = {'actor': positive(actor.user_id), 'authz': positive(actor.authz_version),
                             'location': positive(location), 'target': None, 'version': None}
    if target is not None:
        if not isinstance(target, ObjectExpectation):
            raise RecipeValidationError('Originalobjekt erforderlich.')
        values.update(target=identifier(target.public_id), version=positive(target.row_version))
    try:
        values['payload'] = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise RecipeValidationError('Ungültige Rezeptdaten.') from None
    if engine is None:
        raise RecipeUnavailableError('Rezepte sind derzeit nicht verfügbar.')
    with engine.begin() as current:
        return dict(current.execute(text(SQL[name]), values).scalar_one())


def mutation(engine: Engine, name: str, actor: ActorExpectation, target: ObjectExpectation | None,
             payload: Mapping[str, object], location: int) -> MutationResult:
    result = command(engine, name, actor, target, payload, location)
    return MutationResult(str(result['public_id']), int(result['row_version']))
