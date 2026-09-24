"""Real HTTP/CSP and Chromium evidence for the scoped MP-UI-TOKENS contract."""
from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest
from flask import render_template_string
from playwright.sync_api import expect
from werkzeug.serving import make_server

from cafeteria.branding import change_branding
from cafeteria.branding_config import contrast, default_config
from cafeteria.branding_tokens import _admin_primary_css, brand_tokens
from cafeteria.display_settings import DEFAULT_ADMIN_DISPLAY, get_admin_display
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory

DISPLAY = '/admin/design/darstellung'
PROTECTED = {
    '/cafeteria/heute/': ['body', 'h1', '.card', '.card-title', '.btn-primary'],
    '/druck/cafeteria/woche': ['body', 'h1', '.print-header', '.week-day'],
    '/signage/cafeteria/tag': ['body', '.signage-shell', '.card', '.card-title'],
    '/auth/local': ['body', 'h1', '.auth-card', '.auth-submit'],
}
PALETTES = {
    'default': {},
    'dark': dict(primary='#d98fb0', accent='#9ec6cb', surface='#111111',
                 text='#ffffff', font_body='carlito', font_heading='carlito'),
    'custom': dict(primary='#145c43', accent='#20404d', surface='#fffdf5',
                   text='#20242a', font_body='carlito', font_heading='carlito'),
}


# Measured before product edits at 05b6c81, Chromium 151, 1440x900, via this test.
# Sources: public.css:2,35,47; app.css:335,354; signage.css:6,120; tokens.css:3.
PROTECTED_EXPECTED = {
    'default': {
        '/cafeteria/heute/': {
            'body': {"color":"rgb(56, 48, 39)","background-color":"rgb(255, 255, 255)","font-family":"\"Fira Sans\", sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", sans-serif","font-size":"43.2px","border-radius":"0px"},
            '.card': {"color":"rgb(56, 48, 39)","background-color":"rgb(255, 255, 255)","font-family":"\"Fira Sans\", sans-serif","font-size":"16px","border-radius":"16px"},
            '.card-title': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", sans-serif","font-size":"22px","border-radius":"0px"},
            '.btn-primary': {"color":"rgb(255, 255, 255)","background-color":"rgb(140, 28, 75)","font-family":"\"Fira Sans\", sans-serif","font-size":"16px","border-radius":"6px"},
        },
        '/druck/cafeteria/woche': {
            'body': {"color":"rgb(56, 48, 39)","background-color":"rgb(248, 248, 247)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", sans-serif","font-size":"72px","border-radius":"0px"},
            '.print-header': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            '.week-day': {"color":"rgb(56, 48, 39)","background-color":"rgb(255, 255, 255)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"20px"},
        },
        '/signage/cafeteria/tag': {
            'body': {"color":"rgb(56, 48, 39)","background-color":"rgb(255, 255, 255)","font-family":"\"Fira Sans\", sans-serif","font-size":"14px","border-radius":"0px"},
            '.signage-shell': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", sans-serif","font-size":"14px","border-radius":"0px"},
            '.card': {"color":"rgb(56, 48, 39)","background-color":"rgb(255, 255, 255)","font-family":"\"Fira Sans\", sans-serif","font-size":"14px","border-radius":"16px"},
            '.card-title': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", sans-serif","font-size":"46px","border-radius":"0px"},
        },
        '/auth/local': {
            'body': {"color":"rgb(56, 48, 39)","background-color":"rgb(248, 248, 247)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(56, 48, 39)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", sans-serif","font-size":"40px","border-radius":"0px"},
            '.auth-card': {"color":"rgb(56, 48, 39)","background-color":"rgb(255, 255, 255)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"16px"},
            '.auth-submit': {"color":"rgb(255, 255, 255)","background-color":"rgb(140, 28, 75)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"6px"},
        },
    },
    'dark': {
        '/cafeteria/heute/': {
            'body': {"color":"rgb(255, 255, 255)","background-color":"rgb(255, 255, 255)","font-family":"Carlito, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"43.2px","border-radius":"0px"},
            '.card': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"Carlito, sans-serif","font-size":"16px","border-radius":"16px"},
            '.card-title': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"22px","border-radius":"0px"},
            '.btn-primary': {"color":"rgb(17, 17, 17)","background-color":"rgb(217, 143, 176)","font-family":"Carlito, sans-serif","font-size":"16px","border-radius":"6px"},
        },
        '/druck/cafeteria/woche': {
            'body': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"72px","border-radius":"0px"},
            '.print-header': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            '.week-day': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"20px"},
        },
        '/signage/cafeteria/tag': {
            'body': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"Carlito, sans-serif","font-size":"14px","border-radius":"0px"},
            '.signage-shell': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"14px","border-radius":"0px"},
            '.card': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"Carlito, sans-serif","font-size":"14px","border-radius":"16px"},
            '.card-title': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"46px","border-radius":"0px"},
        },
        '/auth/local': {
            'body': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(255, 255, 255)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"40px","border-radius":"0px"},
            '.auth-card': {"color":"rgb(255, 255, 255)","background-color":"rgb(17, 17, 17)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"16px"},
            '.auth-submit': {"color":"rgb(255, 255, 255)","background-color":"rgb(217, 143, 176)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"6px"},
        },
    },
    'custom': {
        '/cafeteria/heute/': {
            'body': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 255, 255)","font-family":"Carlito, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"43.2px","border-radius":"0px"},
            '.card': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"Carlito, sans-serif","font-size":"16px","border-radius":"16px"},
            '.card-title': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"22px","border-radius":"0px"},
            '.btn-primary': {"color":"rgb(255, 253, 245)","background-color":"rgb(20, 92, 67)","font-family":"Carlito, sans-serif","font-size":"16px","border-radius":"6px"},
        },
        '/druck/cafeteria/woche': {
            'body': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"72px","border-radius":"0px"},
            '.print-header': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            '.week-day': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"20px"},
        },
        '/signage/cafeteria/tag': {
            'body': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"Carlito, sans-serif","font-size":"14px","border-radius":"0px"},
            '.signage-shell': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"14px","border-radius":"0px"},
            '.card': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"Carlito, sans-serif","font-size":"14px","border-radius":"16px"},
            '.card-title': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"46px","border-radius":"0px"},
        },
        '/auth/local': {
            'body': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"0px"},
            'h1': {"color":"rgb(32, 36, 42)","background-color":"rgba(0, 0, 0, 0)","font-family":"Carlito, sans-serif","font-size":"40px","border-radius":"0px"},
            '.auth-card': {"color":"rgb(32, 36, 42)","background-color":"rgb(255, 253, 245)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"16px"},
            '.auth-submit': {"color":"rgb(255, 255, 255)","background-color":"rgb(20, 92, 67)","font-family":"\"Fira Sans\", Aptos, \"Segoe UI Variable\", \"Segoe UI\", ui-sans-serif, sans-serif","font-size":"16px","border-radius":"6px"},
        },
    },
}

