"""Chromium and contract verification for master Jinja macros and component states."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Thread

import pytest
from flask import render_template_string, request
from werkzeug.serving import make_server

from cafeteria.branding_config import contrast
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory

VIEWPORTS = [
    (1440, 900),
    (1024, 768),
    (768, 1024),
    (390, 844),
    (1920, 1080),
]


@pytest.fixture
def macro_site(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    app = _factory(monkeypatch, tmp_path, database_engine)
    client, _ = _login(app, database_engine, ['Cafeteria.Admin'])

    last_post = {}

    @app.post('/__macro_submit__')
    def macro_submit():
        last_post.clear()
        last_post.update(request.form.to_dict())
        return json.dumps(last_post), 200, {'Content-Type': 'application/json'}

    @app.get('/__macro_components__')
    def macro_components():
        return render_template_string('''{% extends 'admin/base_tabler.html' %}
        {% from 'admin/_macros.html' import page_header, field, select, textarea, checkbox, check, form_errors, status_badge, status, empty_state, pagination, actions, icon %}
        {% block page_header %}
        {{ page_header('Komponenten-Testseite', description='Prüfung aller Master-Makros und Zustände', breadcrumbs=[('Admin', '/admin'), ('Komponenten', none)]) }}
        {% endblock %}
        {% block content %}
        <div class="row g-3">
          <div class="col-12">
            <div class="card">
              <div class="card-header"><h2 class="card-title">Formularfelder & Zustände</h2></div>
              <div class="card-body">
                <form id="test-form" method="POST" action="/__macro_submit__">
                  {{ form_errors(['Bitte füllen Sie alle Pflichtfelder aus.', 'Ein Wert ist ungültig.']) }}
                  <div class="row g-3">
                    <div class="col-md-6">{{ field('f_normal', 'Normales Feld', value='Max Muster', hint='Ein normaler Hinweis') }}</div>
                    <div class="col-md-6">{{ field('f_empty', 'Leeres Pflichtfeld', value='', required=true) }}</div>
                    <div class="col-md-6">{{ field('f_invalid', 'Ungültiges Feld', value='Falsch', error='Ungültiger Wert', hint='Hilfe zum Feld') }}</div>
                    <div class="col-md-3">{{ field('f_readonly', 'Readonly Feld', value='Fixwert', readonly=true) }}</div>
                    <div class="col-md-3">{{ field('f_disabled', 'Disabled Feld', value='Ignoriert', disabled=true) }}</div>
                    <div class="col-md-6">{{ select('s_normal', 'Normales Select', choices=[('a', 'Option A'), ('b', 'Option B')], value='b', hint='Auswahl treffen') }}</div>
                    <div class="col-md-6">{{ select('s_empty', 'Leeres Select', choices=[('', '-- Bitte wählen --'), ('1', 'Eins')], value='') }}</div>
                    <div class="col-md-6">{{ select('s_invalid', 'Ungültiges Select', choices=[('x', 'X')], value='', error='Bitte auswählen', hint='Auswahl nötig') }}</div>
                    <div class="col-md-3">{{ select('s_readonly', 'Readonly Select', choices=[('ro', 'Readonly Wert')], value='ro', readonly=true) }}</div>
                    <div class="col-md-3">{{ select('s_disabled', 'Disabled Select', choices=[('dis', 'Disabled Wert')], value='dis', disabled=true) }}</div>
                    <div class="col-md-6">{{ textarea('t_normal', 'Normale Textarea', value='Langer Text', hint='Max 500 Zeichen') }}</div>
                    <div class="col-md-6">{{ textarea('t_empty', 'Leere Textarea', value='') }}</div>
                    <div class="col-md-6">{{ textarea('t_invalid', 'Ungültige Textarea', value='Ungültig', error='Zu kurz', hint='Min 10 Zeichen') }}</div>
                    <div class="col-md-3">{{ textarea('t_readonly', 'Readonly Textarea', value='Festgelegter Text', readonly=true) }}</div>
                    <div class="col-md-3">{{ textarea('t_disabled', 'Disabled Textarea', value='Nicht senden', disabled=true) }}</div>
                    <div class="col-md-3">{{ checkbox('c_normal', 'Normale Checkbox', value='active', checked=true, hint='Erlaubnis erteilt') }}</div>
                    <div class="col-md-3">{{ checkbox('c_empty', 'Leere Checkbox', value='empty', checked=false) }}</div>
                    <div class="col-md-3">{{ checkbox('c_invalid', 'Ungültige Checkbox', value='req', checked=false, error='Muss akzeptiert werden') }}</div>
                    <div class="col-md-3">{{ checkbox('c_readonly', 'Readonly Checkbox', value='ro_check', checked=true, readonly=true) }}</div>
                    <div class="col-md-3">{{ checkbox('c_disabled', 'Disabled Checkbox', value='dis_check', checked=true, disabled=true) }}</div>
                  </div>
                  <div class="mt-4">{{ actions(primary={'label': 'Formular speichern', 'type': 'submit'}, secondary=[{'label': 'Abbrechen', 'url': '#cancel'}]) }}</div>
                </form>
              </div>
            </div>
          </div>

          <div class="col-12">
            <div class="card">
              <div class="card-header"><h2 class="card-title">Status-Badges</h2></div>
              <div class="card-body">
                <div id="status-container" class="d-flex flex-wrap gap-2">
                  {% for val in ['live', 'ready', 'review_open', 'incomplete', 'changed', 'active', 'inactive', 'archived', 'conflict', 'error'] %}
                    {{ status_badge(val) }}
                  {% endfor %}
                  {{ status_badge('custom_val', mapping={'custom_val': ('Spezial-Status', 'info')}) }}
                </div>
              </div>
            </div>
          </div>

          <div class="col-12">
            <div class="card">
              <div class="card-header"><h2 class="card-title">Empty States</h2></div>
              <div class="card-body">
                <div class="row g-3">
                  <div class="col-md-4" id="empty-none">{% call empty_state('none', 'Keine Rezepte vorhanden', 'Erstellen Sie Ihr erstes Rezept.') %}<a href="#neu" class="btn btn-primary">Neues Rezept</a>{% endcall %}</div>
                  <div class="col-md-4" id="empty-no-match">{{ empty_state('no_match', 'Keine Suchtreffer', 'Versuchen Sie einen anderen Suchbegriff.') }}</div>
                  <div class="col-md-4" id="empty-forbidden">{{ empty_state('forbidden', 'Zugriff verweigert', 'Für diesen Bereich fehlen die erforderlichen Rechte.') }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="col-12">
            <div class="card">
              <div class="card-header"><h2 class="card-title">Pagination</h2></div>
              <div class="card-body">
                <div id="pag-multi">{{ pagination(2, has_next=true, prev_url='#p1', next_url='#p3', label='Mehrseitig', total_pages=5, total_items=42) }}</div>
                <div id="pag-first">{{ pagination(1, has_next=true, prev_url=none, next_url='#p2', label='Erste Seite') }}</div>
                <div id="pag-last">{{ pagination(3, has_next=false, prev_url='#p2', next_url=none, label='Letzte Seite', has_prev=true) }}</div>
                <div id="pag-single">{{ pagination(1, has_next=false, prev_url=none, next_url=none, label='Einseitig') }}</div>
              </div>
            </div>
          </div>

          <div class="col-12">
            <div class="card">
              <div class="card-header"><h2 class="card-title">Aktionen</h2></div>
              <div class="card-body">
                <div id="action-bar">
                  {{ actions(primary={'label': 'Hauptaktion ausführen', 'id': 'pri-btn', 'type': 'button'}, secondary=[{'label': 'Zurücksetzen', 'id': 'sec-btn'}, {'label': 'Zur Liste', 'url': '#list', 'id': 'sec-link'}]) }}
                </div>
              </div>
            </div>
          </div>
        </div>
        {% endblock %}''', family='cafeteria', profile='staff_guest', brand=app.jinja_env.undefined())

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with browser.new_context(base_url=origin, viewport={'width': 1440, 'height': 900},
                                 locale='de-CH', timezone_id='Europe/Zurich',
                                 reduced_motion='reduce') as context:
            cookie_name = app.config['SESSION_COOKIE_NAME']
            context.add_cookies([{'name': cookie_name, 'value': client.get_cookie(cookie_name).value,
                                 'url': origin}])
            yield context.new_page(), app, client, last_post
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _hex(value: str) -> str:
    if value.startswith('color(srgb '):
        channels = value.removeprefix('color(srgb ').removesuffix(')').split(' / ')
        return '#' + ''.join(f'{round(float(n) * 255):02x}' for n in channels[0].split())
    if value.startswith('rgba('):
        parts = value[5:-1].split(',')
        return '#' + ''.join(f'{int(n.strip()):02x}' for n in parts[:3])
    if value.startswith('rgb('):
        return '#' + ''.join(f'{int(n.strip()):02x}' for n in value[4:-1].split(','))
    return value


def test_master_page_header_semantics(macro_site):
    page, app, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    # Exactly one H1
    h1s = page.locator('h1.page-title')
    assert h1s.count() == 1
    assert h1s.first.inner_text().strip() == 'Komponenten-Testseite'

    # Description and breadcrumbs present
    subtitle = page.locator('.page-header-subtitle')
    assert subtitle.count() == 1
    assert 'Prüfung aller Master-Makros' in subtitle.first.inner_text()

    crumbs = page.locator('.page-breadcrumb .breadcrumb-item')
    assert crumbs.count() == 2
    assert crumbs.nth(0).locator('a').get_attribute('href') == '/admin'
    assert crumbs.nth(1).get_attribute('aria-current') == 'page'

    # Render without optional fields does not leave empty elements
    with app.app_context():
        empty_header = render_template_string(
            "{% from 'admin/_macros.html' import page_header %}{{ page_header('Kompakt') }}"
        )
        assert 'class="page-header-subtitle"' not in empty_header
        assert 'class="page-breadcrumb"' not in empty_header
        assert 'class="btn-list"' not in empty_header


def test_master_form_controls_and_error_states(macro_site):
    page, _, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    # 1. Normal state: labels bound to controls
    for prefix in ['f', 's', 't']:
        control = page.locator(f'#{prefix}_normal')
        assert control.count() == 1
        label = page.locator(f'label[for="{prefix}_normal"]')
        assert label.is_visible()

    # 2. Empty state: required attribute intact
    assert page.locator('#f_empty').get_attribute('required') is not None
    assert 'required' in page.locator('label[for="f_empty"]').get_attribute('class')

    # 3. Invalid state: aria-invalid and aria-describedby binding
    for prefix in ['f', 's', 't', 'c']:
        control = page.locator(f'#{prefix}_invalid')
        assert control.get_attribute('aria-invalid') == 'true'
        describedby = control.get_attribute('aria-describedby') or ''
        assert f'{prefix}_invalid-error' in describedby
        err_div = page.locator(f'#{prefix}_invalid-error')
        assert err_div.is_visible()

    # 4. Form error region renders list
    assert page.locator('.error-region').is_visible()
    assert page.locator('.error-region li').count() == 2


def test_master_form_readonly_vs_disabled_post(macro_site):
    page, _, client, last_post = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    # Fill required field so form submission is allowed by browser validation
    page.locator('#f_empty').fill('Ausgefüllter Wert')

    # Submit via browser interaction
    submit_btn = page.locator('#test-form button[type="submit"]').first
    submit_btn.click()
    page.wait_for_load_state('networkidle')

    # Readonly fields submitted; disabled fields omitted
    assert last_post.get('f_empty') == 'Ausgefüllter Wert'
    assert last_post.get('f_readonly') == 'Fixwert'
    assert last_post.get('s_readonly') == 'ro'
    assert last_post.get('t_readonly') == 'Festgelegter Text'
    assert last_post.get('c_readonly') == 'ro_check'

    assert 'f_disabled' not in last_post
    assert 's_disabled' not in last_post
    assert 't_disabled' not in last_post
    assert 'c_disabled' not in last_post

    # NoJS HTTP POST test: raw form submit produces identical result
    nojs_res = client.post('/__macro_submit__', data={
        'f_empty': 'Ausgefüllter Wert',
        'f_readonly': 'Fixwert',
        's_readonly': 'ro',
        't_readonly': 'Festgelegter Text',
        'c_readonly': 'ro_check',
    })
    assert nojs_res.status_code == 200
    assert nojs_res.json == last_post


def test_master_status_badges_contrast_and_shape(macro_site):
    page, _, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    badges = page.locator('#status-container .badge')
    count = badges.count()
    assert count >= 10

    for i in range(count):
        badge = badges.nth(i)
        # Text always visible (color never alone)
        text = badge.inner_text().strip()
        assert len(text) > 0

        # Pill shape: border-radius >= 16px (999px)
        styles = badge.evaluate('''(el) => {
            const s = getComputedStyle(el);
            return {
                color: s.color,
                bg: s.backgroundColor,
                radius: parseFloat(s.borderRadius)
            };
        }''')
        assert styles['radius'] >= 10

        # AA Contrast: >= 4.5:1
        c_hex = _hex(styles['color'])
        bg_hex = _hex(styles['bg'])
        ratio = contrast(c_hex, bg_hex)
        assert ratio >= 4.5, f"Badge {text} contrast {ratio} < 4.5 between {c_hex} and {bg_hex}"


def test_master_empty_states_three_kinds(macro_site):
    page, _, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    # none: title, text, action button present
    none_state = page.locator('#empty-none .empty')
    assert none_state.locator('.empty-title').inner_text() == 'Keine Rezepte vorhanden'
    assert none_state.locator('.empty-action a').is_visible()

    # no_match: title and text, no action
    match_state = page.locator('#empty-no-match .empty')
    assert match_state.locator('.empty-title').inner_text() == 'Keine Suchtreffer'
    assert match_state.locator('.empty-action').count() == 0

    # forbidden: title and text, no action
    forb_state = page.locator('#empty-forbidden .empty')
    assert forb_state.locator('.empty-title').inner_text() == 'Zugriff verweigert'
    assert forb_state.locator('.empty-action').count() == 0


def test_master_pagination_behaviours(macro_site):
    page, _, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    # Multi-page with prev and next
    multi = page.locator('#pag-multi .pagination')
    assert multi.locator('.page-item.active').inner_text().strip() == 'Seite 2 von 5'
    assert multi.locator('.page-item:not(.disabled) a').count() == 2
    assert 'Gesamt: 42' in page.locator('#pag-multi').inner_text()

    # First page: Zurück has aria-disabled
    first = page.locator('#pag-first .pagination')
    assert first.locator('.page-item').first.locator('.page-link').get_attribute('aria-disabled') == 'true'

    # Last page: Weiter has aria-disabled
    last = page.locator('#pag-last .pagination')
    assert last.locator('.page-item').last.locator('.page-link').get_attribute('aria-disabled') == 'true'

    # Single-page: renders nothing
    assert page.locator('#pag-single .pagination').count() == 0


def test_master_actions_and_focus_ring(macro_site):
    page, _, _, _ = macro_site
    page.goto('/__macro_components__', wait_until='networkidle')

    # Primary and secondary buttons
    pri_btn = page.locator('#pri-btn')
    sec_btn = page.locator('#sec-btn')
    sec_link = page.locator('#sec-link')

    for btn in [pri_btn, sec_btn, sec_link]:
        box = btn.bounding_box()
        assert box is not None
        assert box['height'] >= 44, f"Target height {box['height']} < 44px"

    # Focus ring matches --app-focus (rgb(163, 22, 77))
    pri_btn.focus()
    outline = pri_btn.evaluate('el => getComputedStyle(el).outlineColor')
    assert outline == 'rgb(163, 22, 77)'


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_master_responsive_viewports_and_screenshots(macro_site, width, height, tmp_path: Path):
    page, _, _, _ = macro_site
    page.set_viewport_size({'width': width, 'height': height})
    page.goto('/__macro_components__', wait_until='networkidle')

    # No document-level horizontal scrollbar
    has_overflow = page.evaluate('() => document.documentElement.scrollWidth > window.innerWidth')
    assert not has_overflow, f"Horizontal overflow detected at {width}x{height}"

    # Screenshot to tmp_path
    screenshot_file = tmp_path / f'master-components-{width}x{height}.png'
    page.screenshot(path=str(screenshot_file), full_page=True)
    assert screenshot_file.is_file()
    assert screenshot_file.stat().st_size > 1000
