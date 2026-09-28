"""Native validation markers use real shared summaries, shell and tooltip lifecycle."""
import json
from threading import Thread

import pytest
from flask import render_template_string, request as flask_request
from playwright.sync_api import expect
from werkzeug.serving import make_server

from cafeteria.ui import register_ui
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory


@pytest.fixture
def error_site(monkeypatch, tmp_path, database_engine, request):  # noqa: F811
    app = _factory(monkeypatch, tmp_path, database_engine)
    app.config['UI_LOCALE'] = getattr(request, 'param', 'de')
    register_ui(app)
    client, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    posts = []

    @app.route('/__disclosure_error__', methods=['GET', 'POST'])
    def error_page():
        if flask_request.method == 'POST':
            posts.append({key: flask_request.form.getlist(key) for key in flask_request.form})
            return {'saved': posts[-1]}
        return render_template_string('''{% extends 'admin/base_tabler.html' %}
            {% from 'admin/_macros.html' import field %}
            {% from 'ui/_semantic.html' import icon_summary, icon_button %}
            {% block content %}
            <form id="draft" method="post" action="/__disclosure_error__">
              <input type="hidden" name="revision" value="7">
              {{ field('note', 'Notiz', 'Entwurf & Kräuter') }}
              <details id="text-detail" open><summary>Weitere Angaben</summary>
                <details id="icon-detail" open>
                  {{ icon_summary('actions.more', object='Entwurf', attrs={'aria-describedby': 'detail-help'}) }}
                  <p id="detail-help">Die Angaben bleiben erhalten.</p>
                  <label for="confirm">Ich bestätige diese Änderung.</label>
                  <input id="confirm" type="checkbox" name="confirm" value="yes" required>
                  <p>Die Bestätigung ist vor dem Speichern erforderlich.</p>
                  {{ field('reference', 'Referenz', 'Entwurf', error='Referenz prüfen' if errors else none) }}
                </details>
              </details>
              {{ icon_button('actions.save', id='save', name='intent', value='save') }}
            </form>
            {% endblock %}''', errors=flask_request.args.get('errors') == '1',
            family='cafeteria', profile='staff_guest', brand=app.jinja_env.undefined())

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    try:
        yield origin, {'name': cookie.key, 'value': cookie.value, 'url': origin}, posts, app
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _visit(context, site, suffix=''):
    origin, cookie, _, _ = site
    context.add_cookies([cookie])
    page = context.new_page()
    assert page.goto(origin + '/__disclosure_error__' + suffix).status == 200
    page.evaluate('document.fonts.ready')
    return page


def _marker_geometry(page, destination):
    summary = page.locator('#icon-detail > summary')
    marker = summary.locator('[data-admin-details-error]')
    expect(marker).to_be_visible()
    metrics = summary.evaluate('''el => {
        const box = node => {const r = node.getBoundingClientRect();
            return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
        const marker = el.querySelector('[data-admin-details-error]');
        return {summary:box(el),marker:box(marker),coarse:matchMedia('(pointer: coarse), (any-pointer: coarse)').matches,
            icon:box(el.querySelector(':scope > .icon')), overflow:document.documentElement.scrollWidth > innerWidth+1};
    }''')
    destination.with_suffix('.json').write_text(json.dumps(metrics, indent=2))
    page.screenshot(path=str(destination.with_suffix('.png')), full_page=True)
    outer, inner = metrics['summary'], metrics['marker']
    size = 44 if metrics['coarse'] else 36
    assert outer['width'] == pytest.approx(size) and outer['height'] == pytest.approx(size)
    assert inner['x'] >= outer['x'] and inner['y'] >= outer['y'], metrics
    assert inner['right'] <= outer['right'] and inner['bottom'] <= outer['bottom'], metrics
    assert metrics['icon']['width'] == 20 and metrics['icon']['height'] == 20
    assert not metrics['overflow']
    expect(marker.locator('svg')).to_be_visible()
    return marker


