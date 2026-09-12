"""MP-UI-SHELL-V2: four areas, native tabs, permissions and responsive geometry."""
from __future__ import annotations

import json
import re
from threading import Thread
from urllib.parse import urlsplit

import pytest
from flask import abort, render_template_string, session
from playwright.sync_api import Page, expect
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria import db as cafeteria_db
from cafeteria.admin import display_routes
from cafeteria.branding_config import contrast
from cafeteria.display_settings import DEFAULT_ADMIN_DISPLAY
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
AREAS = ('Wochenplan', 'Menüs & Bausteine', 'Vorschau & Bildschirme', 'Einstellungen')
# Complete old-to-new entry inventory: old label, new tab, endpoint, URL, admin-only.
ENTRIES = {
    'Wochenplan': (
        ('Wochenpläne', 'Cafeteria', 'cafeteria', '/admin/cafeteria', False),
        ('Patienten', 'Patienten', 'patienten', '/admin/patienten', False),
        ('Wochenverwaltung', 'Wochenübersicht', 'week_management', '/admin/cafeteria/wochen', False),
    ),
    'Menüs & Bausteine': (
        ('Menüs', 'Menüs', 'menu_collection', '/admin/cafeteria/menues', False),
        ('Komponenten', 'Bausteine', 'components_get', '/admin/cafeteria/komponenten', False),
        ('Grundlagen', 'Zutaten', 'master_data_list', '/admin/grundlagen', False),
        ('Rezepte', 'Rezepte', 'recipes_list', '/admin/rezepte', False),
        ('Kochbücher', 'Kochbücher', 'cookbooks_list', '/admin/kochbuecher', False),
    ),
    'Vorschau & Bildschirme': (
        ('Vorschau', 'Vorschau', 'preview', '/admin/cafeteria/preview', False),
        ('Screens', 'Bildschirme', 'screens', '/admin/screens', False),
        ('Vorlagen', 'Druckvorlagen', 'vorlagen', '/admin/vorlagen', False),
    ),
    'Einstellungen': (
        ('Bereiche & Zeiten', 'Bereiche & Öffnungszeiten', 'operations_settings', '/admin/bereiche-zeiten', True),
        ('Design & Marke', 'Erscheinungsbild', 'branding_editor', '/admin/design/marke', True),
        ('Darstellung', 'Darstellung', 'display_settings', '/admin/design/darstellung', True),
        ('CSV Import', 'Daten importieren', 'import_preview', '/admin/import-preview', False),
        ('API & Schnittstellen', 'Schnittstellen', 'api_overview', '/admin/api', False),
        ('Benutzer & Zugriff', 'Benutzer & Zugriff', 'local_users_list', '/admin/benutzer', True),
    ),
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
    _save(database_engine, 'staff_guest', _staff_values())
    _save(database_engine, 'patient', _patient_values())

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
            {% set workflow_nav = 'weeks' %}
            {% set layout_variant = variant %}
            {% block page_header %}
            <div class="container-xl"><div class="page-header-row">
              <div class="page-header-copy"><h1>Shell-Variante</h1>
              <p class="page-header-subtitle">Prüft Containerbreite und Seitenkopf.</p></div>
              <div class="page-header-actions btn-list"><a class="btn" href="#aktion">Aktion</a></div>
            </div></div>
            {% endblock %}
            {% block content %}<p id="shell-body">{{ variant }}</p>
            <a href="#shell-body" id="shell-action">Inhalt öffnen</a>{% endblock %}""",
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


def test_navigation_roles_targets_and_current(site, database_engine, tmp_path):  # noqa: F811
    app, origin, engine, _ = site
    admin, _ = _login(app, engine, ['Cafeteria.Admin'])
    clients = {'Cafeteria.Admin': admin}
    for role in ROLE_CLAIMS:
        clients[role], _ = _role_client(app, engine, role)
    for role, client in clients.items():
        page = _page(site, client, viewport={'width': 1440, 'height': 900})
        _goto(page, '/admin/cafeteria')
        assert _titles(page) == list(AREAS)
        expect(page.locator('.nav-group, .nav-link-desc')).to_have_count(0)
        current = page.locator('.admin-nav a[aria-current="page"] .nav-link-title')
        expect(current).to_have_text('Wochenplan')
        expect(page.locator('.admin-user-role')).to_have_text(
            {'Cafeteria.Admin': 'Administration', 'Cafeteria.Publisher': 'Freigabe & Redaktion',
             'Cafeteria.Editor': 'Küchenplanung'}[role],
        )
        evidence = []
        for area, entries in ENTRIES.items():
            _goto(page, '/admin/cafeteria')
            page.locator('.admin-nav').get_by_role('link', name=area, exact=True).click()
            page.wait_for_load_state('networkidle')
            expect(current).to_have_text(area)
            tabs = page.locator('.admin-area-tabs')
            allowed = [entry for entry in entries if role == 'Cafeteria.Admin' or not entry[4]]
            assert tabs.get_by_role('link').all_text_contents() == [entry[1] for entry in allowed]
            for old, label, endpoint, path, _ in allowed:
                assert 'admin.' + endpoint in app.view_functions
                link = tabs.get_by_role('link', name=label, exact=True)
                href = link.get_attribute('href')
                assert href and urlsplit(href).path == path
                status = page.request.get(origin + href).status
                # Existing API link is visible to all roles, but server remains admin-only.
                assert status == (403 if endpoint == 'api_overview' and role != 'Cafeteria.Admin' else 200)
                evidence.append({'old': old, 'area': area, 'tab': label, 'href': href, 'status': status})
            page.screenshot(path=str(tmp_path / f'{role}-{area.split()[0]}.png'), full_page=True)
        (tmp_path / f'{role}-navigation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        page.context.close()


def test_output_area_entry_keeps_all_output_tabs_reachable(site):
    app, origin, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    try:
        _goto(page, '/admin/cafeteria')
        entry = page.locator('.admin-nav').get_by_role('link', name=AREAS[2], exact=True)
        # Preview is a standalone output page without the admin shell.
        assert urlsplit(entry.get_attribute('href')).path == '/admin/screens'
        entry.click()
        page.wait_for_load_state('networkidle')
        tabs = page.locator('.admin-area-tabs')
        expect(tabs).to_be_visible()
        expect(page.locator('.admin-nav [aria-current="page"] .nav-link-title')).to_have_text(AREAS[2])
        assert tabs.get_by_role('link').all_text_contents() == ['Vorschau', 'Bildschirme', 'Druckvorlagen']
        expect(tabs.get_by_role('link', name='Bildschirme', exact=True)).to_have_attribute(
            'aria-current', 'page',
        )
        preview = tabs.get_by_role('link', name='Vorschau', exact=True)
        href = preview.get_attribute('href')
        assert href and urlsplit(href).path == '/admin/cafeteria/preview'
        assert page.request.get(origin + href).status == 200
    finally:
        page.context.close()


@pytest.mark.parametrize('width', (390, 1440))
def test_current_area_and_tab_on_each_entry(site, width):
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': width, 'height': 900})
    try:
        for area, entries in ENTRIES.items():
            for _, label, endpoint, path, _ in entries:
                if endpoint == 'preview':
                    continue  # Standalone output: covered by the explicit failing entry test.
                _goto(page, path)
                expect(page.locator('.admin-nav [aria-current="page"] .nav-link-title')).to_have_text(area)
                expect(page.locator('.admin-area-tabs [aria-current="page"]')).to_have_text(label)
        for route, tab in (('wochen', 'Wochenübersicht'), ('menues', 'Menüs'), ('komponenten', 'Bausteine')):
            _goto(page, f'/admin/patienten/{route}')
            expect(page.locator('.admin-area-tabs [aria-current="page"]')).to_have_text(tab)
            expect(page.locator('.admin-nav').get_by_role('link', name='Wochenplan', exact=True, include_hidden=True)).to_have_attribute('href', '/admin/patienten')
            for link in page.locator('.admin-area-tabs a').all():
                assert '/admin/cafeteria/' not in link.get_attribute('href')
    finally:
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
    expect(toggle).to_have_attribute('aria-expanded', 'true')
    page.keyboard.press('Tab')
    expect(menu.locator('.admin-nav a').first).to_be_focused()
    page.keyboard.press('Shift+Tab')
    expect(menu.locator('.admin-logout-btn')).to_be_focused()
    page.keyboard.press('Tab')
    expect(menu.locator('.admin-nav a').first).to_be_focused()
    page.keyboard.press('Escape')
    expect(menu).not_to_have_class(re.compile(r'\bshow\b'))
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    for width, height in VIEWPORTS:
        page.set_viewport_size({'width': width, 'height': height})
        if width < 992:
            expect(toggle).to_be_visible()
            expect(page.get_by_role('navigation', name='Backend')).to_be_hidden()
        else:
            expect(toggle).to_be_hidden()
            expect(page.get_by_role('navigation', name='Backend')).to_be_visible()
            assert page.locator('.admin-sidebar').bounding_box()['width'] == 248
        for route in ('/admin/cafeteria', '/admin/cafeteria/menues', '/admin/screens', '/admin/design/marke'):
            _goto(page, route)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (route, width, height)
            for link in page.locator('.admin-area-tabs a').all():
                assert link.bounding_box()['height'] >= 44
            if width >= 992:
                for link in page.locator('.admin-nav a').all():
                    assert link.bounding_box()['height'] >= 56
                    assert float(link.evaluate('el => getComputedStyle(el).fontSize').removesuffix('px')) >= 15
                    assert link.locator('.nav-link-title').evaluate('el => el.scrollWidth <= el.clientWidth + 1')
            page.screenshot(path=str(tmp_path / f'shell-{route.split("/")[-1]}-{width}x{height}.png'), full_page=True)
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
        for viewport_width in (1440, 1920, 2560):
            page.set_viewport_size({'width': viewport_width, 'height': 1080})
            metrics = page.evaluate('''() => {
              const main = document.querySelector('main.admin-main');
              const box = document.querySelector('.page-body > .container-xl');
              const cs = getComputedStyle(box);
              const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
              return {
                maxWidth: cs.maxWidth,
                contentWidth: box.getBoundingClientRect().width - pad,
                expected: main.clientWidth - pad,
              };
            }''')
            assert metrics['maxWidth'] == 'none', (variant, viewport_width, metrics)
            assert abs(metrics['contentWidth'] - metrics['expected']) <= 1, (variant, viewport_width, metrics)
            widths.setdefault(variant, {})[viewport_width] = metrics
        containers = page.locator('.admin-page-header > .container-xl, .admin-area-tabs > .container-xl, .page-body > .container-xl').all()
        boxes = [container.bounding_box() for container in containers]
        assert len(boxes) == 3
        assert max(box['x'] for box in boxes) - min(box['x'] for box in boxes) <= 1
        assert max(box['width'] for box in boxes) - min(box['width'] for box in boxes) <= 1
    assert {variant: widths[variant][1920]['maxWidth'] for variant in widths} == {
        'standard': 'none', 'narrow': 'none', 'workspace': 'none',
    }
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


def test_keyboard_focus_and_sidebar_contrast(site, database_engine, tmp_path):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 390, 'height': 844})
    _goto(page, '/__shell__/standard')
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
    page.keyboard.press('Escape')
    expect(toggle).to_be_focused()
    page.keyboard.press('Tab')
    # Header action precedes tabs; both remain before the content.
    expect(page.get_by_role('link', name='Aktion', exact=True)).to_be_focused()
    for link in page.locator('.admin-area-tabs a').all():
        page.keyboard.press('Tab')
        expect(link).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('#shell-action')).to_be_focused()
    page.set_viewport_size({'width': 1440, 'height': 900})
    _goto(page, '/admin/cafeteria')
    measured = page.locator('aside.admin-sidebar').evaluate('''el => {
      const s = getComputedStyle(el);
      const label = el.querySelector('.admin-user-role');
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
    tabs = page.locator('.admin-area-tabs a')
    for link in tabs.all():
        styles = link.evaluate('''el => {
          const s = getComputedStyle(el);
          return {text:s.color, bg:s.backgroundColor, border:s.borderBottomColor,
                  page:getComputedStyle(document.body).backgroundColor};
        }''')
        background = styles['page'] if styles['bg'] == 'rgba(0, 0, 0, 0)' else styles['bg']
        assert contrast(_hex(styles['text']), _hex(background)) >= 4.5
        if link.get_attribute('aria-current'):
            assert contrast(_hex(styles['border']), _hex(background)) >= 3
            assert contrast(_hex(styles['border']), _hex(styles['page'])) >= 3
    (tmp_path / 'sidebar-contrast.json').write_text(json.dumps(measured, indent=2))
    page.context.close()


def test_native_tabs_without_javascript_and_zoom_reflow(site, tmp_path):
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 390, 'height': 844}, java_script_enabled=False)
    try:
        _goto(page, '/admin/cafeteria')
        nav = page.locator('.admin-nav:visible')
        expect(nav.get_by_role('link')).to_have_count(4)
        nav.get_by_role('link', name=AREAS[1], exact=True).click()
        page.locator('.admin-area-tabs').get_by_role('link', name='Rezepte', exact=True).click()
        expect(page.locator('.admin-area-tabs [aria-current="page"]')).to_have_text('Rezepte')
        for width in (320, 720):  # 1440px at 200% browser zoom gives 720 CSS pixels.
            page.set_viewport_size({'width': width, 'height': 450})
            _goto(page, '/admin/design/marke')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for link in page.locator('.admin-area-tabs a').all():
                box = link.bounding_box()
                assert box['height'] >= 44 and 0 <= box['x'] < box['x'] + box['width'] <= width
            page.screenshot(path=str(tmp_path / f'no-js-reflow-{width}.png'), full_page=True)
    finally:
        page.context.close()
