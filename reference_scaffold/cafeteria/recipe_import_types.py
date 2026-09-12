"""Immutable import previews; parsing never authorizes or performs an import."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeImportIssue:
    row_number: int | None
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class RecipeImportRow:
    row_number: int
    source_line: int | None
    payload: Mapping[str, object] | None
    errors: tuple[RecipeImportIssue, ...]


@dataclass(frozen=True)
class RecipeImportDuplicate:
    title: str
    row_numbers: tuple[int, ...]


@dataclass(frozen=True)
class RecipeImportPreview:
    source_filename: str | None
    source_sha256: str | None
    content_type: str | None
    fetched_at: str | None
    rows: tuple[RecipeImportRow, ...] = ()
    errors: tuple[RecipeImportIssue, ...] = ()
    duplicate_groups: tuple[RecipeImportDuplicate, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Parse validity only; duplicate decisions and all write guards remain required."""
        return bool(self.rows) and not self.errors and all(not row.errors for row in self.rows)
