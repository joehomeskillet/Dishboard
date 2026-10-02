"""Regression coverage for accessible shell logout and long header text."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import pytest
from flask import render_template_string
from playwright.sync_api import expect

from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _cookie, _goto, _page, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'state' / 'ui-shell-evidence'
LONG_NAME = 'A' * 80


def _screenshot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / name), full_page=True)


def test_mobile_logout_remains_reachable_without_javascript(site, database_engine):  # noqa: F811
    app, origin, engine, chromium = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    context = chromium.new_context(
        base_url=origin,
        viewport={'width': 390, 'height': 844},
        java_script_enabled=False,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        reduced_motion='reduce',
    )
    context.add_cookies([_cookie(app, client, origin)])
    page = context.new_page()
    try:
        _goto(page, '/admin/cafeteria')
        disclosure = page.locator('details.admin-nojs-nav')
        expect(disclosure).to_be_visible()
        expect(disclosure.locator('.admin-nav')).to_be_hidden()
        summary = disclosure.locator('summary')
        expect(summary).to_have_attribute('aria-label', 'Menü')
        expect(summary.locator('.navbar-toggler-icon')).to_have_count(1)
        assert summary.inner_text().strip() == ''
        disclosure.locator('summary').click()
        expect(disclosure.locator('.admin-nav')).to_be_visible()
        form = page.locator('form.admin-logout-form:visible')
        expect(form).to_have_count(1)
        expect(form).to_have_attribute('method', 'post')
        logout = form.get_by_role('button', name='Abmelden', exact=True)
        expect(logout).to_have_text('Abmelden')
        expect(logout.locator('svg, .nav-link-icon')).to_have_count(0)
        csrf = form.locator('input[name="_csrf"]').input_value()
        assert csrf
        _screenshot(page, 'cafeteria-nojs-390x844.png')

        captured = {}

        def intercept_logout(route):
            captured['request'] = route.request
            route.fulfill(status=200, content_type='text/html', body='<p>Abgemeldet</p>')

        page.route('**/auth/logout', intercept_logout)
        form.get_by_role('button', name='Abmelden').click()
        request = captured['request']
        assert request.method == 'POST'
        assert parse_qs(request.post_data or '') == {'_csrf': [csrf]}
    finally:
        context.close()

    page = _page(site, client, viewport={'width': 390, 'height': 844})
    try:
        _goto(page, '/admin/cafeteria')
        expect(page.locator('form.admin-logout-form')).to_have_count(1)
        toggle = page.get_by_role('button', name='Menü', exact=True)
        assert toggle.inner_text().strip() == ''
        expect(toggle.locator('.navbar-toggler-icon')).to_have_count(1)
        toggle.click()
        expect(page.locator('form.admin-logout-form')).to_be_visible()
        expect(page.get_by_role('button', name='Abmelden', exact=True)).to_have_text('Abmelden')
        _screenshot(page, 'cafeteria-js-390x844.png')
    finally:
        page.context.close()

    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    try:
        _goto(page, '/admin/cafeteria')
        page.locator('[data-admin-nav-toggle]').click()
        logout = page.get_by_role('button', name='Abmelden', exact=True)
        expect(logout).to_be_visible()
        expect(logout).to_have_text('Abmelden')
        expect(logout.locator('svg')).to_have_count(0)
        assert logout.evaluate('''el => {
            const text = document.createRange(); text.selectNodeContents(el);
            const label = text.getBoundingClientRect();
            const rail = el.closest('aside').getBoundingClientRect();
            return label.width > 1 && label.x >= rail.x && label.right <= rail.right;
        }''')
        _screenshot(page, 'cafeteria-collapsed-1440x900.png')
    finally:
        page.context.close()


def test_long_page_title_and_breadcrumb_wrap_at_mobile_zoom(site, database_engine):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])

    @app.get('/__shell__/long-title')
    def long_title():
        return render_template_string(
            """{% extends 'admin/base_tabler.html' %}
            {% from 'admin/_macros.html' import page_header %}
            {% block page_header %}{{ page_header(title, description=title,
                breadcrumbs=[('Bausteine', '/admin/cafeteria/komponenten'), (title,)]) }}{% endblock %}
            {% block content %}<p>Shell-Titelprüfung</p>{% endblock %}""",
            title=LONG_NAME,
            family='cafeteria',
            profile='staff_guest',
        )

    page = _page(site, client, viewport={'width': 390, 'height': 844})
    try:
        _goto(page, '/__shell__/long-title')
        page.evaluate("document.documentElement.style.zoom = '2'")
        heading = page.locator('h1.page-title')
        breadcrumb = page.locator('.breadcrumb-item.active')
        expect(heading).to_be_visible()
        expect(heading).to_have_text(LONG_NAME)
        expect(breadcrumb).to_have_text(LONG_NAME)
        assert heading.evaluate("el => getComputedStyle(el).overflowWrap") == 'anywhere'
        assert breadcrumb.evaluate("el => getComputedStyle(el).overflowWrap") == 'anywhere'
        metrics = page.evaluate('''() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            overflowers: [...document.querySelectorAll('body *')]
                .filter(el => el.getBoundingClientRect().right > document.documentElement.clientWidth)
                .map(el => `${el.tagName}.${el.className}`)
                .slice(0, 10),
        })''')
        assert metrics['scrollWidth'] <= metrics['clientWidth'], metrics
        _screenshot(page, 'component-long-title-zoom200-390x844.png')
    finally:
        page.context.close()
