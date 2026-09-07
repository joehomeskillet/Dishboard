"""Native Tabler assignment forms with the original signed actor and CAS."""
from __future__ import annotations

import re
from functools import wraps

from flask import abort, current_app, g, make_response, redirect, render_template, request, url_for
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException

from .. import screen_templates as store
from ..roles import capabilities, require_capability
from ..security import csrf_token, validate_csrf
from .workflow_routes import _db, bp, profile_from_endpoint


def database_available(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = make_response(function(*args, **kwargs))
        except (SQLAlchemyError, store.ScreenStateError):
            response = make_response(current_app.jinja_env.get_template(
                'admin/screen_template_unavailable.html').render(), 503)
        except HTTPException as error:
            response = error.get_response()
        response.headers['Cache-Control'] = 'no-store'
        return response
    return wrapped


def _signer() -> URLSafeTimedSerializer:
    if not current_app.secret_key:
        raise store.ScreenStateError('Formularsignatur nicht verfügbar.')
    return URLSafeTimedSerializer(current_app.secret_key, salt='screen-assignment-form-v1')


def _render(family: str, *, error: str | None = None, status: int = 200):
    profile = profile_from_endpoint(family)
    active = None
    if error is None:
        with _db().connect() as connection:
            active = store.read_assignment(connection, profile)
        values = {'version': str(active.version), 'template_id': active.template.id,
                  'renderer_revision': '1', 'action': 'activate', '_csrf': csrf_token()}
        values['_form_context'] = _signer().dumps({
            'actor': g.auth_user.user_id, 'actor_version': g.auth_user.authz_version,
            'scope': 'global', 'target': store.key(profile), 'version': active.version,
            'csrf': values['_csrf'],
        })
    else:
        # Retain submitted values, token and version; no reread or resign of the assignment.
        values = {name: request.form.get(name, '') for name in (
            '_csrf', '_form_context', 'version', 'template_id', 'renderer_revision', 'action')}
    return make_response(render_template('admin/screen_template_assignment.html',
        family=family, profile=profile, choices=store.choices(profile), active=active,
        values=values, error=error, can_write='*' in capabilities() or 'settings.write' in capabilities()), status)


def _expectations(profile: str) -> tuple[int, int, int]:
    names = {'_csrf', '_form_context', 'version', 'template_id', 'renderer_revision', 'action'}
    if set(request.form) != names or any(len(request.form.getlist(name)) != 1 for name in names):
        abort(400, description='Formularfelder fehlen oder sind mehrfach beziehungsweise unerwartet vorhanden.')
    if not request.form['_csrf'].isascii():
        abort(400, description='CSRF-Prüfung fehlgeschlagen.')
    try:
        original = _signer().loads(request.form['_form_context'])
    except BadData:
        abort(400, description='Formularkontext ist ungültig.')
    if not isinstance(original, dict) or set(original) != {'actor', 'actor_version', 'scope', 'target', 'version', 'csrf'}:
        abort(400, description='Formularkontext ist ungültig.')
    if any(original[name] != value for name, value in (
        ('scope', 'global'), ('target', store.key(profile)), ('csrf', request.form['_csrf']),
    )) or any(type(original[name]) is not int for name in ('actor', 'actor_version', 'version')):
        abort(400, description='Formularkontext passt nicht zu diesem Ziel.')
    if (original['actor'], original['actor_version']) != (g.auth_user.user_id, g.auth_user.authz_version):
        abort(401)
    validate_csrf(request.form['_csrf'])
    raw = request.form['version']
    if not re.fullmatch(r'0|[1-9][0-9]{0,18}', raw) or int(raw) != original['version'] or int(raw) > store.MAX_VERSION:
        abort(400, description='Die ursprüngliche Version wurde verändert.')
    if request.form['action'] != 'activate' or request.form['renderer_revision'] != '1':
        abort(400, description='Aktion oder Rendererrevision ist ungültig.')
    return original['actor'], original['actor_version'], original['version']


@bp.route('/screens/<any(cafeteria,patienten):family>/wochenvorlage', methods=['GET', 'POST'])
@database_available
@require_capability('draft.read')
def screen_template_assignment(family: str):
    if request.args:
        abort(400)
    if request.method == 'GET':
        return _render(family)
    if '*' not in capabilities() and 'settings.write' not in capabilities():
        abort(403)
    profile = profile_from_endpoint(family)
    try:
        actor, authz, version = _expectations(profile)
        store.activate(_db(), profile, actor, authz, version, request.form['template_id'], 1)
    except PermissionError:
        abort(403)
    except LookupError:
        abort(404)
    except (BadRequest, store.ScreenValidation, store.ScreenConflict) as error:
        message = error.description if isinstance(error, BadRequest) else str(error)
        return _render(family, error=message, status=409 if isinstance(error, store.ScreenConflict) else 400)
    return redirect(url_for('admin.screen_template_assignment', family=family), 303)


@bp.get('/vorlagen/screens/<any(cafeteria,patienten):family>/<template_id>')
@database_available
@require_capability('draft.read')
def screen_template_preview(family: str, template_id: str):
    if request.args:
        abort(400)
    profile = profile_from_endpoint(family)
    try:
        template = store.resolve(profile, template_id)
    except LookupError:
        abort(404)
    except store.ScreenValidation:
        abort(400)
    from ..public.routes import cafeteria_context, load_context, published_response
    context = cafeteria_context() if profile == 'staff_guest' else load_context(profile)
    context['show_menu_images'] = template.show_menu_images
    context['explicit_without_images'] = False
    response = published_response('public/cafeteria_week.html' if profile == 'staff_guest' else 'public/patient_week.html', context)
    response.headers['X-Screen-Template-Revision'] = f'{template.id}:1:preview'
    return response
