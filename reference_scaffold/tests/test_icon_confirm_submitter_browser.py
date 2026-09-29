"""Submitter confirmations guard real mutations without stranding loading buttons."""
from __future__ import annotations

import datetime as dt
from urllib.parse import parse_qsl

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.shopping_list_store import add_manual_item, create_shopping_list
from cafeteria import recipe_store
from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_routes import _login, _payload, _scope as workflow_scope
from test_cookbooks_browser import cookbook_server  # noqa: F401
from test_dish_template_browser import b3, master_server  # noqa: F401
from test_dish_template_routes import create, snapshot
from test_icon_publish_guards_browser import _database_snapshot
from test_master_data_db import signed_in
from test_recipe_store_db import snapshot as recipe_snapshot
from test_rendered_ui import admin_app, admin_engine  # noqa: F401
from test_shopping_list_browser import (  # noqa: F401
    _scope, app_client, app_engine, browser, installed_pg16, pg16, seeded_pg16,
    server, store,
)


def _open(context, base, cookie, path, dirty_off):
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
    page = context.new_page()
    if dirty_off:
        # Exercise opt-out registration before admin.js runs, using the real page.
        def opt_out(route):
            response = route.fetch()
            body = response.text().replace(
                ' data-loading', ' data-dirty-tracking="off" data-confirm="Formularfrage" data-loading',
            )
            route.fulfill(response=response, body=body)
        page.route(base + path, opt_out, times=1)
    assert page.goto(base + path).status == 200
    return page


def _confirm_mutation(page, button, message, action, cas, activate, read_state, tmp_path):
    form = button.locator('xpath=ancestor::form')
    expected_fields = button.evaluate('button => [...new FormData(button.form, button)]')
    fields = dict(expected_fields)
    assert fields['_csrf'] and fields[cas] and fields['action'] == action
    before = read_state()
    posts, dialogs = [], []
    page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)

    def dismiss(dialog):
        dialogs.append((dialog.type, dialog.message))
        dialog.dismiss()

    def accept(dialog):
        dialogs.append((dialog.type, dialog.message))
        dialog.accept()

    def submit():
        if activate == 'enter':
            button.focus()
            button.press('Enter')
        else:
            button.click()

    page.on('dialog', dismiss)
    submit()
    assert dialogs == [('confirm', message)]
    # Flush the deferred loader before checking cancellation's stable state.
    page.evaluate('() => new Promise(resolve => setTimeout(resolve, 0))')
    assert posts == []
    assert read_state() == before
    expect(button).to_be_enabled()
    assert button.get_attribute('aria-busy') is None
    assert button.evaluate('button => !button.classList.contains("admin-btn-loading")')
    assert button.evaluate('button => [...new FormData(button.form, button)]') == expected_fields
    page.screenshot(path=str(tmp_path / f'{action}-{activate}-cancelled.png'), full_page=True)
    page.remove_listener('dialog', dismiss)
    page.on('dialog', accept)
    target = form.evaluate('form => new URL(form.getAttribute("action"), document.baseURI).href')
    with page.expect_navigation(wait_until='load'), page.expect_response(
        lambda response: response.request.method == 'POST' and response.url == target,
    ) as result:
        submit()
    assert dialogs == [('confirm', message), ('confirm', message)]
    assert result.value.status == 303
    assert len(posts) == 1 and posts[0].url == target
    assert parse_qsl(posts[0].post_data, keep_blank_values=True) == [tuple(pair) for pair in expected_fields]
    assert read_state() != before
    expect(page.locator('.admin-btn-loading, [aria-busy="true"]')).to_have_count(0)


def _shopping_snapshot(owner):
    with owner.connect() as connection:
        return {table: connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
        )).all() for table in ('shopping_lists', 'shopping_list_manual_items', 'audit_events')}


@pytest.mark.parametrize('activate', ['click', 'enter'])
@pytest.mark.parametrize('dirty_off', [False, True], ids=['native', 'dirty-off-form-fallback'])
def test_delete_manual_item_requires_submitter_confirmation(
    server, browser, tmp_path, activate, dirty_off,  # noqa: F811
):
    base, cookie, owner, engine, ids = server
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Bestätigung Einkauf')
    item_id = add_manual_item(engine, scope, list_id, item_text='Bestätigung Mehl', quantity='2', unit_code='KG')
    with browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce') as context:
        page = _open(context, base, cookie, f'/admin/einkaufslisten/{list_id}', dirty_off)
        form = page.locator('form.shopping-item-form').filter(has=page.locator('button[value="delete"]'))
        expect(form.locator('[data-semantic="actions.more"]')).to_have_count(0)
        button = form.locator('button[value="delete"]')
        _confirm_mutation(page, button, 'Diese Position löschen?', 'delete', 'expected_row_version',
                          activate, lambda: _shopping_snapshot(owner), tmp_path)
        with owner.connect() as connection:
            assert connection.execute(text(
                'SELECT count(*) FROM cafeteria.shopping_list_manual_items WHERE public_id=CAST(:id AS uuid)',
            ), {'id': item_id}).scalar_one() == 0
        expect(form).to_have_count(0)


