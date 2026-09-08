from __future__ import annotations

import csv
import hashlib
import io
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Inexact, Rounded, localcontext
from typing import Any

import pytest


WHEN = datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc)
HEADER = ['schema_version', 'title', 'description', 'servings', 'servings_unit_code',
          'prep_minutes', 'cook_minutes', 'source_url', 'source_note', 'ingredients', 'steps']


def recipe(title: str = 'Kartoffelsuppe') -> dict[str, Any]:
    return {
        'title': title, 'description': 'Frisch; gekocht.\nWarm servieren.',
        'servings': '4.000000', 'servings_unit_code': 'PORTION', 'prep_minutes': 10,
        'cook_minutes': None, 'source_url': 'https://example.invalid/rezept',
        'source_note': 'Eigene Aufzeichnung',
        'ingredients': [{'group_label': None, 'ingredient_text': 'Kartoffeln',
                         'quantity': '0.750000', 'unit_code': 'KG', 'note': None}],
        'steps': [{'instruction': 'Kartoffeln garen.\nDann servieren.', 'duration_minutes': 20}],
    }


def json_bytes(*rows: object) -> bytes:
    return json.dumps({'schema_version': 1, 'recipes': rows}, ensure_ascii=False).encode()


def csv_bytes(*rows: dict[str, Any], steps_cell: str | None = None) -> bytes:
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';', lineterminator='\n')
    writer.writerow(HEADER)
    for row in rows:
        values = []
        for key in HEADER[1:]:
            value = row[key]
            if key in ('ingredients', 'steps'):
                value = steps_cell if key == 'steps' and steps_cell is not None else json.dumps(value, ensure_ascii=False)
            values.append('' if value is None else value)
        writer.writerow(['1', *values])
    return stream.getvalue().encode()


def parse(data: bytes, mime: str = 'application/json', **kwargs: Any) -> Any:
    from cafeteria.recipe_import import parse_recipe_import

    return parse_recipe_import(data, filename=kwargs.pop('filename', 'rezepte.json'),
                               content_type=mime, fetched_at=kwargs.pop('fetched_at', WHEN), **kwargs)


def test_valid_recipe_keeps_exact_decimal_text_and_file_provenance() -> None:
    original = recipe()
    data = json_bytes(original)
    preview = parse(data)
    assert preview.is_valid and not preview.errors and len(preview.rows) == 1
    assert preview.source_filename == 'rezepte.json'
    assert preview.source_sha256 == hashlib.sha256(data).hexdigest()
    assert preview.fetched_at == '2026-09-08T12:30:00+00:00'
    row = preview.rows[0]
    assert row.row_number == 1 and row.source_line is None and not row.errors
    assert row.payload['servings'] == '4'
    assert row.payload['ingredients'][0]['quantity'] == '0.75'
    assert row.payload['ingredients'][0]['food_public_id'] is None
    assert row.payload['tag_public_ids'] == () and row.payload['images'] == ()
    source = row.payload['source']
    assert source['kind'] == 'file_import'
    assert source['reference'] == f'sha256:{preview.source_sha256}:row:1'
    assert source['url'] == 'https://example.invalid/rezept'
    assert preview.source_sha256 in source['note'] and 'Eigene Aufzeichnung' in source['note']
    assert row.payload['ingredients'][0]['source_kind'] == 'file_import'
    assert row.payload['ingredients'][0]['source_reference'] == source['reference']
    assert original == recipe()


@pytest.mark.parametrize('bom', [b'', b'\xef\xbb\xbf'])
def test_csv_multiline_order_and_logical_row_numbers(bom: bytes) -> None:
    one, two = recipe('Suppe'), recipe('Brot')
    data = bom + csv_bytes(one, two)
    preview = parse(data, 'text/csv', filename='rezepte.csv')
    assert preview.is_valid and len(preview.rows) == 2
    assert [r.row_number for r in preview.rows] == [1, 2]
    assert preview.rows[0].source_line == 2
    assert preview.rows[1].source_line == 4
    assert preview.rows[0].payload['description'] == 'Frisch; gekocht.\nWarm servieren.'
    assert preview.rows[1].payload['title'] == 'Brot'
    for row in preview.rows:
        assert row.payload['steps'][0]['instruction'] == 'Kartoffeln garen.\nDann servieren.'


