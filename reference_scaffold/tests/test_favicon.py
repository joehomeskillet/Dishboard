"""`/favicon.ico` is the existing static icon and never renders a template."""
from __future__ import annotations

from pathlib import Path

import pytest
from flask import request
from sqlalchemy.exc import OperationalError

from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_screen_template_routes import screen_app  # noqa: F401

_ICON = 'img/suedhang-logo.png'
_TEMPLATES = (
    'admin/screen_template_unavailable.html',
    'admin/grundlagen_unavailable.html',
    'admin/print_template_unavailable.html',
    'admin/recipe_template_error.html',
    'errors/minimal.html',
)


class _DatabaseDown:
    def __init__(self):
        self.calls = 0

    def connect(self, *args, **kwargs):
        self.calls += 1
        raise OperationalError('favicon database down', {}, Exception('down'))

    begin = raw_connection = connect


def test_outage_templates_reference_the_static_icon():
    root = Path(__file__).parents[1] / 'cafeteria' / 'templates'
    page = (root / 'errors' / 'page.html').read_text(encoding='utf-8')
    assert "'admin/base_tabler.html'" in page
    assert "'errors/minimal.html'" in page
    assert "'base.html'" in page
    assert page.strip().startswith('{% extends ')
    for name in _TEMPLATES:
        text = (root / name).read_text(encoding='utf-8')
        assert 'rel="icon"' in text
        assert _ICON in text


@pytest.mark.parametrize('authenticated', [False, True])
def test_favicon_skips_context_processor_during_database_outage(
    screen_app, database_engine, tmp_path, authenticated,  # noqa: F811
):
    if authenticated:
        client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
        cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
        assert cookie is not None
    else:
        client = screen_app.test_client()
    databases = [_DatabaseDown(), _DatabaseDown()]
    for key, database in zip(('cafeteria_db', 'cafeteria_auth_issuer_db'), databases):
        screen_app.extensions[key] = database
    calls: list[str] = []

    def unavailable_context():
        calls.append(request.path)
        raise AssertionError('favicon invoked a template context processor')

    screen_app.template_context_processors[None] = [
        *screen_app.template_context_processors[None],
        unavailable_context,
    ]
    static = client.get(f'/static/{_ICON}')
    assert static.status_code == 200 and static.data.startswith(b'\x89PNG')
    for host in ('menu.test', 'admin.test', 'signage.test'):
        if authenticated:
            client.set_cookie(cookie.key, cookie.value, domain=host)
        response = client.get('/favicon.ico', base_url=f'http://{host}')
        assert response.status_code == static.status_code
        assert response.data == static.data
        assert response.mimetype == static.mimetype
        assert response.headers['Cache-Control'] == static.headers['Cache-Control']
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert "default-src 'self'" in response.headers['Content-Security-Policy']
        head = client.head('/favicon.ico', base_url=f'http://{host}')
        assert head.status_code == 200 and head.data == b''
        cached = client.get('/favicon.ico', base_url=f'http://{host}',
                            headers={'If-None-Match': response.headers['ETag']})
        assert cached.status_code == 304 and cached.data == b''
    screen_app.static_folder = str(tmp_path)
    missing = client.get('/favicon.ico', base_url='http://player.test')
    assert missing.status_code == 204 and missing.get_data() == b''
    assert missing.headers['X-Content-Type-Options'] == 'nosniff'
    assert "default-src 'self'" in missing.headers['Content-Security-Policy']
    assert calls == []
    assert [database.calls for database in databases] == [0, 0]