@pytest.mark.parametrize('activate', ['click', 'enter'])
@pytest.mark.parametrize('dirty_off', [False, True], ids=['native', 'dirty-off-form-fallback'])
def test_archive_dish_template_requires_submitter_confirmation(
    b3, master_server, browser, tmp_path, activate, dirty_off,  # noqa: F811
):
    _, owner, client, _ = b3
    path = create(client, title='Bestätigung Vorlage')
    base, cookie = master_server
    with browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce') as context:
        page = _open(context, base, cookie, path, dirty_off)
        expect(page.locator('.admin-form-footer [data-semantic="actions.more"]')).to_have_count(0)
        button = page.locator('button[value="archive"]')
        _confirm_mutation(page, button, 'Diese Vorlage archivieren?', 'archive', 'updated_at',
                          activate, lambda: snapshot(owner), tmp_path)
        with owner.connect() as connection:
            assert connection.execute(text(
                'SELECT active FROM cafeteria.dish_templates WHERE public_id=CAST(:id AS uuid)',
            ), {'id': path.rsplit('/', 1)[-1]}).scalar_one() is False


def _native_confirmation(page, open_confirmation, return_url, cancel_name, button_name,
                         expected_values, read_state, before, posts, tmp_path):
    """Cancel and reopen the real GET confirmation, then submit its native form once."""
    for cancel in (True, False):
        open_confirmation()
        assert posts == [] and read_state() == before
        button = page.get_by_role('button', name=button_name, exact=True)
        expect(button).to_be_visible()
        expect(button).to_have_text(button_name)
        fields = button.evaluate('button => [...new FormData(button.form, button)]')
        values = dict(fields)
        assert values['_csrf']
        assert set(values) == {'_csrf', *expected_values}
        for name, value in expected_values.items():
            assert values[name] if value is None else values[name] == value
        if cancel:
            page.screenshot(path=str(tmp_path / 'native-confirmation.png'), full_page=True)
            with page.expect_navigation(wait_until='load'):
                page.get_by_role('link', name=cancel_name, exact=True).click()
            expect(page).to_have_url(return_url)
            assert posts == [] and read_state() == before
        else:
            target = button.evaluate('button => button.form.action')
            with page.expect_navigation(wait_until='load'), page.expect_response(
                lambda response: response.request.method == 'POST' and response.url == target,
            ) as result:
                button.focus()
                button.press('Enter')
            assert result.value.status == 303
            expect(page).to_have_url(return_url)
            assert len(posts) == 1 and posts[0].url == target
            assert parse_qsl(posts[0].post_data, keep_blank_values=True) == [tuple(pair) for pair in fields]
            assert read_state() != before