@pytest.mark.parametrize('width,touch', [(390, False), (390, True), (1440, False), (1440, True)])
def test_native_error_marker_fits_and_preserves_submit(error_site, browser, width, touch, tmp_path):  # noqa: F811
    with browser.new_context(viewport={'width': width, 'height': 900}, has_touch=touch,
                             reduced_motion='reduce') as context:
        page = _visit(context, error_site)
        summary = page.locator('#icon-detail > summary')
        name = summary.get_attribute('aria-label')
        description = summary.get_attribute('aria-describedby')
        summary.press('Enter')
        expect(page.locator('#icon-detail')).not_to_have_attribute('open', '')
        page.locator('#save').click()
        expect(page.locator('#confirm')).to_be_focused()
        expect(page.locator('#icon-detail')).to_have_attribute('open', '')
        assert error_site[2] == []
        assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") == touch
        marker = _marker_geometry(page, tmp_path / f'native-{width}-{touch}')
        marker_id = marker.get_attribute('id')
        assert marker_id and marker_id in summary.get_attribute('aria-describedby').split()
        expect(summary).to_have_accessible_name(name)
        expect(summary).to_have_attribute('data-ui-tooltip', name)
        expect(summary).to_have_accessible_description('Die Angaben bleiben erhalten. Fehler')
        expect(page.locator('#text-detail > summary')).to_contain_text('Fehler')
        summary.press('Enter')
        expect(marker).to_be_visible()
        summary.press('Enter')
        page.locator('#confirm').check()
        expect(marker).to_have_count(0)
        page.mouse.move(0, 0)
        page.locator('#note').focus()
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(summary).to_have_attribute('aria-describedby', description)
        page.locator('#save').click()
        expect(page).to_have_url(error_site[0] + '/__disclosure_error__')
        expect(page.locator('body')).to_contain_text('saved')
        assert error_site[2] == [{'revision': ['7'], 'note': ['Entwurf & Kräuter'],
                                 'confirm': ['yes'], 'reference': ['Entwurf'], 'intent': ['save']}]


@pytest.mark.parametrize('phase', ['hover', 'leaving'])
def test_clear_error_preserves_descriptions_through_tooltip_hide(error_site, browser, phase):  # noqa: F811
    with browser.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce') as context:
        page = _visit(context, error_site)
        summary = page.locator('#icon-detail > summary')
        name = summary.get_attribute('aria-label')
        page.locator('#save').click()
        marker = summary.locator('[data-admin-details-error]')
        expect(marker).to_be_visible()
        marker_id = marker.get_attribute('id')
        assert marker_id
        summary.hover()
        tooltip = page.get_by_role('tooltip', name=name, exact=True)
        expect(tooltip).to_be_visible()
        expect(page.locator('#confirm')).to_be_focused()
        if phase == 'leaving':
            page.mouse.move(0, 0)
        page.keyboard.press('Space')
        expect(page.locator('#confirm')).to_be_checked()
        expect(marker).to_have_count(0)
        assert marker_id not in (summary.get_attribute('aria-describedby') or '').split()
        assert 'detail-help' in summary.get_attribute('aria-describedby').split()
        if phase == 'hover':
            expect(tooltip).to_be_visible()
        page.mouse.move(0, 0)
        expect(tooltip).to_have_count(0)
        expect(summary).to_have_attribute('aria-describedby', 'detail-help')
        expect(summary).to_have_accessible_name(name)
        expect(summary).to_have_attribute('data-ui-tooltip', name)
        assert error_site[2] == []


@pytest.mark.parametrize('error_site', ['de', 'en', 'xx'], indirect=True)
def test_server_error_description_is_localized(error_site, browser, tmp_path):  # noqa: F811
    with browser.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce') as context:
        page = _visit(context, error_site, '?errors=1')
        summary = page.locator('#icon-detail > summary')
        marker = _marker_geometry(page, tmp_path / 'server')
        app = error_site[3]
        message = app.extensions['ui_translator'].locales[app.config['UI_LOCALE']]['status.error.label']
        expect(marker).to_contain_text(message)
        expect(summary).to_have_accessible_description('Die Angaben bleiben erhalten. ' + message)
        expect(page.locator('#reference')).to_be_focused()
        expect(page.locator('#reference-error')).to_have_text('Referenz prüfen')
        assert error_site[2] == []


@pytest.mark.parametrize('width', [390, 1440])
def test_nojs_confirmation_stays_native(error_site, browser, width):  # noqa: F811
    with browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=False) as context:
        page = _visit(context, error_site)
        summary = page.locator('#icon-detail > summary')
        summary.press('Enter')
        expect(page.locator('#icon-detail')).not_to_have_attribute('open', '')
        summary.press('Space')
        expect(page.locator('#icon-detail')).to_have_attribute('open', '')
        page.locator('#save').click()
        expect(page.locator('#confirm')).not_to_be_checked()
        assert error_site[2] == []
        page.locator('#confirm').check()
        page.locator('#save').click()
        expect(page.locator('body')).to_contain_text('saved')
        assert error_site[2][0]['confirm'] == ['yes']
        assert error_site[2][0]['note'] == ['Entwurf & Kräuter']
