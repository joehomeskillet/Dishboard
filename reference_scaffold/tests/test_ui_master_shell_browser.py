"""Chromium evidence for MP-UI-SHELL: grouped nav, 992px breakpoint, layout variants."""
from __future__ import annotations

import re
from threading import Thread

import pytest
from flask import abort, render_template_string, session
from playwright.sync_api import Page, expect
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria import db as cafeteria_db
from cafeteria.admin import display_routes
from cafeteria.branding_config import contrast
from cafeteria.display_settings import DEFAULT_ADMIN_DISPLAY
from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
GROUPS = {
    'Arbeitsbereich': ('Wochenpläne', 'Wochenverwaltung', 'Menüs', 'Komponenten'),
    'Rezepte': ('Rezepte', 'Kochbücher', 'Grundlagen'),
    'Ausgabe': ('Screens', 'Vorlagen'),
    'Daten & Schnittstellen': ('CSV Import', 'API & Schnittstellen'),
    'System': ('Benutzer & Zugriff', 'Design & Marke', 'Bereiche & Zeiten'),
}
ROLE_CLAIMS = {
    'Cafeteria.Editor': ('00000000-0000-0000-0000-0000000000ed', 'inventory-editor', 'Redaktion'),
    'Cafeteria.Publisher': ('00000000-0000-0000-0000-0000000000ab', 'inventory-publisher', 'Publikation'),
}


def _hex(value: str) -> str:
    if value.startswith('#'):
        return value.lower()
    nums = value[value.find('(') + 1:value.rfind(')')].split(',')[:3]
    return '#' + ''.join(f'{int(float(n.strip())):02x}' for n in nums)


def _cookie(app, client, origin: str) -> dict:
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    return {'name': cookie.key, 'value': cookie.value, 'url': origin}


def _role_client(app, engine, role: str):
    oid, sub, name = ROLE_CLAIMS[role]
    user_id = cafeteria_db.upsert_entra_user(
        engine,
        {'tid': '00000000-0000-0000-0000-000000000001', 'oid': oid, 'sub': sub,
         'name': name, 'preferred_username': f'{role.split(".")[1].lower()}@example.invalid'},
        [role],
    )
    with engine.connect() as connection:
        version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user_id},
        ).scalar_one()
    client = app.test_client()
    with client.session_transaction() as current:
        current.update(user={'id': user_id, 'name': name}, authz_version=int(version))
        current['_csrf_token'] = f'shell-{role}'
    return client, user_id


