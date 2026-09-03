from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import importlib
import json
from typing import Any

import pytest

from cafeteria.workflow_snapshot import build_snapshot


WEEK_START = date(2026, 9, 7)
GOLDEN_TOKEN = 'sha256:b3526f90550974218338f0f890d8f02a524cfad0dee40ae387074883691e7428'
GOLDEN_PAYLOAD = {
    'allergen_mode': 'auto',
    'allergens': [
        {'code': 'A', 'name': 'Gluten', 'presence': 'contains'},
        {'code': 'B', 'name': 'Milch', 'presence': 'may_contain'},
    ],
    'components': [
        {
            'component_public_id': '11111111-1111-4111-8111-111111111111',
            'component_text': 'Rind & Crème',
            'current_component_row_version': 4,
            'sort_order': 1,
            'stored_component_row_version': 3,
        },
        {
            'component_public_id': None,
            'component_text': 'Freitext',
            'current_component_row_version': None,
            'sort_order': 2,
            'stored_component_row_version': None,
        },
    ],
    'item_row_version': 7,
    'label_mode': 'manual',
    'labels': [{'code': 'L1', 'name': 'Hausgemacht'}],
    'origin_mode': 'auto',
    'origins': [{'country_code': 'CH', 'ingredient': 'Rind', 'text': 'Rind: CH'}],
}


def _review_token(payload: object) -> str:
    module = importlib.import_module('cafeteria.workflow_review')
    return module._review_token(payload)


def _staff_draft() -> dict[str, Any]:
    days = []
    for offset in range(5):
        service_date = (WEEK_START + timedelta(days=offset)).isoformat()
        options = []
        for type_code, title in (('MENU_1', 'Rind'), ('VEGGIE', 'Gemüse')):
            options.append(
                {
                    'type_code': type_code,
                    'title': title,
                    'components': ['Rind & Crème'],
                    'labels': [
                        {
                            'id': 91,
                            'code': 'L1',
                            'name': 'Hausgemacht',
                            'mode': 'auto',
                        }
                    ],
                    'allergens': [
                        {
                            'id': 92,
                            'code': 'A',
                            'name': 'Gluten',
                            'presence': 'contains',
                            'component_row_version': 7,
                        }
                    ],
                    'origins': [
                        {
                            'ingredient': 'Rind',
                            'country_code': 'CH',
                            'text': 'Rind: CH',
                            'component_public_id': '11111111-1111-4111-8111-111111111111',
                        }
                    ],
                    'allergen_review_status': 'checked',
                    'allergen_mode': 'auto',
                    'origin_mode': 'manual',
                    'label_mode': 'auto',
                    'row_version': 8,
                    'internal_rappen': 900,
                    'external_rappen': 1400,
                }
            )
        days.append(
            {
                'date': service_date,
                'services': [
                    {
                        'meal_code': 'LUNCH',
                        'service_state': 'open',
                        'notice': '',
                        'options': options,
                    }
                ],
            }
        )
    return {
        'week_start': WEEK_START.isoformat(),
        'location': {'code': 'KIRCHLINDACH', 'name': 'Südhang'},
        'title': 'Wochenmenü',
        'shared_note': 'Frisch gekocht',
        'days': days,
    }


def test_snapshot_projects_exact_public_metadata_and_detaches_source() -> None:
    draft = _staff_draft()
    snapshot = build_snapshot('staff_guest', draft, 'CAF-2026-KW37-R1')
    option = snapshot['days'][0]['services'][0]['options'][0]

    assert set(option) == {
        'external_id',
        'type_code',
        'type_name',
        'title',
        'description',
        'components',
        'labels',
        'allergens',
        'origins',
        'note',
        'allergen_review_status',
        'prices',
    }
    assert option['components'] == ['Rind & Crème']
    assert option['labels'] == [{'code': 'L1', 'name': 'Hausgemacht'}]
    assert option['allergens'] == [
        {'code': 'A', 'name': 'Gluten', 'presence': 'contains'}
    ]
    assert option['origins'] == [
        {'ingredient': 'Rind', 'country_code': 'CH', 'text': 'Rind: CH'}
    ]

    frozen = deepcopy(snapshot)
    draft['days'][0]['services'][0]['options'][0]['labels'][0]['name'] = 'Geändert'
    draft['days'][0]['services'][0]['options'][0]['components'][0] = 'Geändert'
    assert snapshot == frozen


