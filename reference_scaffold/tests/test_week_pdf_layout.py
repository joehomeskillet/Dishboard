"""Actual native PDFs prove layout geometry, complete content and safe local photos."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import timedelta
from io import BytesIO

import pytest
from pypdf import PdfReader

from cafeteria.admin.week_pdf import ASSETS, WeekPdfFitError, render_week_pdf
from cafeteria.admin.week_pdf_layout import Field, _check_fields
from cafeteria.print_template_config import default_config, default_layout
from test_week_pdf import WEEK, saved_week
from test_print_branding_pdf import BRAND, INHERIT


def config(profile, **choices):
    return {**default_config(), 'layout': {**default_layout(profile), **choices}}


def page(payload):
    reader = PdfReader(BytesIO(payload))
    assert len(reader.pages) == 1
    return reader.pages[0]


def geometry(payload, path):
    result_page = page(payload)
    width, height = float(result_page.mediabox.width), float(result_page.mediabox.height)
    assert sorted((width, height)) == pytest.approx([595.28, 841.89], abs=0.02)
    sizes = []
    result_page.extract_text(visitor_text=lambda text, cm, tm, font, size: sizes.append(size) if text.strip() else None)
    assert min(sizes) >= 8.5
    path.write_bytes(payload)
    result = subprocess.run(['pdftotext', '-bbox', str(path), '-'], capture_output=True, text=True, check=True)
    words = ET.fromstring(result.stdout).findall('.//{http://www.w3.org/1999/xhtml}word')
    boxes = [tuple(float(word.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax')) for word in words]
    assert boxes
    for index, (x1, y1, x2, y2) in enumerate(boxes):
        assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
        for a1, b1, a2, b2 in boxes[index + 1:]:
            assert min(x2, a2) - max(x1, a1) < 0.2 or min(y2, b2) - max(y1, b1) < 0.2
    transforms = []
    result_page.extract_text(visitor_operand_before=lambda op, args, cm, tm: transforms.append(cm) if op == b'Do' else None)
    for a, b, c, d, e, f in transforms:
        assert b == c == 0
        x1, y1, x2, y2 = e, height - f - d, e + a, height - f
        assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
        for a1, b1, a2, b2 in boxes:
            assert min(x2, a2) - max(x1, a1) < 0.2 or min(y2, b2) - max(y1, b1) < 0.2
    return words


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('grid', ['days_rows', 'days_columns'])
def test_complete_native_layout_has_all_slots_and_readable_geometry(profile, grid, tmp_path):
    draft = saved_week(profile, False)
    before = copy.deepcopy(draft)
    payload = render_week_pdf(draft, profile, WEEK, config(profile, grid=grid))
    body = ' '.join(page(payload).extract_text().split())
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                # Narrow day columns can wrap inside a long word; every character survives.
                assert ''.join(option['title'].split()) in ''.join(body.split())
                assert all(''.join(component.split()) in ''.join(body.split()) for component in option['components'])
    assert body.count('Allergenangaben nicht erfasst') == (29 if profile == 'patient' else 11)
    assert 'KW 36' in body
    if profile == 'patient':
        assert re.search(r'preis|chf|rappen|kosten|price', body, re.I) is None
        assert 'SONNTAG' in body and 'Abend' in body
    else:
        assert body.count('Intern: 11.00 CHF') == 10
        assert body.count('Extern: 16.60 CHF') == 10
    geometry(payload, tmp_path / f'{profile}-{grid}.pdf')
    assert draft == before


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('field,value', [
    ('grid', 'days_columns'), ('alignment', 'center'), ('day_label_width', 'compact'),
    ('day_label_width', 'wide'), ('row_spacing', 'compact'), ('row_spacing', 'roomy'),
    ('legend_position', 'top'), ('header', ['title', 'date_range', 'week_number', 'header_note', 'logo']),
    ('footer', ['footer_note', 'service_notes']),
])
def test_layout_controls_change_visible_geometry(profile, field, value, tmp_path):
    draft = saved_week(profile, False)
    base = config(profile)
    base['header_text'] = 'Guten Appetit'
    base['footer_text'] = 'Eine gute Woche'
    changed = copy.deepcopy(base)
    if field == 'grid':
        value = 'days_rows' if base['layout']['grid'] == 'days_columns' else 'days_columns'
    changed['layout'][field] = value
    baseline = render_week_pdf(draft, profile, WEEK, base)
    payload = render_week_pdf(draft, profile, WEEK, changed)
    assert page(baseline).get_contents().get_data() != page(payload).get_contents().get_data()
    geometry(payload, tmp_path / f'{profile}-{field}-{str(value)[:8]}.pdf')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_field_reordering_preserves_distinct_notes_and_declarations(profile, tmp_path):
    draft = saved_week(profile, False)
    option = draft['days'][0]['services'][0]['options'][0]
    option.update(description='Sorgfältig zubereitet', note='Getrennte Zubereitung',
                  labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
                  origins=[{'country_code': 'CH', 'text': 'Kartoffeln: Schweiz'}],
                  allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
                             {'code': 'EGGS', 'name': 'Eier', 'presence': 'may_contain'}])
    chosen = config(profile)
    chosen['layout']['menu_fields'].reverse()
    payload = render_week_pdf(draft, profile, WEEK, chosen)
    body = ' '.join(page(payload).extract_text().split())
    for expected in ('Sorgfältig zubereitet', 'Getrennte Zubereitung', 'Vegetarisch', 'Kartoffeln: Schweiz',
                     'Enthält: Milch', 'Kann enthalten: Eier', 'Allergenprüfung offen', 'Legende der gedruckten Menüs'):
        assert expected in body
    geometry(payload, tmp_path / f'{profile}-reordered.pdf')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('font', ['carlito', 'fira'])
def test_local_photos_show_all_real_menu_slots_and_caption(profile, font, tmp_path):
    draft = saved_week(profile, False)
    # Exact composition match is the same controlled catalogue binding as public screens.
    images = [row for row in json.loads((ASSETS / 'img/menus/manifest.json').read_text()) if row['status'] == 'ready']
    count = 0
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                image = images[count % len(images)]
                option.update(title=image['title'], components=image['components'], note=f'MENUNUMMER{count:02d}')
                count += 1
    grid = 'days_columns' if profile == 'patient' else 'days_rows'
    chosen = config(profile, photo='small', grid=grid)
    chosen['font'] = font
    payload = render_week_pdf(draft, profile, WEEK, chosen)
    body = ' '.join(page(payload).extract_text().split())
    assert all(body.count(f'MENUNUMMER{index:02d}') == 1 for index in range(count))
    assert 'KI-generierte Serviervorschläge' in body
    assert len(page(payload).images) >= 2
    path = tmp_path / f'{profile}-photos-small.pdf'
    words = geometry(payload, path)
    transforms = []
    result_page = page(payload)
    result_page.extract_text(visitor_operand_before=lambda op, args, cm, tm: transforms.append(cm) if op == b'Do' else None)
    assert len(transforms) == count + 1  # One header logo, then every menu photo.
    gaps = []
    for a, b, c, d, e, f in transforms[1:]:
        photo_top = float(result_page.mediabox.height) - f - d
        for word in words:
            left, bottom, right = (float(word.attrib[key]) for key in ('xMin', 'yMax', 'xMax'))
            if min(e + a, right) > max(e, left) and bottom <= photo_top:
                gaps.append(photo_top - bottom)
    assert min(gaps) >= 2.0
    subprocess.run(['pdftoppm', '-singlefile', '-scale-to', '1600', '-png', str(path), str(path.with_suffix(''))], check=True, capture_output=True)
    assert path.with_suffix('.png').stat().st_size > 10000
    hidden = render_week_pdf(draft, profile, WEEK, config(profile, photo='none', grid=grid))
    assert len(page(hidden).images) == 1
    assert 'Serviervorschläge' not in page(hidden).extract_text()


def test_new_patient_layout_defaults_fit_complete_week_with_service_metadata(tmp_path):
    draft = saved_week('patient', False)
    draft['area_name'] = 'Therapie und Rehabilitation'
    for day in draft['days']:
        for service in day['services']:
            lunch = service['meal_code'] == 'LUNCH'
            service.update(service_start='11:45' if lunch else '17:40',
                           service_end='13:15' if lunch else '18:20')
    draft['days'][0]['services'][0]['options'][0].update(
        description='Sorgfältig zubereitet', note='Getrennte Zubereitung',
        labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
        origins=[{'country_code': 'CH', 'text': 'Kartoffeln: Schweiz'}],
        allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
                   {'code': 'EGGS', 'name': 'Eier', 'presence': 'may_contain'}])
    chosen = config('patient')
    payload = render_week_pdf(draft, 'patient', WEEK, chosen)
    body = ''.join(page(payload).extract_text().split())
    expected = ['Therapie und Rehabilitation', '11:45–13:15', '17:40–18:20',
                'Enthält: Milch', 'Kann enthalten: Eier', 'Allergenprüfung offen',
                'Kartoffeln: Schweiz', 'Sorgfältig zubereitet', 'Getrennte Zubereitung']
    expected.extend(option['title'] for day in draft['days']
                    for service in day['services'] for option in service['options'])
    assert all(''.join(value.split()) in body for value in expected)
    assert chosen['layout']['grid'] == 'days_columns'
    assert default_layout('staff_guest')['grid'] == 'days_rows'
    assert 'layout' not in default_config()
    geometry(payload, tmp_path / 'patient-default-complete.pdf')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_unknown_photo_does_not_guess_or_fetch_submitted_locations(profile):
    draft = saved_week(profile, False)
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option['title'] = 'Nicht im Bildkatalog'
    chosen = config(profile, photo='small')
    baseline = render_week_pdf(draft, profile, WEEK, chosen)
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option.update(image='file:///etc/passwd', image_url='http://127.0.0.1:9/private', image_path='/etc/passwd')
    assert render_week_pdf(draft, profile, WEEK, chosen) == baseline
    assert 'Serviervorschläge' not in page(baseline).extract_text()


@pytest.mark.parametrize('grid', ['days_rows', 'days_columns'])
def test_weekend_membership_times_and_closed_notice_survive(grid, tmp_path):
    draft = saved_week('staff_guest', False)
    for offset in (5, 6):
        day = copy.deepcopy(draft['days'][0])
        day['date'] = (WEEK + timedelta(days=offset)).isoformat()
        day['services'][0]['options'][0]['title'] = f'Wochenendmenü {offset}'
        draft['days'].append(day)
    draft['days'][1]['services'][0].update(service_state='closed', notice='Betriebsruhe')
    payload = render_week_pdf(draft, 'staff_guest', WEEK, config('staff_guest', grid=grid))
    body = ' '.join(page(payload).extract_text().split())
    assert all(''.join(value.split()) in ''.join(body.split()) for value in
               ('SAMSTAG', 'SONNTAG', 'Wochenendmenü 5', 'Wochenendmenü 6', 'Betriebsruhe'))
    geometry(payload, tmp_path / f'weekend-{grid}.pdf')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_overflow_names_saved_date_meal_type_and_block(profile):
    draft = saved_week(profile, False)
    draft['days'][0]['services'][0]['options'][0]['note'] = 'Vollständige wichtige Deklaration. ' * 200
    with pytest.raises(WeekPdfFitError, match=r'2026-08-31.*Mittag.*Menü 1.*Komponenten.*A4-Seite'):
        render_week_pdf(draft, profile, WEEK, config(profile))


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_unsupported_glyph_remains_an_explicit_block_error(profile):
    draft = saved_week(profile, False)
    draft['days'][0]['services'][0]['options'][0]['note'] = '🥜'
    with pytest.raises(WeekPdfFitError, match=r'2026-08-31.*Komponenten.*Druckschrift'):
        render_week_pdf(draft, profile, WEEK, config(profile))


@pytest.mark.parametrize('field,label', [
    ('header_text', 'Kopfbereich · Zusatz im Kopfbereich'),
    ('footer_text', 'Fussbereich · Zusatz in der Fusszeile'),
    ('area_name', 'Kopfbereich · Titel'),
    ('notice', 'Fussbereich · Essenszeiten und Hinweise'),
])
def test_header_footer_glyph_errors_use_editor_labels(field, label):
    draft = saved_week('staff_guest', False)
    chosen = config('staff_guest')
    if field == 'area_name':
        draft[field] = '🥜'
    elif field == 'notice':
        draft['days'][0]['services'][0][field] = '🥜'
    else:
        chosen[field] = '🥜'
    with pytest.raises(WeekPdfFitError, match=rf'{label}:.*Druckschrift'):
        render_week_pdf(draft, 'staff_guest', WEEK, chosen)


@pytest.mark.parametrize('field,context,label', [
    ('image', '2026-08-31 · Mittag · Vegetarisch', 'Menübild'),
    ('logo', 'Kopfbereich', 'Logo'),
])
def test_out_of_bounds_image_names_its_visible_field(field, context, label):
    with pytest.raises(WeekPdfFitError, match=rf'{context} · {label}:.*A4-Seite'):
        _check_fields([Field(field, 0, 0, 20, 20)], 10, 10, context)


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_medium_photo_choice_changes_actual_image_geometry(profile, tmp_path):
    draft = saved_week(profile, False)
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option['title'] = 'Tagesangebot'
    image = next(row for row in json.loads((ASSETS / 'img/menus/manifest.json').read_text()) if row['status'] == 'ready')
    draft['days'][0]['services'][0]['options'][0].update(title=image['title'], components=image['components'])
    small = render_week_pdf(draft, profile, WEEK, config(profile, photo='small', grid='days_columns'))
    medium = render_week_pdf(draft, profile, WEEK, config(profile, photo='medium', grid='days_columns'))
    assert page(small).get_contents().get_data() != page(medium).get_contents().get_data()
    geometry(medium, tmp_path / f'{profile}-medium.pdf')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_layout_inherits_brand_fonts_logo_and_contrasting_surface(profile, tmp_path):
    draft = saved_week(profile, False)
    draft['days'][0]['services'][0]['options'][0]['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    chosen = {**INHERIT, 'layout': default_layout(profile)}
    dark = replace(BRAND, primary=(255, 255, 255), surface=(20, 20, 20), text=(240, 240, 240))
    payload = render_week_pdf(draft, profile, WEEK, chosen, branding=dark)
    result_page = page(payload)
    assert result_page.images[0].image.size == (40, 20)
    fonts = [str(font.get_object()['/BaseFont']) for font in result_page['/Resources']['/Font'].values()]
    assert any('Carlito' in name for name in fonts) and any('FiraSans' in name for name in fonts)
    rectangles = [values for values, operator in result_page.get_contents().operations if operator == b're']
    assert any(float(values[2]) == pytest.approx(float(result_page.mediabox.width), abs=0.02)
               and abs(float(values[3])) == pytest.approx(float(result_page.mediabox.height), abs=0.02) for values in rectangles)
    white = [values for values, operator in result_page.get_contents().operations if operator == b'rg' and list(values) == [1, 1, 1]]
    assert len(white) >= 2  # Actual menu and legend icon backgrounds.
    geometry(payload, tmp_path / f'{profile}-brand.pdf')
    assert render_week_pdf(draft, profile, WEEK, config(profile), branding=dark) == render_week_pdf(draft, profile, WEEK, config(profile))
