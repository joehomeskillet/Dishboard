"""Offline native PDF contracts for immutable shopping list output. DB-free."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Inexact, localcontext
from io import BytesIO

import pytest
from pypdf import PdfReader

from cafeteria.admin.shopping_pdf import ShoppingPdfError, render_shopping_pdf
from cafeteria.print_template_config import PrintTemplateValidationError, default_config, default_layout


def _line(**overrides):
    base = {
        'food_public_id': '00000000-0000-0000-0000-000000000010', 'quantity': '2.5', 'unit_code': 'KG',
        'completeness': 'complete', 'reason': None, 'line_key': 'key-1',
        'food_name': 'Karotten', 'ingredient_text': None, 'unit_name': 'Kilogramm', 'checked_status': 'open',
    }
    base.update(overrides)
    return base


def _selected_revision(**overrides):
    base = {
        'public_id': '00000000-0000-0000-0000-000000000002', 'revision_number': 3, 'policy': 'leaf',
        'computed_at': datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc), 'is_latest': True,
        'inputs': [], 'lines': [_line()], 'incomplete_lines': [],
    }
    base.update(overrides)
    return base


def _detail(**overrides):
    base = {
        'public_id': '00000000-0000-0000-0000-000000000001', 'title': 'Wocheneinkauf KW37', 'note': None,
        'row_version': 1, 'archived_at': None, 'menu_week_public_id': None,
        'revisions': ({'public_id': '00000000-0000-0000-0000-000000000002', 'revision_number': 3,
                       'policy': 'leaf', 'computed_at': datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc),
                       'computed_by': 1},),
        'selected_revision': _selected_revision(),
        'manual_items': (),
    }
    base.update(overrides)
    return base


def render(value=None, **kwargs):
    return render_shopping_pdf(value if value is not None else _detail(),
                               config=kwargs.pop('config', default_config()), **kwargs)


def text(data):
    return ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages).split())


def page_text(page):
    return ' '.join(page.extract_text().split())


def test_pdf_opens_and_contains_title_revision_policy_and_lines():
    body = text(render())
    assert 'Wocheneinkauf KW37' in body
    assert 'Beleg 3' in body
    assert 'Blattbedarf' in body
    assert 'Karotten' in body
    assert '2,5 Kilogramm' in body


def test_decimal_quantity_string_reaches_pdf_unrounded():
    detail = _detail(selected_revision=_selected_revision(lines=[
        _line(quantity='0.333333', unit_code='L', unit_name='Liter', food_name='Milch', line_key='a'),
        _line(quantity='1250.500000', unit_code='G', unit_name='Gramm', food_name='Zucker', line_key='b'),
    ]))
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        body = text(render(detail))
    assert '0,333333 Liter · Milch' in body
    assert '1250,500000 Gramm · Zucker' in body


def test_two_hundred_lines_wrap_readably_without_truncation():
    lines = [_line(food_name=f'Zutat{index:04d}', quantity=str(index), unit_code='STK', unit_name='Stück',
                    line_key=f'k{index}') for index in range(200)]
    data = render(_detail(selected_revision=_selected_revision(lines=lines)))
    reader = PdfReader(BytesIO(data))
    assert len(reader.pages) >= 2
    for number, page in enumerate(reader.pages, 1):
        assert f'Seite {number}' in page.extract_text()
    body = text(data)
    assert all(body.count(f'Zutat{index:04d}') == 1 for index in range(200))
    for index in range(200):
        label = f'Zutat{index:04d}'
        holder = [page for page in reader.pages if label in page.extract_text()]
        assert len(holder) == 1
        assert f'{index} Stück · {label}' in page_text(holder[0])


def test_manual_items_are_marked_as_manual():
    detail = _detail(manual_items=(
        {'public_id': 'm1', 'sort_order': 1, 'item_text': 'Servietten', 'quantity': None,
         'unit_code': None, 'checked': False, 'row_version': 1},
        {'public_id': 'm2', 'sort_order': 2, 'item_text': 'Spülmittel', 'quantity': '3',
         'unit_code': 'STK', 'checked': False, 'row_version': 1},
    ))
    body = text(render(detail))
    assert 'Manuelle Positionen' in body
    assert 'Menge unbekannt · Servietten' in body
    assert '3 STK · Spülmittel' in body


def test_incomplete_lines_show_unknown_quantity_never_zero():
    detail = _detail(selected_revision=_selected_revision(lines=[], incomplete_lines=[
        _line(quantity=None, unit_code='', unit_name=None, food_name='Unbekannte Zutat',
              completeness='incomplete', reason='unvollständig', line_key='inc1'),
    ]))
    body = text(render(detail))
    assert 'Unvollständige Mengen' in body
    assert 'Menge unbekannt · Unbekannte Zutat · Grund: unvollständig' in body
    assert '0 · Unbekannte Zutat' not in body


def test_check_status_is_not_printed():
    checked = _detail(selected_revision=_selected_revision(lines=[_line(checked_status='checked')]))
    reopened = _detail(selected_revision=_selected_revision(lines=[_line(checked_status='open')]))
    assert render(checked) == render(reopened)


def test_invalid_template_value_is_rejected_by_existing_validator():
    with pytest.raises(PrintTemplateValidationError):
        render(config={**default_config(), 'palette': 'not-a-real-palette'})
    with pytest.raises(PrintTemplateValidationError, match='Wochenlayout'):
        render(config={**default_config(), 'layout': default_layout('staff_guest')})


def test_render_is_deterministic():
    detail = _detail()
    assert render(detail) == render(detail)


def test_unsupported_character_raises_shopping_pdf_error():
    with pytest.raises(ShoppingPdfError):
        render(_detail(title='🥕 Einkauf'))


def test_missing_selected_revision_raises():
    with pytest.raises(ShoppingPdfError):
        render(_detail(selected_revision=None))
