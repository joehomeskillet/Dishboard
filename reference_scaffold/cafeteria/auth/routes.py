from __future__ import annotations

from urllib.parse import quote

import msal
from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for

from ..db import demo_user, upsert_entra_user
from ..roles import ROLE_CAPABILITIES
from ..security import validate_csrf
from .service import (
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
    validate_csrf(request.form.get('csrf_token'))
    username = request.form.get('username', '')
    password = request.form.get('password', '')
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
        session.clear()
        return render_template('auth/error.html', message='Anmeldung vorübergehend nicht verfügbar.'), 503
    except RateLimitExceeded:
        session.clear()
        return render_template('auth/error.html', message='Anmeldung fehlgeschlagen.'), 429

    identity = authenticate_local_user(
        current_app.extensions['cafeteria_db'],
        username=username,
        password=password,
    )
    if identity is None:
        session.clear()
        return render_template('auth/error.html', message='Anmeldung fehlgeschlagen.'), 401
    try:
        clear_login_attempts(redis_client, key)
    except RateLimitUnavailable:
        session.clear()
        return render_template('auth/error.html', message='Anmeldung vorübergehend nicht verfügbar.'), 503
    _establish_session(
        identity.user_id,
        identity.display_name,
        identity.authz_version,
        provider=identity.auth_provider,
    )
    return redirect(url_for('admin.cafeteria'))


@bp.get('/callback')
def callback():
    flow = session.pop('auth_flow', None)
    if not flow:
        return render_template('auth/error.html', message='Anmeldezustand fehlt oder ist abgelaufen.'), 400
    try:
        result = _client().acquire_token_by_auth_code_flow(flow, request.args)
    except ValueError:
        return render_template('auth/error.html', message='State- oder Nonce-Prüfung fehlgeschlagen.'), 400
    if 'error' in result:
        return render_template('auth/error.html', message=result.get('error_description', result['error'])), 401
    claims = result.get('id_token_claims') or {}
    cfg = current_app.config
    if claims.get('tid') != cfg['ENTRA_TENANT_ID'] or not claims.get('oid'):
        abort(403)
    if claims.get('aud') and claims.get('aud') != cfg['ENTRA_CLIENT_ID']:
        abort(403)
    supplied_roles = claims.get('roles') or []
    if not isinstance(supplied_roles, list) or any(not isinstance(role, str) for role in supplied_roles):
        session.clear()
        abort(403)
    if (
        len(set(supplied_roles)) != len(supplied_roles)
        or any(role not in ROLE_CAPABILITIES for role in supplied_roles)
    ):
        session.clear()
        abort(403)
    roles = supplied_roles
    issuer_engine = current_app.extensions.get('cafeteria_auth_issuer_db')
    if issuer_engine is None:
        return render_template('auth/error.html', message='Anmeldung vorübergehend nicht verfügbar.'), 503
    try:
        user_id = upsert_entra_user(issuer_engine, claims, roles)
    except ValueError:
        abort(403)
    authorization = load_user_authorization(current_app.extensions['cafeteria_db'], user_id)
    if not roles or authorization is None:
        session.clear()
        abort(403)
    _establish_session(
        authorization.user_id,
        authorization.display_name,
        authorization.authz_version,
        oid=claims['oid'],
        tid=claims['tid'],
        provider=authorization.auth_provider,
    )
    return redirect(url_for('admin.cafeteria'))


@bp.get('/logout')
def logout():
    tenant = current_app.config.get('ENTRA_TENANT_ID')
    target = current_app.config['APP_PUBLIC_BASE_URL'] + url_for('public.cafeteria_today')
    session.clear()
    if current_app.config['DEMO_MODE'] or not tenant:
        return redirect(target)
    return redirect(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout?post_logout_redirect_uri={quote(target, safe='')}")


@bp.route('/frontchannel-logout', methods=['GET', 'POST'])
def frontchannel_logout():
    session.clear()
    return '', 200
