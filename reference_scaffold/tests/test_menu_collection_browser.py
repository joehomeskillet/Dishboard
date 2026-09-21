from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit
import json

import pytest
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text

from cafeteria.workflow_review import get_component_review_token, review_component
from cafeteria.workflow_partial_store import persist_menu_item

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine, browser as browser,
    live_server as live_server, page_context as page_context,
)
from test_admin_workflow_routes import WEEK, _login, _payload
from test_menu_collection import _save, _scope
from test_branding_browser import live_branding as live_branding
from test_admin_workflow_routes import app as workflow_app, database_engine as database_engine  # noqa: F401


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_wp04_reference_post_and_density(live_branding, database_engine, tmp_path, family, profile, javascript):
    """Real POST baseline, including ordered repeated fields; never record CSRF."""
    origin, _, client, _, _ = live_branding
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(
        allergens=[{'code': 'MILK', 'presence': 'may_contain'}, {'code': 'GLUTEN', 'presence': 'contains'}],
        origins=[{'ingredient': 'Rind', 'country_code': 'CH', 'text': 'Rind: CH'},
                 {'ingredient': 'Reis', 'country_code': 'IT', 'text': 'Reis: IT'}],
        assignments=[{'component_public_id': None, 'component_text': 'Kartoffeln'}],
    )
    _save(database_engine, _scope(client, database_engine, profile), title='Referenzmenü', payload=payload)
    with sync_playwright() as playwright:
        with playwright.chromium.launch(args=['--no-sandbox']) as chromium:
            with chromium.new_context(java_script_enabled=javascript, reduced_motion='reduce') as context:
                context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': origin}])
                page = context.new_page()
                metrics = []
                for width in (360, 768, 1024, 1440):
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.goto(f'{origin}/admin/{family}/menues')
                    row_height = page.locator('[data-menu-list-id]').first.bounding_box()['height']
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    expect(page.locator('main .btn-primary')).to_have_count(1)
                    expect(page.locator('.admin-statusbar')).to_contain_text('Cafeteria' if family == 'cafeteria' else 'Patienten')
                    expect(page.locator('#menu-list [data-review] .badge')).to_have_count(1)
                    assert row_height < (284 if width < 1440 else 86)
                    page.screenshot(path=str(tmp_path / f'list-{width}.png'), full_page=True)
                    page.locator('#menu-list [data-admin-icon-action]').first.click()
                    for section in ('allergen', 'origin'):
                        details = page.locator(f'details[data-mode-section="{section}"]')
                        if details.get_attribute('open') is None:
                            details.locator('summary').click()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    expect(page.locator('main .btn-primary')).to_have_count(1)
                    expect(page.locator('.admin-statusbar')).to_contain_text('Profil')
                    expect(page.locator('[data-option-group]')).to_contain_text('Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.')
                    expect(page.locator('[data-review-scope="persisted"]')).to_be_visible()
                    for control in page.locator('[data-option-presence]:disabled').all():
                        expect(control).to_be_hidden()
                    metrics.append({'width': width, 'row': round(row_height, 2),
                                    'allergens': round(page.locator('.allergen-list').bounding_box()['height'], 2),
                                    'origins': round(page.locator('#origins-list').bounding_box()['height'], 2)})
                    page.screenshot(path=str(tmp_path / f'editor-{width}.png'), full_page=True)
                page.locator('#f-title').focus()
                page.keyboard.press('Tab')
                expect(page.locator('#accompaniment-none')).to_be_focused()
                assert page.locator('#accompaniment-none').evaluate('e => getComputedStyle(e).outlineStyle !== "none"')
                csrf = page.locator('form[data-menu-editor] [name="_csrf"]').input_value()
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/menu')) as posted:
                    page.get_by_role('button', name='Menü speichern', exact=True).click()
                assert posted.value.status == 303
                fields = parse_qsl(posted.value.request.post_data, keep_blank_values=True)
                assert dict(fields)['_csrf'] == csrf
                sanitized = [(key, value) for key, value in fields if key != '_csrf']
                # Captured on unmodified 9af1334d, for JS and No-JS in both profiles.
                expected = {
                    'week': ['2026-08-31'], 'day': ['2026-08-31'], 'meal': ['LUNCH'],
                    'option': ['MENU_1'], 'row_version': ['1'], 'dish_template_public_id': [''],
                    'title': ['Referenzmenü'], 'accompaniment': ['none'], 'description': [''], 'note': [''],
                    'allergen_mode': ['manual'], 'allergen_code': ['GLUTEN', 'MILK'],
                    'origin_mode': ['manual'],
                    'label_mode': ['manual'], 'component_public_id': [''], 'component_text': ['Kartoffeln'],
                    'recipe_revision_public_id': [''], 'target_quantity': [''], 'target_quantity_unit_code': [''],
                    'origin_ingredient': ['Reis', 'Rind'], 'origin_country_code': ['IT', 'CH'],
                }
                if profile == 'staff_guest':
                    expected.update(internal_chf=['9.50'], external_chf=['14.50'])
                actual = {}
                for key, value in sanitized:
                    actual.setdefault(key, []).append(value)
                presence_fields = {key: value for key, value in actual.items() if key.startswith('allergen_presence__')}
                assert presence_fields['allergen_presence__GLUTEN'] == ['contains']
                assert presence_fields['allergen_presence__MILK'] == ['may_contain']
                expected.update(presence_fields)
                assert actual == expected
                print('WP04_REFERENCE', family, javascript, json.dumps(sanitized, ensure_ascii=False))
                print('WP04_METRICS', family, javascript, json.dumps(metrics), str(tmp_path))
                page.wait_for_load_state()
                saved_review = page.locator('#review').inner_text()
                for code, selected in [('MILK', False), ('LUPIN', True), ('GLUTEN', False), ('GLUTEN', True)]:
                    page.locator(f'[name="allergen_code"][value="{code}"]').set_checked(selected)
                page.locator('#allergen-lupin-presence').select_option('may_contain')
                expect(page.locator('#allergen-milk-presence')).to_be_enabled()
                expect(page.locator('#review')).to_have_text(saved_review)
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/menu')) as changed:
                    page.get_by_role('button', name='Menü speichern', exact=True).click()
                submitted = parse_qs(changed.value.request.post_data, keep_blank_values=True)
                assert submitted['allergen_code'] == ['GLUTEN', 'LUPIN']
                assert changed.value.status == 303
                assert [(code, submitted[f'allergen_presence__{code}'][0]) for code in submitted['allergen_code']] == [
                    ('GLUTEN', 'contains'), ('LUPIN', 'may_contain'),
                ]
                page.wait_for_load_state()
                page.reload()
                assert page.locator('[name="allergen_code"]:checked').evaluate_all('(els) => els.map(e => e.value)') == ['GLUTEN', 'LUPIN']
                expect(page.locator('#allergen-gluten-presence')).to_have_value('contains')
                expect(page.locator('#allergen-lupin-presence')).to_have_value('may_contain')
                next_version = 3

                def invalid_presence(route):
                    fields = parse_qsl(route.request.post_data, keep_blank_values=True)
                    route.continue_(post_data=urlencode([
                        (key, 'invalid' if key == 'allergen_presence__GLUTEN' else value)
                        for key, value in fields]))

                page.route('**/menu', invalid_presence, times=1)
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/menu')) as invalid:
                    page.get_by_role('button', name='Menü speichern', exact=True).click()
                assert invalid.value.status == 400
                presence = page.locator('#allergen-gluten-presence')
                expect(presence).to_have_value('invalid')
                expect(presence).to_have_attribute('aria-invalid', 'true')
                expect(presence).to_have_attribute('aria-describedby', 'allergen-gluten-error')
                expect(page.locator('#allergen-gluten-error')).to_contain_text('ungültig')
                expect(page.locator('#allergen-lupin-presence')).to_have_value('may_contain')
                payload.update(allergen_mode='auto', allergens=[])
                persist_menu_item(database_engine, _scope(client, database_engine, profile), WEEK,
                                  WEEK.isoformat(), 'LUNCH', 'MENU_1', payload, next_version)
                page.goto(f'{origin}/admin/{family}/menu?week={WEEK}&day={WEEK}&meal=LUNCH&option=MENU_1')
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/menu')) as automatic:
                    page.get_by_role('button', name='Menü speichern', exact=True).click()
                auto_fields = parse_qs(automatic.value.request.post_data, keep_blank_values=True)
                assert automatic.value.status == 303
                assert auto_fields['allergen_mode'] == ['auto']
                assert 'allergen_code' not in auto_fields and 'allergen_presence' not in auto_fields
                assert not any(key.startswith('allergen_presence__') for key in auto_fields)
                print('WP04_AUTO', family, javascript, automatic.value.status, 'no allergen fields')


