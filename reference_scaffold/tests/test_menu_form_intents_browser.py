"""Menu form intents in a real browser with JavaScript disabled.

The acceptance walk of the work package: add two differently bound component rows,
reverse them, remove one, search and page past the first bounded page, save, reload and
verify the exact revision identifiers, content hashes and order in PostgreSQL. Nothing
may be written before the deliberate save, and the progressive JavaScript path must run
the same operations without submitting the form twice.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY
from test_menu_form_intents import _state
from test_menu_recipe_choices_reader import active_location, create_recipe, freeze_revision
from test_menu_recipe_selection_browser import nojs_page  # noqa: F401
from test_rendered_ui import PATIENT_FORBIDDEN

EDITOR = f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
FILLER = 55
SAVE = 'form[data-menu-editor] [data-sticky] button[data-semantic="actions.save"]:not([formaction])'


def _native_menu_form_contract(before: dict, after: dict) -> dict:
    """Validate every new view control, then compare the original save contract."""
    intents = [
        'recipe_search', 'recipe_page_previous', 'recipe_page_next',
        'component_move_up:0', 'component_move_down:0', 'component_remove:0',
        'component_add', 'origin_remove:0', 'origin_add',
    ]
    view_names = {'recipe_search', 'recipe_offset', 'form_intent'}
    assert [field for field in after['namedFields'] if field[0] in view_names] == [
        ['recipe_search', '', False, None], ['recipe_offset', '0', False, None],
        *[['form_intent', intent, intent in intents[1:3], None] for intent in intents],
    ]
    assert [field for field in after['fields'] if field[0] in view_names] == [
        ['recipe_search', ''], ['recipe_offset', '0'],
    ]
    added_submitters = [
        ['', '', None, False, None],
        *[['form_intent', intent, None, True, None] for intent in intents],
    ]
    assert after['submitters'] == added_submitters + before['submitters']
    return {
        **after,
        'namedFields': [field for field in after['namedFields'] if field[0] not in view_names],
        'fields': [field for field in after['fields'] if field[0] not in view_names],
        'submitters': after['submitters'][len(added_submitters):],
    }


def _actor(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(
            text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())


def _filler_recipes(engine: Engine, actor_id: int) -> None:
    """Enough active recipes that the wanted options only exist on a later page."""
    location_id = active_location(engine)
    with engine.begin() as connection:
        ids = [int(row.id) for row in connection.execute(text(
            '''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,servings,
               servings_unit_id,source_kind,active)
               SELECT :location,:actor,:actor,'Serie '||to_char(n,'FM000'),4,u.id,'manual',true
               FROM generate_series(1,:count) n,cafeteria.measurement_units u
               WHERE u.code='PORTION' RETURNING id'''),
            {'location': location_id, 'actor': actor_id, 'count': FILLER})]
        connection.execute(text(
            '''INSERT INTO cafeteria.recipe_revisions(location_id,recipe_id,revision_number,
               snapshot_json,content_hash_sha256,created_by)
               SELECT r.location_id,r.id,1,cafeteria.recipe_snapshot_v22(r.id),
                encode(public.digest(convert_to(cafeteria.recipe_snapshot_v22(r.id)::text,'UTF8'),'sha256'),'hex'),
                :actor
               FROM cafeteria.recipes r WHERE r.id=ANY(:ids)'''),
            {'actor': actor_id, 'ids': ids})
    assert len(ids) == FILLER


def _target(engine: Engine, actor_id: int, title: str) -> dict[str, str]:
    recipe_id = create_recipe(engine, actor_id, title, servings='4')
    frozen = freeze_revision(engine, actor_id, recipe_id)
    return {'public_id': frozen['public_id'], 'hash': frozen['hash'], 'title': title}


def _stored(engine: Engine) -> list[tuple[int, str, str | None, str | None]]:
    with engine.connect() as connection:
        return [
            (int(row.sort_order), str(row.component_text or ''), row.revision, row.hash)
            for row in connection.execute(text(
                '''SELECT c.sort_order, c.component_text, rr.public_id::text AS revision,
                          rr.content_hash_sha256 AS hash
                   FROM cafeteria.menu_item_components c
                   LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
                   ORDER BY c.menu_item_id, c.sort_order'''))
        ]


def _fill_component(page: Page, index: int, value: str) -> None:
    row = page.locator('#components-list [data-row]').nth(index)
    kind = row.locator('[data-component-kind-option][value="text"]')
    if kind.is_visible():
        kind.check()
    row.locator('[name="component_text"]').fill(value)


def _submit(page: Page, name: str) -> None:
    value = {'Suchen': 'recipe_search', 'Nächste Seite': 'recipe_page_next',
             'Vorherige Seite': 'recipe_page_previous',
             'Komponente hinzufügen': 'component_add'}[name]
    page.locator(f'button[name="form_intent"][value="{value}"]').click()
    page.wait_for_load_state()


def _submit_row(page: Page, index: int, name: str) -> None:
    value = {'Nach oben': 'component_move_up', 'Komponente entfernen': 'component_remove'}[name]
    page.locator(f'button[name="form_intent"][value="{value}:{index}"]').click()
    page.wait_for_load_state()


def test_nojs_add_reverse_remove_search_page_and_save(
    nojs_page: Page, admin_engine: Engine, tmp_path: Path,  # noqa: F811
) -> None:
    page = nojs_page
    actor_id = _actor(admin_engine)
    _filler_recipes(admin_engine, actor_id)
    first = _target(admin_engine, actor_id, 'Zielsauce Alpha')
    second = _target(admin_engine, actor_id, 'Zielsauce Beta')
    before = _state(admin_engine)

    page.goto(EDITOR)
    page.wait_for_load_state()
    page.get_by_label('Menüname', exact=True).fill('Ohne JavaScript geplant')
    _fill_component(page, 0, 'Erste Komponente')

    # The wanted options are not on the first bounded page.
    assert first['public_id'] not in page.content()
    _submit(page, 'Nächste Seite')
    assert first['public_id'] in page.content()
    expect(page.get_by_label('Menüname', exact=True)).to_have_value('Ohne JavaScript geplant')
    expect(page.locator('[name="component_text"]')).to_have_value('Erste Komponente')

    _submit(page, 'Komponente hinzufügen')
    rows = page.locator('#components-list [data-row]')
    expect(rows).to_have_count(2)
    assert page.evaluate('document.activeElement.id') == 'component-1-id'
    _fill_component(page, 1, 'Zweite Komponente')

    # A real server search over the whole eligible set, not a client-side option filter.
    page.get_by_role('searchbox', name='Rezeptauswahl durchsuchen', exact=True).fill('Zielsauce')
    _submit(page, 'Suchen')
    assert page.evaluate('document.activeElement.id') == 'recipe-search'
    expect(page.locator('[name="component_text"]').nth(1)).to_have_value('Zweite Komponente')
    selects = page.locator('select[name="recipe_revision_public_id"]')
    selects.nth(0).select_option(first['public_id'])
    selects.nth(1).select_option(second['public_id'])

    _submit_row(page, 1, 'Nach oben')
    assert page.evaluate('document.activeElement.id') == 'component-0-id'
    expect(page.locator('[name="component_text"]').first).to_have_value('Zweite Komponente')
    expect(page.locator('select[name="recipe_revision_public_id"]').first).to_have_value(
        second['public_id'])

    _submit(page, 'Komponente hinzufügen')
    expect(page.locator('#components-list [data-row]')).to_have_count(3)
    _submit_row(page, 2, 'Komponente entfernen')
    expect(page.locator('#components-list [data-row]')).to_have_count(2)

    assert _state(admin_engine) == before, 'Ein Formular-Intent hat geschrieben.'

    page.locator(SAVE).click()
    page.wait_for_load_state()
    # sort_order is 1-based in this schema; the reversal must be the stored order.
    assert _stored(admin_engine) == [
        (1, 'Zweite Komponente', second['public_id'], second['hash']),
        (2, 'Erste Komponente', first['public_id'], first['hash']),
    ]

    page.goto(EDITOR)
    page.wait_for_load_state()
    reloaded = page.locator('select[name="recipe_revision_public_id"]')
    expect(reloaded.nth(0)).to_have_value(second['public_id'])
    expect(reloaded.nth(1)).to_have_value(first['public_id'])
    assert PATIENT_FORBIDDEN.search(page.content()) is None
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.locator('main').screenshot(path=str(tmp_path / 'menu-form-intents-nojs.png'))


def test_nojs_enter_in_a_text_field_saves_instead_of_running_an_intent(
    nojs_page: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    """Implicit submission uses the form's first submit button, not the first intent."""
    page = nojs_page
    actor_id = _actor(admin_engine)
    bound = _target(admin_engine, actor_id, 'Eingabesauce')
    page.goto(EDITOR)
    page.wait_for_load_state()
    _fill_component(page, 0, 'Erste Komponente')
    page.get_by_label('Rezeptrevision', exact=True).select_option(bound['public_id'])
    title = page.get_by_label('Menüname', exact=True)
    title.fill('Mit Eingabetaste gespeichert')
    title.press('Enter')
    page.wait_for_load_state()
    assert _stored(admin_engine) == [(1, 'Erste Komponente', bound['public_id'], bound['hash'])]
    expect(page.locator('#components-list [data-row]')).to_have_count(1)


