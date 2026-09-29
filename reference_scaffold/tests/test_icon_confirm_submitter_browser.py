"""Submitter confirmations guard real mutations without stranding loading buttons."""
from __future__ import annotations

from urllib.parse import parse_qsl

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.shopping_list_store import add_manual_item, create_shopping_list
from test_dish_template_browser import b3, master_server  # noqa: F401
from test_dish_template_routes import create, snapshot
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
        form.locator('.ui-sem-actions > summary').click()
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
        page.locator('.admin-form-footer .ui-sem-actions > summary').click()
        button = page.locator('button[value="archive"]')
        _confirm_mutation(page, button, 'Diese Vorlage archivieren?', 'archive', 'updated_at',
                          activate, lambda: snapshot(owner), tmp_path)
        with owner.connect() as connection:
            assert connection.execute(text(
                'SELECT active FROM cafeteria.dish_templates WHERE public_id=CAST(:id AS uuid)',
            ), {'id': path.rsplit('/', 1)[-1]}).scalar_one() is False
