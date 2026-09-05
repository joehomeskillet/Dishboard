from __future__ import annotations

import re
import threading
from wsgiref.simple_server import make_server

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from test_rendered_ui import _login, admin_app, admin_engine, browser  # noqa: E402, F401
from test_admin_workflow_routes import DAY  # noqa: E402, F401
from test_admin_workflow_db import _save, _staff_values  # noqa: E402

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
def page_context(browser: Browser, live_server: str, admin_app: Flask, admin_engine):  # noqa: F811
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
    return page

def test_admin_overview_viewport_matrix_has_no_horizontal_overflow(page_context: Page):
    page = page_context
    for path in ['/admin/cafeteria', '/admin/patienten']:
        page.goto(path)
        for w, h, zoom in [(390, 844, 1), (1440, 1100, 1), (2560, 1440, 1), (1440, 1100, 0.5)]:
            page.set_viewport_size({"width": w, "height": h})
            if zoom != 1:
                page.evaluate(f'document.body.style.zoom="{zoom}"')
            else:
                page.evaluate('document.body.style.zoom="1"')
            page.wait_for_timeout(50)
            
            overflow = page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
            assert not overflow, f"Horizontal overflow on {path} at {w}x{h} zoom {zoom}"

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

def test_admin_editor_dirty_state_blocks_preview_and_publish(page_context: Page):
    page = page_context
    page.goto(f'/admin/cafeteria?week={DAY}')
    page.fill('input[name="title"]', 'Neuer Titel')

    preview_link = page.locator('.admin-actions a[target="_blank"]')
    publish_button = page.locator('form[action*="/publish"] button[type="submit"]')
    assert preview_link.get_attribute('aria-disabled') == 'true'
    assert publish_button.is_disabled()
    assert page.get_by_text('Zuerst speichern', exact=True).first.is_visible()


def test_admin_publish_uses_native_confirm(page_context: Page, admin_app: Flask):
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
    page.goto(f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    page.evaluate('''() => {
        const details = document.createElement('details');
        details.open = true;
        const summary = document.createElement('summary');
        summary.textContent = 'Test';
        details.appendChild(summary);
        document.body.appendChild(details);
    }''')
    page.keyboard.press('Escape')
    assert not page.locator('details').evaluate('el => el.hasAttribute("open")')

def test_admin_patient_pages_have_no_cost_vocabulary_in_dom(page_context: Page):
    page = page_context
    page.goto('/admin/patienten')
    html = page.content()
    assert not re.search(r'preis|chf|rappen|kosten|price', html, re.IGNORECASE)
