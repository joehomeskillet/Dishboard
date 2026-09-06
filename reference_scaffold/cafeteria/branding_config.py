"""The single validated token contract for web, signage and print branding."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, TypedDict, cast

FONTS = {'fira': 'Fira Sans', 'carlito': 'Carlito'}
COLOR_KEYS = ('primary', 'accent', 'surface', 'text')


class BrandConfig(TypedDict):
    logo_sha256: str | None
    font_body: str
    font_heading: str
    primary: str
    accent: str
    surface: str
    text: str


@dataclass(frozen=True)
class BrandRevision:
    id: int
    name: str
    config: BrandConfig


class BrandingValidationError(ValueError):
    """A user supplied branding value violates the token contract."""


def default_config() -> BrandConfig:
    return {'logo_sha256': None, 'font_body': 'fira', 'font_heading': 'fira',
            'primary': '#8c1c4b', 'accent': '#35666f', 'surface': '#ffffff', 'text': '#383027'}


def contrast(first: str, second: str) -> float:
    def luminance(color: str) -> float:
        rgb = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
        return sum(value * factor for value, factor in zip(linear, (0.2126, 0.7152, 0.0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def validate_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 60:
        raise BrandingValidationError('Bitte einen Namen mit 1 bis 60 Zeichen eingeben.')
    if any(unicodedata.category(char).startswith('C') for char in value) or '<' in value or '>' in value:
        raise BrandingValidationError('Der Name darf nur einfachen Text enthalten.')
    return value.strip()


def validate_config(value: Any) -> BrandConfig:
    if not isinstance(value, dict) or set(value) != set(default_config()):
        raise BrandingValidationError('Die Markeneinstellungen sind unvollständig.')
    for key in ('font_body', 'font_heading'):
        if not isinstance(value[key], str) or value[key] not in FONTS:
            raise BrandingValidationError('Bitte eine der lokal verfügbaren Schriften auswählen.')
    logo = value['logo_sha256']
    if logo is not None and (not isinstance(logo, str) or not re.fullmatch('[0-9a-f]{64}', logo)):
        raise BrandingValidationError('Das ausgewählte Logo ist ungültig.')
    for key in COLOR_KEYS:
        if not isinstance(value[key], str) or not re.fullmatch('#[0-9a-fA-F]{6}', value[key]):
            raise BrandingValidationError('Farben müssen sechsstellige Hex-Farbwerte sein.')
    result = cast(BrandConfig, dict(value))
    for key in COLOR_KEYS:
        result[key] = value[key].lower()  # type: ignore[literal-required]
    for key in ('text', 'primary', 'accent'):
        if contrast(result[key], result['surface']) < 4.5:  # type: ignore[literal-required]
            raise BrandingValidationError('Text, Primär- und Akzentfarbe benötigen mindestens 4.5:1 Kontrast zum Hintergrund.')
    return result
