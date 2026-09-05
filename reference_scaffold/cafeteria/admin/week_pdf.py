"""Measured, single-page PDFs of a saved week; no publication or live data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from fpdf import FPDF
from fpdf.fonts import TTFFont

from .rendering import DAY_NAMES, MONTHS

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


class WeekPdfFitError(ValueError):
    """The complete saved content cannot fit at a readable size on one A4 page."""


@dataclass
class Block:
    lines: list[str]
    size: float
    bold: bool = False

    @property
    def height(self) -> float:
        return len(self.lines) * (self.size + 1)


def _wrap(pdf: FPDF, text: str, width: float, size: float, bold: bool = False) -> Block:
    pdf.set_font('Carlito', 'B' if bold else '', size)
    text = ' '.join(text.split())
    font = cast(TTFFont, pdf.current_font)
    if any(ord(char) not in font.cmap for char in text):
        raise WeekPdfFitError(
            'Der gespeicherte Text enthält ein Zeichen, das die Druckschrift nicht unterstützt. '
            'Bitte Sonderzeichen (zum Beispiel Emoji) durch ausgeschriebene Wörter ersetzen, '
            'speichern und das PDF erneut öffnen.'
        )
    lines = cast(list[str], pdf.multi_cell(
        width, size + 1, text, dry_run=True, output='LINES', align='L',
    ))
    return Block(lines, size, bold)


def _draw(pdf: FPDF, block: Block, x: float, y: float) -> float:
    pdf.set_font('Carlito', 'B' if block.bold else '', block.size)
    for line in block.lines:
        # Explicit baselines, identical to preflight: no auto page break or clipping.
        pdf.text(x, y + block.size, line)
        y += block.size + 1
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
    details.extend(origin['text'] for origin in option.get('origins', []))
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


def _rows(draft: dict[str, Any], patient: bool, week: date, prices: bool) -> list[list[tuple[str, str, str]]]:
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
                    row.append((str(service.get('notice') or 'Kein Angebot') if index == 0 else '', '', ''))
                else:
                    row.append(_paragraphs(options.get(code, {}), prices))
        rows.append(row)
    return rows


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


def render_week_pdf(draft: dict[str, Any], profile: str, week: date) -> bytes:
    """Render all saved declarations, or raise an actionable fit error before output."""
    patient = profile == 'patient'
    pdf = FPDF(orientation='L' if patient else 'P', unit='pt', format='A4')
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)
    pdf.c_margin = 0
    for style, suffix in (('', ''), ('B', '-bold')):
        pdf.add_font('Carlito', style, ASSETS / 'fonts' / f'weekly-print-carlito{suffix}.ttf')
    pdf.add_page()
    pdf.set_title('Wochenangebot Patienten' if patient else 'Wochenangebot Cafeteria')
    pdf.set_creator('Dishboard · fpdf2')
    width = pdf.w - 2 * LEFT
    day_width = 60.0 if patient else 104.0
    padding = 2.5 if patient else PAD
    cell_width = (width - day_width) / (4 if patient else 2)
    table_y, header_h, bottom = (52.0, 26.0, 580.0) if patient else (203.0, 31.0, 714.0)
    common_prices = _common_prices(draft, patient)
    content = _rows(draft, patient, week, not patient and common_prices is None)
    if patient:
        content = [[(title, '', ' · '.join(part for part in (components, details) if part))
                    for title, components, details in row] for row in content]
    candidates = ((9.0, 9.0), (8.5, 8.5)) if patient else ((12.0, 10.0), (11.0, 9.0), (10.0, 8.5))
    for body_size, detail_size in candidates:
        rows = [
                [[_wrap(pdf, text, cell_width - 2 * padding, body_size if i < 2 else detail_size, i == 0)
              for i, text in enumerate(cell) if text] for cell in row]
            for row in content
        ]
        heights = [max(sum(block.height for block in cell) for cell in row) + 2 * padding for row in rows]
        notes = _wrap(pdf, _notes(draft), width - 2 * PAD, 8.5 if patient else 10)
        available = bottom - table_y - header_h - notes.height - 2 * PAD
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
    pdf.set_text_color(*BLUE)
    if patient:
        _draw(pdf, Block(['Wochenangebot Patienten'], 19, True), LEFT, 15)
        _draw(pdf, Block([_date_label(week, True)], 11), LEFT, 37)
        pdf.image(ASSETS / 'img/weekly-print-logo.jpg', pdf.w - LEFT - 145, 17, w=145)
    else:
        pdf.image(ASSETS / 'img/weekly-print-header.jpg', 0, 0, w=pdf.w, h=201.96)
        date_block = _wrap(pdf, _date_label(week, False), width, 17)
        # Reference strip geometry; longer month-crossing dates extend it left.
        strip_width = max(250.44, pdf.get_string_width(date_block.lines[0]) + 15.12)
        strip_x = 572.28 - strip_width
        pdf.set_fill_color(*DATE_FILL)
        pdf.rect(strip_x, 145.56, strip_width, 26.28, style='F')
        pdf.set_text_color(*DATE_BLUE)
        _draw(pdf, date_block, strip_x + 7.56, 148.84)
    pdf.set_fill_color(*FILL)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.55)
    pdf.rect(LEFT, table_y, width, header_h, style='DF')
    headings = ('Mittag · Menü 1', 'Mittag · Vegetarisch', 'Abend · Menü 1', 'Abend · Vegetarisch') if patient else ('MENÜ 1', 'VEGETARISCH')
    pdf.set_text_color(*BLUE)
    for index, heading in enumerate(headings):
        _draw(pdf, Block([heading], 11 if patient else 15, True), LEFT + day_width + index * cell_width + PAD, table_y + 7)
    y = table_y + header_h
    pdf.set_text_color(*INK)
    for offset, (row, height) in enumerate(zip(rows, heights, strict=True)):
        pdf.rect(LEFT, y, day_width, height)
        _draw(pdf, Block([DAY_NAMES[offset].upper()], 9 if patient else 15, True), LEFT + PAD, y + (height - 16) / 2)
        for index, cell in enumerate(row):
            x = LEFT + day_width + index * cell_width
            pdf.rect(x, y, cell_width, height)
            text_y = y + padding + (height - 2 * padding - sum(block.height for block in cell)) / 2
            for block in cell:
                text_y = _draw(pdf, block, x + padding, text_y)
        y += height
    pdf.rect(LEFT, y, width, notes.height + 2 * PAD)
    _draw(pdf, notes, LEFT + PAD, y + PAD)
    if not patient:
        pdf.image(ASSETS / 'img/weekly-print-logo.jpg', pdf.w - LEFT - 145, 720, w=145)
        pdf.rect(LEFT, 756, width, 39, style='DF')
        pdf.set_text_color(*BLUE)
        _draw(pdf, Block(['WOCHENANGEBOT CAFETERIA'], 14, True), LEFT + PAD, 768)
        price_text = [f'Intern: {_price(common_prices[0])}', f'Extern: {_price(common_prices[1])}'] if common_prices else ['Preise beim Menü in CHF']
        _draw(pdf, Block(price_text, 14, True), LEFT + width * 0.64, 759)
    return bytes(pdf.output())
