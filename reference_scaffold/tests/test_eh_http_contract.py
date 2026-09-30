"""EH HTTP contracts: real factory, Redis session and PostgreSQL authorization."""
# ruff: noqa: F811 -- shared fixture imported for pytest injection.
import re
from urllib.parse import urlsplit

import pytest
from flask import abort
from redis.exceptions import RedisError

from test_auth_routes import auth_app, _csrf_payload, _provision  # noqa: F401


def test_eh_t01_app_without_login_endpoint_denies_without_broken_redirect():
    from flask import Blueprint, Flask
    from cafeteria.roles import require_capability
    app = Flask(__name__)
    admin = Blueprint('admin', __name__, url_prefix='/admin')
    @admin.get('/private')
    @require_capability('draft.read')
    def private():
        raise AssertionError('Anonymous caller must not reach protected work')
    app.register_blueprint(admin)
    response = app.test_client().get('/admin/private')
    assert response.status_code == 401 and 'Location' not in response.headers


def test_eh_t01_t22_anonymous_reads_redirect_but_posts_never_replay(auth_app):
    app, _, _ = auth_app
    client = app.test_client()
    for method in ('get', 'head'):
        response = getattr(client, method)('/admin/patienten?week=2026-09-28')
        assert response.status_code == 302
        assert urlsplit(response.location).path == '/auth/login'
        assert 'return_token=' in response.location
        assert 'week=' not in response.location and 'next=' not in response.location
        assert response.headers['Cache-Control'] == 'no-store'
        if method == 'head':
            assert response.data == b''
    response = client.post('/admin/patienten/publish', data={'private': 'NEVER-ECHO'})
    assert response.status_code == 401
    assert 'Location' not in response.headers
    assert 'AUTH_REQUIRED' in response.text
    assert 'NEVER-ECHO' not in response.text
    assert 'WWW-Authenticate' not in response.headers  # Cookie auth has no invented scheme.


def test_eh_t24_t25_t26_machine_routes_and_routing_errors(auth_app):
    app, _, _ = auth_app
    client = app.test_client()
    for path in ('/missing', '/admin/missing'):
        response = client.get(path)
        assert response.status_code == 404
        assert 'RESOURCE_NOT_FOUND' in response.text
    for path, mimetype in (('/fhir/missing', 'application/fhir+json'),
                           ('/api/v1/missing', 'application/json')):
        response = client.get(path, headers={'Accept': '*/*'})
        assert response.status_code == 404 and response.mimetype == mimetype
        assert 'Location' not in response.headers
    fhir = client.get('/fhir/missing').json
    assert fhir['resourceType'] == 'OperationOutcome'
    response = client.post('/health/live')
    assert response.status_code == 405
    assert 'GET' in response.headers['Allow']
    assert response.is_json
    assert client.head('/missing').data == b''


def test_eh_t27_t28_t40_downloads_and_bearer_contract(auth_app):
    app, _, _ = auth_app
    client = app.test_client()
    api = client.get('/api/v1/keys/me', headers={'Accept': 'text/html'})
    assert api.status_code == 401 and api.is_json
    assert api.headers['WWW-Authenticate'] == 'Bearer realm="dishboard-api"'
    for path in ('/admin/export/staff_guest.csv', '/admin/patienten/preview/print'):
        response = client.get(path, headers={'Accept': 'text/html'})
        assert response.status_code == 401
        assert 'Location' not in response.headers
        assert response.mimetype != 'text/html'
    assert client.get('/health/live').json == {'status': 'ok'}


def test_eh_t30_t31_t35_renderer_failure_has_one_safe_fallback(auth_app, monkeypatch, caplog):
    app, _, _ = auth_app
    @app.get('/failure')
    def fail():
        raise RuntimeError('SECRET-SQL-CREDENTIAL')
    @app.context_processor
    def broken_context():
        raise AssertionError('context must not run')
    def broken_template(*args, **kwargs):
        raise RuntimeError('SECRET-TEMPLATE')
    monkeypatch.setattr(app.jinja_env, 'get_template', broken_template)
    response = app.test_client().get('/failure', headers={'X-Request-ID': 'ATTACKER'})
    assert response.status_code == 500
    assert 'INTERNAL_ERROR' in response.text
    assert 'SECRET' not in response.text and 'ATTACKER' not in response.text
    assert re.fullmatch(r'EH-[0-9a-f]{16}', response.headers['X-Request-ID'])
    assert response.headers['Cache-Control'] == 'no-store'
    assert "default-src 'self'" in response.headers['Content-Security-Policy']
    assert response.headers['X-Request-ID'] in caplog.text
    assert 'RuntimeError' in caplog.text
    assert 'SECRET' not in caplog.text and 'ATTACKER' not in caplog.text


