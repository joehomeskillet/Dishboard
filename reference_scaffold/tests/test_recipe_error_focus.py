"""Single autofocus target on DB-free recipe recovery HTML."""
from html.parser import HTMLParser
from pathlib import Path
from threading import Thread

import pytest
from flask import Flask
from playwright.sync_api import expect
from werkzeug.serving import make_server

from cafeteria.admin.recipe_errors import render_form_error
from cafeteria.admin.recipe_forms import FormError
from cafeteria.recipe_types import RecipeConflictError, RecipeUnavailableError, RecipeValidationError

ROOT = Path(__file__).resolve().parents[2]
CSRF = 'csrf-token'
CONTEXT = 'signed-cas'
VERSION = '7'
ASSETS = ('tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css')

CASES = {
    'ordinary': {
        'error': FormError('Ungültige Zeichen im Titel.', 'title'),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('title', 'Suppe'), ('row_version', VERSION)),
        'status': 400, 'message': 'Ungültige Zeichen im Titel.',
        'focus': 'original-3', 'invalid': ('original-3',), 'keep': True,
    },
    'group': {
        'error': FormError('Höchstens 64 Zeilen; gültige Einfügeposition erforderlich.', 'ingredients'),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT),
                      ('ingredients.0.ingredient_text', 'Karotte'), ('row_version', VERSION)),
        'status': 400, 'message': 'Höchstens 64 Zeilen; gültige Einfügeposition erforderlich.',
        'focus': 'recipe-error', 'invalid': (), 'keep': True,
    },
    'missing': {
        'error': FormError('Dieses Feld ist erforderlich.', 'title'),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('description', 'Text'), ('row_version', VERSION)),
        'status': 400, 'message': 'Dieses Feld ist erforderlich.',
        'focus': 'recipe-error', 'invalid': (), 'keep': True,
    },
    'hidden_csrf': {
        'error': FormError('CSRF-Prüfung fehlgeschlagen.', '_csrf'),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('title', 'Suppe')),
        'status': 400, 'message': 'CSRF-Prüfung fehlgeschlagen.',
        'focus': 'recipe-error', 'invalid': (), 'keep': True,
    },
    'hidden_context': {
        'error': FormError('Formularkontext ist ungültig.', '_form_context'),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('title', 'Suppe')),
        'status': 400, 'message': 'Formularkontext ist ungültig.',
        'focus': 'recipe-error', 'invalid': (), 'keep': True,
    },
    'duplicate': {
        'error': FormError('Feld fehlt oder ist mehrfach vorhanden.', 'title'),
        'submitted': (('_csrf', CSRF), ('title', 'Eins'), ('title', 'Zwei'), ('_form_context', CONTEXT)),
        'status': 400, 'message': 'Feld fehlt oder ist mehrfach vorhanden.',
        'focus': 'original-2', 'invalid': ('original-2', 'original-3'), 'keep': True,
    },
    'generic400': {
        'error': RecipeValidationError(),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('title', 'Suppe'), ('row_version', VERSION)),
        'status': 400, 'message': 'Bitte prüfen Sie Ihre Eingaben.',
        'focus': 'recipe-error', 'invalid': (), 'keep': True,
    },
    'generic409': {
        'error': RecipeConflictError(),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('title', 'Suppe'), ('row_version', VERSION)),
        'status': 409, 'message': 'Zwischenzeitlich geändert. Ihre Eingaben wurden nicht gespeichert.',
        'focus': 'recipe-error', 'invalid': (), 'keep': True,
    },
    'generic503': {
        'error': RecipeUnavailableError(),
        'submitted': (('_csrf', CSRF), ('_form_context', CONTEXT), ('title', 'Suppe'), ('row_version', VERSION)),
        'status': 503, 'message': 'Rezepte sind momentan nicht verfügbar. Bitte später erneut versuchen.',
        'focus': 'recipe-error', 'invalid': (), 'keep': False,
    },
}


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.autofocus = []
        self.invalid = []
        self.hidden = []
        self.alert = None

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'input' and data.get('type') == 'hidden':
            self.hidden.append((data.get('name'), data.get('value')))
        if 'autofocus' in data:
            self.autofocus.append(data.get('id'))
        if data.get('aria-invalid') == 'true':
            self.invalid.append(data.get('id'))
        if data.get('id') == 'recipe-error':
            self.alert = data


def parse(html):
    markup = Markup()
    markup.feed(html)
    return markup


@pytest.fixture
def app():
    application = Flask(
        'recipe-error-focus',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
        static_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'static'),
    )

    @application.context_processor
    def forbidden_context():
        raise AssertionError('Recovery must not invoke context processors')

    @application.get('/case/<name>')
    def show_case(name):
        case = CASES[name]
        return render_form_error(case['error'], submitted=case['submitted'])

    return application


@pytest.fixture
def server(app):
    http = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{http.server_port}'
    finally:
        http.shutdown()
        thread.join(timeout=5)
        http.server_close()


@pytest.fixture(scope='module')
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        try:
            yield instance
        finally:
            instance.close()


@pytest.mark.parametrize('name', list(CASES))
def test_rendered_html_has_exactly_one_autofocus_and_preserves_payload(app, name):
    case = CASES[name]
    response = app.test_client().get('/case/' + name)
    html = response.get_data(as_text=True)
    markup = parse(html)
    assert response.status_code == case['status']
    assert response.headers['Cache-Control'] == 'no-store'
    assert case['message'] in html
    assert markup.alert['role'] == 'alert' and markup.alert['tabindex'] == '-1'
    assert markup.autofocus == [case['focus']]
    assert tuple(markup.invalid) == case['invalid']
    for asset in ASSETS:
        assert asset in html
        assert app.test_client().get('/static/' + asset).status_code == 200
    assert 'href="/admin/rezepte"' in html
    if case['keep']:
        assert markup.hidden == list(case['submitted'])
        assert CSRF in html and CONTEXT in html
        if ('row_version', VERSION) in case['submitted']:
            assert VERSION in html
    else:
        assert markup.hidden == []
        assert CSRF not in html and CONTEXT not in html


def test_recovery_skips_context_processors(app):
    response = app.test_client().get('/case/ordinary')
    assert response.status_code == 400
    assert 'Ungültige Zeichen im Titel.' in response.get_data(as_text=True)


@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('name', ['ordinary', 'group'])
def test_chromium_focuses_single_target(browser, server, javascript, name):
    case = CASES[name]
    context = browser.new_context(java_script_enabled=javascript)
    page = context.new_page()
    try:
        page.goto(server + '/case/' + name, wait_until='load')
        target = page.locator('#' + case['focus'])
        expect(page.locator('[autofocus]')).to_have_count(1)
        expect(target).to_be_focused()
        if javascript:
            assert page.evaluate(
                'id => document.activeElement === document.getElementById(id)', case['focus'],
            )
    finally:
        context.close()
