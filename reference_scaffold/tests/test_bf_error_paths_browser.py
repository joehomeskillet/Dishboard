"""BF-04/BF-05/BF-09: stock, basket and costing errors keep inputs.

Direct posts bypass HTML ``required``. Browser checks cover JavaScript on and off.
Real zero stays allowed for a count; a movement of zero is rejected by the store.
"""
from __future__ import annotations

from decimal import Decimal
from threading import Thread
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from cafeteria import roles
from cafeteria.order_basket_store import create_basket, get_basket, replace_basket_lines
from cafeteria.shopping_list_reads import ShoppingScope
from cafeteria.supplier_store import create_article, create_supplier
from prepared_food_fixtures import create_food, create_recipe, freeze
from test_master_data_db import (  # noqa: F401
    STORAGE_PUBLIC_ID, app_engine, installed_pg16, pg16, seeded_pg16,
)
from test_master_data_routes import Forms, b3, create  # noqa: F401
from test_order_admin import OrderForms


@pytest.mark.parametrize('endpoint', ['vorschau', 'beleg'])
@pytest.mark.parametrize('failure', [KeyError, ValueError, DBAPIError])
def test_unexpected_cost_error_never_discloses_internal_text(b3, monkeypatch, endpoint, failure):  # noqa: F811
    from cafeteria.admin import cost_routes

    app, _, client, _ = b3
    app.config['PROPAGATE_EXCEPTIONS'] = False

    def fail(*args, **kwargs):
        if failure is DBAPIError:
            raise DBAPIError('private_sql_marker', {}, RuntimeError('private_driver_marker'))
        raise failure('private_internal_marker')

    monkeypatch.setattr(cost_routes, 'project_recipe', fail)
    response = client.post('/admin/kalkulation/' + endpoint, data={
        '_csrf': 'b3-test-csrf', 'kind': 'recipe',
        'revision_public_id': '11111111-1111-4111-8111-111111111111', 'as_of': '2026-09-30',
    })
    assert 'private_' not in response.text
    assert response.status_code == (503 if failure is DBAPIError else 500)


def _stock(owner, food_id: str, storage_id: str) -> Decimal:
    with owner.connect() as connection:
        value = connection.execute(text('''
            SELECT COALESCE(SUM(m.sign * m.normalized_base_quantity), 0)
            FROM cafeteria.inventory_accounts a
            JOIN cafeteria.foods f ON f.id = a.food_id
            JOIN cafeteria.storage_locations s ON s.id = a.storage_location_id
            LEFT JOIN cafeteria.inventory_movements m ON m.account_id = a.id
            WHERE f.public_id = CAST(:food AS uuid) AND s.public_id = CAST(:storage AS uuid)
        '''), {'food': food_id, 'storage': storage_id}).scalar_one()
    return Decimal(str(value))


@pytest.mark.parametrize('field,value,message,target', [
    ('food_public_id', '11111111-1111-4111-8111-111111111111', 'Lebensmittel nicht gefunden.', 'lager-selection'),
    ('storage_public_id', '11111111-1111-4111-8111-111111111111', 'Lagerort nicht gefunden.', 'lager-selection'),
    ('unit_code', 'MISSING', 'Einheit ist unbekannt.', 'unit_code'),
])
def test_missing_inventory_reference_has_its_own_error(b3, field, value, message, target):  # noqa: F811
    ctx = _setup(b3)
    form = _forms(ctx['client'], ctx['lager'])['/admin/lager/bewegung']
    form['quantity'] = '3.25'
    form[field] = value
    response = ctx['client'].post('/admin/lager/bewegung', data=form)
    assert response.status_code == 400
    assert message in response.text
    assert f'id="{target}-error"' in response.text
    assert _movements(ctx['owner']) == 0


def _movements(owner) -> int:
    with owner.connect() as connection:
        return int(connection.execute(text(
            'SELECT count(*) FROM cafeteria.inventory_movements')).scalar_one())


