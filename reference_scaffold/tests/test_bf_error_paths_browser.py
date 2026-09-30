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
    assert response.status_code == 500


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


def _post(client, action: str, source: MultiDict, **overrides):
    data = MultiDict(source)
    for key, value in overrides.items():
        data[key] = value
    try:
        return client.post(action, data=data), None
    except Exception as error:
        return None, error


def _note(problems: list[str], label: str, ok: bool, detail: str) -> None:
    if not ok:
        problems.append(f'{label}: {detail}')


def _html_forms(response):
    return Forms(response.get_data(as_text=True)).forms


def test_direct_posts_keep_inputs_and_reject_empty_quantities(b3, monkeypatch):  # noqa: F811
    ctx = _setup(b3)
    client, owner, food_id = ctx['client'], ctx['owner'], ctx['food_id']
    forms = _forms(client, ctx['lager'])
    move, transfer, count = (
        forms['/admin/lager/bewegung'], forms['/admin/lager/umbuchung'], forms['/admin/lager/zaehlung'],
    )
    problems: list[str] = []

    def reject(label: str, action: str, source: MultiDict, field: str, value: str,
               message: str, status: int = 400):
        before = _movements(owner)
        response, error = _post(client, action, source, **{field: value} if field != 'counted_quantity'
                                else {'counted_quantity': value})
        if field == 'quantity' and action.endswith('/zaehlung'):
            response, error = _post(client, action, source, counted_quantity=value)
        if error is not None:
            problems.append(f'{label}: raised {type(error).__name__}: {error}')
            return
        _note(problems, label, response.status_code == status,
              f'status {response.status_code} body {response.get_data(as_text=True)[:240]}')
        if response.status_code != status:
            return
        parsed = _html_forms(response)
        kept = parsed[action].get(field if action.endswith('/zaehlung') or field != 'quantity' else 'quantity', '')
        if action.endswith('/zaehlung'):
            kept = parsed[action].get('counted_quantity', '')
        elif field == 'quantity':
            kept = parsed[action].get('quantity', '')
        _note(problems, f'{label} value', kept == value, repr(kept))
        text = response.get_data(as_text=True)
        _note(problems, f'{label} message', message in text, 'missing message')
        _note(problems, f'{label} store', response.headers.get('Cache-Control') == 'no-store',
              response.headers.get('Cache-Control', ''))
        _note(problems, f'{label} movements', _movements(owner) == before, str(_movements(owner)))

    reject('empty move', '/admin/lager/bewegung', move, 'quantity', '', 'Menge ist erforderlich.')
    reject('text move', '/admin/lager/bewegung', move, 'quantity', 'abc', 'Menge muss eine Zahl sein.')
    reject('zero move', '/admin/lager/bewegung', move, 'quantity', '0', 'Menge muss positiv sein.')
    reject('blank count', '/admin/lager/zaehlung', count, 'counted_quantity', '   ', 'Menge ist erforderlich.')
    reject('text count', '/admin/lager/zaehlung', count, 'counted_quantity', 'xyz', 'Menge muss eine Zahl sein.')
    reject('empty transfer', '/admin/lager/umbuchung', transfer, 'quantity', '', 'Menge ist erforderlich.')
    reject('text transfer', '/admin/lager/umbuchung', transfer, 'quantity', 'abc', 'Menge muss eine Zahl sein.')
    _note(problems, 'no stock yet', _stock(owner, food_id, STORAGE_PUBLIC_ID) == 0, 'stock changed')

    response, error = _post(client, '/admin/lager/umbuchung', transfer, quantity='1')
    if error is not None:
        problems.append(f'insufficient transfer: {type(error).__name__}: {error}')
    else:
        _note(problems, 'insufficient transfer', response.status_code == 409, str(response.status_code))
        if response.status_code == 409:
            page = response.get_data(as_text=True)
            _note(problems, 'insufficient value', _html_forms(response)['/admin/lager/umbuchung']['quantity'] == '1',
                  'quantity lost')
            _note(problems, 'insufficient copy', 'Bestand würde negativ.' in page, 'missing copy')
            _note(problems, 'insufficient open', 'id="lager-more" open' in page, 'disclosure closed')
        _note(problems, 'insufficient stock', _movements(owner) == 0, str(_movements(owner)))

    booked, error = _post(client, '/admin/lager/bewegung', move, quantity='2')
    if error is not None:
        problems.append(f'receipt: {type(error).__name__}: {error}')
    else:
        _note(problems, 'receipt', booked.status_code == 303, str(booked.status_code))
        _note(problems, 'receipt stock', _stock(owner, food_id, STORAGE_PUBLIC_ID) == Decimal('2'),
              str(_stock(owner, food_id, STORAGE_PUBLIC_ID)))
    forms = _forms(client, ctx['lager'])
    count = forms['/admin/lager/zaehlung']
    reject('empty count', '/admin/lager/zaehlung', count, 'counted_quantity', '', 'Menge ist erforderlich.')
    _note(problems, 'empty count keeps two', _stock(owner, food_id, STORAGE_PUBLIC_ID) == Decimal('2'),
          str(_stock(owner, food_id, STORAGE_PUBLIC_ID)))
    zero, error = _post(client, '/admin/lager/zaehlung', count, counted_quantity='0')
    if error is not None:
        problems.append(f'zero count: {type(error).__name__}: {error}')
    else:
        _note(problems, 'zero count', zero.status_code == 303, str(zero.status_code))
        _note(problems, 'zero stock', _stock(owner, food_id, STORAGE_PUBLIC_ID) == Decimal('0'),
              str(_stock(owner, food_id, STORAGE_PUBLIC_ID)))

    forged, error = _post(client, '/admin/lager/bewegung', move, quantity='4', _csrf='wrong')
    if error is not None:
        problems.append(f'csrf: {type(error).__name__}: {error}')
    else:
        _note(problems, 'csrf', forged.status_code == 400, str(forged.status_code))
        _note(problems, 'csrf form', 'id="lager-move-form"' not in forged.get_data(as_text=True), 'form rendered')

    basket = ctx['basket']
    order_forms = OrderForms(client.get(basket).get_data(as_text=True)).forms
    stale = MultiDict(order_forms[basket])
    current = MultiDict(order_forms[basket])
    current.setlist('quantity', ['3', ''])
    saved = client.post(basket, data=current)
    _note(problems, 'basket save', saved.status_code == 303, str(saved.status_code))
    stale.setlist('quantity', ['9.5', ''])
    conflict, error = None, None
    try:
        conflict = client.post(basket, data=stale)
    except Exception as raised:
        error = raised
    if error is not None:
        problems.append(f'basket conflict: {type(error).__name__}: {error}')
    else:
        _note(problems, 'basket conflict', conflict.status_code == 409, str(conflict.status_code))
        if conflict.status_code == 409:
            returned = OrderForms(conflict.get_data(as_text=True)).forms[basket]
            _note(problems, 'basket value', returned.getlist('quantity')[0] == '9.5',
                  repr(returned.getlist('quantity')))
            _note(problems, 'basket version', returned['row_version'] == stale['row_version'],
                  returned.get('row_version', ''))
            _note(problems, 'basket copy', 'zwischenzeitlich' in conflict.get_data(as_text=True), 'missing copy')
    stored = get_basket(ctx['engine'], ctx['location'], ctx['basket_id'])
    _note(problems, 'basket unchanged', stored['lines'][0]['quantity'] == Decimal('3'),
          str(stored['lines'][0]['quantity']))

    demand = MultiDict(order_forms[basket + '/bedarf'])
    demand['food_public_id'] = '11111111-1111-4111-8111-111111111111'
    demand['need_quantity'] = 'abc'
    demand_response, error = None, None
    try:
        demand_response = client.post(basket + '/bedarf', data=demand)
    except Exception as raised:
        error = raised
    if error is not None:
        problems.append(f'demand: {type(error).__name__}: {error}')
    else:
        _note(problems, 'demand', demand_response.status_code == 400, str(demand_response.status_code))
        if demand_response.status_code == 400:
            parsed = OrderForms(demand_response.get_data(as_text=True)).forms[basket + '/bedarf']
            _note(problems, 'demand food', parsed['food_public_id'] == demand['food_public_id'],
                  parsed.get('food_public_id', ''))
            _note(problems, 'demand qty', parsed['need_quantity'] == 'abc', parsed.get('need_quantity', ''))
            _note(problems, 'demand open', 'id="korb-weitere" open' in demand_response.get_data(as_text=True),
                  'disclosure closed')

    preview, error = None, None
    try:
        preview = client.post('/admin/kalkulation/vorschau', data={
            '_csrf': 'b3-test-csrf', 'kind': 'prepared', 'revision_public_id': 'nicht-eine-uuid',
            'as_of': '2026-09-17', 'menu_revision_public_id': 'extra-wert',
        })
    except Exception as raised:
        error = raised
    if error is not None:
        problems.append(f'cost preview: {type(error).__name__}: {error}')
    else:
        body = preview.get_data(as_text=True)
        _note(problems, 'cost preview', preview.status_code == 400, str(preview.status_code))
        _note(problems, 'cost value', 'value="nicht-eine-uuid"' in body, 'uuid lost')
        _note(problems, 'cost extra', 'value="extra-wert"' in body, 'extra lost')
        _note(problems, 'cost kind', 'value="prepared" selected' in body, 'kind lost')
        _note(problems, 'cost open', 'id="cost-options" open' in body, 'disclosure closed')

    try:
        ids = {
            'actor': ctx['actor'].user_id, 'authz': ctx['actor'].authz_version,
            'location': ctx['location'], 'storage': STORAGE_PUBLIC_ID,
        }
        recipe_food = create_food(ctx['engine'], ids, 'Kalkmehl', unit='G')
        frozen = freeze(ctx['engine'], ids, create_recipe(ctx['engine'], ids, [recipe_food], name='Kalksuppe'))
        first = client.post('/admin/kalkulation/beleg', data={
            '_csrf': 'b3-test-csrf', 'kind': 'recipe', 'revision_public_id': frozen['public_id'],
            'as_of': '2026-09-01', 'menu_revision_public_id': '',
        })
        _note(problems, 'cost confirm', first.status_code == 303, str(first.status_code))
        second = client.post('/admin/kalkulation/beleg', data={
            '_csrf': 'b3-test-csrf', 'kind': 'recipe', 'revision_public_id': frozen['public_id'],
            'as_of': '2026-09-02', 'menu_revision_public_id': '',
        })
        body = second.get_data(as_text=True)
        _note(problems, 'cost conflict', second.status_code == 409, str(second.status_code))
        _note(problems, 'cost date', 'value="2026-09-02"' in body, 'date lost')
        _note(problems, 'cost revision', frozen['public_id'] in body, 'revision lost')
        _note(problems, 'cost conflict copy', 'anderem Inhalt' in body, 'missing copy')
        with owner.connect() as connection:
            receipts = connection.execute(text(
                'SELECT count(*) FROM cafeteria.calculation_receipts')).scalar_one()
        _note(problems, 'one receipt', receipts == 1, str(receipts))
    except Exception as raised:
        problems.append(f'cost conflict setup: {type(raised).__name__}: {raised}')

    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    denied, error = _post(client, '/admin/lager/bewegung', move, quantity='1')
    if error is not None:
        problems.append(f'forbidden: {type(error).__name__}: {error}')
    else:
        _note(problems, 'forbidden', denied.status_code == 403, str(denied.status_code))
    assert problems == [], problems


