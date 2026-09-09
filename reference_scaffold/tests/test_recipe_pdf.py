"""Offline native PDF contracts for immutable, complete recipe output."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Inexact, localcontext
from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfReader

from cafeteria.admin.recipe_pdf import RECIPE_MARGINS, RecipePdfError, render_recipe_pdf
from cafeteria.print_branding import PdfBranding
from cafeteria.print_template_config import default_config, default_layout
from cafeteria.recipe_snapshots import frozen_json
from cafeteria.recipe_types import RecipeAssetDTO, RecipeConfigurationError, RecipeRevisionDTO


def recipe():
    return {
        'title': 'Gemüsesuppe mit Gartenkräutern', 'description': 'Frisch gekocht.\n\nBehutsam abschmecken.',
        'servings': '4', 'servings_unit_code': 'PORTION', 'prep_minutes': 10, 'cook_minutes': 25,
        'source': {'kind': 'manual', 'reference': 'Küchenbuch Herbst', 'url': None,
                   'note': 'Originalbeleg der ausgewählten Revision', 'fetched_at': None},
        'ingredients': [
            {'line_public_id': None, 'group_label': 'Suppe', 'ingredient_text': 'Karotten',
             'food_public_id': None, 'quantity': '0.125', 'unit_code': 'KG', 'note': 'Fein schneiden',
             'source_kind': 'manual', 'source_reference': None, 'fetched_at': None},
            {'line_public_id': None, 'group_label': 'Zum Abschmecken', 'ingredient_text': 'Salz',
             'food_public_id': None, 'quantity': None, 'unit_code': None, 'note': 'Nach Geschmack',
             'source_kind': 'manual', 'source_reference': None, 'fetched_at': None},
        ],
        'steps': [{'instruction': 'Gemüse waschen.\nSchonend garen.', 'duration_minutes': 0, 'image_sha256': None}],
        'tag_public_ids': ['00000000-0000-0000-0000-000000000099'], 'images': [],
    }


def revision(payload=None, **changes):
    return RecipeRevisionDTO(
        '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', 3,
        'a' * 64, frozen_json({'schema_version': 1, 'recipe': recipe() if payload is None else payload,
                             'foods': [{'name': 'FOREIGN LIVE NAME'}], 'units': [], **changes}),
        datetime(2026, 9, 8, tzinfo=timezone.utc), 1,
    )


def asset(color='green'):
    output = BytesIO()
    Image.new('RGB', (160, 100), color).save(output, format='PNG')
    data = output.getvalue()
    return RecipeAssetDTO(hashlib.sha256(data).hexdigest(), data, 'image/png', 160, 100)


def render(value=None, **kwargs):
    return render_recipe_pdf(revision() if value is None else value,
                             config=kwargs.pop('config', default_config()), images=kwargs.pop('images', {}), **kwargs)


def text(data):
    return ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages).split())


def test_decimal_yield_preserves_missing_quantities_units_and_original_inputs():
    source = recipe()
    before = copy.deepcopy(source)
    selected = revision(source)
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        data = render(selected, target='6')
    body = text(data)
    assert 'Original: 4 PORTION · Gewünscht: 6 PORTION' in body
    assert '0.1875 KG · Karotten' in body
    assert 'Salz Nach Geschmack' in body and '0 KG' not in body and 'None' not in body
    assert 'Allergenangaben in dieser Revision nicht erfasst' in body
    assert 'FOREIGN LIVE NAME' not in body and 'allergenfrei' not in body
    assert 'Vorbereitung: 10 Min.' in body and 'Zubereitung: 25 Min.' in body and 'Schritt 1 · 0 Min.' in body
    assert body.index('Suppe 0.1875') < body.index('Zum Abschmecken') < body.index('Schritt 1')
    assert source == before
    assert data == render(selected, target='6')
    assert render(selected) == render(selected, target='4')


@pytest.mark.parametrize('size,minimum', [('auto', 11), ('standard', 11), ('large', 12)])
def test_complete_multipage_text_and_provenance_remain_readable(size, minimum, tmp_path):
    source = recipe()
    expected = []
    for number in range(6):
        words = [f'Arbeit{number}Absatz{index:03d}' for index in range(260)]
        expected.extend(words)
        source['steps'].append({'instruction': '\n\n'.join(' '.join(words[i:i + 65]) for i in range(0, 260, 65)),
                                'duration_minutes': number, 'image_sha256': None})
    source['ingredients'][0]['ingredient_text'] = 'Langzutat ' * 49
    source['ingredients'][0].update(source_kind='file_import', source_reference='Beleg Zutat Ende',
                                    fetched_at='2026-09-01T12:00:00Z', note='Zutatenhinweis ' * 30)
    source['source'].update(kind='file_import', reference='Rezeptbeleg Ende', note='Quellenhinweis ' * 30,
                            fetched_at='2026-09-01T12:00:00Z')
    data = render(revision(source), config={**default_config(), 'text_size': size,
                                          'footer_text': 'Vollständige Rezeptrevision'})
    reader = PdfReader(BytesIO(data))
    assert len(reader.pages) >= 4
    body = text(data)
    assert all(body.count(word) == 1 for word in expected)
    assert body.count('Zutatenhinweis') == 30 and body.count('Quellenhinweis') == 30
    assert 'Rezeptbeleg Ende' in body and 'Beleg Zutat Ende' in body
    assert body.count('2026-09-01T12:00:00Z') == 2
    path = tmp_path / 'complete.pdf'
    path.write_bytes(data)
    boxes = subprocess.run(['rtk', 'pdftotext', '-bbox', str(path), '-'], capture_output=True, text=True, check=True)
    for node in ET.fromstring(boxes.stdout).findall('.//{http://www.w3.org/1999/xhtml}word'):
        x0, y0, x1, y1 = (float(node.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax'))
        assert 47 <= x0 < x1 <= 548 and 0 < y0 < y1 < 842
    for number, page in enumerate(reader.pages, 1):
        assert f'Seite {number}' in page.extract_text()
        sizes = []
        page.extract_text(visitor_text=lambda value, cm, tm, font, point: sizes.append(point) if value.strip() else None)
        assert min(sizes) >= minimum
        assert float(page.mediabox.width) == pytest.approx(595.28, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(841.89, abs=0.01)


def test_only_selected_gallery_and_step_hashes_are_rendered_with_frozen_provenance():
    gallery, step, foreign = asset(), asset('red'), asset('blue')
    source = recipe()
    source['images'] = [{'sha256': gallery.sha256, 'caption': 'Historisches Foto',
                         'source_url': 'https://example.invalid/archiv', 'source_license': 'Historische Lizenz',
                         'fetched_at': '2026-09-01T12:00:00Z'}]
    source['steps'][0]['image_sha256'] = step.sha256
    supplied = {item.sha256: item for item in (gallery, step, foreign)}
    selected = revision(source)
    data = render(selected, images=supplied, config={**default_config(), 'logo': 'none'})
    assert data == render(selected, images={gallery.sha256: gallery, step.sha256: step},
                          config={**default_config(), 'logo': 'none'})
    assert text(data).count('https://example.invalid/archiv') == 1
    assert text(data).count('Historische Lizenz') == 1
    assert 'Historisches Foto' in text(data)
    embedded = [image.image for page in PdfReader(BytesIO(data)).pages for image in page.images]
    colors = {image.convert('RGB').getpixel((0, 0)) for image in embedded}
    assert colors == {(0, 128, 0), (255, 0, 0)}
    for required in (gallery, step):
        with pytest.raises(RecipePdfError, match='fehlt'):
            render(selected, images={key: value for key, value in supplied.items() if key != required.sha256})


@pytest.mark.parametrize('change', ['bytes', 'hash', 'mime', 'width', 'corrupt'])
def test_required_asset_validation_never_omits_bad_images(change):
    image = asset()
    source = recipe()
    source['steps'][0]['image_sha256'] = image.sha256
    bad = {'bytes': replace(image, data=asset('red').data), 'hash': replace(image, sha256='b' * 64),
           'mime': replace(image, content_type='image/jpeg'), 'width': replace(image, width=161),
           'corrupt': replace(image, data=b'not an image')}[change]
    with pytest.raises((RecipePdfError, RecipeConfigurationError)):
        render(revision(source), images={image.sha256: bad})


def test_brand_fonts_logo_colors_and_revision_are_part_of_resolved_identity():
    brand = PdfBranding(7, (140, 28, 75), (53, 102, 111), (255, 255, 255), (32, 50, 51),
                       'carlito', 'fira', asset().data)
    config = {**default_config(), 'palette': 'active_brand', 'font': 'active_brand', 'logo': 'active_brand'}
    data = render(config=config, branding=brand)
    reader = PdfReader(BytesIO(data))
    metadata = reader.metadata
    assert metadata.creation_date == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert revision().public_id in metadata.subject and 'a' * 64 in metadata.subject
    assert 'Markenrevision 7' in metadata.subject
    assert render(config=config, branding=replace(brand, revision_id=8)) != data
    assert render(branding=brand) == render()
    fonts = [str(font.get_object()['/BaseFont']) for font in reader.pages[0]['/Resources']['/Font'].values()]
    assert any('Carlito' in font for font in fonts) and any('FiraSans' in font for font in fonts)
    assert list(reader.pages[0].images)[0].image.size == (160, 100)
    colors = [tuple(float(value) for value in values) for values, operation in reader.pages[0].get_contents().operations if operation == b'rg']
    for color in (brand.primary, brand.text):
        assert any(actual == pytest.approx(tuple(value / 255 for value in color), abs=0.001) for actual in colors)
    with pytest.raises(RecipeConfigurationError, match='geladen'):
        render(config=config)
    with pytest.raises(RecipeConfigurationError):
        render(config=config, branding=replace(brand, font_body='../private'))


@pytest.mark.parametrize('has_logo', [False, True])
@pytest.mark.parametrize('has_photos', [False, True])
def test_active_brand_logo_absence_never_substitutes_a_legacy_logo(has_logo, has_photos):
    gallery, step, logo = asset(), asset('red'), asset('blue')
    brand = PdfBranding(7, (140, 28, 75), (53, 102, 111), (255, 255, 255), (32, 50, 51),
                       'carlito', 'fira', logo.data if has_logo else None)
    source = recipe()
    if has_photos:
        source['images'] = [{'sha256': gallery.sha256, 'caption': 'Rezeptfoto',
                             'source_url': None, 'source_license': None, 'fetched_at': None}]
        source['steps'][0]['image_sha256'] = step.sha256
    config = {**default_config(), 'logo': 'active_brand'}
    data = render(revision(source), config=config, branding=brand,
                  images={item.sha256: item for item in (gallery, step)})
    embedded = [image.image for page in PdfReader(BytesIO(data)).pages for image in page.images]
    assert len(embedded) == int(has_logo) + (2 if has_photos else 0)
    expected = ({(0, 128, 0), (255, 0, 0)} if has_photos else set()) | ({(0, 0, 255)} if has_logo else set())
    assert {image.convert('RGB').getpixel((0, 0)) for image in embedded} == expected
    with pytest.raises(RecipeConfigurationError, match='geladen'):
        render(revision(source), config=config)


@pytest.mark.parametrize('field,value', [('palette', 'teal'), ('font', 'fira'), ('text_size', 'large'),
    ('logo', 'none'), ('logo', 'wordmark'), ('margin', 'wide'), ('margin', 'wider'),
    ('spacing', 'roomy'), ('header_text', 'Küchenrezept'), ('footer_text', 'Nur diese Revision')])
def test_every_recipe_property_has_a_native_consumer(field, value):
    data = render(config={**default_config(), field: value})
    assert data != render()
    assert 'Gemüsesuppe mit Gartenkräutern' in text(data)
    if field in ('header_text', 'footer_text'):
        assert value in text(data)
    if field == 'margin':
        positions = []
        PdfReader(BytesIO(data)).pages[0].extract_text(
            visitor_text=lambda value, cm, tm, font, size: positions.append(tm[4]) if value.strip() else None)
        assert min(positions) == RECIPE_MARGINS[value]


@pytest.mark.parametrize('version', [None, True, 1.0, '1', 3])
def test_unsupported_snapshot_versions_fail_closed(version):
    with pytest.raises(RecipeConfigurationError, match='nicht unterstützt'):
        render(revision(schema_version=version))


def test_v2_without_original_canonical_evidence_fails_closed():
    with pytest.raises(RecipeConfigurationError):
        render(revision(schema_version=2))


def prepared_revision():
    """Self-consistent offline DTO; real PostgreSQL canonical equivalence has separate DB tests."""
    def recorded(public_id, recipe_id, body, children=()):
        raw = json.dumps(body, ensure_ascii=False)
        return RecipeRevisionDTO(public_id, recipe_id, 1, hashlib.sha256(raw.encode()).hexdigest(),
            frozen_json(body), datetime(2026, 9, 9, tzinfo=timezone.utc), 1, children, raw)
    units = [{'public_id': f'00000000-0000-0000-0000-{number:012d}', 'code': code,
              'display_name': code, 'dimension': dimension, 'base_factor': factor}
             for number, (code, dimension, factor) in enumerate(
                 [('G', 'mass', '1'), ('KG', 'mass', '1000'), ('PORTION', 'contextual', None)], 10)]
    calculation = {'precision': 50, 'rounding': 'ROUND_HALF_UP', 'quantity_places': 6,
                   'bases': {'mass': 'G', 'volume': 'ML', 'count': 'STK'}, 'contextual': 'same-code-only'}
    child_recipe = recipe()
    child_recipe.update(title='Erfasste Gemüsebasis', servings='3', servings_unit_code='KG', images=[])
    child_recipe['ingredients'] = [dict(child_recipe['ingredients'][0], quantity='1', unit_code='G')]
    child = recorded('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000004',
        {'schema_version': 1, 'recipe': child_recipe, 'calculation': calculation, 'units': units, 'foods': []})
    pin = {'recipe_public_id': child.recipe_public_id, 'revision_public_id': child.public_id,
           'content_hash_sha256': child.content_hash_sha256}
    food_id = '00000000-0000-0000-0000-000000000005'
    parent = recipe()
    parent.update(title='Teller mit Zubereitung', servings='3')
    parent['ingredients'] = [dict(parent['ingredients'][0], ingredient_text='Gemüsemischung',
        food_public_id=food_id, quantity='1', unit_code='G')] * 2
    # JSON-compatible source body is retained separately from the immutable DTO.
    child_body = json.loads(child.canonical_snapshot_text)
    return recorded('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002',
        {'schema_version': 2, 'recipe': parent, 'calculation': calculation, 'units': units,
         'foods': [{'public_id': food_id, 'name': 'Gemüsemischung', 'density_g_per_ml': None,
                    'piece_weight_g': None, 'prepared_recipe': pin, 'base_unit': units[0],
                    'storage_locations': []}],
         'prepared_revisions': [{**pin, 'snapshot': child_body}]}, (child,))


def test_v2_repeated_preparation_preserves_each_amount_and_prints_full_steps_once():
    selected = prepared_revision()
    data = render(selected, target='2')
    body = text(data)
    assert body.count('Erfasste Gemüsebasis') == 2
    assert body.count('Gemüse waschen.') == 2  # Parent plus first full child; repeated use points back.
    assert 'Arbeitsschritte, Bilder und Herkunft stehen bei der ersten Ausgabe' in body
    assert '0.00022222222222222222222222222222222222222222222222222 G' in body
    assert data == render(selected, target='2')


@pytest.mark.parametrize('field,value', [('title', '🥜'), ('description', 'Text\x00'),
    ('servings', '0'), ('steps', [{'instruction': 'Text', 'duration_minutes': 0}]), ('images', [{}])])
def test_bad_stored_data_and_unsupported_glyphs_are_controlled(field, value):
    source = recipe()
    source[field] = value
    with pytest.raises((RecipePdfError, RecipeConfigurationError)):
        render(revision(source))


@pytest.mark.parametrize('target', ['0', 'NaN', 'Infinity', '-1', '1.0000001', 'SECRET_SENTINEL'])
def test_bad_target_has_bounded_error_without_echo(target):
    with pytest.raises(RecipeConfigurationError) as error:
        render(target=target)
    assert target not in str(error.value)
    with pytest.raises(RecipeConfigurationError):
        render(config={**default_config(), 'layout': default_layout('staff_guest')})


@pytest.mark.parametrize('field,label', [('text', 'Textfarbe'), ('primary', 'Überschriftenfarbe')])
def test_white_paper_contrast_checks_only_selected_text_colors(field, label):
    brand = PdfBranding(7, (140, 28, 75), (255, 255, 255), (0, 0, 0), (32, 50, 51),
                       'carlito', 'fira', asset().data)
    pale = replace(brand, **{field: (240, 240, 240)})
    with pytest.raises(RecipeConfigurationError, match=label):
        render(config={**default_config(), 'palette': 'active_brand'}, branding=pale)
    assert render(config={**default_config(), 'logo': 'active_brand'}, branding=pale)
    assert render(config={**default_config(), 'palette': 'active_brand'}, branding=brand)


def test_maximum_unbroken_footer_text_never_overlaps_or_adds_blank_pages():
    data = render(config={**default_config(), 'footer_text': 'W' * 160, 'header_text': 'H' * 72,
                          'margin': 'wider', 'font': 'fira', 'text_size': 'large'})
    reader = PdfReader(BytesIO(data))
    assert len(reader.pages) <= 2
    for page in reader.pages:
        assert page.extract_text().replace('\n', '').count('W' * 160) == 1
        positions = []
        page.extract_text(visitor_text=lambda value, cm, tm, font, size: positions.append(tm[5]) if value.strip() else None)
        assert min(positions) >= 12
