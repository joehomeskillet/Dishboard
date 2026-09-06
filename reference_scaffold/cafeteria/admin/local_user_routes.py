"""Local account UI; all writes retain the original actor and target expectations."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from flask import abort, current_app, flash, g, make_response, redirect, render_template, request, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from ..auth import local_users as accounts
from ..roles import capabilities, require_capability
from ..security import csrf_token, validate_csrf
from .rendering import _template_context
from .workflow_routes import _db, bp

ROLE_LABELS = {'Cafeteria.Editor': 'Editor · Menüs bearbeiten',
               'Cafeteria.Publisher': 'Publisher · Menüs veröffentlichen',
               'Cafeteria.Admin': 'Admin · Benutzer und Einstellungen verwalten'}


def _protected(function):
    authorised = require_capability('users.manage')(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = make_response(authorised(*args, **kwargs))
        except (SQLAlchemyError, accounts.ReadUnavailable):
            # No Flask context processors: display/branding may share the failed DB.
            page = current_app.jinja_env.get_template('admin/local_user_unavailable.html').render()
            response = make_response(page, 503)
        except HTTPException as error:
            response = make_response(error)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return wrapped


@bp.context_processor
def local_user_navigation() -> dict[str, bool]:
    allowed = capabilities()
    return {'can_manage_users': '*' in allowed or 'users.manage' in allowed}


def _positive(value: str, maximum: int) -> int:
    if not value or len(value) > 19 or not value.isascii() or not value.isdecimal():
        abort(400, description='Ungültige Seiten- oder Versionsnummer.')
    number = int(value)
    if not 1 <= number <= maximum:
        abort(400, description='Ungültige Seiten- oder Versionsnummer.')
    return number


def _query(allowed: set[str]) -> None:
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        abort(400, description='Ungültige Parameter der Benutzerverwaltung.')


def _back(source, *, form: bool = False) -> tuple[int, str]:
    prefix = 'return_' if form else ''
    page = _positive(source.get(prefix + 'page', '1'), accounts.LOCAL_USER_MAX_PAGE)
    status = source.get(prefix + 'status', 'all')
    if status not in ('all', 'active', 'disabled'):
        abort(400, description='Ungültiger Kontostatus.')
    return page, status


def _list_url(page: int, status: str) -> str:
    return url_for('admin.local_users_list', page=page, status=status)


def _time(value: datetime | None) -> str:
    return value.astimezone(ZoneInfo('Europe/Zurich')).strftime('%d.%m.%Y %H:%M') if value else 'Noch nicht erfasst'


def _render(template: str, *, status_code: int = 200, **values: Any) -> Response:
    return make_response(render_template('admin/' + template, family='cafeteria', profile='staff_guest',
        csrf=csrf_token(), role_labels=ROLE_LABELS, format_time=_time,
        now=datetime.now(timezone.utc), can_mutate=current_app.extensions.get('cafeteria_auth_issuer_db') is not None,
        **_template_context(), **values), status_code)


def _account(public_id: UUID):
    account = accounts.get_local_user(_db(), public_id=public_id)
    if account is None:
        abort(404, description='Lokales Konto nicht gefunden.')
    return account


def _form(required: set[str], *, roles: bool = False) -> tuple[int, str]:
    if request.args or request.files:
        abort(400)
    fields = required | {'_csrf', 'return_page', 'return_status'}
    if set(request.form) - (fields | ({'roles'} if roles else set())) or not fields <= set(request.form):
        abort(400, description='Ungültiges Kontoformular.')
    if any(len(request.form.getlist(key)) != 1 for key in request.form if key != 'roles'):
        abort(400, description='Mehrdeutiges Kontoformular.')
    validate_csrf(request.form['_csrf'])
    return _back(request.form, form=True)


def _roles() -> tuple[str, ...]:
    roles = tuple(request.form.getlist('roles'))
    if not 1 <= len(roles) <= 3 or len(set(roles)) != len(roles) or set(roles) - ROLE_LABELS.keys():
        raise ValueError('Bitte eine oder mehrere unterschiedliche angebotene Rollen auswählen.')
    return roles


def _password() -> str:
    if request.form['password'] != request.form['password_confirm']:
        raise ValueError('Die beiden neuen Passwörter müssen übereinstimmen.')
    return request.form['password']


def _issuer():
    engine = current_app.extensions.get('cafeteria_auth_issuer_db')
    if engine is None:
        raise accounts.IssuerUnavailable('Kontoänderungen sind momentan nicht verfügbar. Die Konten bleiben lesbar.')
    return engine


def _write_error(error: ValueError) -> int:
    if isinstance(error, (accounts.ActorDenied, accounts.StaleActor)):
        session.clear()
        abort(401 if isinstance(error, accounts.StaleActor) else 403)
    if isinstance(error, accounts.UnknownTarget):
        abort(404)
    if isinstance(error, accounts.IssuerUnavailable):
        return 503
    return 409 if isinstance(error, (accounts.StaleTarget, accounts.LastLocalAdmin, accounts.DuplicateUsername)) else 400


@bp.get('/benutzer')
@_protected
def local_users_list() -> Response:
    _query({'page', 'status'})
    page, status = _back(request.args)
    rows = accounts.list_local_users(_db(), page=page, status=status)
    return _render('local_users.html', rows=rows, page=page, status=status,
        has_next=len(rows) == accounts.LOCAL_USER_PAGE_SIZE and page < accounts.LOCAL_USER_MAX_PAGE,
        prev_url=_list_url(max(1, page - 1), status), next_url=_list_url(min(accounts.LOCAL_USER_MAX_PAGE, page + 1), status))


@bp.get('/benutzer/neu')
@_protected
def local_user_new() -> Response:
    _query({'page', 'status'})
    page, status = _back(request.args)
    return _render('local_user_create.html', values={}, error='', page=page, status=status)


@bp.post('/benutzer')
@_protected
def local_user_create() -> Response:
    actor = accounts.ActorExpectation(g.auth_user.user_id, g.auth_user.authz_version)
    page, status = _form({'username', 'display_name', 'password', 'password_confirm'}, roles=True)
    values = {key: request.form[key] for key in ('username', 'display_name')}
    try:
        result = accounts.create_local_user(_issuer(), actor=actor, **values,
            password=_password(), roles=_roles())
    except ValueError as error:
        return _render('local_user_create.html', status_code=_write_error(error),
                       values=values, error=str(error), page=page, status=status)
    flash('Lokales Konto angelegt.')
    return redirect(url_for('admin.local_user_detail', public_id=result.public_id, page=page, status=status), 303)


@bp.get('/benutzer/<uuid:public_id>')
@_protected
def local_user_detail(public_id: UUID) -> Response:
    _query({'page', 'status'})
    page, status = _back(request.args)
    return _render('local_user_editor.html', account=_account(public_id), error='',
                   error_action='', page=page, status=status)


@bp.post('/benutzer/<uuid:public_id>/<action>')
@_protected
def local_user_change(public_id: UUID, action: str) -> Response:
    actor = accounts.ActorExpectation(g.auth_user.user_id, g.auth_user.authz_version)
    if action not in ('rollen', 'passwort', 'deaktivieren', 'aktivieren'):
        abort(404)
    fields = {'target_version', 'confirm'} | ({'password', 'password_confirm'} if action == 'passwort' else set())
    page, status = _form(fields, roles=action == 'rollen')
    target = accounts.TargetExpectation(public_id, _positive(request.form['target_version'], 9223372036854775807))
    _account(public_id)
    with _db().connect() as connection:
        own_id = connection.execute(text('SELECT public_id FROM cafeteria.users WHERE id=:actor'),
                                    {'actor': actor.user_id}).scalar_one()
    try:
        if request.form['confirm'] != 'yes':
            raise ValueError('Bitte die angezeigte Kontoaktion ausdrücklich bestätigen.')
        engine = _issuer()
        if action == 'rollen':
            result = accounts.replace_local_roles(engine, actor=actor, target=target, roles=_roles())
        elif action == 'passwort':
            result = accounts.reset_local_password(engine, actor=actor, target=target, password=_password())
        elif action == 'deaktivieren':
            result = accounts.deactivate_local_user(engine, actor=actor, target=target)
        else:
            result = accounts.reactivate_local_user(engine, actor=actor, target=target)
    except ValueError as error:
        code = _write_error(error)
        return _render('local_user_editor.html', status_code=code, account=_account(public_id),
                       error=str(error), error_action=action, page=page, status=status)
    if own_id == public_id and result.changed:
        session.clear()
        return redirect(url_for('auth.local_login'), 303)
    flash('Kontoaktion gespeichert.' if result.changed else 'Das Konto hat bereits den gewünschten Zustand.')
    return redirect(url_for('admin.local_user_detail', public_id=public_id, page=page, status=status), 303)


@bp.get('/benutzer/protokoll')
@_protected
def local_user_events() -> Response:
    _query({'page', 'target'})
    page = _positive(request.args.get('page', '1'), accounts.LOCAL_USER_MAX_PAGE)
    target = None
    if 'target' in request.args:
        try:
            target = UUID(request.args['target'])
        except ValueError:
            abort(400, description='Ungültiges lokales Konto.')
        _account(target)
    rows = accounts.list_local_user_events(_db(), page=page, target_public_id=target)
    parameters: dict[str, Any] = {'target': str(target)} if target else {}
    return _render('local_user_events.html', rows=rows, page=page,
        has_next=len(rows) == accounts.LOCAL_USER_PAGE_SIZE and page < accounts.LOCAL_USER_MAX_PAGE,
        prev_url=url_for('admin.local_user_events', page=max(1, page - 1), **parameters),
        next_url=url_for('admin.local_user_events', page=min(accounts.LOCAL_USER_MAX_PAGE, page + 1), **parameters))
