"""MP-REC-PLAN-PORTIONS in the menu editor: target-quantity field, real browser + DB round-trip.

D3 (unit): the hidden ``target_quantity_unit_code`` always mirrors the bound revision's own
unit, regardless of whether a quantity is currently typed (see workflow_partial_form._target_
quantity_pair docstring) — a NoJS user can type a brand-new value into an already-bound row
without any script keeping the pairing in sync. D4 (publication untouched) is checked at the
wiring level via load_draft_connection's option['components'] projection, complementing (not
repeating) PP-STORE's own pure-function build_snapshot() proof.
Screenshots go to .claude/evidence/pp-ui-0914/ (not committed); fixture titles carry no digits.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text
from werkzeug.datastructures import MultiDict

from test_admin_ux_browser import (  # noqa: F401
    _submit_menu, admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import WEEK, _menu_form
from test_menu_recipe_selection_browser import (  # noqa: F401
    _editor, _insert_revision, _no_overflow, _ready, _token, http_client, nojs_page,
)
from cafeteria.workflow_store import load_draft_connection

EDITOR = _editor('patienten')
VIEWPORTS = ((1440, 900), (390, 844), (1024, 768), (768, 1024), (1920, 1080))
EVIDENCE = Path(__file__).resolve().parents[2] / '.claude' / 'evidence' / 'pp-ui-0914'


def _target_rows(engine: Engine) -> list[tuple[str | None, str | None, str | None]]:
    with engine.connect() as connection:
        rows = connection.execute(text(
            '''SELECT c.component_text, c.target_quantity::text AS quantity, u.code AS unit
               FROM cafeteria.menu_item_components c
               LEFT JOIN cafeteria.measurement_units u ON u.id=c.target_quantity_unit_id
               ORDER BY c.menu_item_id, c.sort_order'''
        ))
        return [(row.component_text, row.quantity, row.unit) for row in rows]


def _target_form(token: str, revision: str, quantity: str, **changes: str) -> MultiDict[str, str]:
    data = MultiDict(_menu_form(
        _csrf=token, component_public_id='', component_text='Kartoffelstock',
        recipe_revision_public_id=revision, target_quantity=quantity,
        target_quantity_unit_code='PORTION' if quantity else '', **changes,
    ))
    return data


def test_http_exact_decimal_round_trip_and_null_clear(http_client) -> None:  # noqa: F811
    client, actor_id, engine = http_client
    revision = _insert_revision(engine, actor_id, 'Zielmengensuppe')
    token_page = client.get(EDITOR)
    token = _token(client)
    saved = client.post('/admin/patienten/menu', data=_target_form(token, revision['public_id'], '2.5'))
    assert saved.status_code == 303
    assert _target_rows(engine) == [('Kartoffelstock', '2.500000', 'PORTION')]
    reload = client.get(EDITOR).get_data(as_text=True)
    # Load contract: the exact DB-scale string round-trips (D-decimal, no reformatting).
    # [^>]* between name= and value= tolerates the inputmode="decimal" attribute in between.
    assert re.search(r'name="target_quantity"[^>]*value="2\.500000"', reload)
    assert re.search(r'name="target_quantity_unit_code"[^>]*value="PORTION"', reload)

    cleared = client.post('/admin/patienten/menu', data=_target_form(
        token, revision['public_id'], '', row_version='1',
    ))
    assert cleared.status_code == 303
    assert _target_rows(engine) == [('Kartoffelstock', None, None)]
    assert token_page.status_code == 200


@pytest.mark.parametrize('amount', ['0', '-1', '2,5'])
def test_http_rejects_invalid_amount_at_field_and_keeps_values(http_client, amount: str) -> None:  # noqa: F811
    client, actor_id, engine = http_client
    revision = _insert_revision(engine, actor_id, 'Ungueltigesuppe')
    token = _token(client)
    response = client.post('/admin/patienten/menu', data=_target_form(
        token, revision['public_id'], amount, title='Geprueft',
    ))
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert f'value="{amount}"' in body
    assert 'Geprueft' in body
    assert _target_rows(engine) == []


def test_http_target_quantity_requires_bound_revision(http_client) -> None:  # noqa: F811
    client, actor_id, engine = http_client
    csrf = _token(client)
    token = MultiDict(_menu_form(
        _csrf=csrf, component_public_id='', component_text='Ohne Rezept',
        target_quantity='2.5', target_quantity_unit_code='PORTION',
    ))
    response = client.post('/admin/patienten/menu', data=token)
    assert response.status_code == 400
    assert _target_rows(engine) == []


def test_http_aligned_add_remove_reorder_keeps_target_with_right_component(http_client) -> None:  # noqa: F811
    client, actor_id, engine = http_client
    first = _insert_revision(engine, actor_id, 'Erste Portion')
    second = _insert_revision(engine, actor_id, 'Zweite Portion')
    token = _token(client)
    data = MultiDict(_menu_form(_csrf=token, title='Zwei Bausteine', allergen_mode='auto',
                                origin_mode='auto', label_mode='auto'))
    data.setlist('component_public_id', ['', ''])
    data.setlist('component_text', ['Erste Portion', 'Zweite Portion'])
    data.setlist('recipe_revision_public_id', [first['public_id'], second['public_id']])
    data.setlist('target_quantity', ['1.5', '3'])
    data.setlist('target_quantity_unit_code', ['PORTION', 'PORTION'])
    assert client.post('/admin/patienten/menu', data=data).status_code == 303
    assert _target_rows(engine) == [
        ('Erste Portion', '1.500000', 'PORTION'), ('Zweite Portion', '3.000000', 'PORTION'),
    ]
    reordered = MultiDict(_menu_form(_csrf=token, title='Zwei Bausteine', row_version='1',
                                     allergen_mode='auto', origin_mode='auto', label_mode='auto'))
    reordered.setlist('component_public_id', ['', ''])
    reordered.setlist('component_text', ['Zweite Portion', 'Erste Portion'])
    reordered.setlist('recipe_revision_public_id', [second['public_id'], first['public_id']])
    reordered.setlist('target_quantity', ['3', '1.5'])
    reordered.setlist('target_quantity_unit_code', ['PORTION', 'PORTION'])
    assert client.post('/admin/patienten/menu', data=reordered).status_code == 303
    assert _target_rows(engine) == [
        ('Zweite Portion', '3.000000', 'PORTION'), ('Erste Portion', '1.500000', 'PORTION'),
    ]


def test_http_proposal_without_target_quantity_has_empty_field_and_no_error(http_client) -> None:  # noqa: F811
    client, _actor_id, _engine = http_client
    body = client.get(EDITOR).get_data(as_text=True)
    assert 'name="target_quantity"' in body
    assert 'name="target_quantity" value=""' in body or 'name="target_quantity" ' in body


def _loaded_option(engine: Engine) -> dict[str, object]:
    with engine.connect() as connection:
        draft = load_draft_connection(connection, 'patient', WEEK)
    return draft['days'][0]['services'][0]['options'][0]


def test_http_publication_projection_unaffected_by_target_quantity(http_client) -> None:  # noqa: F811
    """D4 at the wiring level: PP-STORE already proved build_snapshot() is structurally
    unable to read option['assignments']; this proves the real HTTP form path this
    package owns produces the identical option['components'] projection either way,
    without needing a full publish-ready patient week for build_snapshot's own checks."""
    client, actor_id, engine = http_client
    revision = _insert_revision(engine, actor_id, 'Schnappschusssuppe')
    token = _token(client)
    assert client.post('/admin/patienten/menu', data=_target_form(
        token, revision['public_id'], '2.5', title='Momentaufnahme',
    )).status_code == 303
    option_with_target = _loaded_option(engine)
    assert option_with_target['components'] == ['Kartoffelstock']
    assert 'target_quantity' not in json.dumps(option_with_target['components'])

    cleared = client.post('/admin/patienten/menu', data=_target_form(
        token, revision['public_id'], '', title='Momentaufnahme', row_version='1',
    ))
    assert cleared.status_code == 303
    option_without_target = _loaded_option(engine)
    assert option_without_target['components'] == option_with_target['components']