@pytest.fixture
def site(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    app = _factory(monkeypatch, tmp_path, database_engine)
    client, actor = _login(app, database_engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        authz = session['authz_version']
    # Internal test fixture: production base/macros and actual Tabler components,
    # never a product route or a separately styled component approximation.
    @app.get('/__tokens__')
    def components():
        return render_template_string('''{% extends 'admin/base_tabler.html' %}
        {% from 'admin/_macros.html' import field, check, status, pagination, page_header %}
        {% block page_header %}{{ page_header('Komponentenzustände') }}{% endblock %}
        {% block content %}<div class="card"><div class="card-header">
        <ul class="nav nav-tabs card-header-tabs"><li><a class="nav-link" href="#normal">Normal</a></li>
        <li><a class="nav-link active" href="#active">Aktiv</a></li>
        <li><button class="nav-link" disabled>Inaktiv</button></li></ul></div>
        <div class="card-body"><h2 class="card-title">Zustände</h2>
        {% for kind in ['primary', 'outline-primary', 'danger'] %}
        <button type="button" class="btn btn-{{ kind }}" id="{{ kind }}">Aktion</button>
        {% endfor %}<button class="btn btn-primary" disabled>Deaktiviert</button>
        {{ field('normal', 'Bezeichnung', hint='Hinweis') }}
        {{ field('invalid', 'Ungültig', error='Bitte prüfen') }}
        {{ field('upload', 'Datei', type='file') }}{{ check('check', 'Auswahl', id='check') }}
        <select class="form-select" aria-label="Auswahl"><option>Option</option></select>
        {% for state in ['live', 'ready', 'review_open', 'incomplete', 'unknown'] %}
        {{ status(state, state) }}{% endfor %}
        {% for state in ['success', 'warning', 'danger', 'info', 'secondary'] %}
        <span class="badge bg-{{ state }}-lt">{{ state }}</span>
        <div class="alert alert-{{ state }}">{{ state }}</div>{% endfor %}
        <div class="alert">Neutraler Hinweis</div>
        {{ pagination(1, true, '#prev', '#next', 'Seiten') }}
        <div class="list-group"><a class="list-group-item active" href="#item">Auswahl</a></div>
        </div></div>{% endblock %}''', family='cafeteria', profile='staff_guest',
                                      brand=app.jinja_env.undefined())
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
            yield context.new_page(), app, actor, authz
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _activate(site, variant):
    _, app, actor, authz = site
    config = default_config() | PALETTES[variant]
    doc = change_branding(app.extensions['cafeteria_db'], actor, authz, 0, 'save',
                          name='Token test', config=config)
    change_branding(app.extensions['cafeteria_db'], actor, authz, doc['version'], 'activate',
                    revision_id=doc['revisions'][-1]['id'])


def _goto(page, path):
    response = page.goto(path, wait_until='networkidle')
    assert response.status == 200
    page.evaluate('document.fonts.ready')


def _styles(locator):
    return locator.evaluate('''el => {
      const s = getComputedStyle(el);
      return Object.fromEntries(['color', 'background-color', 'font-family', 'font-size',
        'font-weight', 'line-height', 'border-top-color', 'border-top-width', 'border-radius',
        'padding-top', 'padding-left', 'min-height', 'box-shadow', 'outline-color',
        'outline-width', 'outline-offset', 'opacity'].map(k => [k, s.getPropertyValue(k)]));
    }''')


@pytest.mark.parametrize('variant', PALETTES)
def test_protected_channels(site, variant, tmp_path: Path):
    _activate(site, variant)
    page = site[0]
    measured = {}
    for path, selectors in PROTECTED.items():
        _goto(page, path)
        measured[path] = {s: _styles(page.locator(s).first) for s in selectors
                          if page.locator(s).count()}
        for selector, expected in PROTECTED_EXPECTED[variant][path].items():
            assert {key: measured[path][selector][key] for key in expected} == expected
    _goto(page, DISPLAY)
    measured['admin'] = {s: _styles(page.locator(s).first)
                               for s in ['body', 'h1', '.card-title', '.btn-primary', '.admin-sidebar']}
    (tmp_path / f'protected-{variant}.json').write_text(json.dumps(measured, indent=2))


def _hex(value):
    if value.startswith('color(srgb '):
        channels = value.removeprefix('color(srgb ').removesuffix(')').split(' / ')
        assert len(channels) == 1 or float(channels[1]) == 1, value
        return '#' + ''.join(f'{round(float(n) * 255):02x}' for n in channels[0].split())
    return '#' + ''.join(f'{int(n.strip()):02x}' for n in value[4:-1].split(','))


def _assert_color(locator, color, background=None):
    values = _styles(locator)
    assert _hex(values['color']) == color, values
    if background:
        assert _hex(values['background-color']) == background, values
        assert contrast(color, background) >= 4.5, values


def _focus(locator):
    locator.page.keyboard.press('Tab')
    locator.focus()
    values = _styles(locator)
    assert values['outline-color'] == 'rgb(163, 22, 77)', values
    assert values['outline-width'] == '2px' and values['outline-offset'] == '2px', values
    assert values['box-shadow'] == 'none', values


def test_master_components_and_states(site, tmp_path: Path):
    page = site[0]
    _goto(page, '/__tokens__')
    master = (Path(__file__).resolve().parents[2] / 'docs/design/2026-09-09-unified-ui-design-system.md').read_text()
    palette = dict(re.findall(r'(--app-[\w-]+):\s*(#[0-9A-F]{6});', master))
    assert len(palette) == 34  # plus primary-rgb = all 35 master colour tokens
    effective = page.locator('body').evaluate('(el, names) => Object.fromEntries(names.map(k => [k, getComputedStyle(el).getPropertyValue(k).trim()]))', list(palette))
    assert effective == palette
    _assert_color(page.locator('body'), '#1f2937', '#f6f4f1')
    assert _styles(page.locator('.admin-sidebar'))['background-color'] == 'rgb(23, 60, 63)'
    assert page.locator('body').evaluate("el => getComputedStyle(el).getPropertyValue('--tblr-primary-rgb').trim()") == '163, 22, 77'
    for kind in ['primary', 'outline-primary', 'danger']:
        button = page.locator('#' + kind)
        _assert_color(button, '#a3164d' if kind == 'outline-primary' else '#ffffff',
                      '#ffffff' if kind == 'outline-primary' else '#b42318' if kind == 'danger' else '#a3164d')
        button.hover()
        _assert_color(button, '#ffffff', '#b42318' if kind == 'danger' else '#8e123f')
        page.mouse.down()
        _assert_color(button, '#ffffff', '#b42318' if kind == 'danger' else '#7c1037')
        page.mouse.up()
        _focus(button)
    disabled = page.locator('button.btn:disabled')
    _assert_color(disabled, '#ffffff', '#a3164d')
    assert _styles(disabled)['opacity'] == '1'
    for selector in ['#normal', 'select.form-select', '#check']:
        field = page.locator(selector)
        assert _styles(field)['border-top-color'] == 'rgb(128, 139, 153)'
        field.hover()
        assert _styles(field)['border-top-color'] == 'rgb(128, 139, 153)'
        _focus(field)
        field.evaluate("el => el.disabled = true")
        _assert_color(field, '#596273', '#faf9f7')
        field.evaluate("el => el.disabled = false")
    page.locator('#check').check()
    assert _styles(page.locator('#check'))['background-color'] == 'rgb(163, 22, 77)'
    assert '%23fff' in page.locator('#check').evaluate('el => getComputedStyle(el).backgroundImage')
    page.locator('#check').evaluate('el => { el.checked = false; el.indeterminate = true; }')
    assert _styles(page.locator('#check'))['background-color'] == 'rgb(163, 22, 77)'
    _focus(page.locator('#invalid'))
    assert _styles(page.locator('#invalid'))['border-top-color'] == 'rgb(180, 35, 24)'
    page.locator('#normal').evaluate("el => el.setAttribute('aria-invalid', 'true')")
    assert _styles(page.locator('#normal'))['border-top-color'] == 'rgb(180, 35, 24)'
    upload = page.locator('#upload').evaluate("el => {const s=getComputedStyle(el,'::file-selector-button'); return [s.color,s.backgroundColor]}")
    assert upload == ['rgb(31, 41, 55)', 'rgb(250, 249, 247)']
    page.mouse.move(0, 0)
    tab = page.locator('.nav-tabs a:not(.active)')
    _assert_color(tab, '#1f2937')
    tab.hover()
    _assert_color(tab, '#8e123f', '#f7e8ee')
    _focus(tab)
    _assert_color(page.locator('.nav-tabs .active'), '#a3164d', '#f7e8ee')
    assert _styles(page.locator('.nav-tabs .active'))['border-top-width'] == '1px'
    assert page.locator('.nav-tabs .active').evaluate('el => getComputedStyle(el).borderBottomWidth') == '2px'
    _assert_color(page.locator('.nav-tabs :disabled'), '#596273', '#faf9f7')
    link = page.locator('.pagination a')
    _assert_color(link, '#a3164d', '#ffffff')
    link.hover()
    _assert_color(link, '#8e123f', '#f7e8ee')
    page.mouse.down()
    _assert_color(link, '#ffffff', '#7c1037')
    page.mouse.up()
    _focus(link)
    _assert_color(page.locator('.pagination .active .page-link'), '#ffffff', '#a3164d')
    _assert_color(page.locator('.pagination .disabled .page-link'), '#596273', '#faf9f7')
    _assert_color(page.locator('.list-group-item.active'), '#ffffff', '#a3164d')
    assert page.locator('.list-group-item.active').evaluate('el => getComputedStyle(el).borderInlineStartColor') == 'rgb(163, 22, 77)'
    _assert_color(page.locator('.alert').last, '#475467', '#eef0f2')
    # Invalid is applicable to fields only; disabled controls cannot receive focus.
    # Selected tabs/pagination use .active; fields have checked/indeterminate instead.
    for badge in page.locator('.badge').all():
        s = _styles(badge)
        assert contrast(_hex(s['color']), _hex(s['background-color'])) >= 4.5, s
        # P2b uses the shared 14px label token for semantic and legacy badges.
        assert s['border-radius'] == '999px' and s['font-size'] == '14px', s
    for alert in page.locator('.alert').all():
        assert _styles(alert)['border-top-color'] == 'rgb(229, 231, 235)'
    page.screenshot(path=str(tmp_path / 'component-states.png'), full_page=True)


@pytest.mark.parametrize('variant,primary,hover,active,rgb', [
    ('default', '#8c1c4b', '#7b1942', '#6a1539', '140, 28, 75'),
    ('dark', '#a3164d', '#8e123f', '#7c1037', '163, 22, 77'),
    ('custom', '#145c43', '#12513b', '#0f4633', '20, 92, 67'),
])
def test_brand_gate_real_admin(site, variant, primary, hover, active, rgb, tmp_path):
    _activate(site, variant)
    page = site[0]
    _goto(page, DISPLAY)
    button = page.locator('button.btn-primary')
    _assert_color(button, '#ffffff', primary)
    button.hover()
    _assert_color(button, '#ffffff', hover)
    page.mouse.down()
    _assert_color(button, '#ffffff', active)
    # Avoid submitting the real form when releasing the pressed pointer.
    page.mouse.move(0, 0)
    page.mouse.up()
    _focus(page.locator('#admin-density'))
    assert page.locator('body').evaluate("el => getComputedStyle(el).getPropertyValue('--tblr-primary-rgb').trim()") == rgb
    for selector in ['body', 'h1', '.card-title']:
        assert _styles(page.locator(selector).first)['font-family'].startswith('"Fira Sans"')
    cdp = page.context.new_cdp_session(page)
    cdp.send('DOM.enable')
    cdp.send('CSS.enable')
    root = cdp.send('DOM.getDocument')['root']['nodeId']
    fonts = {}
    for selector in ['body', 'h1', '.card-title']:
        node = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': selector})['nodeId']
        fonts[selector] = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
        assert any('Fira' in f['familyName'] and f['glyphCount'] > 0 for f in fonts[selector]), fonts
    cdp.detach()
    (tmp_path / 'rendered-fonts.json').write_text(json.dumps(fonts, indent=2))
    _assert_color(page.locator('body'), '#1f2937', '#f6f4f1')
    readonly = page.locator('#display-example')
    _assert_color(readonly, '#1f2937', '#faf9f7')
    assert _styles(readonly)['border-top-color'] == 'rgb(128, 139, 153)'
    assert _styles(readonly)['opacity'] == '1'


@pytest.mark.parametrize('width,height,padding', [(1440, 900, 32), (1024, 768, 32),
    (768, 1024, 24), (390, 844, 16), (1920, 1080, 32)])
def test_viewports_and_real_routes(site, width, height, padding, tmp_path):
    page = site[0]
    page.set_viewport_size({'width': width, 'height': height})
    for path in [DISPLAY, '/admin/cafeteria/komponenten', '/admin/cafeteria', '/admin/rezepte/neu']:
        _goto(page, path)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), path
        assert page.locator('.page-body > .container-xl').evaluate('el => parseFloat(getComputedStyle(el).paddingLeft)') == padding
        assert page.locator('.page-body > .container-xl').evaluate('el => getComputedStyle(el).maxWidth') == 'none'
        assert _styles(page.locator('h1'))['font-size'] == ('34px' if width >= 992 else '28px')
        for control in page.locator('.btn:visible, .form-control:visible, .form-select:visible').all():
            assert control.evaluate('el => el.getBoundingClientRect().height >= 48'), path
        page.screenshot(path=str(tmp_path / f'{path.rsplit("/", 1)[-1]}-{width}.png'), full_page=True)


def _open_display_reset(page):
    # Rare actions are collapsed by default; measure them after native disclosure.
    reset = page.locator('#display-reset-btn')
    expect(reset).to_be_hidden()
    summary = page.locator('#display-more > summary')
    summary.focus()
    page.keyboard.press('Enter')
    expect(reset).to_be_visible()
    page.keyboard.press('Tab')
    expect(reset).to_be_focused()
    expect(reset).to_have_attribute('name', 'action')
    expect(reset).to_have_attribute('value', 'reset')
    expect(page.locator('#display-reset-hint')).to_be_visible()


@pytest.mark.parametrize('width', [390, 1920])
def test_persisted_options_and_preview(site, width, tmp_path):
    page, app, _, _ = site
    page.set_viewport_size({'width': width, 'height': 1080})
    _goto(page, DISPLAY)
    values = [('comfortable', 'large', 'full', 'hide'), ('compact', 'normal', 'contained', 'show')]
    for density, size, content, images in values:
        for key, value in zip(DEFAULT_ADMIN_DISPLAY, [density, size, content, images]):
            page.locator(f'[name="{key}"]').select_option(value)
        before = get_admin_display(app.extensions['cafeteria_db'])
        page.locator('[name="action"][value="preview"]').click()
        assert get_admin_display(app.extensions['cafeteria_db']) == before
        expect(page.locator('.display-preview')).to_have_attribute('data-font-size', size)
        for scope in ['.display-preview', '.admin-main']:
            if scope == '.admin-main':
                page.locator('[name="action"][value="save"]').click()
                _open_display_reset(page)
            container = page.locator(scope)
            for key, value in [('density', density), ('font-size', size), ('content-width', content), ('menu-images', images)]:
                expect(container).to_have_attribute('data-' + key, value)
            scale = 1.125 if size == 'large' else 1
            expected_padding = (24 if width < 768 else 32) if density == 'comfortable' else (16 if width < 768 else 24)
            assert _styles(container.locator('.card-body').first)['padding-top'] == f'{expected_padding}px'
            for selector, base in [('.card-title', 20), ('.form-label', 14), ('.form-control', 16)]:
                assert float(_styles(container.locator(selector).first)['font-size'][:-2]) == base * scale
            for control in container.locator('.btn, .form-control, .form-select').all():
                assert control.evaluate('el => el.clientHeight >= el.scrollHeight - 1'), control.inner_text()
            preview = page.locator('.display-preview')
            expect(preview.locator('.menu-photo')).to_have_count(0 if images == 'hide' else 1)
        assert _styles(page.locator('h1'))['font-size'] == f'{(28 if width < 992 else 34) * scale:g}px'
        page.screenshot(path=str(tmp_path / f'options-{size}-{width}.png'), full_page=True)


def test_admin_contrast_gate_checks_unrounded_boundary():
    # #bd4573 passes on white, but fails on the selected-tab surface; gate is atomic.
    config = default_config() | {'primary': '#bd4573'}
    assert contrast(config['primary'], '#ffffff') >= 4.5
    assert contrast(config['primary'], '#f7e8ee') < 4.5
    assert '--app-primary' not in _admin_primary_css(config)


def test_sidebar_and_adjacent_contrasts(site, tmp_path):
    page = site[0]
    _goto(page, '/admin/cafeteria')
    selector = '.admin-sidebar .nav-link, .admin-user-text > span, .form-label, .form-hint, .badge'
    pairs = page.locator(selector).evaluate_all('''els => els.map(el => {
      let parent=el;
      while (parent && getComputedStyle(parent).backgroundColor === 'rgba(0, 0, 0, 0)') parent=parent.parentElement;
      return {text:getComputedStyle(el).color, bg:getComputedStyle(parent).backgroundColor};
    })''')
    for pair in pairs:
        assert contrast(_hex(pair['text']), _hex(pair['bg'])) >= 4.5, pair
    # Two contextual markers -> one strong surface (navigation supplement 2026-09-24).
    active_links = page.locator('.admin-sidebar .nav-link.active')
    expect(active_links).to_have_count(2)
    parent_styles = _styles(active_links.first)
    assert parent_styles['box-shadow'] == 'none'
    assert parent_styles['background-color'] == 'rgba(0, 0, 0, 0)'
    active_styles = _styles(active_links.last)
    assert 'rgb(243, 166, 192)' in active_styles['box-shadow']
    assert contrast('#ffffff', _hex(active_styles['background-color'])) >= 4.5
    active = page.locator('.admin-sidebar .admin-nav-subitems .nav-link[aria-current="page"]')
    expect(active).to_have_count(1)
    active.focus()
    page.keyboard.press('Tab')
    focused = page.locator('.admin-sidebar :focus-visible')
    assert _styles(focused)['outline-color'] == 'rgb(255, 255, 255)'
    _goto(page, DISPLAY)
    field = _styles(page.locator('#display-example'))
    assert contrast(_hex(field['border-top-color']), _hex(field['background-color'])) >= 3
    _focus(page.locator('#admin-density'))
    field = _styles(page.locator('#admin-density'))
    assert contrast(_hex(field['outline-color']), _hex(field['background-color'])) >= 3
    (tmp_path / 'adjacent-contrasts.json').write_text(json.dumps(pairs, indent=2))


@pytest.mark.parametrize('width', [390, 1440])
def test_no_js_keyboard_and_larger_text(site, width, tmp_path):
    page = site[0]
    _goto(page, DISPLAY)
    url = urlsplit(page.url)
    with page.context.browser.new_context(base_url=f'{url.scheme}://{url.netloc}',
            java_script_enabled=False, viewport={'width': width, 'height': 900},
            reduced_motion='reduce') as context:
        context.add_cookies(page.context.cookies())
        no_js = context.new_page()
        for path in [DISPLAY, '/admin/cafeteria/komponenten', '/admin/cafeteria', '/admin/rezepte/neu']:
            _goto(no_js, path)
            assert no_js.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), path
            no_js.keyboard.press('Tab')
            expect(no_js.locator('.skip-link')).to_be_focused()
            no_js.keyboard.press('Enter')
            expect(no_js.locator('#main-content')).to_be_focused()
            no_js.screenshot(path=str(tmp_path / f'no-js-{path.rsplit("/", 1)[-1]}-{width}.png'), full_page=True)
        _goto(no_js, DISPLAY)
        # Text-only 200% enlargement, in addition to the responsive viewport matrix.
        no_js.evaluate("document.documentElement.style.fontSize = '200%'")
        _open_display_reset(no_js)
        assert no_js.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for control in no_js.locator('.btn, .form-control, .form-select').all():
            assert control.evaluate('el => el.clientHeight >= el.scrollHeight - 1')


