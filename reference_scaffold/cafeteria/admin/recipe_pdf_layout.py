"""Native recipe sheet primitives, with independently flowing A4 columns."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import cast
from xml.etree import ElementTree

from fpdf import FPDF
from fpdf.fonts import TTFFont

from ..print_branding import PdfBranding
from ..print_template_config import PrintTemplateConfig
from ..recipe_types import RecipeConfigurationError
from .week_pdf import ASSETS, INK, PALETTES

RECIPE_MARGINS = {'standard': 48.0, 'wide': 54.0, 'wider': 64.0}


class RecipePdfError(ValueError):
    """A bounded, complete recipe PDF could not be produced."""


@dataclass(frozen=True)
class SheetLine:
    text: str = ''
    height: float = 0
    size: float = 11
    bold: bool = False
    icon: str | None = None
    photo: bytes | None = None
    keep_next: bool = False


class RecipeSheet(FPDF):
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
        self.c_margin = 0
        self.continuation = ''
        self.footer_height = 36.0
        self.set_auto_page_break(True, margin=48)
        self.add_page()
        if config['footer_text']:
            self.footer_height += sum(line.height for line in self.lines(config['footer_text'], self.epw)) + 3
        self.set_auto_page_break(True, margin=self.footer_height + 12)
        sprite = ElementTree.parse(ASSETS / 'vendor' / 'tabler-icons' / 'tabler-icons.svg')
        self.symbols = {node.attrib['id']: node for node in sprite.getroot()}

    def _font(self, size: float, bold: bool) -> float:
        self.set_font('Recipe', 'B' if bold else '', size)
        self.set_text_color(*(self.primary if bold and size >= 14 else self.ink))
        font = cast(TTFFont, self.current_font)
        return max(self.leading, size * 1.35,
                   size * (font.desc.ascent - font.desc.descent) / 1000 + 0.2)

    def lines(self, text: str, width: float, *, bold: bool = False, size: float | None = None,
              icon: str | None = None, keep_next: bool = False) -> list[SheetLine]:
        point = size or self.body_size
        height = self._font(point, bold)
        font = cast(TTFFont, self.current_font)
        if any(char != '\n' and ord(char) not in font.cmap for char in text):
            raise RecipePdfError('Ein Zeichen dieser Rezeptrevision wird von der Druckschrift nicht unterstützt.')
        inset = point + 7 if icon else 0
        wrapped = cast(list[str], self.multi_cell(width - inset, height, text, dry_run=True, output='LINES'))
        return [SheetLine(value, height, point, bold, icon if index == 0 else None,
                          keep_next=keep_next or index < len(wrapped) - 1 and bold)
                for index, value in enumerate(wrapped)]

    def icon(self, name: str, x: float, y: float, size: float) -> None:
        # Only the committed Tabler subset is used; SVG paths paint as PDF vectors.
        symbol = self.symbols['tabler-' + name]
        color = 'rgb(' + ','.join(str(channel) for channel in self.primary) + ')'
        svg = ElementTree.Element('svg', {**symbol.attrib, 'xmlns': 'http://www.w3.org/2000/svg',
                                         'width': '24', 'height': '24', 'stroke': color})
        svg.attrib.pop('id')
        svg.extend(list(symbol))
        self.image(BytesIO(ElementTree.tostring(svg)), x=x, y=y, w=size, h=size)

    def draw_line(self, line: SheetLine, x: float, y: float, width: float) -> None:
        self.set_xy(x, y)
        if line.photo is not None:
            self.image(BytesIO(line.photo), x=x, y=y, w=width, h=line.height - 8, keep_aspect_ratio=True)
        elif line.text:
            self._font(line.size, line.bold)
            if line.icon:
                self.icon(line.icon, x, y + (line.height - line.size) / 2, line.size)
                self.set_x(x + line.size + 7)
            self.cell(width - (self.x - x), line.height, line.text)
        self.set_xy(x, y + line.height)

    def paragraph(self, text: str, *, bold: bool = False, size: float | None = None,
                  icon: str | None = None) -> None:
        for line in self.lines(text, self.epw, bold=bold, size=size, icon=icon):
            if self.will_page_break(line.height):
                self.add_page()
            self.draw_line(line, self.l_margin, self.y, self.epw)

    def heading(self, text: str, *, icon: str | None = None, title: bool = False) -> None:
        if self.will_page_break(4 * self.leading):
            self.add_page()
        self.ln(8)
        self.paragraph(text, bold=True, size=26 if title else 15, icon=icon)
        self.ln(5)

    def start_recipe(self, title: str, label: str, revision: str, amount: str) -> None:
        """Keep a child's measured title and quantity context together when it starts."""
        self.continuation = ''
        required = sum(line.height for line in self.lines(title, self.epw, bold=True, size=26))
        for text, icon in ((label, 'components'), (revision, 'history'), (amount, 'tools-kitchen-2')):
            required += sum(line.height for line in self.lines(text, self.epw, icon=icon))
        required += 13 + self.leading  # Heading spacing and at least one following body line.
        if self.will_page_break(required + 12):
            self.add_page()
        else:
            self.ln(12)

    def photo(self, data: bytes, *, logo: bool = False) -> None:
        width, height = (110.0, 42.0) if logo else (self.epw, 160.0)
        if self.will_page_break(height + 8):
            self.add_page()
        self.image(BytesIO(data), x=self.l_margin, y=self.y, w=width, h=height, keep_aspect_ratio=True)
        self.ln(height + 8)

    def header(self) -> None:
        if self.continuation:
            self.paragraph(self.continuation, bold=True)
            self.paragraph('Fortsetzung')
            self.ln(10)

    def footer(self) -> None:
        self.set_y(-self.footer_height)
        if self.config['footer_text']:
            self.paragraph(self.config['footer_text'])
            self.ln(3)
        self.paragraph(f'Seite {self.page_no()}')

    @property
    def column_widths(self) -> tuple[float, float]:
        left = (self.epw - 24) / 3
        return left, self.epw - left - 24

    def columns(self, left: list[SheetLine], right: list[SheetLine]) -> None:
        queues = (deque(left), deque(right))
        widths = self.column_widths
        while any(queues):
            start = self.y
            ends = []
            for queue, width, x in zip(queues, widths, (self.l_margin, self.l_margin + widths[0] + 24)):
                y = start
                while queue:
                    line = queue[0]
                    if not line.text and line.photo is None:
                        queue.popleft()
                        y = min(y + line.height, self.page_break_trigger)
                        continue
                    reserve = line.height + (queue[1].height if line.keep_next and len(queue) > 1 else 0)
                    if y + reserve > self.page_break_trigger:
                        break
                    self.draw_line(queue.popleft(), x, y, width)
                    y += line.height
                ends.append(y)
            self.set_draw_color(*self.primary)
            self.set_line_width(0.5)
            self.line(self.l_margin + widths[0] + 12, start,
                      self.l_margin + widths[0] + 12, max(ends))
            self.set_xy(self.l_margin, max(ends) + 8)
            if any(queues):
                self.add_page()
