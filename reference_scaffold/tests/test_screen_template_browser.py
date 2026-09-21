"""Real published snapshots, runtime app role and native screen forms in Chromium."""
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria.menu_images import CATALOG
from cafeteria.screen_templates import key
from cafeteria.workflow import publish_draft
from test_admin_workflow_db import WEEK_START, _actor_id, _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_routes import screen_app as screen_app
from test_screen_template_store import state


@pytest.fixture
def published_app(screen_app, database_engine):  # noqa: F811
    image = next(item for item in json.loads(CATALOG.read_text()) if item['status'] == 'ready')
    snapshots = {}
    for profile, values in [('staff_guest', _staff_values()), ('patient', _patient_values())]:
        option = values['days'][0]['services'][0]['options'][0]
        option.update(title=image['title'], components=image['components'])
        version = _save_reviewed(database_engine, profile, values)
        snapshots[profile] = publish_draft(database_engine, profile, WEEK_START, expected_row_version=version,
                                           actor_id=_actor_id(database_engine), issuer_engine=database_engine)
    screen_app.config['S1_PUBLISHED_SNAPSHOTS'] = snapshots
    return screen_app


@pytest.fixture
def server(published_app):
    http = make_server('127.0.0.1', 0, published_app, threaded=True)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{http.server_port}'
    finally:
        http.shutdown()
        thread.join(timeout=5)
        http.server_close()


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_published_previews_and_assignment_form_are_readonly_tabler(
    published_app, server, database_engine, browser, width, javascript, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(published_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(published_app.config['SESSION_COOKIE_NAME'])
    before = state(database_engine)
    with browser.new_context(base_url=server, viewport={'width': width, 'height': 1100},
                             java_script_enabled=javascript, has_touch=width < 1440) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
        page = context.new_page()
        failures: list[str] = []
        requests: list[str] = []
        assets: dict[str, set[int]] = {}
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: requests.append(request.method) if request.method != 'GET' else None)
        page.on('response', lambda response: assets.setdefault(urlsplit(response.url).path, set()).add(response.status)
                if '/static/' in response.url else None)
        for family, prefix in [('cafeteria', 'cafeteria'), ('patienten', 'patient')]:
            # A prior preview click leaves the pointer over the next page's link.
            # Start each deliberate hover/focus check outside interactive content.
            page.mouse.move(0, 0)
            response = page.goto(f'/admin/screens/{family}/wochenvorlage')
            assert response.status == 200
            expect(page.get_by_role('heading', level=1)).to_have_text('Vorlage zuweisen')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assignment = page.locator('#screen-assignment-details')
            expect(assignment).not_to_have_attribute('open', '')
            help_control = assignment.locator(':scope > summary')
            assert help_control.bounding_box()['height'] >= 48
            help_control.tap() if width < 1440 else help_control.click()
            expect(assignment).to_have_attribute('open', '')
            cards = page.locator('.screen-choice-card').evaluate_all('els => els.map(el => {const b=el.getBoundingClientRect(); return [b.width,b.height]})')
            assert len(cards) == 2
            assert abs(cards[0][0] - cards[1][0]) <= 1 and abs(cards[0][1] - cards[1][1]) <= 1
            for control in page.locator('main .btn, main .screen-choice-control').all():
                assert control.bounding_box()['height'] >= 48
            expect(assignment).to_contain_text('Darstellung auswählen')
            preview = assignment.locator('a[href$="-week-text"]')
            expect(preview).to_have_accessible_name('Wochenplan ohne Bilder prüfen')
            assert preview.bounding_box()['width'] >= 48
            if javascript and width == 1440:
                preview.hover()
                tooltip = page.get_by_role('tooltip')
                expect(tooltip).to_have_text('Wochenplan ohne Bilder prüfen')
                expect(tooltip).to_be_visible()
                expect(tooltip).to_have_class(re.compile(r'\bshow\b'))
                page.mouse.move(0, 0)
                expect(page.get_by_role('tooltip')).to_have_count(0)
            preview.focus()
            if javascript:
                tooltip = page.get_by_role('tooltip')
                expect(tooltip).to_have_text('Wochenplan ohne Bilder prüfen')
                expect(tooltip).to_be_visible()
                expect(tooltip).to_have_class(re.compile(r'\bshow\b'))
                page.keyboard.press('Escape')
                expect(page.get_by_role('tooltip')).to_have_count(0)
                expect(preview).to_be_focused()
            radio = page.get_by_role('radio', name='Wochenplan ohne Bilder auswählen', exact=True)
            radio.focus()
            expect(radio).to_be_focused()
            page.keyboard.press('Space')
            expect(radio).to_be_checked()
            page.screenshot(path=str(tmp_path / f'assignment-{family}-{width}-js{javascript}.png'), full_page=True)
            for mode in ('photo', 'text'):
                page.goto(f'/admin/screens/{family}/wochenvorlage')
                page.locator('#screen-assignment-details > summary').click()
                target = f'/admin/vorlagen/screens/{family}/{prefix}-week-{mode}'
                name = 'Wochenplan mit Bildern prüfen' if mode == 'photo' else 'Wochenplan ohne Bilder prüfen'
                with page.expect_response(lambda response: urlsplit(response.url).path == target) as result:
                    preview_link = page.get_by_role('link', name=name, exact=True)
                    preview_link.tap() if width < 1440 else preview_link.click()
                response = result.value
                page.wait_for_url(f'{server}{target}', wait_until='domcontentloaded')
                assert response.status == 200 and response.headers['cache-control'] == 'no-store'
                assert response.headers['x-snapshot-revision']
                snapshot = published_app.config['S1_PUBLISHED_SNAPSHOTS']['patient' if family == 'patienten' else 'staff_guest']
                titles = [option['title'] for day in snapshot['days'] for meal in day['services'] for option in meal['options']]
                assert page.locator('.card:has(> .card-status-top) .card-title').all_text_contents() == titles
                assert page.locator('.menu-photo').count() > 0 if mode == 'photo' else page.locator('.menu-photo').count() == 0
                for photo in page.locator('.menu-photo img').all():
                    photo.scroll_into_view_if_needed()
                    expect(photo).to_have_js_property('complete', True)
                    assert photo.evaluate('image => image.naturalWidth > 0')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.screenshot(path=str(tmp_path / f'preview-{family}-{mode}-{width}-js{javascript}.png'), full_page=True)
        assert not failures and not requests
        for path in ('/static/tokens.css', '/static/vendor/tabler/tabler.min.css', '/static/admin-tabler.css'):
            assert 200 in assets[path]
        assert all(status < 400 for statuses in assets.values() for status in statuses)
    assert state(database_engine) == before


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('family,prefix,path', [
    ('cafeteria', 'cafeteria', '/cafeteria/wochenangebot/'),
    ('patienten', 'patient', '/patienten/wochenplan/'),
])
def test_real_activation_changes_canonical_view_and_preserves_original_conflict(
    published_app, server, database_engine, browser, width, javascript, family, prefix, path, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(published_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(published_app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(base_url=server, viewport={'width': width, 'height': 1100},
                             java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
        page = context.new_page()
        stale = context.new_page()
        route = f'/admin/screens/{family}/wochenvorlage'
        assert page.goto(path).headers['cache-control'] == 'no-store'
        original = page.locator('.card-body').all_text_contents()
        assert page.locator('.menu-photo').count() > 0
        page.goto(route)
        stale.goto(route)
        page.locator('#screen-assignment-details > summary').click()
        stale.locator('#screen-assignment-details > summary').click()
        token = stale.locator('[name="_form_context"]').input_value()
        submitted = []
        page.on('request', lambda request: submitted.append(request.method) if request.method == 'POST' else None)
        for version, (mode, name) in enumerate([('text', 'ohne Bilder'), ('photo', 'mit Bildern')], 1):
            page.get_by_role('radio', name=f'Wochenplan {name} auswählen', exact=True).check()
            with page.expect_response(lambda response: response.request.method == 'POST') as result:
                page.get_by_role('button', name='Speichern', exact=True).click()
            assert result.value.status == 303
            expect(page.locator('[name="version"]')).to_have_value(str(version))
            assert page.goto(path).headers['cache-control'] == 'no-store'
            assert page.locator('.card-body').all_text_contents() == original
            assert page.locator('.menu-photo').count() > 0 if mode == 'photo' else page.locator('.menu-photo').count() == 0
            page.goto(path + 'ohne-bilder/')
            assert page.locator('.menu-photo').count() == 0
            page.goto('/admin/screens')
            expect(page.locator(f'#{prefix}-public-week-tab')).to_have_text(f'Wochenplan {name} · aktiv')
            page.goto(route)
            page.locator('#screen-assignment-details > summary').click()
        assert submitted == ['POST', 'POST']
        stale.get_by_role('radio', name='Wochenplan ohne Bilder auswählen', exact=True).check()
        before = state(database_engine)
        with stale.expect_response(lambda response: response.request.method == 'POST') as result:
            stale.get_by_role('button', name='Speichern', exact=True).click()
        assert result.value.status == 409
        expect(stale.locator('[name="_form_context"]')).to_have_value(token)
        expect(stale.locator('[name="version"]')).to_have_value('0')
        expect(stale.get_by_role('radio', name='Wochenplan ohne Bilder auswählen')).to_be_checked()
        expect(stale.get_by_role('alert')).to_be_focused()
        assert stale.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        stale.screenshot(path=str(tmp_path / f'conflict-{family}-{width}-js{javascript}.png'), full_page=True)
        assert state(database_engine) == before
        stale.locator('[name="renderer_revision"]').evaluate("input => input.value = '2'")
        with stale.expect_response(lambda response: response.request.method == 'POST') as result:
            stale.get_by_role('button', name='Speichern', exact=True).click()
        assert result.value.status == 400
        expect(stale.get_by_role('alert')).to_have_text('Aktion oder Rendererrevision ist ungültig.')
        expect(stale.locator('[name="_form_context"]')).to_have_value(token)
        expect(stale.locator('[name="version"]')).to_have_value('0')
        expect(stale.locator('[name="renderer_revision"]')).to_have_value('2')
        expect(stale.get_by_role('radio', name='Wochenplan ohne Bilder auswählen')).to_be_checked()
        expect(stale.get_by_role('alert')).to_be_focused()
        assert state(database_engine) == before
        with database_engine.begin() as connection:
            connection.execute(text('''UPDATE cafeteria.settings SET setting_value=CAST(:value AS jsonb)
                WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key'''),
                {'key': key('staff_guest' if family == 'cafeteria' else 'patient'),
                 'value': json.dumps({'schema_version': 99})})
        before_failure = state(database_engine)
        failure = page.goto(path)
        assert failure.status == 503 and failure.headers['cache-control'] == 'no-store'
        assert page.locator('.menu-photo').count() == 0
        expect(page.get_by_role('heading', level=1)).to_have_text('Bildschirmvorlagen vorübergehend nicht verfügbar')
        assert state(database_engine) == before_failure


def _assert_wp23_compact_frames_payload_order_and_keyboard(
    published_app, server, database_engine, javascript, tmp_path: Path,  # noqa: F811
):
    """Own browser start; measure the same default state as the pre-edit probe."""
    client, _ = _login(published_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(published_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    baseline = {360: (2572, 468.1875), 768: (1450, 586.40625),
                1024: (1385, 581.90625), 1440: (1567, 672.90625)}
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        try:
            with instance.new_context(base_url=server, java_script_enabled=javascript) as context:
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
                page = context.new_page()
                for width, height in [(360, 800), (768, 1024), (1024, 768), (1440, 900)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    assert page.goto('/admin/screens').status == 200
                    page.evaluate('document.fonts.ready')
                    metrics = page.evaluate('''() => ({
                        pageHeight: document.documentElement.scrollHeight,
                        cardHeight: document.querySelector('.screen-card').getBoundingClientRect().height,
                        primary: document.querySelectorAll('main .btn-primary').length,
                        openDetails: document.querySelectorAll('main details[open]').length,
                        scrollWidth: document.documentElement.scrollWidth
                    })''')
                    print('WP23_AFTER', width, javascript, json.dumps(metrics))
                    assert metrics['pageHeight'] < baseline[width][0]
                    assert metrics['cardHeight'] < baseline[width][1]
                    assert metrics['scrollWidth'] <= width
                    assert metrics['primary'] == metrics['openDetails'] == 0
                    expect(page.locator('.admin-statusbar-item')).to_have_count(2)
                    expect(page.locator('.screen-card')).to_have_count(4)
                    expect(page.locator('.screen-card .btn:visible')).to_have_count(8)
                    page.screenshot(path=str(tmp_path / f'wp23-{width}-{javascript}.png'), full_page=True)
                    for selector in ('.screen-more-actions', '.screen-preview-details'):
                        details = page.locator(selector).first
                        summary = details.locator(':scope > summary')
                        summary.focus()
                        page.keyboard.press('Enter')
                        expect(details).to_have_attribute('open', '')
                        expect(summary).to_be_focused()
                        assert summary.bounding_box()['height'] >= 48
                        assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                        page.keyboard.press('Enter')
                        expect(details).not_to_have_attribute('open', '')
                    assert page.goto('/admin/screens/cafeteria/wochenvorlage').status == 200
                    form = page.locator('#screen-assignment-details form')
                    fields = form.evaluate('form => Array.from(new FormData(form))')
                    assert [name for name, _ in fields] == [
                        '_csrf', '_form_context', 'version', 'renderer_revision', 'action', 'template_id',
                    ]
                    assert all(value for _, value in fields[:2])
                    assert fields[2:] == [['version', '0'], ['renderer_revision', '1'],
                                         ['action', 'activate'], ['template_id', 'cafeteria-week-photo']]
                    summary = page.locator('#screen-assignment-details > summary')
                    summary.focus()
                    page.keyboard.press('Enter')
                    expect(page.locator('.admin-form-footer .btn-primary')).to_have_text('Speichern')
                    assert form.evaluate('form => Array.from(new FormData(form))') == fields
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    expect(page.locator('#screen-assignment-version')).not_to_have_attribute('open', '')
                    for target in page.locator('main .btn:visible, main summary:visible').all():
                        assert target.bounding_box()['height'] >= 48
                    assert page.goto('/admin/cafeteria/preview?week=2026-08-31').status == 200
                    expect(page.locator('.page-header .admin-statusbar')).to_have_count(1)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    expect(page.locator('main .btn-primary')).to_have_count(1)
                    expect(page.locator('script, style, [style], form, button')).to_have_count(0)
        finally:
            instance.close()


@pytest.mark.parametrize('javascript', [False, True], ids=['nojs', 'js'])
def test_wp23_compact_frames_payload_order_and_keyboard(
    published_app, server, database_engine, javascript, tmp_path: Path,  # noqa: F811
):
    # The module's existing browser fixture owns a sync event loop on the main thread.
    # Keep this explicitly independent Playwright start on its own thread.
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(
            _assert_wp23_compact_frames_payload_order_and_keyboard,
            published_app, server, database_engine, javascript, tmp_path,
        ).result(timeout=120)
