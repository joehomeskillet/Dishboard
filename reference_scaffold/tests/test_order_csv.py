"""Formula-safe order CSV; preview bytes equal download source."""
from pathlib import Path

from cafeteria.order_csv import assert_no_http_clients, basket_csv_bytes, csv_cell


def test_csv_cells_neutralize_formulas() -> None:
    assert csv_cell('=CMD') == "'=CMD"
    assert csv_cell('+1') == "'+1"
    assert csv_cell('-1') == "'-1"
    assert csv_cell('@import') == "'@import"
    assert csv_cell('Kartoffeln') == 'Kartoffeln'


def test_preview_bytes_are_stable_and_neutral() -> None:
    basket = {
        'lines': [{
            'article_code': '=HYPERLINK',
            'article_name': 'Mehl',
            'quantity': '2',
            'order_unit_code': 'KG',
            'pack_size': '1',
            'without_food': True,
        }],
    }
    first = basket_csv_bytes(basket)
    second = basket_csv_bytes(basket)
    assert first == second
    assert b"'=HYPERLINK" in first
    assert b'BESTELLEN' not in first
    assert b'Rohmenge' in first


def test_order_modules_have_no_http_clients() -> None:
    root = Path(__file__).resolve().parents[1] / 'cafeteria'
    for name in ('order_csv.py', 'order_basket_store.py', 'admin/order_routes.py'):
        assert_no_http_clients((root / name).read_text(encoding='utf-8'))
