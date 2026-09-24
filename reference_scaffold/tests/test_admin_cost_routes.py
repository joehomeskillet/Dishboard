"""Kalkulation routes exist; preview has no BESTELLEN; missing price stays incomplete."""
import json
import secrets
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs

import pytest
from flask import Flask, render_template, request, url_for
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui


def test_kalkulation_template_preview_not_send() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'kalkulation.html').read_text(encoding='utf-8')
    assert 'Vorschau schreibt nichts' in text
    assert 'unvollständig, nie 0' in text
    assert 'BESTELLEN' not in text
    assert 'admin.cost_preview' in text
    assert 'admin.cost_confirm' in text
    assert 'menu_revision_public_id' in text


def test_cost_routes_registered() -> None:
    app = Flask('cost')
    from cafeteria.admin.routes import bp
    import cafeteria.admin.cost_routes  # noqa: F401
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.cost_home') == '/admin/kalkulation'
        assert url_for('admin.cost_preview') == '/admin/kalkulation/vorschau'
        assert url_for('admin.cost_confirm') == '/admin/kalkulation/beleg'


FOOD_ID = '11111111-1111-4111-8111-111111111111'
REVISION_ID = '22222222-2222-4222-8222-222222222222'
PRICE_ID = '33333333-3333-4333-8333-333333333333'
EXTRA_ID = '44444444-4444-4444-8444-444444444444'