@pytest.mark.parametrize('action,field', [
    ('bewegung', 'food_public_id'), ('bewegung', 'storage_public_id'),
    ('umbuchung', 'source_storage_public_id'), ('umbuchung', 'dest_storage_public_id'),
    ('zaehlung', 'food_public_id'), ('zaehlung', 'storage_public_id'),
])
def test_invalid_inventory_uuid_rerenders_without_500(b3, action, field):  # noqa: F811
    ctx = _setup(b3)
    ctx['app'].config['PROPAGATE_EXCEPTIONS'] = False
    path = '/admin/lager/' + action
    form = _forms(ctx['client'], ctx['lager'])[path]
    form['quantity' if action != 'zaehlung' else 'counted_quantity'] = '3.25'
    form[field] = 'invalid-uuid'
    response = ctx['client'].post(path, data=form)
    assert response.status_code == 400
    target = 'dest_storage_public_id' if field == 'dest_storage_public_id' else 'lager-selection'
    assert f'id="{target}-error"' in response.text
    assert 'Ungültige Kennung.' in response.text
    assert _movements(ctx['owner']) == 0


def _location(owner) -> int:
    with owner.connect() as connection:
        return int(connection.execute(text(
            'SELECT id FROM cafeteria.locations WHERE active')).scalar_one())


@pytest.mark.parametrize('adder', [False, True])
def test_inactive_article_keeps_basket_inputs(b3, adder):  # noqa: F811
    ctx = _setup(b3)
    client, path = ctx['client'], ctx['basket']
    form = OrderForms(client.get(path).text).forms[path]
    if adder:
        form.setlist('article_public_id', [ctx['article_id'], ctx['article_id']])
    form.setlist('quantity', ['7.25', '4.5' if adder else ''])
    form.setlist('raw_quantity', ['1.5', '3.5' if adder else ''])
    with ctx['owner'].begin() as connection:
        connection.execute(text('UPDATE cafeteria.supplier_articles SET active=false WHERE public_id=CAST(:id AS uuid)'),
                           {'id': ctx['article_id']})
    response = client.post(path, data=form)
    assert response.status_code == 400
    assert 'Artikel nicht gefunden.' in response.text
    kept = OrderForms(response.text).forms[path]
    for field in ('article_public_id', 'quantity', 'raw_quantity', 'row_version'):
        assert kept.getlist(field) == form.getlist(field)
    assert get_basket(ctx['engine'], ctx['location'], ctx['basket_id'])['lines'][0]['quantity'] == Decimal('2')


@pytest.mark.parametrize('field,index,value,target', [
    ('raw_quantity', 0, 'abc', 'line-raw-0'),
    ('quantity', 1, 'abc', 'line-qty-new'),
    ('raw_quantity', 1, '-1', 'line-raw-new'),
    ('article_public_id', 1, 'invalid-uuid', 'line-article-new'),
    ('row_version', 0, 'abc', 'basket-save'),
])
def test_basket_parse_error_targets_actual_field(b3, field, index, value, target):  # noqa: F811
    ctx = _setup(b3)
    path = ctx['basket']
    form = OrderForms(ctx['client'].get(path).text).forms[path]
    form.setlist('article_public_id', [ctx['article_id'], ctx['article_id']])
    form.setlist('quantity', ['3.25', '4.5'])
    form.setlist('raw_quantity', ['1.5', '2.5'])
    values = form.getlist(field)
    values[index] = value
    form.setlist(field, values)
    response = ctx['client'].post(path, data=form)
    assert response.status_code == 400
    assert f'id="{target}-error"' in response.text
    assert f'href="#{target}"' in response.text
    kept = OrderForms(response.text).forms[path]
    for name in ('quantity', 'raw_quantity', 'article_public_id', 'row_version'):
        assert kept.getlist(name) == form.getlist(name)


@pytest.mark.parametrize('field,value,target,message', [
    ('as_of', '2026-02-30', 'as_of', 'Stichtag ist ungültig.'),
    ('as_of', 'not-a-date', 'as_of', 'Stichtag ist ungültig.'),
    ('menu_revision_public_id', 'invalid-uuid', 'menu_revision_public_id', 'Rezeptrevision ist ungültig.'),
])
@pytest.mark.parametrize('endpoint', ['vorschau', 'beleg'])
def test_cost_parse_error_targets_actual_field(b3, field, value, target, message, endpoint):  # noqa: F811
    _, _, client, _ = b3
    data = {'_csrf': 'b3-test-csrf', 'kind': 'menu', 'as_of': '2026-09-30',
            'revision_public_id': '11111111-1111-4111-8111-111111111111', field: value}
    response = client.post('/admin/kalkulation/' + endpoint, data=data)
    assert response.status_code == 400
    assert f'id="{target}-error"' in response.text
    assert f'href="#{target}"' in response.text
    assert message in response.text
    assert f'value="{value}"' in response.text


