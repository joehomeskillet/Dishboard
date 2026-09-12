from __future__ import annotations

import secrets
from urllib.parse import quote

import msal
from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from redis.exceptions import RedisError
from requests.exceptions import RequestException  # type: ignore[import-untyped]
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.wrappers import Response

from ..db import demo_user, upsert_entra_user
from ..roles import ROLE_CAPABILITIES
from ..security import validate_csrf
from .access_events import AccessEventUnavailable, record_access_event
from .service import (
    AuthorizationState,
    RateLimitExceeded,
    RateLimitUnavailable,
    authenticate_local_user,
    clear_login_attempts,
    consume_login_attempt,
    login_rate_key,
    load_user_authorization,
    trusted_client_address,
)

bp = Blueprint('auth', __name__, url_prefix='/auth')
_MAX_PROVIDER_SID_LENGTH = 255


def _login_failure(
    provider: str, reason: str, status: int, username: str = '', *, clear_session: bool = True,
) -> tuple[str, int]:
    if clear_session:
        session.clear()
    action = 'auth.login.unavailable' if reason == 'unavailable' else 'auth.login.rejected'
    try:
        record_access_event(provider, action, reason)
    except AccessEventUnavailable:
        status = 503
    message = 'Anmeldung vorübergehend nicht verfügbar.' if status == 503 else 'Anmeldung fehlgeschlagen.'
    if provider == 'local':
        return render_template('auth/local_login.html', error=message, username=username), status
    return render_template('auth/error.html', message=message), status


def _login_accepted(provider: str, identity: AuthorizationState, **claims: str) -> Response | tuple[str, int]:
    try:
        record_access_event(provider, 'auth.login.accepted', identity=identity)
    except AccessEventUnavailable:
        return _login_failure(provider, 'unavailable', 503)
    try:
        _establish_session(identity.user_id, identity.display_name, identity.authz_version,
                           provider=provider, **claims)
    except RedisError:
        session.clear()
        current_app.logger.warning('Authentication session establishment unavailable.')
        message = 'Anmeldung vorübergehend nicht verfügbar.'
        return render_template('auth/error.html', message=message), 503
    return redirect(url_for('admin.cafeteria'))


def _clear_session_for_logout(action: str) -> None:
    user, version = session.get('user'), session.get('authz_version')
    session.clear()
    if (not isinstance(user, dict) or type(user.get('id')) is not int or user['id'] <= 0
        or user.get('provider') not in ('local', 'entra') or type(version) is not int or version <= 0):
        return
    identity = None
    try:
        current = load_user_authorization(current_app.extensions['cafeteria_db'], user['id'])
        if current is not None and current.authz_version == version and current.auth_provider == user['provider']:
            identity = current
    except SQLAlchemyError:
        current_app.logger.warning('Logout identity verification unavailable.')
    try:
        record_access_event(user['provider'], action, identity=identity)
    except AccessEventUnavailable:
        # The fixed writer diagnostic makes no claim that Redis has saved deletion.
        # Always reach response saving, which revokes the existing server session.
        return


def _establish_session(user_id: int, display_name: str, authz_version: int, **claims: str) -> None:
    session.clear()
    session['_regenerate'] = True
    regenerate = getattr(current_app.session_interface, 'regenerate', None)
    if callable(regenerate):
        regenerate(session)
    session.clear()
    session['user'] = {'id': user_id, 'name': display_name, **claims}
    session['authz_version'] = authz_version
    session.permanent = True


def _client() -> msal.ConfidentialClientApplication:
    cfg = current_app.config
    return msal.ConfidentialClientApplication(
        cfg['ENTRA_CLIENT_ID'],
        authority=f"https://login.microsoftonline.com/{cfg['ENTRA_TENANT_ID']}",
        client_credential=cfg['ENTRA_CLIENT_SECRET'],
    )


