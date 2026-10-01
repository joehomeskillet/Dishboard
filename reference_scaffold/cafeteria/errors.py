"""HTTP error surfaces and bounded, server-side login navigation contexts."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import date
from time import time
from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import UUID

from flask import current_app, g, redirect, render_template, request, session, url_for
from markupsafe import escape
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException, InternalServerError, ServiceUnavailable
from werkzeug.wrappers import Response

_CODES = {
    400: 'REQUEST_INVALID', 401: 'AUTH_REQUIRED', 403: 'AUTH_FORBIDDEN',
    404: 'RESOURCE_NOT_FOUND', 405: 'METHOD_NOT_ALLOWED', 409: 'VERSION_CONFLICT',
    413: 'UPLOAD_TOO_LARGE', 415: 'UNSUPPORTED_FORMAT', 422: 'VALIDATION_FAILED',
    429: 'RATE_LIMITED', 500: 'INTERNAL_ERROR', 503: 'SERVICE_UNAVAILABLE',
}
_TITLES = {
    'AUTH_REQUIRED': 'Anmeldung erforderlich', 'AUTH_SESSION_INVALID': 'Bitte erneut anmelden',
    'AUTH_FORBIDDEN': 'Kein Zugriff', 'RESOURCE_NOT_FOUND': 'Seite nicht gefunden',
    'FORM_STALE': 'Formular nicht mehr aktuell', 'REQUEST_INVALID': 'Angaben prüfen',
    'METHOD_NOT_ALLOWED': 'Dieser Aufruf ist nicht möglich', 'UPLOAD_TOO_LARGE': 'Datei ist zu gross',
    'UNSUPPORTED_FORMAT': 'Dateiformat nicht unterstützt', 'RATE_LIMITED': 'Bitte kurz warten',
    'INTERNAL_ERROR': 'Vorgang konnte nicht abgeschlossen werden',
    'SERVICE_UNAVAILABLE': 'Dienst vorübergehend nicht verfügbar',
}
_DOWNLOADS = {
    'admin.export_csv', 'admin.order_basket_csv', 'admin.print_week', 'admin.shopping_list_pdf',
    'admin.recipe_revision_pdf', 'admin.print_template_preview', 'admin.recipe_print_template_preview',
    'admin.branding_preview_css', 'admin.branding_preview_logo', 'admin.recipe_asset',
}
# Deliberately enumerate reading endpoints; a future GET action is not automatically eligible.
_READS = set(('dashboard cafeteria patienten recipes_list recipe_view recipe_edit recipe_revisions '
    'recipe_revision dish_templates_list dish_template_edit local_users_list local_user_detail '
    'local_user_events access_history api_overview master_data_list master_data_detail '
    'order_home order_basket shopping_lists_index shopping_list_detail inventory_home cost_home '
    'operations_settings display_settings branding_editor screens vorlagen kitchen_calendar '
    'week_management week_review_get menu_collection menu_get header_get service_get '
    'components_get component_detail preview').split())
_WEEK_READS = set(('cafeteria patienten week_management week_review_get menu_collection '
    'menu_get header_get service_get preview').split())
_TOKEN = re.compile(r'[0-9a-f]{48}')
_TTL = 600
_NAVIGATION_BUDGET = 8
_OWNER_TOKEN_BUDGET = 16
_BUDGET_TAKE = (
    "local n=redis.call('INCR',KEYS[1]); "
    "if redis.call('TTL',KEYS[1])<0 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; "
    "return n"
)


@dataclass(frozen=True)
class ErrorView:
    code: str
    http_status: int
    title_key: str
    message_key: str
    message_params: dict = field(default_factory=dict)
    request_id: str = ''
    recovery: list[dict] = field(default_factory=list)
    frame: str = 'minimal'
    mutation_state: str = 'unknown'
    surface: str = 'html'
    auth_state: str = 'unknown'
    retry_after: str | None = None


def surface(req) -> str:
    """Endpoint contracts win over request Content-Type and Accept, including routing failures."""
    endpoint, path = req.endpoint or '', req.path
    for prefix, kind in (('/fhir', 'fhir'), ('/api', 'api'), ('/health', 'health'),
                         ('/signage', 'signage')):
        if path == prefix or path.startswith(prefix + '/'):
            return kind
    if endpoint in _DOWNLOADS or endpoint.startswith(('branding.', 'static')):
        return 'download'
    if path.startswith(('/branding/', '/static/')) or path.endswith(('.pdf', '.csv', '.png', '.css')):
        return 'download'
    if req.headers.get('Accept') and not req.accept_mimetypes['text/html']:
        return 'api' if req.accept_mimetypes['application/json'] else 'download'
    return 'html' if req.method in ('GET', 'HEAD', 'OPTIONS') else 'form_post'


def safe_return_target(target: str | None) -> str | None:
    """Accept only canonical URLs built from enumerated GET routes and bounded navigation values."""
    if not isinstance(target, str) or len(target) > 1024 or not target.startswith('/'):
        return None
    if any(ord(c) < 33 or ord(c) == 127 for c in target) or any(c in target for c in ('%', '\\', '#')):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or parts.path.startswith('//'):
        return None
    try:
        endpoint, values = current_app.url_map.bind('localhost').match(parts.path, method='GET')
        name = endpoint.removeprefix('admin.')
        if not endpoint.startswith('admin.') or name not in _READS:
            return None
        for key, value in values.items():
            if key == 'family' and value in ('cafeteria', 'patienten'):
                continue
            if key == 'kind' and value in ('foods', 'allergens', 'suppliers', 'categories'):
                continue
            if key not in ('recipe_id', 'revision_id', 'public_id') or str(UUID(str(value))) != str(value):
                return None
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=4)
        if len(dict(pairs)) != len(pairs):
            return None
        for key, value in pairs:
            if key == 'week' and name in _WEEK_READS:
                if date.fromisoformat(value).isoformat() != value or date.fromisoformat(value).weekday() != 0:
                    return None
            else:
                return None
        canonical = url_for(endpoint, **values, _external=False)
        if pairs:
            canonical += '?' + urlencode(pairs)
        return canonical if canonical == target else None
    except (HTTPException, ValueError, TypeError):
        return None


def _owner() -> str | None:
    owner = session.get('_eh_navigation')
    if isinstance(owner, str) and _TOKEN.fullmatch(owner):
        return owner
    return None


def _token_key(owner: str, token: str) -> str:
    return f'dishboard:login-navigation:{owner}:{token}'


def _state_key(owner: str, state: str) -> str:
    digest = hashlib.sha256(state.encode()).hexdigest()
    return f'dishboard:login-navigation:state:{owner}:{digest}'


def login_context(token: str | None, *, consume: bool = False) -> dict:
    owner = _owner()
    if not owner or not isinstance(token, str) or not _TOKEN.fullmatch(token):
        return {}
    client = current_app.extensions.get('cafeteria_rate_redis')
    if client is None:
        return {}
    key = _token_key(owner, token)
    if consume:
        raw = client.eval(
            "local v=redis.call('GET',KEYS[1]); redis.call('DEL',KEYS[1]); return v", 1, key)
    else:
        raw = client.get(key)
    if not raw:
        return {}
    context = json.loads(raw)
    if context.get('expires', 0) <= time() or not safe_return_target(context.get('target')):
        return {}
    return context


def _new_navigation_allowed(client) -> bool:
    """Allow an existing browser or an authenticated session; cap new anonymous owners per IP."""
    if session.get('user') is not None or _owner() is not None:
        return True
    from .auth.service import trusted_client_address
    peers = tuple(current_app.config.get('TRUSTED_PROXY_PEERS', ()))
    address = trusted_client_address(request.environ, request.remote_addr or 'unknown', peers)
    digest = hashlib.sha256(address.encode()).hexdigest()
    count = client.eval(_BUDGET_TAKE, 1, f'dishboard:login-navigation:budget:{digest}', _TTL)
    return isinstance(count, int) and count <= _NAVIGATION_BUDGET


def issue_return_token(target: str | None, notice: str = 'auth.required') -> str:
    target = safe_return_target(target) or '/admin/cafeteria'
    client = current_app.extensions.get('cafeteria_rate_redis')
    if client is None:
        # Without a server store, use the safe default; never put a target in a cookie or URL.
        return ''
    if not _new_navigation_allowed(client):
        return ''
    owner = _owner()
    if owner is None:
        session['_eh_navigation'] = secrets.token_hex(24)
        if session.get('user') is None and session.permanent:
            session.permanent = False
        owner = _owner()
    if owner is None:
        return ''
    # Keep the counter alive as long as the newest token, including across a busy window.
    count = client.eval(
        "local n=redis.call('INCR',KEYS[1]); redis.call('EXPIRE',KEYS[1],ARGV[1]); return n",
        1, f'dishboard:login-navigation:count:{owner}', _TTL,
    )
    if not isinstance(count, int) or count > _OWNER_TOKEN_BUDGET:
        return ''
    token = secrets.token_hex(24)
    context = {'target': target, 'notice': notice, 'expires': int(time()) + _TTL}
    client.set(_token_key(owner, token), json.dumps(context), ex=_TTL)
    return token


_BIND_KEEP = (
    "local t=redis.call('PTTL',KEYS[1]); if t<1 then return 0 end; "
    "redis.call('SET',KEYS[1],ARGV[1],'PX',t); return 1"
)


def bind_entra_flow(token: str, flow: dict) -> None:
    context = login_context(token)
    if not context:
        raise ServiceUnavailable()
    context['flow'] = flow
    owner = _owner()
    client = current_app.extensions.get('cafeteria_rate_redis')
    if not owner or client is None or not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise ServiceUnavailable()
    key = _token_key(owner, token)
    updated = client.eval(_BIND_KEEP, 1, key, json.dumps(context))
    if not updated:
        raise ServiceUnavailable()
    state = flow.get('state') if isinstance(flow, dict) else None
    if isinstance(state, str) and 0 < len(state) <= 1024:
        ttl = client.ttl(key)
        if isinstance(ttl, int) and ttl > 0:
            client.set(_state_key(owner, state), token, ex=ttl)


def consume_entra_flow(state: str | None) -> tuple[dict, dict]:
    owner = _owner()
    client = current_app.extensions.get('cafeteria_rate_redis')
    if not owner or client is None or not isinstance(state, str) or not state or len(state) > 1024:
        return {}, {}
    raw_token = client.get(_state_key(owner, state))
    if not raw_token:
        return {}, {}
    token = raw_token.decode() if isinstance(raw_token, bytes) else raw_token
    peeked = login_context(token)
    flow = peeked.get('flow') if isinstance(peeked.get('flow'), dict) else {}
    stored = flow.get('state')
    if not isinstance(stored, str) or not secrets.compare_digest(stored, state):
        return {}, {}
    client.delete(_state_key(owner, state))
    context = login_context(token, consume=True)
    stored_flow = context.get('flow') if isinstance(context.get('flow'), dict) else {}
    return stored_flow, context


def request_id() -> str:
    value = request.environ.get('dishboard.error_id')
    if value is None:
        value = 'EH-' + secrets.token_hex(8)
        request.environ['dishboard.error_id'] = value
    return value


_LOG = logging.getLogger('cafeteria.errors')


def _diagnose(event: str, error: Exception, status: int) -> None:
    try:
        route = request.url_rule.rule if request.url_rule else 'unmatched'
        _LOG.warning(
            'event=%s status=%s route=%s reference=%s exception=%s',
            event, status, route, request_id(), type(error).__name__,
            exc_info=(type(error), error, error.__traceback__),
        )
    except Exception:
        # Diagnostics must not prevent the isolated fallback from reaching the caller.
        return


def error_view(error: HTTPException, *, code: str | None = None) -> ErrorView:
    status = error.code or 500
    code = code or ('FORM_STALE' if isinstance(error, FormStale) else _CODES.get(status, 'REQUEST_INVALID'))
    kind = surface(request)
    verified = getattr(g, 'auth_user', None) is not None
    state = getattr(g, 'eh_auth_state', 'authenticated' if verified else 'unknown')
    mutation = getattr(g, 'eh_mutation_state', 'unknown' if request.method not in ('GET', 'HEAD') else 'not_started')
    if code == 'FORM_STALE':
        mutation = 'not_started'
    if kind != 'form_post':
        mutation = ''
    elif mutation == 'unknown':
        mutation = 'unclear'
    params = {}
    if status < 500 and error.description != type(error).description:
        params['detail'] = str(error.description)[:500]
    recovery = []
    if kind in ('html', 'form_post'):
        if status == 401:
            recovery.append(dict(semantic='actions.login', label_key='actions.login.label',
                                 href='/auth/login', method='get', primary=True))
        else:
            recovery.append(dict(semantic='navigation.overview', label_key='navigation.overview.label',
                                 href='/cafeteria/heute/', method='get', primary=True))
        target = safe_return_target(request.full_path.rstrip('?')) if request.method in ('GET', 'HEAD') else None
        if status >= 500 and target:
            recovery.insert(0, dict(semantic='actions.reload', label_key='actions.reload.label',
                                   href=target, method='get', primary=True))
    title_key = 'auth.unavailable' if status == 503 and request.blueprint == 'auth' else f'errors.{code}.title'
    return ErrorView(code, status, title_key, f'errors.{code}.message', params,
        request_id(), recovery, 'minimal' if status >= 500 else ('admin' if verified else 'auth'),
        mutation, kind, state, error.get_response().headers.get('Retry-After'))


def _minimal(view: ErrorView) -> str:
    title = _TITLES.get(view.code, 'Anfrage konnte nicht verarbeitet werden')
    if view.title_key == 'auth.unavailable':
        title = 'Anmeldung momentan nicht verfügbar'
    message = 'Bitte versuchen Sie einen sicheren neuen Seitenaufruf.'
    if view.http_status == 401:
        message = 'Bitte erneut anmelden. Eingaben werden nicht über die Anmeldung hinweg gesichert.'
    elif view.code == 'FORM_STALE':
        message = 'Das Formular ist nicht mehr aktuell. Öffnen Sie es erneut und prüfen Sie Ihre Eingaben.'
    elif view.http_status == 403:
        message = 'Für diese Seite oder Aktion fehlt Ihnen die Berechtigung.'
    if view.mutation_state == 'not_started' and view.surface == 'form_post':
        message += ' Die angeforderte Aktion wurde vor der Ausführung abgelehnt.'
    elif view.mutation_state == 'unclear' and view.surface == 'form_post':
        message += ' Es ist unklar, ob die Änderung gespeichert wurde. Prüfen Sie den gespeicherten Stand.'
    labels = {'actions.login': 'Anmelden', 'actions.reload': 'Neu laden', 'navigation.overview': 'Zur Übersicht'}
    links = ' '.join(f'<a href="{escape(item["href"])}">{labels[item["semantic"]]}</a>' for item in view.recovery)
    detail = escape(view.message_params.get('detail', ''))
    detail_html = f'<p>{detail}</p>' if detail.strip() else ''
    return (f'<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>{title} · Dishboard</title>'
        f'<main id="main-content"><h1>{title}</h1><p>{message}</p>{detail_html}{links}'
        f'<p>{view.code} · {view.http_status} · Referenz: {view.request_id}</p></main></html>')


def render_error(error: HTTPException, *, code: str | None = None, minimal: bool = False) -> Response:
    if error.code in (401, 403) and error.response is not None:
        # A guard or domain boundary already supplied the complete HTTP response.
        return error.get_response()
    view = error_view(error, code=code)
    response = error.get_response()
    if view.surface == 'fhir':
        issue = {404: 'not-found', 405: 'not-supported', 401: 'login', 403: 'forbidden'}.get(view.http_status, 'exception')
        response.set_data(json.dumps({'resourceType': 'OperationOutcome', 'issue': [
            {'severity': 'error', 'code': issue, 'diagnostics': _TITLES.get(view.code, 'Anfrage fehlgeschlagen.')}]}))
        response.content_type = 'application/fhir+json'
    elif view.surface in ('api', 'health'):
        code = {404: 'not_found', 405: 'method_not_allowed', 500: 'internal_error', 503: 'unavailable'}.get(
            view.http_status, view.code.lower())
        response.set_data(json.dumps({'error': code, 'detail': _TITLES.get(view.code, 'Anfrage fehlgeschlagen.')}))
        response.content_type = 'application/json'
    elif view.surface == 'download':
        detail = view.message_params.get('detail') or _TITLES.get(view.code, 'Anfrage fehlgeschlagen.')
        response.set_data(f'{view.code}: {detail}')
        response.content_type = 'text/plain; charset=utf-8'
    else:
        try:
            payload = asdict(view)
            if minimal or view.http_status >= 500 or view.surface == 'signage':
                payload['frame'] = 'minimal'
                html = current_app.jinja_env.get_template('errors/minimal.html').render(
                    error=payload, ui_locale=current_app.config.get('UI_LOCALE', 'de'))
            else:
                html = render_template('errors/page.html', error=payload)
        except Exception as renderer_error:
            # One isolated fallback. The traceback stays in the server log, not in the response.
            _diagnose('error.renderer_failed', renderer_error, view.http_status)
            html = _minimal(view)
        response.set_data(html)
        response.content_type = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Request-ID'] = view.request_id
    return response


def authentication_required(*, invalid: bool = False) -> Response:
    from werkzeug.exceptions import Unauthorized
    g.eh_auth_state = 'invalid' if invalid else 'anonymous'
    g.eh_mutation_state = 'not_started'
    if (surface(request) == 'html' and request.method in ('GET', 'HEAD')
            and request.blueprint == 'admin' and 'auth.login' in current_app.view_functions):
        token = issue_return_token(request.full_path.rstrip('?'), 'auth.session_invalid' if invalid else 'auth.required')
        login_url = url_for('auth.login', return_token=token) if token else url_for('auth.login')
        response = redirect(login_url, code=302)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return render_error(Unauthorized(), code='AUTH_SESSION_INVALID' if invalid else 'AUTH_REQUIRED')


class FormStale(BadRequest):
    """Typed CSRF failure; existing domain handlers still own their 400 input context."""

    def __init__(self, description: str | None = 'CSRF-Prüfung fehlgeschlagen.',
                 response: Response | None = None) -> None:
        # An instance description keeps the domain detail visible in error_view.
        super().__init__(description=description, response=response)


def _session_is_authenticated(sess) -> bool:
    user = sess.get('user')
    version = sess.get('authz_version')
    return isinstance(user, dict) and type(user.get('id')) is int and type(version) is int


def _cap_anonymous_session(delegate, sess) -> None:
    if not sess or _session_is_authenticated(sess):
        return
    client = getattr(delegate, 'client', None)
    store_id_for = getattr(delegate, '_get_store_id', None)
    sid = getattr(sess, 'sid', None)
    if client is None or not callable(store_id_for) or not sid:
        return
    try:
        store_id = store_id_for(sid)
        ttl = client.ttl(store_id)
        if isinstance(ttl, int) and ttl > _TTL:
            client.expire(store_id, _TTL)
    except RedisError as error:
        _diagnose('error.session_ttl', error, 503)


class _SessionBoundary:
    """Handle Redis failures before dispatch or after response processing without replaying work."""
    def __init__(self, delegate):
        self.delegate = delegate

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    @property
    def key_prefix(self):
        return self.delegate.key_prefix

    @key_prefix.setter
    def key_prefix(self, value):
        self.delegate.key_prefix = value

    def open_session(self, app, req):
        try:
            return self.delegate.open_session(app, req)
        except RedisError:
            req.environ['dishboard.session_unavailable'] = True
            return self.delegate.make_null_session(app)

    def save_session(self, app, sess, response):
        try:
            if sess and not _session_is_authenticated(sess) and sess.permanent:
                sess.permanent = False
            self.delegate.save_session(app, sess, response)
            _cap_anonymous_session(self.delegate, sess)
        except RedisError as error:
            _diagnose('error.session_save_failed', error, 503)
            fallback = render_error(ServiceUnavailable(), minimal=True)
            response.direct_passthrough = False
            response.set_data(fallback.get_data())
            response.status_code = 503
            for name in ('Location', 'Content-Disposition', 'Content-Encoding', 'ETag', 'Set-Cookie'):
                response.headers.pop(name, None)
            response.headers.update(fallback.headers)


def register_error_handlers(app) -> None:
    app.session_interface = _SessionBoundary(app.session_interface)

    @app.before_request
    def session_available():
        if request.environ.get('dishboard.session_unavailable'):
            return render_error(ServiceUnavailable(), minimal=True)

    @app.after_request
    def auth_cache_headers(response):
        if request.blueprint == 'auth':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return render_error(error)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        unavailable = isinstance(error, (RedisError, SQLAlchemyError))
        _diagnose('error.unhandled', error, 503 if unavailable else 500)
        return render_error(ServiceUnavailable() if unavailable else InternalServerError())
