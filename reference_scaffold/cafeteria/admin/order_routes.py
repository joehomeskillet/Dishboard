"""Order draft UI: catalog, basket, CSV download. No send."""
from __future__ import annotations

from flask import Response, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.wrappers import Response as WerkzeugResponse

from ..calendar_event_store import CalendarEventConflictError, CalendarEventValidationError
from ..order_basket_store import (
    OrderBasketError, create_basket, fill_from_demand, get_basket, list_baskets, replace_basket_lines,
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
    location = get_location(_db())
    try:
        basket = get_basket(_db(), location, public_id)
    except CalendarEventValidationError:
        return ('', 404)
    preview = basket_csv_bytes(basket).decode('utf-8')
    return render_template(
        'admin/bestellung_korb.html', family='cafeteria', profile='staff_guest',
        basket=basket, preview=preview, articles=list_articles(_db(), location, basket['supplier_public_id']),
    )


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
            _db(), _scope(), public_id,
            expected_row_version=int(request.form.get('row_version') or 0),
            lines=lines,
        )
    except (OrderBasketError, CalendarEventConflictError, CalendarEventValidationError, ValueError) as error:
        flash(str(error))
        return redirect(url_for('admin.order_basket', public_id=public_id), 303)
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
            _db(), _scope(), public_id,
            expected_row_version=int(request.form.get('row_version') or 0),
            demands=demands,
        )
    except (OrderBasketError, ValueError) as error:
        flash(str(error))
        return redirect(url_for('admin.order_basket', public_id=public_id), 303)
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
