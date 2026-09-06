"""Actual authorization, CSRF, multipart boundaries and public draft isolation."""
from __future__ import annotations

from io import BytesIO

import pytest
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from cafeteria.branding import change_branding, read_branding
from cafeteria.branding_config import default_config
from cafeteria.branding_routes import bp as branding_bp
from test_admin_workflow_routes import _login, app as workflow_app, database_engine  # noqa: F401
from test_branding_store import _png


@pytest.fixture
def app(workflow_app):  # noqa: F811
    workflow_app.register_blueprint(branding_bp)
    return workflow_app


def _form(**changes):
    return {'_csrf': 'workflow-csrf', 'action': 'save', 'version': '0', 'name': 'Neue Marke',
            **default_config(), 'logo_sha256': '', **changes}


def test_brand_editor_upload_preview_activate_and_history(app, database_engine):  # noqa: F811
    client, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    response = client.get('/admin/design/marke')
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    with database_engine.connect() as connection:
        before = connection.execute(text('SELECT to_jsonb(s) FROM cafeteria.settings s ORDER BY id')).scalars().all()
    assert client.get('/admin/design/marke/vorschau/1').status_code == 200
    assert client.get('/admin/design/marke/vorschau/1.css').status_code == 200
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT to_jsonb(s) FROM cafeteria.settings s ORDER BY id')).scalars().all() == before
    data = _form(logo=(BytesIO(_png()), '../../logo.svg'))
    saved = client.post('/admin/design/marke', data=data)
    assert saved.status_code == 303
    with database_engine.connect() as connection:
        document = read_branding(connection)
    sha = document['revisions'][1]['config']['logo_sha256']
    public = app.test_client()
    assert public.get('/branding/revisions/2.css').status_code == 404
    assert public.get(f'/branding/logos/{sha}.png').status_code == 404
    assert client.get(f'/admin/design/marke/logo/{sha}.png').mimetype == 'image/png'
    assert client.get('/admin/design/marke/vorschau/2.css').headers['Cache-Control'] == 'no-store'
    assert client.post('/admin/design/marke', data={'_csrf': 'workflow-csrf', 'action': 'activate', 'version': '1', 'revision': '2'}).status_code == 303
    assert public.get('/branding/revisions/2.css').mimetype == 'text/css'
    image = public.get(f'/branding/logos/{sha}.png')
    assert image.status_code == 200 and image.mimetype == 'image/png'
    assert 'immutable' in image.headers['Cache-Control'] and 'Set-Cookie' not in image.headers
    assert image.headers['X-Content-Type-Options'] == 'nosniff'
    assert public.get(f'/branding/logos/{sha}.png', headers={'If-None-Match': image.headers['ETag']}).status_code == 304
    assert client.post('/admin/design/marke', data=_form(version='0')).status_code == 409
    with database_engine.connect() as connection:
        assert read_branding(connection)['active_revision'] == 2


@pytest.mark.parametrize('roles', [[], ['Cafeteria.Editor'], ['Cafeteria.Publisher']])
def test_only_current_admin_can_read_or_write_drafts(app, database_engine, roles):  # noqa: F811
    client, _ = _login(app, database_engine, roles)
    expected = 403 if roles else 401
    for path in ['/admin/design/marke', '/admin/design/marke/vorschau/1', '/admin/design/marke/vorschau/1.css', '/admin/design/marke/logo/' + 'a' * 64 + '.png']:
        assert client.get(path).status_code == expected
    assert client.post('/admin/design/marke', data=_form()).status_code == expected


@pytest.mark.parametrize('kind', ['csrf', 'duplicate', 'unknown', 'scope', 'bad-image', 'too-large', 'duplicate-file'])
def test_invalid_multipart_request_never_saves(app, database_engine, kind):  # noqa: F811
    client, _ = _login(app, database_engine, ['Cafeteria.Admin'])
    data = MultiDict(_form())
    path = '/admin/design/marke'
    if kind == 'csrf':
        data['_csrf'] = 'wrong'
    elif kind == 'duplicate':
        data.add('primary', '#000000')
    elif kind == 'unknown':
        data['external_url'] = 'https://example.invalid'
    elif kind == 'scope':
        path += '?profile=patient'
    else:
        payload = b'not an image' if kind == 'bad-image' else b'x' * (1024 * 1024 + 1)
        data.add('logo', (BytesIO(payload), 'logo.png'))
        if kind == 'duplicate-file':
            data.add('logo', (BytesIO(_png()), 'other.png'))
    response = client.post(path, data=data)
    assert response.status_code in (400, 403)
    with database_engine.connect() as connection:
        assert read_branding(connection)['version'] == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.branding_assets')).scalar_one() == 0


def test_public_css_has_only_validated_same_origin_resources_and_no_draft_name(app, database_engine):  # noqa: F811
    client, actor = _login(app, database_engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        authz = session['authz_version']
    config = {**default_config(), 'surface': '#111111', 'text': '#ffffff', 'primary': '#ffddaa', 'accent': '#aaddff'}
    change_branding(database_engine, actor, authz, 0, 'save', name='Vertraulicher Entwurf', config=config)
    assert app.test_client().get('/branding/revisions/2.css').status_code == 404
    change_branding(database_engine, actor, authz, 1, 'activate', revision_id=2)
    css = app.test_client().get('/branding/revisions/2.css')
    assert css.status_code == 200 and css.mimetype == 'text/css'
    assert 'Vertraulicher' not in css.text and 'https:' not in css.text
    assert '--brand-on-primary:#111111' in css.text
    assert app.test_client().get('/branding/revisions/2.css?anything=true').status_code == 400