def test_cached_legacy_brand_response_cannot_recolor_admin(site):
    page = site[0]
    config = default_config() | PALETTES['dark']
    # Frozen response rules from branding_tokens.py:74-87 at 05b6c81 (before MP).
    legacy = ':root{' + ';'.join(f'{k}:{v}' for k, v in brand_tokens(config).items()) + '}'
    legacy += (
        '.dishboard-admin h1,.dishboard-admin h2,.dishboard-admin h3{font-family:var(--sh-font-display)}'
        '.dishboard-admin{--tblr-primary-fg:var(--brand-on-primary,var(--sh-white));'
        '--tblr-heading-color:var(--sh-ink);--tblr-bg-forms:var(--sh-panel);--tblr-body-bg:var(--sh-canvas);'
        '--tblr-bg-surface:var(--sh-panel);--tblr-bg-surface-secondary:var(--sh-panel-soft);'
        '--tblr-bg-surface-tertiary:var(--sh-panel-soft)}'
        '.dishboard-admin .admin-sidebar{--tblr-navbar-bg:var(--brand-sidebar,var(--sh-teal-950))}'
        '.bg-primary.text-white,.btn-primary{color:var(--brand-on-primary,var(--sh-white))!important}'
        '.list-group-item.active{background:var(--sh-primary);color:var(--brand-on-primary,var(--sh-white))}'
        '.dishboard-admin .nav-tabs .nav-link{color:var(--sh-primary)}'
        '.dishboard-admin .form-control::file-selector-button{color:var(--sh-ink);background:var(--sh-panel-soft)}'
    )
    page.route('**/branding/revisions/*.css', lambda route: route.fulfill(content_type='text/css', body=legacy))
    _goto(page, DISPLAY)
    _assert_color(page.locator('body'), '#1f2937', '#f6f4f1')
    _assert_color(page.locator('button.btn-primary'), '#ffffff', '#a3164d')
    assert _styles(page.locator('h1'))['font-family'].startswith('"Fira Sans"')
    assert _styles(page.locator('.admin-sidebar'))['background-color'] == 'rgb(23, 60, 63)'


