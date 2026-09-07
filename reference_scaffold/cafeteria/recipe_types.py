"""Immutable recipe values and public validation errors."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal


class RecipeValidationError(ValueError):
    """Invalid recipe input; contains no database details."""


@dataclass(frozen=True)
class IngredientQuantity:
    """Parsed quantity and code; no unit existence or conversion guarantee."""

    quantity: Decimal | None
    unit_code: str | None


class RecipeNotFoundError(ValueError):
    pass


class RecipeConflictError(ValueError):
    pass


class RecipeActorDeniedError(ValueError):
    pass


class RecipeStaleActorError(RecipeActorDeniedError):
    pass


class RecipeConfigurationError(ValueError):
    pass


class RecipeUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class RecipeDTO:
    public_id: str
    row_version: int
    active: bool
    payload: Mapping[str, object]


@dataclass(frozen=True)
class RevisionResult:
    public_id: str
    recipe_public_id: str
    revision_number: int
    recipe_row_version: int
    content_hash_sha256: str


@dataclass(frozen=True)
class RecipeRevisionDTO:
    public_id: str
    recipe_public_id: str
    revision_number: int
    content_hash_sha256: str
    snapshot: Mapping[str, object]
    created_at: datetime
    created_by: int


@dataclass(frozen=True)
class RecipeRevisionSummaryDTO:
    public_id: str
    recipe_public_id: str
    revision_number: int
    content_hash_sha256: str
    created_at: datetime
    created_by: int


@dataclass(frozen=True)
class RecipeAssetDTO:
    sha256: str
    data: bytes
    content_type: str
    width: int
    height: int


@dataclass(frozen=True)
class CookbookDTO:
    public_id: str
    row_version: int
    name: str
    description: str | None
    active: bool
    recipe_public_ids: tuple[str, ...]
