"""Pure display scaling preserves exact calculation results and original payloads."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, Inexact, localcontext
import hashlib
import json

import pytest

from cafeteria.admin.recipe_forms import FormError
from cafeteria.admin.recipe_scaling import scaled_recipe
from cafeteria.recipe_snapshots import frozen_json
from cafeteria.recipe_types import RecipeConfigurationError
from test_recipe_store_db import payload, line
from test_recipe_pdf import prepared_revision


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


def test_captured_preparation_preserves_periodic_computed_yield_and_repeated_uses():
    revision = prepared_revision()
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        result = scaled_recipe(revision.snapshot['recipe'], '2', revision=revision)
    assert len(result['prepared']) == 2
    for use in result['prepared']:
        assert use['calculated']['target'] == '0.00066666666666666666666666666666666666666666666666667'
        assert use['calculated']['rows'][0]['scaled'] == '0.00022222222222222222222222222222222222222222222222222'
        assert use['calculated']['unit'] == 'KG'
    assert revision.snapshot['recipe']['ingredients'][0]['quantity'] == '1'


@pytest.mark.parametrize(('unit', 'density', 'valid'), [('ML', '1.5', True), ('ML', None, False), ('PORTION', None, False)])
def test_prepared_conversion_uses_only_captured_density_and_never_assumes_portion_mass(unit, density, valid):
    original = prepared_revision()
    body = json.loads(original.canonical_snapshot_text)
    body['units'].append({'public_id': '00000000-0000-0000-0000-000000000013', 'code': 'ML',
                          'display_name': 'Milliliter', 'dimension': 'volume', 'base_factor': '1'})
    for ingredient in body['recipe']['ingredients']:
        ingredient['unit_code'] = unit
    body['foods'][0]['density_g_per_ml'] = density
    raw = json.dumps(body, ensure_ascii=False)
    revision = replace(original, snapshot=frozen_json(body), canonical_snapshot_text=raw,
                       content_hash_sha256=hashlib.sha256(raw.encode()).hexdigest())
    if valid:
        result = scaled_recipe(revision.snapshot['recipe'], '2', revision=revision)
        assert all(Decimal(use['calculated']['target']) == Decimal('0.001') for use in result['prepared'])
    else:
        with pytest.raises(RecipeConfigurationError):
            scaled_recipe(revision.snapshot['recipe'], '2', revision=revision)
