"""Stable B2 imports for B3, B4 and recipe persistence."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Engine
from . import master_data_reads as reads
from .auth.local_users import ActorExpectation
from .master_data_commands import command, decision, mutation, safe
from .master_data_types import MasterDataValidationError, MutationResult, ObjectExpectation, ProposalDecision, VocabularyKind
from .roles import require_capability


# The availability wrapper encloses the session/capability database lookup too.
list_units = safe(require_capability('draft.read')(reads.list_units))
get_unit = safe(require_capability('draft.read')(reads.get_unit))
list_vocabulary = safe(require_capability('draft.read')(reads.list_vocabulary))
get_vocabulary = safe(require_capability('draft.read')(reads.get_vocabulary))
list_foods = safe(require_capability('draft.read')(reads.list_foods))
get_food = safe(require_capability('draft.read')(reads.get_food))
list_proposals = safe(require_capability('draft.read')(reads.list_proposals))
get_proposal = safe(require_capability('draft.read')(reads.get_proposal))

resolve_food = safe(reads.resolve_food)
resolve_unit = safe(reads.resolve_unit)
resolve_tag = safe(reads.resolve_tag)

@safe
@require_capability('masterdata.write')
def create_unit(engine: Engine, actor: ActorExpectation, *, code: str, display_name: str, dimension: str, base_factor: str | Decimal | None) -> MutationResult:
    return mutation(engine, 'create_unit', actor, None, {'code': code, 'display_name': display_name, 'dimension': dimension, 'base_factor': base_factor})


@safe
@require_capability('masterdata.write')
def rename_unit(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, display_name: str) -> MutationResult:
    return mutation(engine, 'rename_unit', actor, target, {'display_name': display_name})


@safe
@require_capability('masterdata.write')
def set_unit_active(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, active: bool) -> MutationResult:
    return mutation(engine, 'set_active_unit', actor, target, {'active': active})


@safe
@require_capability('masterdata.write')
def create_food(engine: Engine, actor: ActorExpectation, payload: Mapping[str, object]) -> MutationResult:
    return mutation(engine, 'create_food', actor, None, payload)


@safe
@require_capability('masterdata.write')
def update_food(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, payload: Mapping[str, object]) -> MutationResult:
    return mutation(engine, 'update_food', actor, target, payload)


@safe
@require_capability('masterdata.write')
def set_food_active(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, active: bool) -> MutationResult:
    return mutation(engine, 'set_food_active', actor, target, {'active': active})


@safe
@require_capability('masterdata.write')
def replace_food_tags(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, tag_public_ids: Sequence[str]) -> MutationResult:
    return mutation(engine, 'replace_food_tags', actor, target, {'tags': tag_public_ids})


@safe
@require_capability('masterdata.write')
def replace_food_metadata(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, allergens: Sequence[Mapping[str, str]], labels: Sequence[str]) -> MutationResult:
    return mutation(engine, 'replace_food_metadata', actor, target, {'allergens': allergens, 'labels': labels})


@safe
@require_capability('masterdata.write')
def set_food_allergen_review(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, *, checked: bool) -> MutationResult:
    return mutation(engine, 'set_food_allergen_review', actor, target, {'checked': checked})


@safe
@require_capability('masterdata.write')
def replace_food_storage_locations(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, storage_public_ids: Sequence[str]) -> MutationResult:
    return mutation(engine, 'replace_food_storage_locations', actor, target, {'storage_locations': storage_public_ids})


@safe
@require_capability('masterdata.write')
def create_proposal(engine: Engine, actor: ActorExpectation, *, source: str, source_reference: str, fetched_at: datetime, payload: Mapping[str, object], source_url: str | None = None, source_note: str | None = None, food_public_id: str | None = None) -> MutationResult:
    return mutation(engine, 'create_proposal', actor, None, {'source': source, 'source_reference': source_reference, 'fetched_at': fetched_at, 'payload': payload, 'source_url': source_url, 'source_note': source_note, 'food_public_id': food_public_id})


@safe
@require_capability('masterdata.write')
def create_vocabulary(engine: Engine, kind: VocabularyKind, actor: ActorExpectation, *, code: str, name: str, sort_order: int | None = None) -> MutationResult:
    reads.vocabulary_sql(kind)
    payload: dict[str, object] = {'code': code, 'name': name}
    if sort_order is not None:
        payload['sort_order'] = sort_order
    return mutation(engine, 'create_' + kind, actor, None, payload)


@safe
@require_capability('masterdata.write')
def update_vocabulary(engine: Engine, kind: VocabularyKind, actor: ActorExpectation, target: ObjectExpectation, *, name: str, sort_order: int | None = None) -> MutationResult:
    reads.vocabulary_sql(kind)
    payload: dict[str, object] = {'name': name}
    if sort_order is not None:
        payload['sort_order'] = sort_order
    return mutation(engine, 'update_' + kind, actor, target, payload)


@safe
@require_capability('masterdata.write')
def set_vocabulary_active(engine: Engine, kind: VocabularyKind, actor: ActorExpectation, target: ObjectExpectation, *, active: bool) -> MutationResult:
    reads.vocabulary_sql(kind)
    payload: dict[str, object] = {'active': active}
    return mutation(engine, 'set_active_' + kind, actor, target, payload)


@safe
@require_capability('recipe.import')
def accept_proposal(engine: Engine, actor: ActorExpectation, proposal: ObjectExpectation,
                    food: ObjectExpectation, fields: Sequence[str]) -> ProposalDecision:
    if not isinstance(food, ObjectExpectation):
        raise MasterDataValidationError('Ungültige Objekterwartung.')
    return decision(command(engine, 'accept_proposal', actor, proposal,
        {'food_public_id': food.public_id, 'food_row_version': food.row_version, 'fields': fields}))


@safe
@require_capability('recipe.import')
def reject_proposal(engine: Engine, actor: ActorExpectation, proposal: ObjectExpectation, *,
                    reason: str | None = None) -> ProposalDecision:
    return decision(command(engine, 'reject_proposal', actor, proposal, {'reason': reason}))
