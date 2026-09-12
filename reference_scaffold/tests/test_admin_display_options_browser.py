"""Global display options have visible consumers and preserve complete menu cards."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from cafeteria.display_settings import DEFAULT_ADMIN_DISPLAY, get_admin_display
from test_admin_display_browser import PATH, _assert_controls, _context
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('width', [390, 820, 1440])
def test_preview_global_consumers_reset_and_fresh_login(
    browser, live_server, admin_app, admin_engine, width, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    for profile, values in [('staff_guest', _staff_values()), ('patient', _patient_values())]:
        options = [option for day in values['days'] for service in day['services'] for option in service['options']]
        options[0].update(title='Pouletbrust an Kräutersauce', components=['Kartoffelstock', 'Zucchetti'])
        options[-1]['note'] = 'Wichtiger langer Rezepturhinweis bleibt vollständig sichtbar. ' * 6
        options[-1]['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
        options[-1]['allergen_review_status'] = 'not_checked'
        _save(admin_app.extensions['cafeteria_db'], profile, values)
    with _context(browser, live_server, client, javascript=False) as first, _context(browser, live_server, client) as second:
        a, b = first.new_page(), second.new_page()
        for page in (a, b):
            page.set_viewport_size({'width': width, 'height': 1100})
        a.goto(PATH)
        expect(a.locator('#admin-content-width-hint')).to_contain_text('volle Breite')
        initial_preview_width = a.locator('.display-preview').bounding_box()['width']
        contained_preview = None
        shell_width = None
        if width == 1440:
            a.set_viewport_size({'width': 1920, 'height': 1100})
            contained_preview = a.locator('.display-preview').bounding_box()['width']
            shell_width = a.locator('.page-body > .container-xl').bounding_box()['width']
            a.set_viewport_size({'width': width, 'height': 1100})
        a.get_by_label('Abstände', exact=True).select_option('comfortable')
        a.get_by_label('Schriftgröße', exact=True).select_option('large')
        a.get_by_label('Inhaltsbreite', exact=True).select_option('full')
        a.get_by_label('Menübilder', exact=True).select_option('hide')
        a.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(a.get_by_text('Vorschau der Auswahl – noch nicht gespeichert.', exact=True)).to_be_visible()
        expect(a.locator('.display-preview')).to_have_attribute('data-font-size', 'large')
        expect(a.locator('.display-preview .menu-photo')).to_have_count(0)
        assert a.locator('#display-example').evaluate('el => parseFloat(getComputedStyle(el).fontSize)') == 18
        # K7-A, Entscheidungsdokument §10: comfortable = nächste Stufe (24 px mobil, 32 px ab 768 px)
        assert a.locator('.display-preview .card-body').evaluate(
            'el => parseFloat(getComputedStyle(el).paddingTop)',
        ) == (24 if width < 768 else 32)
        # Page shell is always full width. Inhaltsbreite still caps .display-preview at 1440 px.
        if width == 1440:
            assert a.locator('.display-preview').bounding_box()['width'] == initial_preview_width
            a.set_viewport_size({'width': 1920, 'height': 1100})
            assert a.locator('.display-preview').bounding_box()['width'] > contained_preview
            assert a.locator('.page-body > .container-xl').bounding_box()['width'] == shell_width
            a.set_viewport_size({'width': width, 'height': 1100})
        assert get_admin_display(admin_engine) == DEFAULT_ADMIN_DISPLAY
        b.goto('/admin/cafeteria/menues')
        expect(b.locator('.menu-photo')).to_have_count(1)
        a.get_by_role('button', name='Darstellung speichern', exact=True).click()
        for family in ('cafeteria', 'patienten'):
            for path, cards in [(f'/admin/{family}?week={DAY}', '.menu-slot'),
                                (f'/admin/{family}/menues', '.menu-grid article[data-menu-id]')]:
                response = b.goto(path)
                assert response is not None and response.status == 200
                expect(b.locator('main')).to_have_attribute('data-font-size', 'large')
                expect(b.locator('main')).to_have_attribute('data-content-width', 'full')
                expect(b.locator('main')).to_have_attribute('data-menu-images', 'hide')
                expect(b.locator('.menu-photo')).to_have_count(0)
                if width == 1440 and family == 'cafeteria' and cards == '.menu-slot':
                    b.set_viewport_size({'width': 1920, 'height': 1100})
                    metrics = b.evaluate('''() => {
                      const main = document.querySelector('main.admin-main');
                      const box = document.querySelector('.page-body > .container-xl');
                      const cs = getComputedStyle(box);
                      const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
                      return {
                        maxWidth: cs.maxWidth,
                        contentWidth: box.getBoundingClientRect().width - pad,
                        expected: main.clientWidth - pad,
                      };
                    }''')
                    assert metrics['maxWidth'] == 'none'
                    assert abs(metrics['contentWidth'] - metrics['expected']) <= 1, metrics
                    b.set_viewport_size({'width': width, 'height': 1100})
                assert b.locator('main .btn').first.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') == 18
                _assert_controls(b)
                dimensions = b.locator(cards).evaluate_all('''els => els.map(el => {
                    const r = el.getBoundingClientRect(); return {y: r.y, width: r.width, height: r.height,
                        overflow: el.scrollHeight > el.clientHeight + 1};
                })''')
                assert dimensions
                if cards == '.menu-slot':
                    rows: dict[int, list] = {}
                    for item in dimensions:
                        rows.setdefault(round(item['y']), []).append(item)
                    for row in rows.values():
                        heights = [item['height'] for item in row]
                        assert max(heights) - min(heights) <= 1
                    widths = [item['width'] for item in dimensions]
                    assert max(widths) - min(widths) <= 1
                else:
                    for axis in ('width', 'height'):
                        assert max(d[axis] for d in dimensions) - min(d[axis] for d in dimensions) <= 1
                assert not any(d['overflow'] for d in dimensions)
                assert 'Milch' in b.locator('main').inner_text()
                if cards == '.menu-slot':
                    last_card = b.locator(cards).last
                    assert 'Wichtiger langer Rezepturhinweis bleibt vollständig sichtbar.' in (last_card.text_content() or '')
            b.screenshot(path=str(tmp_path / f'display-large-{family}-{width}.png'), full_page=True)
        a.goto(PATH)
        a.get_by_role('button', name='Standardwerte speichern', exact=True).click()
        assert get_admin_display(admin_engine) == DEFAULT_ADMIN_DISPLAY
        b.goto('/admin/cafeteria/menues')
        expect(b.locator('.menu-photo')).to_have_count(1)
        expect(b.locator('main')).to_have_attribute('data-font-size', 'normal')
        a.screenshot(path=str(tmp_path / f'display-default-{width}.png'), full_page=True)
        a.get_by_label('Schriftgröße', exact=True).select_option('large')
        a.get_by_role('button', name='Darstellung speichern', exact=True).click()
    fresh, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    with _context(browser, live_server, fresh) as context:
        page = context.new_page()
        page.goto('/admin/patienten')
        expect(page.locator('main')).to_have_attribute('data-font-size', 'large')
        expect(page.get_by_role('link', name='Design & Marke', exact=True)).to_have_count(0)