def test_polish_six_status_styles_have_text_icons_and_contrast(site, tmp_path):
    page, app, _, _ = site
    _goto(page, DISPLAY)
    keys = ['status.neutral', 'status.active', 'status.success', 'status.warning', 'status.error', 'status.info']
    variants = ['neutral', 'active', 'success', 'warning', 'danger', 'info']
    with app.test_request_context():
        markup = render_template_string('''
            {% from 'ui/_semantic.html' import status_badge_sem, status_bar %}
            {% for key in keys %}{{ status_badge_sem(key) }}{% endfor %}
            {% for key in keys %}{{ status_bar('navigation.menus', [{'key': key, 'value': 0}]) }}{% endfor %}
        ''', keys=keys)
    page.locator('main').evaluate('(el, html) => el.innerHTML = html', markup)
    for key, variant in zip(keys, variants, strict=True):
        badge = page.locator(f'.badge[data-semantic="{key}"]')
        expect(badge).to_have_class(re.compile(rf'admin-status--{variant}(?:\s|$)'))
        for node in [badge, page.locator(f'.admin-statusbar-item--{variant}')]:
            assert node.inner_text().strip()
            expect(node.locator('svg')).to_have_count(1)
            assert node.locator('svg use').evaluate('el => el.getBBox().width > 0')
            colors = _styles(node)
            assert contrast(_hex(colors['color']), _hex(colors['background-color'])) >= 4.5, (variant, colors)
    page.screenshot(path=str(tmp_path / 'polish-statuses-after.png'), full_page=True)


