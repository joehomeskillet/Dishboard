"""Purchase price form on the food sheet. masterdata.write, append-only revisions."""
from __future__ import annotations

from flask import flash, g, redirect, request, url_for
from werkzeug.wrappers import Response

from ..auth.local_users import ActorExpectation
from ..food_price_store import append_price_revision, list_price_revisions
from ..master_data_types import MasterDataConflictError, MasterDataValidationError
from ..roles import require_capability
from ..security import validate_csrf
from . import master_data_forms as forms
from .routes import bp


@bp.post('/grundlagen/zutaten/<public_id>/preis')
@require_capability('masterdata.write')
def food_price_save(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    actor = ActorExpectation(g.auth_user.user_id, g.auth_user.authz_version)
    head_version = request.form.get('head_row_version') or None
    yield_raw = request.form.get('yield_factor') or None
    try:
        append_price_revision(
            forms.engine(), actor, public_id,
            expected_head_version=int(head_version) if head_version else None,
            intervals=[{
                'valid_from': request.form.get('valid_from') or '',
                'valid_to': request.form.get('valid_to') or None,
                'unit_price': request.form.get('unit_price') or '',
                'unit_code': request.form.get('unit_code') or 'KG',
                'yield_factor': yield_raw or None,
            }],
        )
    except (MasterDataValidationError, MasterDataConflictError, ValueError) as error:
        flash(str(error))
        return redirect(url_for('admin.master_data_detail', kind='zutaten', public_id=public_id), 303)
    flash('Einkaufspreis gespeichert.')
    return redirect(url_for('admin.master_data_detail', kind='zutaten', public_id=public_id), 303)


def load_food_prices(engine, public_id: str):
    try:
        return list_price_revisions(engine, public_id)
    except Exception:
        return ()
