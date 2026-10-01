"""UI-DELTA master lists and vocabulary, preserving native errors and read permissions."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect
from sqlalchemy.exc import SQLAlchemyError

from cafeteria import roles
from test_delta_renderer_browser import VISIBILITY
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, create, installed_pg16, pg16, seeded_pg16,
)
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_master_list_vocabulary_delta(b3, master_server, browser, monkeypatch, tmp_path,  # noqa: F811
                                      width, height, touch, javascript):
    _, _, client, _ = b3
    base, cookie = master_server
    failures = []
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()

        def capture(label, *, listing=False):
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            # D-80 is a central filter contract gap, intentionally left in place.
            if not listing and page.locator('main details, main summary').count():
                failures.append(label + ': content accordion')
            for control in page.locator('main .ui-sem-control:visible, nav[aria-label="Stammdatenbereiche"] a').all():
                rendered = control.evaluate(VISIBILITY)
                if rendered['pseudos'] or not (
                    rendered['icons'] == 1 and not rendered['text'] or
                    rendered['icons'] == 0 and bool(rendered['text'])
                ):
                    failures.append((label, rendered))

        def visit(path, label, *, listing=False):
            assert page.goto(base + path).status == 200
            capture(label, listing=listing)

        visit('/admin/grundlagen', 'empty-foods', listing=True)
        if page.locator('main a[href="/admin/grundlagen/zutaten/neu"]').count() != 1:
            failures.append('R-11: duplicate create entry')
        for kind in ('units', 'categories', 'tags', 'storage_locations'):
            visit('/admin/grundlagen?kind=' + kind, 'list-' + kind, listing=True)
            expect(page.locator('.grundlagen-list .admin-list-status')).to_have_count(0)
        visit('/admin/grundlagen?q=KeinTreffer', 'empty-filter', listing=True)
        # Active navigation has a different purpose; only explicit reset actions are counted.
        if page.locator('main a[data-semantic="view.reset"]').count() != 1:
            failures.append('R-71: duplicate empty reset')

        unit = create(client, 'einheiten', display_name='Kontexteinheit', code='DELTAUNIT',
                      dimension='contextual', base_factor='')
        vocabulary = create(client, 'lagerorte', name='Nebenlager', code='DELTASTORE', sort_order='2')
        visit('/admin/grundlagen/einheiten/neu', 'unit-new')
        expect(page.locator('#base_factor')).to_have_attribute('name', 'base_factor')
        visit('/admin/grundlagen/lagerorte/neu', 'vocabulary-new')
        expect(page.locator('#sort_order')).to_have_attribute('name', 'sort_order')
        for path, label in ((unit, 'unit'), (vocabulary, 'vocabulary')):
            visit(path, label)
            for form in page.locator('main form[method="post"]').all():
                expect(form.locator('[name="_csrf"]')).to_have_value('b3-test-csrf')
                expect(form.locator('[name="_form_context"]')).to_have_count(1)
                expect(form.locator('[name="row_version"]')).to_have_count(1)
            if not page.locator('#master-status').is_visible():
                failures.append(label + ': status form hidden')
            if label == 'unit' and not page.get_by_text('Kontextabhängig', exact=True).is_visible():
                failures.append('D-88: unit technical context hidden')

        visit(unit, 'unit-before-error')
        name_form = page.locator('form[action$="/name"]')
        version = name_form.locator('[name="row_version"]').input_value()
        token = name_form.locator('[name="_form_context"]').input_value()
        page.locator('#display_name').fill(' ')
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            name_form.get_by_role('button').click()
        assert rejected.value.status == 400
        expect(page.locator('#master-error')).to_be_visible()
        expect(name_form.locator('[name="row_version"]')).to_have_value(version)
        expect(name_form.locator('[name="_form_context"]')).to_have_value(token)
        capture('unit-error')
        recovery = page.locator('#master-error a')
        if recovery.evaluate(VISIBILITY)['icons']:
            failures.append('B-30: recovery must be text')

        with monkeypatch.context() as read_only:
            read_only.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
            for path, label in ((unit, 'unit-readonly'), (vocabulary, 'vocabulary-readonly')):
                visit(path, label)
                expect(page.locator('main form[method="post"]')).to_have_count(0)

        def unavailable(*args, **kwargs):
            raise SQLAlchemyError('private service detail')

        monkeypatch.setattr(roles, 'load_user_authorization', unavailable)
        response = page.goto(base + '/admin/grundlagen')
        assert response.status == 503
        assert response.headers['cache-control'] == 'no-store'
        expect(page.locator('main')).not_to_contain_text('private service detail')
        capture('unavailable')
        retry = page.locator('main a[data-semantic="actions.retry"]')
        expect(retry).to_have_attribute('href', '/admin/grundlagen')
        if retry.evaluate(VISIBILITY)['icons']:
            failures.append('B-25: unavailable retry must be text')
    assert not failures, failures