@pytest.mark.parametrize(('width', 'height'), ((1440, 900), (390, 844)))
def test_nojs_intent_controls_stay_usable_on_both_viewports(
    nojs_page: Page, admin_engine: Engine, width: int, height: int, tmp_path: Path,  # noqa: F811
) -> None:
    page = nojs_page
    actor_id = _actor(admin_engine)
    _target(admin_engine, actor_id, f'Sichtsauce {width}')
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(EDITOR)
    page.wait_for_load_state()
    for name in ('recipe_search', 'recipe_page_next', 'recipe_page_previous', 'component_add',
                 'component_remove:0', 'component_move_up:0', 'component_move_down:0', 'origin_add'):
        control = page.locator(f'button[name="form_intent"][value="{name}"]').first
        expect(control).to_be_visible()
        box = control.bounding_box()
        minimum = page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches ? 44 : 36")
        assert box is not None and box['height'] >= minimum, f'{name} bei {width}px zu klein'
    search = page.get_by_role('searchbox', name='Rezeptauswahl durchsuchen', exact=True)
    expect(search).to_be_visible()
    search_box = search.bounding_box()
    assert search_box is not None and search_box['height'] >= minimum
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.locator('main').screenshot(path=str(tmp_path / f'menu-form-intents-{width}x{height}.png'))
    _submit(page, 'Komponente hinzufügen')
    expect(page.locator('#components-list [data-row]')).to_have_count(2)
    search.fill('Sichtsauce')
    _submit(page, 'Suchen')
    expect(page.locator('#components-list [data-row]')).to_have_count(2)
    page.locator('main').screenshot(path=str(tmp_path / f'menu-form-intents-search-{width}x{height}.png'))


