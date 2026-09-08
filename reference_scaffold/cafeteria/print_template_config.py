"""Bounded properties for the two existing weekly PDF layouts."""
from __future__ import annotations

import unicodedata
from typing import Any, NotRequired, TypedDict, cast

from .patient_payload import _patient_text_is_forbidden

PROFILES = ('staff_guest', 'patient')
CHOICES = {
    'palette': {'reference': 'Druckvorlage Blau', 'brand': 'Südhang Magenta', 'teal': 'Südhang Petrol',
                'active_brand': 'Aktive Marke übernehmen'},
    'font': {'carlito': 'Carlito', 'fira': 'Fira Sans', 'active_brand': 'Aktive Marke übernehmen'},
    'text_size': {'auto': 'Automatisch, mindestens 8,5 pt', 'standard': 'Standard', 'large': 'Gross'},
    'logo': {'print': 'Südhang Drucklogo', 'wordmark': 'Südhang Wortmarke', 'none': 'Ohne Logo',
             'active_brand': 'Aktive Marke übernehmen'},
    'margin': {'standard': 'Standard · 21 pt', 'wide': 'Breit · 28 pt', 'wider': 'Sehr breit · 36 pt'},
    'spacing': {'standard': 'Standard', 'roomy': 'Mehr Abstand'},
}
TEXT_LIMITS = {'header_text': 72, 'footer_text': 160}
LAYOUT_CHOICES = {
    'grid': ('days_rows', 'days_columns'), 'photo': ('none', 'small', 'medium'),
    'alignment': ('left', 'center'), 'day_label_width': ('compact', 'standard', 'wide'),
    'row_spacing': ('compact', 'standard', 'roomy'), 'legend_position': ('top', 'bottom'),
}
LAYOUT_BINDINGS = {
    'header': ('logo', 'title', 'date_range', 'week_number', 'header_note'),
    'footer': ('service_notes', 'footer_note'),
    'menu_fields': ('title', 'components', 'image', 'origins', 'allergens', 'labels', 'prices'),
}


class WeekPdfLayout(TypedDict):
    version: int
    grid: str
    header: list[str]
    footer: list[str]
    menu_fields: list[str]
    photo: str
    alignment: str
    day_label_width: str
    row_spacing: str
    legend_position: str


class PrintTemplateConfig(TypedDict):
    palette: str
    font: str
    text_size: str
    logo: str
    margin: str
    spacing: str
    header_text: str
    footer_text: str
    layout: NotRequired[WeekPdfLayout]


def default_config() -> PrintTemplateConfig:
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


def default_layout(profile: str) -> WeekPdfLayout:
    """New layouts are explicit; never inject these fields into old revisions."""
    if profile not in PROFILES:
        raise PrintTemplateValidationError('Unbekanntes Druckprofil.')
    return {
        'version': 1, 'grid': 'days_columns' if profile == 'patient' else 'days_rows',
        'header': list(LAYOUT_BINDINGS['header']),
        'footer': list(LAYOUT_BINDINGS['footer']),
        'menu_fields': [field for field in LAYOUT_BINDINGS['menu_fields']
                        if profile != 'patient' or field != 'prices'],
        'photo': 'none', 'alignment': 'left', 'day_label_width': 'standard',
        'row_spacing': 'standard', 'legend_position': 'bottom',
    }


def validate_layout(value: Any, profile: str) -> WeekPdfLayout:
    keys = {'version', *LAYOUT_CHOICES, *LAYOUT_BINDINGS}
    if (profile not in PROFILES or not isinstance(value, dict) or len(value) != len(keys)
            or set(value) != keys or type(value['version']) is not int or value['version'] != 1):
        raise PrintTemplateValidationError('Das Wochenlayout ist ungültig.', 'layout')
    result: dict[str, Any] = {'version': 1}
    for field, choices in LAYOUT_CHOICES.items():
        if not isinstance(value[field], str) or value[field] not in choices:
            raise PrintTemplateValidationError('Bitte eine angebotene Layouteinstellung auswählen.', field)
        result[field] = value[field]
    for field, bindings in LAYOUT_BINDINGS.items():
        required = set(bindings) - ({'prices'} if profile == 'patient' else set())
        order = value[field]
        if (not isinstance(order, list) or len(order) != len(required)
                or not all(isinstance(item, str) and item in bindings for item in order)
                or set(order) != required):
            raise PrintTemplateValidationError('Alle Pflichtfelder müssen genau einmal vorkommen.', field)
        result[field] = list(order)
    return cast(WeekPdfLayout, result)


def validate_config(value: Any, profile: str) -> PrintTemplateConfig:
    if (profile not in PROFILES or not isinstance(value, dict) or len(value) not in {8, 9}
            or set(value) not in (set(default_config()), {*default_config(), 'layout'})):
        raise PrintTemplateValidationError('Die Vorlageneigenschaften sind ungültig.')
    result: dict[str, Any] = {}
    for field, choices in CHOICES.items():
        if not isinstance(value[field], str) or value[field] not in choices:
            raise PrintTemplateValidationError('Bitte eine angebotene Einstellung auswählen.', field)
        result[field] = value[field]
    for field, limit in TEXT_LIMITS.items():
        result[field] = plain_text(value[field], field, limit)
        if profile == 'patient' and _patient_text_is_forbidden(result[field]):
            raise PrintTemplateValidationError('Patientenvorlagen dürfen keine Kostenangaben enthalten.', field)
    if 'layout' in value:
        result['layout'] = validate_layout(value['layout'], profile)
    return cast(PrintTemplateConfig, result)