@pytest.fixture(scope='module')
def cost_layout_site():
    """Real template, shell and local assets; synthetic context, no DB writes.

    Requests to the product's POST endpoints are captured by the browser test,
    not executed. Store/calculation contracts run separately in the WP gate.
    No product validation or authorization implementation is replaced.
    """
    root = Path(__file__).resolve().parents[1] / 'cafeteria'
    app = Flask('cost-layout', template_folder=str(root / 'templates'),
                static_folder=str(root / 'static'))
    app.config.update(TESTING=True, SECRET_KEY=secrets.token_hex(32))
    from cafeteria.admin.routes import bp
    import cafeteria.admin.cost_routes  # noqa: F401
    app.register_blueprint(bp)
    app.add_url_rule('/logout', endpoint='auth.logout', view_func=lambda: '')
    register_template_filters(app)
    register_ui(app)
    app.jinja_env.globals['csrf_token'] = lambda: 'cost-layout-csrf'

    @app.get('/__cost_layout__/<state>')
    def layout(state):
        complete = state in {'complete', 'zero'}
        amount = '0.00' if state == 'zero' else '1.00'
        projection = None if state == 'empty' else {
            'complete': complete, 'total': ('0.00' if state == 'zero' else '6.00') if complete else None,
            'lines': [{'food_public_id': FOOD_ID, 'quantity': '250', 'unit_code': 'G',
                       'status': 'complete' if complete else 'incomplete',
                       'amount': amount if complete else None}] * 6,
            'price_revisions': {FOOD_ID: PRICE_ID} if complete else {},
        }
        return render_template(
            'admin/kalkulation.html', projection=projection, as_of='2026-09-20',
            revision_public_id='' if state == 'empty' else REVISION_ID,
            kind=request.args.get('kind', 'recipe'),
            menu_revision_public_ids=request.args.getlist('extra'),
            can_browse_recipes=True,
        )

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                yield browser, f'http://127.0.0.1:{server.server_port}'
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width', [360, 768, 1024, 1440])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_kalkulation_layout_status_keyboard_and_form_contract(cost_layout_site, width, javascript, tmp_path):
    browser, origin = cost_layout_site
    with browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript,
                             reduced_motion='reduce', locale='de-CH', timezone_id='Europe/Zurich') as context:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        metrics = []
        for state in ('empty', 'incomplete', 'complete', 'zero'):
            assert page.goto(origin + '/__cost_layout__/' + state).status == 200
            page.evaluate('document.fonts.ready')
            expect(page.locator('h1')).to_have_text('Kalkulation')
            expect(page.locator('main .btn-primary')).to_have_count(1)
            expect(page.locator('.admin-statusbar')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert page.locator('main details[open]').count() == 0
            assert page.locator('#menu_revision_public_id').is_hidden()
            if state == 'empty':
                expect(page.locator('.admin-statusbar')).to_contain_text('Offen')
                expect(page.locator('.cost-empty a')).to_have_attribute('href', '#kind')
                expect(page.locator('main .btn-primary')).to_have_text('Vorschau')
            else:
                expect(page.locator('main .btn-primary')).to_have_text('Bestätigen')
                expect(page.locator('.cost-lines tbody tr')).to_have_count(6)
                assert FOOD_ID not in page.locator('.cost-lines').inner_text()
                if state == 'incomplete':
                    expect(page.locator('.admin-statusbar')).to_contain_text('unvollständig')
                    expect(page.locator('.admin-statusbar')).to_contain_text('6 · Offen')
                    assert 'CHF' not in page.locator('.admin-statusbar').inner_text()
                    expect(page.get_by_text('Unvollständig — fehlender Preis oder fehlende Umrechnung, nicht als 0.')).to_be_visible()
                    assert page.locator('.cost-lines tbody tr td:last-child').all_inner_texts() == ['—'] * 6
                else:
                    expect(page.locator('.admin-statusbar-item--success')).to_contain_text('vollständig')
                    expect(page.locator('.admin-statusbar')).to_contain_text('0.00 CHF' if state == 'zero' else '6.00 CHF')
            measured = page.evaluate('''() => ({height: document.documentElement.scrollHeight,
                form: document.querySelector('#cost-preview').getBoundingClientRect().height,
                row: document.querySelector('.cost-lines tbody tr')?.getBoundingClientRect().height ?? null,
                primary: document.querySelectorAll('main .btn-primary').length,
                open: document.querySelectorAll('main details[open]').length})''')
            expect(page.locator('main .btn-primary')).to_be_visible()
            if width < 768 and state != 'empty':
                stacked = page.evaluate('''() => {
                    const table = document.querySelector('.cost-lines.admin-table.admin-table--stack');
                    return Boolean(table) && getComputedStyle(table.querySelector('tbody')).display === 'block';
                }''')
                assert stacked, (state, width, javascript)
                expect(page.locator('table.admin-table.admin-table--stack').first).to_be_visible()
                expect(page.locator('.admin-label').first).to_be_visible()
            hint = page.locator('details.admin-hint').first
            summary = hint.locator('summary')
            expect(summary).to_be_visible()
            summary.focus()
            expect(summary).to_be_focused()
            if hint.get_attribute('open') is None:
                page.keyboard.press('Enter')
            expect(hint).to_have_attribute('open', '')
            page.keyboard.press('Enter')
            if measured['row'] is not None:
                assert measured['row'] < (109 if width == 360 else 46)
            assert measured['form'] < (428 if width == 360 else 218)
            metrics.append({'state': state, 'width': width, 'javascript': javascript, **measured})
            for control in page.locator('main :is(.btn, input:not([type=hidden]), select, summary):visible').all():
                assert control.bounding_box()['height'] >= 48
            page.screenshot(path=str(tmp_path / f'cost-{state}-{width}-{javascript}.png'), full_page=True)

        # Native select + disclosure works without JavaScript; optional values still submit.
        page.goto(origin + '/__cost_layout__/empty')
        page.locator('main .btn-primary').click()
        expect(page.locator('#revision_public_id')).to_be_focused()
        page.locator('#revision_public_id').fill(REVISION_ID)
        page.locator('#kind').select_option('menu')
        summary = page.locator('#cost-options > summary')
        expect(summary).to_be_visible()
        page.locator('#as_of').focus()
        # Chromium's native date control has multiple keyboard segments.
        for _ in range(6):
            page.keyboard.press('Tab')
            if summary.evaluate('el => el === document.activeElement'):
                break
        expect(summary).to_be_focused()
        assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Enter')
        expect(page.locator('#cost-options')).to_have_attribute('open', '')
        page.keyboard.press('Tab')
        expect(page.locator('#menu_revision_public_id')).to_be_focused()
        page.locator('#menu_revision_public_id').fill(EXTRA_ID)
        summary.press('Enter')
        expect(page.locator('#cost-options')).not_to_have_attribute('open', '')

        captured = []

        def capture_post(route):
            captured.append((route.request.url, parse_qs(route.request.post_data, keep_blank_values=True)))
            route.fulfill(status=200, content_type='text/plain', body='Captured for contract comparison')

        page.route('**/admin/kalkulation/*', capture_post)
        with page.expect_request('**/admin/kalkulation/vorschau'):
            page.locator('main .btn-primary').press('Enter')
        page.wait_for_load_state()
        assert captured[-1][1] == {
            '_csrf': ['cost-layout-csrf'], 'kind': ['menu'], 'revision_public_id': [REVISION_ID],
            'menu_revision_public_id': [EXTRA_ID], 'as_of': ['2026-09-20'],
        }
        page.goto(origin + '/__cost_layout__/complete?kind=menu&extra=' + EXTRA_ID)
        expect(page.locator('#cost-options')).to_have_attribute('open', '')
        with page.expect_request('**/admin/kalkulation/beleg'):
            page.locator('main .btn-primary').press('Enter')
        page.wait_for_load_state()
        assert captured[-1][1] == {
            '_csrf': ['cost-layout-csrf'], 'kind': ['menu'], 'revision_public_id': [REVISION_ID],
            'menu_revision_public_id': [EXTRA_ID], 'as_of': ['2026-09-20'],
            'price_food_id': [FOOD_ID], 'price_revision_id': [PRICE_ID],
        }
        assert not errors
        (tmp_path / f'cost-metrics-{width}-{javascript}.json').write_text(json.dumps(metrics, indent=2))
        print('COST_METRICS=' + json.dumps(metrics))
