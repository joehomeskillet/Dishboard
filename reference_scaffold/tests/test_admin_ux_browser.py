from __future__ import annotations

import re
import threading
from collections.abc import Iterator
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from test_rendered_ui import _login, admin_app, admin_engine, browser  # noqa: E402, F401
from test_admin_workflow_routes import DAY, _scope  # noqa: E402
from test_admin_workflow_db import _save, _staff_values  # noqa: E402
from cafeteria.component_catalog_store import (  # noqa: E402
    AdminScope, archive_component, create_component,
)

@pytest.fixture
def live_server(admin_app: Flask) -> str:  # noqa: F811

    server = make_server('127.0.0.1', 0, admin_app)
    host, port = server.server_address
    url = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield url
    server.shutdown()
    server.server_close()
    thread.join(timeout=1)

@pytest.fixture
def page_context(browser: Browser, live_server: str, admin_app: Flask, admin_engine) -> Iterator[Page]:  # noqa: F811
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    context = browser.new_context(base_url=live_server)
    
    cookie = client.get_cookie('session')
            
    if cookie:
        context.add_cookies([{
            'name': 'session',
            'value': cookie.value,
            'domain': '127.0.0.1',
            'path': '/',
            'httpOnly': True,
        }])
        
    page = context.new_page()
    page.emulate_media(reduced_motion='reduce')
    try:
        yield page
    finally:
        context.close()

def test_admin_overview_viewport_matrix_has_no_horizontal_overflow(page_context: Page):
    page = page_context
    for path in ['/admin/cafeteria', '/admin/patienten']:
        page.goto(path)
        for w, h in [(390, 844), (1440, 1100), (2560, 1440)]:
            page.set_viewport_size({"width": w, "height": h})
            overflow = page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
            assert not overflow, f"Horizontal overflow on {path} at {w}x{h}"

def test_admin_overview_keyboard_order_focus_and_targets(page_context: Page):
    page = page_context
    page.goto('/admin/cafeteria')
    page.set_viewport_size({"width": 390, "height": 844})
    
    targets_ok = page.evaluate('''() => {
        let ok = true;
        document.querySelectorAll('.btn').forEach(btn => {
            const rect = btn.getBoundingClientRect();
            if (rect.width > 0 && (rect.width < 44 || rect.height < 44)) ok = false;
        });
        document.querySelectorAll('input[type="checkbox"]').forEach(chk => {
            const label = chk.closest('label') || document.querySelector(`label[for="${chk.id}"]`);
            if (label) {
                const rect = label.getBoundingClientRect();
                if (rect.width > 0 && (rect.width < 44 || rect.height < 44)) ok = false;
            }
        });
        return ok;
    }''')
    assert targets_ok, "Touch targets too small"
    
    page.keyboard.press("Tab")
    outline = page.evaluate('window.getComputedStyle(document.activeElement).outlineStyle')
    assert outline != 'none', "Focus outline is not visible"

@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_admin_editor_dirty_state_blocks_preview_and_publish(page_context: Page, family: str):
    page = page_context
    page.goto(f'/admin/{family}?week={DAY}')
    page.fill('input[name="title"]', 'Neuer Titel')

    preview_links = page.locator('a[href*="/preview"]')
    publish_button = page.locator('form[action*="/publish"] button[type="submit"]')
    assert preview_links.count() >= 1
    for preview_link in preview_links.all():
        assert preview_link.get_attribute('aria-disabled') == 'true'
        preview_link.focus()
        page.keyboard.press('Enter')
    assert page.context.pages == [page]
    assert f'/admin/{family}?week={DAY}' in page.url
    assert publish_button.is_disabled()
    assert page.get_by_text('Zuerst speichern', exact=True).first.is_visible()


def test_admin_publish_uses_native_confirm(page_context: Page, admin_app: Flask):  # noqa: F811
    _save(admin_app.extensions['cafeteria_db'], 'staff_guest', _staff_values())
    page = page_context
    page.goto(f'/admin/cafeteria?week={DAY}')

    publish_btn = page.locator('form[action*="/publish"] button[type="submit"]')
    assert publish_btn.is_enabled()
    assert page.locator('.status-pill').get_attribute('data-status') == 'ready'

    dialogs: list[str] = []

    def dismiss(dialog) -> None:
        dialogs.append(dialog.type)
        dialog.dismiss()

    page.once('dialog', dismiss)
    publish_btn.click()
    assert dialogs == ['confirm']
    assert page.locator('.status-pill').get_attribute('data-status') == 'ready'

    page.once('dialog', lambda dialog: dialog.accept())
    publish_btn.click()
    assert page.locator('.status-pill').get_attribute('data-status') == 'live'