def test_collection_navigation_search_and_mobile_layout(page_context, admin_app, admin_engine):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(client, admin_engine)
    payload = _payload()
    payload['description'] = 'Zubereitung mit Kartoffeln und frischen Kräutern. ' * 5
    _save(admin_engine, scope, title='Kartoffelgratin mit Gemüse', payload=payload)
    _save(admin_engine, scope, week=WEEK + timedelta(days=7), title='Tomatensuppe')
    page = page_context
    page.goto('/admin/patienten')
    page.get_by_role('navigation', name='Backend').locator('.nav-link-title', has_text='Menüs').click()
    expect(page.get_by_role('heading', name='Menüs', exact=True)).to_be_visible()
    expect(page.locator('[data-menu-id]')).to_have_count(2)
    for width, height in [(390, 844), (1440, 1100), (2560, 1440)]:
        page.set_viewport_size({'width': width, 'height': height})
        assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
        expect(page.locator('#menu-list')).to_be_visible()
        assert page.locator('[data-menu-list-id]').first.bounding_box()['width'] >= 250
    page.get_by_label('Suche').fill('Kartoffelgratin')
    page.get_by_role('button', name='Filtern', exact=True).click()
    expect(page.locator('[data-menu-id]')).to_have_count(1)
    page.get_by_role('link', name='Kartoffelgratin mit Gemüse vom 31.08.2026 bearbeiten').click()
    assert '/admin/patienten/menu?' in page.url
    expect(page.locator('input[name="title"]')).to_have_value('Kartoffelgratin mit Gemüse')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 1100)])