def _setup(b3):  # noqa: F811
    app, owner, client, actor = b3
    other = urlsplit(create(
        client, 'lagerorte', name='Zweitlager', code='SECOND', sort_order='2',
    )).path.rstrip('/').rsplit('/', 1)[-1]
    create(client, name='Zweitzutat', storage_location_public_ids=other)
    food_id = urlsplit(create(client, name='Fehlerpfadmehl')).path.rstrip('/').rsplit('/', 1)[-1]
    engine = app.extensions['cafeteria_db']
    location = _location(owner)
    scope = ShoppingScope(actor.user_id, location, actor.authz_version)
    supplier = create_supplier(engine, actor, {'code': 'FEH', 'name': 'Fehlerhof'})
    article = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': None,
        'article_code': 'FEHL-1', 'name': 'Fehlerartikel', 'order_unit_code': 'KG',
        'pack_size': '1', 'preferred': False,
    })
    basket_id = create_basket(engine, scope, supplier.public_id)
    replace_basket_lines(
        engine, scope, basket_id,
        expected_row_version=get_basket(engine, location, basket_id)['row_version'],
        lines=[{'article_public_id': article.public_id, 'quantity': '2', 'raw_quantity': '1'}],
    )
    return {
        'app': app, 'owner': owner, 'client': client, 'actor': actor, 'engine': engine,
        'location': location, 'scope': scope, 'food_id': food_id, 'other': other,
        'basket_id': basket_id, 'article_id': article.public_id,
        'lager': f'/admin/lager?food_public_id={food_id}&storage_public_id={STORAGE_PUBLIC_ID}',
        'basket': f'/admin/bestellung/korb/{basket_id}',
    }


def _forms(client, path: str):
    response = client.get(path)
    assert response.status_code == 200, response.status_code
    return Forms(response.get_data(as_text=True)).forms


@pytest.mark.parametrize('action,field,value,message', [
    ('bewegung', 'quantity', '', 'Menge ist erforderlich.'),
    ('bewegung', 'quantity', 'abc', 'Menge muss eine Zahl sein.'),
    ('bewegung', 'quantity', '0', 'Menge muss positiv sein.'),
    ('umbuchung', 'quantity', '', 'Menge ist erforderlich.'),
    ('umbuchung', 'quantity', 'abc', 'Menge muss eine Zahl sein.'),
    ('umbuchung', 'quantity', '0', 'Menge muss positiv sein.'),
    ('zaehlung', 'counted_quantity', '', 'Menge ist erforderlich.'),
    ('zaehlung', 'counted_quantity', '   ', 'Menge ist erforderlich.'),
    ('zaehlung', 'counted_quantity', 'xyz', 'Menge muss eine Zahl sein.'),
    ('zaehlung', 'counted_quantity', '-1', 'Zählmenge darf nicht negativ sein.'),
])
def test_direct_quantity_rejection_keeps_input(b3, action, field, value, message):  # noqa: F811
    ctx = _setup(b3)
    path = '/admin/lager/' + action
    form = _forms(ctx['client'], ctx['lager'])[path]
    form[field] = value
    response = ctx['client'].post(path, data=form)
    assert response.status_code == 400
    assert Forms(response.text).forms[path][field] == value
    assert message in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert _movements(ctx['owner']) == 0


