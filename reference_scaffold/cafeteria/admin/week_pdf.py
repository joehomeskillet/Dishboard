"""Measured, single-page PDFs of a saved week; no publication or live data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from fpdf import FPDF
from fpdf.fonts import TTFFont

from ..food_symbols import food_legend
from ..print_branding import PdfBranding
from ..print_template_config import PrintTemplateValidationError, default_config, validate_config
from .rendering import DAY_NAMES, MONTHS
from .week_pdf_symbols import (
    ICON_GAP, ICON_HEIGHT, SymbolMark, draw_symbol, draw_symbols, legend_text,
    measure_symbols, origin_text, symbol_mark,
)

ASSETS = Path(__file__).resolve().parents[1] / 'static'
# Print tokens sampled from the supplied Südhang PDF (independent of admin CSS).
BLUE = (0, 82, 147)
FILL = (222, 234, 246)
BORDER = (174, 170, 170)
INK = (0, 0, 0)
DATE_BLUE = (0, 112, 136)
DATE_FILL = (242, 242, 242)
LEFT = 21.0
PAD = 4.0
# Approved print counterparts of the existing Südhang color tokens.
PALETTES = {
    'reference': (BLUE, FILL),
    'brand': ((140, 28, 75), (246, 231, 238)),
    'teal': ((53, 102, 111), (220, 237, 240)),
}
LOGOS = {'print': 'weekly-print-logo.jpg', 'wordmark': 'suedhang-logo@2x.png'}


class WeekPdfFitError(ValueError):
    """The complete saved content cannot fit at a readable size on one A4 page."""


@dataclass
class Block:
    lines: list[str]
    size: float
    bold: bool = False
    leading: float = 1.0

    @property
    def height(self) -> float:
        return len(self.lines) * (self.size + self.leading)


@dataclass
class MenuCell:
    paragraphs: tuple[str, str, str]
    option: dict[str, Any] | None = None


def _wrap(pdf: FPDF, text: str, width: float, size: float, bold: bool = False,
          leading: float = 1.0) -> Block:
    pdf.set_font('Weekly', 'B' if bold else '', size)
    text = ' '.join(text.split())
    font = cast(TTFFont, pdf.current_font)
    leading = max(leading, size * (font.desc.ascent - font.desc.descent) / 1000 - size + 0.2)
    if any(ord(char) not in font.cmap for char in text):
        raise WeekPdfFitError(
            'Der gespeicherte Text enthält ein Zeichen, das die Druckschrift nicht unterstützt. '
            'Bitte Sonderzeichen (zum Beispiel Emoji) durch ausgeschriebene Wörter ersetzen, '
            'speichern und das PDF erneut öffnen.'
        )
    lines = cast(list[str], pdf.multi_cell(
        width, size + leading, text, dry_run=True, output='LINES', align='L',
    ))
    return Block(lines, size, bold, leading)


def _draw(pdf: FPDF, block: Block, x: float, y: float) -> float:
    pdf.set_font('Weekly', 'B' if block.bold else '', block.size)
    font = cast(TTFFont, pdf.current_font)
    line_height = max(block.size + block.leading, block.size * (font.desc.ascent - font.desc.descent) / 1000 + 0.2)
    for line in block.lines:
        # Explicit baselines, identical to preflight: no auto page break or clipping.
        pdf.text(x, y + block.size, line)
        y += line_height
    return y


def _price(value: object) -> str:
    return f'{value / 100:.2f} CHF' if isinstance(value, int) else 'nicht erfasst'


def _common_prices(draft: dict[str, Any], patient: bool) -> tuple[Any, Any] | None:
    if patient:
        return None
    pairs = {
        (option.get('internal_rappen'), option.get('external_rappen'))
        for day in draft['days'] for service in day['services']
        if service['service_state'] == 'open'
        for option in service['options'] if option['title']
    }
    return next(iter(pairs)) if len(pairs) == 1 else None


def _paragraphs(option: dict[str, Any], individual_prices: bool) -> tuple[str, str, str]:
    title = str(option.get('title') or '')
    if not title:
        return 'Menü noch nicht erfasst', '', ''
    components = ' · '.join(option.get('components') or [])
    details = [str(option.get(key) or '') for key in ('description', 'note')]
    details.extend(label['name'] for label in option.get('labels', []))
    details.extend(origin_text(origin) for origin in option.get('origins', []))
    allergens = option.get('allergens') or []
    for presence, label in (('contains', 'Enthält'), ('may_contain', 'Kann enthalten')):
        names = [item['name'] for item in allergens if item['presence'] == presence]
        if names:
            details.append(f'{label}: {", ".join(names)}')
    if not allergens:
        details.append('Allergenangaben nicht erfasst')
    elif option.get('allergen_review_status') != 'checked':
        details.append('Allergenprüfung offen')
    if individual_prices:
        details.append(f'Intern: {_price(option.get("internal_rappen"))} · Extern: {_price(option.get("external_rappen"))}')
    return title, components, ' · '.join(part for part in details if part)


def _rows(draft: dict[str, Any], patient: bool, week: date, prices: bool) -> list[list[MenuCell]]:
    days = {str(day['date']): day for day in draft['days']}
    rows = []
    for offset in range(7 if patient else 5):
        day = days.get((week + timedelta(days=offset)).isoformat(), {})
        services = {service['meal_code']: service for service in day.get('services', [])}
        row = []
        for meal in (('LUNCH', 'DINNER') if patient else ('LUNCH',)):
            service = services.get(meal, {})
            options = {option['type_code']: option for option in service.get('options', [])}
            for index, code in enumerate(('MENU_1', 'VEGGIE')):
                if service and service['service_state'] != 'open':
                    row.append(MenuCell((str(service.get('notice') or 'Kein Angebot') if index == 0 else '', '', '')))
                else:
                    option = options.get(code, {})
                    row.append(MenuCell(_paragraphs(option, prices), option if option.get('title') else None))
        rows.append(row)
    return rows


def _legend(pdf: FPDF, content: list[list[MenuCell]], width: float, patient: bool) -> tuple[
    Block, list[list[tuple[Block, SymbolMark | None]]], list[float], float,
]:
    legend = food_legend(cell.option for row in content for cell in row if cell.option is not None)
    columns = 4 if patient else 3
    cell_width = width / columns
    items: list[tuple[Block, SymbolMark | None]] = []
    for entry in legend.entries:
        mark = symbol_mark(entry)
        text_width = cell_width - 2 * PAD - (mark.width + ICON_GAP if mark else 0)
        items.append((_wrap(pdf, legend_text(entry), text_width, 8.5), mark))
    for flag, text in ((legend.allergens_unknown, 'Allergenangaben nicht erfasst'),
                       (legend.review_open, 'Allergenprüfung offen')):
        if flag:
            items.append((_wrap(pdf, text, cell_width - 2 * PAD, 8.5), None))
    rows = [items[index:index + columns] for index in range(0, len(items), columns)]
    heights = [max(max(block.height, ICON_HEIGHT if mark else 0) for block, mark in row) + PAD
               for row in rows]
    heading = _wrap(pdf, 'Legende der gedruckten Menüs', width - 2 * PAD, 9, True)
    return heading, rows, heights, cell_width


def _date_label(week: date, patient: bool) -> str:
    end = week + timedelta(days=6 if patient else 4)
    start = f'{week.day:02d}.'
    if week.month != end.month or week.year != end.year:
        start += f' {MONTHS[week.month - 1]} {week.year}'
    return f'{start} bis {end.day:02d}. {MONTHS[end.month - 1]} {end.year}'


def _notes(draft: dict[str, Any]) -> str:
    state = {'draft': 'Entwurf', 'ready': 'Bereit', 'published': 'Publiziert', 'archived': 'Archiviert'}
    return ' · '.join(str(part) for part in (
        draft.get('title'), draft.get('shared_note'),
        f'Zuletzt gespeicherter Stand: {state[draft["workflow_state"]]}',
        'Allergene und Herkunft beim Menü. Offene Angaben vor Abgabe prüfen.',
    ) if part)


def render_week_pdf(
    draft: dict[str, Any], profile: str, week: date, config: dict[str, str] | None = None,
    *, branding: PdfBranding | None = None,
) -> bytes:
    """Render all saved declarations, or raise an actionable fit error before output."""
    config = validate_config(default_config() if config is None else config, profile)
    inherits = any(config[field] == 'active_brand' for field in ('palette', 'font', 'logo'))
    if inherits and branding is None:
        raise PrintTemplateValidationError('Die aktive Marke muss vor dem PDF-Druck geladen werden.')
    if not inherits:
        branding = None
    brand_palette = branding is not None and config['palette'] == 'active_brand'
    patient = profile == 'patient'
    margin = {'standard': LEFT, 'wide': 28.0, 'wider': 36.0}[config['margin']]
    blue, fill = (branding.primary, branding.surface) if brand_palette and branding else PALETTES[config['palette']]
    ink = branding.text if brand_palette and branding else INK
    body_font = branding.font_body if branding and config['font'] == 'active_brand' else config['font']
    heading_font = branding.font_heading if branding and config['font'] == 'active_brand' else config['font']
    pdf = FPDF(orientation='L' if patient else 'P', unit='pt', format='A4')
    # Canonical export metadata makes identical saved content/config byte-stable.
    # Actual save times belong to the explicit template revision history.
    pdf.set_creation_date(datetime(1970, 1, 1, tzinfo=timezone.utc))
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)
    pdf.c_margin = 0
    for style, suffix in (('', ''), ('B', '-bold')):
        font = heading_font if style else body_font
        pdf.add_font('Weekly', style, ASSETS / 'fonts' / f'weekly-print-{font}{suffix}.ttf')
    pdf.add_page()
    pdf.set_title('Wochenangebot Patienten' if patient else 'Wochenangebot Cafeteria')
    pdf.set_creator('Dishboard · fpdf2')
    if branding:
        pdf.set_subject(f'Dishboard Markenrevision {branding.revision_id}')
    width = pdf.w - 2 * margin
    day_width = 60.0 if patient else 104.0
    padding = 2.0 if patient else PAD
    if config['spacing'] == 'roomy':
        padding += 1.5
    cell_width = (width - day_width) / (4 if patient else 2)
    table_y, header_h, bottom = (52.0, 26.0, 580.0) if patient else (203.0, 31.0, 714.0)
    custom_header = _wrap(pdf, config['header_text'], width, 11, True) if config['header_text'] else None
    custom_y = table_y
    if custom_header:
        table_y += custom_header.height + 2 * padding
    common_prices = _common_prices(draft, patient)
    content = _rows(draft, patient, week, not patient and common_prices is None)
    legend_heading, legend_rows, legend_heights, legend_width = _legend(pdf, content, width, patient)
    legend_height = legend_heading.height + sum(legend_heights) + 2 * PAD if legend_rows else 0.0
    symbols = [[measure_symbols(cell.option, cell_width - 2 * padding) for cell in row] for row in content]
    if patient:
        for content_row in content:
            for content_cell in content_row:
                title, components, details = content_cell.paragraphs
                content_cell.paragraphs = (title, '', ' · '.join(part for part in (components, details) if part))
    candidates: tuple[tuple[float, float], ...] = ((9.0, 9.0), (8.5, 8.5)) if patient else ((12.0, 10.0), (11.0, 9.0), (10.0, 8.5))
    if config['text_size'] == 'standard':
        candidates = ((9.0, 9.0),) if patient else ((12.0, 10.0),)
    elif config['text_size'] == 'large':
        candidates = ((10.0, 10.0),) if patient else ((14.0, 12.0),)
    for body_size, detail_size in candidates:
        rows = [
                [[_wrap(pdf, text, cell_width - 2 * padding, body_size if i < 2 else detail_size,
                        i == 0, 0.5 if patient else 1.0)
              for i, text in enumerate(cell.paragraphs) if text] for cell in row]
            for row in content
        ]
        heights = [max(sum(block.height for block in cell) + strip.height
                       for cell, strip in zip(row, strips, strict=True)) + 2 * padding
                   for row, strips in zip(rows, symbols, strict=True)]
        notes_text = ' · '.join(part for part in (_notes(draft), config['footer_text']) if part)
        notes = _wrap(pdf, notes_text, width - 2 * PAD, 8.5 if patient else 10)
        available = bottom - table_y - header_h - notes.height - 2 * PAD - legend_height
        if sum(heights) <= available:
            break
    else:
        raise WeekPdfFitError(
            'Diese gespeicherte Woche passt nicht vollständig und lesbar auf eine A4-Seite. '
            'Bitte lange Beschreibungen oder Notizen in der Wochenbearbeitung kürzen, '
            'ohne erforderliche Allergen- und Herkunftsangaben zu entfernen, speichern und das PDF erneut öffnen.'
        )
    # Give spare space to the day rows, preserving all measured content heights.
    extra = (available - sum(heights)) / len(heights)
    heights = [height + extra for height in heights]
    if brand_palette:
        pdf.set_fill_color(*fill)
        pdf.rect(0, 0, pdf.w, pdf.h, style='F')
    pdf.set_text_color(*blue)
    if patient:
        _draw(pdf, Block(['Wochenangebot Patienten'], 19, True), margin, 15)
        _draw(pdf, Block([_date_label(week, True)], 11), margin, 37)
        if config['logo'] == 'active_brand':
            logo = BytesIO(branding.logo_png) if branding and branding.logo_png else ASSETS / 'img' / LOGOS['print']
            pdf.image(logo, pdf.w - margin - 145, 17, w=145, h=24, keep_aspect_ratio=True)
        elif config['logo'] != 'none':
            pdf.image(ASSETS / 'img' / LOGOS[config['logo']], pdf.w - margin - 145, 17, w=145)
    else:
        if branding:
            # The old raster contains an embedded Südhang brand: never combine it with an inherited brand.
            _draw(pdf, Block(['WOCHENANGEBOT'], 27, True), margin, 50)
            _draw(pdf, Block(['CAFETERIA'], 18, True), margin, 85)
        else:
            pdf.image(ASSETS / 'img/weekly-print-header.jpg', 0, 0, w=pdf.w, h=201.96)
        date_block = _wrap(pdf, _date_label(week, False), width, 17)
        # Reference strip geometry; longer month-crossing dates extend it left.
        strip_width = max(250.44, pdf.get_string_width(date_block.lines[0]) + 15.12)
        strip_x = 572.28 - strip_width
        pdf.set_fill_color(*(fill if brand_palette else DATE_FILL))
        pdf.rect(strip_x, 145.56, strip_width, 26.28, style='F')
        pdf.set_text_color(*(branding.accent if brand_palette and branding else DATE_BLUE))
        _draw(pdf, date_block, strip_x + 7.56, 148.84)
    pdf.set_text_color(*blue)
    if custom_header:
        _draw(pdf, custom_header, margin, custom_y + padding)
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*(branding.accent if brand_palette and branding else BORDER))
    pdf.set_line_width(0.55)
    pdf.rect(margin, table_y, width, header_h, style='DF')
    headings = ('Mittag · Menü 1', 'Mittag · Vegetarisch', 'Abend · Menü 1', 'Abend · Vegetarisch') if patient else ('MENÜ 1', 'VEGETARISCH')
    pdf.set_text_color(*blue)
    for index, heading in enumerate(headings):
        _draw(pdf, Block([heading], 11 if patient else 15, True), margin + day_width + index * cell_width + PAD, table_y + 7)
    y = table_y + header_h
    pdf.set_text_color(*ink)
    for offset, (row, height) in enumerate(zip(rows, heights, strict=True)):
        pdf.rect(margin, y, day_width, height)
        _draw(pdf, Block([DAY_NAMES[offset].upper()], 9 if patient else 15, True), margin + PAD, y + (height - 16) / 2)
        for index, cell in enumerate(row):
            x = margin + day_width + index * cell_width
            pdf.rect(x, y, cell_width, height)
            strip = symbols[offset][index]
            text_y = y + padding + (height - 2 * padding - sum(block.height for block in cell) - strip.height) / 2
            for block in cell:
                text_y = _draw(pdf, block, x + padding, text_y)
            if brand_palette and strip.height:
                with pdf.local_context(fill_color=(255, 255, 255)):
                    pdf.rect(x + padding, text_y, cell_width - 2 * padding, strip.height, style='F')
            draw_symbols(pdf, strip, x + padding, text_y)
        y += height
    pdf.rect(margin, y, width, notes.height + 2 * PAD)
    _draw(pdf, notes, margin + PAD, y + PAD)
    y += notes.height + 2 * PAD
    if legend_rows:
        pdf.rect(margin, y, width, legend_height)
        y = _draw(pdf, legend_heading, margin + PAD, y + PAD)
        for legend_row, height in zip(legend_rows, legend_heights, strict=True):
            for index, (block, mark) in enumerate(legend_row):
                x = margin + index * legend_width + PAD
                if mark:
                    if brand_palette:
                        with pdf.local_context(fill_color=(255, 255, 255)):
                            pdf.rect(x, y, mark.width, ICON_HEIGHT, style='F')
                    draw_symbol(pdf, mark, x, y)
                    x += mark.width + ICON_GAP
                _draw(pdf, block, x, y)
            y += height
    if not patient:
        if config['logo'] == 'active_brand':
            logo = BytesIO(branding.logo_png) if branding and branding.logo_png else ASSETS / 'img' / LOGOS['print']
            pdf.image(logo, pdf.w - margin - 145, 720, w=145, h=28, keep_aspect_ratio=True)
        elif config['logo'] != 'none':
            pdf.image(ASSETS / 'img' / LOGOS[config['logo']], pdf.w - margin - 145, 720, w=145)
        pdf.rect(margin, 756, width, 39, style='DF')
        pdf.set_text_color(*blue)
        _draw(pdf, Block(['WOCHENANGEBOT CAFETERIA'], 14, True), margin + PAD, 768)
        price_text = [f'Intern: {_price(common_prices[0])}', f'Extern: {_price(common_prices[1])}'] if common_prices else ['Preise beim Menü in CHF']
        _draw(pdf, Block(price_text, 14, True), margin + width * 0.64, 759)
    return bytes(pdf.output())
