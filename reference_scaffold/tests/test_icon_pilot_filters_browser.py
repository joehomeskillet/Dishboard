"""Shared recipe filtering keeps native queries, paging, roles and row context."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria import roles
from test_master_data_browser import master_server  # noqa: F401
from test_recipe_filter_reads import (  # noqa: F401
    app_engine, b3, complete_snapshot, filter_catalog, installed_pg16, pg16,
    seeded_pg16, seed_pages,
)
from test_rendered_ui import browser  # noqa: F401


def _assert_direct_actions(page, row, readonly, locale, javascript):
    title = row.locator('.admin-list-primary').inner_text()
    group = row.get_by_role('group', name=(f'Aktionen für {title}' if locale == 'de'
                                         else f'Actions for {title}'), exact=True)
    expect(group).to_be_visible()
    expect(row.locator('details.ui-sem-actions, [data-semantic="actions.more"]')).to_have_count(0)
    names = {
        'actions.open': (f'{title} öffnen', f'Open {title}'),
        'actions.edit': (f'{title} bearbeiten', f'Edit {title}'),
        'actions.open_pdf': (f'PDF von {title} öffnen', f'Open PDF of {title}'),
        'actions.history': (f'Verlauf für {title}', f'History for {title}'),
        'actions.snapshot': (f'Stand von {title} festhalten', f'Save a revision of {title}'),
        'actions.create_template': (f'Gerichtvorlage für {title} anlegen', f'Create dish template for {title}'),
    }
    keys = ['actions.open', 'actions.open_pdf', 'actions.history'] if readonly else list(names)
    assert group.locator('[data-semantic]').evaluate_all('(els) => els.map(el => el.dataset.semantic)') == keys
    for key in keys:
        action = group.locator(f'[data-semantic="{key}"]')
        name = names[key][locale == 'en']
        expect(action).to_be_visible()
        expect(action).to_have_text('')
        expect(action).to_have_accessible_name(name)
        if key == 'actions.open_pdf':
            expect(action).to_be_disabled()
            expect(action).to_have_accessible_description('Noch kein gespeicherter Stand vorhanden')
            assert action.get_attribute('href') is None
            action = group.locator('.ui-sem-disabled')
            expect(action).to_have_accessible_name(name)
            name += ': Noch kein gespeicherter Stand vorhanden'
        else:
            assert action.get_attribute('href')
        expect(action).to_have_attribute('data-ui-tooltip', name)
        action.focus()
        expect(action).to_be_focused()
        if javascript:
            tooltip = page.get_by_role('tooltip', name=name, exact=True)
            expect(tooltip).to_be_visible()
            page.keyboard.press('Escape')
            expect(tooltip).to_be_hidden()
            expect(action).to_be_focused()
        else:
            expect(page.get_by_role('tooltip')).to_have_count(0)


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('readonly', [False, True])
def test_recipe_shared_filters_keep_queries_paging_and_role_actions(
    b3, filter_catalog, master_server, browser, monkeypatch, tmp_path,  # noqa: F811
    width, javascript, readonly,
):
    app, owner, _, _ = b3
    tag, _ = seed_pages(b3)
    if readonly:
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = complete_snapshot(owner)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        writes, errors = [], []
        page.on('request', lambda request: writes.append(request.method) if request.method != 'GET' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(base + '/admin/rezepte', wait_until='networkidle')
        assert response.status == 200 and response.headers['cache-control'] == 'no-store'
        expect(page.locator('.admin-statusbar')).to_have_count(0)
        form = page.get_by_role('search')
        expect(form).to_have_count(1)
        expect(form).to_have_attribute('method', 'get')
        expect(form).to_have_attribute('action', '/admin/rezepte')
        expect(form.locator('input[name="text"]')).to_have_attribute('id', 'text')
        expect(form.locator('input[name="text"]')).to_have_attribute('aria-describedby', 'text-hint')
        expect(form.locator('input[name="text"]')).to_have_attribute('maxlength', '200')
        trigger = form.locator('.admin-filter-more > summary')
        expect(trigger).to_have_count(1)
        expect(trigger).to_have_attribute('data-semantic', 'view.filter')
        expect(trigger).to_have_text('', use_inner_text=True)
        expect(trigger.locator('.admin-filter-count')).to_be_hidden()
        expect(form.locator('button[data-semantic="view.filter"]')).to_have_count(0)
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('.page-header [data-semantic="actions.add"]')).to_have_count(0 if readonly else 1)
        if readonly:
            expect(form.locator('.btn-primary')).to_have_attribute('data-semantic', 'view.search')
            expect(page.locator('.recipe-row [data-semantic="actions.edit"]')).to_have_count(0)
        trigger.focus()
        expect(trigger).to_be_focused()
        page.keyboard.press('Enter')
        params = {'text': 'Seitensuppe', 'q': 'Seitensuppe', 'ingredient': 'rüebli',
                  'tag': tag, 'archived': '1'}
        for name in ('text', 'q', 'ingredient'):
            form.locator(f'[name="{name}"]').fill(params[name])
        form.locator('[name="tag"]').select_option(tag)
        form.locator('[name="archived"]').check()
        form.get_by_role('button', name='Übernehmen', exact=True).press('Enter')
        expect(page.locator('.recipe-row')).to_have_count(50)
        assert parse_qs(urlsplit(page.url).query) == {key: [value] for key, value in params.items()}
        expect(form.locator('.admin-filter-more')).to_have_attribute('open', '')
        expect(page.locator('.recipe-row .admin-status--info')).to_have_count(50)
        for name in ('text', 'q', 'ingredient', 'tag'):
            expect(form.locator(f'[name="{name}"]')).to_have_value(params[name])
        expect(form.locator('[name="archived"]')).to_be_checked()
        page.locator('nav[aria-label="Rezeptseiten"] a[href*="page=2"]').press('Enter')
        expect(page.locator('.recipe-row')).to_have_count(3)
        assert parse_qs(urlsplit(page.url).query) == ({key: [value] for key, value in params.items()}
                                                    | {'page': ['2']})
        row = page.locator('.recipe-row').first
        _assert_direct_actions(page, row, readonly, 'de', javascript)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / f'filters-{width}-js{javascript}-readonly{readonly}.png'), full_page=True)
        form.get_by_role('link', name='Zurücksetzen', exact=True).click()
        assert urlsplit(page.url).query == ''
        for name in ('text', 'q', 'ingredient', 'tag'):
            expect(form.locator(f'[name="{name}"]')).to_have_value('')
        expect(form.locator('[name="archived"]')).not_to_be_checked()
        form.locator('[name="text"]').fill('Keine passende Rezeptur')
        form.get_by_role('button', name='Suchen', exact=True).press('Enter')
        expect(page.locator('[data-empty-kind="no_match"] .empty-title')).to_have_text('Keine passenden Rezepte')
        expect(form.locator('[name="text"]')).to_have_value('Keine passende Rezeptur')
        expect(page.locator('main .btn-primary')).to_have_count(1)
        app.config['UI_LOCALE'] = 'en'
        assert page.goto(base + '/admin/rezepte').status == 200
        row = page.locator('.recipe-row').first
        _assert_direct_actions(page, row, readonly, 'en', javascript)
        app.config['UI_LOCALE'] = 'de'
        assert not writes and not errors
    assert complete_snapshot(owner) == before