@bp.get('/login')
def login():
    cfg = current_app.config
    if cfg['DEMO_MODE']:
        demo = demo_user(current_app.extensions['cafeteria_db'])
        authorization = load_user_authorization(current_app.extensions['cafeteria_db'], demo['id'])
        if authorization is None:
            return render_template('auth/error.html', message='Demo-Benutzer ist nicht aktiv.'), 503
        _establish_session(
            authorization.user_id,
            authorization.display_name,
            authorization.authz_version,
            oid='demo-user',
            tid='demo-tenant',
            provider=authorization.auth_provider,
        )
        return redirect(url_for('admin.cafeteria'))
    if not cfg.get('ENTRA_ENABLED', False):
        if cfg.get('LOCAL_AUTH_ENABLED', False):
            return redirect(url_for('auth.local_login'))
        return render_template('auth/error.html', message='Keine Anmeldung konfiguriert.'), 503
    if not cfg['ENTRA_TENANT_ID'] or not cfg['ENTRA_CLIENT_ID'] or not cfg['ENTRA_CLIENT_SECRET']:
        return render_template('auth/error.html', message='Entra-Konfiguration ist unvollständig.'), 503
    flow = _client().initiate_auth_code_flow(scopes=[], redirect_uri=cfg['APP_PUBLIC_BASE_URL'] + url_for('auth.callback'))
    session['auth_flow'] = flow
    return redirect(flow['auth_uri'])


@bp.route('/local', methods=['GET', 'POST'])
def local_login():
    if not current_app.config.get('LOCAL_AUTH_ENABLED', False):
        abort(404)
    if request.method == 'GET':
        return render_template('auth/local_login.html')

    username = request.form.get('username', '')
    password = request.form.get('password', '')

    validate_csrf(request.form.get('csrf_token'))
    remote_address = trusted_client_address(
        request.environ,
        request.remote_addr or 'unknown',
        tuple(current_app.config.get('TRUSTED_PROXY_PEERS', ())),
    )
    key = login_rate_key(username, remote_address)
    redis_client = current_app.extensions.get('cafeteria_rate_redis')

    try:
        consume_login_attempt(redis_client, key)
    except RateLimitUnavailable:
        return _login_failure('local', 'unavailable', 503, username)
    except RateLimitExceeded:
        return _login_failure('local', 'throttled', 429, username)

    try:
        identity = authenticate_local_user(
            current_app.extensions['cafeteria_db'], username=username, password=password,
        )
    except SQLAlchemyError:
        return _login_failure('local', 'unavailable', 503, username)

    if identity is None:
        return _login_failure('local', 'credentials', 401, username)

    try:
        clear_login_attempts(redis_client, key)
    except RateLimitUnavailable:
        return _login_failure('local', 'unavailable', 503, username)
    return _login_accepted('local', identity)


