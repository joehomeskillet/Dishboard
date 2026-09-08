"""Native, deterministic A4 recipes from one immutable revision; no live reads."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, cast

from fpdf import FPDF
from fpdf.errors import FPDFException
from fpdf.fonts import TTFFont

from ..branding_config import contrast
from ..print_branding import PdfBranding
from ..print_template_config import PrintTemplateConfig, PrintTemplateValidationError, validate_config
from ..recipe_snapshots import image_payload
from ..recipe_types import (
    RecipeAssetDTO, RecipeConfigurationError, RecipeRevisionDTO, RecipeValidationError,
)
from ..recipe_values import identifier, positive, recipe_payload
from .recipe_forms import FormError
from .recipe_scaling import scaled_recipe
from .week_pdf import ASSETS, INK, LOGOS, PALETTES

# Recipe pages flow freely; these generous margins are independent of weekly grids.
RECIPE_MARGINS = {'standard': 48.0, 'wide': 54.0, 'wider': 64.0}
UNKNOWN_ALLERGENS = 'Allergenangaben in dieser Revision nicht erfasst'
SOURCE_NAMES = {'manual': 'Manuell erfasst', 'url': 'Internetquelle',
                'file_import': 'Dateiimport', 'ai_assisted': 'KI-unterstützt'}


class RecipePdfError(ValueError):
    """A bounded, complete recipe PDF could not be produced."""


def _readable_brand(branding: PdfBranding) -> None:
    # Paper is always white; primary appears only in large, bold headings.
    for color, minimum, label in ((branding.text, 4.5, 'Textfarbe'),
                                   (branding.primary, 3.0, 'Überschriftenfarbe')):
        if len(color) != 3 or any(type(channel) is not int or not 0 <= channel <= 255 for channel in color):
            raise RecipeConfigurationError('Die Druckfarben der aktiven Marke sind ungültig.')
        encoded = '#' + ''.join(f'{channel:02x}' for channel in color)
        if contrast(encoded, '#ffffff') < minimum:
            raise RecipeConfigurationError(
                f'Die {label} der aktiven Marke ist auf weissem Rezeptpapier nicht lesbar.')


def _selected_recipe(revision: RecipeRevisionDTO) -> Mapping[str, Any]:
    if (not isinstance(revision.snapshot, Mapping)
            or type(revision.snapshot.get('schema_version')) is not int
            or revision.snapshot['schema_version'] != 1):
        raise RecipeConfigurationError('Diese Rezeptrevision wird vom PDF-Druck nicht unterstützt.')
    identifier(revision.public_id)
    identifier(revision.recipe_public_id)
    positive(revision.revision_number)
    if not isinstance(revision.content_hash_sha256, str) or not re.fullmatch('[0-9a-f]{64}', revision.content_hash_sha256):
        raise RecipeConfigurationError('Die Identität der Rezeptrevision ist ungültig.')
    original = revision.snapshot['recipe']
    recipe_payload(original)  # Validate bounds only; print the original frozen values.
    return cast(Mapping[str, Any], original)


def _selected_images(recipe: Mapping[str, Any], images: Mapping[str, RecipeAssetDTO]) -> dict[str, bytes]:
    required = {item['sha256'] for item in recipe['images']}
    required.update(step['image_sha256'] for step in recipe['steps'] if step['image_sha256'] is not None)
    selected = {}
    for digest in sorted(required):
        asset = images.get(digest)
        if not isinstance(asset, RecipeAssetDTO) or asset.sha256 != digest:
            raise RecipePdfError('Ein Bild dieser Rezeptrevision fehlt.')
        verified = image_payload(asset.data, asset.content_type)
        if (verified['sha256'] != digest or verified['width'] != asset.width
                or verified['height'] != asset.height):
            raise RecipePdfError('Ein Bild dieser Rezeptrevision ist beschädigt.')
        selected[digest] = asset.data
    return selected


class _RecipeDocument(FPDF):
    def __init__(self, config: PrintTemplateConfig, branding: PdfBranding | None) -> None:
        super().__init__(orientation='P', unit='pt', format='A4')
        self.config = config
        self.body_size = 12.0 if config['text_size'] == 'large' else 11.0
        self.leading = self.body_size * (1.6 if config['spacing'] == 'roomy' else 1.45)
        self.primary, self.ink = (
            (branding.primary, branding.text) if branding and config['palette'] == 'active_brand'
            else (PALETTES[config['palette']][0], INK)
        )
        body = branding.font_body if branding and config['font'] == 'active_brand' else config['font']
        heading = branding.font_heading if branding and config['font'] == 'active_brand' else config['font']
        if body not in ('carlito', 'fira') or heading not in ('carlito', 'fira'):
            raise RecipeConfigurationError('Die Druckschrift der aktiven Marke ist ungültig.')
        for style, font, suffix in (('', body, ''), ('B', heading, '-bold')):
            self.add_font('Recipe', style, ASSETS / 'fonts' / f'weekly-print-{font}{suffix}.ttf')
        self.set_creation_date(datetime(1970, 1, 1, tzinfo=timezone.utc))
        margin = RECIPE_MARGINS[config['margin']]
        self.set_margins(margin, margin, margin)
        self.footer_height = 36.0
        self.set_auto_page_break(True, margin=48)
        self.c_margin = 0
        self.add_page()
        if config['footer_text']:
            self.footer_height += self.paragraph(config['footer_text'], measure=True) + 3
        self.set_auto_page_break(True, margin=self.footer_height + 12)

    def paragraph(self, value: str, *, size: float | None = None, bold: bool = False,
                  measure: bool = False) -> float:
        self.set_font('Recipe', 'B' if bold else '', size or self.body_size)
        self.set_text_color(*(self.primary if bold else self.ink))
        font = cast(TTFFont, self.current_font)
        if any(char != '\n' and ord(char) not in font.cmap for char in value):
            raise RecipePdfError('Ein Zeichen dieser Rezeptrevision wird von der Druckschrift nicht unterstützt.')
        height = max(self.leading, self.font_size * 1.35,
                     self.font_size * (font.desc.ascent - font.desc.descent) / 1000 + 0.2)
        return cast(float, self.multi_cell(self.epw, height, value, align='L', new_x='LMARGIN', new_y='NEXT',
                                          dry_run=measure, output='HEIGHT'))

    def heading(self, value: str, *, title: bool = False) -> None:
        size = 26.0 if title else 15.0
        if self.will_page_break(size * 1.35 + 2 * self.leading + 12):
            self.add_page()
        self.ln(10)
        self.paragraph(value, size=size, bold=True)
        self.ln(5)

    def photo(self, data: bytes, *, logo: bool = False) -> None:
        width, height = (110.0, 42.0) if logo else (self.epw, 180.0)
        if self.will_page_break(height + self.leading):
            self.add_page()
        self.image(BytesIO(data), x=self.l_margin, y=self.y, w=width, h=height, keep_aspect_ratio=True)
        self.ln(height + 8)

    def footer(self) -> None:
        self.set_y(-self.footer_height)
        if self.config['footer_text']:
            self.paragraph(self.config['footer_text'])
            self.ln(3)
        self.paragraph(f'Seite {self.page_no()}')


def _provenance(pdf: _RecipeDocument, source: Mapping[str, Any], *, ingredient: bool = False) -> None:
    kind = source['source_kind' if ingredient else 'kind']
    pdf.paragraph(SOURCE_NAMES[kind])
    fields = (('source_reference' if ingredient else 'reference', 'Beleg'),
              ('fetched_at', 'Erfasst am')) if ingredient else (
                  ('reference', 'Beleg'), ('url', 'Quelle'), ('note', 'Hinweis'), ('fetched_at', 'Erfasst am'))
    for field, label in fields:
        if source[field] is not None:
            pdf.paragraph(f'{label}: {source[field]}')


def _render(revision: RecipeRevisionDTO, recipe: Mapping[str, Any], *, config: PrintTemplateConfig,
            images: dict[str, bytes], target: str | None, branding: PdfBranding | None) -> bytes:
    scaled = scaled_recipe(recipe, target)
    pdf = _RecipeDocument(config, branding)
    pdf.set_title(recipe['title'])
    pdf.set_creator('Dishboard · fpdf2')
    identity = f'Rezeptrevision {revision.public_id} · SHA-256 {revision.content_hash_sha256}'
    if branding:
        identity += f' · Markenrevision {branding.revision_id}'
    pdf.set_subject(identity)
    if config['logo'] != 'none':
        logo = branding.logo_png if branding and config['logo'] == 'active_brand' else None
        if logo is None:
            logo = (ASSETS / 'img' / LOGOS['print' if config['logo'] == 'active_brand' else config['logo']]).read_bytes()
        pdf.photo(logo, logo=True)
    if config['header_text']:
        pdf.paragraph(config['header_text'])
    pdf.heading(recipe['title'], title=True)
    pdf.paragraph(f'Revision {revision.revision_number}')
    pdf.paragraph(f'Original: {scaled["source"]} {scaled["unit"]} · Gewünscht: {scaled["target"]} {scaled["unit"]}')
    for field, label in (('prep_minutes', 'Vorbereitung'), ('cook_minutes', 'Zubereitung')):
        if recipe[field] is not None:
            pdf.paragraph(f'{label}: {recipe[field]} Min.')
    if recipe['description'] is not None:
        pdf.ln(8)
        pdf.paragraph(recipe['description'])
    pdf.ln(8)
    pdf.paragraph(UNKNOWN_ALLERGENS)
    for photo in recipe['images']:
        pdf.ln(10)
        pdf.photo(images[photo['sha256']])
        for field, label in (('caption', ''), ('source_url', 'Bildquelle: '),
                             ('source_license', 'Lizenz: '), ('fetched_at', 'Erfasst am: ')):
            if photo[field] is not None:
                pdf.paragraph(label + photo[field])
    pdf.heading('Zutaten')
    previous_group = None
    for row in scaled['rows']:
        ingredient = row['ingredient']
        if ingredient['group_label'] != previous_group and ingredient['group_label'] is not None:
            pdf.heading(ingredient['group_label'])
        previous_group = ingredient['group_label']
        amount = f'{row["scaled"]} {row["unit"]} · ' if row['scaled'] is not None else ''
        pdf.paragraph(amount + ingredient['ingredient_text'])
        if ingredient['note'] is not None:
            pdf.paragraph(ingredient['note'])
        pdf.ln(7)
    pdf.heading('Zubereitung')
    for number, step in enumerate(recipe['steps'], 1):
        label = f'Schritt {number}'
        if step['duration_minutes'] is not None:
            label += f' · {step["duration_minutes"]} Min.'
        pdf.heading(label)
        pdf.paragraph(step['instruction'])
        if step['image_sha256'] is not None:
            pdf.ln(8)
            pdf.photo(images[step['image_sha256']])
    pdf.heading('Quelle und Herkunft')
    _provenance(pdf, recipe['source'])
    for number, ingredient in enumerate(recipe['ingredients'], 1):
        if ingredient['source_kind'] != 'manual' or any(ingredient[field] is not None for field in ('source_reference', 'fetched_at')):
            pdf.heading(f'Zutat {number} · {ingredient["ingredient_text"]}')
            _provenance(pdf, ingredient, ingredient=True)
    return bytes(pdf.output())


def render_recipe_pdf(revision: RecipeRevisionDTO, *, config: PrintTemplateConfig,
                      images: Mapping[str, RecipeAssetDTO], target: str | None = None,
                      branding: PdfBranding | None = None) -> bytes:
    """Render all selected recipe contents, or fail before returning any bytes."""
    try:
        config = validate_config(config, 'recipe')
        inherits = any(config.get(field) == 'active_brand' for field in ('palette', 'font', 'logo'))
        if inherits and branding is None:
            raise RecipeConfigurationError('Die aktive Marke muss vor dem Rezeptdruck geladen werden.')
        if not inherits:
            branding = None
        if branding is not None:
            positive(branding.revision_id)
            if config['palette'] == 'active_brand':
                _readable_brand(branding)
        recipe = _selected_recipe(revision)
        selected = _selected_images(recipe, images)
        return _render(revision, recipe, config=config, images=selected, target=target, branding=branding)
    except (PrintTemplateValidationError, RecipeValidationError, FormError, KeyError, TypeError, AttributeError):
        raise RecipeConfigurationError('Gespeicherte Rezeptdaten oder Druckeinstellungen sind ungültig.') from None
    except (FPDFException, OSError, ValueError) as error:
        if isinstance(error, (RecipePdfError, RecipeConfigurationError)):
            raise
        raise RecipePdfError('Die Rezeptrevision kann nicht vollständig als PDF ausgegeben werden.') from None
