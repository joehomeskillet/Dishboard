"""Native recipe parser values and structural bounds without a database."""
from uuid import uuid4

import pytest
from werkzeug.datastructures import MultiDict

from cafeteria.admin.recipe_forms import FormError, parse_recipe_form
from test_recipe_store_db import payload


def form_values(data=None):
    result = MultiDict()
    for key, value in (payload() if data is None else data).items():
        if key == 'source':
            for field, entry in value.items():
                result.add('source.' + field, '' if entry is None else str(entry))
        elif key in ('ingredients', 'steps', 'images'):
            for index, row in enumerate(value):
                for field, entry in row.items():
                    result.add(f'{key}.{index}.{field}', '' if entry is None else str(entry))
        elif key == 'tag_public_ids':
            for entry in value:
                result.add(key, entry)
        else:
            result.add(key, '' if value is None else str(value))
    return result


def test_complete_recipe_and_incomplete_structural_values():
    data = form_values()
    data['description'] = '\nErste\r\nZweite'
    original = list(data.items(multi=True))
    assert parse_recipe_form(data)['description'] == 'Erste\nZweite'
    assert list(data.items(multi=True)) == original
    data['ingredients.0.quantity'] = ''
    data['steps.0.instruction'] = '\n'
    assert parse_recipe_form(data, structural_only=True)['steps'][0]['instruction'] == '\n'
    with pytest.raises(FormError) as error:
        parse_recipe_form(data)
    assert error.value.field == 'ingredients.0.quantity'


@pytest.mark.parametrize('change', ['duplicate', 'unknown', 'gap', 'missing', '65', 'tags'])
def test_structural_rejects_ambiguous_forms(change):
    data = form_values()
    if change == 'duplicate':
        data.add('title', 'anderer Titel')
    elif change == 'unknown':
        data['server_role'] = 'Admin'
    elif change == 'gap':
        data['ingredients.2.note'] = 'Lücke'
    elif change == 'missing':
        del data['ingredients.0.note']
    elif change == '65':
        data['steps.64.instruction'] = 'zu viel'
    else:
        data.setlist('tag_public_ids', [str(uuid4())] * 2)
    with pytest.raises(FormError):
        parse_recipe_form(data, structural_only=True)


@pytest.mark.parametrize('field,value', [('title', '<script>'), ('prep_minutes', 'true'),
                                       ('cook_minutes', '10081'), ('steps.0.instruction', '\x00')])
def test_precise_invalid_field(field, value):
    data = form_values()
    data[field] = value
    with pytest.raises(FormError) as error:
        parse_recipe_form(data)
    assert error.value.field == field