def test_preview_is_deeply_immutable() -> None:
    preview = parse(json_bytes(recipe()))
    with pytest.raises(FrozenInstanceError):
        preview.source_filename = 'changed'
    payload = preview.rows[0].payload
    with pytest.raises(TypeError):
        payload['title'] = 'changed'
    with pytest.raises(TypeError):
        payload['ingredients'][0]['quantity'] = '99'
    with pytest.raises(TypeError):
        payload['steps'][0] = {}


@pytest.mark.parametrize('value', ['0', '-1', 'NaN', 'Infinity', '1,5', '0.0000001',
                                  '1000000000000', 1, 1.5, True, None])
def test_invalid_servings_never_produce_partial_success(value: object) -> None:
    bad = recipe('Fehlerhaft')
    bad['servings'] = value
    preview = parse(json_bytes(recipe(), bad))
    assert not preview.is_valid and len(preview.rows) == 2
    assert preview.rows[0].payload is not None
    assert preview.rows[1].payload is None
    assert any(e.field == 'servings' and e.row_number == 2 for e in preview.rows[1].errors)


def test_decimal_context_and_missing_ingredient_amount_are_preserved() -> None:
    row = recipe()
    row['servings'] = '999999999999.999999000'
    row['ingredients'][0].update(quantity=None, unit_code=None)
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = context.traps[Rounded] = True
        context.clear_flags()
        result = parse(json_bytes(row))
        assert result.is_valid
        assert result.rows[0].payload['servings'] == '999999999999.999999'
        assert result.rows[0].payload['ingredients'][0]['quantity'] is None
        assert not any(context.flags.values()) and context.prec == 2


@pytest.mark.parametrize(('field', 'value', 'path'), [
    ('title', '', 'title'), ('prep_minutes', True, 'prep_minutes'),
    ('cook_minutes', 1.5, 'cook_minutes'), ('cook_minutes', 10081, 'cook_minutes'),
    ('source_url', 'file:///etc/passwd', 'source_url'), ('source_note', 'x' * 401, 'source_note'),
    ('description', '<script>example</script>', 'description'),
])
def test_precise_field_errors_do_not_echo_untrusted_values(field: str, value: object, path: str) -> None:
    row = recipe()
    row[field] = value
    result = parse(json_bytes(row))
    assert not result.is_valid
    assert any(e.field == path for e in result.rows[0].errors)
    assert str(value) not in ' '.join(e.message for e in result.rows[0].errors) if len(str(value)) > 10 else True


@pytest.mark.parametrize('field', ['images', 'allergen_review_status', 'tag_public_ids', 'target_public_id'])
def test_unexpected_trusted_or_media_fields_are_rejected(field: str) -> None:
    row = recipe()
    row[field] = []
    result = parse(json_bytes(row))
    assert not result.is_valid and result.rows[0].payload is None


def test_invalid_nested_fields_have_exact_paths_and_no_partial_payload() -> None:
    row = recipe()
    row['ingredients'][0]['quantity'] = '0.0000001'
    row['steps'][0]['duration_minutes'] = False
    result = parse(json_bytes(row))
    assert not result.is_valid and result.rows[0].payload is None
    assert {e.field for e in result.rows[0].errors} == {'ingredients[0].quantity', 'steps[0].duration_minutes'}


def test_title_duplicates_remain_separate_even_when_one_row_is_invalid() -> None:
    invalid = recipe('  SUppE  ')
    invalid['servings'] = '0'
    result = parse(json_bytes(recipe('Suppe'), invalid, recipe('Brot')))
    assert not result.is_valid and len(result.rows) == 3
    assert len(result.duplicate_groups) == 1
    assert result.duplicate_groups[0].row_numbers == (1, 2)
    valid = parse(json_bytes(recipe('Suppe'), recipe('suppe')))
    assert valid.is_valid and valid.duplicate_groups[0].row_numbers == (1, 2)