def test_inventory_insufficient_and_real_zero_are_distinct(b3):  # noqa: F811
    ctx = _setup(b3)
    client, owner = ctx['client'], ctx['owner']
    forms = _forms(client, ctx['lager'])
    transfer = forms['/admin/lager/umbuchung']
    transfer['quantity'] = '1'
    response = client.post('/admin/lager/umbuchung', data=transfer)
    assert response.status_code == 409
    assert Forms(response.text).forms['/admin/lager/umbuchung']['quantity'] == '1'
    assert 'Bestand würde negativ.' in response.text and 'id="lager-more" open' in response.text
    assert _movements(owner) == 0
    move = forms['/admin/lager/bewegung']
    move['quantity'] = '2'
    assert client.post('/admin/lager/bewegung', data=move).status_code == 303
    assert _stock(owner, ctx['food_id'], STORAGE_PUBLIC_ID) == Decimal('2')
    count = _forms(client, ctx['lager'])['/admin/lager/zaehlung']
    count['counted_quantity'] = ''
    before = _movements(owner)
    rejected = client.post('/admin/lager/zaehlung', data=count)
    assert rejected.status_code == 400 and 'Menge ist erforderlich.' in rejected.text
    assert _stock(owner, ctx['food_id'], STORAGE_PUBLIC_ID) == Decimal('2')
    assert _movements(owner) == before
    count['counted_quantity'] = '0'
    assert client.post('/admin/lager/zaehlung', data=count).status_code == 303
    assert _stock(owner, ctx['food_id'], STORAGE_PUBLIC_ID) == Decimal('0')


@pytest.mark.parametrize('denial', ['csrf', 'permission'])
def test_error_rerender_preserves_security_boundary(b3, monkeypatch, denial):  # noqa: F811
    ctx = _setup(b3)
    form = _forms(ctx['client'], ctx['lager'])['/admin/lager/bewegung']
    form['quantity'] = '4'
    if denial == 'csrf':
        form['_csrf'] = 'wrong'
    else:
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    response = ctx['client'].post('/admin/lager/bewegung', data=form)
    assert response.status_code == (400 if denial == 'csrf' else 403)
    assert 'id="lager-move-form"' not in response.text
    assert _movements(ctx['owner']) == 0


def test_basket_conflict_keeps_original_version_and_quantities(b3):  # noqa: F811
    ctx = _setup(b3)
    client, path = ctx['client'], ctx['basket']
    stale = OrderForms(client.get(path).text).forms[path]
    current = MultiDict(stale)
    current.setlist('quantity', ['3', ''])
    assert client.post(path, data=current).status_code == 303
    stale.setlist('quantity', ['9.5', ''])
    response = client.post(path, data=stale)
    assert response.status_code == 409
    returned = OrderForms(response.text).forms[path]
    assert returned.getlist('quantity') == ['9.5', '']
    assert returned['row_version'] == stale['row_version']
    assert 'zwischenzeitlich' in response.text
    assert get_basket(ctx['engine'], ctx['location'], ctx['basket_id'])['lines'][0]['quantity'] == Decimal('3')


@pytest.mark.parametrize('food,quantity,target', [
    ('11111111-1111-4111-8111-111111111111', 'abc', 'need_quantity'),
    ('invalid-uuid', '3.25', 'demand_food'),
])
def test_demand_error_keeps_both_values(b3, food, quantity, target):  # noqa: F811
    ctx = _setup(b3)
    path = ctx['basket'] + '/bedarf'
    form = OrderForms(ctx['client'].get(ctx['basket']).text).forms[path]
    form['food_public_id'], form['need_quantity'] = food, quantity
    response = ctx['client'].post(path, data=form)
    assert response.status_code == 400
    kept = OrderForms(response.text).forms[path]
    assert kept['food_public_id'] == food and kept['need_quantity'] == quantity
    assert f'id="{target}-error"' in response.text
    assert 'id="korb-weitere" open' in response.text


def test_cost_input_error_keeps_kind_revision_and_extra(b3):  # noqa: F811
    _, _, client, _ = b3
    response = client.post('/admin/kalkulation/vorschau', data={
        '_csrf': 'b3-test-csrf', 'kind': 'prepared', 'revision_public_id': 'nicht-eine-uuid',
        'as_of': '2026-09-17', 'menu_revision_public_id': 'extra-wert',
    })
    assert response.status_code == 400
    assert 'value="nicht-eine-uuid"' in response.text and 'value="extra-wert"' in response.text
    assert 'value="prepared" selected' in response.text and 'id="cost-options" open' in response.text