@pytest.mark.parametrize('kind', ['recipe', 'cookbook'])
@pytest.mark.parametrize('javascript', [False, True], ids=['no-js', 'js'])
@pytest.mark.parametrize('width', [390, 1440])
def test_archive_recipe_and_cookbook_native_confirmation(
    cookbook_server, browser, tmp_path, kind, javascript, width,  # noqa: F811
):
    base, cookie, owner, engine, actor = (
        cookbook_server[key] for key in ('base', 'cookie', 'owner', 'engine', 'actor')
    )
    public_id, version = cookbook_server['first'], 1
    if kind == 'cookbook':
        with signed_in(engine, actor):
            location = recipe_store.get_location(engine)
            book = recipe_store.create_cookbook(
                engine, actor, name='Bestätigung Kochbuch', expected_location_id=location,
            )
            book = recipe_store.replace_cookbook_recipes(
                engine, actor, recipe_store.ObjectExpectation(book.public_id, book.row_version),
                [cookbook_server['second'], cookbook_server['first']], expected_location_id=location,
            )
            public_id, version = book.public_id, book.row_version
    collection = 'rezepte' if kind == 'recipe' else 'kochbuecher'
    path = f'/admin/{collection}/{public_id}'
    before = recipe_snapshot(owner)
    with browser.new_context(viewport={'width': width, 'height': 900},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        page = _open(context, base, cookie, path, False)
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)

        def open_confirmation():
            expect(page.locator('[data-semantic="actions.more"], .admin-form-rare > summary')).to_have_count(0)
            name = 'Alpha archivieren' if kind == 'recipe' else 'Bestätigung Kochbuch archivieren'
            archive = page.get_by_role('link', name=name, exact=True)
            expect(archive).to_be_visible()
            expect(archive).to_have_attribute('data-ui-tooltip', name)
            expect(archive).to_have_text('')
            assert posts == [] and recipe_snapshot(owner) == before
            with page.expect_navigation(wait_until='load'):
                archive.click()
            expect(page).to_have_url(base + path + '/status')
            expect(page.get_by_text(
                'Archivieren erhält Zutaten, Bilder und gespeicherte Stände.' if kind == 'recipe'
                else 'wird archiviert und bleibt lesbar.', exact=False,
            )).to_be_visible()

        expected = {'_form_context': None, 'row_version': str(version)}
        expected.update({'active': '0'} if kind == 'recipe' else {'status_action': 'cookbook.archive'})
        _native_confirmation(page, open_confirmation, base + path, 'Abbrechen', 'Archivieren',
                             expected, lambda: recipe_snapshot(owner), before, posts, tmp_path)
        if kind == 'recipe':
            expect(page.locator('#recipe-editor fieldset')).to_have_attribute('disabled', '')
            expect(page.get_by_label('Titel', exact=True)).to_be_disabled()
            expect(page.get_by_label('Zutatenbezeichnung', exact=True)).to_be_disabled()
        else:
            expect(page.get_by_role('button', name='Rezepte speichern', exact=True)).to_have_count(0)
            expect(page.locator('[data-status="archived"]')).to_have_text('Archiviert')
    table = 'recipes' if kind == 'recipe' else 'cookbooks'
    with owner.connect() as connection:
        assert tuple(connection.execute(text(
            f'SELECT active, row_version FROM cafeteria.{table} WHERE public_id=CAST(:id AS uuid)',
        ), {'id': public_id}).one()) == (False, version + 1)
    after = recipe_snapshot(owner)
    # Archive preserves contents, recipe order, images and revisions.
    assert {key: value for key, value in after.items() if key not in (table, 'audit_events')} == {
        key: value for key, value in before.items() if key not in (table, 'audit_events')
    }


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [False, True], ids=['no-js', 'js'])
@pytest.mark.parametrize('width', [390, 1440])
def test_previous_week_copy_native_confirmation(
    browser, live_server, admin_app, admin_engine, tmp_path, family, profile, javascript, width,  # noqa: F811
):
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    source = dt.date(2026, 12, 28)
    target = source + dt.timedelta(days=7)
    persist_menu_item(
        admin_app.extensions['cafeteria_db'], workflow_scope(admin_engine, user_id, profile),
        source, source.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=profile == 'staff_guest'), 0,
    )
    before = _database_snapshot(admin_engine)
    cookie = client.get_cookie('session')
    assert cookie is not None
    path = f'/admin/{family}?week={target.isoformat()}'
    with browser.new_context(viewport={'width': width, 'height': 900},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        page = _open(context, live_server, cookie, path, False)
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)

        def open_confirmation():
            expect(page.locator('.admin-week-more > summary')).to_have_count(0)
            expect(page.get_by_role('link', name='Vorwoche kopieren', exact=True)).to_be_visible()
            assert posts == [] and _database_snapshot(admin_engine) == before
            with page.expect_navigation(wait_until='load') as response:
                page.get_by_role('link', name='Vorwoche kopieren', exact=True).click()
            assert response.value.status == 200
            expect(page).to_have_url(f'{live_server}/admin/{family}/copy?week={target.isoformat()}')
            expect(page.locator('#copy-effects')).to_contain_text('Prüfbestätigungen werden nicht übernommen')
            expect(page.get_by_role('button', name='Vorwoche kopieren', exact=True)).to_have_attribute(
                'form', 'week-copy-form',
            )

        _native_confirmation(
            page, open_confirmation, live_server + path, 'Zurück zur Wochenübersicht', 'Vorwoche kopieren',
            {'source_week': source.isoformat(), 'target_week': target.isoformat(), 'target_row_version': '0'},
            lambda: _database_snapshot(admin_engine), before, posts, tmp_path,
        )
        expect(page.locator(
            f'.menu-slot[data-day="{target.isoformat()}"][data-meal="LUNCH"]'
            '[data-option="MENU_1"] h3',
        )).to_have_text('Kartoffelgratin')
    with admin_engine.connect() as connection:
        rows = connection.execute(text(
            'SELECT p.code, w.week_start, w.workflow_state, i.title FROM cafeteria.menu_weeks w '
            'JOIN cafeteria.offer_profiles p ON p.id=w.profile_id '
            'JOIN cafeteria.menu_services s ON s.menu_week_id=w.id '
            'JOIN cafeteria.menu_items i ON i.service_id=s.id ORDER BY w.week_start',
        )).all()
        assert [tuple(row) for row in rows] == [
            (profile, source, 'draft', 'Kartoffelgratin'), (profile, target, 'draft', 'Kartoffelgratin'),
        ]
    after = _database_snapshot(admin_engine)
    assert after['publication_revisions'] == before['publication_revisions']
    assert after['publication_lifecycle_events'] == before['publication_lifecycle_events']
