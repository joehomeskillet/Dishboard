"""Browser evidence for the error and sign-in family (EH-2).

The fixture renders the templates with an example context. It does not boot the
database, Redis, or the production error handlers.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace

import pytest
from flask import Blueprint, Flask, current_app, render_template, request, session
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui

SCAFFOLD = Path(__file__).resolve().parents[1]
AUDIT = SCAFFOLD.parent / '.claude/state/EH-2-evidence'
SECRET_NAME = 'Geheim Nutzer'
EH11 = (
    ('AUTH_REQUIRED', 'Anmeldung erforderlich', 'Sign-in required'),
    ('AUTH_SESSION_INVALID', 'Bitte erneut anmelden', 'Please sign in again'),
    ('AUTH_FORBIDDEN', 'Kein Zugriff', 'No access'),
    ('RESOURCE_NOT_FOUND', 'Seite nicht gefunden', 'Page not found'),
    ('REQUEST_INVALID', 'Anfrage konnte nicht verarbeitet werden', 'Request could not be processed'),
    ('FORM_STALE', 'Formular nicht mehr aktuell', 'Form is out of date'),
    ('VALIDATION_FAILED', 'Angaben prüfen', 'Check your entries'),
    ('VERSION_CONFLICT', 'Zwischenzeitlich geändert', 'Changed in the meantime'),
    ('METHOD_NOT_ALLOWED', 'Dieser Aufruf ist nicht möglich', 'This request is not possible'),
    ('UPLOAD_TOO_LARGE', 'Datei ist zu gross', 'File is too large'),
    ('UNSUPPORTED_FORMAT', 'Dateiformat nicht unterstützt', 'File format not supported'),
    ('RATE_LIMITED', 'Bitte kurz warten', 'Please wait briefly'),
    ('INTERNAL_ERROR', 'Vorgang konnte nicht abgeschlossen werden', 'The action could not be completed'),
    ('SERVICE_UNAVAILABLE', 'Dienst vorübergehend nicht verfügbar', 'Service temporarily unavailable'),
    ('GATEWAY_ERROR', 'Anwendung momentan nicht erreichbar', 'Application currently unreachable'),
    ('GATEWAY_TIMEOUT', 'Anwendung momentan nicht erreichbar', 'Application currently unreachable'),
    ('NETWORK_UNAVAILABLE', 'Verbindung unterbrochen', 'Connection interrupted'),
)
ADMIN_ENDPOINTS = (
    'cafeteria', 'patienten', 'week_management', 'kitchen_calendar',
    'menu_collection', 'components_get', 'master_data_list',
    'preview', 'screens', 'vorlagen', 'import_preview', 'api_overview',
)
OVERVIEW = {
    'semantic': 'navigation.overview',
    'label_key': 'navigation.overview.label',
    'href': '/eh/overview',
    'method': 'get',
    'primary': True,
}
RELOAD = {
    'semantic': 'actions.reload',
    'label_key': 'actions.reload.label',
    'href': '/eh/minimal',
    'method': 'get',
    'primary': True,
}


def _locale() -> None:
    lang = request.args.get('lang', 'de')
    current_app.config['UI_LOCALE'] = lang if lang in {'de', 'en'} else 'de'


def _add_endpoints(blueprint: Blueprint, names: tuple[str, ...]) -> None:
    for name in names:
        def view() -> str:
            return 'ok'
        view.__name__ = name
        blueprint.add_url_rule(f'/{name}', name, view)


def _error(code: str, *, frame: str, status: int, request_id: str,
           recovery: list[dict[str, object]] | None = None,
           mutation_state: str = '', params: dict[str, str] | None = None) -> dict[str, object]:
    return {
        'code': code,
        'http_status': status,
        'title_key': f'errors.{code}.title',
        'message_key': f'errors.{code}.message',
        'message_params': params or {},
        'request_id': request_id,
        'recovery': [] if recovery is None else recovery,
        'frame': frame,
        'mutation_state': mutation_state,
    }


def _configure(app: Flask) -> None:
    app.secret_key = 'eh-2-test'
    app.config.update(TESTING=True, UI_LOCALE='de', ENTRA_ENABLED=False)
    register_ui(app)


def build_bare_app() -> Flask:
    """Minimal frame without branding or CSRF context processors."""
    app = Flask(
        'eh_bare',
        template_folder=str(SCAFFOLD / 'cafeteria' / 'templates'),
        static_folder=str(SCAFFOLD / 'cafeteria' / 'static'),
    )
    _configure(app)

    @app.before_request
    def _plant() -> None:
        session['user'] = {'name': SECRET_NAME, 'role': 'admin'}

    @app.get('/')
    def index() -> str:
        _locale()
        error = _error(
            'INTERNAL_ERROR', frame='minimal', status=500, request_id='EH-31B8',
            recovery=[{**RELOAD, 'primary': True}, {**OVERVIEW, 'primary': False}],
        )
        return render_template('errors/minimal.html', error=error)

    @app.get('/post')
    def post_action() -> str:
        _locale()
        recovery = [{**RELOAD, 'method': 'post', 'href': '/post'}]
        error = _error('INTERNAL_ERROR', frame='minimal', status=500, request_id='EH-POST', recovery=recovery)
        return render_template('errors/minimal.html', error=error)

    return app


def build_family_app() -> Flask:
    app = Flask(
        'eh_family',
        template_folder=str(SCAFFOLD / 'cafeteria' / 'templates'),
        static_folder=str(SCAFFOLD / 'cafeteria' / 'static'),
    )
    _configure(app)
    register_template_filters(app)
    admin = Blueprint('admin', __name__)
    auth = Blueprint('auth', __name__)
    public = Blueprint('public', __name__)
    branding = Blueprint('branding', __name__)
    _add_endpoints(admin, ADMIN_ENDPOINTS)
    _add_endpoints(auth, ('local_login', 'login', 'logout'))
    _add_endpoints(public, ('cafeteria_today', 'cafeteria_week', 'patient_week'))

    @branding.get('/stylesheet')
    def stylesheet() -> str:
        return ''

    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(public, url_prefix='/public')
    app.register_blueprint(branding, url_prefix='/branding')

    @app.context_processor
    def _shell() -> dict[str, object]:
        return {
            'brand': SimpleNamespace(id=0, config=None),
            'csrf_token': lambda: 'test-csrf',
            'can_browse_recipes': False,
            'can_configure_display': False,
            'can_manage_users': False,
            'profile': 'staff_guest',
        }

    @app.before_request
    def _plant() -> None:
        if request.args.get('session_user') == '1':
            session['user'] = {'name': SECRET_NAME, 'role': 'admin'}
        else:
            session.pop('user', None)

    @app.get('/eh/overview')
    def overview() -> str:
        return 'overview'

    @app.get('/eh/login')
    def login_page() -> str:
        _locale()
        methods = request.args.get('methods')
        method_map = {
            'entra': {'local': False, 'entra': True},
            'both': {'local': True, 'entra': True},
            'none': {'local': False, 'entra': False},
            'local': {'local': True, 'entra': False},
        }.get(methods or '')
        return render_template(
            'auth/local_login.html',
            notice_key=request.args.get('notice') or None,
            methods=method_map,
            error_key=request.args.get('error_key') or None,
            return_token=request.args.get('return_token') or None,
            username='',
        )

    @app.get('/eh/legacy')
    def legacy() -> str:
        _locale()
        return render_template('auth/error.html', message='Keine Anmeldung konfiguriert.')

    @app.get('/eh/admin')
    def admin_error() -> str:
        _locale()
        error = _error(
            'AUTH_FORBIDDEN', frame='admin', status=403, request_id='EH-7C24',
            recovery=[OVERVIEW],
        )
        return render_template('errors/page.html', error=error)

    @app.get('/eh/minimal')
    def minimal_error() -> str:
        _locale()
        error = _error(
            'INTERNAL_ERROR', frame='minimal', status=500, request_id='EH-31B8',
            recovery=[{**RELOAD, 'primary': True}, {**OVERVIEW, 'primary': False}],
        )
        return render_template('errors/page.html', error=error)

    @app.get('/eh/session')
    def session_error() -> str:
        _locale()
        login = {
            'semantic': 'actions.login',
            'label_key': 'actions.login.label',
            'href': '/eh/login',
            'method': 'get',
            'primary': True,
        }
        error = _error(
            'AUTH_SESSION_INVALID', frame='auth', status=401, request_id='EH-SESSION',
            recovery=[login], mutation_state='not_started',
        )
        return render_template('errors/page.html', error=error)

    @app.get('/eh/upload')
    def upload_error() -> str:
        _locale()
        error = _error(
            'UPLOAD_TOO_LARGE', frame='auth', status=413, request_id='EH-UPLOAD',
            params={'limit': '8 MB'},
        )
        return render_template('errors/page.html', error=error)

    @app.get('/eh/code/<code>')
    def by_code(code: str) -> str:
        _locale()
        error = _error(code, frame='minimal', status=400, request_id='EH-CODE')
        return render_template('errors/minimal.html', error=error)

    return app


@pytest.fixture(scope='module')
def family() -> tuple[Flask, str]:
    app = build_family_app()
    server = make_server('127.0.0.1', 0, app, threaded=False)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield app, f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            yield instance
        finally:
            instance.close()


def _html(app: Flask, path: str) -> str:
    response = app.test_client().get(path)
    assert response.status_code == 200, response.get_data(as_text=True)[:1500]
    return response.get_data(as_text=True)


def test_minimal_frame_has_no_context_processor_dependency() -> None:
    app = build_bare_app()
    html = _html(app, '/')
    assert 'data-eh-frame="minimal"' in html
    assert '/static/errors.css' in html
    assert '/static/tokens.css' in html
    assert '/static/img/suedhang-logo.png' in html
    assert 'navbar-vertical' not in html
    assert 'Küche Administration' not in html
    assert SECRET_NAME not in html
    assert 'data-brand-stylesheet' not in html
    assert '<script' not in html
    assert ' style="' not in html
    assert 'name="_csrf"' not in html
    assert html.count('<h1') == 1
    assert 'Neu laden' in html
    assert 'location.reload' not in html
    posted = _html(app, '/post')
    assert 'name="_csrf"' not in posted
    assert 'Neu laden' in posted


def test_frames_languages_and_login_variants(family: tuple[Flask, str]) -> None:
    app, _origin = family
    login = _html(app, '/eh/login?session_user=1')
    assert 'data-eh-frame="auth"' in login
    assert '<h1 id="local-login-title">Anmelden</h1>' in login
    assert login.count('<h1') == 1
    assert 'navbar-vertical' not in login
    assert SECRET_NAME not in login
    assert '<script' not in login
    assert ' style="' not in login
    assert login.count('class="auth-field"') == 2
    assert 'auth-org-link' not in login
    assert '<title>Anmelden · Südhang Menüplanung</title>' in login

    both = _html(app, '/eh/login?methods=both&notice=auth.required&return_token=opaque-token')
    assert 'Anmeldung erforderlich' in both
    assert 'Bitte anmelden, um diesen Bereich zu öffnen.' in both
    assert 'name="return_token" value="opaque-token"' in both
    assert 'auth-org-divider' in both
    assert 'auth-org-primary' not in both
    assert both.count('<h1') == 1

    entra = _html(app, '/eh/login?methods=entra&return_token=opaque-token')
    assert 'class="auth-field"' not in entra
    assert 'auth-org-primary' in entra
    assert 'name="return_token"' in entra
    assert 'autocomplete="username"' not in entra

    failed = _html(app, '/eh/login?error_key=auth.failed')
    assert 'Anmeldung fehlgeschlagen.' in failed
    none = _html(app, '/eh/login?methods=none')
    assert 'Die Anmeldung ist momentan nicht verfügbar.' in none
    assert 'class="auth-field"' not in none

    admin = _html(app, '/eh/admin?session_user=1')
    assert 'data-eh-frame="admin"' in admin
    assert 'navbar-vertical' in admin
    assert SECRET_NAME in admin
    assert 'Kein Zugriff' in admin
    assert 'Fehler 403' in admin
    assert 'EH-7C24' in admin
    assert 'Zur Übersicht' in admin
    assert '>Support<' not in admin
    assert admin.count('data-semantic="navigation.overview"') == 1

    minimal = _html(app, '/eh/minimal?session_user=1')
    assert 'data-eh-frame="minimal"' in minimal
    assert 'navbar-vertical' not in minimal
    assert SECRET_NAME not in minimal
    assert 'Neu laden' in minimal
    assert 'href="/eh/minimal"' in minimal
    assert 'location.reload' not in minimal
    assert '<script' not in minimal

    session_page = _html(app, '/eh/session')
    assert 'Die angeforderte Aktion wurde vor der Ausführung abgelehnt.' in session_page
    assert 'Anmelden' in session_page
    assert 'Ihre Eingaben sind gesichert' not in session_page

    upload = _html(app, '/eh/upload')
    assert 'Erlaubte Grösse: 8 MB.' in upload
    plain = _html(app, '/eh/code/UPLOAD_TOO_LARGE')
    assert 'Erlaubte Grösse' not in plain

    legacy = _html(app, '/eh/legacy')
    assert 'Anmeldung nicht möglich' in legacy
    assert 'Keine Anmeldung konfiguriert.' in legacy
    assert 'data-eh-frame="auth"' in legacy
    assert 'navbar-vertical' not in legacy
    assert 'href="/cafeteria/heute/"' in legacy

    english = _html(app, '/eh/admin?lang=en')
    assert 'No access' in english
    assert 'Overview' in english
    assert '<title>No access · Südhang Menüplanung</title>' in english


@pytest.mark.parametrize(('code', 'de_title', 'en_title'), EH11)
def test_eh11_titles(family: tuple[Flask, str], code: str, de_title: str, en_title: str) -> None:
    app, _origin = family
    german = _html(app, f'/eh/code/{code}')
    english = _html(app, f'/eh/code/{code}?lang=en')
    assert de_title in german
    assert en_title in english
    assert 'Support wurde informiert' not in german
    assert 'location.reload' not in german


def _tab_until(page, selector: str, limit: int = 80) -> bool:
    page.locator('body').focus()
    for _step in range(limit):
        page.keyboard.press('Tab')
        found = page.evaluate(
            '(selector) => !!(document.activeElement && document.activeElement.closest(selector))',
            selector,
        )
        if found:
            return True
    return False


def _reachable(page, selector: str) -> dict[str, object]:
    return page.evaluate(
        """(selector) => {
          const node = document.querySelector(selector);
          if (!node) return {ok: false};
          node.scrollIntoView({block: 'center', inline: 'nearest'});
          const box = node.getBoundingClientRect();
          const style = getComputedStyle(node);
          return {
            ok: box.width > 0 && box.height > 0 && box.bottom > 0 && box.top < innerHeight,
            height: box.height,
            overflow: style.overflow,
            userSelect: style.userSelect,
            fits: node.scrollHeight <= node.clientHeight + 2,
            inside: box.left >= -1 && box.right <= innerWidth + 1,
          };
        }""",
        selector,
    )


def test_browser_frames_zoom_keyboard_and_screenshots(family: tuple[Flask, str], browser) -> None:
    _app, origin = family
    AUDIT.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    page.goto(f'{origin}/eh/login?notice=auth.required&methods=both')
    expect(page.locator('h1')).to_have_text('Anmeldung erforderlich')
    page.screenshot(path=str(AUDIT / 'zielbild-a-login-1440.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(AUDIT / 'zielbild-a-login-390.png'), full_page=True)
    page.set_viewport_size({'width': 320, 'height': 480})
    login_narrow = _reachable(page, '.auth-card')
    assert login_narrow['ok'] and login_narrow['inside'], login_narrow
    assert _tab_until(page, '.auth-submit')

    page.set_viewport_size({'width': 1440, 'height': 900})
    page.goto(f'{origin}/eh/admin?session_user=1')
    expect(page.locator('h1')).to_have_text('Kein Zugriff')
    expect(page.locator('.navbar-vertical')).to_be_visible()
    page.screenshot(path=str(AUDIT / 'zielbild-b-admin-403-1440.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(AUDIT / 'zielbild-b-admin-403-390.png'), full_page=True)
    admin_narrow = _reachable(page, '.eh-card')
    assert admin_narrow['ok'] and admin_narrow['fits'], admin_narrow
    reference = _reachable(page, '.eh-reference')
    assert reference['ok'] and reference['userSelect'] == 'text', reference
    assert _tab_until(page, '.eh-action')
    action_height = page.locator('.eh-action').first.evaluate(
        'node => node.getBoundingClientRect().height')
    assert action_height >= 44

    page.set_viewport_size({'width': 1440, 'height': 900})
    page.goto(f'{origin}/eh/minimal')
    expect(page.locator('h1')).to_have_text('Vorgang konnte nicht abgeschlossen werden')
    expect(page.locator('.navbar-vertical')).to_have_count(0)
    primary = page.evaluate(
        """() => {
          const node = document.querySelector('.eh-action-primary');
          const probe = document.createElement('div');
          probe.style.background = 'var(--sh-magenta)';
          document.body.appendChild(probe);
          const expected = getComputedStyle(probe).backgroundColor;
          probe.remove();
          return getComputedStyle(node).backgroundColor === expected;
        }""")
    assert primary
    card = _reachable(page, '.eh-card')
    assert card['overflow'] == 'visible'
    assert card['fits']
    page.screenshot(path=str(AUDIT / 'zielbild-c-minimal-500-1440.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(AUDIT / 'zielbild-c-minimal-500-390.png'), full_page=True)
    narrow = _reachable(page, '.eh-card')
    assert narrow['ok'] and narrow['inside'], narrow
    page.set_viewport_size({'width': 320, 'height': 180})
    for selector in ('h1', '.eh-action', '.eh-reference'):
        short = _reachable(page, selector)
        assert short['ok'], (selector, short)
    assert _reachable(page, '.eh-reference')['userSelect'] == 'text'
    assert _reachable(page, '.eh-card')['overflow'] == 'visible'
    context.close()

    with TemporaryDirectory(prefix='eh-zoom-') as profile_dir:
        with browser.browser_type.launch_persistent_context(
            profile_dir, channel='chromium', headless=True, no_viewport=True, base_url=origin,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as zoom_context:
            zoomed = zoom_context.pages[0]
            zoomed.goto('chrome://settings/appearance')
            zoomed.evaluate(
                'new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(4, resolve))')
            zoom = zoomed.evaluate(
                'new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))')
            assert zoom == pytest.approx(4)
            zoomed.goto('/eh/minimal')
            zoomed.evaluate(
                "document.querySelector('.eh-reference').scrollIntoView({block:'center'})")
            box = zoomed.locator('.eh-reference').bounding_box()
            title_box = zoomed.locator('h1').bounding_box()
            action_box = zoomed.locator('.eh-action').first.bounding_box()
            assert box is not None and box['height'] > 0
            assert title_box is not None and title_box['height'] > 0
            assert action_box is not None and action_box['height'] >= 44


def test_degraded_without_css_js_and_icons(family: tuple[Flask, str], browser) -> None:
    _app, origin = family

    def block_assets(route) -> None:
        if route.request.resource_type == 'document':
            route.continue_()
        else:
            route.abort()

    context = browser.new_context(
        java_script_enabled=False, viewport={'width': 390, 'height': 800})
    context.route('**/*', block_assets)
    page = context.new_page()
    page.goto(f'{origin}/eh/minimal?session_user=1')
    expect(page.locator('h1')).to_have_text('Vorgang konnte nicht abgeschlossen werden')
    expect(page.get_by_text('Zur Übersicht')).to_be_visible()
    expect(page.get_by_text('Neu laden')).to_be_visible()
    assert SECRET_NAME not in page.content()
    assert 'navbar-vertical' not in page.content()
    page.locator('a.eh-action', has_text='Zur Übersicht').click()
    expect(page.locator('body')).to_contain_text('overview')

    page.goto(f'{origin}/eh/login?notice=auth.required&methods=both&session_user=1')
    expect(page.locator('h1')).to_have_text('Anmeldung erforderlich')
    expect(page.locator('.auth-submit')).to_contain_text('Anmelden')
    assert 'navbar-vertical' not in page.content()
    assert SECRET_NAME not in page.content()

    page.goto(f'{origin}/eh/admin?session_user=1')
    expect(page.locator('h1')).to_have_text('Kein Zugriff')
    expect(page.get_by_text('Zur Übersicht')).to_be_visible()
    context.close()
