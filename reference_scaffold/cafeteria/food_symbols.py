"""Local presentation symbols; declarations and publication decisions stay upstream."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

PREFIX = 'vendor/food-symbols/'
ASSETS = Path(__file__).parent / 'static' / PREFIX


@dataclass(frozen=True)
class FoodSymbol:
    code: str
    name: str
    filename: str
    pdf_filename: str | None


@dataclass(frozen=True)
class LegendEntry:
    kind: str
    code: str
    name: str
    presence: str
    symbol: FoodSymbol | None


@dataclass(frozen=True)
class FoodLegend:
    entries: tuple[LegendEntry, ...]
    allergens_unknown: bool
    review_open: bool


@lru_cache(maxsize=1)
def _symbols() -> dict[tuple[str, str], FoodSymbol]:
    manifest = json.loads((ASSETS / 'manifest.json').read_text(encoding='utf-8'))
    audit = json.loads((ASSETS / 'pdf-compatibility.json').read_text(encoding='utf-8'))
    result = {}
    for kind in ('allergens', 'countries'):
        for code, row in manifest[kind].items():
            filename = PREFIX + row['file']
            compatible = audit['results'][f'{kind}/{code}']['status'] == 'renders_without_warning'
            result[kind, code] = FoodSymbol(
                code, row['name'], filename, filename if compatible else None,
            )
    return result


def food_symbol(code: object, kind: str = 'allergens') -> FoodSymbol | None:
    """Exact known codes only: never construct paths from an input or infer a code."""
    if not isinstance(code, str) or kind not in ('allergens', 'countries'):
        return None
    return _symbols().get((kind, code))


def food_legend(options: Iterable[Mapping[str, Any]]) -> FoodLegend:
    """Collect only supplied visible options, sorted by kind, name and presence.

    Presence remains part of allergen identity. The caller selects the displayed
    day/services/page; this helper neither loads nor mutates a snapshot.
    """
    entries: dict[tuple[str, str, str], LegendEntry] = {}
    unknown = review_open = False
    for option in options:
        allergens = option.get('allergens') or []
        unknown |= not allergens
        review_open |= bool(allergens) and option.get('allergen_review_status') != 'checked'
        for kind, field in (('allergens', 'allergens'), ('countries', 'origins'), ('labels', 'labels')):
            for row in option.get(field) or []:
                code = str(row.get('country_code' if kind == 'countries' else 'code') or '')
                presence = str(row.get('presence') or '') if kind == 'allergens' else ''
                symbol = food_symbol(code, kind)
                if kind == 'countries':
                    name = symbol.name if symbol else code or str(row.get('text') or 'Nicht erfasst')
                else:
                    name = str(row.get('name') or (symbol.name if symbol else code) or 'Nicht erfasst')
                # Missing codes must not collapse distinct unrecognized declarations.
                key = kind, code or name, presence
                entries.setdefault(key, LegendEntry(kind, code, name, presence, symbol))
    kind_order = {'allergens': 0, 'countries': 1, 'labels': 2}
    presence_order = {'contains': 0, 'may_contain': 1}
    ordered = sorted(entries.values(), key=lambda item: (
        kind_order[item.kind], item.name.casefold(), item.code,
        presence_order.get(item.presence, 2), item.presence,
    ))
    return FoodLegend(tuple(ordered), unknown, review_open)
