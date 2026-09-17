"""Kalkulation: preview is GET/POST without write; confirm stores an immutable receipt."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from flask import current_app, flash, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..calculation_receipts import CalculationReceiptConflictError, append_receipt
from ..food_price_store import list_price_revisions
from ..public.routes import effective_today
from ..recipe_cost import project_menu, project_prepared, project_recipe
from ..recipe_reads import get_location
from ..roles import require_capability
from ..security import validate_csrf
from ..shopping_list_reads import ShoppingScope
from .routes import bp


def _db():
    return current_app.extensions['cafeteria_db']


def _scope() -> ShoppingScope:
    return ShoppingScope(g.auth_user.user_id, get_location(_db()), g.auth_user.authz_version)


def _as_of() -> date:
    raw = (request.values.get('as_of') or '').strip()
    if raw:
        return date.fromisoformat(raw)
    return effective_today()


def _price_map() -> dict[str, str]:
    foods = request.values.getlist('price_food_id')
    revisions = request.values.getlist('price_revision_id')
    return {food: revision for food, revision in zip(foods, revisions) if food and revision}


def _current_prices(food_ids: list[str]) -> dict[str, str]:
    chosen: dict[str, str] = {}
    for food_id in food_ids:
        for row in list_price_revisions(_db(), food_id):
            if row.get('is_current'):
                chosen[food_id] = str(row['public_id'])
                break
    return chosen


def _line_dict(line) -> dict:
    return {
        'food_public_id': line.food_public_id,
        'quantity': None if line.quantity is None else str(line.quantity),
        'unit_code': line.unit_code,
        'status': line.status,
        'amount': None if line.amount is None else str(line.amount),
    }


def _serialize(projection: dict) -> dict:
    payload = {
        'kind': projection['kind'],
        'complete': projection['complete'],
        'total': None if projection['total'] is None else str(projection['total']),
        'as_of': projection['as_of'],
        'price_revisions': projection['price_revisions'],
        'revision_public_id': projection.get('revision_public_id'),
        'lines': [_line_dict(line) for line in projection['lines']],
    }
    if projection.get('parts'):
        payload['parts'] = [
            {
                'revision_public_id': part.get('revision_public_id'),
                'complete': part['complete'],
                'total': None if part['total'] is None else str(part['total']),
                'lines': [_line_dict(line) for line in part['lines']],
            }
            for part in projection['parts']
        ]
    return payload


def _project(prices: dict[str, str] | None = None):
    kind = request.values.get('kind') or 'recipe'
    revision = (request.values.get('revision_public_id') or '').strip()
    extras = [item.strip() for item in request.values.getlist('menu_revision_public_id') if item.strip()]
    chosen = prices if prices is not None else _price_map()
    as_of = _as_of()
    if kind == 'menu':
        ids = ([revision] if revision else []) + extras
        return project_menu(_db(), ids, as_of, chosen)
    if kind == 'prepared':
        return project_prepared(_db(), revision, as_of, chosen)
    return project_recipe(_db(), revision, as_of, chosen)


@bp.get('/kalkulation')
@require_capability('draft.read')
def cost_home() -> Response:
    response = make_response(render_template(
        'admin/kalkulation.html', family='cafeteria', profile='staff_guest',
        projection=None, as_of=effective_today().isoformat(),
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.post('/kalkulation/vorschau')
@require_capability('draft.read')
def cost_preview() -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        projection = _project()
        if not _price_map():
            foods = [line.food_public_id for line in projection['lines'] if line.food_public_id]
            filled = _current_prices([item for item in foods if item])
            if filled:
                projection = _project(filled)
    except Exception as error:
        flash(str(error))
        return redirect(url_for('admin.cost_home'), 303)
    response = make_response(render_template(
        'admin/kalkulation.html', family='cafeteria', profile='staff_guest',
        projection=projection,
        as_of=projection['as_of'],
        revision_public_id=(request.form.get('revision_public_id') or '').strip(),
        menu_revision_public_ids=[item.strip() for item in request.form.getlist('menu_revision_public_id') if item.strip()],
        kind=request.form.get('kind') or 'recipe',
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.post('/kalkulation/beleg')
@require_capability('masterdata.write')
def cost_confirm() -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        projection = _project()
        payload = _serialize(projection)
        subject = (request.form.get('revision_public_id') or request.form.get('menu_revision_public_id') or '').strip()
        UUID(subject)
        append_receipt(
            _db(), _scope(), kind=projection['kind'], subject_public_id=subject, payload=payload,
        )
    except CalculationReceiptConflictError as error:
        flash(str(error))
        return redirect(url_for('admin.cost_home'), 303)
    except Exception as error:
        flash(str(error))
        return redirect(url_for('admin.cost_home'), 303)
    flash('Kalkulationsbeleg gespeichert.')
    return redirect(url_for('admin.cost_home'), 303)