@bp.get('/callback')
def callback():
    if not current_app.config.get('ENTRA_ENABLED', False):
        abort(404)
    flow = session.pop('auth_flow', None)
    if not flow:
        return _login_failure('entra', 'flow', 400, clear_session=False)
    try:
        result = _client().acquire_token_by_auth_code_flow(flow, request.args)
    except ValueError:
        return _login_failure('entra', 'flow', 400, clear_session=False)
    except RequestException:
        return _login_failure('entra', 'unavailable', 503)
    if not isinstance(result, dict):
        return _login_failure('entra', 'flow', 400)
    if 'error' in result:
        return _login_failure('entra', 'credentials', 401)
    claims = result.get('id_token_claims') or {}
    cfg = current_app.config
    if not isinstance(claims, dict) or claims.get('tid') != cfg['ENTRA_TENANT_ID'] or not claims.get('oid'):
        return _login_failure('entra', 'flow', 403)
    if claims.get('aud') and claims.get('aud') != cfg['ENTRA_CLIENT_ID']:
        return _login_failure('entra', 'flow', 403)
    provider_sid = claims.get('sid')
    if provider_sid is not None and (
        not isinstance(provider_sid, str)
        or not provider_sid
        or len(provider_sid) > _MAX_PROVIDER_SID_LENGTH
    ):
        return _login_failure('entra', 'flow', 403)
    supplied_roles = claims.get('roles') or []
    if not isinstance(supplied_roles, list) or any(not isinstance(role, str) for role in supplied_roles):
        return _login_failure('entra', 'role', 403)
    if (
        len(set(supplied_roles)) != len(supplied_roles)
        or any(role not in ROLE_CAPABILITIES for role in supplied_roles)
    ):
        return _login_failure('entra', 'role', 403)
    roles = supplied_roles
    issuer_engine = current_app.extensions.get('cafeteria_auth_issuer_db')
    if issuer_engine is None:
        return _login_failure('entra', 'unavailable', 503)
    try:
        user_id = upsert_entra_user(issuer_engine, claims, roles)
    except ValueError:
        return _login_failure('entra', 'flow', 403)
    except SQLAlchemyError:
        return _login_failure('entra', 'unavailable', 503)
    try:
        authorization = load_user_authorization(current_app.extensions['cafeteria_db'], user_id)
    except SQLAlchemyError:
        return _login_failure('entra', 'unavailable', 503)
    if not roles or authorization is None:
        return _login_failure('entra', 'role', 403)
    if provider_sid is None:
        # OIDC makes sid optional. Without it, no later logout request can be
        # bound to this provider session, so front-channel logout defaults deny.
        current_app.logger.warning(
            'Entra ID token has no sid claim; front-channel logout will default-deny.',
        )
        return _login_accepted('entra', authorization, oid=claims['oid'], tid=claims['tid'])
    return _login_accepted(
        'entra', authorization, oid=claims['oid'], tid=claims['tid'], sid=provider_sid,
    )


@bp.post('/logout')
def logout():
    validate_csrf(request.form.get("_csrf"))
    tenant = current_app.config.get('ENTRA_TENANT_ID')
    target = current_app.config['APP_PUBLIC_BASE_URL'] + url_for('public.cafeteria_today')
    _clear_session_for_logout('auth.logout.requested')
    if (
        current_app.config['DEMO_MODE']
        or not current_app.config.get('ENTRA_ENABLED', False)
        or not tenant
    ):
        return redirect(target)
    return redirect(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout?post_logout_redirect_uri={quote(target, safe='')}")


@bp.route('/frontchannel-logout', methods=['GET', 'POST'])
def frontchannel_logout():
    if not current_app.config.get('ENTRA_ENABLED', False):
        abort(404)
    parameters = request.args if request.method == 'GET' else request.form
    unexpected_parameters = request.form if request.method == 'GET' else request.args
    parameter_names = set(parameters)
    issuer_values = parameters.getlist('iss')
    sid_values = parameters.getlist('sid')
    if (
        parameter_names != {'iss', 'sid'}
        or unexpected_parameters
        or len(issuer_values) != 1
        or len(sid_values) != 1
        or not issuer_values[0]
        or not sid_values[0]
        or len(sid_values[0]) > _MAX_PROVIDER_SID_LENGTH
        or request.files
    ):
        response = current_app.make_response(('', 400))
        response.headers['Cache-Control'] = 'no-store'
        return response

    expected_issuer = current_app.config.get('ENTRA_ISSUER', '')
    user = session.get('user')
    stored_sid = user.get('sid') if isinstance(user, dict) and user.get('provider') == 'entra' else None
    if (
        expected_issuer
        and secrets.compare_digest(issuer_values[0], expected_issuer)
        and isinstance(stored_sid, str)
        and stored_sid
        and secrets.compare_digest(sid_values[0], stored_sid)
    ):
        _clear_session_for_logout('auth.frontchannel.requested')
    response = current_app.make_response(('', 200))
    response.headers['Cache-Control'] = 'no-store'
    return response
