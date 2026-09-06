"""Pure recipe quantities; storage validation is separate from calculation precision."""
from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
    Overflow, ROUND_HALF_UP, Underflow, localcontext,
)


class QuantityError(ValueError):
    """Invalid quantity, unit metadata or missing ingredient-specific conversion."""


_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')
_CODE = re.compile(r'[A-Z][A-Z0-9_]{0,15}')
_SEED_UNITS = (
    ('G', 'mass', '1'), ('KG', 'mass', '1000'),
    ('ML', 'volume', '1'), ('L', 'volume', '1000'),
    ('EL', 'volume', '15'), ('TL', 'volume', '5'), ('STK', 'count', '1'),
    ('PORTION', 'contextual', None), ('PRISE', 'contextual', None),
)


@contextmanager
def _arithmetic() -> Iterator[None]:
    # Set every context field: even caller traps, exponent limits and flags are irrelevant.
    context = Context(
        prec=50, rounding=ROUND_HALF_UP, Emin=-999999, Emax=999999,
        capitals=1, clamp=0, flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow, Underflow],
    )
    try:
        with localcontext(context):
            yield
    except DecimalException as error:
        raise QuantityError('Mengenberechnung liegt ausserhalb des Rechenbereichs.') from error


def _positive(value: Decimal, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise QuantityError(f'{label} muss eine endliche, positive Decimal-Zahl sein.')
    return value


def _parse(value: str | Decimal, integer_places: int, decimal_places: int, label: str) -> Decimal:
    if isinstance(value, str):
        if _NUMBER.fullmatch(value.strip()) is None:
            raise QuantityError(f'{label} ist keine gültige Dezimalzahl.')
        with _arithmetic():
            number = Decimal(value.strip())
    elif isinstance(value, Decimal):
        number = value
    else:
        raise QuantityError(f'{label} muss als Text oder Decimal übergeben werden.')
    _positive(number, label)
    _, digits, exponent = number.as_tuple()
    if not isinstance(exponent, int):
        raise QuantityError(f'{label} muss endlich sein.')
    end = len(digits)
    while end > 1 and digits[end - 1] == 0:
        end -= 1
    exponent += len(digits) - end
    if end + exponent > integer_places or -exponent > decimal_places:
        raise QuantityError(
            f'{label} erlaubt höchstens {integer_places} Vorkomma- und '
            f'{decimal_places} Nachkommastellen; keine automatische Rundung.'
        )
    return Decimal((0, digits[:end], exponent))


def parse_quantity(value: str | Decimal) -> Decimal:
    """Validate the storage boundary: 12 integer and 6 fractional places."""
    return _parse(value, 12, 6, 'Menge')


def parse_factor(value: str | Decimal) -> Decimal:
    """Validate the storage boundary: 11 integer and 9 fractional places."""
    return _parse(value, 11, 9, 'Faktor')


@dataclass(frozen=True)
class Unit:
    code: str
    dimension: str
    base_factor: Decimal | None

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or _CODE.fullmatch(self.code) is None:
            raise QuantityError('Einheitencode muss aus 1 bis 16 Grossbuchstaben/Ziffern bestehen.')
        if not isinstance(self.dimension, str) or self.dimension not in (
            'mass', 'volume', 'count', 'contextual',
        ):
            raise QuantityError('Einheit hat eine unbekannte Dimension.')
        if self.dimension == 'contextual':
            if self.base_factor is not None:
                raise QuantityError('Kontextabhängige Einheiten dürfen keinen Basisfaktor haben.')
        else:
            if self.base_factor is None:
                raise QuantityError('Einheit benötigt einen positiven Basisfaktor.')
            object.__setattr__(self, 'base_factor', parse_factor(self.base_factor))
        for code, dimension, factor in _SEED_UNITS:
            if self.code == code and (
                self.dimension != dimension
                or self.base_factor != (Decimal(factor) if factor is not None else None)
            ):
                raise QuantityError(f'Die Bedeutung der Einheit {code} ist fest vorgegeben.')


@dataclass(frozen=True)
class FoodFactors:
    density_g_per_ml: Decimal | None = None
    piece_weight_g: Decimal | None = None

    def __post_init__(self) -> None:
        if self.density_g_per_ml is not None:
            object.__setattr__(self, 'density_g_per_ml', parse_factor(self.density_g_per_ml))
        if self.piece_weight_g is not None:
            object.__setattr__(self, 'piece_weight_g', parse_factor(self.piece_weight_g))


def _unit(value: Unit) -> Unit:
    if not isinstance(value, Unit):
        raise QuantityError('Eine validierte Einheit ist erforderlich.')
    return value


def _base_factor(unit: Unit) -> Decimal:
    if unit.base_factor is None:
        raise QuantityError('Kontextabhängige Einheiten haben keine globale Basismenge.')
    return unit.base_factor


def _food_factor(food: FoodFactors | None, dimension: str) -> Decimal:
    if dimension == 'volume':
        value = food.density_g_per_ml if food is not None else None
        label = 'Dichte'
    else:
        value = food.piece_weight_g if food is not None else None
        label = 'Stückgewicht'
    if value is None:
        raise QuantityError(f'{label} der Zutat fehlt für diese Umrechnung.')
    return value


def convert(quantity: Decimal, from_unit: Unit, to_unit: Unit,
            food: FoodFactors | None = None) -> Decimal:
    """Convert using one ingredient's factors; never quantize to a storage scale."""
    amount = _positive(quantity, 'Menge')
    source, target = _unit(from_unit), _unit(to_unit)
    if food is not None and not isinstance(food, FoodFactors):
        raise QuantityError('Zutatenfaktoren müssen als FoodFactors übergeben werden.')
    if source.code == target.code and source != target:
        raise QuantityError('Derselbe Einheitencode hat widersprüchliche Metadaten.')
    if 'contextual' in (source.dimension, target.dimension):
        if source == target:
            return amount
        raise QuantityError('Kontextabhängige Einheiten erlauben nur denselben Code als Identität.')
    with _arithmetic():
        base = amount * _base_factor(source)
        if source.dimension != target.dimension:
            if source.dimension != 'mass':
                base *= _food_factor(food, source.dimension)
            if target.dimension != 'mass':
                base /= _food_factor(food, target.dimension)
        return base / _base_factor(target)


def to_base(quantity: Decimal, unit: Unit) -> Decimal:
    """Return grams, millilitres or pieces; contextual units have no global base."""
    amount = _positive(quantity, 'Menge')
    factor = _base_factor(_unit(unit))
    with _arithmetic():
        return amount * factor


def sum_in_base(quantities_and_units: Sequence[tuple[Decimal, Unit]]) -> Decimal:
    """Aggregate one dimension in its base; the empty sequence has value zero."""
    if isinstance(quantities_and_units, (str, bytes)) or not isinstance(quantities_and_units, Sequence):
        raise QuantityError('Summierung benötigt eine Folge von Mengen und Einheiten.')
    dimension: str | None = None
    seen: dict[str, Unit] = {}
    with _arithmetic():
        total = Decimal('0')
        for row in quantities_and_units:
            if not isinstance(row, (tuple, list)) or len(row) != 2:
                raise QuantityError('Jede Summenzeile benötigt genau Menge und Einheit.')
            quantity, unit = row
            unit = _unit(unit)
            if unit.dimension == 'contextual' or dimension not in (None, unit.dimension):
                raise QuantityError('Nur dieselbe konvertierbare Dimension darf summiert werden.')
            if unit.code in seen and seen[unit.code] != unit:
                raise QuantityError('Derselbe Einheitencode hat widersprüchliche Metadaten.')
            seen[unit.code] = unit
            dimension = unit.dimension
            total += to_base(quantity, unit)
        return total


def scale_servings(quantity: Decimal, source_servings: Decimal, target_servings: Decimal) -> Decimal:
    """Scale a single recipe row, including a contextual pinch/portion row."""
    amount = _positive(quantity, 'Menge')
    source = parse_quantity(source_servings)
    target = parse_quantity(target_servings)
    with _arithmetic():
        return amount * target / source
