from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from cafeteria.menu_images import CATALOG
from test_admin_screens_preview_browser import _capture_card_visuals

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


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
        assert box['width'] >= 130 and abs(box['width'] / box['height'] - 16 / 9) < .01
        expect(card.locator('figcaption')).to_have_text('KI-generierter Serviervorschlag')
        missing = page.locator('.menu-slot').nth(1)
        expect(missing.locator('[data-menu-image] img')).to_have_count(0)
        expect(missing.get_by_text('Kein passendes Menübild', exact=True)).to_be_visible()
        expect(card).to_contain_text('Mitarbeitende CHF')
        expect(card).to_contain_text('Externe CHF')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        edit = card.get_by_role('link', name='Bearbeiten:', exact=False)
        assert card.locator('h3').bounding_box()['y'] < box['y']
        assert edit.bounding_box()['y'] + edit.bounding_box()['height'] <= photo.bounding_box()['y']
        if width < 768:
            later = page.locator('.menu-slot').nth(2).bounding_box()
            assert later['height'] < card.bounding_box()['height'] - box['height'] / 2
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
        name = f'Bearbeiten: {day_labels[day_index]}, {meal_label}, {option_label} – {title}'
        link = page.get_by_role('link', name=name, exact=True)
        expect(link).to_have_count(1)
        expect(link).to_have_text('Menü bearbeiten')
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
                return {y: box.y, height: box.height, width: box.width,
                    overflowY: style.overflowY, overflowX: style.overflowX,
                    clientHeight: element.clientHeight, scrollHeight: element.scrollHeight,
                    clientWidth: element.clientWidth, scrollWidth: element.scrollWidth};
            })''')
            assert len(dimensions) == (10 if profile == 'staff_guest' else 28)
            rows: dict[int, list] = {}
            for item in dimensions:
                rows.setdefault(round(item['y']), []).append(item)
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
            page.locator('details.admin-week-service').evaluate_all(
                'els => els.forEach(el => { el.open = true })',
            )
            controls = page.locator(
                '.admin-week-service :is(input:not([type="hidden"]), select, button), '
                '.patient-admin-meal form :is(input:not([type="hidden"]), select, button), .menu-slot .btn',
            )
            for control in controls.all():
                box = control.bounding_box()
                assert box is not None and box['width'] >= 48 and box['height'] >= 48
            page.locator('.admin-day-card, .patient-admin-day').last.screenshot(
                path=str(tmp_path / f'{family}-equal-cards-{width}.png'),
            )
