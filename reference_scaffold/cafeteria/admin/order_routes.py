"""Order draft UI: catalog, basket, CSV download. No send."""
from __future__ import annotations

from decimal import InvalidOperation

from flask import Response, current_app, flash, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response as WerkzeugResponse

from ..calendar_event_store import CalendarEventConflictError, CalendarEventValidationError
from ..order_basket_store import (
    OrderBasketConflictError, OrderBasketError, create_basket, fill_from_demand, get_basket, list_baskets,
    replace_basket_lines,
)
from ..order_csv import basket_csv_bytes
from ..recipe_reads import get_location
from ..roles import require_capability
from ..security import validate_csrf
from ..shopping_list_reads import ShoppingScope
from ..supplier_store import create_article, create_supplier, list_articles, list_suppliers
from ..auth.local_users import ActorExpectation
from .routes import bp


def _db():
    return current_app.extensions['cafeteria_db']


def _scope() -> ShoppingScope:
    return ShoppingScope(g.auth_user.user_id, get_location(_db()), g.auth_user.authz_version)


def _actor() -> ActorExpectation:
    return ActorExpectation(g.auth_user.user_id, g.auth_user.authz_version)


def _basket_message(error: BaseException) -> str:
    if isinstance(error, InvalidOperation):
        return 'Menge muss eine Zahl sein.'
    raw = str(error)
    lowered = raw.casefold()
    if 'hexadecimal' in lowered or 'uuid' in lowered:
        return 'Ungültige Kennung.'
    return raw


def _save_field(error: BaseException, message: str, has_lines: bool) -> str:
    raw_id = 'line-raw-0' if has_lines else 'line-raw-new'
    qty_id = 'line-qty-0' if has_lines else 'line-qty-new'
    if 'rohmenge' in message.casefold():
        return raw_id
    if isinstance(error, InvalidOperation) and 'raw' in message.casefold():
        return raw_id
    return qty_id


def _demand_field(error: BaseException, message: str) -> str:
    lowered = message.casefold()
    if isinstance(error, InvalidOperation) or any(
        token in lowered for token in ('rohmenge', 'zahl', 'positiv', 'negativ')
    ):
        return 'need_quantity'
    return 'demand_food'


def _view_line(code: str, qty: str, raw: str, basket: dict, articles: tuple) -> dict[str, str]:
    known = next((line for line in basket['lines'] if str(line['article_public_id']) == code), None)
    catalog = next((row for row in articles if str(row['public_id']) == code), None)
    source = known or catalog or {}
    return {
        'article_public_id': code,
        'article_name': source.get('article_name') or source.get('name') or code,
        'article_code': source.get('article_code') or '',
        'quantity': qty,
        'raw_quantity': raw,
        'pack_size': '' if source.get('pack_size') is None else str(source.get('pack_size')),
        'order_unit_code': source.get('order_unit_code') or '',
    }


def _split_posted(basket: dict, articles: tuple) -> tuple[list[dict[str, str]], dict[str, str]]:
    codes = request.form.getlist('article_public_id')
    qtys = request.form.getlist('quantity')
    raws = request.form.getlist('raw_quantity')
    width = max(len(codes), len(qtys), len(raws), 1)

    def item(index: int) -> dict[str, str]:
        return _view_line(
            codes[index] if index < len(codes) else '',
            qtys[index] if index < len(qtys) else '',
            raws[index] if index < len(raws) else '',
            basket, articles,
        )

    return [item(index) for index in range(width - 1)], item(width - 1)


def _render_basket(
    public_id: str, *, status: int = 200, field_errors: dict | None = None, error_form: str = '',
    posted_lines: list | None = None, posted_adder: dict | None = None,
    submitted_row_version: str | None = None, posted_demand_food: str = '', posted_need_quantity: str = '',
) -> WerkzeugResponse:
    location = get_location(_db())
    try:
        basket = get_basket(_db(), location, public_id)
    except CalendarEventValidationError:
        return ('', 404)
    html = render_template(
        'admin/bestellung_korb.html', family='cafeteria', profile='staff_guest',
        basket=basket, preview=basket_csv_bytes(basket).decode('utf-8'),
        articles=list_articles(_db(), location, basket['supplier_public_id']),
        field_errors=field_errors or {}, error_form=error_form,
        posted_lines=posted_lines, posted_adder=posted_adder,
        submitted_row_version=submitted_row_version,
        posted_demand_food=posted_demand_food, posted_need_quantity=posted_need_quantity,
    )
    if status == 200:
        return html
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


def _fail_basket(public_id: str, error: BaseException, status: int, *, demand: bool) -> WerkzeugResponse:
    if isinstance(error, CalendarEventValidationError) and 'nicht gefunden' in str(error).casefold():
        return ('', 404)
    location = get_location(_db())
    try:
        basket = get_basket(_db(), location, public_id)
    except CalendarEventValidationError:
        return ('', 404)
    articles = list_articles(_db(), location, basket['supplier_public_id'])
    message = _basket_message(error)
    posted_lines, posted_adder = (None, None)
    if not demand:
        posted_lines, posted_adder = _split_posted(basket, articles)
    has_lines = bool(posted_lines) or bool(basket['lines'])
    field = _demand_field(error, message) if demand else _save_field(error, message, has_lines)
    submitted = request.form.get('row_version') if 'row_version' in request.form else None
    return _render_basket(
        public_id, status=status, field_errors={field: message},
        error_form='demand' if demand else 'save',
        posted_lines=posted_lines, posted_adder=posted_adder, submitted_row_version=submitted,
        posted_demand_food=(request.form.get('food_public_id') or '') if demand else '',
        posted_need_quantity=(request.form.get('need_quantity') or '') if demand else '',
    )


