"""Native helper responses retain unsaved state across document reloads."""
from __future__ import annotations

from pathlib import Path
import re

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY
from test_menu_form_intents import _state
from test_menu_form_intents_browser import (
    _BEFOREUNLOAD_BLOCKED, _actor, _fill_component, _filler_recipes, _stored, _target,
)

SAVE = 'form[data-menu-editor] [data-sticky] button[data-semantic="actions.save"]:not([formaction])'


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('intent', ('recipe_search', 'recipe_page_next', 'recipe_page_previous'))
def test_native_recipe_helper_keeps_pending_values_and_leave_guard(
    page_context: Page, admin_engine: Engine, family: str, intent: str, tmp_path: Path,  # noqa: F811
) -> None:
    page = page_context
    url = f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    actor = _actor(admin_engine)
    _filler_recipes(admin_engine, actor)
    bound = _target(admin_engine, actor, 'Pending Rezept')
    page.goto(url)
    title = page.get_by_label('Menüname', exact=True)
    title.fill('Gespeicherter Titel')
    _fill_component(page, 0, 'Gebundene Zeile')
    page.locator('select[name="recipe_revision_public_id"]').select_option(bound['public_id'])
    if family == 'cafeteria':
        page.locator('[name="internal_chf"]').fill('9.50')
        page.locator('[name="external_chf"]').fill('12.00')
    with page.expect_response(lambda response: response.request.method == 'POST'
                              and response.url.endswith('/menu')) as saved:
        page.locator(SAVE).click()
    assert saved.value.status == 303
    page.wait_for_load_state()

    page.goto(url)
    page.wait_for_load_state()
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is False
    note = page.locator('[data-menu-editor-dirty-note]')
    expect(note.locator('[data-dirty-status]')).to_have_text('')
    expect(note).not_to_have_class(re.compile(r'\bis-dirty\b'))
    review = page.locator('form[action$="/menu/review"] button[type="submit"]')
    expect(review).to_be_enabled()
    before, bindings = _state(admin_engine), _stored(admin_engine)
    title.fill('Behaltener Entwurf')
    if intent == 'recipe_page_previous':
        with page.expect_response(lambda response: response.request.method == 'POST'
                                  and response.url.endswith('/menu')) as advanced:
            page.locator('button[name="form_intent"][value="recipe_page_next"]').click()
        assert advanced.value.status == 200
        page.wait_for_load_state()
        expect(page.locator('[name="recipe_offset"]')).to_have_value('50')
    with page.expect_response(lambda response: response.request.method == 'POST'
                              and response.url.endswith('/menu')) as submitted:
        page.locator(f'button[name="form_intent"][value="{intent}"]').click()
    assert submitted.value.status == 200
    page.wait_for_load_state()
    expect(title).to_have_value('Behaltener Entwurf')
    expect(page.locator('form[data-menu-editor]')).to_have_attribute('data-form-pending', 'true')
    expect(note).to_be_visible()
    expect(note).to_have_class(re.compile(r'\bis-dirty\b'))
    expect(note.locator('[data-dirty-status]')).to_have_text('Nicht gespeichert')
    expect(review).to_be_disabled()
    assert _state(admin_engine) == before
    assert _stored(admin_engine) == bindings

    # A later recomputation must not treat retained POST values as a clean baseline.
    title.fill('Behaltener Entwurf geändert')
    title.fill('Behaltener Entwurf')
    expect(note.locator('[data-dirty-status]')).to_have_text('Nicht gespeichert')
    expect(review).to_be_disabled()
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is True
    posts = []
    page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
    review.evaluate('button => button.click()')
    assert posts == []
    for preview in page.locator('a[href*="/preview"]').all():
        expect(preview).to_have_attribute('aria-disabled', 'true')

    dialogs = []

    def dismiss(dialog):
        dialogs.append(dialog.type)
        dialog.dismiss()

    page.once('dialog', dismiss)
    current = page.url
    page.get_by_role('link', name='Abbrechen', exact=True).click()
    assert dialogs == ['beforeunload']
    assert page.url == current
    expect(title).to_have_value('Behaltener Entwurf')
    expect(review).to_be_disabled()
    page.locator('main').screenshot(path=str(tmp_path / f'menu-form-pending-{family}-{intent}.png'))

    with page.expect_response(lambda response: response.request.method == 'POST'
                              and response.url.endswith('/menu')) as saved:
        page.locator(SAVE).click()
    assert saved.value.status == 303
    page.wait_for_load_state()
    expect(title).to_have_value('Behaltener Entwurf')
    assert page.locator('form[data-menu-editor]').get_attribute('data-form-pending') is None
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is False
    expect(note.locator('[data-dirty-status]')).to_have_text('')
    expect(note).not_to_have_class(re.compile(r'\bis-dirty\b'))
    expect(review).to_be_enabled()
    page.goto(url)
    page.wait_for_load_state()
    expect(title).to_have_value('Behaltener Entwurf')
    expect(note.locator('[data-dirty-status]')).to_have_text('')
    expect(note).not_to_have_class(re.compile(r'\bis-dirty\b'))
    expect(review).to_be_enabled()
    assert page.evaluate(_BEFOREUNLOAD_BLOCKED) is False
