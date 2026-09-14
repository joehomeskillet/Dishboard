"""Internal recipe-aware assignments; wire only with the complete R5b writer.

A legacy replace/reorder must conflict if ANY stored recipe binding exists.
Never preserve by position or infer the latest revision from a recipe head.
"""
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from .quantities import QuantityError, parse_quantity


class AssignmentValidationError(ValueError):
    """Malformed internal assignment payload."""


# Same format as quantities.Unit's code and recipe_values' unit_code (duplicated on purpose:
# each module validates its own storage boundary independently).
_UNIT_CODE = re.compile(r'[A-Z][A-Z0-9_]{0,15}')
_REQUIRED_KEYS = {'component_public_id', 'component_text'}
_TARGET_KEYS = {'target_quantity', 'target_quantity_unit_code'}


@dataclass(frozen=True)
class Assignment:
    component_public_id: str | None
    component_text: str | None
    recipe_revision_public_id: str | None
    recipe_field_present: bool
    target_quantity: str | None = None
    target_quantity_unit_code: str | None = None
    target_field_present: bool = False

    def as_payload(self) -> dict[str, str | None]:
        result = {'component_public_id': self.component_public_id, 'component_text': self.component_text}
        if self.recipe_field_present:
            result['recipe_revision_public_id'] = self.recipe_revision_public_id
        if self.target_field_present:
            result['target_quantity'] = self.target_quantity
            result['target_quantity_unit_code'] = self.target_quantity_unit_code
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


def _empty(value: object) -> bool:
    return value is None or value == ''


def _target_pair(raw_quantity: object, raw_unit: object) -> tuple[str | None, str | None]:
    """Both keys stay optional but only as a pair; an empty pair clears a stored value."""
    if _empty(raw_quantity) and _empty(raw_unit):
        return None, None
    if _empty(raw_quantity) or _empty(raw_unit):
        raise AssignmentValidationError('Zielmenge und Zieleinheit müssen gemeinsam angegeben werden.')
    if not isinstance(raw_quantity, str):
        raise AssignmentValidationError('Zielmenge muss als Text übergeben werden.')
    try:
        quantity = parse_quantity(raw_quantity)
    except QuantityError as error:
        raise AssignmentValidationError(str(error)) from error
    if not isinstance(raw_unit, str) or _UNIT_CODE.fullmatch(raw_unit) is None:
        raise AssignmentValidationError('Zieleinheit hat ein ungültiges Format.')
    return str(quantity), raw_unit


def normalize_assignments(value: object) -> tuple[Assignment, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) > 32767:
        raise AssignmentValidationError('Ungültige Komponentenliste.')
    result = []
    for row in value:
        if not isinstance(row, Mapping):
            raise AssignmentValidationError('Ungültige Komponentenfelder.')
        extra = set(row) - _REQUIRED_KEYS
        target_keys_present = extra & _TARGET_KEYS
        if len(target_keys_present) == 1:
            raise AssignmentValidationError('Zielmenge und Zieleinheit müssen gemeinsam angegeben werden.')
        recognized = _REQUIRED_KEYS | (extra & {'recipe_revision_public_id'}) | (extra & _TARGET_KEYS)
        if set(row) != recognized:
            raise AssignmentValidationError('Ungültige Komponentenfelder.')
        public_id = _uuid(row['component_public_id'])
        label = row['component_text']
        if (public_id is None) == (label is None) or (label is not None and (
                not isinstance(label, str) or not label.strip())):
            raise AssignmentValidationError('Genau Katalogkomponente oder Komponententext ist erforderlich.')
        target_field_present = bool(target_keys_present)
        target_quantity, target_quantity_unit_code = (
            _target_pair(row.get('target_quantity'), row.get('target_quantity_unit_code'))
            if target_field_present else (None, None)
        )
        result.append(Assignment(public_id, label, _uuid(row.get('recipe_revision_public_id')),
                                 'recipe_revision_public_id' in row, target_quantity,
                                 target_quantity_unit_code, target_field_present))
    return tuple(result)
