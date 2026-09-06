"""Measured local PDF symbols; audited incompatible flags retain country text."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fpdf import FPDF

from ..food_symbols import FoodSymbol, LegendEntry, food_legend, food_symbol

ASSETS = Path(__file__).resolve().parents[1] / 'static'
ICON_HEIGHT = 12.0
ICON_GAP = 3.0
LINE_HEIGHT = 16.0


@dataclass(frozen=True)
class SymbolMark:
    symbol: FoodSymbol
    width: float


@dataclass(frozen=True)
class SymbolStrip:
    rows: tuple[tuple[SymbolMark, ...], ...]

    @property
    def height(self) -> float:
        return len(self.rows) * LINE_HEIGHT


def symbol_mark(entry: LegendEntry) -> SymbolMark | None:
    if entry.symbol is None or entry.symbol.pdf_filename is None:
        return None
    return SymbolMark(entry.symbol, 18.0 if entry.kind == 'countries' else ICON_HEIGHT)


def measure_symbols(option: dict[str, Any] | None, width: float) -> SymbolStrip:
    rows: list[tuple[SymbolMark, ...]] = []
    row: list[SymbolMark] = []
    used = 0.0
    seen: set[str] = set()
    for entry in food_legend([option] if option else []).entries:
        mark = symbol_mark(entry)
        if mark is None or mark.symbol.filename in seen:
            continue
        seen.add(mark.symbol.filename)
        if row and used + mark.width > width:
            rows.append(tuple(row))
            row, used = [], 0.0
        row.append(mark)
        used += mark.width + ICON_GAP
    if row:
        rows.append(tuple(row))
    return SymbolStrip(tuple(rows))


def draw_symbol(pdf: FPDF, mark: SymbolMark, x: float, y: float) -> None:
    # Paths come only from the audited local manifest, never from menu input.
    if mark.symbol.pdf_filename is not None:
        # Erudus paths inherit their fill: isolate black print ink from table fills.
        # Explicit country colors inside each SVG still take precedence.
        with pdf.local_context(fill_color=(0, 0, 0), draw_color=(0, 0, 0)):
            pdf.image(ASSETS / mark.symbol.pdf_filename, x, y, w=mark.width, h=ICON_HEIGHT,
                      keep_aspect_ratio=True)


def draw_symbols(pdf: FPDF, strip: SymbolStrip, x: float, y: float) -> float:
    for row in strip.rows:
        current_x = x
        for mark in row:
            draw_symbol(pdf, mark, current_x, y)
            current_x += mark.width + ICON_GAP
        y += LINE_HEIGHT
    return y


def origin_text(origin: dict[str, Any]) -> str:
    text = str(origin.get('text') or '')
    country = food_symbol(origin.get('country_code'), 'countries')
    if country and country.pdf_filename is None and country.name.casefold() not in text.casefold():
        text = f'{text} ({country.name})' if text else country.name
    return text


def legend_text(entry: LegendEntry) -> str:
    if entry.kind == 'allergens':
        prefix = {'contains': 'Enthält', 'may_contain': 'Kann enthalten'}.get(
            entry.presence, 'Allergenangabe ungeklärt',
        )
        return f'{prefix}: {entry.name}'
    return f'Herkunft: {entry.name}' if entry.kind == 'countries' else entry.name
