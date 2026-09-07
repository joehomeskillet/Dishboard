from io import BytesIO
import json

from fpdf import FPDF
from pypdf import PdfReader

from cafeteria.admin.week_pdf_symbols import ASSETS, draw_symbols, measure_symbols, origin_text
from cafeteria.food_symbols import food_symbol


def test_all_audited_compatible_symbols_render_with_native_fpdf(caplog):
    manifest = json.loads((ASSETS / 'vendor/food-symbols/manifest.json').read_text())
    option = {
        'allergens': [{'code': code, 'presence': 'contains'} for code in manifest['allergens']],
        'origins': [{'country_code': code} for code in manifest['countries']],
        'labels': [{'code': code} for code in manifest['labels']],
    }
    strip = measure_symbols(option, 550)
    marks = [mark for row in strip.rows for mark in row]
    assert len(marks) == 14 + 249 - 21 + 2
    assert all(mark.symbol.pdf_filename is not None for mark in marks)
    pdf = FPDF(unit='pt', format='A4')
    pdf.add_page()
    draw_symbols(pdf, strip, 20, 20)
    page = PdfReader(BytesIO(bytes(pdf.output()))).pages[0]
    assert len(page.get_contents().operations) > 1000
    assert 20 + strip.height < float(page.mediabox.height)
    assert not [record for record in caplog.records if record.levelname in ('WARNING', 'ERROR')]


def test_all_21_incompatible_flags_use_country_text_without_pdf_image():
    manifest = json.loads((ASSETS / 'vendor/food-symbols/manifest.json').read_text())
    incompatible = [food_symbol(code, 'countries') for code in manifest['countries']
                    if food_symbol(code, 'countries').pdf_filename is None]
    assert len(incompatible) == 21
    for symbol in incompatible:
        origin = {'country_code': symbol.code, 'text': 'Zutat: deklarierte Herkunft'}
        assert origin_text(origin) == f'Zutat: deklarierte Herkunft ({symbol.name})'
        assert origin_text({'country_code': symbol.code, 'text': symbol.name}) == symbol.name
        assert measure_symbols({'origins': [origin]}, 100).height == 0


def test_duplicate_allergen_presence_does_not_repeat_menu_icon():
    strip = measure_symbols({'allergens': [
        {'code': 'MILK', 'presence': 'contains'}, {'code': 'MILK', 'presence': 'may_contain'},
    ]}, 100)
    assert [mark.symbol.code for row in strip.rows for mark in row] == ['MILK']


def test_monochrome_allergen_uses_black_ink_and_restores_table_colors():
    pdf = FPDF(unit='pt', format='A4')
    pdf.add_page()
    pdf.set_fill_color(222, 234, 246)
    pdf.set_draw_color(174, 170, 170)
    original = pdf.fill_color, pdf.draw_color
    strip = measure_symbols({'allergens': [{'code': 'MILK', 'presence': 'contains'}]}, 100)
    draw_symbols(pdf, strip, 20, 20)
    assert (pdf.fill_color, pdf.draw_color) == original
    page = PdfReader(BytesIO(bytes(pdf.output()))).pages[0]
    operations = page.get_contents().operations
    assert any(operator == b'g' and args == [0] for args, operator in operations)
