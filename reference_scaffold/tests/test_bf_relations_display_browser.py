"""BF-T14: editing/archiving a recipe head preserves the bound frozen revision."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from test_admin_workflow_db import _actor_id
from test_admin_workflow_routes import DAY
from test_bf_state_dimensions_browser import (  # noqa: F401
    FAMILIES, _editor, admin_app, admin_engine, bf_page, browser, javascript_enabled, live_server,
)
from test_menu_recipe_selection_browser import _bound, _insert_revision


def _bind_and_change_recipe(
    bf_page: Page, admin_engine: Engine, family: str,  # noqa: F811
    javascript_enabled: bool,  # noqa: F811
) -> tuple:
    page = bf_page
    actor = _actor_id(admin_engine)
    first = _insert_revision(admin_engine, actor, 'Ursprüngliche Suppe', servings='4')
    page.goto(_editor(family))
    page.get_by_label('Menüname', exact=True).fill('Menü mit festem Rezeptstand')
    if javascript_enabled:
        page.locator('[data-edit-row]').first.click()
        page.locator('[data-component-kind-option][value="text"]').first.check()
    page.locator('[name="component_text"]').fill('Ursprüngliche Suppe')
    page.get_by_label('Rezeptrevision', exact=True).select_option(first['public_id'])
    if family == 'cafeteria':
        if page.locator('#sec-output-texts').get_attribute('open') is None:
            page.locator('#sec-output-texts > summary').click()
        page.locator('[name="internal_chf"]').fill('9.50')
        page.locator('[name="external_chf"]').fill('14.50')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        page.locator('form[data-menu-editor] button[type="submit"].btn-primary').click()
    assert saved.value.status == 303
    page.wait_for_load_state()
    binding = {'recipe_revision_public_id': first['public_id'], 'hash': first['hash']}
    assert _bound(admin_engine) == binding
    later = _insert_revision(
        admin_engine, actor, 'Umbenannte Suppe', revision_number=2,
        recipe_id=int(first['recipe_id']), servings='9',
    )
    assert later['public_id'] != first['public_id'] and later['hash'] != first['hash']
    return first, binding


@pytest.mark.parametrize('family,profile', FAMILIES)
def test_t14_bound_revision_survives_recipe_change_and_archive(
    bf_page: Page, admin_engine: Engine, family: str, profile: str,  # noqa: F811
    javascript_enabled: bool,  # noqa: F811
) -> None:
    first, binding = _bind_and_change_recipe(bf_page, admin_engine, family, javascript_enabled)
    page = bf_page
    for archived in (False, True):
        if archived:
            with admin_engine.begin() as connection:
                connection.execute(text(
                    'UPDATE cafeteria.recipes SET active=false WHERE id=:id',
                ), {'id': int(first['recipe_id'])})
        page.goto(_editor(family))
        if javascript_enabled:
            page.locator('[data-edit-row]').first.click()
        select = page.get_by_label('Rezeptrevision', exact=True)
        expect(select).to_be_visible()
        expect(select).to_have_value(first['public_id'])
        selected = select.locator('option:checked')
        expect(selected).to_contain_text('Ursprüngliche Suppe · Revision 1 · 4 PORTION')
        expect(selected).not_to_contain_text('Umbenannte Suppe')
        expect(selected).to_have_attribute('data-content-hash', first['hash'])
        expect(selected).to_have_attribute('data-archived', '1' if archived else '0')
        if archived:
            expect(selected).to_contain_text('(archiviert)')
        expect(page.locator('#component-0-recipe-hint')).to_be_visible()
        expect(page.locator('#component-0-recipe-hint')).to_contain_text(
            'Titel und Ausbeute stammen unveränderlich aus der jeweiligen Revision',
        )
        expect(page.locator('[data-review-field="components"]')).to_contain_text(
            'Deklarierte Ausbeute: 4',
        )
        page.goto(f'/admin/{family}?week={DAY}')
        card = page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1')
        expect(card).to_contain_text('Ursprüngliche Suppe')
        expect(card).not_to_contain_text('Umbenannte Suppe')
        assert _bound(admin_engine) == binding


# BF-Lücke: reference_scaffold/cafeteria/templates/admin/_week_menu_card.html:17
@pytest.mark.parametrize('family,profile', FAMILIES)
@pytest.mark.parametrize('archived', (False, True), ids=('changed', 'archived'))
def test_t14_week_card_explains_bound_revision_and_archive(
    bf_page: Page, admin_engine: Engine, family: str, profile: str, archived: bool,  # noqa: F811
    javascript_enabled: bool,  # noqa: F811
) -> None:
    first, binding = _bind_and_change_recipe(bf_page, admin_engine, family, javascript_enabled)
    if archived:
        with admin_engine.begin() as connection:
            connection.execute(text(
                'UPDATE cafeteria.recipes SET active=false WHERE id=:id',
            ), {'id': int(first['recipe_id'])})
    page = bf_page
    page.goto(f'/admin/{family}?week={DAY}')
    card = page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1')
    expect(card).to_contain_text('Ursprüngliche Suppe')
    assert _bound(admin_engine) == binding
    visible = card.inner_text()
    assert 'Revision 1' in visible, f'Feste Rezeptrevision fehlt auf Wochenkarte: {visible}'
    if archived:
        assert 'archiviert' in visible.lower(), f'Archivierte Quelle bleibt unerklärt: {visible}'
