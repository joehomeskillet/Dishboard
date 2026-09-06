from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.wrappers import Response

from ..api.v1_routes import status_payload
from ..api_keys import ApiKeyValidationError, create_api_key, list_api_keys, revoke_api_key
from ..db import SCHEMA_VERSION
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from .rendering import _template_context
from .routes import _actor_id, bp

_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_CREATE_FIELDS = frozenset({'_csrf', 'label', 'scopes', 'expires_at'})
# An unchecked scope checkbox is simply absent from the form; the store reports the validation error.
_CREATE_REQUIRED = frozenset({'_csrf', 'label', 'expires_at'})


def _db():
    return current_app.extensions['cafeteria_db']


def _parse_expires_at(raw: str) -> datetime | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    if _ISO.fullmatch(cleaned) is None:
        raise ApiKeyValidationError('Ablaufzeit ist ungültig.')
    try:
        parsed = date.fromisoformat(cleaned)
    except ValueError as error:
        raise ApiKeyValidationError('Ablaufzeit ist ungültig.') from error
    return datetime(parsed.year, parsed.month, parsed.day, 23, 59, 59, tzinfo=ZoneInfo('Europe/Zurich'))


def _form_values() -> dict[str, str | bool]:
    return {
        'label': request.form.get('label', ''),
        'expires_at': request.form.get('expires_at', ''),
        'scopes_preview': 'preview.read' in request.form.getlist('scopes'),
    }


def _render_api(
    *,
    error: str | None = None,
    new_key: dict[str, str] | None = None,
    values: dict[str, str | bool] | None = None,
) -> str:
    try:
        keys = list_api_keys(_db())
    except PermissionError:
        abort(403)
    return render_template(
        'admin/api.html',
        family='cafeteria',
        profile='staff_guest',
        keys=keys,
        status=status_payload(),
        schema_version=SCHEMA_VERSION,
        fhir_version='5.0.0',
        api_version='1.0.0',
        csrf=csrf_token(),
        error=error,
        new_key=new_key,
        values=values if values is not None else {'label': '', 'expires_at': '', 'scopes_preview': False},
        **_template_context(),
    )


@bp.get('/api')
@require_capability('api.keys.manage')
def api_overview() -> str:
    if request.args:
        abort(400, description='Query-Parameter sind ungültig.')
    new_key = session.pop('api_key_created', None)
    return _render_api(new_key=new_key)


@bp.post('/api/keys')
@require_capability('api.keys.manage')
def api_key_create() -> Response | tuple[str, int]:
    if request.args:
        abort(400, description='Formularparameter gehören in das Formular.')
    validate_csrf(request.form.get('_csrf'))
    submitted = set(request.form)
    if not _CREATE_REQUIRED <= submitted <= _CREATE_FIELDS:
        abort(400, description='Formularfelder sind ungültig.')
    values = _form_values()
    try:
        record, plaintext = create_api_key(
            _db(),
            actor_id=_actor_id(),
            label=request.form.get('label', ''),
            scopes=request.form.getlist('scopes'),
            expires_at=_parse_expires_at(request.form.get('expires_at', '')),
        )
    except PermissionError:
        abort(403)
    except ApiKeyValidationError as error:
        return _render_api(error=str(error), values=values), 400
    session['api_key_created'] = {'public_id': record.public_id, 'plaintext': plaintext}
    return redirect(url_for('admin.api_overview'), 303)


@bp.post('/api/keys/<public_id>/revoke')
@require_capability('api.keys.manage')
def api_key_revoke(public_id: str) -> Response:
    if request.args:
        abort(400, description='Formularparameter gehören in das Formular.')
    validate_csrf(request.form.get('_csrf'))
    if set(request.form) != {'_csrf'}:
        abort(400, description='Formularfelder sind ungültig.')
    try:
        revoked = revoke_api_key(_db(), actor_id=_actor_id(), public_id=public_id)
    except PermissionError:
        abort(403)
    except ApiKeyValidationError:
        flash('Schlüssel war bereits widerrufen.')
        return redirect(url_for('admin.api_overview'), 303)
    if not revoked:
        flash('Schlüssel war bereits widerrufen.')
    return redirect(url_for('admin.api_overview'), 303)
