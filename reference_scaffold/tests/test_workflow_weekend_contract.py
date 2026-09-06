from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from cafeteria.workflow import WorkflowValidationError, _validate_values
from cafeteria.workflow_form import parse_draft_form, submitted_form_values
from cafeteria.workflow_partial_form import parse_menu_item_form, parse_service_form
from tests.test_workflow_form import _menu_form, _service_partial_form, _staff_form


def _weekend_form(offsets: tuple[int, ...]) -> MultiDict[str, str]:
    form = MultiDict(_staff_form())
    monday = {key: value for key, value in form.items() if key.startswith('service_0_')}
    for offset in offsets:
        for key, value in monday.items():
            form[key.replace('service_0_', f'service_{offset}_', 1)] = value
        form[f'service_{offset}_LUNCH_start'] = '11:30'
        form[f'service_{offset}_LUNCH_end'] = '13:30'
    return form


@pytest.mark.parametrize('offsets', [(5,), (6,), (5, 6)])
def test_full_form_keeps_individually_optional_weekend_days(offsets: tuple[int, ...]) -> None:
    form = _weekend_form(offsets)
    parsed = parse_draft_form('staff_guest', form)
    assert [day['date'] for day in parsed.values['days']] == [
        f'2026-08-{31:02d}' if offset == 0 else f'2026-09-{offset:02d}'
        for offset in (*range(5), *offsets)
    ]
    _validate_values('staff_guest', date(2026, 8, 31), parsed.values)
    for offset in offsets:
        service = next(day for day in parsed.values['days']
                       if day['date'] == f'2026-09-{offset:02d}')['services'][0]
        assert (service['service_start'], service['service_end']) == ('11:30', '13:30')
        assert submitted_form_values('staff_guest', form)[f'service_{offset}_LUNCH_start'] == '11:30'


def test_optional_weekend_still_requires_complete_fields_and_unique_scalars() -> None:
    form = _weekend_form((6,))
    del form['service_6_LUNCH_MENU_1_title']
    with pytest.raises(WorkflowValidationError) as caught:
        parse_draft_form('staff_guest', form)
    assert caught.value.field_name == 'service_6_LUNCH_MENU_1_title'
    form = _weekend_form((5,))
    form.add('service_5_LUNCH_start', '12:00')
    with pytest.raises(WorkflowValidationError) as caught:
        parse_draft_form('staff_guest', form)
    assert caught.value.field_name == 'service_5_LUNCH_start'


@pytest.mark.parametrize('day', ['2026-09-05', '2026-09-06'])
def test_partial_form_parses_weekend_scope_for_transactional_flag_check(day: str) -> None:
    service = parse_service_form('staff_guest', _service_partial_form(day=day))
    assert service.day == day
    menu = parse_menu_item_form('staff_guest', _menu_form(
        day=day, internal_chf='9.50', external_chf='14.50',
    ))
    assert menu.day == day


def test_full_form_without_weekend_keeps_legacy_five_days() -> None:
    assert len(parse_draft_form('staff_guest', _staff_form()).values['days']) == 5