@pytest.mark.parametrize('data', [b'', b'\xff', b'\x00', b'{}', b'[]',
                                b'{"schema_version":true,"recipes":[]}',
                                b'{"schema_version":1,"recipes":[]}',
                                b'{"schema_version":1,"schema_version":1,"recipes":[]}',
                                b'{"schema_version":1,"recipes":[NaN]}',
                                b'\xef\xbb\xbf{}'])
def test_invalid_json_files_fail_closed_without_rows(data: bytes) -> None:
    result = parse(data)
    assert not result.is_valid and result.errors and not result.rows


@pytest.mark.parametrize('mime', ['text/plain', 'application/json; charset=utf-8', 'text/csvx', '', None])
def test_exact_mime_boundary(mime: Any) -> None:
    result = parse(json_bytes(recipe()), mime)
    assert not result.is_valid and result.errors and not result.rows


@pytest.mark.parametrize('name', ['', '../rezepte.json', 'a\\b.csv', '.', '..', 'a\x00.json', 'x' * 201])
def test_filename_is_metadata_never_a_path(name: str) -> None:
    result = parse(json_bytes(recipe()), filename=name)
    assert not result.is_valid and result.errors and not result.rows


def test_file_and_record_bounds_do_not_silently_truncate() -> None:
    data = json_bytes(recipe())
    padded = data + b' ' * (5 * 1024 * 1024 - len(data))
    assert parse(padded).is_valid
    too_large = parse(padded + b' ')
    assert not too_large.is_valid and not too_large.rows
    rows = [recipe(f'Rezept {n}') for n in range(2000)]
    assert len(parse(json_bytes(*rows)).rows) == 2000
    excess = parse(json_bytes(*rows, recipe('Zuviel')))
    assert not excess.is_valid and not excess.rows


def test_nested_depth_and_duplicate_nested_keys_are_controlled() -> None:
    deep = b'{"schema_version":1,"recipes":' + b'[' * 13 + b']' * 13 + b'}'
    assert parse(deep).errors
    repeated = json_bytes(recipe()).replace(b'"title":', b'"title":"ignored","title":', 1)
    assert parse(repeated).errors
    text = recipe()
    text['steps'][0]['instruction'] = 'Klammern [ { und Escape \\ bleiben Text. ] }'
    assert parse(json_bytes(text)).is_valid


def test_csv_field_limit_counts_decoded_utf8_bytes_and_never_changes_global_limit() -> None:
    steps = [{'instruction': 'ö' * 4000, 'duration_minutes': None} for _ in range(10)]
    cell = json.dumps(steps, ensure_ascii=False)
    cell += ' ' * (120 * 1024 - len(cell.encode()))
    before = csv.field_size_limit()
    assert parse(csv_bytes(recipe(), steps_cell=cell), 'text/csv').is_valid
    too_large = parse(csv_bytes(recipe(), steps_cell=cell + ' '), 'text/csv')
    assert not too_large.is_valid and not too_large.rows and too_large.errors
    assert csv.field_size_limit() == before
    try:
        csv.field_size_limit(50)
        blocked = parse(csv_bytes(recipe()), 'text/csv')
        assert not blocked.is_valid and blocked.errors and not blocked.rows
        assert csv.field_size_limit() == 50
    finally:
        csv.field_size_limit(before)


def test_csv_broken_header_quoting_version_and_field_count_are_rejected() -> None:
    valid = csv_bytes(recipe())
    for malformed in [valid.replace(b'schema_version;', b'version;', 1),
                      valid + b'"unfinished', valid.replace(b';title;', b';schema_version;', 1)]:
        result = parse(malformed, 'text/csv')
        assert not result.is_valid and result.errors and not result.rows
    for malformed in [valid.replace(b'\n1;', b'\n2;', 1), valid + b'1;too;few\n']:
        result = parse(malformed, 'text/csv')
        assert not result.is_valid and any(row.errors for row in result.rows)


