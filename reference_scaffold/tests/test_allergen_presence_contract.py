"""Allergen identity survives successful-control ordering and no-JS selection changes."""
import pytest
from werkzeug.datastructures import MultiDict

from cafeteria.workflow import WorkflowValidationError
from cafeteria.workflow_partial_form import (
    parse_component_create_form, parse_component_update_form, parse_menu_item_form,
    parse_week_header_form,
)


@pytest.fixture(params=['menu', 'create', 'update'])
def contract(request):
    kind = request.param
    if kind == 'menu':
        base = dict(_csrf='test', week='2026-09-21', day='2026-09-21', meal='LUNCH',
                    option='MENU_1', row_version='1', title='Test', allergen_mode='manual',
                    origin_mode='auto', label_mode='auto')
    else:
        base = dict(_csrf='test', category='other', name='Test', origin_country_code='')
        base.update({'target_scope': 'common'} if kind == 'create' else {'row_version': '1'})

    def parse(fields):
        form = MultiDict(base)
        for key, value in fields:
            form.add(key, value)
        if kind == 'menu':
            rows = parse_menu_item_form('patient', form).payload['allergens']
            return [(row['code'], row['presence']) for row in rows]
        parser = parse_component_create_form if kind == 'create' else parse_component_update_form
        return parser(form).payload['allergens']
    return parse


@pytest.mark.parametrize('reverse', [False, True])
def test_attack_preserves_identity(contract, reverse):
    fields = [('allergen_code', 'GLUTEN'), ('allergen_code', 'LUPIN'),
              ('allergen_presence__GLUTEN', 'contains'),
              ('allergen_presence__MILK', 'may_contain'),
              ('allergen_presence__LUPIN', 'contains')]
    if reverse:
        fields.reverse()
    assert sorted(contract(fields)) == [('GLUTEN', 'contains'), ('LUPIN', 'contains')]


@pytest.mark.parametrize('fields,field,message', [
    ([('allergen_code', 'MILK')], 'allergen_presence__MILK', 'unvollständig'),
    ([('allergen_code', 'MILK'), ('allergen_presence__GLUTEN', 'contains')],
     'allergen_presence__MILK', 'unvollständig'),
    ([('allergen_code', 'MILK'), ('allergen_presence__MILK', 'invalid')],
     'allergen_presence__MILK', 'ungültig'),
    ([('allergen_presence', 'contains'), ('allergen_presence__MILK', 'contains')],
     'allergen_presence', 'Allergenangaben sind widersprüchlich'),
    ([('allergen_code', 'MILK'), ('allergen_code', 'MILK'),
      ('allergen_presence__MILK', 'contains')], 'allergen_code', 'doppelt'),
])
def test_invalid_contract(contract, fields, field, message):
    with pytest.raises(WorkflowValidationError, match=message) as caught:
        contract(fields)
    assert caught.value.field_name == field


def test_legacy_contract(contract):
    assert contract([('allergen_code', 'MILK'), ('allergen_presence', 'may_contain')]) == [
        ('MILK', 'may_contain')]


def test_unselected_values_ignored(contract):
    assert contract([('allergen_presence__UNKNOWN', 'invalid')]) == []


def test_auto_mode_rejects_keyed_fields():
    form = dict(_csrf='test', week='2026-09-21', day='2026-09-21', meal='LUNCH',
                option='MENU_1', row_version='1', title='Test', allergen_mode='auto',
                origin_mode='auto', label_mode='auto', allergen_presence__MILK='contains')
    with pytest.raises(WorkflowValidationError, match='nur im Modus manuell'):
        parse_menu_item_form('patient', form)


def test_keyed_fields_do_not_relax_other_form_shapes():
    form = dict(_csrf='test', week='2026-09-21', row_version='1', title='Test',
                shared_note='', allergen_presence__MILK='contains')
    with pytest.raises(WorkflowValidationError, match='Unzulässiges Formularfeld'):
        parse_week_header_form('patient', form)


def test_selected_keyed_field_must_be_scalar(contract):
    with pytest.raises(WorkflowValidationError, match='mehrfach gesendet'):
        contract([('allergen_code', 'MILK'), ('allergen_presence__MILK', 'contains'),
                  ('allergen_presence__MILK', 'may_contain')])
