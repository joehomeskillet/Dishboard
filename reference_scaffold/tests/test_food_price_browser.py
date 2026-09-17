"""PRICE-UI: food sheet exposes purchase-price form."""
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'grundlagen_food.html'


def test_food_sheet_has_purchase_price_form() -> None:
    text = TEMPLATE.read_text(encoding='utf-8')
    assert 'Einkaufspreis' in text
    assert 'admin.food_price_save' in text
    assert 'unit_price' in text
    assert 'unvollständig, nicht als 0' in text
