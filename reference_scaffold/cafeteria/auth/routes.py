from __future__ import annotations

from urllib.parse import quote

import msal
from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for

from ..db import demo_user, upsert_entra_user
from ..roles import ROLE_CAPABILITIES

bp = Blueprint('auth', __name__, url_prefix='/auth')


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
        session.clear()
        demo = demo_user(current_app.extensions['cafeteria_db'])
        session['user'] = {'id': demo['id'], 'name': demo['name'], 'oid': 'demo-user', 'tid': 'demo-tenant'}
        session['roles'] = ['Cafeteria.Editor', 'Cafeteria.Publisher']
        session.permanent = True
        return redirect(url_for('admin.cafeteria'))
    if not cfg['ENTRA_TENANT_ID'] or not cfg['ENTRA_CLIENT_ID'] or not cfg['ENTRA_CLIENT_SECRET']:
        return render_template('auth/error.html', message='Entra-Konfiguration ist unvollständig.'), 503
    flow = _client().initiate_auth_code_flow(scopes=[], redirect_uri=cfg['APP_PUBLIC_BASE_URL'] + url_for('auth.callback'))
    session['auth_flow'] = flow
    return redirect(flow['auth_uri'])


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
    roles = sorted(set(claims.get('roles') or []) & set(ROLE_CAPABILITIES))
    if not roles:
        abort(403)
    user_id = upsert_entra_user(current_app.extensions['cafeteria_db'], claims, roles)
    session.clear()
    session['user'] = {'id': user_id, 'name': claims.get('name'), 'oid': claims['oid'], 'tid': claims['tid']}
    session['roles'] = roles
    session.permanent = True
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