def test_icon_actions_use_tabler_tooltips_under_real_csp(
    live_branding, database_engine, browser, family, profile, width, height, tmp_path,
):
    origin, _, client, _, _ = live_branding
    _save(database_engine, _scope(client, database_engine, profile), title='Kartoffelgratin mit Gemüse')
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': origin}])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        response = page.goto(origin + f'/admin/{family}/menues')
        assert response.status == 200
        assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        for view in ('cards', 'list'):
            page.get_by_role('tab', name='Karten' if view == 'cards' else 'Liste', exact=True).click()
            link = page.locator(f'#menu-{view} [data-admin-icon-action]').first
            expect(link).to_have_attribute('aria-label', 'Kartoffelgratin mit Gemüse vom 31.08.2026 bearbeiten')
            assert link.inner_text() == 'Bearbeiten'
            expect(link.locator('use')).to_have_attribute('href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-pencil')
            assert link.evaluate('element => Boolean(window.tabler.Tooltip.getInstance(element))')
            link.hover()
            tooltip = page.get_by_role('tooltip')
            expect(tooltip).to_be_visible()
            expect(tooltip).to_have_text('Kartoffelgratin mit Gemüse vom 31.08.2026 bearbeiten')
            tooltip.hover()
            page.wait_for_timeout(150)  # Longer than Tabler's 50 ms hide delay.
            expect(tooltip).to_be_visible()
            page.mouse.move(0, 0)
            expect(tooltip).to_have_count(0)
            link.focus()
            page.keyboard.press('Shift+Tab')
            page.keyboard.press('Tab')
            expect(link).to_be_focused()
            expect(tooltip).to_be_visible()
            assert link.evaluate('element => getComputedStyle(element).outlineStyle !== "none"')
            assert link.get_attribute('aria-describedby') == tooltip.get_attribute('id')
            for target in (link, tooltip):
                box = target.bounding_box()
                assert box and box['x'] >= 0 and box['y'] >= 0
                assert box['x'] + box['width'] <= width + 1
                assert box['y'] + box['height'] <= height + 1
            box = link.bounding_box()
            assert box['width'] >= 48 and box['height'] >= 48
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
            page.screenshot(path=str(tmp_path / f'{family}-{view}-tooltip-{width}.png'), full_page=True)
            page.keyboard.press('Escape')
            expect(tooltip).to_have_count(0)
            expect(link).to_be_focused()
            assert link.get_attribute('aria-describedby') is None
        assert errors == []


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False])
def test_icon_help_and_first_tap_work_with_and_without_javascript(
    live_branding, database_engine, browser, family, profile, javascript,
):
    origin, _, client, _, _ = live_branding
    _save(database_engine, _scope(client, database_engine, profile), title='Kartoffelgratin mit Gemüse')
    with browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True,
                             is_mobile=True, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': origin}])
        page = context.new_page()
        page.goto(origin + f'/admin/{family}/menues')
        link = page.locator('#menu-list [data-admin-icon-action]').first
        destination = link.get_attribute('href')
        link.tap()
        page.wait_for_url(origin + destination)
        expect(page.locator('input[name="title"]')).to_have_value('Kartoffelgratin mit Gemüse')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 1100)])
