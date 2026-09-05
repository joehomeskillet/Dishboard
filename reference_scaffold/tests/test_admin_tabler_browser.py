from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from flask import render_template_string
from playwright.sync_api import expect

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine, browser as browser,
    live_server as live_server, page_context as page_context,
)
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_rendered_ui import app as app


def test_shared_macros_expose_errors_labels_and_touch_targets(page_context, admin_app):
    with admin_app.test_request_context('/admin/patienten/wochen'):
        html = render_template_string('''
            {% extends 'admin/base_tabler.html' %}
            {% from 'admin/_macros.html' import field, check, status %}
            {% block content %}
              {{ field('title', 'Testtitel', '<unverändert>', id='test-title', error='Titel prüfen') }}
              {{ check('review', 'Gespeicherten Stand geprüft', id='test-review') }}
              {{ status('review_open', 'Prüfung offen') }}
            {% endblock %}
        ''', family='patienten', profile='patient')
    page = page_context
    page.goto('/admin/patienten/wochen')
    page.set_content(html, wait_until='load')
    field = page.get_by_label('Testtitel', exact=True)
    expect(field).to_have_value('<unverändert>')
    expect(field).to_have_attribute('aria-invalid', 'true')
    expect(field).to_have_attribute('aria-describedby', 'test-title-error')
    expect(page.locator('#test-title-error')).to_have_text('Titel prüfen')
    check = page.get_by_label('Gespeicherten Stand geprüft', exact=True)
    assert page.locator('label[for="test-review"]').bounding_box()['height'] >= 48
    page.locator('label[for="test-review"]').click()
    expect(check).to_be_checked()
    expect(page.get_by_text('Prüfung offen', exact=True)).to_be_visible()


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_tabler_lists_preserve_navigation_and_tablet_layout(page_context, admin_engine, family):
    _save(admin_engine, 'staff_guest', _staff_values())
    _save(admin_engine, 'patient', _patient_values())
    page = page_context
    for route, row in [('menues', '[data-menu-id]'), ('wochen', '[data-week-id]')]:
        response = page.goto(f'/admin/{family}/{route}')
        assert response.status == 200
        expect(page.locator(row).first).to_be_visible()
        assert page.locator('link[href$="vendor/tabler/tabler.min.css"]').count() == 1
        assert page.locator('link[href$="/app.css"]').count() == 0
        assert page.locator('script[src$="vendor/tabler/tabler.min.js"]').count() == 1
        assert page.locator('svg use[href*="tabler-icons.svg#"]').count() > 5
        assert page.locator('[style], script:not([src])').count() == 0
        if family == 'patienten':
            assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I)
        for width, height in [(360, 800), (768, 1024), (820, 1180), (1024, 768), (1199, 800), (1200, 800), (1280, 800)]:
            page.set_viewport_size({'width': width, 'height': height})
            toggle = page.get_by_role('button', name='Menü', exact=True)
            nav = page.get_by_role('navigation', name='Backend')
            if width < 1200:
                expect(toggle).to_be_visible()
                assert toggle.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
                if toggle.get_attribute('aria-expanded') == 'true':
                    toggle.click()
                expect(nav).to_be_hidden()
                toggle.focus()
                page.keyboard.press('Enter')
                expect(toggle).to_have_attribute('aria-expanded', 'true')
                expect(page.locator('#sidebar-menu')).to_have_class(re.compile(r'\bshow\b'))
                expect(nav).to_be_visible()
            else:
                expect(toggle).to_be_hidden()
                expect(nav).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (route, width)
            assert page.get_by_label('Kompakte Ansicht', exact=True).locator('..').bounding_box()['height'] >= 48
            for control in page.locator('input[type="date"], input[name="title"], textarea, button[type="submit"]').all():
                assert control.bounding_box()['height'] >= 48, (width, control.evaluate('(el) => el.outerHTML'))
            for link in page.get_by_role('navigation', name='Backend').get_by_role('link').all():
                expect(link).to_be_visible()
                assert link.bounding_box()['height'] >= 48
            if width < 1200:
                toggle.focus()
                page.keyboard.press('Space')
                expect(toggle).to_have_attribute('aria-expanded', 'false')
                expect(nav).to_be_hidden()
                expect(toggle).to_be_focused()
            output = os.environ.get('TABLER_PROOF_DIR')
            if output:
                directory = Path(output)
                directory.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(directory / f'{family}-{route}-{width}x{height}.png'), full_page=True)
        page.locator(f'{row} a[href]').first.click()
        assert '/menu?' in page.url if route == 'menues' else f'/admin/{family}?' in page.url


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_legacy_week_sidebar_keeps_content_beside_it(page_context, admin_engine, family):
    _save(admin_engine, 'staff_guest', _staff_values())
    _save(admin_engine, 'patient', _patient_values())
    page = page_context
    page.set_viewport_size({'width': 1280, 'height': 800})
    assert page.goto(f'/admin/{family}').status == 200
    main = page.locator('main.admin-main').bounding_box()
    sidebar = page.locator('.admin-sidebar').bounding_box()
    assert main['y'] < 120, 'The existing week must not move below a full-height sidebar.'
    assert main['x'] >= sidebar['x'] + sidebar['width'] - 1
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_tabler_styles_do_not_load_on_public_or_login_pages(app):
    client = app.test_client()
    for route in ('/auth/local', '/cafeteria/wochenangebot/', '/patienten/wochenplan/'):
        response = client.get(route)
        assert response.status_code == 200, route
        assert 'tabler' not in response.get_data(as_text=True)
