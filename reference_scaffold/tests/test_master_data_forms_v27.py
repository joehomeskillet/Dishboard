"""Pure native-form boundary checks for storage and exact prepared revision pins."""
from __future__ import annotations

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict

from cafeteria.admin.master_data_forms import FormError, payload, preparation_arguments
from cafeteria.master_data_proposals import normalize
from cafeteria.master_data_types import MasterDataValidationError

STORAGE = '11111111-1111-4111-8111-111111111111'
REVISION = '22222222-2222-4222-8222-222222222222'
HASH = 'a' * 64


def core() -> MultiDict[str, str]:
    return MultiDict({'_csrf': 'fixture', '_form_context': 'fixture', 'name': 'Hummus',
        'base_unit_code': 'G', 'category_public_id': '', 'density_g_per_ml': '',
        'piece_weight_g': '', 'note': '', 'storage_location_public_ids': STORAGE})


def parsed(values: MultiDict[str, str]) -> dict[str, object]:
    with Flask(__name__).test_request_context(method='POST', data=values):
        return payload('zutaten', 'neu', None, set())


def test_missing_preparation_choice_preserves_existing_pin() -> None:
    result = parsed(core())
    assert result['storage_location_public_ids'] == [STORAGE]
    assert 'prepared_recipe_revision_public_id' not in result
    assert 'prepared_recipe_content_hash_sha256' not in result


@pytest.mark.parametrize('choice,revision,content_hash', [
    ('', None, None), (REVISION + ':' + HASH, REVISION, HASH),
])
def test_choice_is_explicit_null_pair_or_exact_pin(choice, revision, content_hash) -> None:
    values = core()
    values['prepared_recipe_choice'] = choice
    result = parsed(values)
    assert result['prepared_recipe_revision_public_id'] == revision
    assert result['prepared_recipe_content_hash_sha256'] == content_hash


@pytest.mark.parametrize('choice', ['latest', REVISION, REVISION + ':', ':' + HASH,
                                   REVISION + ':' + HASH.upper(), REVISION + ':' + HASH + ':extra'])
def test_invalid_preparation_choice_is_field_error(choice: str) -> None:
    values = core()
    values['prepared_recipe_choice'] = choice
    with pytest.raises(FormError) as error:
        parsed(values)
    assert error.value.field == 'prepared_recipe_choice'


def test_storage_is_required_and_duplicates_do_not_disappear() -> None:
    values = core()
    del values['storage_location_public_ids']
    with pytest.raises(FormError) as error:
        parsed(values)
    assert error.value.field == 'storage_location_public_ids'
    values.setlist('storage_location_public_ids', [STORAGE, STORAGE])
    with pytest.raises(FormError):
        parsed(values)


@pytest.mark.parametrize('fields', [
    {'prepared_recipe_revision_public_id': REVISION},
    {'prepared_recipe_content_hash_sha256': HASH},
    {'prepared_recipe_revision_public_id': None, 'prepared_recipe_content_hash_sha256': HASH},
    {'prepared_recipe_revision_public_id': REVISION, 'prepared_recipe_content_hash_sha256': None},
    {'prepared_recipe_revision_public_id': REVISION, 'prepared_recipe_content_hash_sha256': 'latest'},
    {'storage_location_public_ids': []}, {'storage_location_public_ids': [STORAGE, STORAGE]},
])
def test_service_normalization_rejects_partial_pairs_and_empty_storage(fields) -> None:
    with pytest.raises(MasterDataValidationError):
        normalize(fields)


def test_normalization_keeps_pin_omission_and_exact_pair() -> None:
    assert normalize({'name': 'Hummus'}) == {'name': 'Hummus'}
    pair = {'prepared_recipe_revision_public_id': REVISION, 'prepared_recipe_content_hash_sha256': HASH}
    assert normalize(pair) == pair
    nulls = {key: None for key in pair}
    assert normalize(nulls) == nulls


@pytest.mark.parametrize('query', ['recipe_q=%00', 'recipe_q=' + 'x' * 201,
    'recipe_page=0', 'recipe_page=100001', 'recipe_page=2&recipe_page=3', 'profile=patient'])
def test_preparation_search_bounds_and_unexpected_fields(query: str) -> None:
    from werkzeug.exceptions import BadRequest
    with Flask(__name__).test_request_context('/?' + query):
        with pytest.raises((FormError, BadRequest)):
            preparation_arguments('zutaten')


def test_search_is_get_only_and_storage_vocabulary_sort_order_is_explicit() -> None:
    from werkzeug.exceptions import BadRequest
    with Flask(__name__).test_request_context('/?recipe_q=Hummus', method='POST'):
        with pytest.raises(BadRequest):
            preparation_arguments('zutaten')
    with Flask(__name__).test_request_context(method='POST', data={
        '_csrf': 'fixture', '_form_context': 'fixture', 'name': 'Kühlraum', 'code': 'COOL', 'sort_order': '2',
    }):
        assert payload('lagerorte', 'neu', None, set()) == {'name': 'Kühlraum', 'code': 'COOL', 'sort_order': 2}
