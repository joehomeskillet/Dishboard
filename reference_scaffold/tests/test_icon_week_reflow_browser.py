"""Long weekly course names and truthful missing-image text retain their own space."""
from __future__ import annotations

import base64
import json

import pytest
from playwright.sync_api import expect

from cafeteria.course_store import persist_service_courses
from test_admin_ux_browser import live_server
from test_admin_workflow_db import _actor_id, _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, WEEK, _scope
from test_course_week_html import _recipe
from test_rendered_ui import _login, admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server']

SOUP = 'Synthetische Wintergemüsesuppe mit gerösteten Kürbiskernen und frischen Gartenkräutern'
DESSERT = 'Synthetisches Apfelkompott mit LangnamenprüfungOhneWortzwischenraumundZusätzlicherVanilledekoration'
GEOMETRY = '''() => {
    const failures = [];
    const contains = (outer, inner) => inner.left >= outer.left - 1 && inner.right <= outer.right + 1
        && inner.top >= outer.top - 1 && inner.bottom <= outer.bottom + 1;
    const intersects = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1
        && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
    const rows = [...document.querySelectorAll('.admin-week-course, .admin-week-image-missing')];
    const measurements = rows.map(row => {
        const boundary = row.getBoundingClientRect();
        const texts = [];
        const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (!node.textContent.trim() || node.parentElement.closest('a, .visually-hidden')) continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            for (const rect of range.getClientRects()) {
                if (rect.width && rect.height) {
                    texts.push(rect.toJSON());
                    if (!contains(boundary, rect)) failures.push('Text outside row: ' + row.textContent.trim());
                    for (const action of row.querySelectorAll('a')) {
                        if (intersects(rect, action.getBoundingClientRect())) failures.push('Text overlaps action');
                    }
                }
            }
        }
        return {text: row.textContent.trim(), box: boundary.toJSON(), texts};
    });
    for (let i = 0; i < measurements.length; i++) {
        for (let j = i + 1; j < measurements.length; j++) {
            if (intersects(measurements[i].box, measurements[j].box)) failures.push('Rows overlap');
        }
    }
    return {failures, measurements, width: innerWidth, scrollWidth: document.documentElement.scrollWidth};
}'''


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('width,zoom', [(1440, 1), (1024, 1), (768, 1), (390, 1), (1440, 2)])
def test_week_long_names_missing_images_and_native_controls_reflow(
    browser, live_server, admin_app, admin_engine, tmp_path, family, profile, javascript, width, zoom,
):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    for day in values['days']:
        for service in day['services']:
            for option in service['options']:
                option['title'] = 'Synthetisches Menü ohne Bildzuordnung'
                option['allergens'] = []
                option['allergen_review_status'] = 'not_checked'
    _save(admin_engine, profile, values)
    actor = _actor_id(admin_engine)
    scope = _scope(admin_engine, actor, profile)
    soup = _recipe(admin_engine, actor, scope.location_id, SOUP)
    dessert = _recipe(admin_engine, actor, scope.location_id, DESSERT)
    meals = ('LUNCH',) if family == 'cafeteria' else ('LUNCH', 'DINNER')
    for meal in meals:
        persist_service_courses(
            admin_engine, scope, WEEK, DAY, meal,
            soup={'state': 'planned', 'recipe_public_id': soup['public_id']},
            dessert={'state': 'planned', 'recipe_public_id': dessert['public_id']}, exceptions=[],
        )
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    options = dict(base_url=live_server, java_script_enabled=javascript, reduced_motion='reduce')
    if zoom == 2:
        context = browser.browser_type.launch_persistent_context(
            str(tmp_path / 'chrome-profile'), channel='chromium', headless=True, no_viewport=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'], **options,
        )
        page = context.pages[0]
    else:
        context = browser.new_context(viewport={'width': width, 'height': 900}, **options)
        page = context.new_page()
    try:
        if zoom == 2:
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
        cookie = client.get_cookie('session')
        assert cookie is not None
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'domain': '127.0.0.1', 'path': '/', 'httpOnly': True}])
        response = page.goto(f'/admin/{family}?week={DAY}', wait_until='networkidle')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        first_day = page.locator('.admin-day-card, .patient-admin-day').first
        courses = first_day.locator('.admin-week-course')
        expect(courses).to_have_count(len(meals) * 2)
        assert courses.evaluate_all('nodes => nodes.map(node => node.dataset.course)') == ['soup', 'dessert'] * len(meals)
        assert courses.locator('a').evaluate_all('nodes => nodes.map(node => node.getAttribute("href"))') == [
            f'#course-{DAY}-{meal}-{kind}-state' for meal in meals for kind in ('soup', 'dessert')
        ]
        for index in range(len(meals)):
            expect(courses.nth(index * 2)).to_contain_text(SOUP)
            expect(courses.nth(index * 2 + 1)).to_contain_text(DESSERT)
        expect(courses.locator('[data-allergen-state="missing"]')).to_have_count(len(meals) * 2)
        expect(courses.locator('[data-allergen-state="missing"]').first).to_have_text('Allergenangaben fehlen')
        expect(page.locator('[data-menu-metadata]').first).to_contain_text('nicht allergenfrei')
        expect(page.locator('#week-publish-form [type="submit"]')).to_be_disabled()
        if family == 'cafeteria':
            expect(page.locator('.admin-week-image-missing')).to_have_count(10)
            expect(page.locator('.admin-week-image-missing').first).to_have_text('Kein passendes Menübild')
            expect(page.locator('[data-menu-image] img')).to_have_count(0)
        else:
            expect(page.locator('[data-menu-image]')).to_have_count(0)
        name = f'{family}-{width}-{zoom}x-{javascript}'
        metrics = page.evaluate(GEOMETRY)
        if family == 'cafeteria':
            missing_image = page.locator('.admin-week-image-missing').first
            missing_image.scroll_into_view_if_needed()
            metrics['clippedImageCharacters'] = missing_image.evaluate('''row => {
                const clipped = [];
                const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    for (let i = 0; i < node.length; i++) {
                        if (!node.textContent[i].trim()) continue;
                        const range = document.createRange();
                        range.setStart(node, i); range.setEnd(node, i + 1);
                        const r = range.getBoundingClientRect();
                        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                        if (!node.parentElement.contains(hit)) clipped.push(node.textContent[i]);
                    }
                }
                return clipped;
            }''')
            page.evaluate('scrollTo(0, 0)')
        (tmp_path / f'{name}.geometry.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
        # Capture before geometry assertions so the unchanged-source run proves the regression.
        if zoom == 2:
            cdp = context.new_cdp_session(page)
            try:
                proof = cdp.send('Page.getLayoutMetrics')
                assert proof['cssVisualViewport']['zoom'] == 2
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
                (tmp_path / f'{name}.zoom.json').write_text(json.dumps(proof, indent=2))
                for label, target in [('courses', courses.first), ('menu', first_day.locator('.menu-slot').first)]:
                    target.scroll_into_view_if_needed()
                    png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                        'format': 'png', 'captureBeyondViewport': False,
                    })['data'], validate=True)
                    (tmp_path / f'{name}-{label}.png').write_bytes(png)
                    assert int.from_bytes(png[16:20], 'big') == 1440
            finally:
                cdp.detach()
        else:
            page.screenshot(path=str(tmp_path / f'{name}.png'), full_page=True)
        assert metrics['scrollWidth'] <= metrics['width'] + 1, metrics
        assert not metrics['failures'], metrics['failures']
        assert not metrics.get('clippedImageCharacters'), metrics
        # Static course fields retain their native POST contract without app scripts.
        editor = first_day.locator('.admin-week-course-editor').first
        expect(editor.locator('details, summary')).to_have_count(0)
        form = editor.locator('form[method="post"]')
        expect(form).to_have_attribute('action', f'/admin/{family}/courses')
        expect(form.locator('[name="soup_state"]')).to_have_value('planned')
        expect(form.locator('[name="dessert_state"]')).to_have_value('planned')
        fields = form.evaluate('node => Object.fromEntries(new FormData(node))')
        assert fields['_csrf'] and fields['week'] == DAY and fields['day'] == DAY and fields['meal'] == 'LUNCH'
        assert fields['soup_recipe'] == soup['public_id'] and fields['dessert_recipe'] == dessert['public_id']
        assert fields['soup_row_version'] and fields['dessert_row_version']
        form.locator('[name="soup_state"]').focus()
        expect(form.locator('[name="soup_state"]')).to_be_focused()
        expect(form.locator('[name="soup_recipe"]')).to_be_visible()
    finally:
        context.close()
