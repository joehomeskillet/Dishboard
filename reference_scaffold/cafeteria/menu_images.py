"""Local serving illustrations, matched to the exact published or saved composition."""
from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

CATALOG = Path(__file__).parent / 'static' / 'img' / 'menus' / 'manifest.json'


@lru_cache(maxsize=1)
def _images() -> dict[tuple[str, tuple[str, ...]], str]:
    rows = json.loads(CATALOG.read_text(encoding='utf-8'))
    return {
        (row['title'], tuple(row['components'])): row['file']
        for row in rows if row['status'] == 'ready'
    }


def menu_image(option: object) -> str | None:
    """Do not infer from historical IDs, similar titles or changed components."""
    if not isinstance(option, Mapping):
        return None
    title, components = option.get('title'), option.get('components')
    if not isinstance(title, str) or not isinstance(components, (list, tuple)):
        return None
    if any(not isinstance(component, str) for component in components):
        return None
    return _images().get((title, tuple(components)))
