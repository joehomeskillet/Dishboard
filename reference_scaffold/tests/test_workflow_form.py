from __future__ import annotations

import pytest
from werkzeug.datastructures import MultiDict

from cafeteria.workflow import WorkflowValidationError, validate_publication_fit
from cafeteria.workflow_form import parse_draft_form
from cafeteria.workflow_partial_form import (
    parse_menu_item_form,
    parse_service_form,
    parse_week_header_form,
)


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


def test_publication_rejects_unchecked_open_option() -> None:
    parsed = parse_draft_form('staff_guest', MultiDict(_staff_form().items()))
    option = parsed.values['days'][0]['services'][0]['options'][0]
    option['allergen_review_status'] = 'not_checked'

    with pytest.raises(WorkflowValidationError, match='nicht geprüft') as raised:
        validate_publication_fit('staff_guest', parsed.values)

    assert raised.value.field_name == 'service_0_LUNCH_MENU_1_allergen_reviewed'


def _menu_form(**updates: str) -> MultiDict[str, str]:
    values = MultiDict(
        [
            ('_csrf', 'test-csrf'),
            ('week', '2026-08-31'),
            ('day', '2026-09-02'),
            ('meal', 'LUNCH'),
            ('option', 'MENU_1'),
            ('row_version', '0'),
            ('title', 'Rindsragout'),
            ('description', 'Langsam geschmort'),
            ('note', ''),
            ('allergen_mode', 'manual'),
            ('origin_mode', 'manual'),
            ('label_mode', 'manual'),
        ]
    )
    for key, value in updates.items():
        values.setlist(key, [value])
    return values


def test_parse_week_header_form_returns_exact_payload_and_zero_version() -> None:
    parsed = parse_week_header_form(
        'patient',
        MultiDict(
            [
                ('_csrf', 'test-csrf'),
                ('week', '2026-08-31'),
                ('row_version', '0'),
                ('title', '  Herbstwoche  '),
                ('shared_note', '  Guten Appetit  '),
            ]
        ),
    )

    assert parsed.week_start.isoformat() == '2026-08-31'
    assert parsed.expected_week_row_version == 0
    assert parsed.payload == {'title': 'Herbstwoche', 'shared_note': 'Guten Appetit'}


def test_parse_service_form_returns_scoped_identity_and_payload() -> None:
    parsed = parse_service_form(
        'patient',
        MultiDict(
            [
                ('_csrf', 'test-csrf'),
                ('week', '2026-08-31'),
                ('day', '2026-09-06'),
                ('meal', 'DINNER'),
                ('row_version', '4'),
                ('service_state', 'closed'),
                ('notice', '  Küche geschlossen  '),
            ]
        ),
    )

    assert (parsed.day, parsed.meal, parsed.expected_service_row_version) == (
        '2026-09-06',
        'DINNER',
        4,
    )
    assert parsed.payload == {'service_state': 'closed', 'notice': 'Küche geschlossen'}


@pytest.mark.parametrize(
    ('profile_code', 'updates', 'field_name'),
    [
        ('patient', {'week': '20260831'}, 'week'),
        ('patient', {'week': '2026-09-01'}, 'week'),
        ('patient', {'day': '2026-09-07'}, 'day'),
        (
            'staff_guest',
            {'day': '2026-09-05', 'internal_chf': '9.50', 'external_chf': '14.50'},
            'day',
        ),
        (
            'staff_guest',
            {'meal': 'DINNER', 'internal_chf': '9.50', 'external_chf': '14.50'},
            'meal',
        ),
        ('patient', {'meal': 'BREAKFAST'}, 'meal'),
        ('patient', {'option': 'MENU_2'}, 'option'),
    ],
)
def test_parse_menu_item_form_rejects_invalid_raster(
    profile_code: str,
    updates: dict[str, str],
    field_name: str,
) -> None:
    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form(profile_code, _menu_form(**updates))

    assert raised.value.field_name == field_name


def test_parse_menu_item_form_normalizes_staff_chf_and_exact_payload() -> None:
    form = _menu_form(internal_chf='9,50', external_chf='14.5')
    form.add('component_public_id', '11111111-1111-4111-8111-111111111111')
    form.add('component_text', '')
    form.add('component_public_id', '')
    form.add('component_text', '  Eigene Sauce  ')
    form.add('label_code', 'VEGAN')
    form.add('allergen_code', 'A')
    form.add('allergen_presence', 'contains')
    form.add('origin_ingredient', '  Rind  ')
    form.add('origin_country_code', ' CH ')

    parsed = parse_menu_item_form('staff_guest', form)

    assert parsed.expected_item_row_version == 0
    assert parsed.payload == {
        'title': 'Rindsragout',
        'description': 'Langsam geschmort',
        'note': '',
        'allergen_mode': 'manual',
        'origin_mode': 'manual',
        'label_mode': 'manual',
        'assignments': [
            {
                'component_public_id': '11111111-1111-4111-8111-111111111111',
                'component_text': None,
            },
            {'component_public_id': None, 'component_text': '  Eigene Sauce  '},
        ],
        'labels': ['VEGAN'],
        'allergens': [{'code': 'A', 'presence': 'contains'}],
        'origins': [{'ingredient': 'Rind', 'country_code': 'CH', 'text': 'Rind: CH'}],
        'internal_rappen': 950,
        'external_rappen': 1450,
    }


