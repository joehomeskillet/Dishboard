"""Pure shopping-list aggregator on captured revision DTOs. No I/O."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .quantities import FoodFactors, QuantityError, Unit, convert, scale_servings

POLICY_LEAF = 'leaf'
POLICY_PREPARED = 'prepared'
_STATUS_COMPLETE = 'complete'
_STATUS_INCOMPLETE = 'incomplete'
_GRAM = Unit('G', 'mass', Decimal('1'))


@dataclass(frozen=True)
class IngredientNeed:
    food_public_id: str | None
    quantity: Decimal | None
    unit: Unit | None
    food: FoodFactors | None
    prepared_child: RevisionNeed | None = None
    schema_version: int = 2
    text: str = ''


@dataclass(frozen=True)
class RevisionNeed:
    revision_id: str
    content_hash: str
    source_servings: Decimal
    target_servings: Decimal
    ingredients: tuple[IngredientNeed, ...]


@dataclass(frozen=True)
class AggregateLine:
    food_public_id: str | None
    quantity: Decimal | None
    unit_code: str
    status: str
    reason: str | None
    captured: tuple[object, ...]


def _key(food_id: str, unit: Unit, food: FoodFactors | None) -> tuple[object, ...]:
    density = food.density_g_per_ml if food is not None else None
    piece = food.piece_weight_g if food is not None else None
    return (food_id, unit.dimension, unit.base_factor, density, piece)


def _scale(item: IngredientNeed, source: Decimal, target: Decimal) -> IngredientNeed:
    if item.quantity is None:
        return item
    try:
        scaled = scale_servings(item.quantity, source, target)
    except QuantityError:
        return IngredientNeed(
            item.food_public_id, None, item.unit, item.food, item.prepared_child,
            item.schema_version, item.text,
        )
    return IngredientNeed(
        item.food_public_id, scaled, item.unit, item.food, item.prepared_child,
        item.schema_version, item.text,
    )


def _expand(need: RevisionNeed, policy: str, stop: frozenset[str]) -> list[IngredientNeed]:
    out: list[IngredientNeed] = []
    for item in need.ingredients:
        scaled = _scale(item, need.source_servings, need.target_servings)
        if item.schema_version == 1:
            out.append(scaled)
            continue
        child = item.prepared_child
        if child is None:
            out.append(scaled)
            continue
        stop_here = policy == POLICY_PREPARED and (
            not stop or (item.food_public_id is not None and item.food_public_id in stop)
        )
        if stop_here:
            out.append(IngredientNeed(
                scaled.food_public_id, scaled.quantity, scaled.unit, scaled.food,
                None, scaled.schema_version, scaled.text,
            ))
            continue
        child_target = scaled.quantity if scaled.quantity is not None else child.target_servings
        expanded = RevisionNeed(
            child.revision_id, child.content_hash, child.source_servings,
            child_target, child.ingredients,
        )
        out.extend(_expand(expanded, POLICY_LEAF, frozenset()))
    return out


def _to_grams(item: IngredientNeed) -> Decimal | None:
    if item.quantity is None or item.unit is None:
        return None
    try:
        return convert(item.quantity, item.unit, _GRAM, item.food)
    except QuantityError:
        return None


def aggregate(
    needs: Sequence[RevisionNeed],
    *,
    policy: str = POLICY_LEAF,
    stop_prepared_food_ids: frozenset[str] | None = None,
) -> tuple[AggregateLine, ...]:
    """Merge captured ingredient needs. Unknown quantities stay incomplete, never zero."""
    if policy not in {POLICY_LEAF, POLICY_PREPARED}:
        raise ValueError('Bedarfspolitik ist leaf oder prepared.')
    stop = stop_prepared_food_ids or frozenset()
    leaves: list[IngredientNeed] = []
    for need in needs:
        leaves.extend(_expand(need, policy, stop))

    buckets: dict[tuple[object, ...], list[IngredientNeed]] = {}
    isolated: list[AggregateLine] = []
    for item in leaves:
        if item.food_public_id is None or item.quantity is None or item.unit is None:
            isolated.append(AggregateLine(
                item.food_public_id, None, item.unit.code if item.unit else '',
                _STATUS_INCOMPLETE, 'unvollständig',
                (item.food_public_id, item.text, item.schema_version),
            ))
            continue
        grams = _to_grams(item)
        key = ('mass', item.food_public_id, item.food) if grams is not None else _key(
            item.food_public_id, item.unit, item.food,
        )
        buckets.setdefault(key, []).append(item)

    merged: list[AggregateLine] = []
    for key, group in buckets.items():
        if key[0] == 'mass':
            total = Decimal('0')
            food_id = group[0].food_public_id
            captured = (
                food_id,
                group[0].food.density_g_per_ml if group[0].food else None,
                group[0].food.piece_weight_g if group[0].food else None,
            )
            complete = True
            for item in group:
                grams = _to_grams(item)
                if grams is None:
                    complete = False
                    isolated.append(AggregateLine(
                        item.food_public_id, item.quantity, item.unit.code,
                        _STATUS_INCOMPLETE, 'nicht umrechenbar', captured,
                    ))
                    continue
                total += grams
            if complete:
                merged.append(AggregateLine(
                    food_id, total, 'G', _STATUS_COMPLETE, None, captured,
                ))
            continue
        if len(group) == 1:
            item = group[0]
            merged.append(AggregateLine(
                item.food_public_id, item.quantity, item.unit.code,
                _STATUS_COMPLETE, None, key,
            ))
            continue
        total = Decimal('0')
        unit = group[0].unit
        food_id = group[0].food_public_id
        ok = True
        for item in group:
            try:
                total += convert(item.quantity, item.unit, unit, item.food)
            except QuantityError:
                ok = False
                isolated.append(AggregateLine(
                    item.food_public_id, item.quantity, item.unit.code,
                    _STATUS_INCOMPLETE, 'nicht umrechenbar', key,
                ))
        if ok:
            merged.append(AggregateLine(
                food_id, total, unit.code, _STATUS_COMPLETE, None, key,
            ))
    return tuple(merged + isolated)
