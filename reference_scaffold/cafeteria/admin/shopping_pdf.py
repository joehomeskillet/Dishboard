"""Native, deterministic A4 shopping list PDFs from one immutable revision; no live reads."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

from fpdf.errors import FPDFException

from ..print_branding import PdfBranding
from ..print_template_config import PrintTemplateConfig, validate_config
from ..recipe_types import RecipeConfigurationError, RecipeValidationError
from .recipe_pdf_layout import RecipePdfError, RecipeSheet
from .week_pdf import ASSETS, LOGOS

_ZURICH = ZoneInfo('Europe/Zurich')
_POLICY_LABELS = {'leaf': 'Blattbedarf', 'prepared': 'Vorbereiteter Bedarf'}


class ShoppingPdfError(ValueError):
    """A bounded, complete shopping list PDF could not be produced."""


def _text_or_raise(value: object, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ShoppingPdfError(message)
    return value


def _quantity_text(quantity: object, unit: object) -> str:
    """Show the frozen Decimal string as-is; only '.'->',' is a display substitution."""
    if quantity is None:
        return 'Menge unbekannt'
    if not isinstance(quantity, str):
        raise ShoppingPdfError('Eine Mengenangabe dieser Einkaufsliste ist ungültig.')
    display = quantity.replace('.', ',')
    return f'{display} {unit}' if isinstance(unit, str) and unit else display


def _computed_at_text(value: object) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ShoppingPdfError('Der Berechnungszeitpunkt dieser Revision ist ungültig.')
    return value.astimezone(_ZURICH).strftime('%d.%m.%Y %H:%M')


def _checkbox(pdf: RecipeSheet, top: float, height: float) -> None:
    size = pdf.body_size
    pdf.set_draw_color(*pdf.ink)
    pdf.set_line_width(0.7)
    pdf.rect(pdf.l_margin, top + (height - size) / 2, size, size)


def _item(pdf: RecipeSheet, row_text: str, *, checkbox: bool) -> None:
    """One shopping position: wraps freely, but never splits across a page break."""
    indent = pdf.body_size + 8 if checkbox else 0
    width = pdf.epw - indent
    wrapped = pdf.lines(row_text, width)
    if not wrapped:
        return
    if pdf.will_page_break(sum(line.height for line in wrapped)):
        pdf.add_page()
    top = pdf.y
    for line in wrapped:
        pdf.draw_line(line, pdf.l_margin + indent, pdf.y, width)
    if checkbox:
        _checkbox(pdf, top, wrapped[0].height)


def _line_label(line: Mapping[str, object]) -> str:
    name = line.get('food_name') or line.get('ingredient_text')
    if not isinstance(name, str) or not name:
        return 'Freitext'
    return name


def _revision_number(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ShoppingPdfError('Die Revisionsnummer dieser Einkaufsliste ist ungültig.')
    return value


def _line_row(line: Mapping[str, object]) -> str:
    quantity = _quantity_text(line.get('quantity'), line.get('unit_name') or line.get('unit_code'))
    return f'{quantity} · {_line_label(line)}'


def _incomplete_row(line: Mapping[str, object]) -> str:
    quantity = _quantity_text(line.get('quantity'), line.get('unit_name') or line.get('unit_code'))
    reason = line.get('reason')
    suffix = f' · Grund: {reason}' if isinstance(reason, str) and reason else ''
    return f'{quantity} · {_line_label(line)}{suffix}'


def _manual_row(item: Mapping[str, object]) -> str:
    quantity = _quantity_text(item.get('quantity'), item.get('unit_code'))
    label = item.get('item_text')
    if not isinstance(label, str) or not label:
        raise ShoppingPdfError('Eine manuelle Position dieser Einkaufsliste hat keinen Text.')
    return f'{quantity} · {label}'


def _section(pdf: RecipeSheet, title: str, rows: list[str], *, icon: str, checkbox: bool) -> None:
    if not rows:
        return
    indent = pdf.body_size + 8 if checkbox else 0
    first_wrapped = pdf.lines(rows[0], pdf.epw - indent)
    required = 4 * pdf.leading + sum(line.height for line in first_wrapped)
    if pdf.will_page_break(required):
        pdf.add_page()
    pdf.heading(title, icon=icon)
    for row in rows:
        _item(pdf, row, checkbox=checkbox)
        pdf.ln(4)


def _render(detail: Mapping[str, object], selected: Mapping[str, object], *,
            config: PrintTemplateConfig, branding: PdfBranding | None) -> bytes:
    title = _text_or_raise(detail.get('title'), 'Diese Einkaufsliste hat keinen Titel.')
    revision_id = _text_or_raise(selected.get('public_id'), 'Die Revision dieser Einkaufsliste ist ungültig.')
    policy = _POLICY_LABELS.get(cast(str, selected.get('policy')))
    if policy is None:
        raise ShoppingPdfError('Die Bedarfsart dieser Revision ist ungültig.')
    pdf = RecipeSheet(config, branding)
    pdf.set_title(title)
    pdf.set_creator('Dishboard · fpdf2')
    pdf.set_subject(f'Einkaufslistenrevision {revision_id}')
    if config['logo'] != 'none':
        logo = branding.logo_png if branding and config['logo'] == 'active_brand' else None
        if config['logo'] != 'active_brand':
            logo = (ASSETS / 'img' / LOGOS[config['logo']]).read_bytes()
        if logo is not None:
            pdf.photo(logo, logo=True)
    if config['header_text']:
        pdf.paragraph(config['header_text'])
    pdf.heading(title, title=True)
    pdf.paragraph(f'Beleg {_revision_number(selected.get("revision_number"))}', icon='file-check')
    pdf.paragraph(policy, icon='components')
    pdf.paragraph('Berechnet am ' + _computed_at_text(selected.get('computed_at')), icon='history')
    note = detail.get('note')
    if isinstance(note, str) and note:
        pdf.ln(4)
        pdf.paragraph(note, icon='info-circle')
    pdf.ln(8)
    lines = cast(list, selected.get('lines') or [])
    _section(pdf, 'Einkaufspositionen', [_line_row(cast(Mapping[str, object], line)) for line in lines],
             icon='salad', checkbox=True)
    incomplete = cast(list, selected.get('incomplete_lines') or [])
    _section(pdf, 'Unvollständige Mengen',
             [_incomplete_row(cast(Mapping[str, object], line)) for line in incomplete],
             icon='alert-triangle', checkbox=True)
    manual_items = cast(list, detail.get('manual_items') or [])
    _section(pdf, 'Manuelle Positionen',
             [_manual_row(cast(Mapping[str, object], item)) for item in manual_items],
             icon='plus', checkbox=True)
    return bytes(pdf.output())


def render_shopping_pdf(detail: Mapping[str, object], *, config: PrintTemplateConfig,
                        branding: PdfBranding | None = None) -> bytes:
    """Render one immutable, selected shopping list revision, or fail before returning any bytes."""
    config = validate_config(config, 'recipe')
    selected = detail.get('selected_revision')
    if not isinstance(selected, Mapping):
        raise ShoppingPdfError('Für diese Einkaufsliste ist keine Revision zum Drucken ausgewählt.')
    try:
        return _render(detail, selected, config=config, branding=branding)
    except ShoppingPdfError:
        raise
    except (RecipePdfError, RecipeConfigurationError, RecipeValidationError, FPDFException, OSError):
        raise ShoppingPdfError('Die Einkaufsliste kann nicht vollständig als PDF ausgegeben werden.') from None
