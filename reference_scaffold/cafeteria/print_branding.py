"""Resolve one active brand at the PDF database boundary, never in the renderer."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import Connection

from .branding import BrandingStateError, active_branding
from .branding_assets import load_logo
from .print_template_config import validate_config

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class PdfBranding:
    revision_id: int
    primary: RGB
    accent: RGB
    surface: RGB
    text: RGB
    font_body: str
    font_heading: str
    logo_png: bytes | None


def _rgb(value: str) -> RGB:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def load_pdf_branding(connection: Connection, profile: str, config: Mapping[str, object]) -> PdfBranding | None:
    """Legacy overrides neither read branding nor depend on its availability."""
    config = validate_config(config, profile)
    if not any(config.get(field) == 'active_brand' for field in ('palette', 'font', 'logo')):
        return None
    revision = active_branding(connection)
    brand = revision.config
    png = None
    if config['logo'] == 'active_brand' and brand['logo_sha256']:
        try:
            logo = load_logo(connection, brand['logo_sha256'])
        except LookupError as error:
            raise BrandingStateError('Das aktive Markenlogo ist nicht verfügbar.') from error
        if sha256(logo.png).hexdigest() != brand['logo_sha256']:
            raise BrandingStateError('Das aktive Markenlogo ist beschädigt.')
        png = logo.png
    return PdfBranding(revision.id, _rgb(brand['primary']), _rgb(brand['accent']),
                       _rgb(brand['surface']), _rgb(brand['text']),
                       brand['font_body'], brand['font_heading'], png)