def test_javascript_enhances_the_same_row_actions_without_a_second_submit(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    actor_id = _actor(admin_engine)
    bound = _target(admin_engine, actor_id, 'Verbesserte Sauce')
    before = _state(admin_engine)
    page.goto(EDITOR)
    page.wait_for_load_state()
    page.get_by_label('Menüname', exact=True).fill('Mit JavaScript')
    _fill_component(page, 0, 'Erste Komponente')
    page.get_by_label('Rezeptrevision').select_option(bound['public_id'])

    posts: list[str] = []
    page.on('request', lambda request: posts.append(request.url)
            if request.method == 'POST' else None)
    page.locator('[data-add-row="components-list"]').click()
    expect(page.locator('#components-list [data-row]')).to_have_count(2)
    _fill_component(page, 1, 'Zweite Komponente')
    page.locator('#components-list [data-row]').nth(1).locator('[data-move-row="up"]').click()
    expect(page.locator('[name="component_text"]').first).to_have_value('Zweite Komponente')
    assert posts == [], 'Die JavaScript-Bedienung hat zusätzlich abgeschickt.'
    assert _state(admin_engine) == before

    # The locally rearranged rows still carry the correct native fallback positions.
    values = page.locator('#components-list [data-row]').nth(1).locator(
        'button[name="form_intent"]').evaluate_all('els => els.map(el => el.value)')
    assert values == ['component_move_up:1', 'component_move_down:1', 'component_remove:1']

    with page.expect_response(
        lambda response: response.request.method == 'POST' and response.url.endswith('/menu')
    ) as submitted:
        page.locator(SAVE).click()
    assert submitted.value.status == 303
    page.wait_for_load_state()
    assert [row[1] for row in _stored(admin_engine)] == ['Zweite Komponente', 'Erste Komponente']


_BEFOREUNLOAD_BLOCKED = """() => {
  const event = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(event);
  return Boolean(event.defaultPrevented || event.returnValue === '');
}"""


def test_javascript_row_move_and_remove_after_fresh_get_mark_dirty(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    """A fresh GET plus only a local row action must restore the leave-page warning.

    The previous JS test filled title first, so isDirty was already true and missed
    the regression: row move/remove no longer dispatch the generic input event.
    """
    page = page_context
    actor_id = _actor(admin_engine)
    first = _target(admin_engine, actor_id, 'Dirty-Erste')
    second = _target(admin_engine, actor_id, 'Dirty-Zweite')
    page.goto(EDITOR)
    page.wait_for_load_state()
    page.get_by_label('Menüname', exact=True).fill('Frisch geladen')
    _fill_component(page, 0, 'Erste Komponente')
    page.get_by_label('Rezeptrevision').first.select_option(first['public_id'])
    page.locator('[data-add-row="components-list"]').click()
    _fill_component(page, 1, 'Zweite Komponente')
    page.locator('select[name="recipe_revision_public_id"]').nth(1).select_option(second['public_id'])
    with page.expect_response(
        lambda response: response.request.method == 'POST' and response.url.endswith('/menu')
    ) as submitted:
        page.locator(SAVE).click()
    assert submitted.value.status == 303
    page.wait_for_load_state()

    page.goto(EDITOR)
    page.wait_for_load_state()
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is False

    posts: list[str] = []
    page.on('request', lambda request: posts.append(request.url)
            if request.method == 'POST' else None)
    page.locator('#components-list [data-row]').nth(1).locator('[data-move-row="up"]').click()
    expect(page.locator('[name="component_text"]').first).to_have_value('Zweite Komponente')
    assert posts == [], 'Die JavaScript-Bedienung hat zusätzlich abgeschickt.'
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is True
    values = page.locator('#components-list [data-row]').nth(1).locator(
        'button[name="form_intent"]').evaluate_all('els => els.map(el => el.value)')
    assert values == ['component_move_up:1', 'component_move_down:1', 'component_remove:1']

    dialogs: list[str] = []

    def dismiss(dialog) -> None:
        dialogs.append(dialog.type)
        dialog.dismiss()

    page.once('dialog', dismiss)
    page.get_by_role('link', name='Abbrechen', exact=True).click()
    assert 'beforeunload' in dialogs

    page.goto(EDITOR)
    page.wait_for_load_state()
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is False
    page.locator('#components-list [data-row]').nth(1).get_by_role(
        'button', name='Baustein löschen', exact=True).click()
    expect(page.locator('#components-list [data-row]')).to_have_count(1)
    assert posts == [], 'Entfernen hat zusätzlich abgeschickt.'
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is True
