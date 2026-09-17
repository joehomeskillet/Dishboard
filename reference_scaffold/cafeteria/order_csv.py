"""Formula-safe CSV preview bytes. Download must equal preview. No HTTP clients."""
from __future__ import annotations

import ast
import csv
import io
from typing import Any, Mapping


def csv_cell(value: object) -> str:
    text = '' if value is None else str(value)
    if text[:1] in '=+-@':
        return "'" + text
    return text


def basket_csv_bytes(basket: Mapping[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(['Artikelcode', 'Name', 'Menge', 'Einheit', 'Gebinde', 'Ohne Zutat'])
    for line in basket.get('lines') or ():
        writer.writerow([
            csv_cell(line.get('article_code')),
            csv_cell(line.get('article_name')),
            csv_cell(line.get('quantity')),
            csv_cell(line.get('order_unit_code')),
            csv_cell(line.get('pack_size')),
            'ja' if line.get('without_food') else 'nein',
        ])
    return buffer.getvalue().encode('utf-8')


def assert_no_http_clients(source: str) -> None:
    tree = ast.parse(source)
    forbidden = {'requests', 'httpx', 'urllib', 'httplib', 'http.client'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                if alias.name in forbidden or root in forbidden:
                    raise AssertionError(alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split('.')[0]
            if node.module in forbidden or root in forbidden:
                raise AssertionError(node.module)
