"""Origin-only submits must preserve saved recipe bindings and target quantities."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from test_menu_form_intents import (
    _posted_selects, _revision, _rows, _save_payload_from_editor, _state, _token,
    _two_row_form,
)
from test_menu_form_intents import active_location, admin_app, admin_engine, client  # noqa: F401


def _bindings(engine):
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text(
            '''SELECT c.sort_order, c.component_text, rr.public_id::text,
                      rr.content_hash_sha256, c.target_quantity::text, u.code, mi.row_version
               FROM cafeteria.menu_item_components c
               JOIN cafeteria.menu_items mi ON mi.id=c.menu_item_id
               LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
               LEFT JOIN cafeteria.measurement_units u ON u.id=c.target_quantity_unit_id
               ORDER BY c.menu_item_id, c.sort_order'''))]


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('intent', ('origin_add', 'origin_remove:1'))
@pytest.mark.parametrize('field', (
    'recipe_revision_public_id', 'target_quantity', 'target_quantity_unit_code',
))
@pytest.mark.parametrize('shape', ('missing', 'shifted'))
def test_origin_intents_reject_malformed_components_and_preserve_saved_bindings(  # noqa: F811
    client, family, intent, field, shape,  # noqa: F811
):
    session_client, actor, engine = client
    first = _revision(engine, actor, 'Origin binding A')
    second = _revision(engine, actor, 'Origin binding B')
    token = _token(session_client, family)
    url = f'/admin/{family}/menu'
    prices = {'internal_chf': '9.50', 'external_chf': '12.00'} if family == 'cafeteria' else {}
    created = _two_row_form(token, first['public_id'], second['public_id'], **prices)
    assert session_client.post(url, data=created).status_code == 303
    bound = _bindings(engine)
    assert [row[1:6] for row in bound] == [
        ('Erste Zeile', first['public_id'], first['hash'], '2.500000', 'PORTION'),
        ('Zweite Zeile', second['public_id'], second['hash'], '7.000000', 'PORTION'),
    ]
    before = _state(engine)
    data = _two_row_form(token, first['public_id'], second['public_id'], row_version='1',
                         form_intent=intent, **prices)
    data['origin_mode'] = 'manual'
    data.setlist('origin_ingredient', ['Poulet', 'Kartoffeln'])
    data.setlist('origin_country_code', ['CH', 'DE'])
    if shape == 'missing':
        del data[field]
    else:
        data.setlist(field, data.getlist(field)[:1])

    response = session_client.post(url, data=data)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert _posted_selects(html, 'recipe_revision_public_id') == [first['public_id'], second['public_id']]
    assert _rows(html, 'target_quantity') == ['2.500000', '7.000000']
    assert _rows(html, 'target_quantity_unit_code') == ['PORTION', 'PORTION']
    assert _bindings(engine) == bound
    assert _state(engine) == before

    # Submit the form actually returned by the rejected intent, not the original payload.
    saved = session_client.post(url, data=_save_payload_from_editor(html, url, family))
    assert saved.status_code == 303
    after = _bindings(engine)
    assert [row[:-1] for row in after] == [row[:-1] for row in bound]
    assert [row[-1] for row in after] == [row[-1] + 1 for row in bound]


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('intent', ('origin_add', 'origin_remove:1'))
def test_origin_intents_may_omit_whole_component_group_without_detaching(client, family, intent):  # noqa: F811
    session_client, actor, engine = client
    first = _revision(engine, actor, 'Omitted binding A')
    second = _revision(engine, actor, 'Omitted binding B')
    token = _token(session_client, family)
    url = f'/admin/{family}/menu'
    prices = {'internal_chf': '9.50', 'external_chf': '12.00'} if family == 'cafeteria' else {}
    created = _two_row_form(token, first['public_id'], second['public_id'], **prices)
    assert session_client.post(url, data=created).status_code == 303
    bound, before = _bindings(engine), _state(engine)
    data = _two_row_form(token, first['public_id'], second['public_id'], row_version='1',
                         form_intent=intent, **prices)
    for field in ('component_public_id', 'component_text', 'recipe_revision_public_id',
                  'target_quantity', 'target_quantity_unit_code'):
        del data[field]
    data['origin_mode'] = 'manual'
    data.setlist('origin_ingredient', ['Poulet', 'Kartoffeln'])
    data.setlist('origin_country_code', ['CH', 'DE'])
    response = session_client.post(url, data=data)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert _posted_selects(html, 'recipe_revision_public_id') == [first['public_id'], second['public_id']]
    assert _rows(html, 'target_quantity') == ['2.500000', '7.000000']
    assert _bindings(engine) == bound
    assert _state(engine) == before
    assert session_client.post(url, data=_save_payload_from_editor(html, url, family)).status_code == 303
    assert [row[:-1] for row in _bindings(engine)] == [row[:-1] for row in bound]
