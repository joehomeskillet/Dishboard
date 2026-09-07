"""Public R1 service contract; decorators match the existing B2 trust boundary."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import Engine

from . import recipe_reads as reads
from .auth.local_users import ActorExpectation
from .master_data_types import MutationResult, ObjectExpectation
from .recipe_commands import command, mutation, safe
from .recipe_snapshots import image_payload
from .recipe_types import RecipeValidationError, RevisionResult
from .recipe_values import identifier, image_fields, recipe_payload, recipe_text, rows
from .roles import require_capability

get_location = safe(require_capability('draft.read')(reads.get_location))
list_recipes = safe(require_capability('draft.read')(reads.list_recipes))
get_recipe = safe(require_capability('draft.read')(reads.get_recipe))
get_revision = safe(require_capability('draft.read')(reads.get_revision))
list_revisions = safe(require_capability('draft.read')(reads.list_revisions))
get_recipe_asset = safe(require_capability('draft.read')(reads.get_recipe_asset))
list_cookbooks = safe(require_capability('draft.read')(reads.list_cookbooks))
get_cookbook = safe(require_capability('draft.read')(reads.get_cookbook))


@safe
@require_capability('recipe.write')
def create_recipe(engine: Engine, actor: ActorExpectation, payload: Mapping[str, object], *, expected_location_id: int) -> MutationResult:
    return mutation(engine, 'create_recipe', actor, None, recipe_payload(payload), expected_location_id)


@safe
@require_capability('recipe.write')
def update_recipe(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, payload: Mapping[str, object], *, expected_location_id: int) -> MutationResult:
    return mutation(engine, 'update_recipe', actor, target, recipe_payload(payload), expected_location_id)


@safe
@require_capability('recipe.write')
def set_recipe_active(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, active: bool, expected_location_id: int) -> MutationResult:
    if type(active) is not bool:
        raise RecipeValidationError('Archivstatus muss boolesch sein.')
    return mutation(engine, 'set_recipe_active', actor, target, {'active': active}, expected_location_id)


@safe
@require_capability('recipe.write')
def freeze_revision(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, expected_location_id: int) -> RevisionResult:
    result = command(engine, 'freeze_recipe_revision', actor, target, {}, expected_location_id)
    return RevisionResult(**result)


@safe
@require_capability('recipe.write')
def add_recipe_image(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, data: bytes,
                     content_type: str, caption: str | None = None, source_url: str | None = None,
                     source_license: str | None = None, fetched_at: datetime | None = None,
                     expected_location_id: int) -> MutationResult:
    payload = image_payload(data, content_type)
    payload.update(image_fields({'sha256': payload['sha256'], 'caption': caption, 'source_url': source_url,
                                 'source_license': source_license, 'fetched_at': fetched_at}))
    return mutation(engine, 'add_recipe_image', actor, target, payload, expected_location_id)


@safe
@require_capability('recipe.write')
def create_cookbook(engine: Engine, actor: ActorExpectation, *, name: str, description: str | None = None,
                    expected_location_id: int) -> MutationResult:
    return mutation(engine, 'create_cookbook', actor, None,
                    {'name': recipe_text(name, 120), 'description': recipe_text(description, 2000, multiline=True, required=False)}, expected_location_id)


@safe
@require_capability('recipe.write')
def update_cookbook(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, name: str,
                    description: str | None = None, expected_location_id: int) -> MutationResult:
    return mutation(engine, 'update_cookbook', actor, target,
                    {'name': recipe_text(name, 120), 'description': recipe_text(description, 2000, multiline=True, required=False)}, expected_location_id)


@safe
@require_capability('recipe.write')
def set_cookbook_active(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, active: bool,
                        expected_location_id: int) -> MutationResult:
    if type(active) is not bool:
        raise RecipeValidationError('Archivstatus muss boolesch sein.')
    return mutation(engine, 'set_cookbook_active', actor, target, {'active': active}, expected_location_id)


@safe
@require_capability('recipe.write')
def replace_cookbook_recipes(engine: Engine, actor: ActorExpectation, target: ObjectExpectation,
                             recipe_public_ids: Sequence[str], *, expected_location_id: int) -> MutationResult:
    identifiers = [identifier(value) for value in rows(recipe_public_ids)]
    if len(identifiers) != len(set(identifiers)):
        raise RecipeValidationError('Rezeptzuordnungen müssen eindeutig sein.')
    return mutation(engine, 'replace_cookbook_recipes', actor, target, {'recipes': identifiers}, expected_location_id)
