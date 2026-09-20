"""Validate trusted semantic data against the assets actually shipped."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from pathlib import Path
from types import MappingProxyType
from xml.etree import ElementTree

from cafeteria.food_symbols import food_symbol

ROOT = Path(__file__).resolve().parent
STATIC = ROOT.parent / 'static'
ROLES = frozenset({'primary', 'secondary', 'danger', 'neutral', 'success', 'warning'})
FOOD = {
    'diet.vegetarian': ('labels', 'VEGETARIAN'),
    'diet.vegan': ('labels', 'VEGAN'),
    **{f'allergen.{key}': ('allergens', code) for key, code in {
        'gluten': 'GLUTEN', 'crustaceans': 'CRUSTACEANS', 'eggs': 'EGGS',
        'fish': 'FISH', 'peanuts': 'PEANUTS', 'soy': 'SOY', 'milk': 'MILK',
        'nuts': 'NUTS', 'celery': 'CELERY', 'mustard': 'MUSTARD',
        'sesame': 'SESAME', 'sulfites': 'SULPHITES', 'lupin': 'LUPIN',
        'molluscs': 'MOLLUSCS',
    }.items()},
}


class SemanticError(ValueError):
    """Invalid semantic presentation contract; do not render a broken control."""


@dataclass(frozen=True)
class Semantic:
    key: str
    category: str
    ascii: str
    icon: str
    label_key: str
    tooltip_key: str
    aria_key: str
    icon_only_allowed: bool
    role: str
    resolved_icon: str = ''


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SemanticError(f'{key}: duplicate JSON key')
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)


def sprite_icons() -> frozenset[str]:
    # This is a fixed, trusted project asset, never a user-supplied XML document.
    root = ElementTree.parse(STATIC / 'vendor/tabler-icons/tabler-icons.svg').getroot()
    return frozenset(node.attrib['id'].removeprefix('tabler-') for node in root
                     if node.tag.endswith('}symbol'))


def load_registry(path: Path = ROOT / 'semantic_registry.json') -> Mapping[str, Semantic]:
    rows = read_json(path)
    fallbacks = read_json(ROOT / 'icon_fallbacks.json')
    available = sprite_icons()
    schema = {field.name for field in fields(Semantic)} - {'resolved_icon'}
    if not isinstance(rows, list):
        raise SemanticError('registry: expected a list')
    result: dict[str, Semantic] = {}
    for row in rows:
        key = row.get('key', '<missing>') if isinstance(row, dict) else '<missing>'
        if not isinstance(row, dict) or set(row) != schema:
            raise SemanticError(f'{key}: incomplete or unexpected registry schema')
        if any(not isinstance(row[name], str) or not row[name].strip()
               for name in schema - {'icon_only_allowed'}):
            raise SemanticError(f'{key}: expected nonempty strings')
        if type(row['icon_only_allowed']) is not bool or row['role'] not in ROLES:
            raise SemanticError(f'{key}: invalid icon policy or role')
        if key in result:
            raise SemanticError(f'{key}: duplicate semantic key')
        item = Semantic(**row)
        for suffix in ('label', 'tooltip', 'aria'):
            if getattr(item, f'{suffix}_key') != f'{key}.{suffix}':
                raise SemanticError(f'{key}: invalid {suffix}_key')
        resolved = item.icon
        allowed = item.icon_only_allowed
        if key in FOOD:
            kind, code = FOOD[key]
            asset = food_symbol(code, kind)
            if asset is None or not (STATIC / asset.filename).is_file():
                raise SemanticError(f'{key}: missing food symbol {kind}/{code}')
            resolved = f'food:{kind}:{code}'
        elif item.icon not in available:
            fallback = fallbacks.get(item.icon)
            if (not isinstance(fallback, dict) or set(fallback) != {'icon', 'icon_only_allowed'}
                    or type(fallback['icon_only_allowed']) is not bool
                    or fallback['icon'] not in available):
                raise SemanticError(f'{key}: missing or invalid fallback for {item.icon}')
            resolved = fallback['icon']
            allowed = allowed and fallback['icon_only_allowed']
        if resolved not in available and not resolved.startswith('food:'):
            raise SemanticError(f'{key}: missing resolved icon {resolved}')
        result[key] = replace(item, resolved_icon=resolved, icon_only_allowed=allowed)
    return MappingProxyType(result)


def validate_locales(registry: Mapping[str, Semantic], locales: Mapping[str, Mapping[str, str]]) -> None:
    expected = {getattr(item, field) for item in registry.values()
                for field in ('label_key', 'tooltip_key', 'aria_key')}
    if 'de' not in locales:
        raise SemanticError('de: required primary locale missing')
    for locale, messages in locales.items():
        for key in sorted(expected - messages.keys()):
            raise SemanticError(f'{key}: translation missing in {locale}')
        for key in sorted(messages.keys() - expected):
            raise SemanticError(f'{key}: orphan translation in {locale}')
        for key, value in messages.items():
            if not isinstance(value, str) or not value.strip():
                raise SemanticError(f'{key}: empty or invalid translation in {locale}')