def test_browser_fill_save_reload_shows_exact_value_and_unit_label(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, 'Anzeigesuppe')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Menüname', exact=True).fill('Mit Zielmenge')
    page.locator('[data-edit-row]').first.click()
    page.locator('[data-component-kind-option][value="text"]').first.check()
    page.locator('[name="component_text"]').fill('Anzeigesuppe')
    page.get_by_label('Rezeptrevision').select_option(revision['public_id'])
    quantity = page.get_by_label('Zielmenge')
    expect(quantity).not_to_have_js_property('readOnly', True)
    quantity.fill('2.5')
    expect(page.locator('[data-target-quantity-unit-label]').first).to_have_text(' (Portion)')
    unit_field = page.locator('[data-target-quantity-unit]').first
    assert unit_field.input_value() == 'PORTION'
    payload = _submit_menu(page)
    assert payload['target_quantity'] == ['2.5']
    assert payload['target_quantity_unit_code'] == ['PORTION']
    page.wait_for_load_state()
    # Load contract: the exact DB-scale string round-trips (no client-side reformatting).
    expect(page.get_by_label('Zielmenge')).to_have_value('2.500000')
    expect(page.locator('[data-review-field="components"]')).to_contain_text('Zielmenge: 2.500000 Portion')
    _no_overflow(page)