def test_polish_heading_scale_flat_cards_and_header_budget(site, tmp_path):
    page, app, _, _ = site
    _goto(page, DISPLAY)
    with app.test_request_context():
        markup = render_template_string('''{% from 'admin/_macros.html' import page_header, actions %}
          <header class="admin-page-header">{{ page_header('Menüs', description='Aktuelle Woche bearbeiten',
            breadcrumbs=[('Wochenplan', '#week'), ('Menüs', none)],
            actions=actions(primary={'label': 'Speichern', 'icon': 'device-floppy'}),
            status_items=[{'label': 'Prüfstand', 'value': 'Offen', 'detail': '2 Angaben fehlen', 'href': '#review'}] * 5) }}</header>
          <div class="card"><div class="card-body"><h2>Abschnitt</h2>
            <div class="card"><div class="card-body"><h3>Details</h3>Inhalt</div></div>
          </div></div>''')
    page.locator('main').evaluate('(el, html) => el.innerHTML = html', markup)
    values = page.locator('body').evaluate('''el => Object.fromEntries(
        ['--app-font-size-h1', '--app-font-size-h2', '--app-font-size-h3', '--app-table-row-height']
        .map(k => [k, getComputedStyle(el).getPropertyValue(k).trim()]))''')
    assert values == {'--app-font-size-h1': '2.125rem', '--app-font-size-h2': '1.25rem',
                      '--app-font-size-h3': '1.125rem', '--app-table-row-height': '56px'}
    assert [float(_styles(page.locator(tag))['font-size'][:-2]) for tag in ['h1', 'h2', 'h3']] == [34, 20, 18]
    nested = page.locator('.card .card')
    assert nested.evaluate('el => ["Top", "Right", "Bottom", "Left"].every(s => getComputedStyle(el)["border" + s + "Width"] === "0px")')
    expect(nested).to_have_css('box-shadow', 'none')
    assert page.locator('.admin-page-header').bounding_box()['height'] <= 200, page.locator(
        '.admin-page-header, .page-header, .page-header-row, .admin-statusbar, .admin-statusbar-item'
    ).evaluate_all('els => els.map(el => ({class: el.className, height: el.offsetHeight, width: el.offsetWidth, padding: getComputedStyle(el).padding, margin: getComputedStyle(el).margin}))')
    assert page.locator('.card').first.evaluate('el => parseFloat(getComputedStyle(el).borderTopWidth)') == 1
    page.screenshot(path=str(tmp_path / 'polish-header-cards.png'), full_page=True)