@pytest.mark.parametrize(
    ('collection', 'field', 'value'),
    [
        ('labels', 'name', None),
        ('allergens', 'presence', 'trace'),
        ('origins', 'country_code', 41),
    ],
)
def test_snapshot_rejects_non_public_metadata_types(
    collection: str, field: str, value: object
) -> None:
    draft = _staff_draft()
    option = draft['days'][0]['services'][0]['options'][0]
    option[collection][0][field] = value

    with pytest.raises(ValueError):
        build_snapshot('staff_guest', draft, 'CAF-2026-KW37-R1')


def test_review_token_matches_mandatory_utf8_golden_payload() -> None:
    assert _review_token(deepcopy(GOLDEN_PAYLOAD)) == GOLDEN_TOKEN


def test_review_token_preserves_non_uuid_strings_byte_exactly() -> None:
    payload = deepcopy(GOLDEN_PAYLOAD)
    payload['components'][0]['component_text'] = ' e\u0301 '
    payload['labels'][0]['name'] = ' HausGEMACHT '
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')
    expected = f'sha256:{hashlib.sha256(encoded).hexdigest()}'

    assert _review_token(payload) == expected


def test_review_token_rejects_wrong_keys_types_nulls_uuid_and_ordering() -> None:
    invalid_payloads = []

    extra = deepcopy(GOLDEN_PAYLOAD)
    extra['review_status'] = 'checked'
    invalid_payloads.append(extra)
    missing = deepcopy(GOLDEN_PAYLOAD)
    del missing['origins']
    invalid_payloads.append(missing)
    boolean_version = deepcopy(GOLDEN_PAYLOAD)
    boolean_version['item_row_version'] = True
    invalid_payloads.append(boolean_version)
    bad_mode = deepcopy(GOLDEN_PAYLOAD)
    bad_mode['label_mode'] = None
    invalid_payloads.append(bad_mode)
    uppercase_uuid = deepcopy(GOLDEN_PAYLOAD)
    uppercase_uuid['components'][0]['component_public_id'] = (
        'AAAAAAAA-1111-4111-8111-111111111111'
    )
    invalid_payloads.append(uppercase_uuid)
    null_text = deepcopy(GOLDEN_PAYLOAD)
    null_text['components'][0]['component_text'] = None
    invalid_payloads.append(null_text)
    zero_version = deepcopy(GOLDEN_PAYLOAD)
    zero_version['components'][0]['stored_component_row_version'] = 0
    invalid_payloads.append(zero_version)
    internal_id = deepcopy(GOLDEN_PAYLOAD)
    internal_id['labels'][0]['id'] = 9
    invalid_payloads.append(internal_id)
    bad_presence = deepcopy(GOLDEN_PAYLOAD)
    bad_presence['allergens'][0]['presence'] = 'trace'
    invalid_payloads.append(bad_presence)
    null_origin = deepcopy(GOLDEN_PAYLOAD)
    null_origin['origins'][0]['text'] = None
    invalid_payloads.append(null_origin)
    unordered = deepcopy(GOLDEN_PAYLOAD)
    unordered['labels'] = [
        {'code': 'Z', 'name': 'Z'},
        {'code': 'A', 'name': 'A'},
    ]
    invalid_payloads.append(unordered)

    for payload in invalid_payloads:
        with pytest.raises(ValueError):
            _review_token(payload)
