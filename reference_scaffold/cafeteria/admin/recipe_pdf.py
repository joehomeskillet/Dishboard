"""Native, deterministic A4 recipes from one immutable revision; no live reads."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from fpdf.errors import FPDFException

from ..branding_config import contrast, default_config as default_branding_config
from ..print_branding import PdfBranding
from ..print_template_config import PrintTemplateConfig, PrintTemplateValidationError, validate_config
from ..recipe_snapshots import image_payload
from ..recipe_snapshot_v2 import verified_prepared
from ..recipe_types import (
    RecipeAssetDTO, RecipeConfigurationError, RecipeRevisionDTO, RecipeValidationError,
)
from ..recipe_values import identifier, positive, recipe_payload
from .recipe_forms import FormError
from .recipe_document import build_recipe_document
from .recipe_pdf_layout import RECIPE_MARGINS as RECIPE_MARGINS
from .recipe_pdf_layout import RecipePdfError, RecipeSheet, SheetLine
from .week_pdf import ASSETS, LOGOS

def _readable_brand(branding: PdfBranding) -> None:
    # Paper is always white; primary appears only in large, bold headings.
    surface = default_branding_config()['surface']
    for color, minimum, label in ((branding.text, 4.5, 'Textfarbe'),
                                   (branding.primary, 3.0, 'Überschriftenfarbe')):
        if len(color) != 3 or any(type(channel) is not int or not 0 <= channel <= 255 for channel in color):
            raise RecipeConfigurationError('Die Druckfarben der aktiven Marke sind ungültig.')
        encoded = '#' + ''.join(f'{channel:02x}' for channel in color)
        if contrast(encoded, surface) < minimum:
            raise RecipeConfigurationError(
                f'Die {label} der aktiven Marke ist auf weissem Rezeptpapier nicht lesbar.')


def _selected_recipe(revision: RecipeRevisionDTO) -> Mapping[str, Any]:
    if (not isinstance(revision.snapshot, Mapping)
            or type(revision.snapshot.get('schema_version')) is not int
            or revision.snapshot['schema_version'] not in (1, 2)):
        raise RecipeConfigurationError('Diese Rezeptrevision wird vom PDF-Druck nicht unterstützt.')
    if revision.snapshot['schema_version'] == 2:
        verified_prepared(revision)
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


def _render(revision: RecipeRevisionDTO, recipe: Mapping[str, Any], *, config: PrintTemplateConfig,
            images: dict[str, bytes], target: str | None, branding: PdfBranding | None) -> bytes:
    document = build_recipe_document(recipe, target, revision=revision)
    pdf = RecipeSheet(config, branding)
    pdf.set_title(document['title'])
    pdf.set_creator('Dishboard · fpdf2')
    identity = f'Rezeptrevision {revision.public_id} · SHA-256 {revision.content_hash_sha256}'
    if branding:
        identity += f' · Markenrevision {branding.revision_id}'
    pdf.set_subject(identity)
    if config['logo'] != 'none':
        logo = branding.logo_png if branding and config['logo'] == 'active_brand' else None
        if config['logo'] != 'active_brand':
            logo = (ASSETS / 'img' / LOGOS[config['logo']]).read_bytes()
        if logo is not None:
            pdf.photo(logo, logo=True)
    if config['header_text']:
        pdf.paragraph(config['header_text'])
    _content(pdf, document, images)
    for prepared in document['prepared']:
        pdf.continuation = ''
        pdf.add_page()
        pdf.paragraph('Zubereitung für ' + prepared['for_ingredient'], icon='components')
        _content(pdf, prepared['document'], images,
                 details=prepared['use_number'] == prepared['first_use_number'])
    return bytes(pdf.output())


def _ingredient_lines(pdf: RecipeSheet, document: dict[str, Any], width: float) -> list[SheetLine]:
    lines = pdf.lines('Zutaten', width, bold=True, size=15, icon='components', keep_next=True)
    previous_group = None
    for row in document['ingredients']:
        if row['group_label'] is not None and row['group_label'] != previous_group:
            lines.extend(pdf.lines(row['group_label'], width, bold=True, keep_next=True))
        previous_group = row['group_label']
        label = row['text']
        if row['amount'] is not None:
            unit = ' ' + row['unit'] if row['unit'] is not None else ''
            label = f'{row["amount"]}{unit} · {label}'
        lines.extend(pdf.lines(label, width, keep_next=row['note'] is not None))
        if row['note'] is not None:
            lines.extend(pdf.lines(row['note'], width))
        if row['amount'] is None:
            lines.extend(pdf.lines('Menge nicht erfasst', width))
        if row['unit'] is None:
            lines.extend(pdf.lines('Einheit nicht erfasst', width))
        lines.append(SheetLine(height=7))
    if document['empty_ingredients']:
        lines.extend(pdf.lines(document['empty_ingredients'], width))
    return lines


def _step_lines(pdf: RecipeSheet, document: dict[str, Any], width: float,
                images: dict[str, bytes], details: bool) -> list[SheetLine]:
    lines = pdf.lines('Zubereitung', width, bold=True, size=15, icon='clipboard-check', keep_next=True)
    if not details:
        return lines + pdf.lines(
            'Arbeitsschritte, Bilder und Herkunft stehen bei der ersten Ausgabe dieser Zubereitung.', width)
    for step in document['steps']:
        label = f'Schritt {step["number"]}'
        if step['duration_minutes'] is not None:
            label += f' · {step["duration_minutes"]} Min.'
        lines.extend(pdf.lines(label, width, bold=True, keep_next=True))
        lines.extend(pdf.lines(step['instruction'], width))
        if step['image_sha256'] is not None:
            lines.append(SheetLine(height=168, photo=images[step['image_sha256']]))
        lines.append(SheetLine(height=10))
    if document['empty_steps']:
        lines.extend(pdf.lines(document['empty_steps'], width))
    return lines


def _source_uses(uses: list[str]) -> str:
    """Compact contiguous ingredient references without merging distinct origins."""
    labels = ['Rezept'] if 'recipe' in uses else []
    numbers = sorted(int(use.split(':')[1]) for use in uses if use != 'recipe')
    ranges: list[list[int]] = []
    for number in numbers:
        if ranges and ranges[-1][-1] == number - 1:
            ranges[-1].append(number)
        else:
            ranges.append([number])
    if numbers:
        label = 'Zutat ' if len(numbers) == 1 else 'Zutaten '
        labels.append(label + ', '.join(str(run[0]) if len(run) == 1 else f'{run[0]}–{run[-1]}' for run in ranges))
    return ' · '.join(labels)


def _provenance(pdf: RecipeSheet, document: dict[str, Any], shown_notes: set[str]) -> None:
    pdf.heading('Quelle und Herkunft', icon='info-circle')
    references: dict[tuple[str, str], int] = {}
    for number, record in enumerate(document['provenance'], 1):
        pdf.paragraph(f'Quelle {number} · {record["label"]} · ' + _source_uses(record['uses']), bold=True)
        for field, label in (('reference', 'Beleg'), ('url', 'Quelle'), ('note', 'Hinweis'),
                             ('fetched_at', 'Erfasst am')):
            value = record['source'][field]
            if value is None:
                continue
            if field == 'note' and value in shown_notes:
                pdf.paragraph('Hinweis: siehe Rezeptnotiz oben')
                continue
            key = (field, value)
            if field in ('reference', 'url') and key in references:
                pdf.paragraph(f'{label}: siehe Quelle {references[key]}')
            else:
                pdf.paragraph(f'{label}: {value}')
                references[key] = number
        pdf.ln(4)


def _content(pdf: RecipeSheet, document: dict[str, Any], images: dict[str, bytes], *, details: bool = True) -> None:
    pdf.heading(document['title'], title=True)
    version = document['identity']['revision_number']
    pdf.paragraph(f'Revision {version}', icon='history')
    pdf.continuation = document['title'] + f' · Revision {version}'
    quantity = document['yield']
    pdf.paragraph(f'Original: {quantity["original_amount"]} {quantity["unit"]} · '
                  f'Gewünscht: {quantity["amount"]} {quantity["unit"]}', icon='tools-kitchen-2')
    for field, label in (('prep_minutes', 'Vorbereitung'), ('cook_minutes', 'Zubereitung')):
        if document['times'][field] is not None:
            pdf.paragraph(f'{label}: {document["times"][field]} Min.', icon='history')
    if details and document['description'] is not None:
        pdf.ln(6)
        pdf.paragraph(document['description'])
    pdf.ln(6)
    for warning in document['warnings']:
        pdf.paragraph(warning['text'], bold=True, icon='alert-triangle')
    shown_notes = set()
    if details:
        for note in document['source_notes']:
            if note not in shown_notes:
                pdf.paragraph(note, icon='info-circle')
                shown_notes.add(note)
        for photo in document['images']:
            pdf.ln(8)
            pdf.photo(images[photo['sha256']])
            for field, label in (('caption', ''), ('source_url', 'Bildquelle: '),
                                 ('source_license', 'Lizenz: '), ('fetched_at', 'Erfasst am: ')):
                if photo[field] is not None:
                    pdf.paragraph(label + photo[field])
    pdf.ln(12)
    left, right = pdf.column_widths
    pdf.columns(_ingredient_lines(pdf, document, left), _step_lines(pdf, document, right, images, details))
    if details:
        _provenance(pdf, document, shown_notes)

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
        for child in revision.prepared_revisions:
            selected.update(_selected_images(cast(Mapping[str, Any], child.snapshot['recipe']), images))
        return _render(revision, recipe, config=config, images=selected, target=target, branding=branding)
    except (PrintTemplateValidationError, RecipeValidationError, FormError, KeyError, TypeError, AttributeError):
        raise RecipeConfigurationError('Gespeicherte Rezeptdaten oder Druckeinstellungen sind ungültig.') from None
    except (FPDFException, OSError, ValueError) as error:
        if isinstance(error, (RecipePdfError, RecipeConfigurationError)):
            raise
        raise RecipePdfError('Die Rezeptrevision kann nicht vollständig als PDF ausgegeben werden.') from None
