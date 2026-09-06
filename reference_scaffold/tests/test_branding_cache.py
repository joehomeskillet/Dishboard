"""Deterministically overlap real brand reads, then check HTTP outage consistency."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread

import pytest
from sqlalchemy.exc import OperationalError

from cafeteria import branding_routes
from cafeteria.branding import change_branding
from cafeteria.branding_assets import normalize_logo
from cafeteria.branding_config import default_config
from test_admin_workflow_routes import _login
from test_branding_routes import app, database_engine, workflow_app  # noqa: F401
from test_branding_store import _png


def _offline(*_args):
    raise OperationalError('offline', {}, None)


def _save_brand(engine, actor, authz, version, size, font):
    asset = normalize_logo(_png(size))
    config = {**default_config(), 'logo_sha256': asset.sha256, 'font_body': font}
    saved = change_branding(engine, actor, authz, version, 'save', name=font, config=config, logo=asset)
    revision = saved['revisions'][-1]['id']
    change_branding(engine, actor, authz, version + 1, 'activate', revision_id=revision)
    return asset


def test_overlapping_context_publication_retains_matching_css_and_logo_during_outage(app, database_engine, monkeypatch):  # noqa: F811
    client, actor = _login(app, database_engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        authz = session['authz_version']
    first_logo = _save_brand(database_engine, actor, authz, 0, (40, 20), 'fira')
    first_published, resume_first = Event(), Event()

    class PausedExtensions(dict):
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            # Pause after the first brand cache write, regardless of its implementation/key.
            if key.startswith('branding_') and current_thread().name.startswith('older-brand') and not first_published.is_set():
                first_published.set()
                assert resume_first.wait(timeout=10)

    monkeypatch.setattr(app, 'extensions', PausedExtensions(app.extensions))

    def render_context():
        with app.app_context():
            return branding_routes.branding_context()['brand']

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='older-brand') as worker:
        older = worker.submit(render_context)
        try:
            assert first_published.wait(timeout=10)
            second_logo = _save_brand(database_engine, actor, authz, 2, (60, 30), 'carlito')
            newer = render_context()
            assert newer.id == 3
        finally:
            resume_first.set()
        assert older.result(timeout=10).id == 2

    public = app.test_client()
    # Published historical resources remain accessible while the database is available.
    for revision, asset in ((2, first_logo), (3, second_logo)):
        assert public.get(f'/branding/revisions/{revision}.css').status_code == 200
        assert public.get(f'/branding/logos/{asset.sha256}.png').data == asset.png
    monkeypatch.setattr(branding_routes, 'read_branding', _offline)
    retained = render_context()
    assert retained.id == 3 and retained.config['logo_sha256'] == second_logo.sha256
    css = public.get('/branding/revisions/3.css')
    logo = public.get(f'/branding/logos/{second_logo.sha256}.png')
    assert css.status_code == 200 and 'Carlito' in css.text
    assert logo.status_code == 200 and logo.data == second_logo.png
    for response in (css, logo):
        assert 'immutable' in response.headers['Cache-Control']
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert 'Set-Cookie' not in response.headers
    assert public.get(f'/branding/logos/{second_logo.sha256}.png', headers={'If-None-Match': logo.headers['ETag']}).status_code == 304
    assert public.get('/branding/revisions/2.css').status_code == 503
    assert public.get(f'/branding/logos/{first_logo.sha256}.png').status_code == 503


def test_returned_context_cannot_mutate_the_retained_revision(app, database_engine, monkeypatch):  # noqa: F811
    client, actor = _login(app, database_engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        authz = session['authz_version']
    asset = _save_brand(database_engine, actor, authz, 0, (40, 20), 'carlito')
    with app.app_context():
        returned = branding_routes.branding_context()['brand']
    returned.config['font_body'] = 'fira'
    returned.config['logo_sha256'] = None
    monkeypatch.setattr(branding_routes, 'read_branding', _offline)
    with app.app_context():
        retained = branding_routes.branding_context()['brand']
    assert retained.config['font_body'] == 'carlito'
    assert retained.config['logo_sha256'] == asset.sha256
    assert app.test_client().get(f'/branding/logos/{asset.sha256}.png').data == asset.png


@pytest.mark.parametrize('path,status', [('/branding/revisions/1.css', 200),
                                       ('/branding/revisions/2.css', 503),
                                       ('/branding/logos/' + 'a' * 64 + '.png', 503)])
def test_cold_outage_keeps_default_and_does_not_invent_public_resources(app, monkeypatch, path, status):  # noqa: F811
    monkeypatch.setattr(branding_routes, 'read_branding', _offline)
    with app.app_context():
        assert branding_routes.branding_context()['brand'].id == 1
    assert app.test_client().get(path).status_code == status