def test_polish_interaction_states_keep_focus_and_disabled_distinct(site):
    page = site[0]
    _goto(page, DISPLAY)
    page.locator('main').evaluate('''el => el.innerHTML = `<div class="admin-list-actions">
        <button class="btn btn-ghost" id="ghost">Bearbeiten</button>
        <button class="btn btn-danger" id="danger">Löschen</button>
        <button class="btn btn-primary" disabled>Gesperrt</button>
        <a href="#target" aria-disabled="true">Nicht verfügbar</a></div>`''')
    assert page.locator('body').evaluate('el => getComputedStyle(el).getPropertyValue("--app-focus-width").trim()') == '2px'
    for selector in ['#ghost', '#danger']:
        control = page.locator(selector)
        before = control.evaluate('el => [getComputedStyle(el).backgroundColor, getComputedStyle(el).filter]')
        control.hover()
        hover = control.evaluate('el => [getComputedStyle(el).backgroundColor, getComputedStyle(el).filter]')
        assert hover != before
        page.mouse.down()
        active = control.evaluate('el => [getComputedStyle(el).backgroundColor, getComputedStyle(el).filter]')
        assert active != hover
        page.mouse.move(0, 0)
        page.mouse.up()
        _focus(control)
        assert float(_styles(control)['outline-width'][:-2]) >= 2
    expect(page.locator('button:disabled')).to_have_css('border-top-style', 'dashed')
    link = page.get_by_role('link', name='Nicht verfügbar')
    link.focus()
    page.keyboard.press('Enter')
    assert urlsplit(page.url).fragment == ''
