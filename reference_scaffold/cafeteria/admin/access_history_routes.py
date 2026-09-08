"""Read-only native forms for local and Entra authentication decisions."""
from __future__ import annotations

from flask import abort, request, url_for
from werkzeug.wrappers import Response

from ..auth.access_history_reads import ACTION_LABELS, PROVIDER_LABELS, list_access_history
from ..auth.local_users import LOCAL_USER_MAX_PAGE, InvalidInput
from .local_user_routes import _positive, _protected, _query, _render
from .workflow_routes import _db, bp


@bp.get('/benutzer/zugriffsverlauf')
@_protected
def access_history() -> Response:
    _query({'page', 'provider', 'action'})
    page = _positive(request.args.get('page', '1'), LOCAL_USER_MAX_PAGE)
    provider, action = request.args.get('provider', 'all'), request.args.get('action', 'all')
    try:
        result = list_access_history(_db(), page=page, provider=provider, action=action)
    except InvalidInput as error:
        abort(400, description=str(error))
    return _render('access_history.html', rows=result.rows, page=page,
        provider=provider, action=action, providers=PROVIDER_LABELS, actions=ACTION_LABELS,
        has_next=result.has_next and page < LOCAL_USER_MAX_PAGE,
        prev_url=url_for('admin.access_history', page=page - 1, provider=provider, action=action),
        next_url=url_for('admin.access_history', page=page + 1, provider=provider, action=action))
