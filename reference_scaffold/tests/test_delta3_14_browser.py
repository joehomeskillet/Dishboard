"""UI-DELTA: component fields/labels stay visible; filter contract is explicit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_component_catalog_routes import _create_csrf, _create_fields
from test_delta_renderer_browser import VISIBILITY

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/delta3/DELTA-3-14'


@pytest.mark.parametrize('width,coarse', [(1440, False), (1440, True), (390, False), (390, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_component_fields_labels_and_confirmations_remain_native(
    admin_app, admin_engine, browser, live_server, width, coarse, javascript,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with admin_engine.connect() as connection:
        labels = connection.execute(text(
            'SELECT code, display_name AS name FROM cafeteria.dietary_labels WHERE active ORDER BY code LIMIT 3'
        )).all()
    assert len(labels) == 3
    routes = []
    for family in ['cafeteria', 'patienten']:
        fields = _create_fields()
        fields['_csrf'] = _create_csrf(client, family)
        fields['name'] = 'Baustein A&B - 0'
        fields['origin_country_code'] = ''
        fields.setlist('label_code', [row.code for row in labels])
        result = client.post(f'/admin/{family}/komponenten', data=fields)
        assert result.status_code == 303
        routes.extend([(family, 'list', f'/admin/{family}/komponenten'),
                       (family, 'editor', result.headers['Location'])])
    cookie = client.get_cookie(admin_app.config['SESSION_COOKIE_NAME'])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with browser.new_context(base_url=live_server, viewport={'width': width, 'height': 900},
                             has_touch=coarse, java_script_enabled=javascript,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts, errors, rows = [], [], []
        page.on('request', lambda r: posts.append(r.method) if r.method == 'POST' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        for family, kind, route in routes:
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            # D-57 belongs to the protected shared renderer; separate test below.
            disclosures = page.locator('main details:not(.admin-filter-more)').count()
            phase = 'before' if disclosures else 'after'
            stem = f'{phase}-{family}-{kind}-{width}-{"coarse" if coarse else "fine"}-js{javascript}'
            page.screenshot(path=str(EVIDENCE / f'{stem}.png'))
            assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
            rows.append({'route': route, 'disclosures': disclosures})
        (EVIDENCE / f'routes-{width}-{coarse}-js{javascript}.json').write_text(
            json.dumps(rows, ensure_ascii=False, indent=2))
        assert all(row['disclosures'] == 0 for row in rows), rows
        for family, kind, route in routes:
            page.goto(route)
            expect(page.locator('#c-name')).to_be_visible()
            for control in page.locator('main .btn:visible').all():
                visible = control.evaluate(VISIBILITY)
                assert bool(visible['text']) != bool(visible['icons']), visible
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if kind == 'list':
                row = page.locator('.component-row').filter(has_text='Baustein A&B - 0')
                for label in labels:
                    expect(row.get_by_text(label.name, exact=True)).to_be_visible()
                expect(row.locator('.usage')).to_have_text('0 Gerichte')
                expect(row.locator('.component-markers')).to_contain_text('Nicht erfasst')
                expect(page.locator('#create-component summary')).to_have_count(0)
                expect(page.locator('main a[href="#c-name"]')).to_have_count(1)
                page.goto(route + '?q=keine-treffer-delta')
                expect(page.locator('main [data-semantic="view.reset"]')).to_have_count(1)
                expect(page.locator('#component-result-count')).to_contain_text('0 Treffer')
            else:
                expect(page.locator('#c-food')).to_be_visible()
                expect(page.locator('#c-food-extra-hint')).to_be_visible()
                expect(page.get_by_role('heading', name='Wirkung zentraler Änderungen', exact=True)).to_be_visible()
                form = page.locator('#component-form')
                original = form.evaluate('f => [...new FormData(f)]')
                page.locator('#c-name').fill('Ungespeichert A&B - 0')
                current = form.evaluate('f => [...new FormData(f)]')
                assert [(k, v) for k, v in current if k != 'name'] == [
                    (k, v) for k, v in original if k != 'name']
                action = page.locator('#component-status button')
                visible = action.evaluate(VISIBILITY)
                assert visible['text'] == 'Archivieren' and not visible['icons'], visible
                if javascript:
                    page.once('dialog', lambda dialog: dialog.dismiss())
                    action.click()
                    expect(page.locator('main')).to_have_attribute('data-active', '1')
                expect(page.locator('#c-name')).to_have_value('Ungespeichert A&B - 0')
        assert not posts and not errors


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('width', [1440, 390])
def test_component_error_and_result_count_follow_stable_profile_navigation(
    admin_app, admin_engine, browser, live_server, family, width,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(admin_app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(base_url=live_server, viewport={'width': width, 'height': 900}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        route = f'/admin/{family}/komponenten'
        page.goto(route)
        tabs = page.locator('.profile-tabs')
        geometry = 'e => {const b=e.getBoundingClientRect(); return [b.x,b.y+scrollY,b.width,b.height]}'
        before = tabs.evaluate(geometry)
        form = page.locator('#component-form')
        csrf = form.locator('[name="_csrf"]').input_value()
        form.locator('[name="name"]').fill('   ')
        form.locator('[name="category"]').select_option('side')
        with page.expect_response(lambda r: r.request.method == 'POST') as failed:
            form.get_by_role('button', name='Anlegen', exact=True).click()
        assert failed.value.status == 400
        after = tabs.evaluate(geometry)
        assert max(abs(a - b) for a, b in zip(after, before, strict=True)) <= 1
        alert = page.locator('.error-region')
        expect(alert).to_be_focused()
        assert alert.evaluate(geometry)[1] >= after[1] + after[3]
        expect(form.locator('[name="_csrf"]')).to_have_value(csrf)
        expect(form.locator('[name="category"]')).to_have_value('side')
        positions = []
        for status in ['active', 'all']:
            page.goto(route + '?q=unmatched&status=' + status)
            positions.append(tabs.evaluate(geometry))
            count = page.locator('#component-result-count')
            expect(count).to_contain_text('0 Treffer')
            assert count.evaluate(geometry)[1] >= positions[-1][1] + positions[-1][3]
        assert max(abs(a - b) for a, b in zip(*positions, strict=True)) <= 1, positions


def test_component_filter_has_no_content_disclosure(
    admin_app, admin_engine, browser, live_server,  # noqa: F811
):
    """D-57 stays red until shared filter_bar_sem supplies its promised replacement."""
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(admin_app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(base_url=live_server) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        assert page.goto('/admin/cafeteria/komponenten').status == 200
        expect(page.locator('main .admin-filter-more')).to_have_count(0)
