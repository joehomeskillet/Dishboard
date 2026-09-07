"""Pure display scaling preserves exact calculation results and original payloads."""
from copy import deepcopy
from decimal import Decimal, localcontext

import pytest

from cafeteria.admin.recipe_forms import FormError
from cafeteria.admin.recipe_scaling import scaled_recipe
from test_recipe_store_db import payload, line


def test_scaling_keeps_original_quantities_units_and_missing_amounts():
    source = payload(ingredients=[line(quantity='0.125', unit_code='KG'),
                                  line('Salz', quantity=None, unit_code=None)])
    before = deepcopy(source)
    result = scaled_recipe(source, '6')
    assert result['source'] == '4' and result['target'] == '6'
    assert result['unit'] == 'PORTION'
    assert result['rows'][0]['original'] == '0.125'
    assert result['rows'][0]['scaled'] == '0.1875'
    assert result['rows'][0]['unit'] == 'KG'
    assert result['rows'][1]['scaled'] is None and result['rows'][1]['unit'] is None
    assert source == before


def test_periodic_scaling_is_not_rounded_to_six_places_or_ambient_context():
    source = payload(servings='3')
    with localcontext() as context:
        context.prec = 2
        result = scaled_recipe(source, '1')
    assert result['rows'][0]['scaled'] == '0.' + '3' * 50
    assert Decimal(result['rows'][0]['scaled']) > Decimal('0.333333')


@pytest.mark.parametrize('target', ['0', '-1', 'NaN', 'Infinity', '1e12', '0.0000001', '1,5', ''])
def test_invalid_target_is_a_named_form_error(target):
    with pytest.raises(FormError) as caught:
        scaled_recipe(payload(), target)
    assert caught.value.field == 'yield'


def test_maximum_storage_target_is_read_only_calculation_without_overflow():
    source = payload(servings='0.000001', ingredients=[line(quantity='999999999999.999999')])
    result = scaled_recipe(source, '999999999999.999999')
    assert result['rows'][0]['scaled'] == '999999999999999998000000000000.000001'