def test_cost_receipt_conflict_keeps_inputs_without_second_receipt(b3):  # noqa: F811
    ctx = _setup(b3)
    ids = {'actor': ctx['actor'].user_id, 'authz': ctx['actor'].authz_version,
           'location': ctx['location'], 'storage': STORAGE_PUBLIC_ID}
    food = create_food(ctx['engine'], ids, 'Kalkmehl', unit='G')
    frozen = freeze(ctx['engine'], ids, create_recipe(ctx['engine'], ids, [food], name='Kalksuppe'))
    data = {'_csrf': 'b3-test-csrf', 'kind': 'recipe', 'revision_public_id': frozen['public_id'],
            'as_of': '2026-09-01', 'menu_revision_public_id': ''}
    assert ctx['client'].post('/admin/kalkulation/beleg', data=data).status_code == 303
    data['as_of'] = '2026-09-02'
    response = ctx['client'].post('/admin/kalkulation/beleg', data=data)
    assert response.status_code == 409
    assert 'value="2026-09-02"' in response.text and frozen['public_id'] in response.text
    assert 'anderem Inhalt' in response.text
    with ctx['owner'].connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.calculation_receipts')).scalar_one() == 1


@pytest.mark.parametrize('javascript', [False, True], ids=['nojs', 'js'])
@pytest.mark.parametrize('case', ['move', 'transfer', 'count', 'basket', 'cost', 'new_raw', 'inactive', 'cost_extra'])
def test_browser_keeps_error_inputs_with_and_without_javascript(b3, javascript, case, tmp_path):  # noqa: F811
    ctx = _setup(b3)
    app, client = ctx['app'], ctx['client']
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                with browser.new_context(viewport={'width': 1440, 'height': 900},
                                         java_script_enabled=javascript, reduced_motion='reduce', locale='de-CH') as context:
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
                    page = context.new_page()
                    page.set_default_timeout(5000)

                    def post_status(button):
                        with page.expect_response(lambda item: item.request.method == 'POST') as caught:
                            button.click()
                        return caught.value.status

                    if case in ('move', 'transfer', 'count'):
                        assert page.goto(origin + ctx['lager']).status == 200
                        if case == 'move':
                            _move(page, origin, ctx, post_status)
                        elif case == 'transfer':
                            _transfer(page, post_status)
                        else:
                            page.locator('#lager-more > summary').click()
                            _count(page, post_status)
                    elif case == 'basket':
                        _basket(page, origin, ctx, client, post_status)
                    elif case == 'cost':
                        _cost(page, origin, post_status)
                    else:
                        _review_browser_case(case, page, origin, ctx, post_status)
                    for width, height in ((1440, 900), (390, 844)):
                        page.set_viewport_size({'width': width, 'height': height})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        page.screenshot(path=str(tmp_path / f'{case}-{width}.png'), full_page=True)
                    _narrow(page)
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _review_browser_case(case, page, origin, ctx, post_status):
    if case == 'cost_extra':
        page.goto(origin + '/admin/kalkulation')
        page.locator('#revision_public_id').fill('11111111-1111-4111-8111-111111111111')
        page.locator('#kind').select_option('menu')
        page.locator('#cost-options > summary').click()
        page.locator('#menu_revision_public_id').fill('invalid-extra')
        assert post_status(page.locator('main .btn-primary')) == 400
        expect(page.locator('#menu_revision_public_id-error')).to_be_visible()
        expect(page.locator('#menu_revision_public_id')).to_have_value('invalid-extra')
        return
    page.goto(origin + ctx['basket'])
    version = page.locator('#basket-save [name="row_version"]').input_value()
    if case == 'new_raw':
        page.locator('#line-article-new').select_option(ctx['article_id'])
        page.locator('#line-qty-new').fill('4.5')
        page.locator('#line-raw-new').fill('abc')
    else:
        page.locator('#line-qty-0').fill('7.25')
        with ctx['owner'].begin() as connection:
            connection.execute(text('UPDATE cafeteria.supplier_articles SET active=false WHERE public_id=CAST(:id AS uuid)'),
                               {'id': ctx['article_id']})
    assert post_status(page.locator('#basket-save button[type="submit"]')) == 400
    expect(page.locator('#basket-save [name="row_version"]')).to_have_value(version)
    if case == 'new_raw':
        expect(page.locator('#line-raw-new-error')).to_contain_text('Zahl')
        expect(page.locator('#line-qty-new')).to_have_value('4.5')
        expect(page.locator('#line-raw-new')).to_have_value('abc')
        expect(page.locator('#line-article-new')).to_have_value(ctx['article_id'])
    else:
        expect(page.locator('#basket-save-error')).to_contain_text('Artikel nicht gefunden.')
        expect(page.locator('#line-qty-0')).to_have_value('7.25')


