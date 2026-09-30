"""Inventory UI. Unknown stock is labelled, never shown as 0."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import current_app, flash, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..inventory_store import (
    InventoryError, InventoryInsufficientError, balance, list_assigned_slots, post_count, post_movement, transfer,
)
from ..recipe_reads import get_location
from ..roles import require_capability
from ..security import validate_csrf
from ..shopping_list_reads import ShoppingScope
from .routes import bp

_QUANTITY_FIELD = {'move': 'quantity', 'transfer': 'transfer_qty', 'count': 'counted_quantity'}
_UNIT_FIELD = {'move': 'unit_code', 'transfer': 'transfer_unit', 'count': 'count_unit'}


def _db():
    return current_app.extensions['cafeteria_db']


def _scope() -> ShoppingScope:
    return ShoppingScope(g.auth_user.user_id, get_location(_db()), g.auth_user.authz_version)


def _home_redirect(*, food: str = '', storage: str = '') -> Response:
    food = food or request.form.get('food_public_id') or ''
    storage = storage or request.form.get('storage_public_id') or request.form.get('dest_storage_public_id') or ''
    return redirect(url_for('admin.inventory_home', food_public_id=food, storage_public_id=storage), 303)


def _blank_values() -> dict[str, str | None]:
    return {
        'kind': 'receipt', 'quantity': '', 'unit_code': None,
        'dest_storage_public_id': '', 'transfer_quantity': '', 'transfer_unit': None,
        'counted_quantity': '', 'count_unit': None,
    }


def _posted_values(form: str) -> dict[str, str | None]:
    values = _blank_values()
    if form == 'move':
        values['kind'] = request.form.get('kind') or 'receipt'
        if 'quantity' in request.form:
            values['quantity'] = request.form.get('quantity')
        if 'unit_code' in request.form:
            values['unit_code'] = request.form.get('unit_code')
    elif form == 'transfer':
        if 'dest_storage_public_id' in request.form:
            values['dest_storage_public_id'] = request.form.get('dest_storage_public_id') or ''
        if 'quantity' in request.form:
            values['transfer_quantity'] = request.form.get('quantity')
        if 'unit_code' in request.form:
            values['transfer_unit'] = request.form.get('unit_code')
    elif form == 'count':
        if 'counted_quantity' in request.form:
            values['counted_quantity'] = request.form.get('counted_quantity')
        if 'unit_code' in request.form:
            values['count_unit'] = request.form.get('unit_code')
    return values


def _require_quantity(raw: str | None) -> str:
    stripped = ('' if raw is None else str(raw)).strip()
    if not stripped:
        raise InventoryError('Menge ist erforderlich.')
    try:
        number = Decimal(stripped)
    except InvalidOperation as error:
        raise InventoryError('Menge muss eine Zahl sein.') from error
    if not number.is_finite():
        raise InventoryError('Menge muss eine Zahl sein.')
    return stripped


def _public_error(error: BaseException) -> str:
    if isinstance(error, InvalidOperation):
        return 'Menge muss eine Zahl sein.'
    raw = str(error)
    lowered = raw.casefold()
    if 'hexadecimal' in lowered or 'uuid' in lowered:
        return 'Ungültige Kennung.'
    return raw


def _inventory_field(form: str, message: str) -> str:
    lowered = message.casefold()
    if 'verschieden' in lowered or 'ziel' in lowered:
        return 'dest_storage_public_id'
    if 'einheit' in lowered:
        return _UNIT_FIELD[form]
    if 'bewegungsart' in lowered or 'vorzeichen' in lowered:
        return 'kind'
    return _QUANTITY_FIELD[form]


def _inventory_context(food: str, storage: str, values: dict, field_errors: dict, error_form: str) -> dict:
    location_id = get_location(_db())
    slots = list_assigned_slots(_db(), location_id)
    selected = next(
        (item for item in slots
         if item['food_public_id'] == food and item['storage_public_id'] == storage),
        None,
    )
    stock = {'captured': False, 'label': 'Kein Bestand erfasst', 'unit_code': 'KG'}
    if food and storage:
        stock = balance(_db(), location_id, food, storage)
        if selected and not stock.get('unit_code'):
            stock = {**stock, 'unit_code': selected['unit_code']}
    dests = tuple({item['storage_public_id']: item['storage_name'] for item in slots}.items())
    return {
        'family': 'cafeteria', 'profile': 'staff_guest',
        'slots': slots, 'selected': selected,
        'balance_label': stock['label'], 'captured': stock.get('captured', False),
        'food_public_id': food, 'storage_public_id': storage,
        'unit_code': stock.get('unit_code') or (selected['unit_code'] if selected else 'G'),
        'dests': dests, 'values': values, 'field_errors': field_errors, 'error_form': error_form,
    }


def _fail_inventory(form: str, error: BaseException, status: int) -> Response:
    message = _public_error(error)
    food = request.form.get('food_public_id') or ''
    storage = request.form.get('source_storage_public_id') or request.form.get('storage_public_id') or ''
    field = getattr(error, 'field', None)
    if field in ('food_public_id', 'storage_public_id'):
        field = 'lager-selection'
    elif field == 'unit_code':
        field = _UNIT_FIELD[form]
    response = make_response(render_template(
        'admin/lager.html',
        **_inventory_context(food, storage, _posted_values(form), {field or _inventory_field(form, message): message}, form),
    ), status)
    response.headers['Cache-Control'] = 'no-store'
    return response


def _reject_inventory(form: str, error: BaseException) -> Response:
    status = 409 if isinstance(error, InventoryInsufficientError) else 400
    return _fail_inventory(form, error, status)


@bp.get('/lager')
@require_capability('draft.read')
def inventory_home() -> Response:
    food = request.args.get('food_public_id') or ''
    storage = request.args.get('storage_public_id') or ''
    return render_template('admin/lager.html', **_inventory_context(food, storage, _blank_values(), {}, ''))


@bp.post('/lager/bewegung')
@require_capability('draft.write')
def inventory_move() -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        post_movement(
            _db(), _scope(),
            food_public_id=request.form.get('food_public_id') or '',
            storage_public_id=request.form.get('storage_public_id') or '',
            kind=request.form.get('kind') or 'receipt',
            quantity=_require_quantity(request.form.get('quantity')),
            unit_code=request.form.get('unit_code') or 'KG',
            note=request.form.get('note') or None,
        )
    except (InventoryInsufficientError, InventoryError, ValueError, InvalidOperation) as error:
        return _reject_inventory('move', error)
    flash('Bewegung gebucht.')
    return _home_redirect()


@bp.post('/lager/umbuchung')
@require_capability('draft.write')
def inventory_transfer() -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        transfer(
            _db(), _scope(),
            food_public_id=request.form.get('food_public_id') or '',
            source_storage_public_id=request.form.get('source_storage_public_id') or '',
            dest_storage_public_id=request.form.get('dest_storage_public_id') or '',
            quantity=_require_quantity(request.form.get('quantity')),
            unit_code=request.form.get('unit_code') or 'KG',
        )
    except (InventoryInsufficientError, InventoryError, ValueError, InvalidOperation) as error:
        return _reject_inventory('transfer', error)
    flash('Umbuchung gebucht.')
    return _home_redirect(
        food=request.form.get('food_public_id') or '',
        storage=request.form.get('dest_storage_public_id') or '',
    )


@bp.post('/lager/zaehlung')
@require_capability('draft.write')
def inventory_count() -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        result = post_count(
            _db(), _scope(),
            food_public_id=request.form.get('food_public_id') or '',
            storage_public_id=request.form.get('storage_public_id') or '',
            counted_quantity=_require_quantity(request.form.get('counted_quantity')),
            unit_code=request.form.get('unit_code') or 'KG',
        )
    except (InventoryInsufficientError, InventoryError, ValueError, InvalidOperation) as error:
        return _reject_inventory('count', error)
    if result['movement_public_id'] is None:
        flash('Zählung bestätigt, ohne Bewegung.')
    else:
        flash('Zählkorrektur gebucht.')
    return _home_redirect()