def test_parse_patient_item_has_exact_payload_and_rejects_prices() -> None:
    parsed = parse_menu_item_form('patient', _menu_form())

    assert set(parsed.payload) == {
        'title',
        'description',
        'note',
        'allergen_mode',
        'origin_mode',
        'label_mode',
        'assignments',
        'labels',
        'allergens',
        'origins',
    }

    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form('patient', _menu_form(internal_chf='9.50'))

    assert raised.value.field_name == 'internal_chf'


@pytest.mark.parametrize('amount', ['0', '-1.00', '12.345', 'CHF 12.00', 'NaN'])
def test_parse_staff_price_errors_name_novice_context(amount: str) -> None:
    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form(
            'staff_guest',
            _menu_form(internal_chf=amount, external_chf='14.50'),
        )

    assert raised.value.field_name == 'internal_chf'
    assert str(raised.value).startswith('Mittwoch, Mittag, Menü 1: ')


def test_parse_staff_price_requires_external_not_below_internal() -> None:
    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form(
            'staff_guest',
            _menu_form(internal_chf='15.00', external_chf='14.00'),
        )

    assert raised.value.field_name == 'external_chf'
    assert 'Mittwoch, Mittag, Menü 1' in str(raised.value)


@pytest.mark.parametrize(
    ('mode', 'field'),
    [
        ('allergen_mode', 'allergen_code'),
        ('origin_mode', 'origin_ingredient'),
        ('label_mode', 'label_code'),
    ],
)
def test_auto_mode_rejects_manual_metadata_fields(mode: str, field: str) -> None:
    form = _menu_form(**{mode: 'auto'})
    form.add(field, 'A')

    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form('patient', form)

    assert raised.value.field_name == field


@pytest.mark.parametrize(
    ('left_key', 'right_key'),
    [
        ('component_public_id', 'component_text'),
        ('allergen_code', 'allergen_presence'),
        ('origin_ingredient', 'origin_country_code'),
    ],
)
def test_paired_menu_arrays_must_have_equal_length(left_key: str, right_key: str) -> None:
    form = _menu_form()
    form.add(left_key, 'A')
    form.add(right_key, 'B')
    form.add(right_key, 'C')

    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form('patient', form)

    assert raised.value.field_name == right_key


def test_manual_origins_trim_pairs_and_reject_duplicate_ingredient() -> None:
    form = _menu_form()
    form.add('origin_ingredient', '  Rind  ')
    form.add('origin_country_code', ' CH ')
    form.add('origin_ingredient', 'Rind')
    form.add('origin_country_code', 'DE')

    with pytest.raises(WorkflowValidationError, match='Rind') as raised:
        parse_menu_item_form('patient', form)

    assert raised.value.field_name == 'origin_ingredient'


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('allergen_presence', 'sometimes'),
        ('origin_country_code', 'ch'),
        ('component_text', '   '),
    ],
)
def test_menu_repeated_values_are_validated(field: str, value: str) -> None:
    form = _menu_form()
    if field == 'allergen_presence':
        form.add('allergen_code', 'A')
    if field == 'origin_country_code':
        form.add('origin_ingredient', 'Rind')
    if field == 'component_text':
        form.add('component_public_id', '')
    form.add(field, value)

    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form('patient', form)

    assert raised.value.field_name == field


@pytest.mark.parametrize(
    ('parser_name', 'form'),
    [
        (
            'header',
            MultiDict(
                [
                    ('_csrf', 'x'),
                    ('week', '2026-08-31'),
                    ('row_version', '0'),
                    ('title', 'Woche'),
                    ('shared_note', ''),
                    ('week_id', '7'),
                ]
            ),
        ),
        ('service', _menu_form(service_state='open', notice='')),
        ('menu', _menu_form(profile='patient')),
    ],
)
def test_partial_forms_reject_unexpected_or_internal_fields(
    parser_name: str,
    form: MultiDict[str, str],
) -> None:
    parsers = {
        'header': parse_week_header_form,
        'service': parse_service_form,
        'menu': parse_menu_item_form,
    }

    with pytest.raises(WorkflowValidationError, match='Unzulässiges Formularfeld'):
        parsers[parser_name]('patient', form)


def test_partial_forms_reject_duplicate_scalar() -> None:
    form = _menu_form()
    form.add('title', 'Zweites Menü')

    with pytest.raises(WorkflowValidationError, match='mehrfach') as raised:
        parse_menu_item_form('patient', form)

    assert raised.value.field_name == 'title'