def _expected_version() -> int:
    raw = request.form.get('row_version') or '0'
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError('Ungültiger Bearbeitungsstand.') from error


@bp.get('/bestellung')
@require_capability('draft.read')
def order_home() -> WerkzeugResponse:
    location = get_location(_db())
    return render_template(
        'admin/bestellung.html', family='cafeteria', profile='staff_guest',
        suppliers=list_suppliers(_db(), location),
        baskets=list_baskets(_db(), location),
        articles=list_articles(_db(), location),
    )


@bp.post('/bestellung/lieferanten')
@require_capability('masterdata.write')
def order_supplier_create() -> WerkzeugResponse:
    validate_csrf(request.form.get('_csrf'))
    create_supplier(_db(), _actor(), {'code': request.form.get('code') or '', 'name': request.form.get('name') or ''})
    flash('Lieferant gespeichert.')
    return redirect(url_for('admin.order_home'), 303)


@bp.post('/bestellung/artikel')
@require_capability('masterdata.write')
def order_article_create() -> WerkzeugResponse:
    validate_csrf(request.form.get('_csrf'))
    create_article(_db(), _actor(), {
        'supplier_public_id': request.form.get('supplier_public_id') or '',
        'food_public_id': request.form.get('food_public_id') or None,
        'article_code': request.form.get('article_code') or '',
        'name': request.form.get('name') or '',
        'order_unit_code': request.form.get('order_unit_code') or 'KG',
        'pack_size': request.form.get('pack_size') or '1',
        'preferred': request.form.get('preferred') == 'on',
    })
    flash('Artikel gespeichert.')
    return redirect(url_for('admin.order_home'), 303)


@bp.post('/bestellung/korb')
@require_capability('draft.write')
def order_basket_create() -> WerkzeugResponse:
    validate_csrf(request.form.get('_csrf'))
    public_id = create_basket(_db(), _scope(), request.form.get('supplier_public_id') or '')
    return redirect(url_for('admin.order_basket', public_id=public_id), 303)


@bp.get('/bestellung/korb/<public_id>')
@require_capability('draft.read')
def order_basket(public_id: str) -> WerkzeugResponse:
    return _render_basket(public_id)


@bp.post('/bestellung/korb/<public_id>')
@require_capability('draft.write')
def order_basket_save(public_id: str) -> WerkzeugResponse:
    validate_csrf(request.form.get('_csrf'))
    codes = request.form.getlist('article_public_id')
    qtys = request.form.getlist('quantity')
    raws = request.form.getlist('raw_quantity')
    lines = []
    for index, (code, qty) in enumerate(zip(codes, qtys)):
        if not code or not qty:
            continue
        raw = raws[index] if index < len(raws) else ''
        item = {'article_public_id': code, 'quantity': qty}
        if raw:
            item['raw_quantity'] = raw
        lines.append(item)
    try:
        replace_basket_lines(
            _db(), _scope(), public_id, expected_row_version=_expected_version(), lines=lines,
        )
    except (CalendarEventConflictError, OrderBasketConflictError) as error:
        return _fail_basket(public_id, error, 409, demand=False)
    except (OrderBasketError, CalendarEventValidationError, ValueError, InvalidOperation) as error:
        return _fail_basket(public_id, error, 400, demand=False)
    flash('Korb gespeichert.')
    return redirect(url_for('admin.order_basket', public_id=public_id), 303)


@bp.post('/bestellung/korb/<public_id>/bedarf')
@require_capability('draft.write')
def order_basket_from_demand(public_id: str) -> WerkzeugResponse:
    validate_csrf(request.form.get('_csrf'))
    foods = request.form.getlist('food_public_id')
    qtys = request.form.getlist('need_quantity')
    demands = [{'food_public_id': food, 'quantity': qty} for food, qty in zip(foods, qtys) if food and qty]
    try:
        fill_from_demand(
            _db(), _scope(), public_id, expected_row_version=_expected_version(), demands=demands,
        )
    except (CalendarEventConflictError, OrderBasketConflictError) as error:
        return _fail_basket(public_id, error, 409, demand=True)
    except (OrderBasketError, CalendarEventValidationError, ValueError, InvalidOperation) as error:
        return _fail_basket(public_id, error, 400, demand=True)
    flash('Bedarf in den Entwurfskorb übernommen. Rohmenge bleibt sichtbar; Gebinde sind gerundet.')
    return redirect(url_for('admin.order_basket', public_id=public_id), 303)


@bp.get('/bestellung/korb/<public_id>/csv')
@require_capability('draft.read')
def order_basket_csv(public_id: str) -> Response:
    try:
        basket = get_basket(_db(), get_location(_db()), public_id)
    except CalendarEventValidationError:
        return Response('', status=404)
    payload = basket_csv_bytes(basket)
    response = Response(payload, mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = 'attachment; filename="bestellvorschau.csv"'
    response.headers['Cache-Control'] = 'no-store'
    return response
