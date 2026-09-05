from __future__ import annotations

import re

from flask import abort, render_template, request

from ..roles import require_capability
from ..workflow_review import review_open
from .menu_collection_store import find_menus
from .rendering import MEAL_LABELS, OPTION_LABELS, _template_context
from .workflow_routes import _call, _db, _reject_override, _scope, bp, profile_from_endpoint


@bp.get('/<any(cafeteria, patienten):family>/menues')
@require_capability('draft.read')
def menu_collection(family: str) -> str:
    profile = profile_from_endpoint(family)
    _reject_override()
    if set(request.args) - {'q', 'page'} or any(
        len(request.args.getlist(key)) != 1 for key in request.args
    ):
        abort(400, description='Suchparameter sind ungültig.')
    query = request.args.get('q', '').strip()
    raw_page = request.args.get('page', '1')
    if len(query) > 200 or re.fullmatch(r'[1-9][0-9]{0,4}', raw_page) is None:
        abort(400, description='Menüsuche oder Seitennummer ist ungültig.')
    page = int(raw_page)
    if page > 10000:
        abort(400, description='Seitennummer ist zu gross.')
    scope = _scope(profile)
    rows, has_next = _call(lambda: find_menus(_db(), scope, query, page))
    for row in rows:
        row['review_open'] = _call(lambda: review_open(_db(), scope, row['id']))
    return render_template(
        'admin/menu_collection.html', profile=profile, family=family,
        rows=rows, query=query, page=page, has_next=has_next,
        meal_labels=MEAL_LABELS, option_labels=OPTION_LABELS,
        **_template_context(),
    )
