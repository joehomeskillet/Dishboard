"""Order admin has no send button; routes exist."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qsl

from flask import Flask, url_for
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from cafeteria.order_basket_store import create_basket, get_basket, replace_basket_lines
from cafeteria.shopping_list_reads import ShoppingScope
from cafeteria.supplier_store import create_article, create_supplier
from test_master_data_routes import Forms, b3  # noqa: F401
from test_master_data_db import app_engine, installed_pg16, pg16, seeded_pg16  # noqa: F401

ROOT = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin'
HOME_FIELDS = {
    '/admin/bestellung/lieferanten': {'_csrf', 'code', 'name'},
    '/admin/bestellung/artikel': {
        '_csrf', 'supplier_public_id', 'article_code', 'name', 'order_unit_code', 'pack_size',
    },
    '/admin/bestellung/korb': {'_csrf', 'supplier_public_id'},
}
BASKET_SAVE_FIELDS = {'_csrf', 'row_version', 'article_public_id', 'quantity', 'raw_quantity'}
BASKET_DEMAND_FIELDS = {'_csrf', 'row_version', 'food_public_id', 'need_quantity'}
VIEWPORTS = ((360, 844), (390, 844), (768, 1024), (1024, 768), (1440, 900))


class OrderForms(Forms):
    """Successful controls for these input/select forms, including repeated selects."""

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'select':
            self.select = None if 'disabled' in data else data.get('name')
            self.options = []
            return
        if tag == 'option':
            if self.select and 'disabled' not in data:
                self.options.append((data.get('value', ''), 'selected' in data))
            return
        if 'disabled' not in data:
            super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'select' and self.select and self.options:
            selected = next((v for v, chosen in self.options if chosen), self.options[0][0])
            self.current.add(self.select, selected)
        super().handle_endtag(tag)


def test_form_parser_omits_disabled_but_keeps_readonly_and_repeated_controls():
    form = OrderForms('''<form action="/save">
        <input name="quantity" value="2" disabled>
        <input name="quantity" value="3">
        <input name="raw_quantity" value="1.25" readonly>
        <input name="article_public_id" value="first">
        <select name="article_public_id"><option value="second">Second</option></select>
        <select name="article_public_id" disabled><option value="bad">Bad</option></select>
        </form>''').forms['/save']
    assert form.getlist('quantity') == ['3']
    assert form.getlist('raw_quantity') == ['1.25']
    assert form.getlist('article_public_id') == ['first', 'second']


def test_templates_have_no_send_action() -> None:
    for name in ('bestellung.html', 'bestellung_korb.html'):
        text = (ROOT / name).read_text(encoding='utf-8')
        assert 'BESTELLEN' not in text
        assert 'send_pending' not in text or 'Status' in text
        if name == 'bestellung_korb.html':
            assert 'Rohmenge' in text
            assert 'Gebinde' in text


def test_order_home_is_registered() -> None:
    app = Flask('orders')
    from cafeteria.admin.routes import bp
    import cafeteria.admin.order_routes  # noqa: F401
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.order_home') == '/admin/bestellung'
        assert 'csv' in url_for('admin.order_basket_csv', public_id='00000000-0000-4000-8000-000000000001')
        assert url_for('admin.order_basket_from_demand', public_id='00000000-0000-4000-8000-000000000001').endswith('/bedarf')


def test_templates_use_statusbar_and_one_primary() -> None:
    home = (ROOT / 'bestellung.html').read_text(encoding='utf-8')
    basket = (ROOT / 'bestellung_korb.html').read_text(encoding='utf-8')
    assert 'status_items=' in home
    assert 'status_items=' in basket
    assert "t('navigation.orders.label')" in home
    assert "t('navigation.orders.label')" in basket
    assert home.count('btn-primary') == 1
    assert basket.count('btn-primary') == 1
    assert 'name="row_version"' in basket
    assert 'name="_csrf"' in home
    assert 'name="_csrf"' in basket


def test_home_and_basket_post_fields_stay_byte_equal() -> None:
    home = (ROOT / 'bestellung.html').read_text(encoding='utf-8')
    basket = (ROOT / 'bestellung_korb.html').read_text(encoding='utf-8')
    assert 'name="code"' in home
    assert 'name="name"' in home
    assert 'name="supplier_public_id"' in home
    assert 'name="article_code"' in home
    assert 'name="order_unit_code"' in home
    assert 'value="KG"' in home
    assert 'name="pack_size"' in home
    assert 'value="1"' in home
    assert 'name="article_public_id"' in basket
    assert 'name="quantity"' in basket
    assert 'name="raw_quantity"' in basket
    assert 'name="food_public_id"' in basket
    assert 'name="need_quantity"' in basket
    assert 'preferred' not in home


def _names(form) -> set[str]:
    return set(form.keys())


def test_rendered_forms_keep_posted_names(b3) -> None:  # noqa: F811
    app, owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with owner.connect() as connection:
        location = connection.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    supplier = create_supplier(engine, actor, {'code': 'SUD', 'name': 'Süd'})
    article = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': None,
        'article_code': 'MEHL-1', 'name': 'Mehl', 'order_unit_code': 'KG',
        'pack_size': '1', 'preferred': False,
    })
    basket_id = create_basket(engine, ShoppingScope(actor.user_id, location, actor.authz_version), supplier.public_id)
    replace_basket_lines(
        engine, ShoppingScope(actor.user_id, location, actor.authz_version), basket_id,
        expected_row_version=get_basket(engine, location, basket_id)['row_version'],
        lines=[{'article_public_id': article.public_id, 'quantity': '1', 'raw_quantity': '1'}],
    )
    second = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': None,
        'article_code': 'REIS-2', 'name': 'Reis', 'order_unit_code': 'KG',
        'pack_size': '1', 'preferred': False,
    })
    replace_basket_lines(
        engine, ShoppingScope(actor.user_id, location, actor.authz_version), basket_id,
        expected_row_version=get_basket(engine, location, basket_id)['row_version'],
        lines=[{'article_public_id': article.public_id, 'quantity': '2', 'raw_quantity': '1.25'},
               {'article_public_id': second.public_id, 'quantity': '4', 'raw_quantity': '3.75'}],
    )
    home = OrderForms(client.get('/admin/bestellung').get_data(as_text=True))
    for action, expected in HOME_FIELDS.items():
        assert action in home.forms, sorted(home.forms)
        assert expected <= _names(home.forms[action]), (action, _names(home.forms[action]))
    detail = OrderForms(client.get(f'/admin/bestellung/korb/{basket_id}').get_data(as_text=True))
    save_action = f'/admin/bestellung/korb/{basket_id}'
    demand_action = f'/admin/bestellung/korb/{basket_id}/bedarf'
    assert BASKET_SAVE_FIELDS <= _names(detail.forms[save_action])
    assert BASKET_DEMAND_FIELDS <= _names(detail.forms[demand_action])
    assert detail.forms[save_action]['row_version']
    form = detail.forms[save_action]
    assert form.getlist('article_public_id') == [article.public_id, second.public_id, '']
    assert [Decimal(v) for v in form.getlist('quantity')[:-1]] == [Decimal('2'), Decimal('4')]
    assert [Decimal(v) for v in form.getlist('raw_quantity')[:-1]] == [Decimal('1.25'), Decimal('3.75')]
    assert form.getlist('quantity')[-1] == form.getlist('raw_quantity')[-1] == ''
    form.setlist('quantity', ['5.5', '8.25', ''])
    response = client.post(save_action, data=form)
    assert response.status_code == 303 and response.location.endswith(save_action)
    saved = get_basket(engine, location, basket_id)
    assert saved['row_version'] > int(form['row_version'])
    assert [(str(line['article_public_id']), line['quantity'], line['raw_quantity'])
            for line in saved['lines']] == [
        (article.public_id, Decimal('5.5'), Decimal('1.25')),
        (second.public_id, Decimal('8.25'), Decimal('3.75')),
    ]
    html = client.get('/admin/bestellung').get_data(as_text=True)
    assert 'admin-statusbar' in html
    assert html.count('btn-primary') == 1


def test_order_pages_viewports_statusbar_keyboard_nojs(b3, tmp_path) -> None:  # noqa: F811
    app, owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with owner.connect() as connection:
        location = connection.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    supplier = create_supplier(engine, actor, {'code': 'SUD', 'name': 'Südhang Hof'})
    article = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': None,
        'article_code': 'MEHL-1', 'name': 'Mehl', 'order_unit_code': 'KG',
        'pack_size': '1', 'preferred': False,
    })
    scope = ShoppingScope(actor.user_id, location, actor.authz_version)
    basket_id = create_basket(engine, scope, supplier.public_id)
    replace_basket_lines(
        engine, scope, basket_id,
        expected_row_version=get_basket(engine, location, basket_id)['row_version'],
        lines=[{'article_public_id': article.public_id, 'quantity': '2', 'raw_quantity': '1.5'}],
    )
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    origin = f'http://127.0.0.1:{server.server_port}'
    measurements = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                for javascript in (False, True):
                    context = browser.new_context(
                        java_script_enabled=javascript, reduced_motion='reduce',
                        viewport={'width': 1440, 'height': 900})
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
                    page = context.new_page()
                    for width, height in VIEWPORTS:
                        page.set_viewport_size({'width': width, 'height': height})
                        assert page.goto(origin + '/admin/bestellung').status == 200
                        page.evaluate('document.fonts && document.fonts.ready')
                        metrics = page.evaluate('''() => {
                            const row = document.querySelector('.admin-list-row');
                            const primary = document.querySelector('main .btn-primary');
                            return {
                                overflow: document.documentElement.scrollWidth > innerWidth + 1,
                                height: document.documentElement.scrollHeight,
                                row: row ? Math.round(row.getBoundingClientRect().height) : null,
                                primary: primary ? Math.round(primary.getBoundingClientRect().height) : null,
                                primaries: document.querySelectorAll('main .btn-primary').length,
                                openDetails: document.querySelectorAll('main details[open]').length,
                            };
                        }''')
                        print('WP11_METRICS ' + json.dumps({
                            'page': 'home', 'javascript': javascript,
                            'width': width, **metrics,
                        }))
                        assert not metrics['overflow']
                        assert metrics['primaries'] == 1
                        assert metrics['primary'] >= 48
                        assert metrics['row'] is not None and metrics['row'] < (140 if width < 768 else 96)
                        targets = page.locator('main .btn:visible, main summary:visible')
                        sizes = targets.evaluate_all('els => els.map(el => {const r = el.getBoundingClientRect(); return [r.width, r.height];})')
                        assert all(w >= 48 and h >= 48 for w, h in sizes), sizes
                        measurements.append({'page': 'home', 'width': width, 'javascript': javascript,
                                             **metrics, 'targets': sizes})
                        print('WP11_TARGETS ' + json.dumps({'page': 'home', 'width': width, 'javascript': javascript, 'sizes': sizes}))
                        expect(page.get_by_role('heading', level=1)).to_contain_text('Bestellung')
                        bar = page.locator('dl.admin-statusbar')
                        expect(bar).to_be_visible()
                        expect(bar).to_contain_text('Warenkorb')
                        expect(bar).to_contain_text('Lieferant')
                        primary = page.locator('main .btn-primary')
                        primary.focus()
                        expect(primary).to_be_focused()
                        assert primary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                        page.screenshot(path=str(tmp_path / f'home-{width}-js-{javascript}.png'), full_page=True)
                        assert page.goto(origin + f'/admin/bestellung/korb/{basket_id}').status == 200
                        page.evaluate('document.fonts && document.fonts.ready')
                        basket_metrics = page.evaluate('''() => {
                            const line = document.querySelector('.order-lines tbody tr');
                            return {
                                overflow: document.documentElement.scrollWidth > innerWidth + 1,
                                height: document.documentElement.scrollHeight,
                                line: line ? Math.round(line.getBoundingClientRect().height) : null,
                                primaries: document.querySelectorAll('main .btn-primary').length,
                                rowVersion: Boolean(document.querySelector('form [name="row_version"]')),
                                csrf: Boolean(document.querySelector('form [name="_csrf"]')),
                            };
                        }''')
                        print('WP11_METRICS ' + json.dumps({
                            'page': 'basket', 'javascript': javascript,
                            'width': width, **basket_metrics,
                        }))
                        assert not basket_metrics['overflow']
                        assert basket_metrics['primaries'] == 1
                        expect(page.locator('main .btn-primary')).to_be_visible()
                        if width < 768:
                            stacked = page.evaluate('''() => {
                                const table = document.querySelector('.order-lines.admin-table--stack');
                                return Boolean(table) && getComputedStyle(table.querySelector('tbody')).display === 'block';
                            }''')
                            assert stacked, (javascript, width)
                        hint = page.locator('details.admin-hint').first
                        summary = hint.locator('summary')
                        expect(summary).to_be_visible()
                        summary.focus()
                        expect(summary).to_be_focused()
                        if hint.get_attribute('open') is None:
                            page.keyboard.press('Enter')
                        expect(hint).to_have_attribute('open', '')
                        page.keyboard.press('Enter')
                        if width == 1440:
                            heights = page.locator('.order-lines tbody tr').evaluate_all('els => els.map(el => el.getBoundingClientRect().height)')
                            assert all(h <= 96 for h in heights), heights
                        targets = page.locator('main .btn:visible, main summary:visible, main input:not([type=hidden]):visible, main select:visible')
                        sizes = targets.evaluate_all('els => els.map(el => {const r = el.getBoundingClientRect(); return [r.width, r.height];})')
                        assert all(w >= 48 and h >= 48 for w, h in sizes), sizes
                        measurements.append({'page': 'basket', 'width': width, 'javascript': javascript,
                                             **basket_metrics, 'targets': sizes})
                        print('WP11_TARGETS ' + json.dumps({'page': 'basket', 'width': width, 'javascript': javascript, 'sizes': sizes}))
                        assert basket_metrics['rowVersion'] and basket_metrics['csrf']
                        expect(page.locator('dl.admin-statusbar')).to_contain_text('Entwurf')
                        expect(page.locator('dl.admin-statusbar')).to_contain_text('Südhang Hof')
                        more = page.locator('#korb-weitere')
                        expect(more).not_to_have_attribute('open', '')
                        more.locator('summary').focus()
                        expect(more.locator('summary')).to_be_focused()
                        page.keyboard.press('Enter')
                        expect(more).to_have_attribute('open', '')
                        expect(page.locator('#demand_food')).to_be_visible()
                        page.keyboard.press('Enter')
                        expect(more).not_to_have_attribute('open', '')
                        page.screenshot(path=str(tmp_path / f'basket-{width}-js-{javascript}.png'), full_page=True)
                    # A real navigation from an existing basket must expose creation immediately.
                    page.goto(origin + '/admin/bestellung')
                    page.locator('main .btn-primary').click()
                    expect(page.locator('#korb-anlegen')).to_have_attribute('open', '')
                    expect(page.locator('#basket_supplier')).to_be_visible()
                    sizes = page.locator('#korb-anlegen select, #korb-anlegen button').evaluate_all(
                        'els => els.map(el => {const r = el.getBoundingClientRect(); return [r.width, r.height];})')
                    assert all(w >= 48 and h >= 48 for w, h in sizes), sizes
                    if javascript:
                        expect(page.locator('#basket_supplier')).to_be_focused()
                    with page.expect_response(lambda r: r.request.method == 'POST') as creation:
                        page.locator('#korb-anlegen button[type=submit]').click()
                    assert creation.value.status == 303
                    expect(page.locator('.order-basket-form')).to_be_visible()
                    created_id = page.url.rsplit('/', 1)[1]
                    assert get_basket(engine, location, created_id)['lines'] == ()
                    # Browser serialization includes readonly values and all repeated controls.
                    page.goto(origin + f'/admin/bestellung/korb/{basket_id}')
                    page.locator('.order-basket-form [name=quantity]').first.fill('6.25' if javascript else '5.75')
                    expected = page.locator('.order-basket-form').evaluate('form => Array.from(new FormData(form).entries())')
                    parsed = OrderForms(page.content()).forms[f'/admin/bestellung/korb/{basket_id}']
                    for name in BASKET_SAVE_FIELDS - {'quantity'}:
                        assert parsed.getlist(name) == [v for k, v in expected if k == name]
                    with page.expect_response(lambda r: r.request.method == 'POST') as saving:
                        page.locator('.order-basket-form button[type=submit]').click()
                    assert saving.value.status == 303
                    posted = MultiDict(parse_qsl(saving.value.request.post_data, keep_blank_values=True))
                    assert list(posted.lists()) == list(MultiDict(expected).lists())
                    saved = get_basket(engine, location, basket_id)
                    assert saved['lines'][0]['quantity'] == Decimal('6.25' if javascript else '5.75')
                    assert saved['lines'][0]['raw_quantity'] == Decimal('1.5')
                    context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        (tmp_path / 'measurements.json').write_text(json.dumps(measurements, indent=2))
        print(f'WP11_EVIDENCE {tmp_path}')


def test_order_statuses_and_empty_texts_in_both_locales(b3, monkeypatch):  # noqa: F811
    from cafeteria.admin import order_routes

    app, owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    for locale, empty in (('de', 'Noch keine Körbe'), ('en', 'No baskets yet')):
        app.config['UI_LOCALE'] = locale
        html = client.get('/admin/bestellung').text
        assert empty in html and '⟦' not in html
        assert 'data-semantic="ui.order_empty_suppliers"' in html
        assert 'data-semantic="ui.order_empty_articles"' in html
    with owner.connect() as connection:
        location = connection.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    supplier = create_supplier(engine, actor, {'code': 'ST', 'name': 'Status fixture'})
    basket_id = create_basket(engine, ShoppingScope(actor.user_id, location, actor.authz_version), supplier.public_id)
    basket = get_basket(engine, location, basket_id)
    # Schema states are rendered only: this test introduces no send transition.
    for state, key, variant, de, en in (
        ('draft', 'publish.draft', 'neutral', 'Entwurf', 'Draft'),
        ('abandoned', 'ui.order_abandoned', 'neutral', 'Verworfen', 'Abandoned'),
        ('send_pending', 'ui.order_pending', 'warning', 'Versand ausstehend', 'Send pending'),
        ('sent', 'ui.order_sent', 'success', 'Gesendet', 'Sent'),
        ('send_unknown', 'ui.order_unknown', 'warning', 'Versandstatus unklar', 'Send status unknown'),
    ):
        rendered = {**basket, 'status': state}
        monkeypatch.setattr(order_routes, 'get_basket', lambda *args: rendered)
        monkeypatch.setattr(order_routes, 'list_baskets', lambda *args: (rendered,))
        for locale, label in (('de', de), ('en', en)):
            app.config['UI_LOCALE'] = locale
            home = client.get('/admin/bestellung').text
            detail = client.get(f'/admin/bestellung/korb/{basket_id}').text
            for html in (home, detail):
                assert f'data-semantic="{key}"' in html
                assert f'<span>{label}</span>' in html
                assert '⟦' not in html
                assert f'>{state}<' not in html
                assert f'badge admin-status--{variant} ui-sem-label' in html
            assert f'admin-statusbar-item--{variant}' in detail
            assert ('Zeilen' if locale == 'de' else 'Lines') in detail