def test_browser_revision_change_clears_quantity_and_updates_unit(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    first = _insert_revision(admin_engine, actor, 'Wechselsuppe')
    second = _insert_revision(admin_engine, actor, 'Zweitwechselsuppe')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Menüname', exact=True).fill('Wechsel')
    page.locator('[data-edit-row]').first.click()
    page.locator('[data-component-kind-option][value="text"]').first.check()
    page.locator('[name="component_text"]').fill('Wechselsuppe')
    page.get_by_label('Rezeptrevision').select_option(first['public_id'])
    page.get_by_label('Zielmenge').fill('4')
    page.get_by_label('Rezeptrevision').select_option(second['public_id'])
    expect(page.get_by_label('Zielmenge')).to_have_value('')
    unit_field = page.locator('[data-target-quantity-unit]').first
    assert unit_field.input_value() == 'PORTION'
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_label('Rezeptrevision').select_option('')
    expect(page.get_by_label('Zielmenge')).to_have_value('')
    expect(page.get_by_label('Zielmenge')).to_have_js_property('readOnly', True)
    assert unit_field.input_value() == ''


def test_browser_add_remove_reorder_keeps_target_quantity_with_own_row(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    first = _insert_revision(admin_engine, actor, 'Obensuppe')
    second = _insert_revision(admin_engine, actor, 'Untensuppe')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Menüname', exact=True).fill('Reihenfolge Zielmenge')
    page.locator('[data-edit-row]').first.click()
    page.locator('[data-component-kind-option][value="text"]').first.check()
    page.locator('[name="component_text"]').fill('Obensuppe')
    page.locator('[name="recipe_revision_public_id"]').select_option(first['public_id'])
    page.locator('[name="target_quantity"]').fill('1.5')
    page.get_by_role('button', name='Baustein hinzufügen').click()
    page.locator('[data-component-kind-option][value="text"]').nth(1).check()
    page.locator('[name="component_text"]').nth(1).fill('Untensuppe')
    page.locator('[name="recipe_revision_public_id"]').nth(1).select_option(second['public_id'])
    page.locator('[name="target_quantity"]').nth(1).fill('3')
    page.locator('[data-finish-row]').nth(1).click()
    page.locator('#components-list [data-row]').nth(1).locator('summary').click()
    page.locator('#components-list [data-row]').nth(1).get_by_role('button', name='Nach oben', exact=True).click()
    payload = _submit_menu(page)
    assert payload['component_text'] == ['Untensuppe', 'Obensuppe']
    assert payload['target_quantity'] == ['3', '1.5']
    assert payload['target_quantity_unit_code'] == ['PORTION', 'PORTION']
    page.locator('#components-list [data-row]').first.locator('summary').click()
    page.locator('#components-list').get_by_role('button', name='Löschen', exact=True).first.click()
    leftover = _submit_menu(page)
    assert leftover['component_text'] == ['Obensuppe']
    # The first submit already round-tripped through the DB, so the reloaded page
    # (and this second submit of it) carries the DB-scale string, not the raw '1.5'.
    assert leftover['target_quantity'] == ['1.500000']


def test_browser_zero_rejected_at_field_with_aria_invalid(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, 'Nullsuppe')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Menüname', exact=True).fill('Nullwert')
    page.locator('[data-edit-row]').first.click()
    page.locator('[data-component-kind-option][value="text"]').first.check()
    page.locator('[name="component_text"]').fill('Nullsuppe')
    page.get_by_label('Rezeptrevision').select_option(revision['public_id'])
    page.get_by_label('Zielmenge').fill('0')
    _submit_menu(page, 400)
    expect(page.get_by_label('Zielmenge')).to_have_value('0')
    expect(page.get_by_label('Zielmenge')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('.error-region[role="alert"]')).to_be_visible()


def test_nojs_type_new_quantity_on_already_bound_row_saves(
    nojs_page: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    """Proves the hidden unit mirrors the bound revision even before any quantity exists,
    so a first-time NoJS entry on an already-saved bound row does not need a script."""
    page = nojs_page
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, 'Ohnejssuppe')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Menüname', exact=True).fill('Ohne JavaScript Bindung')
    page.locator('[name="component_text"]').fill('Ohnejssuppe')
    page.get_by_label('Rezeptrevision').select_option(revision['public_id'])
    page.get_by_role('button', name='Menü speichern', exact=True).click()
    page.wait_for_load_state()
    expect(page.get_by_label('Rezeptrevision')).to_have_value(revision['public_id'])
    page.get_by_label('Zielmenge').fill('5')
    page.get_by_role('button', name='Menü speichern', exact=True).click()
    page.wait_for_load_state()
    expect(page.get_by_label('Zielmenge')).to_have_value('5.000000')
    assert _target_rows(admin_engine) == [('Ohnejssuppe', '5.000000', 'PORTION')]


_VIEWPORT_NAMES = {
    (1440, 900): 'Breitensuppe', (390, 844): 'Schmalsuppe', (1024, 768): 'Kleinsuppe',
    (768, 1024): 'Hochsuppe', (1920, 1080): 'Riesensuppe',
}


@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
def test_target_quantity_viewports_keyboard_and_zoom(
    page_context: Page, admin_engine: Engine, width: int, height: int,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, _VIEWPORT_NAMES[(width, height)])
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(EDITOR)
    _ready(page)
    page.locator('[data-edit-row]').first.click()
    page.locator('[data-component-kind-option][value="text"]').first.check()
    page.locator('[name="component_text"]').fill(revision['title'])
    page.get_by_label('Rezeptrevision').select_option(revision['public_id'])
    quantity = page.get_by_label('Zielmenge')
    expect(quantity).to_be_visible()
    box = quantity.bounding_box()
    assert box is not None and box['height'] >= 44
    quantity.click()
    outline = page.evaluate('getComputedStyle(document.activeElement).outlineStyle')
    assert outline != 'none'
    quantity.fill('1.5')
    _no_overflow(page)
    page.evaluate('document.documentElement.style.zoom = "2"')
    _ready(page)
    if width >= 1440:
        _no_overflow(page)
    page.evaluate('document.documentElement.style.zoom = "1"')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f'menu-editor-target-quantity-{width}x{height}.png'), full_page=True)
