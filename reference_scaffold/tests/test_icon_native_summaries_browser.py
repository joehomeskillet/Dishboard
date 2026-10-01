"""Native icon disclosures retain selected content, forms and error recovery."""
from __future__ import annotations

import threading
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy.exc import OperationalError
from werkzeug.serving import make_server

from cafeteria.admin import screen_template_routes
from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login, _payload
from test_menu_collection import _save, _scope
from test_print_template_browser import browser, _context  # noqa: F401
from test_print_template_routes import database_engine  # noqa: F401
from test_recipe_template_editor_browser import recipe_server  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    BASE, recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example, state,
)
from test_screen_template_routes import screen_app  # noqa: F401
from test_screen_template_store import state as screen_state


def _icon(trigger):
    expect(trigger).to_have_text('', timeout=300)
    assert trigger.get_attribute('aria-label')
    assert trigger.get_attribute('data-ui-tooltip') == trigger.get_attribute('aria-label')
    expect(trigger.locator('svg[aria-hidden="true"]')).to_have_count(1)
    assert trigger.evaluate('el => el.getBoundingClientRect().width >= 36')


def _keyboard(page, details, javascript):
    summary = details.locator(':scope > summary')
    _icon(summary)
    if details.get_attribute('open') is not None:
        summary.press('Enter')
    expect(details).not_to_have_attribute('open', '')
    summary.press('Space')
    expect(details).to_have_attribute('open', '')
    if javascript:
        expect(page.get_by_role('tooltip')).to_have_count(1)
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(summary).to_be_focused()
    summary.press('Enter')
    expect(details).not_to_have_attribute('open', '')
    summary.press('Space')
    expect(details).to_have_attribute('open', '')


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
def test_recipe_selection_icons_keep_names_revisions_and_native_gets(
    recipe_editor, recipe_server, browser, tmp_path, width, javascript,  # noqa: F811
):
    _, owner, client, _ = recipe_editor
    recipe, revision, _ = example(recipe_editor)
    before = state(owner)
    with _context(browser, recipe_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        posts, errors = [], []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        assert page.goto(BASE).status == 200
        page.screenshot(path=str(tmp_path / f'recipe-initial-{width}-js{javascript}.png'), full_page=True)
        selection = page.locator('[data-recipe-selection]')
        _keyboard(page, selection, javascript)
        search = selection.locator('details').first
        _keyboard(page, search, javascript)
        expect(search.get_by_text('Suppe', exact=True)).to_be_visible()
        search.get_by_role('link', name='Gespeicherte Stände für Suppe auswählen', exact=True).click()
        query = parse_qs(urlsplit(page.url).query)
        assert query['recipe'] == [recipe] and 'recipe_revision' not in query
        revisions = selection.locator('details').last
        _keyboard(page, revisions, javascript)
        expect(revisions.get_by_role('heading', name='Suppe', exact=True)).to_be_visible()
        saved = page.get_by_label('Gespeicherter Rezeptstand', exact=True)
        expect(saved.locator(f'option[value="{revision.public_id}"]')).to_contain_text('Gespeicherter Stand 1')
        saved.select_option(revision.public_id)
        page.get_by_role('button', name='Gespeicherten Stand verwenden', exact=True).click()
        assert parse_qs(urlsplit(page.url).query)['recipe_revision'] == [revision.public_id]
        expect(selection).not_to_have_attribute('open', '')
        _icon(selection.locator(':scope > summary'))
        assert 'Suppe' in selection.locator(':scope > summary').get_attribute('aria-label')
        page.screenshot(path=str(tmp_path / f'recipe-selected-{width}-js{javascript}.png'), full_page=True)
        page.get_by_label('Vorlagenname', exact=True).fill('Mein ungespeicherter Vorlagenname')
        fields = page.locator('main form').evaluate_all('forms => forms.map(f => [...new FormData(f)])')
        _keyboard(page, selection, javascript)
        assert page.locator('main form').evaluate_all('forms => forms.map(f => [...new FormData(f)])') == fields
        expect(page.get_by_role('heading', name='Ausgewählt: Suppe · Gespeicherter Stand 1', exact=True)).to_be_visible()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Mein ungespeicherter Vorlagenname')
        page.get_by_label('Gewünschte Ausbeute', exact=True).fill('8')
        page.on('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Ausbeute anwenden', exact=True).click()
        query = parse_qs(urlsplit(page.url).query)
        assert query['recipe'] == [recipe] and query['recipe_revision'] == [revision.public_id]
        assert query['yield'] == ['8']
        selection.locator(':scope > summary').press('Enter')
        expect(page.get_by_label('Gewünschte Ausbeute', exact=True)).to_have_value('8')
        page.screenshot(path=str(tmp_path / f'recipe-open-{width}-js{javascript}.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not posts and not errors and state(owner) == before


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Publisher'])
def test_menu_note_icons_keep_content_profile_navigation_and_native_keyboard(
    admin_app, admin_engine, live_server, browser, tmp_path, width, javascript, role,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    title = 'Kartoffelgratin <&> "Hausart"'
    for family, profile in [('cafeteria', 'staff_guest'), ('patienten', 'patient')]:
        payload = _payload(staff=profile == 'staff_guest')
        payload.update(description='Mit frischen Kräutern.', note='Vor Ausgabe umrühren.')
        _save(admin_engine, _scope(client, admin_engine, profile), title=title, payload=payload)
    client, _ = _login(admin_app, admin_engine, [role])
    with _context(browser, live_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        posts, errors = [], []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        for family, label in [('cafeteria', 'Cafeteria'), ('patienten', 'Patienten')]:
            assert page.goto(f'/admin/{family}/menues').status == 200
            page.screenshot(path=str(tmp_path / f'menu-initial-{family}-{width}-js{javascript}-{role}.png'), full_page=True)
            expect(page.locator('nav.profile-tabs a[aria-current="true"]')).to_have_text(label)
            for view in ['list', 'cards']:
                if javascript:
                    page.get_by_role('tab', name='Liste' if view == 'list' else 'Karten', exact=True).click()
                row = page.locator(f'#menu-{view} [data-menu-{"list-id" if view == "list" else "id"}]')
                details = row.locator('.menu-note-details')
                _keyboard(page, details, javascript)
                expect(details.locator('.menu-description')).to_contain_text('Mit frischen Kräutern.')
                expect(details.locator('.shared-note')).to_contain_text('Vor Ausgabe umrühren.')
                summary = details.locator(':scope > summary')
                assert title in summary.get_attribute('aria-label')
                expect(summary.locator('img, script, button, input')).to_have_count(0)
                target = row.locator('[data-semantic="actions.edit"]').get_attribute('href')
                assert urlsplit(target).path == f'/admin/{family}/menu'
                assert parse_qs(urlsplit(target).query)['option'] == ['MENU_1']
                page.screenshot(path=str(tmp_path / f'menu-{family}-{view}-{width}-js{javascript}-{role}.png'), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not posts and not errors


@pytest.fixture
def unavailable_server(screen_app):  # noqa: F811
    server = make_server('127.0.0.1', 0, screen_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
def test_unavailable_retry_icon_is_a_native_get_after_failed_assignment(
    screen_app, database_engine, unavailable_server, browser, monkeypatch, tmp_path, width, javascript,  # noqa: F811
):
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    path = '/admin/screens/patienten/wochenvorlage'
    before = screen_state(database_engine)
    with _context(browser, unavailable_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        posts, errors = [], []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        assert page.goto(path).status == 200
        expect(page.locator('#screen-assignment-details')).to_be_visible()

        def unavailable(*args, **kwargs):
            raise OperationalError('private statement', {}, Exception('private error'))

        context_calls = []

        def unavailable_context():
            context_calls.append(True)
            raise AssertionError('Unavailable response invoked DB-dependent template context')

        with monkeypatch.context() as patch:
            patch.setattr(screen_template_routes.store, 'read_assignment', unavailable)
            patch.setattr(screen_template_routes.store, 'activate', unavailable)
            patch.setitem(screen_app.template_context_processors, None, [
                *screen_app.template_context_processors[None],
                unavailable_context,
            ])
            with page.expect_response(lambda response: response.request.method == 'POST') as failed:
                page.get_by_role('button', name='Speichern', exact=True).click()
            assert failed.value.status == 503
            assert "script-src 'self'" in failed.value.headers['content-security-policy']
            expect(page.get_by_text('Der Abschluss der Zuweisung konnte nicht bestätigt werden.', exact=False)).to_be_visible()
            page.screenshot(path=str(tmp_path / f'unavailable-initial-{width}-js{javascript}.png'), full_page=True)
            retry = page.get_by_role('link', name='Neu laden: Aktualisieren', exact=True)
            expect(retry).to_contain_text('Neu laden')
            assert retry.get_attribute('aria-label') == 'Neu laden: Aktualisieren'
            assert retry.get_attribute('data-ui-tooltip') == retry.get_attribute('aria-label')
            expect(retry.locator('svg[aria-hidden="true"]')).to_have_count(1)
            assert retry.evaluate('el => el.getBoundingClientRect().width >= 36')
            expect(retry).to_have_attribute('href', path)
            retry.focus()
            expect(retry).to_be_focused()
            if javascript:
                expect(page.get_by_role('tooltip')).to_have_text('Neu laden: Aktualisieren')
                page.keyboard.press('Escape')
                expect(page.get_by_role('tooltip')).to_have_count(0)
                expect(retry).to_be_focused()
                retry.blur()
                retry.hover()
                expect(page.get_by_role('tooltip')).to_have_text('Neu laden: Aktualisieren')
                page.keyboard.press('Escape')
                expect(page.get_by_role('tooltip')).to_have_count(0)
            page.screenshot(path=str(tmp_path / f'unavailable-post-{width}-js{javascript}.png'), full_page=True)
            with page.expect_navigation() as retried:
                retry.press('Enter')
            assert retried.value.request.method == 'GET' and retried.value.status == 503
            expect(page.get_by_text('Der Abschluss der Zuweisung konnte nicht bestätigt werden.', exact=False)).to_have_count(0)
            assert 'private' not in page.locator('main').inner_text()
            page.screenshot(path=str(tmp_path / f'unavailable-get-{width}-js{javascript}.png'), full_page=True)
        with page.expect_navigation() as recovered:
            page.get_by_role('link', name='Neu laden: Aktualisieren', exact=True).press('Enter')
        assert recovered.value.status == 200 and recovered.value.request.method == 'GET'
        expect(page.locator('#screen-assignment-details')).to_be_visible()
        assert len(posts) == 1 and not errors and not context_calls and screen_state(database_engine) == before