def test_admin_error_state_focuses_first_error_and_offers_retry(page_context: Page):
    page = page_context
    page.goto(f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    page.fill('input[name="internal_chf"]', 'invalid')
    page.click('button[type="submit"]')
    
    page.wait_for_selector('.error-region[role="alert"]')
    page.wait_for_function(
        'document.activeElement.getAttribute("aria-invalid") === "true"'
    )
    assert page.evaluate('document.activeElement.getAttribute("aria-invalid")') == 'true'
    assert page.locator('.error-region button:has-text("Erneut versuchen")').is_visible()

def test_admin_escape_closes_details_and_restores_focus(page_context: Page):
    page = page_context
    page.goto('/admin/cafeteria/komponenten')
    summary = page.locator('#create-component summary')
    summary.click()
    assert page.locator('#create-component').get_attribute('open') is not None
    page.keyboard.press('Escape')
    assert page.locator('#create-component').get_attribute('open') is None
    expect(summary).to_be_focused()

def test_admin_patient_pages_have_no_cost_vocabulary_in_dom(page_context: Page):
    page = page_context
    page.goto('/admin/patienten')
    html = page.content()
    assert not re.search(r'preis|chf|rappen|kosten|price', html, re.IGNORECASE)


@pytest.fixture
def catalog_component(admin_app: Flask, admin_engine: Engine) -> tuple[dict, AdminScope]:  # noqa: F811
    _, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, user_id)
    component = create_component(admin_engine, scope, 'side', 'Kartoffelstock', 'CH', 'common', (), ())
    return component, scope


def _open_menu(page: Page, family: str, width: int, height: int) -> None:
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    page.get_by_label('Titel', exact=True).fill('Herbstteller')
    page.get_by_label('Beschreibung', exact=True).fill('Mit Gemüse')
    page.get_by_label('Hinweis', exact=True).fill('Frisch zubereitet')
    if family == 'cafeteria':
        page.locator('[name="internal_chf"]').fill('9.50')
        page.locator('[name="external_chf"]').fill('14.50')
    for mode in ('allergen', 'origin', 'label'):
        page.locator(f'[name="{mode}_mode"][value="auto"]').check()


def _submit_menu(page: Page, status: int = 303) -> dict[str, list[str]]:
    with page.expect_response(
        lambda response: response.request.method == 'POST' and response.url.endswith('/menu')
    ) as submitted:
        page.locator('form[data-menu-editor] button[type="submit"]').click()
    response = submitted.value
    assert response.status == status
    data = response.request.post_data
    assert data is not None
    page.wait_for_load_state()
    return parse_qs(data, keep_blank_values=True)


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_menu_native_auto_form_saves_and_reloads_without_optional_rows(
    page_context: Page, family: str, width: int, height: int,
) -> None:
    page = page_context
    _open_menu(page, family, width, height)
    payload = _submit_menu(page)
    assert not any(name.endswith('[]') for name in payload)
    assert not any(name in payload for name in (
        'component_public_id', 'component_text', 'allergen_code', 'allergen_presence',
        'origin_ingredient', 'origin_country_code', 'label_code',
    ))
    page.reload()
    expect(page.get_by_label('Titel', exact=True)).to_have_value('Herbstteller')
    expect(page.get_by_label('Beschreibung', exact=True)).to_have_value('Mit Gemüse')
    expect(page.get_by_label('Hinweis', exact=True)).to_have_value('Frisch zubereitet')
    expect(page.locator('form[data-menu-editor] [name="row_version"]')).to_have_value('1')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_menu_manual_metadata_and_optional_rows_roundtrip(
    page_context: Page, width: int, height: int,
) -> None:
    page = page_context
    _open_menu(page, 'patienten', width, height)
    for mode in ('allergen', 'origin', 'label'):
        page.locator(f'[name="{mode}_mode"][value="manual"]').check()
    for index, text in enumerate(('Blattsalat', 'Gebäck')):
        if index:
            page.get_by_role('button', name='Komponente hinzufügen').click()
        page.locator('[name="component_text"]').nth(index).fill(text)
    page.get_by_role('button', name='Komponente hinzufügen').click()
    page.get_by_role('button', name='Komponente entfernen').last.click()
    page.get_by_role('button', name='Komponente hinzufügen').click()
    for index, (ingredient, country) in enumerate((('Rind', 'CH'), ('Kartoffel', 'DE'))):
        if index:
            page.get_by_role('button', name='Herkunft hinzufügen').click()
        page.locator('[name="origin_ingredient"]').nth(index).fill(ingredient)
        page.locator('[name="origin_country_code"]').nth(index).fill(country)
    page.get_by_role('button', name='Herkunft hinzufügen').click()
    page.get_by_role('button', name='Herkunft entfernen').last.click()
    page.get_by_role('button', name='Herkunft hinzufügen').click()
    for code, presence in (('MILK', 'may_contain'), ('GLUTEN', 'contains')):
        checkbox = page.locator(f'[name="allergen_code"][value="{code}"]')
        checkbox.check()
        checkbox.locator('xpath=ancestor::div[@class="allergen-row"]').locator('select').select_option(presence)
    page.locator('[name="label_code"][value="VEGAN"]').check()
    payload = _submit_menu(page)
    assert payload['component_text'] == ['Blattsalat', 'Gebäck']
    assert payload['component_public_id'] == ['', '']
    assert payload['origin_ingredient'] == ['Rind', 'Kartoffel']
    assert payload['origin_country_code'] == ['CH', 'DE']
    assert dict(zip(payload['allergen_code'], payload['allergen_presence'], strict=True)) == {
        'MILK': 'may_contain', 'GLUTEN': 'contains',
    }
    page.reload()
    expect(page.locator('[name="component_text"]').nth(1)).to_have_value('Gebäck')
    expect(page.locator('[name="origin_country_code"]').nth(1)).to_have_value('DE')
    expect(page.locator('[name="allergen_code"][value="MILK"]')).to_be_checked()
    expect(page.locator('.allergen-row').filter(has=page.locator('[value="MILK"]')).locator('select')).to_have_value('may_contain')
    expect(page.locator('[name="label_code"][value="VEGAN"]')).to_be_checked()
    for mode in ('allergen', 'origin', 'label'):
        page.locator(f'[name="{mode}_mode"][value="auto"]').check()
    payload = _submit_menu(page)
    assert not any(name in payload for name in (
        'allergen_code', 'allergen_presence', 'origin_ingredient', 'origin_country_code', 'label_code',
    ))


