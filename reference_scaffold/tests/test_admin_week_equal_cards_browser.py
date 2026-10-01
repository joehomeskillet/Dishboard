from __future__ import annotations

from datetime import date, timedelta
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, url_for
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from cafeteria.menu_images import CATALOG
from test_admin_screens_preview_browser import _capture_card_visuals

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family,profile,total', [
    ('cafeteria', 'staff_guest', 2), ('patienten', 'patient', 4),
])
@pytest.mark.parametrize('width,height,touch', [
    (1440, 900, False), (1440, 900, True), (390, 844, False), (390, 844, True),
])
@pytest.mark.parametrize('javascript', [True, False])
def test_week_patterns_keep_empty_and_filled_slots_actionable(
    browser, live_server, admin_app, admin_engine, tmp_path,  # noqa: F811
    family, profile, total, width, height, touch, javascript,
):
    """Both profiles keep the day context and right-aligned planning actions."""
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    evidence = Path(os.environ.get('UC_WEEK_EVIDENCE_DIR', tmp_path))
    evidence.mkdir(parents=True, exist_ok=True)
    name = f'{family}-{width}-{"coarse" if touch else "fine"}-js{int(javascript)}'
    metrics = {}
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, java_script_enabled=javascript, reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        for state in ('empty', 'filled'):
            if state == 'filled':
                _save(admin_engine, profile, _staff_values() if total == 2 else _patient_values())
            assert page.goto(f'/admin/{family}?week={DAY}').status == 200
            assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") is touch
            page.evaluate('document.fonts.ready')
            metrics[state] = page.evaluate('''() => {
                const day = document.querySelector('.admin-day-card, .patient-admin-day');
                const box = element => {
                    const r = element.getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height, right: r.right};
                };
                return {
                    coarse: matchMedia('(pointer: coarse), (any-pointer: coarse)').matches,
                    overflow: document.documentElement.scrollWidth > innerWidth + 1,
                    day: box(day), head: box(day.querySelector('.admin-week-day-head')),
                    empty: !!document.querySelector('.empty--compact'),
                    slots: [...day.querySelectorAll('.menu-slot')].map(box),
                    actions: [...day.querySelectorAll('.admin-week-card-action')].map(box),
                    courses: [...day.querySelectorAll('.admin-week-course-line')].map(element => ({
                        line: box(element), action: box(element.querySelector('a')),
                    })),
                };
            }''')
            page.screenshot(path=str(evidence / f'{name}-{state}.png'))
            page.locator('.admin-day-card, .patient-admin-day').first.scroll_into_view_if_needed()
            page.screenshot(path=str(evidence / f'{name}-{state}-day.png'))
            assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") is touch
        editor_url = page.locator('.admin-week-card-action a').first.get_attribute('href')
        # UI-DELTA replaces week/service disclosures with always visible fields.
        for section in ('settings', 'service', 'course-editor', 'check-entries'):
            details = page.locator(f'.admin-week-{section}').first
            summary = details.locator(':scope > summary')
            static = section in ('settings', 'service')
            if static:
                expect(summary).to_have_count(0)
                expect(details.locator('input:not([type="hidden"])').first).to_be_visible()
            else:
                summary.focus()
                page.keyboard.press('Enter')
                expect(details).to_have_attribute('open', '')
            metrics[section] = details.evaluate('''element => {
                const rect = element.getBoundingClientRect();
                const heading = element.querySelector('summary, h2, .form-label');
                const style = getComputedStyle(heading);
                return {height: rect.height, width: rect.width,
                    summaryHeight: heading.getBoundingClientRect().height,
                    summaryGap: style.gap, summaryPadding: style.padding,
                    overflow: document.documentElement.scrollWidth > innerWidth + 1};
            }''')
            assert not metrics[section]['overflow'], metrics[section]
            details.scroll_into_view_if_needed()
            page.screenshot(path=str(evidence / f'{name}-{section}-open.png'))
            save = details.locator('form[method="post"] [data-semantic="actions.save"]')
            if section != 'check-entries':
                expect(save).to_have_count(1)
                save.scroll_into_view_if_needed()
                page.screenshot(path=str(evidence / f'{name}-{section}-footer.png'))
            if not static:
                summary.focus()
                page.keyboard.press('Space')
                expect(details).not_to_have_attribute('open', '')
        if not javascript:
            fallback = page.locator('.admin-week-nojs-publish')
            expect(fallback.locator('summary')).to_have_count(0)
            expect(fallback).to_be_visible()
            expect(fallback.locator('button')).to_have_attribute('form', 'week-publish-form')
            page.screenshot(path=str(evidence / f'{name}-publish-open.png'))
        with admin_app.test_request_context():
            event_url = url_for('admin.kitchen_event_new', date=DAY)
        # Same fixture and viewport also document the neighbouring G0 migrations.
        for route_name, route in (
            ('weeks', f'/admin/{family}/wochen'),
            ('review', f'/admin/{family}/wochen/pruefung?week={DAY}'),
            ('calendar', '/admin/kuechenkalender?jump=2026-09'),
            ('event', event_url),
            ('menu', editor_url),
        ):
            assert page.goto(route).status == 200
            assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") is touch
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(evidence / f'{name}-{route_name}.png'))
            if route_name == 'menu':
                footer = page.locator('form[data-menu-editor] .admin-actions[data-sticky]')
                actions = footer.locator('button, a')
                expect(actions).to_have_count(3)
                expect(actions.nth(0)).to_have_attribute('data-semantic', 'actions.save')
                expect(actions.nth(1)).to_have_attribute('formaction', f'/admin/{family}/menu?return_to=week')
                expect(actions.nth(2)).to_have_attribute('data-semantic', 'actions.cancel')
                footer.scroll_into_view_if_needed()
                metrics['menu-footer'] = footer.evaluate('''element => ({
                    height: element.getBoundingClientRect().height,
                    width: element.getBoundingClientRect().width,
                    overflow: document.documentElement.scrollWidth > innerWidth + 1,
                })''')
                assert not metrics['menu-footer']['overflow'], metrics['menu-footer']
                page.screenshot(path=str(evidence / f'{name}-menu-footer.png'))
            assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") is touch
        (evidence / f'{name}-metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        assert metrics['empty']['empty'], 'Both profiles need the compact first-slot empty state'
        for state_metrics in (metrics['empty'], metrics['filled']):
            assert not state_metrics['overflow'], state_metrics
            for index, course in enumerate(state_metrics['courses']):
                assert abs(course['line']['right'] - course['action']['right']) <= 1, course
                menu_actions = state_metrics['actions'][index]
                assert abs(course['action']['right'] - menu_actions['right']) <= 1, (course, menu_actions)
        day = page.locator('article.admin-day-card').first
        expect(day.locator('.admin-week-day-count')).to_have_text(f'{total} von {total} Menükarten erfasst')
        expect(day.locator('.menu-slot')).to_have_count(total)
        expect(day.locator('[data-semantic="status.unsaved"]')).to_have_count(0)
        first_action = day.locator('.admin-week-card-action a').first
        expect(first_action).to_be_visible()
        href = first_action.get_attribute('href')
        first_action.focus()
        page.keyboard.press('Enter')
        expect(page).to_have_url(live_server + href)
        expect(page.locator('form input[name="row_version"]')).not_to_have_count(0)


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844), (320, 844)])
@pytest.mark.parametrize('javascript', [True, False])
def test_card_visuals_cafeteria_exact_image_and_fallback(
    browser, live_server, admin_app, admin_engine, width, height, javascript,  # noqa: F811
) -> None:
    image = next(row for row in json.loads(CATALOG.read_text()) if row['status'] == 'ready')
    values = _staff_values()
    options = values['days'][0]['services'][0]['options']
    options[0].update(title=image['title'], components=image['components'])
    options[1].update(title=image['title'], components=[*image['components'], 'Abweichende Beilage'])
    _save(admin_engine, 'staff_guest', values)
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    with browser.new_context(base_url=live_server, viewport={'width': width, 'height': height},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        assert page.goto(f'/admin/cafeteria?week={DAY}').status == 200
        _capture_card_visuals(page, f'cafeteria-{width}-{javascript}')
        card = page.locator('.menu-slot').first
        photo = card.locator('[data-menu-image] img')
        expect(photo).to_be_visible()
        assert photo.get_attribute('src') == '/static/' + image['file']
        assert page.request.get(photo.get_attribute('src')).status == 200
        assert photo.get_attribute('loading') == 'lazy'
        assert photo.evaluate('el => el.complete && el.naturalWidth > 0')
        assert photo.evaluate('el => getComputedStyle(el).objectFit') == 'cover'
        box = photo.bounding_box()
        assert 0 < box['width'] <= 96 and box['height'] <= 96 and abs(box['width'] / box['height'] - 16 / 9) < .01, box
        expect(card.locator('figcaption')).to_have_text('KI-generierter Serviervorschlag')
        missing = page.locator('.menu-slot').nth(1)
        expect(missing.locator('[data-menu-image] img')).to_have_count(0)
        expect(missing.get_by_text('Kein passendes Menübild', exact=True)).to_be_visible()
        expect(card).to_contain_text('Mitarbeitende CHF')
        expect(card).to_contain_text('Externe CHF')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        edit = card.get_by_role(
            'link',
            name=f'Montag, 31. August, Mittag, Menü 1 – {image["title"]} bearbeiten',
            exact=True,
        )
        assert card.locator('h3').bounding_box()['y'] >= card.bounding_box()['y']
        assert edit.bounding_box()['y'] + edit.bounding_box()['height'] <= card.bounding_box()['y'] + card.bounding_box()['height']
        if width < 768:
            later = page.locator('.menu-slot').nth(2).bounding_box()
            assert later['height'] <= card.bounding_box()['height'] + 1
        href = edit.get_attribute('href')
        edit.focus()
        page.keyboard.press('Enter')
        expect(page).to_have_url(live_server + href)
        expect(page.get_by_label('Menüname', exact=True)).to_have_value(image['title'])
        assert page.goto(f'/admin/patienten?week={DAY}').status == 200
        expect(page.locator('[data-menu-image]')).to_have_count(0)


def _assert_edit_link_context(page: Page, family: str, titles: list[str]) -> None:
    day_labels = (
        'Montag, 31. August', 'Dienstag, 1. September', 'Mittwoch, 2. September',
        'Donnerstag, 3. September', 'Freitag, 4. September', 'Samstag, 5. September',
        'Sonntag, 6. September',
    )
    per_day = 2 if family == 'cafeteria' else 4
    links = page.locator('.menu-slot').get_by_role('link')
    assert links.count() == len(titles) == (10 if family == 'cafeteria' else 28)
    for index, title in enumerate(titles):
        day_index, slot = divmod(index, per_day)
        meal, meal_label = ('LUNCH', 'Mittag') if slot < 2 else ('DINNER', 'Abend')
        option, option_label = ('MENU_1', 'Menü 1') if slot % 2 == 0 else ('VEGGIE', 'Vegetarisch')
        verb = 'anlegen' if title == 'Noch kein Gericht' else 'bearbeiten'
        name = f'{day_labels[day_index]}, {meal_label}, {option_label} – {title} {verb}'
        link = page.get_by_role('link', name=name, exact=True)
        expect(link).to_have_count(1)
        expect(link).to_have_attribute('data-semantic', 'actions.add' if title == 'Noch kein Gericht' else 'actions.edit')
        target = urlsplit(link.get_attribute('href') or '')
        assert target.path == f'/admin/{family}/menu'
        assert parse_qs(target.query) == {
            'week': [DAY], 'day': [(date.fromisoformat(DAY) + timedelta(days=day_index)).isoformat()],
            'meal': [meal], 'option': [option],
        }


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_all_week_editor_cards_share_size_without_hiding_long_content(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    options = [option for day in values['days'] for service in day['services'] for option in service['options']]
    # The longest option is on Friday/Sunday evening, after every earlier row and meal.
    options[-1]['components'] = ['Reis', 'Zucchetti', 'Frisch zubereitet mit saisonalem Gemüse. ' * 5]
    options[-1]['note'] = 'Vollständiger langer Rezepturhinweis bleibt sichtbar. ' * 8
    options[-1]['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    options[-1]['allergen_review_status'] = 'not_checked'
    cookie = client.get_cookie('session')
    assert cookie is not None
    with browser.new_context(base_url=live_server, java_script_enabled=False) as context:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
        page = context.new_page()
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        _assert_edit_link_context(page, family, ['Noch kein Gericht'] * len(options))
        _save(admin_app.extensions['cafeteria_db'], profile, values)
        for width, height in [(390, 844), (768, 1024), (1024, 768), (1440, 1100)]:
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(f'/admin/{family}?week={DAY}')
            assert response is not None and response.status == 200
            page.evaluate('document.fonts.ready')
            cards = page.locator('.menu-slot')
            assert cards.locator('h3').all_text_contents() == [option['title'] for option in options]
            for component in options[-1]['components']:
                assert component.strip() in cards.last.inner_text()
            assert options[-1]['note'].strip() in (cards.last.text_content() or '')
            assert 'Enthält: Milch' in cards.last.inner_text()
            dimensions = cards.evaluate_all('''elements => elements.map(element => {
                const box = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return {meal: element.dataset.meal, y: box.y, height: box.height, width: box.width,
                    overflowY: style.overflowY, overflowX: style.overflowX,
                    clientHeight: element.clientHeight, scrollHeight: element.scrollHeight,
                    clientWidth: element.clientWidth, scrollWidth: element.scrollWidth};
            })''')
            assert len(dimensions) == (10 if profile == 'staff_guest' else 28)
            rows: dict[tuple[int, str], list] = {}
            for item in dimensions:
                # M27: equal options within a meal; a long dinner must not stretch lunch.
                rows.setdefault((round(item['y']), item['meal']), []).append(item)
            for row in rows.values():
                heights = [item['height'] for item in row]
                assert max(heights) - min(heights) <= 1, (family, width, 'height', heights)
            widths = [item['width'] for item in dimensions]
            assert max(widths) - min(widths) <= 1, (family, width, 'width', widths)
            assert all(item['scrollHeight'] <= item['clientHeight'] + 1 for item in dimensions)
            assert all(item['scrollWidth'] <= item['clientWidth'] + 1 for item in dimensions)
            assert all(item['overflowY'] != 'hidden' and item['overflowX'] != 'hidden' for item in dimensions)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert page.locator('[style], [onclick], script:not([src])').count() == 0
            _assert_edit_link_context(page, family, [option['title'] for option in options])
            expect(page.locator('details.admin-week-service')).to_have_count(0)
            controls = page.locator(
                '.admin-week-service :is(input:not([type="hidden"]), select, button), '
                '.patient-admin-meal form :is(input:not([type="hidden"]), select, button):visible, .menu-slot .btn',
            )
            for control in controls.all():
                box = control.bounding_box()
                assert box is not None
                if control.evaluate("el => el.matches('.ui-sem-control--icon-only')"):
                    assert box['width'] == box['height'] == 36
                else:
                    minimum = control.evaluate("e => parseFloat(getComputedStyle(e).getPropertyValue('--app-control-min-height'))")
                    assert box['width'] >= minimum and box['height'] >= minimum
            page.locator('.admin-day-card, .patient-admin-day').last.screenshot(
                path=str(tmp_path / f'{family}-equal-cards-{width}.png'),
            )
