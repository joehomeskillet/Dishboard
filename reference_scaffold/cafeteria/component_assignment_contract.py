"""Internal recipe-aware assignments; wire only with the complete R5b writer.

A legacy replace/reorder must conflict if ANY stored recipe binding exists.
Never preserve by position or infer the latest revision from a recipe head.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID


class AssignmentValidationError(ValueError):
    """Malformed internal assignment payload."""


@dataclass(frozen=True)
class Assignment:
    component_public_id: str | None
    component_text: str | None
    recipe_revision_public_id: str | None
    recipe_field_present: bool

    def as_payload(self) -> dict[str, str | None]:
        result = {'component_public_id': self.component_public_id, 'component_text': self.component_text}
        if self.recipe_field_present:
            result['recipe_revision_public_id'] = self.recipe_revision_public_id
        return result


def _uuid(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AssignmentValidationError('Die Referenz muss eine UUID sein.')
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise AssignmentValidationError('Die Referenz muss eine UUID sein.') from exc
    if canonical != value:
        raise AssignmentValidationError('Die Referenz muss eine kanonische UUID sein.')
    return canonical


def normalize_assignments(value: object) -> tuple[Assignment, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) > 32767:
        raise AssignmentValidationError('Ungültige Komponentenliste.')
    required = {'component_public_id', 'component_text'}
    result = []
    for row in value:
        if not isinstance(row, Mapping) or set(row) not in (required, required | {'recipe_revision_public_id'}):
            raise AssignmentValidationError('Ungültige Komponentenfelder.')
        public_id = _uuid(row['component_public_id'])
        label = row['component_text']
        if (public_id is None) == (label is None) or (label is not None and (
                not isinstance(label, str) or not label.strip())):
            raise AssignmentValidationError('Genau Katalogkomponente oder Komponententext ist erforderlich.')
        result.append(Assignment(public_id, label, _uuid(row.get('recipe_revision_public_id')),
                                 'recipe_revision_public_id' in row))
    return tuple(result)
