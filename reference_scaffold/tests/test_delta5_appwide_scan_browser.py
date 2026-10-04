"""Rendered UI-DELTA ratchet; baseline records debt, never product compliance."""
from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Thread
from time import monotonic
from urllib.parse import urlsplit

import pytest
from flask import abort
from werkzeug.serving import make_server

from test_admin_workflow_routes import DATABASE_URL, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import (
    _factory, _matrix, _prepare_inventory_entities, _role_clients,
)

BASELINE = Path(__file__).with_name('delta5_scan_baseline.json')
PROBE = Path(__file__).with_name('delta5_scan_probe.js')
VIEWPORTS = ((1440, 900), (390, 844))
WEEK = '2026-08-31'


def _key(row):
    return (row['route'], row['viewport'], row['category'], row['selector'], row['text'])


def _regressions(findings, baseline):
    allowed = {_key(row) for row in baseline}
    return [row for row in findings if _key(row) not in allowed]


def _cases(app, prepared):
    """Use inventory seeds, real URL rules and both concrete family variants."""
    adapter = app.url_map.bind('localhost')
    rules = {rule.endpoint: rule for rule in app.url_map.iter_rules() if 'GET' in rule.methods}
    cases = []
    for row in _matrix()['routes']:
        if not row['visual'] or 'GET' not in row['methods'] or not row['rule'].startswith('/admin'):
            continue
        rule = rules[row['endpoint']]
        for family in ('cafeteria', 'patienten') if 'family' in rule.arguments else (None,):
            path = prepared['endpoint_paths'].get(row['endpoint'])
            if path:
                if family:
                    path = re.sub(r'(?<=/)cafeteria(?=[/?]|$)', family, path)
            else:
                assert rule.arguments <= {'family'}, (row['endpoint'], rule.arguments)
                path = adapter.build(row['endpoint'], {'family': family} if family else {})
            if family == 'patienten' and row['endpoint'] == 'admin.screen_template_preview':
                path = path.replace('cafeteria-week-photo', 'patient-week-photo')
            separator = '&' if '?' in path else '?'
            if row['endpoint'] in {'admin.cafeteria', 'admin.patienten', 'admin.copy_get',
                                    'admin.header_get', 'admin.service_get', 'admin.menu_get',
                                    'admin.preview', 'admin.week_review_get'} and 'week=' not in path:
                path += separator + 'week=' + WEEK
            if row['endpoint'] == 'admin.kitchen_calendar':
                path += '?year=2026&month=9'
            route = re.sub(r'<(?:[^<>:]+:)?([^<>]+)>', lambda m: (
                family if m[1] == 'family' else '<' + m[1] + '>'), rule.rule)
            cases.append({'endpoint': row['endpoint'], 'route': route, 'path': path})
    return cases