def _move(page, origin, ctx, post_status) -> None:
    assert page.goto(origin + ctx['lager'], wait_until='load').status == 200
    page.locator('#quantity').fill('0')
    status = post_status(page.locator('#lager-move-form button[type="submit"]'))
    assert status == 400
    expect(page.locator('#quantity')).to_have_value('0')
    expect(page.locator('#quantity-error')).to_contain_text('positiv')
    expect(page.locator('.error-region a[href="#quantity"]')).to_be_visible()


def _transfer(page, post_status) -> None:
    page.locator('#lager-more > summary').click()
    page.locator('#transfer_qty').fill('abc')
    status = post_status(page.locator('#lager-transfer-form button[type="submit"]'))
    assert status == 400
    expect(page.locator('#transfer_qty')).to_have_value('abc')
    expect(page.locator('#lager-more')).to_have_attribute('open', '')
    expect(page.locator('#transfer_qty-error')).to_contain_text('Zahl')


def _count(page, post_status) -> None:
    page.locator('#counted_quantity').fill('xyz')
    status = post_status(page.locator('#lager-count-form button[type="submit"]'))
    assert status == 400
    expect(page.locator('#counted_quantity')).to_have_value('xyz')
    expect(page.locator('#counted_quantity-error')).to_contain_text('Zahl')


def _basket(page, origin, ctx, client, post_status) -> None:
    assert page.goto(origin + ctx['basket'], wait_until='load').status == 200
    version = page.locator('form.order-basket-form input[name="row_version"]').input_value()
    page.locator('#line-qty-0').fill('7.25')
    current = OrderForms(client.get(ctx['basket']).get_data(as_text=True)).forms[ctx['basket']]
    current.setlist('quantity', ['3', ''])
    assert client.post(ctx['basket'], data=current).status_code == 303
    status = post_status(page.locator('form.order-basket-form button[type="submit"]'))
    assert status == 409
    expect(page.locator('#line-qty-0')).to_have_value('7.25')
    expect(page.locator('form.order-basket-form input[name="row_version"]')).to_have_value(version)
    expect(page.locator('#basket-save-error')).to_contain_text('zwischenzeitlich')
    expect(page.locator('#line-qty-0')).not_to_have_attribute('aria-invalid', 'true')


def _cost(page, origin, post_status) -> None:
    assert page.goto(origin + '/admin/kalkulation', wait_until='load').status == 200
    page.locator('#revision_public_id').fill('nicht-eine-uuid')
    page.locator('#kind').select_option('menu')
    page.locator('#cost-options > summary').click()
    page.locator('#menu_revision_public_id').fill('extra-wert')
    status = post_status(page.locator('main .btn-primary'))
    assert status == 400
    expect(page.locator('#revision_public_id')).to_have_value('nicht-eine-uuid')
    expect(page.locator('#kind')).to_have_value('menu')
    expect(page.locator('#menu_revision_public_id')).to_have_value('extra-wert')
    expect(page.locator('#revision_public_id-error')).to_be_visible()


def _narrow(page) -> None:
    page.set_viewport_size({'width': 360, 'height': 800})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for control in page.locator('main :is(.btn, .form-control, .form-select):visible').all():
        box = control.bounding_box()
        minimum = control.evaluate("e => parseFloat(getComputedStyle(e).getPropertyValue('--app-control-min-height'))")
        assert box is not None and box['height'] + 0.5 >= minimum