@pytest.fixture
def site(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    app = _factory(monkeypatch, tmp_path, database_engine)

    @app.get('/__shell__/empty')
    def shell_empty():
        return render_template_string(
            "{% extends 'admin/base_tabler.html' %}{% block content %}<p id='shell-empty'>leer</p>{% endblock %}",
            family='cafeteria', profile='staff_guest',
        )

    @app.get('/__shell__/<variant>')
    def shell_variant(variant: str):
        if variant not in {'standard', 'narrow', 'workspace'}:
            abort(404)
        return render_template_string(
            """{% extends 'admin/base_tabler.html' %}
            {% set layout_variant = variant %}
            {% block page_header %}
            <div class="container-xl"><div class="page-header-row">
              <div class="page-header-copy"><h1>Shell-Variante</h1>
              <p class="page-header-subtitle">Prüft Containerbreite und Seitenkopf.</p></div>
              <div class="page-header-actions btn-list"><a class="btn" href="#aktion">Aktion</a></div>
            </div></div>
            {% endblock %}
            {% block content %}<p id="shell-body">{{ variant }}</p>{% endblock %}""",
            family='cafeteria', profile='staff_guest', variant=variant,
        )

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        yield app, origin, database_engine, browser
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _page(site, client, **kwargs) -> Page:
    app, origin, _, chromium = site
    context = chromium.new_context(
        base_url=origin, locale='de-CH', timezone_id='Europe/Zurich',
        reduced_motion='reduce', **kwargs,
    )
    context.add_cookies([_cookie(app, client, origin)])
    return context.new_page()


def _goto(page, path: str):
    response = page.goto(path, wait_until='networkidle')
    assert response is not None and response.status == 200
    page.evaluate('document.fonts.ready')
    return response


def _titles(page) -> list[str]:
    return page.locator('.admin-nav .nav-link-title').all_inner_texts()


def _groups(page) -> list[str]:
    return [text.strip() for text in page.locator('.admin-nav .nav-group-label').all_text_contents()]


def test_navigation_roles_targets_and_current(site, database_engine):  # noqa: F811
    app, origin, engine, _ = site
    admin, _ = _login(app, engine, ['Cafeteria.Admin'])
    clients = {'Cafeteria.Admin': admin}
    for role in ROLE_CLAIMS:
        clients[role], _ = _role_client(app, engine, role)
    for role, client in clients.items():
        page = _page(site, client, viewport={'width': 1440, 'height': 900})
        _goto(page, '/admin/cafeteria')
        expected_groups = list(GROUPS)
        if role != 'Cafeteria.Admin':
            expected_groups.remove('System')
        assert _groups(page) == expected_groups
        expected = [item for group in expected_groups for item in GROUPS[group]]
        assert _titles(page) == expected
        current = page.locator('.admin-nav a[aria-current="page"] .nav-link-title')
        expect(current).to_have_text('Wochenpläne')
        expect(page.locator('.admin-user-role')).to_have_text(
            {'Cafeteria.Admin': 'Administration', 'Cafeteria.Publisher': 'Freigabe & Redaktion',
             'Cafeteria.Editor': 'Küchenplanung'}[role],
        )
        for link in page.locator('.admin-nav a.nav-link').all():
            href = link.get_attribute('href')
            assert href
            status = page.request.get(origin + href if href.startswith('/') else href).status
            assert status <= 399 or status == 403, (role, href, status)
            if status == 403:
                assert 'API' in (link.locator('.nav-link-title').inner_text())
        page.context.close()


def test_logout_form_csrf_and_session(site, database_engine):  # noqa: F811
    app, origin, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    _goto(page, '/admin/cafeteria')
    form = page.locator('form.admin-logout-form')
    expect(form).to_have_attribute('method', 'post')
    assert '/auth/logout' in (form.get_attribute('action') or '')
    assert form.locator('input[name="_csrf"]').input_value()
    form.locator('button[type="submit"]').click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('aside.admin-sidebar')).to_have_count(0)
    denied = page.request.get(origin + '/admin/cafeteria')
    assert denied.status == 401
    login = page.request.get(origin + '/auth/local')
    assert login.status == 200
    page.context.close()