@pytest.mark.skipif(not DATABASE_URL, reason='Exclusive TEST_DATABASE_URL required.')
def test_delta5_appwide_render_ratchet(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    started = monotonic()
    app = _factory(monkeypatch, tmp_path, database_engine)
    clients, user_id = _role_clients(app, database_engine)
    prepared = _prepare_inventory_entities(app, database_engine, user_id)
    cases = _cases(app, prepared)

    @app.get('/__delta5_error/<int:status>')
    def error_page(status):
        # Real production error handlers/templates, synthetic HTTP failure only.
        abort(status)

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    cookie = clients['Cafeteria.Admin'].get_cookie(app.config['SESSION_COOKIE_NAME'])
    findings, coverage = [], []
    try:
        for width, height in VIEWPORTS:
            app.config['DEMO_MODE'] = True
            with browser.new_context(
                base_url=origin, viewport={'width': width, 'height': height},
                locale='de-CH', timezone_id='Europe/Zurich', java_script_enabled=True,
                reduced_motion='reduce', has_touch=width == 390,
            ) as context:
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
                page = context.new_page()
                page.set_default_timeout(10000)
                page.set_default_navigation_timeout(20000)
                for case in cases:
                    if case['endpoint'] == 'admin.order_basket_csv':
                        response = context.request.get(case['path'])
                        assert response.status == 200
                        assert 'text/csv' in response.headers['content-type']
                        coverage.append({'route': case['route'], 'viewport': width,
                                         'endpoint': case['endpoint'], 'status': 200,
                                         'measurement': 'non_html_download',
                                         'classification': 'Messartefakt: visual=true CSV'})
                        continue
                    _scan_page(page, case, width, findings, coverage)
                specials = [('/__delta5_error/403', 403), ('/__delta5_missing', 404),
                            ('/__delta5_error/500', 500), ('/__delta5_error/503', 503)]
                for path, status in specials:
                    _scan_page(page, {'path': path, 'route': path, 'status': status},
                               width, findings, coverage)
                context.clear_cookies()
                app.config.update(DEMO_MODE=False, ENTRA_ENABLED=False)
                for path in ('/auth/login', '/auth/local'):
                    _scan_page(page, {'path': path, 'route': path, 'landing': '/auth/local'},
                               width, findings, coverage)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    findings.sort(key=_key)
    result = {'role': 'Cafeteria.Admin', 'javascript': True, 'demo_today': '2026-09-02',
              'viewports': [list(size) for size in VIEWPORTS], 'coverage': coverage,
              'findings': findings, 'duration_seconds': round(monotonic() - started, 3)}
    artifact = tmp_path / 'findings.json'
    artifact.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    regressions = _regressions(findings, baseline)
    assert result['duration_seconds'] < 900, result['duration_seconds']
    assert not regressions, f'{len(regressions)} new findings; evidence={artifact}\n' + json.dumps(
        regressions[:8], ensure_ascii=False, indent=2)


def _scan_page(page, case, width, findings, coverage):
    response = page.goto(case['path'], wait_until='load')
    assert response.status == case.get('status', 200), (case['route'], response.status)
    assert 'text/html' in response.headers['content-type'], case
    assert urlsplit(page.url).path == urlsplit(case.get('landing', case['path'])).path, (case, page.url)
    page.evaluate('document.fonts.ready')
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    rows = page.evaluate(PROBE.read_text(encoding='utf-8'))
    for row in rows:
        findings.append({'route': case['route'], 'viewport': width, **row})
    coverage.append({'route': case['route'], 'viewport': width, 'status': response.status,
                     'landing': urlsplit(page.url).path,
                     'endpoint': case.get('endpoint', 'special'), 'measurement': 'rendered_dom',
                     'findings': len(rows)})


def test_delta5_detector_rendered_counterexamples(browser):  # noqa: F811
    """Catch hidden text/icons, generated content, native values and real overlays."""
    with browser.new_context() as context:
        page = context.new_page()
        page.set_content('''<style>
          svg {width:20px;height:20px} .gone {display:none} .invisible {visibility:hidden}
          .visually-hidden {position:absolute;width:1px;height:1px;overflow:hidden}
          .pseudo::before {content:"\\e900";display:inline-block;width:20px;height:20px}
          .pseudo-dash::after {content:"—"} .pseudo-text::before {content:"Text"}
          .arrow::after {content:"";display:inline-block;border-top:5px solid;border-left:5px solid transparent}
          .background {display:inline-block;width:20px;height:20px;background-image:linear-gradient(black,white)}
          .overlay {position:fixed} .zero {width:0;height:0;overflow:hidden;display:inline-block}
        </style>
        <button id="mixed"><svg></svg>Speichern</button>
        <button id="pseudo" class="pseudo">Text</button>
        <button id="arrow" class="arrow">Auswahl</button>
        <button id="background"><span class="background"></span>Text</button>
        <button id="generated-text" class="pseudo-text"><svg></svg></button>
        <button id="italic"><i>★</i>Text</button>
        <button id="hidden-text"><svg></svg><span class="visually-hidden">Name</span></button>
        <button id="hidden-icon"><svg class="gone"></svg>Text</button>
        <button id="zero-icon"><span class="background zero"></span>Text</button>
        <button class="invisible"><svg></svg>Hidden</button>
        <div style="opacity:0"><button><svg></svg>Transparent</button></div>
        <aside class="admin-sidebar"><a class="nav-link"><svg></svg>Navigation</a>
          <button id="sidebar-action"><svg></svg>Abmelden</button>
          <details><summary>Gruppe</summary>Navigation</details></aside>
        <span id="dash">—</span><span id="pseudo-dash" class="pseudo-dash"></span>
        <span id="real-negative">−2</span><code>−</code><select><option>—</option></select>
        <div id="not-a-dash">−<button>Action</button></div>
        <button id="sr-text"><svg></svg><span class="sr-only">Name</span></button>
        <a class="btn" id="link"><svg></svg>Link</a>
        <span role="button" id="role-button"><svg></svg>Action</span>
        <span role="tab" id="tab"><svg></svg>Tab</span>
        <a class="nav-link" id="area-nav"><svg></svg>Area</a>
        <label><input type="checkbox">Checkbox</label>
        <details id="details"><summary>Zusatzinhalt</summary><p>Inhalt</p></details>
        <button id="flow-trigger" aria-expanded="false" aria-controls="flow">Details</button>
        <div id="flow" hidden>Inhalt</div>
        <button aria-expanded="false" aria-controls="modal">Dialog</button>
        <dialog id="modal">Overlay</dialog>
        <button aria-expanded="false" aria-controls="picker" role="combobox">Select</button>
        <div id="picker" role="listbox">Auswahl</div>
        <button aria-expanded="false" aria-controls="overlay">Overlay</button>
        <div class="overlay" id="overlay">Overlay</div>''')
        actual = {(row['category'], row['selector']) for row in page.evaluate(PROBE.read_text(encoding='utf-8'))}
    assert actual == {
        ('mixed_button', '#' + name) for name in (
            'mixed', 'pseudo', 'arrow', 'background', 'generated-text', 'italic', 'sidebar-action',
            'link', 'role-button', 'tab', 'area-nav')
    } | {('dash_placeholder', '#dash'), ('dash_placeholder', '#pseudo-dash'),
         ('content_disclosure', '#details'), ('content_disclosure', '#flow-trigger')}


def test_delta5_ratchet_checks_identity_and_allows_debt_removal():
    row = dict(route='/admin/x', viewport=390, category='mixed_button', selector='#save', text='Save')
    assert not _regressions([row], [row])
    assert not _regressions([], [row])
    for field, replacement in [('route', '/admin/new'), ('viewport', 1440),
                               ('category', 'dash_placeholder'), ('selector', '#other'), ('text', 'New')]:
        assert _regressions([{**row, field: replacement}], [row])