@pytest.mark.parametrize('stage', ('open_session', 'save_session'))
def test_eh_t31_session_outage_is_503_without_authentication(auth_app, monkeypatch, stage):
    app, _, _ = auth_app
    interface = app.session_interface
    delegate = getattr(interface, 'delegate', interface)
    def unavailable(*args, **kwargs):
        raise RedisError('SECRET-REDIS')
    monkeypatch.setattr(delegate, stage, unavailable)
    response = app.test_client().get('/auth/local')
    assert response.status_code == 503
    assert 'SERVICE_UNAVAILABLE' in response.text
    assert 'SECRET' not in response.text
    assert 'Location' not in response.headers


def test_eh_t12_t21_auth_csrf_then_business_logic(auth_app):
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    client = app.test_client()
    client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery'))
    forbidden = client.get('/admin/api')
    assert forbidden.status_code == 403
    assert 'AUTH_FORBIDDEN' in forbidden.text and 'Location' not in forbidden.headers
    stale = client.post('/admin/patienten/header', data={'_csrf': 'invalid'})
    assert stale.status_code == 400
    assert 'FORM_STALE' in stale.text


def test_eh_t13_t25_http_descriptions_headers_and_direct_responses(auth_app):
    app, _, _ = auth_app
    @app.get('/described')
    def described():
        abort(404, description='Erlaubte fachliche Erklärung <script>')
    @app.get('/direct')
    def direct():
        return 'EXISTING FORM VALUES', 404
    client = app.test_client()
    described_response = client.get('/described')
    assert 'Erlaubte fachliche Erklärung &lt;script&gt;' in described_response.text
    assert described_response.status_code == 404
    assert client.get('/direct').text == 'EXISTING FORM VALUES'
    response = client.post('/described')
    assert response.status_code == 405 and 'GET' in response.headers['Allow']


def test_eh_t26_t35_error_catalog_preserves_status_and_safe_write_recovery(auth_app):
    app, _, _ = auth_app
    @app.route('/catalog-error/<int:status>', methods=['GET', 'POST'])
    def catalog_error(status):
        abort(status)
    client = app.test_client()
    for status, code in ((400, 'REQUEST_INVALID'), (401, 'AUTH_REQUIRED'), (403, 'AUTH_FORBIDDEN'),
                         (404, 'RESOURCE_NOT_FOUND'), (405, 'METHOD_NOT_ALLOWED'), (413, 'UPLOAD_TOO_LARGE'),
                         (415, 'UNSUPPORTED_FORMAT'), (429, 'RATE_LIMITED'), (500, 'INTERNAL_ERROR'),
                         (503, 'SERVICE_UNAVAILABLE')):
        response = client.get(f'/catalog-error/{status}')
        assert response.status_code == status and code in response.text
        assert response.mimetype == 'text/html'
        assert client.head(f'/catalog-error/{status}').data == b''
    uncertain = client.post('/catalog-error/500', data={'private': 'MUST-NOT-ECHO'})
    assert 'unklar' in uncertain.text and 'MUST-NOT-ECHO' not in uncertain.text
    assert '<form' not in uncertain.text and 'Neu laden' not in uncertain.text


def test_eh_t30_context_processor_outage_renders_without_calling_it_again(auth_app):
    from flask import render_template
    from sqlalchemy.exc import SQLAlchemyError
    app, _, _ = auth_app
    @app.get('/render-outage')
    def render_outage():
        return render_template('auth/local_login.html')
    @app.context_processor
    def unavailable_context():
        raise SQLAlchemyError('PRIVATE-DATABASE-DETAIL')
    response = app.test_client().get('/render-outage')
    assert response.status_code == 503 and 'SERVICE_UNAVAILABLE' in response.text
    assert 'PRIVATE-DATABASE-DETAIL' not in response.text


def test_eh_t41_mandatory_audit_failure_remains_fail_closed(auth_app, monkeypatch):
    from cafeteria.auth import routes
    from cafeteria.auth.access_events import AccessEventUnavailable
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    def unavailable(*args, **kwargs):
        raise AccessEventUnavailable('PRIVATE-AUDIT-DETAIL')
    monkeypatch.setattr(routes, 'record_access_event', unavailable)
    client = app.test_client()
    response = client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery'))
    assert response.status_code == 503 and 'Location' not in response.headers
    assert 'PRIVATE-AUDIT-DETAIL' not in response.text
    with client.session_transaction() as sess:
        assert 'user' not in sess and 'authz_version' not in sess


def test_eh_t40_stream_failure_does_not_append_html_or_restart(auth_app):
    from flask import Response
    app, _, _ = auth_app
    @app.get('/stream.pdf')
    def stream():
        def chunks():
            yield b'%PDF-partial'
            raise RuntimeError('interrupted stream')
        return Response(chunks(), mimetype='application/pdf')
    response = app.test_client().get('/stream.pdf', buffered=False)
    iterator = iter(response.response)
    assert next(iterator) == b'%PDF-partial'
    with pytest.raises(RuntimeError, match='interrupted stream'):
        next(iterator)
