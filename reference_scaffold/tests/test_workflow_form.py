from __future__ import annotations

import pytest
from werkzeug.datastructures import MultiDict

from cafeteria.workflow import WorkflowValidationError, validate_publication_fit
from cafeteria.workflow_form import parse_draft_form


def _staff_form() -> dict[str, str]:
    form = {
        '_csrf': 'test-csrf',
        'week_start': '2026-08-31',
        'row_version': '1',
        'title': 'Cafeteria Herbst',
        'shared_note': 'Mittagsangebot',
    }
    for day_index in range(5):
        service = f'service_{day_index}_LUNCH'
        form[f'{service}_state'] = 'open'
        form[f'{service}_notice'] = ''
        for type_code, title in (('MENU_1', 'Tagesmenü'), ('VEGGIE', 'Vegetarisch')):
            option = f'{service}_{type_code}'
            form[f'{option}_title'] = title
            form[f'{option}_components'] = 'Salat'
            form[f'{option}_internal_rappen'] = '950'
            form[f'{option}_external_rappen'] = '1450'
            form[f'{option}_allergen_reviewed'] = 'on'
    return form


def test_parse_draft_form_preserves_every_repeated_label_value() -> None:
    form = MultiDict(_staff_form().items())
    labels_field = 'service_0_LUNCH_MENU_1_labels'
    form.add(labels_field, 'VEGAN')
    form.add(labels_field, 'GLUTEN_FREE')

    parsed = parse_draft_form('staff_guest', form)

    assert parsed.values['days'][0]['services'][0]['options'][0]['labels'] == [
        {'code': 'VEGAN', 'name': 'VEGAN'},
        {'code': 'GLUTEN_FREE', 'name': 'GLUTEN_FREE'},
    ]


def test_parse_draft_form_rejects_substring_matched_optional_field() -> None:
    form = _staff_form()
    form['evil_labels_suffix'] = 'VEGAN'

    with pytest.raises(WorkflowValidationError, match='Unzulässiges Formularfeld'):
        parse_draft_form('staff_guest', form)


def test_parse_draft_form_normalizes_legacy_reviewed_value_to_checked() -> None:
    form = _staff_form()
    form['service_0_LUNCH_MENU_1_allergen_reviewed'] = 'reviewed'

    parsed = parse_draft_form('staff_guest', form)

    assert (
        parsed.values['days'][0]['services'][0]['options'][0]['allergen_review_status']
        == 'checked'
    )


def test_publication_title_limit_targets_title_input() -> None:
    form = _staff_form()
    form['service_0_LUNCH_MENU_1_title'] = 'G' * 37
    parsed = parse_draft_form('staff_guest', form)

    with pytest.raises(WorkflowValidationError) as raised:
        validate_publication_fit('staff_guest', parsed.values)

    assert raised.value.field_name == 'service_0_LUNCH_MENU_1_title'


def test_publication_components_limit_targets_components_input() -> None:
    form = _staff_form()
    form['service_0_LUNCH_MENU_1_components'] = 'K' * 49
    parsed = parse_draft_form('staff_guest', form)

    with pytest.raises(WorkflowValidationError) as raised:
        validate_publication_fit('staff_guest', parsed.values)

    assert raised.value.field_name == 'service_0_LUNCH_MENU_1_components'
