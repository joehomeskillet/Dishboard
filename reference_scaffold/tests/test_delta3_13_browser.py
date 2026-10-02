"""UI-DELTA: static output settings and direct published read pages."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_admin_workflow_routes import DAY, _login, database_engine  # noqa: F401
from test_admin_screens_preview_browser import TARGETS
from test_delta_renderer_browser import VISIBILITY
from test_print_template_archive import COPY_ID, legacy_document, seed, snapshot
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_browser import published_app, server  # noqa: F401
from test_screen_template_routes import screen_app  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/delta3/DELTA-3-13'
ROUTES = ['/admin/screens', f'/admin/vorlagen?week={DAY}',
          '/admin/screens/cafeteria/wochenvorlage', '/admin/screens/patienten/wochenvorlage']


@pytest.mark.parametrize('width,coarse', [(1440, False), (1440, True), (390, False), (390, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_output_sections_and_published_reads_preserve_native_contracts(
    published_app, server, database_engine, browser, width, coarse, javascript,  # noqa: F811
):
    for profile in ['staff_guest', 'patient']:
        document = legacy_document()
        document['schema_version'] = 2
        for item in document['templates']:
            item['archived'] = item['id'] == COPY_ID
        seed(database_engine, profile, document)
    client, _ = _login(published_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(published_app.config['SESSION_COOKIE_NAME'])
    before = snapshot(database_engine)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with browser.new_context(base_url=server, viewport={'width': width, 'height': 900},
                             has_touch=coarse, java_script_enabled=javascript,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
        page = context.new_page()
        posts, errors, metrics = [], [], []
        page.on('request', lambda r: posts.append(r.method) if r.method == 'POST' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        # Capture every main route before asserting: red baselines stay complete.
        for index, route in enumerate(ROUTES):
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            disclosures = page.locator('main details').count()
            phase = 'before' if disclosures else 'after'
            stem = f'{phase}-{index}-{width}-{"coarse" if coarse else "fine"}-js{javascript}'
            page.screenshot(path=str(EVIDENCE / f'{stem}.png'))
            assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
            controls = []
            for control in page.locator('main .btn:visible, main .nav-link:visible').all():
                visible = control.evaluate(VISIBILITY)
                assert bool(visible['text']) != bool(visible['icons']), visible
                controls.append(visible)
            metrics.append({'route': route, 'disclosures': disclosures, 'controls': controls})
        (EVIDENCE / f'routes-{width}-{coarse}-js{javascript}.json').write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2))
        assert all(row['disclosures'] == 0 for row in metrics), metrics
        assert page.goto('/admin/screens').status == 200
        expect(page.locator('main iframe, main summary')).to_have_count(0)
        links = page.locator('.screen-card .admin-row-actions a')
        urls = [link.get_attribute('href') for link in links.all()]
        assert set(urls) == TARGETS | set(ROUTES[2:])
        for control in links.all():
            visible = control.evaluate(VISIBILITY)
            assert visible['text'] and not visible['icons'], visible
            control.focus()
            expect(control).to_be_focused()
        # Every former iframe target remains a native GET with rendered content.
        for target in sorted(TARGETS):
            assert page.goto('/admin/screens').status == 200
            link = page.locator(f'.screen-card a[href="{target}"]')
            with page.expect_navigation() as navigation:
                link.press('Enter')
            assert navigation.value.status == 200
            assert navigation.value.request.method == 'GET'
            assert urlsplit(page.url).path == target
            expect(page.locator('main')).to_be_visible()
            assert page.locator('main').inner_text().strip()
        for family in ['cafeteria', 'patienten']:
            page.goto(f'/admin/screens/{family}/wochenvorlage')
            form = page.locator('#screen-assignment-details form')
            fields = form.evaluate('f => [...new FormData(f)]')
            assert [name for name, _ in fields] == [
                '_csrf', '_form_context', 'version', 'renderer_revision', 'action', 'template_id']
            expect(page.locator('#screen-assignment-version')).to_have_text('Noch nicht gespeichert')
            for hint in page.locator('.screen-choice-card [id^="screen-choice-"][id$="-hint"]').all():
                expect(hint).to_be_visible()
            expect(page.locator('main [data-semantic="actions.back"]')).to_have_count(0)
            expect(page.locator('.admin-form-footer a')).to_have_attribute('href', '/admin/screens')
            assert form.evaluate('f => [...new FormData(f)]') == fields
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.goto(ROUTES[1])
        tabs = page.locator('.output-area-tabs')
        hint = page.locator('#output-week-hint')
        assert tabs.bounding_box()['y'] + tabs.bounding_box()['height'] <= hint.bounding_box()['y'] + 1
        for family in ['cafeteria', 'patienten']:
            page.locator(f'#output-{family}-tab').click()
            archive = page.locator(f'#output-{family} [data-template-id="{COPY_ID}"]')
            expect(archive).to_be_visible()
            expect(archive).to_contain_text('Kopie')
        assert not posts and not errors
    assert snapshot(database_engine) == before


def test_readonly_template_cells_are_empty_and_assignment_return_remains(
    published_app, server, database_engine, browser,  # noqa: F811
):
    client, _ = _login(published_app, database_engine, ['Cafeteria.Publisher'])
    cookie = client.get_cookie(published_app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(base_url=server) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
        page = context.new_page()
        assert page.goto(ROUTES[1]).status == 200
        cells = page.locator('.output-layouts-section td[data-label="Aktionen"]')
        assert cells.count() > 0
        assert cells.evaluate_all('cells => cells.every(c => c.innerHTML === "")')
        assert page.goto(ROUTES[2]).status == 200
        expect(page.get_by_role('link', name='Zur Bildschirmübersicht', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Speichern', exact=True)).to_have_count(0)
