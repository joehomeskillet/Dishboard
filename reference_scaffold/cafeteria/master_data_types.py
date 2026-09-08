"""Public, immutable master-data values and safe service errors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


VocabularyKind = Literal['food_category', 'tag', 'storage_location']


class MasterDataError(ValueError):
    """A bounded public error; never contains SQL or connection parameters."""


class MasterDataValidationError(MasterDataError):
    pass


class MasterDataNotFoundError(MasterDataError):
    pass


class MasterDataConflictError(MasterDataError):
    pass


class StaleObjectError(MasterDataConflictError):
    pass


class ActorDeniedError(MasterDataError):
    pass


class StaleActorError(ActorDeniedError):
    pass


class MasterDataConfigurationError(MasterDataError):
    pass


class MasterDataUnavailableError(MasterDataError):
    pass


@dataclass(frozen=True)
class ObjectExpectation:
    public_id: str
    row_version: int


@dataclass(frozen=True)
class MutationResult:
    public_id: str
    row_version: int


@dataclass(frozen=True)
class UnitDTO:
    public_id: str
    code: str
    display_name: str
    dimension: str
    base_factor: Decimal | None
    active: bool
    row_version: int


@dataclass(frozen=True)
class VocabularyDTO:
    public_id: str
    kind: VocabularyKind
    code: str
    name: str
    sort_order: int | None
    active: bool
    row_version: int


@dataclass(frozen=True)
class SourceDTO:
    kind: str
    reference: str | None
    url: str | None
    note: str | None
    fetched_at: datetime | None


@dataclass(frozen=True)
class PreparedRecipeDTO:
    recipe_public_id: str
    revision_public_id: str
    revision_number: int
    content_hash_sha256: str
    title: str
    yield_quantity: Decimal
    yield_unit_code: str
    recipe_active: bool


@dataclass(frozen=True)
class FoodDTO:
    public_id: str
    name: str
    category: VocabularyDTO | None
    base_unit: UnitDTO
    density_g_per_ml: Decimal | None
    piece_weight_g: Decimal | None
    note: str
    allergen_review_status: str
    source: SourceDTO
    active: bool
    row_version: int
    allergens: tuple[tuple[str, str], ...]
    labels: tuple[str, ...]
    tags: tuple[VocabularyDTO, ...]
    storage_locations: tuple[VocabularyDTO, ...]
    prepared_recipe: PreparedRecipeDTO | None = None


@dataclass(frozen=True)
class ProposalDecision:
    status: str
    decided_at: datetime
    adopted: tuple[str, ...]
    unchanged: tuple[str, ...]
    not_supported: tuple[str, ...]
    food_public_id: str | None
    food_row_version_before: int | None
    food_row_version_after: int | None


@dataclass(frozen=True)
class ProposalDTO:
    public_id: str
    row_version: int
    status: str
    source: SourceDTO
    food_public_id: str | None
    payload: object
    decision: ProposalDecision | None
