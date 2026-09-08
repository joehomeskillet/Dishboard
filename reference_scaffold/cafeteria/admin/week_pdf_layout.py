"""Bounded native layouts of the complete saved week; preflight before PDF output."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.fonts import TTFFont

from ..menu_images import menu_image
from ..print_branding import PdfBranding
from ..print_template_config import LAYOUT_LABELS, PrintTemplateConfig, PrintTemplateValidationError, WeekPdfLayout
from .rendering import DAY_NAMES
from .week_pdf import (
    ASSETS, BORDER, INK, LOGOS, PALETTES, Block, WeekPdfFitError, _date_label,
    _day_offsets, _legend, _notes, _price, _rows, _time_labels, _wrap,
)
from .week_pdf_symbols import ICON_GAP, ICON_HEIGHT, SymbolStrip, draw_symbol, draw_symbols, measure_symbols, origin_text

GAP = 5.0
PHOTO_LEADING_GAP = 2.0
STUB_WIDTH = {'compact': 58.0, 'standard': 76.0, 'wide': 96.0}
ROW_PAD = {'compact': 1.5, 'standard': 3.0, 'roomy': 5.0}


@dataclass
class Field:
    name: str
    x: float
    y: float
    width: float
    height: float
    block: Block | None = None
    image: Path | None = None
    symbols: SymbolStrip | None = None


def local_photo(option: dict[str, Any]) -> Path | None:
    filename = menu_image(option)
    if not filename:
        return None
    path = (ASSETS / filename).resolve()
    if not path.is_relative_to((ASSETS / 'img/menus').resolve()) or not path.is_file():
        raise WeekPdfFitError('Das lokale Menübild ist nicht verfügbar. Bitte die Bildzuordnung prüfen.')
    return path


def binding_text(option: dict[str, Any], name: str) -> str:
    if name == 'title':
        return str(option.get('title') or 'Menü noch nicht erfasst')
    if not option.get('title'):
        return ''
    if name == 'components':
        return ' · '.join(str(part) for part in (
            ' · '.join(option.get('components') or []), option.get('description'), option.get('note'),
        ) if part)
    if name == 'origins':
        return ' · '.join(origin_text(item) for item in option.get('origins', []))
    if name == 'labels':
        return ' · '.join(item['name'] for item in option.get('labels', []))
    if name == 'prices':
        return f'Intern: {_price(option.get("internal_rappen"))} · Extern: {_price(option.get("external_rappen"))}'
    if name == 'allergens':
        allergens = option.get('allergens') or []
        parts = [f'{label}: {", ".join(item["name"] for item in allergens if item.get("presence") == presence)}'
                 for presence, label in (('contains', 'Enthält'), ('may_contain', 'Kann enthalten'))
                 if any(item.get('presence') == presence for item in allergens)]
        parts.extend(f'Allergenangabe ungeklärt: {item["name"]}' for item in allergens
                     if item.get('presence') not in ('contains', 'may_contain'))
        if not allergens:
            parts.append('Allergenangaben nicht erfasst')
        elif option.get('allergen_review_status') != 'checked':
            parts.append('Allergenprüfung offen')
        return ' · '.join(parts)
    return ''


def _menu_text(pdf: FPDF, text: str, width: float, size: float, bold: bool) -> Block:
    block = _wrap(pdf, text, width, size, bold)
    words = set(text.split())
    # Prefer a real compound boundary over an isolated final letter in narrow columns.
    for index in range(len(block.lines) - 1):
        left, right = block.lines[index], block.lines[index + 1]
        last, first = left.split()[-1], right.split()[0]
        if '-' in last and not last.endswith('-') and last + first in words:
            prefix, suffix = left.rsplit('-', 1)
            if pdf.get_string_width(suffix + right) <= width:
                block.lines[index:index + 2] = [prefix + '-', suffix + right]
    return block


def _block_height(pdf: FPDF, block: Block) -> float:
    # The last baseline has descenders below it; reserve their actual font bounds
    # even when the next field is an image rather than another line of text.
    font = pdf.current_font
    if not isinstance(font, TTFFont):
        raise WeekPdfFitError('Die Druckschrift ist nicht verfügbar. Bitte die Schriftdateien prüfen.')
    descent = -font.desc.descent * block.size / 1000
    return block.height + max(0.0, descent - block.leading) + 0.2


def measure_menu(pdf: FPDF, option: dict[str, Any], layout: WeekPdfLayout, width: float,
                 size: float, context: str) -> list[Field]:
    fields: list[Field] = []
    y = 0.0
    for name in layout['menu_fields']:
        try:
            if name == 'image':
                image = local_photo(option) if layout['photo'] != 'none' and option.get('title') else None
                if image:
                    if fields:
                        y += PHOTO_LEADING_GAP
                    image_width = min(width, 48.0 if layout['photo'] == 'small' else 72.0)
                    height = image_width * 0.75
                    x = (width - image_width) / 2 if layout['alignment'] == 'center' else 0.0
                    fields.append(Field(name, x, y, image_width, height, image=image))
                    y += height
                continue
            text = binding_text(option, name)
            subset = {key: option.get(key, []) if key == name else [] for key in ('labels', 'origins', 'allergens')}
            block = _menu_text(pdf, text, width, size, name == 'title') if text else None
            if block:
                height = _block_height(pdf, block)
                fields.append(Field(name, 0, y, width, height, block=block))
                y += height
            symbols = measure_symbols(subset, width) if option.get('title') else None
            if symbols and symbols.height:
                fields.append(Field(name, 0, y, width, symbols.height, symbols=symbols))
                y += symbols.height
        except WeekPdfFitError as error:
            raise WeekPdfFitError(f'{context} · {LAYOUT_LABELS[name]}: {error}') from error
    return fields


def fields_height(fields: list[Field]) -> float:
    return max((field.y + field.height for field in fields), default=0.0)


def draw_fields(pdf: FPDF, fields: list[Field], x: float, y: float, align: str) -> None:
    for field in fields:
        left, top = x + field.x, y + field.y
        if field.block:
            block = field.block
            pdf.set_font('Weekly', 'B' if block.bold else '', block.size)
            for line in block.lines:
                offset = (field.width - pdf.get_string_width(line)) / 2 if align == 'center' else 0
                pdf.text(left + offset, top + block.size, line)
                top += block.size + block.leading
        elif field.image:
            pdf.image(field.image, left, top, w=field.width, h=field.height, keep_aspect_ratio=True)
        elif field.symbols:
            with pdf.local_context(fill_color=(255, 255, 255)):
                pdf.rect(left, top, field.width, field.height, style='F')
            draw_symbols(pdf, field.symbols, left, top)


def _text(pdf: FPDF, text: str, width: float, size: float, name: str,
          *, bold: bool = False) -> Field:
    try:
        block = _wrap(pdf, text, width, size, bold)
    except WeekPdfFitError as error:
        raise WeekPdfFitError(f'{name}: {error}') from error
    return Field(name, 0, 0, width, _block_height(pdf, block), block=block)


def _header(pdf: FPDF, config: PrintTemplateConfig, title: str, week: date, last: int,
            width: float, branding: PdfBranding | None) -> list[Field]:
    fields: list[Field] = []
    x = y = row_height = 0.0
    for name in config['layout']['header']:
        if name == 'logo':
            if config['logo'] == 'none':
                continue
            filename = LOGOS.get(config['logo'], LOGOS['print'])
            field = Field(name, 0, 0, 100, 22, image=ASSETS / 'img' / filename)
        else:
            value = {'title': title, 'date_range': _date_label(week, last),
                     'week_number': f'KW {week.isocalendar().week}',
                     'header_note': config['header_text']}[name]
            if not value:
                continue
            size = 16.0 if name == 'title' else 10.0
            pdf.set_font('Weekly', 'B' if name == 'title' else '', size)
            field = _text(pdf, value, min(width, pdf.get_string_width(value) + 1),
                          size, f'Kopfbereich · {LAYOUT_LABELS[name]}', bold=name == 'title')
        if x and x + field.width > width:
            x, y, row_height = 0.0, y + row_height + GAP, 0.0
        field.x, field.y = x, y
        fields.append(field)
        row_height = max(row_height, field.height)
        x += field.width + 2 * GAP
    return fields


def _footer(pdf: FPDF, draft: dict[str, Any], config: PrintTemplateConfig, width: float,
            has_photos: bool) -> list[Field]:
    notes = [_notes(draft)]
    for day in draft['days']:
        for service in day['services']:
            if service.get('notice') and service.get('service_state') == 'open':
                meal = 'Mittag' if service['meal_code'] == 'LUNCH' else 'Abend'
                notes.append(f'{day["date"]} · {meal}: {service["notice"]}')
    if has_photos:
        notes.append('Menübilder: KI-generierte Serviervorschläge.')
    values = {'service_notes': ' · '.join(notes), 'footer_note': config['footer_text']}
    fields: list[Field] = []
    for name in config['layout']['footer']:
        if values[name]:
            field = _text(pdf, values[name], width, 8.5, f'Fussbereich · {LAYOUT_LABELS[name]}')
            field.y = fields_height(fields)
            fields.append(field)
    return fields


def _prepare_pdf(patient: bool, config: PrintTemplateConfig,
                 branding: PdfBranding | None) -> FPDF:
    pdf = FPDF(orientation='L' if patient else 'P', unit='pt', format='A4')
    pdf.set_creation_date(datetime(1970, 1, 1, tzinfo=timezone.utc))
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)
    pdf.c_margin = 0
    for style, suffix in (('', ''), ('B', '-bold')):
        font = (branding.font_heading if style else branding.font_body) if (
            branding and config['font'] == 'active_brand') else config['font']
        pdf.add_font('Weekly', style, ASSETS / 'fonts' / f'weekly-print-{font}{suffix}.ttf')
    pdf.add_page()
    pdf.set_creator('Dishboard · fpdf2')
    if branding:
        pdf.set_subject(f'Dishboard Markenrevision {branding.revision_id}')
    return pdf


def _check_fields(fields: list[Field], width: float, height: float, context: str) -> None:
    for field in fields:
        if field.x < 0 or field.y < 0 or field.x + field.width > width + 0.01 or field.y + field.height > height + 0.01:
            raise WeekPdfFitError(
                f'{context} · {LAYOUT_LABELS.get(field.name, field.name)}: passt nicht vollständig und lesbar auf eine A4-Seite. '
                'Bitte Abstände, Raster oder Textlängen anpassen; Pflichtangaben beibehalten.'
            )


def render_layout(draft: dict[str, Any], profile: str, week: date, config: PrintTemplateConfig,
                  *, branding: PdfBranding | None = None) -> bytes:
    inherits = any(config.get(field) == 'active_brand' for field in ('palette', 'font', 'logo'))
    if inherits and branding is None:
        raise PrintTemplateValidationError('Die aktive Marke muss vor dem PDF-Druck geladen werden.')
    if not inherits:
        branding = None
    patient, layout = profile == 'patient', config['layout']
    pdf = _prepare_pdf(patient, config, branding)
    margin = {'standard': 21.0, 'wide': 28.0, 'wider': 36.0}[config['margin']]
    width = pdf.w - 2 * margin
    blue, fill = (branding.primary, branding.surface) if branding and config['palette'] == 'active_brand' else PALETTES[config['palette']]
    ink = branding.text if branding and config['palette'] == 'active_brand' else INK
    offsets = _day_offsets(draft, patient, week)
    content = _rows(draft, patient, week, offsets, not patient)
    area = str(draft.get('area_name') or ('Patienten' if patient else 'Cafeteria'))
    title = f'Wochenangebot {area}'
    pdf.set_title(title)
    header = _header(pdf, config, title, week, offsets[-1], width, branding)
    header_h = fields_height(header)
    _check_fields(header, width, pdf.h - 2 * margin, 'Kopfbereich')
    headings = ['Mittag · Menü 1', 'Mittag · Vegetarisch', 'Abend · Menü 1', 'Abend · Vegetarisch'] if patient else ['Menü 1', 'Vegetarisch']
    day_labels = [' · '.join([DAY_NAMES[offset].upper(), (week + timedelta(days=offset)).strftime('%d.%m.'),
                             *_time_labels(draft, patient, week, offset)]) for offset in offsets]
    contexts = [[f'{week + timedelta(days=offset)} · {heading if patient else "Mittag · " + heading}'
                 for heading in headings] for offset in offsets]
    if layout['grid'] == 'days_columns':
        content = [list(row) for row in zip(*content, strict=True)]
        contexts = [list(row) for row in zip(*contexts, strict=True)]
        column_labels, row_labels = day_labels, headings
    else:
        column_labels, row_labels = headings, day_labels
    stub = STUB_WIDTH[layout['day_label_width']]
    cell_width = (width - stub) / len(column_labels)
    pad = ROW_PAD[layout['row_spacing']] + (1.5 if config['spacing'] == 'roomy' else 0)
    heading_fields = [_text(pdf, label, cell_width - 2 * pad, 9, 'Spaltenkopf', bold=True) for label in column_labels]
    heading_h = max(field.height for field in heading_fields) + 2 * pad
    row_fields = [_text(pdf, label, stub - 2 * pad, 8.5, f'Tag/Angebot · {label}', bold=True) for label in row_labels]
    legend_heading, legend_rows, legend_heights, legend_width = _legend(pdf, content, width, patient)
    legend_h = legend_heading.height + sum(legend_heights) + 8 if legend_rows else 0.0
    candidates = {'auto': (10.0, 9.0, 8.5), 'standard': (9.0,), 'large': (11.0,)}[config['text_size']]
    if patient and config['text_size'] == 'auto':
        candidates = (9.0, 8.5)
    fit_error: WeekPdfFitError | None = None
    for size in candidates:
        measured: list[list[list[Field]]] = []
        for row, context_row in zip(content, contexts, strict=True):
            cells = []
            for cell, context in zip(row, context_row, strict=True):
                option = cell.option
                if option is None:
                    cells.append([_text(pdf, cell.paragraphs[0], cell_width - 2 * pad, size, context)] if cell.paragraphs[0] else [])
                else:
                    cells.append(measure_menu(pdf, option, layout, cell_width - 2 * pad, size, context))
            measured.append(cells)
        has_photos = any(field.image for row in measured for cell in row for field in cell)
        footer = _footer(pdf, draft, config, width, has_photos)
        footer_h = fields_height(footer)
        available = pdf.h - 2 * margin - header_h - heading_h - legend_h - footer_h - 4 * GAP
        heights = [max(row_field.height, *(fields_height(cell) for cell in row)) + 2 * pad
                   for row, row_field in zip(measured, row_fields, strict=True)]
        if sum(heights) <= available:
            break
        largest_row = max(range(len(measured)), key=lambda index: heights[index])
        largest_cell = max(range(len(measured[largest_row])), key=lambda index: fields_height(measured[largest_row][index]))
        fields = measured[largest_row][largest_cell]
        field_name = max(fields, key=lambda item: item.height).name if fields else 'Tag/Angebot'
        fit_error = WeekPdfFitError(
            f'{contexts[largest_row][largest_cell]} · {LAYOUT_LABELS.get(field_name, field_name)}: Die vollständige Woche passt '
            'mit diesem Layout nicht lesbar auf eine A4-Seite. Bitte Raster, Bildgrösse oder '
            'Abstände ändern oder lange Texte kürzen; Pflichtangaben beibehalten.'
        )
    else:
        raise fit_error or WeekPdfFitError('Die vollständige Woche passt nicht auf eine A4-Seite.')
    _check_fields(footer, width, footer_h, 'Fussbereich')
    for measured_row, height, context_row in zip(measured, heights, contexts, strict=True):
        for measured_cell, context in zip(measured_row, context_row, strict=True):
            _check_fields(measured_cell, cell_width - 2 * pad, height - 2 * pad, context)
    # All sizes and bounds are fixed before the first visible mark is emitted.
    if branding and config['palette'] == 'active_brand':
        pdf.set_fill_color(*fill)
        pdf.rect(0, 0, pdf.w, pdf.h, style='F')
    pdf.set_text_color(*blue)
    for field in header:
        if field.name == 'logo' and config['logo'] == 'active_brand' and branding and branding.logo_png:
            pdf.image(BytesIO(branding.logo_png), margin + field.x, margin + field.y,
                      w=field.width, h=field.height, keep_aspect_ratio=True)
        else:
            draw_fields(pdf, [field], margin, margin, layout['alignment'])
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.4)
    y = margin + header_h + GAP

    def paint_legend(top: float) -> float:
        if not legend_rows:
            return top
        pdf.set_text_color(*ink)
        draw_fields(pdf, [Field('legend', 4, 4, width - 8, legend_heading.height, block=legend_heading)], margin, top, layout['alignment'])
        current = top + 4 + legend_heading.height
        for row, height in zip(legend_rows, legend_heights, strict=True):
            for index, (block, mark) in enumerate(row):
                x = margin + index * legend_width + 4
                if mark:
                    with pdf.local_context(fill_color=(255, 255, 255)):
                        pdf.rect(x, current, mark.width, ICON_HEIGHT, style='F')
                    draw_symbol(pdf, mark, x, current)
                    x += mark.width + ICON_GAP
                draw_fields(pdf, [Field('legend', 0, 0, legend_width - 8 - (mark.width + ICON_GAP if mark else 0), block.height, block=block)], x, current, layout['alignment'])
            current += height
        return top + legend_h + GAP

    if layout['legend_position'] == 'top':
        y = paint_legend(y)
    pdf.set_fill_color(*fill)
    pdf.rect(margin, y, width, heading_h, style='DF')
    pdf.set_text_color(*blue)
    for index, field in enumerate(heading_fields):
        draw_fields(pdf, [field], margin + stub + index * cell_width + pad, y + pad, layout['alignment'])
    y += heading_h
    pdf.set_text_color(*ink)
    for measured_row, height, label in zip(measured, heights, row_fields, strict=True):
        pdf.rect(margin, y, stub, height)
        draw_fields(pdf, [label], margin + pad, y + pad, layout['alignment'])
        for index, measured_cell in enumerate(measured_row):
            x = margin + stub + index * cell_width
            pdf.rect(x, y, cell_width, height)
            draw_fields(pdf, measured_cell, x + pad, y + pad, layout['alignment'])
        y += height
    y += GAP
    if layout['legend_position'] == 'bottom':
        y = paint_legend(y)
    draw_fields(pdf, footer, margin, y, layout['alignment'])
    return bytes(pdf.output())
