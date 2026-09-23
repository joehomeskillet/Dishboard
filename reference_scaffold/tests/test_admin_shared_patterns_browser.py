import pytest
from flask import Flask, render_template_string
from threading import Thread
from werkzeug.serving import make_server
from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui
from cafeteria.ui.semantics import ROOT, STATIC, load_registry

PAGE = '''<!doctype html><html lang="de"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% for file in ['vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
<link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
</head><body class="admin-body dishboard-admin"><main class="container-fluid py-4">
{% from 'admin/_macros.html' import icon %}
{% for ic in icons %}
    {{ icon(ic) }}
{% endfor %}
</main></body></html>'''

def test_admin_icons_exist_and_render():
    from playwright.sync_api import sync_playwright
    
    app = Flask('semantic-browser2', template_folder=str(ROOT.parent / 'templates'),
                static_folder=str(STATIC))
    app.config.update(TESTING=True, UI_LOCALE='de')
    register_template_filters(app)
    register_ui(app)
    
    registry = load_registry()
    icons = [entry.icon for entry in registry.values()]
    
    @app.route('/__test__')
    def test_page():
        return render_template_string(PAGE, icons=icons)

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                context = browser.new_context(java_script_enabled=False)
                page = context.new_page()
                response = page.goto(f'http://127.0.0.1:{server.server_port}/__test__')
                assert response.status == 200
                
                # Wait for any network idle just in case
                page.wait_for_load_state('networkidle')
                
                # Verify all <use> elements have a bounding box > 0
                for glyph in page.locator('main svg use').all():
                    if glyph.is_visible():
                        assert glyph.evaluate('el => el.getBBox().width > 0'), f"Icon has 0 width: {glyph.get_attribute('href')}"
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
