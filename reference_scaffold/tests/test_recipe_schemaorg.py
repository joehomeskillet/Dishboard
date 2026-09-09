"""Drive parse_schemaorg; no network and no product import path."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from cafeteria.recipe_schemaorg import MAX_BYTES, parse_schemaorg

WHEN = '2026-09-08T12:30:00+00:00'
URL = 'https://example.invalid/rezept'


def _recipe(**fields: object) -> dict[str, object]:
    body = {
        '@type': 'Recipe',
        'name': 'Kartoffelsuppe',
        'recipeYield': '4 Portionen',
        'recipeIngredient': ['Kartoffeln'],
        'recipeInstructions': ['Kochen.'],
    }
    body.update(fields)
    return body


def _parse(document: str | dict | list, url: str = URL) -> object:
    if not isinstance(document, str):
        document = json.dumps(document)
    return parse_schemaorg(document, url, WHEN)


def test_yield_four_portions_maps_to_portion_unit() -> None:
    preview = _parse(_recipe())
    assert preview.is_valid
    payload = preview.rows[0].payload
    assert payload['servings'] == '4' and payload['servings_unit_code'] == 'PORTION'
    assert payload['source']['kind'] == 'url' and payload['source']['url'] == URL


def test_ambiguous_yield_is_field_error_without_echo() -> None:
    preview = _parse(_recipe(recipeYield='ca. 4-6'))
    assert not preview.is_valid
    issue = preview.rows[0].errors[0]
    assert issue.field == 'recipeYield'
    assert 'ca. 4-6' not in issue.message
    assert preview.rows[0].payload is None


@pytest.mark.parametrize('raw,minutes', [('PT20M', 20), ('PT1H30M', 90), ('P1D', 1440)])
def test_iso_durations_become_minutes(raw: str, minutes: int) -> None:
    preview = _parse(_recipe(prepTime=raw, cookTime='PT0M'))
    assert preview.is_valid
    assert preview.rows[0].payload['prep_minutes'] == minutes
    assert preview.rows[0].payload['cook_minutes'] == 0


def test_two_hundred_hours_is_rejected() -> None:
    preview = _parse(_recipe(prepTime='PT200H'))
    assert not preview.is_valid
    assert preview.rows[0].errors[0].field == 'prepTime'
    assert 'PT200H' not in preview.rows[0].errors[0].message


def test_document_without_recipe_type_is_file_error_without_rows() -> None:
    preview = _parse({'@type': 'Article', 'name': 'Kein Rezept'})
    assert preview.rows == ()
    assert preview.errors[0].field == 'file'
    assert not preview.is_valid


def test_graph_self_reference_is_rejected_without_loop() -> None:
    document = {
        '@graph': [
            {'@id': '#a', '@type': 'Recipe', 'name': 'Loop', 'recipeYield': '4 Portionen',
             'recipeIngredient': {'@id': '#a'}},
        ]
    }
    preview = _parse(document)
    assert preview.rows == ()
    assert preview.errors[0].code == 'graph_cycle'


def test_html_json_ld_script_is_read_without_executing_markup() -> None:
    html = (
        '<html><head><script type="application/ld+json">'
        + json.dumps(_recipe())
        + '</script><script>window.steal=1</script></head></html>'
    )
    preview = parse_schemaorg(html, URL, WHEN)
    assert preview.is_valid and preview.rows[0].payload['title'] == 'Kartoffelsuppe'


def test_module_does_not_open_network_or_files(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('network')

    monkeypatch.setattr(socket, 'create_connection', blocked)
    preview = _parse(_recipe())
    assert preview.is_valid
    source = Path(__file__).resolve().parents[1] / 'cafeteria' / 'recipe_schemaorg.py'
    text = source.read_text(encoding='utf-8')
    assert 'urllib' not in text and 'requests' not in text and 'socket' not in text
    assert 'urlopen' not in text and 'eval(' not in text and 'exec(' not in text


def test_error_paths_do_not_echo_untrusted_input() -> None:
    preview = _parse(_recipe(name='<script>alert(1)</script>'))
    messages = ' '.join(issue.message for row in preview.rows for issue in row.errors)
    messages += ' '.join(issue.message for issue in preview.errors)
    assert '<script>' not in messages


def test_document_over_two_mib_is_rejected() -> None:
    preview = parse_schemaorg('x' * (MAX_BYTES + 1), URL, WHEN)
    assert preview.rows == () and preview.errors[0].code == 'size'