def test_browser_keeps_error_inputs_with_and_without_javascript(b3):  # noqa: F811
    ctx = _setup(b3)
    app, client = ctx['app'], ctx['client']
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    origin = f'http://127.0.0.1:{server.server_port}'
    problems: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                for javascript in (False, True):
                    label = 'js' if javascript else 'nojs'
                    context = browser.new_context(
                        viewport={'width': 1440, 'height': 900}, java_script_enabled=javascript,
                        reduced_motion='reduce', locale='de-CH',
                    )
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
                    page = context.new_page()
                    page.set_default_timeout(5000)
                    _browser_case(problems, label, page, origin, ctx, client)
                    context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert problems == [], problems


def _browser_case(problems, label, page, origin, ctx, client) -> None:
    def check(name, fn) -> None:
        try:
            fn()
        except Exception as error:
            problems.append(f'{label} {name}: {type(error).__name__}: {error}')

    def post_status(button):
        with page.expect_response(lambda item: item.request.method == 'POST', timeout=5000) as caught:
            button.click()
        return caught.value.status

    check('move', lambda: _move(page, origin, ctx, post_status))
    check('transfer', lambda: _transfer(page, post_status))
    check('count', lambda: _count(page, post_status))
    check('basket', lambda: _basket(page, origin, ctx, client, post_status))
    check('cost', lambda: _cost(page, origin, post_status))
    check('narrow', lambda: _narrow(page))


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
    expect(page.locator('#line-qty-0-error')).to_contain_text('zwischenzeitlich')


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
        minimum = 36 if 'ui-sem-control' in (control.get_attribute('class') or '') else 48
        assert box is not None and box['height'] + 0.5 >= minimum
