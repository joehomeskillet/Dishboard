"""Inventory UI. Unknown stock is labelled, never shown as 0."""
from __future__ import annotations

from flask import current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..inventory_store import (
    InventoryError, InventoryInsufficientError, balance, post_count, post_movement, transfer,
)
from ..recipe_reads import get_location
from ..roles import require_capability
from ..security import validate_csrf
from ..shopping_list_reads import ShoppingScope
from .routes import bp


def _db():
    return current_app.extensions['cafeteria_db']


def _scope() -> ShoppingScope:
    return ShoppingScope(g.auth_user.user_id, get_location(_db()), g.auth_user.authz_version)


@bp.get('/lager')
@require_capability('draft.read')
def inventory_home() -> Response:
    food = request.args.get('food_public_id') or ''
    storage = request.args.get('storage_public_id') or ''
    stock = {'captured': False, 'label': 'Kein Bestand erfasst'}
    if food and storage:
        stock = balance(_db(), get_location(_db()), food, storage)
    response = render_template(
        'admin/lager.html', family='cafeteria', profile='staff_guest',
        balance_label=stock['label'], captured=stock['captured'],
        food_public_id=food, storage_public_id=storage,
    )
    return response


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
            quantity=request.form.get('quantity') or '0',
            unit_code=request.form.get('unit_code') or 'KG',
            note=request.form.get('note') or None,
        )
    except (InventoryInsufficientError, InventoryError, ValueError) as error:
        flash(str(error))
        return redirect(url_for('admin.inventory_home'), 303)
    flash('Bewegung gebucht.')
    return redirect(url_for('admin.inventory_home'), 303)


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
            quantity=request.form.get('quantity') or '0',
            unit_code=request.form.get('unit_code') or 'KG',
        )
    except (InventoryInsufficientError, InventoryError, ValueError) as error:
        flash(str(error))
        return redirect(url_for('admin.inventory_home'), 303)
    flash('Umbuchung gebucht.')
    return redirect(url_for('admin.inventory_home'), 303)


@bp.post('/lager/zaehlung')
@require_capability('draft.write')
def inventory_count() -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        result = post_count(
            _db(), _scope(),
            food_public_id=request.form.get('food_public_id') or '',
            storage_public_id=request.form.get('storage_public_id') or '',
            counted_quantity=request.form.get('counted_quantity') or '0',
            unit_code=request.form.get('unit_code') or 'KG',
        )
    except (InventoryInsufficientError, InventoryError, ValueError) as error:
        flash(str(error))
        return redirect(url_for('admin.inventory_home'), 303)
    if result['movement_public_id'] is None:
        flash('Zählung bestätigt, ohne Bewegung.')
    else:
        flash('Zählkorrektur gebucht.')
    return redirect(url_for('admin.inventory_home'), 303)
