from __future__ import annotations

from dataclasses import dataclass

from cafeteria.component_catalog_metadata import (
    MetadataValidationError, normalize_metadata, origin_country_code,
)


@dataclass(frozen=True)
class ComponentFilters:
    usage: str = ''
    allergen: str = ''
    presence: str = ''
    label: str = ''
    origin: str = ''
    status: str = ''

    def __post_init__(self) -> None:
        values = (self.usage, self.allergen, self.presence, self.label, self.origin, self.status)
        if any(type(value) is not str for value in values):
            raise MetadataValidationError('Komponentenfilter sind ungültig.')
        if self.usage not in {'', 'used', 'unused'}:
            raise MetadataValidationError('Verwendungsfilter ist ungültig.')
        if self.status not in {'', 'active', 'archived', 'all'}:
            raise MetadataValidationError('Archivfilter ist ungültig.')
        if self.presence not in {'', 'contains', 'may_contain'}:
            raise MetadataValidationError('Allergenpräsenz ist ungültig.')
        if self.presence and self.allergen in {'', 'unknown'}:
            raise MetadataValidationError('Bitte ein Allergen für die Präsenz auswählen.')
        normalize_metadata(
            [self.label] if self.label else [],
            [(self.allergen, 'contains')] if self.allergen not in {'', 'unknown'} else [],
        )
        if self.origin != 'unknown':
            origin_country_code(self.origin)