def test_collection_card_list_switch_keeps_scope_search_and_editor_targets(
    page_context, admin_app, admin_engine, family, profile, width, height, tmp_path,
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(client, admin_engine, profile)
    _save(admin_engine, scope, title='Kartoffelgratin mit Gemüse')
    reviewed_payload = _payload(staff=profile == 'staff_guest')
    reviewed_payload['allergens'] = [{'code': 'GLUTEN', 'presence': 'contains'}]
    _save(admin_engine, scope, week=WEEK + timedelta(days=7), title='Tomatensuppe', payload=reviewed_payload)
    with admin_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))
        reviewed = connection.execute(text(
            "SELECT id,row_version FROM cafeteria.menu_items WHERE title='Tomatensuppe'"
        )).one()
    review_component(admin_engine, scope, reviewed.id,
                     get_component_review_token(admin_engine, scope, reviewed.id), reviewed.row_version)
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(f'/admin/{family}/menues')
    cards, listing = page.get_by_role('tab', name='Karten', exact=True), page.get_by_role('tab', name='Liste', exact=True)
    expect(listing).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-list')).to_be_visible()
    expect(page.locator('#menu-cards')).to_be_hidden()
    cards.click()
    expect(cards).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-cards')).to_be_visible()
    expect(page.locator('#menu-list')).to_be_hidden()
    expect(page.locator('#menu-cards [data-menu-id]').filter(has_text='Kartoffelgratin').locator('[data-review]')).to_have_attribute('data-review', 'open')
    expect(page.locator('#menu-cards [data-menu-id]').filter(has_text='Tomatensuppe').locator('[data-review]')).to_have_attribute('data-review', 'checked')
    list_url = page.url
    listing.click()
    expect(listing).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-cards')).to_be_hidden()
    expect(page.locator('#menu-list')).to_be_visible()
    assert page.url == list_url
    rows = page.locator('#menu-list tbody tr')
    expect(rows).to_have_count(2)
    expect(rows.filter(has_text='Kartoffelgratin')).to_contain_text('Prüfung offen')
    expect(rows.filter(has_text='Tomatensuppe')).to_contain_text('Geprüft')
    for row in rows.all():
        expect(row).to_contain_text('Mittag')
        expect(row).to_contain_text('Menü 1')
        link = row.get_by_role('link')
        destination = urlsplit(link.get_attribute('href'))
        assert destination.path == f'/admin/{family}/menu'
        fields = parse_qs(destination.query)
        assert set(fields) == {'week', 'day', 'meal', 'option'}
        assert fields['week'] == fields['day']
        assert fields['meal'] == ['LUNCH'] and fields['option'] == ['MENU_1']
        assert link.bounding_box()['height'] >= 48
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
    assert not page.locator('#menu-list img').count()
    if family == 'patienten':
        assert not any(word in page.content().lower() for word in ('price', 'rappen', 'chf'))
    page.screenshot(path=str(tmp_path / f'{family}-list-{width}.png'), full_page=True)
    listing.focus()
    page.keyboard.press('ArrowRight')
    expect(cards).to_be_focused()
    expect(cards).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-cards')).to_be_visible()
    page.get_by_label('Suche').fill('Kartoffelgratin')
    page.get_by_role('button', name='Filtern', exact=True).click()
    assert parse_qs(urlsplit(page.url).query) == {'q': ['Kartoffelgratin']}
    listing.click()
    expect(rows).to_have_count(1)
    rows.get_by_role('link').click()
    expect(page.locator('input[name="title"]')).to_have_value('Kartoffelgratin mit Gemüse')