def test_mobile_focus_escape_and_viewports(site, database_engine, tmp_path):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 390, 'height': 844})
    _goto(page, '/admin/cafeteria')
    toggle = page.get_by_role('button', name='Menü', exact=True)
    expect(toggle).to_be_visible()
    box = toggle.bounding_box()
    assert box is not None and box['width'] >= 44 and box['height'] >= 44
    expect(toggle).to_have_attribute('aria-controls', 'sidebar-menu')
    assert toggle.get_attribute('aria-expanded') is not None
    toggle.focus()
    toggle.click()
    menu = page.locator('#sidebar-menu')
    expect(menu).to_have_class(re.compile(r'\bshow\b'))
    expect(menu).to_be_focused()
    expect(toggle).to_have_attribute('aria-expanded', re.compile(r'true|false'))
    page.keyboard.press('Escape')
    expect(menu).not_to_have_class(re.compile(r'\bshow\b'))
    expect(toggle).to_be_focused()
    for width, height in VIEWPORTS:
        page.set_viewport_size({'width': width, 'height': height})
        if width < 992:
            expect(toggle).to_be_visible()
            expect(page.get_by_role('navigation', name='Backend')).to_be_hidden()
        else:
            expect(toggle).to_be_hidden()
            expect(page.get_by_role('navigation', name='Backend')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (width, height)
        page.screenshot(path=str(tmp_path / f'shell-{width}x{height}.png'), full_page=True)
    page.context.close()


def test_layout_min_width_overlap_and_padding(site, database_engine):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    _goto(page, '/admin/cafeteria')
    assert page.locator('main.admin-main').evaluate('el => getComputedStyle(el).minWidth') == '0px'
    sidebar = page.locator('aside.admin-sidebar').bounding_box()
    main = page.locator('main.admin-main').bounding_box()
    assert sidebar is not None and main is not None
    overlap = not (main['x'] >= sidebar['x'] + sidebar['width'] - 1
                   or sidebar['x'] >= main['x'] + main['width'] - 1
                   or main['y'] >= sidebar['y'] + sidebar['height'] - 1
                   or sidebar['y'] >= main['y'] + main['height'] - 1)
    assert not overlap
    paddings = {}
    for width, expected in ((1440, '32px'), (768, '24px'), (390, '16px')):
        page.set_viewport_size({'width': width, 'height': 900})
        paddings[width] = page.locator('.page-body > .container-xl').evaluate(
            'el => getComputedStyle(el).paddingLeft',
        )
        assert paddings[width] == expected, paddings
    widths = {}
    for variant in ('standard', 'narrow', 'workspace'):
        _goto(page, f'/__shell__/{variant}')
        expect(page.locator('main.admin-main')).to_have_attribute('data-layout', variant)
        expect(page.locator('header.admin-page-header h1')).to_have_text('Shell-Variante')
        page.set_viewport_size({'width': 1920, 'height': 1080})
        widths[variant] = page.locator('.page-body > .container-xl').evaluate(
            'el => getComputedStyle(el).maxWidth',
        )
    assert widths['standard'] == '1440px'
    assert widths['narrow'] == '960px'
    assert widths['workspace'] == 'none'
    _goto(page, '/__shell__/empty')
    expect(page.locator('#shell-empty')).to_have_text('leer')
    assert page.locator('header.admin-page-header').count() == 0
    page.context.close()


def test_display_options_two_sessions(site, database_engine, monkeypatch):  # noqa: F811
    app, _, engine, _ = site
    admin, admin_id = _login(app, engine, ['Cafeteria.Admin'])
    editor, editor_id = _role_client(app, engine, 'Cafeteria.Editor')
    values = {
        admin_id: {**DEFAULT_ADMIN_DISPLAY, 'admin_density': 'comfortable', 'admin_content_width': 'full'},
        editor_id: {**DEFAULT_ADMIN_DISPLAY, 'admin_density': 'compact', 'admin_content_width': 'contained'},
    }

    def fake_get(_engine):
        uid = (session.get('user') or {}).get('id')
        return values.get(uid, DEFAULT_ADMIN_DISPLAY)

    monkeypatch.setattr(display_routes, 'get_admin_display', fake_get)
    admin_page = _page(site, admin, viewport={'width': 1440, 'height': 900})
    editor_page = _page(site, editor, viewport={'width': 1440, 'height': 900})
    _goto(admin_page, '/admin/cafeteria')
    _goto(editor_page, '/admin/cafeteria')
    expect(admin_page.locator('main.admin-main')).to_have_attribute('data-density', 'comfortable')
    expect(admin_page.locator('main.admin-main')).to_have_attribute('data-content-width', 'full')
    expect(editor_page.locator('main.admin-main')).to_have_attribute('data-density', 'compact')
    expect(editor_page.locator('main.admin-main')).to_have_attribute('data-content-width', 'contained')
    admin_page.context.close()
    editor_page.context.close()


def test_keyboard_focus_and_sidebar_contrast(site, database_engine):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 390, 'height': 844})
    _goto(page, '/admin/cafeteria')
    page.keyboard.press('Tab')
    skip = page.get_by_role('link', name='Zum Inhalt springen')
    expect(skip).to_be_focused()
    outline = skip.evaluate('el => getComputedStyle(el).outlineColor')
    assert _hex(outline) == '#a3164d'
    page.keyboard.press('Tab')
    toggle = page.get_by_role('button', name='Menü', exact=True)
    expect(toggle).to_be_focused()
    page.keyboard.press('Enter')
    menu = page.locator('#sidebar-menu')
    expect(menu).to_have_class(re.compile(r'\bshow\b'))
    expect(menu).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('.admin-nav a.nav-link').first).to_be_focused()
    page.set_viewport_size({'width': 1440, 'height': 900})
    measured = page.locator('aside.admin-sidebar').evaluate('''el => {
      const s = getComputedStyle(el);
      const label = el.querySelector('.nav-group-label');
      const active = el.querySelector('a.nav-link[aria-current="page"]');
      const title = active.querySelector('.nav-link-title');
      return {
        sidebar: s.backgroundColor,
        text: getComputedStyle(title).color,
        label: getComputedStyle(label).color,
        activeBg: getComputedStyle(active).backgroundColor,
        indicator: s.getPropertyValue('--app-sidebar-indicator').trim(),
      };
    }''')
    assert contrast(_hex(measured['text']), _hex(measured['sidebar'])) >= 4.5
    assert contrast(_hex(measured['label']), _hex(measured['sidebar'])) >= 4.5
    assert contrast(_hex(measured['indicator']), _hex(measured['activeBg'])) >= 3
    page.context.close()
