"""Real HTTP/CSP editor flow, palette contrast, logo sizing and signage refresh."""
from __future__ import annotations

from copy import deepcopy
from threading import Thread
from types import SimpleNamespace

import pytest
from flask import request
from playwright.sync_api import expect
from sqlalchemy.exc import OperationalError
from werkzeug.serving import make_server

from cafeteria import create_app, branding_routes
from cafeteria.branding import change_branding, read_branding
from cafeteria.branding_config import contrast, default_config
from test_admin_workflow_routes import _login, app as workflow_app, database_engine  # noqa: F401
from test_branding_store import _png
from test_rendered_ui import browser as browser
from demo_snapshots import cafeteria_snapshot, patient_snapshot


@pytest.fixture
def live_branding(workflow_app, database_engine, monkeypatch):  # noqa: F811
    monkeypatch.setattr('cafeteria.Config', lambda: SimpleNamespace(**workflow_app.config))
    monkeypatch.setattr('cafeteria.init_app_database', lambda real: real.extensions.update(workflow_app.extensions))
    snapshots = {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}
    monkeypatch.setattr('cafeteria.public.routes.active_snapshot', lambda _engine, profile, *_args, **_kwargs: deepcopy(snapshots[profile]))
    real = create_app()
    @real.after_request
    def polling(response):
        if request.path.startswith('/signage/'):
            response.set_data(response.get_data().replace(b'data-signage-interval="60000"', b'data-signage-interval="100"'))
        return response
    client, actor = _login(real, database_engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        authz = session['authz_version']
    server = make_server('127.0.0.1', 0, real, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', real, client, actor, authz
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _hex(value):
    channels = value.removeprefix('rgb(').removesuffix(')').split(',')
    return '#' + ''.join(f'{int(part.strip()):02x}' for part in channels)


def test_http_editor_preview_activation_inverted_palette_and_logo(live_branding, database_engine, browser, tmp_path):  # noqa: F811
    origin, _, client, _, _ = live_branding
    cookie = client.get_cookie('session')
    with browser.new_context(viewport={'width': 1440, 'height': 1100}) as context:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': origin}])
        page = context.new_page()
        failures = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        response = page.goto(origin + '/admin/design/marke', wait_until='networkidle')
        assert response.status == 200
        assert "style-src 'self'" in response.headers['content-security-policy']
        assert page.locator('link[rel="icon"]').count() == 1
        page.locator('#brand-name').fill('Nachtpalette')
        page.locator('#brand-primary').fill('#ffddaa')
        page.locator('#brand-accent').fill('#aaddff')
        page.locator('#brand-surface').fill('#111111')
        page.locator('#brand-text').fill('#ffffff')
        page.locator('#brand-font_body').select_option('carlito')
        page.locator('#brand-upload').set_input_files({'name': 'Logo.png', 'mimeType': 'image/png', 'buffer': _png((100, 100))})
        page.get_by_role('button', name='Entwurf speichern & Vorschau').click()
        expect(page).to_have_url(origin + '/admin/design/marke?revision=2')
        preview = page.frame_locator('iframe')
        expect(preview.get_by_role('heading', name='Frisch zubereitet')).to_be_visible()
        button_colors = preview.locator('.btn-primary').evaluate('(el) => ({text:getComputedStyle(el).color,bg:getComputedStyle(el).backgroundColor})')
        assert contrast(_hex(button_colors['text']), _hex(button_colors['bg'])) >= 4.5, button_colors
        assert preview.locator('body').evaluate('el=>getComputedStyle(el).fontFamily').startswith('Carlito')
        with database_engine.connect() as connection:
            assert read_branding(connection)['active_revision'] == 1
        page.screenshot(path=str(tmp_path / 'brand-editor-desktop.png'), full_page=True)
        page.get_by_role('button', name='Revision 2 aktivieren').click()
        expect(page.get_by_role('status')).to_contain_text('Nachtpalette')
        for width in (390, 820, 1440):
            page.set_viewport_size({'width': width, 'height': 1100})
            page.goto(origin + '/admin/design/marke', wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            pairs = page.locator('.form-label, .form-hint, .card-title, .nav-tabs .nav-link.active, .brand-status, .list-group-item.active').evaluate_all('''elements=>elements.map(el=>{
                let parent=el;
                while (parent && getComputedStyle(parent).backgroundColor==='rgba(0, 0, 0, 0)') parent=parent.parentElement;
                return {text:getComputedStyle(el).color,bg:getComputedStyle(parent).backgroundColor,label:el.textContent};
            })''')
            for pair in pairs:
                assert contrast(_hex(pair['text']), _hex(pair['bg'])) >= 4.5, pair
            page.screenshot(path=str(tmp_path / f'brand-editor-{width}.png'), full_page=True)
        for path in ('/cafeteria/heute/', '/cafeteria/wochenangebot/', '/patienten/heute/', '/patienten/wochenplan/'):
            response = page.goto(origin + path, wait_until='networkidle')
            assert response.status == 200
            assert page.locator('link[data-brand-stylesheet]').get_attribute('href') == '/branding/revisions/2.css'
            image = page.locator('.site-logo-img')
            assert image.evaluate('el=>el.complete && el.naturalWidth===100 && getComputedStyle(el).objectFit==="contain"')
            colors = page.locator('.card-title').first.evaluate('el=>({text:getComputedStyle(el).color,bg:getComputedStyle(el.closest(".card")).backgroundColor})')
            assert contrast(_hex(colors['text']), _hex(colors['bg'])) >= 4.5, colors
            page.screenshot(path=str(tmp_path / f'brand-{path.strip("/").replace("/","-")}.png'), full_page=True)
        assert failures == []


def test_signage_brand_signal_updates_styles_without_menu_revision_or_navigation(live_branding, database_engine, browser, tmp_path):  # noqa: F811
    origin, _, _, actor, authz = live_branding
    with browser.new_context(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce') as context:
        page = context.new_page()
        page.goto(origin + '/signage/cafeteria/tag', wait_until='load')
        revision = page.locator('html').get_attribute('data-signage-revision')
        navigations = []
        page.on('framenavigated', lambda frame: navigations.append(frame.url))
        config = {**default_config(), 'primary': '#173b66', 'font_body': 'carlito'}
        change_branding(database_engine, actor, authz, 0, 'save', name='Neue Marke', config=config)
        change_branding(database_engine, actor, authz, 1, 'activate', revision_id=2)
        expect(page.locator('html')).to_have_attribute('data-brand-revision', '2')
        expect(page.locator('link[data-brand-stylesheet]')).to_have_attribute('href', origin + '/branding/revisions/2.css')
        assert page.locator('html').get_attribute('data-signage-revision') == revision
        assert page.locator('body').evaluate('el=>getComputedStyle(el).fontFamily').startswith('Carlito')
        assert navigations == []
        page.screenshot(path=str(tmp_path / 'brand-signage-fhd.png'))
        page.set_viewport_size({'width': 3840, 'height': 2160})
        page.screenshot(path=str(tmp_path / 'brand-signage-4k.png'))


def test_brand_read_failure_keeps_last_valid_menu_and_brand(live_branding, database_engine, monkeypatch):  # noqa: F811
    _, real, _, actor, authz = live_branding
    change_branding(database_engine, actor, authz, 0, 'save', name='Gültig', config={**default_config(), 'font_body': 'carlito'})
    change_branding(database_engine, actor, authz, 1, 'activate', revision_id=2)
    client = real.test_client()
    before = client.get('/cafeteria/heute/')
    assert before.status_code == 200 and b'/branding/revisions/2.css' in before.data
    def unavailable(*_args):
        raise OperationalError('offline', {}, None)
    monkeypatch.setattr(branding_routes, 'read_branding', unavailable)
    after = client.get('/cafeteria/heute/')
    assert after.status_code == 200 and b'/branding/revisions/2.css' in after.data
    assert after.headers['X-Snapshot-Revision'] == before.headers['X-Snapshot-Revision']
    assert client.get('/branding/revisions/2.css').status_code == 200


@pytest.mark.parametrize('path', ['/signage/cafeteria/tag', '/signage/cafeteria/woche', '/signage/patienten/tag', '/signage/patienten/woche'])
def test_inverted_signage_palette_keeps_menu_labels_readable(live_branding, database_engine, browser, tmp_path, path):  # noqa: F811
    origin, _, _, actor, authz = live_branding
    config = {**default_config(), 'surface': '#111111', 'text': '#ffffff', 'primary': '#ffddaa', 'accent': '#aaddff', 'font_body': 'carlito'}
    change_branding(database_engine, actor, authz, 0, 'save', name='Nachtpalette', config=config)
    change_branding(database_engine, actor, authz, 1, 'activate', revision_id=2)
    with browser.new_context(reduced_motion='reduce') as context:
        page = context.new_page()
        failures = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        for width,height in [(1920,1080),(3840,2160)]:
            page.set_viewport_size({'width':width,'height':height})
            page.goto(origin + path, wait_until='load')
            page.evaluate('document.fonts.ready')
            pairs = page.locator('.card h2:visible,.card h3:visible,.card p:visible,.meal-name:visible,.slot-type:visible').evaluate_all('''elements=>elements.flatMap(el=>{
                let parent=el;
                while (parent && getComputedStyle(parent).backgroundColor==='rgba(0, 0, 0, 0)') parent=parent.parentElement;
                return parent ? [{text:getComputedStyle(el).color,bg:getComputedStyle(parent).backgroundColor,label:el.textContent}] : [];
            })''')
            assert pairs
            for pair in pairs:
                assert contrast(_hex(pair['text']), _hex(pair['bg'])) >= 4.5, pair
            page.screenshot(path=str(tmp_path / f'{path.strip("/").replace("/","-")}-{width}.png'))
        assert failures == []
