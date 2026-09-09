"""Drive parse_ai_extraction; no provider, file or database access."""
from __future__ import annotations

import socket
from pathlib import Path

from cafeteria.recipe_ai_extraction import parse_ai_extraction

WHEN = '2026-09-08T12:30:00+00:00'
SHA = 'a' * 64
FOOD = '00000000-0000-4000-8000-000000000001'


def _doc(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        'document_sha256': SHA,
        'page': 1,
        'line': 4,
        'note': 'KI-Auszug, ungeprüft',
        'fetched_at': WHEN,
        'recipes': [{
            'title': 'Suppe',
            'servings': '4',
            'servings_unit_code': 'PORTION',
            'ingredients': [{
                'ingredient_text': 'Kartoffeln',
                'food_public_id': FOOD,
                'quantity': '500',
                'unit_code': 'G',
            }],
            'steps': ['Kochen.'],
        }],
    }
    body.update(changes)
    return body


def test_ai_origin_and_required_note_stay_on_the_common_payload() -> None:
    preview = parse_ai_extraction(_doc())
    assert preview.is_valid
    source = preview.rows[0].payload['source']
    assert source['kind'] == 'ai_assisted'
    assert source['note'] == 'KI-Auszug, ungeprüft'
    assert SHA in source['reference'] and 'page:1' in source['reference']
    assert preview.rows[0].payload['ingredients'][0]['source_kind'] == 'ai_assisted'


def test_missing_source_hash_is_file_error_without_echoing_input() -> None:
    preview = parse_ai_extraction(_doc(document_sha256='not-a-hash'))
    assert preview.rows == ()
    assert preview.errors[0].field == 'document_sha256'
    assert 'not-a-hash' not in preview.errors[0].message


def test_unresolved_ingredient_blocks_confirmed_import_but_keeps_a_row() -> None:
    recipes = [{
        'title': 'Suppe',
        'servings': '4',
        'servings_unit_code': 'PORTION',
        'ingredients': [{'ingredient_text': 'Etwas Unklares', 'uncertainty': 'unresolved_food'}],
        'steps': ['Rühren.'],
    }]
    preview = parse_ai_extraction(_doc(recipes=recipes))
    assert not preview.is_valid
    assert len(preview.rows) == 1
    codes = {issue.code for issue in preview.rows[0].errors}
    assert 'uncertainty' in codes and 'unresolved' in codes
    assert preview.rows[0].payload is not None
    assert preview.rows[0].payload['source']['kind'] == 'ai_assisted'


def test_incomplete_recipe_head_is_a_row_not_a_file_failure() -> None:
    preview = parse_ai_extraction(_doc(recipes=[{'title': 'Nur Titel'}]))
    assert preview.errors == ()
    assert len(preview.rows) == 1
    assert not preview.is_valid
    assert preview.rows[0].payload is None


def test_allergens_are_never_auto_confirmed() -> None:
    recipes = _doc()['recipes']
    recipes[0]['allergens'] = [{'code': 'MILK', 'confirmed': True}]
    preview = parse_ai_extraction(_doc(recipes=recipes))
    assert not preview.is_valid
    assert any(issue.field == 'allergens' for issue in preview.rows[0].errors)
    payload = preview.rows[0].payload
    if payload is not None:
        assert 'allergens' not in payload


def test_adapter_source_has_no_provider_or_socket_import() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'recipe_ai_extraction.py').read_text(encoding='utf-8')
    assert 'urllib' not in text and 'requests' not in text and 'psycopg' not in text
    assert 'openai' not in text and 'socket' not in text
    assert socket.create_connection