@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_menu_partial_origin_stays_invalid_and_preserves_input(
    page_context: Page, width: int, height: int,
) -> None:
    page = page_context
    _open_menu(page, 'patienten', width, height)
    page.locator('[name="origin_mode"][value="manual"]').check()
    page.locator('[name="origin_ingredient"]').fill('Rind')
    payload = _submit_menu(page, 400)
    assert payload['origin_ingredient'] == ['Rind']
    assert payload['origin_country_code'] == ['']
    expect(page.get_by_label('Titel', exact=True)).to_have_value('Herbstteller')
    expect(page.locator('[name="origin_ingredient"]')).to_have_value('Rind')
    expect(page.locator('[name="origin_country_code"]')).to_be_focused()
    page.locator('[name="origin_country_code"]').fill('CH')
    _submit_menu(page)


@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_menu_catalog_pair_errors_and_archived_assignment_survive(
    page_context: Page, catalog_component: tuple[dict, AdminScope],
    admin_engine: Engine, width: int, height: int,  # noqa: F811
) -> None:
    component, scope = catalog_component
    public_id = str(component['public_id'])
    page = page_context
    _open_menu(page, 'patienten', width, height)
    page.locator('[name="component_public_id"]').select_option(public_id)
    page.locator('[name="component_text"]').fill('Ungültige zweite Auswahl')
    payload = _submit_menu(page, 400)
    assert payload['component_public_id'] == [public_id]
    assert payload['component_text'] == ['Ungültige zweite Auswahl']
    expect(page.locator('[name="component_public_id"]')).to_have_value(public_id)
    expect(page.locator('[name="component_text"]')).to_have_value('Ungültige zweite Auswahl')
    page.locator('[name="component_text"]').fill('')
    _submit_menu(page)
    archive_component(admin_engine, scope, public_id, int(component['row_version']))
    page.reload()
    expect(page.locator('[name="component_public_id"]')).to_have_value(public_id)
    assert page.locator(f'option[value="{public_id}"]').is_disabled()
    assert _submit_menu(page)['component_public_id'] == [public_id]


def test_cancelled_archive_confirm_keeps_unsaved_changes_guard(
    page_context: Page, catalog_component: tuple[dict, AdminScope],
) -> None:
    component, _ = catalog_component
    page = page_context
    page.goto(f'/admin/patienten/komponenten/{component["public_id"]}')
    page.get_by_label('Name', exact=True).fill('Noch nicht gespeichert')
    dialogs: list[str] = []

    def dismiss(dialog) -> None:
        dialogs.append(dialog.type)
        dialog.dismiss()

    page.once('dialog', dismiss)
    page.locator('form[action$="/archive"] button').click()
    assert dialogs == ['confirm']
    page.once('dialog', dismiss)
    page.get_by_role('link', name='Zurück zur Liste').click()
    assert dialogs == ['confirm', 'beforeunload']
    expect(page.get_by_label('Name', exact=True)).to_have_value('Noch nicht gespeichert')
