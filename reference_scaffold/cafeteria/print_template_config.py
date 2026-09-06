"""Bounded properties for the two existing weekly PDF layouts."""
from __future__ import annotations

import unicodedata
from typing import Any

from .patient_payload import _patient_text_is_forbidden

PROFILES = ('staff_guest', 'patient')
CHOICES = {
    'palette': {'reference': 'Druckvorlage Blau', 'brand': 'Südhang Magenta', 'teal': 'Südhang Petrol'},
    'font': {'carlito': 'Carlito', 'fira': 'Fira Sans'},
    'text_size': {'auto': 'Automatisch, mindestens 8,5 pt', 'standard': 'Standard', 'large': 'Gross'},
    'logo': {'print': 'Südhang Drucklogo', 'wordmark': 'Südhang Wortmarke', 'none': 'Ohne Logo'},
    'margin': {'standard': 'Standard · 21 pt', 'wide': 'Breit · 28 pt', 'wider': 'Sehr breit · 36 pt'},
    'spacing': {'standard': 'Standard', 'roomy': 'Mehr Abstand'},
}
TEXT_LIMITS = {'header_text': 72, 'footer_text': 160}


def default_config() -> dict[str, str]:
    return {
        'palette': 'reference', 'font': 'carlito', 'text_size': 'auto', 'logo': 'print',
        'margin': 'standard', 'spacing': 'standard', 'header_text': '', 'footer_text': '',
    }


class PrintTemplateValidationError(ValueError):
    def __init__(self, message: str, field: str = 'form') -> None:
        super().__init__(message)
        self.field = field


def plain_text(value: object, field: str, limit: int, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise PrintTemplateValidationError(f'Bitte einen Text mit höchstens {limit} Zeichen eingeben.', field)
    if any(unicodedata.category(char).startswith('C') for char in value) or any(char in value for char in '<>'):
        raise PrintTemplateValidationError('Bitte einfachen Text ohne Steuerzeichen oder HTML eingeben.', field)
    return value.strip()


def validate_config(value: Any, profile: str) -> dict[str, str]:
    if profile not in PROFILES or not isinstance(value, dict) or set(value) != set(default_config()):
        raise PrintTemplateValidationError('Die Vorlageneigenschaften sind ungültig.')
    result: dict[str, str] = {}
    for field, choices in CHOICES.items():
        if not isinstance(value[field], str) or value[field] not in choices:
            raise PrintTemplateValidationError('Bitte eine angebotene Einstellung auswählen.', field)
        result[field] = value[field]
    for field, limit in TEXT_LIMITS.items():
        result[field] = plain_text(value[field], field, limit)
        if profile == 'patient' and _patient_text_is_forbidden(result[field]):
            raise PrintTemplateValidationError('Patientenvorlagen dürfen keine Kostenangaben enthalten.', field)
    return result
