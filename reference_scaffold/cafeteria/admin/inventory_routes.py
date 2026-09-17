"""Inventory UI. Unknown stock is labelled, never shown as 0."""
from __future__ import annotations

from flask import current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..inventory_store import InventoryInsufficientError, balance, post_movement
from ..recipe_reads import get_location
from ..roles import require_capability
from ..security import validate_csrf
from ..shopping_list_reads import ShoppingScope
from .routes import bp


def _db():
    return current_app.extensions['cafeteria_db']


@bp.get('/lager')
@require_capability('draft.read')
def inventory_home() -> Response:
    return render_template(
        'admin/lager.html', family='cafeteria', profile='staff_guest',
        balance_label='Kein Bestand erfasst', captured=False,
    )


@bp.post('/lager/bewegung')
@require_capability('draft.write')
def inventory_move() -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = ShoppingScope(g.auth_user.user_id, get_location(_db()), g.auth_user.authz_version)
    try:
        post_movement(
            _db(), scope,
            food_public_id=request.form.get('food_public_id') or '',
            storage_public_id=request.form.get('storage_public_id') or '',
            kind=request.form.get('kind') or 'receipt',
            quantity=request.form.get('quantity') or '0',
            unit_code=request.form.get('unit_code') or 'KG',
            note=request.form.get('note') or None,
        )
    except InventoryInsufficientError as error:
        flash(str(error))
        return redirect(url_for('admin.inventory_home'), 303)
    flash('Bewegung gebucht.')
    return redirect(url_for('admin.inventory_home'), 303)