def test_nested_collection_and_field_error_limits() -> None:
    row = recipe()
    row['steps'] *= 65
    invalid = parse(json_bytes(row))
    assert not invalid.is_valid and any(e.field == 'steps' for e in invalid.rows[0].errors)
    row = recipe()
    row['steps'] = [{'instruction': '', 'duration_minutes': -1} for _ in range(64)]
    errors = parse(json_bytes(row)).rows[0].errors
    assert len(errors) <= 17 and errors[-1].code == 'too_many_errors'


def test_trusted_timestamp_requires_a_timezone_and_input_is_unchanged() -> None:
    row = recipe()
    original = deepcopy(row)
    result = parse(json_bytes(row), fetched_at=datetime(2026, 9, 8))
    assert not result.is_valid and result.errors and not result.rows
    assert row == original


def test_numeric_json_exponent_is_rejected_without_decimal_exception_or_context_changes() -> None:
    data = json_bytes(recipe()).replace(b'"4.000000"', b'1e99999999999999999999999999999')
    with localcontext() as context:
        context.clear_flags()
        result = parse(data)
        assert not result.is_valid and result.rows[0].payload is None
        assert any(e.field == 'servings' for e in result.rows[0].errors)
        assert not any(context.flags.values())


@pytest.mark.parametrize(('collection', 'extra'), [('ingredients', 'food_public_id'),
                                                  ('ingredients', 'source_kind'),
                                                  ('steps', 'image_sha256')])
def test_nested_reference_or_source_fields_cannot_override_import_provenance(collection: str, extra: str) -> None:
    row = recipe()
    row[collection][0][extra] = 'untrusted-reference'
    result = parse(json_bytes(row))
    assert not result.is_valid and result.rows[0].payload is None
    assert result.rows[0].errors[0].field == f'{collection}[0]'


def test_csv_record_limit_includes_invalid_records() -> None:
    rows = [recipe(f'Rezept {n}') for n in range(2000)]
    data = csv_bytes(*rows)
    assert parse(data, 'text/csv').is_valid
    result = parse(data + b'broken\n', 'text/csv')
    assert not result.is_valid and result.errors and not result.rows


def test_large_recipe_is_valid_json_even_when_csv_field_is_too_large() -> None:
    row = recipe()
    row['ingredients'] *= 64
    row['steps'] = [{'instruction': 'Z' * 8000, 'duration_minutes': 10080} for _ in range(64)]
    result = parse(json_bytes(row))
    assert result.is_valid and len(result.rows[0].payload['steps']) == 64
    assert len(result.rows[0].payload['ingredients']) == 64
    assert all(r['fetched_at'] == '2026-09-08T12:30:00+00:00' for r in result.rows[0].payload['ingredients'])
    assert not parse(csv_bytes(row), 'text/csv').is_valid


@pytest.mark.parametrize('field', ['title', 'description', 'source_note', 'ingredients', 'steps'])
def test_json_noninteger_numbers_never_become_strings_null_or_empty_collections(field: str) -> None:
    row = recipe()
    row[field] = 1.25
    result = parse(json_bytes(row))
    assert not result.is_valid and result.rows[0].payload is None
    assert any(e.field == field for e in result.rows[0].errors)


def test_parser_does_not_open_files_fetch_sources_or_emit_input(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    import builtins
    import socket
    from pathlib import Path

    from cafeteria.recipe_import import parse_recipe_import

    data = json_bytes(recipe())

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError('Parser attempted external I/O')

    with monkeypatch.context() as patches:
        patches.setattr(builtins, 'open', forbidden)
        patches.setattr(Path, 'open', forbidden)
        patches.setattr(socket.socket, 'connect', forbidden)
        patches.setattr(socket, 'create_connection', forbidden)
        result = parse_recipe_import(data, filename='rezepte.json', content_type='application/json', fetched_at=WHEN)
        assert result.is_valid
    assert capsys.readouterr() == ('', '')
