"""Actual PostgreSQL, Redis sessions and native immutable recipe PDF downloads."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from pypdf import PdfReader
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

import cafeteria
from cafeteria import recipe_store as store, roles
from cafeteria.admin import recipe_revision_routes as routes
from cafeteria.branding import change_branding
from cafeteria.branding_config import default_config as brand_defaults
from cafeteria.print_template_config import default_config
from cafeteria.print_templates import change_template
from test_master_data_db import make_actor, signed_in
from test_recipe_revision_immutable_db import png
from test_recipe_store_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16, line, mutable, payload, snapshot, target,
)


@pytest.fixture
def pdf_http(seeded_pg16, app_engine, monkeypatch, tmp_path):  # noqa: F811
    redis_url = os.environ.get('TEST_REDIS_URL')
    assert redis_url, 'Dedicated HTTP test Redis is required.'
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', redis_url)
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda app: None)
    app = cafeteria.create_app()
    app.config.update(TESTING=True, SECRET_KEY='recipe-pdf-http-isolated',
                      SESSION_COOKIE_SECURE=False, LAST_GOOD_DIR=str(tmp_path))
    app.extensions['cafeteria_db'] = app_engine
    app.extensions['cafeteria_auth_issuer_db'] = app_engine
    prefix = 'recipe-pdf-http:' + uuid4().hex + ':'
    app.session_interface.key_prefix = prefix
    redis = app.extensions['cafeteria_rate_redis']
    assert redis.ping()
    actor = make_actor(seeded_pg16, 'Cafeteria.Editor')
    admin = make_actor(seeded_pg16, 'Cafeteria.Admin')
    with signed_in(app_engine, actor):
        location = store.get_location(app_engine)
        row = store.create_recipe(app_engine, actor, payload(ingredients=[
            line(quantity='0.125', unit_code='KG'), line('Salz', quantity=None, unit_code=None)]),
            expected_location_id=location)
        row = store.add_recipe_image(app_engine, actor, target(row), data=png(),
            content_type='image/png', caption='Originalbild', expected_location_id=location)
        data = mutable(store.get_recipe(app_engine, row.public_id).payload)
        digest = data['images'][0]['sha256']
        data['steps'][0]['image_sha256'] = digest
        row = store.update_recipe(app_engine, actor, target(row), data, expected_location_id=location)
        frozen = store.freeze_revision(app_engine, actor, target(row), expected_location_id=location)
    config = {**default_config(), 'palette': 'active_brand', 'font': 'active_brand',
              'logo': 'active_brand', 'header_text': 'Aktive Rezeptvorlage'}
    change_template(app_engine, 'recipe', admin.user_id, admin.authz_version, 0, 'standard',
                    'save', name='Rezeptdruck', config=config)
    change_template(app_engine, 'recipe', admin.user_id, admin.authz_version, 1, 'standard',
                    'activate', revision_id=2, recipe_public_id=row.public_id,
                    recipe_revision_public_id=frozen.public_id)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': actor.user_id, 'name': 'Redaktion'}
        session['authz_version'] = actor.authz_version
    assert list(redis.scan_iter(match=prefix + '*'))
    try:
        yield app, seeded_pg16, client, actor, admin, frozen, digest
    finally:
        for key in redis.scan_iter(match=prefix + '*'):
            redis.delete(key)
        redis.close()


def path(frozen):
    return f'/admin/rezepte/{frozen.recipe_public_id}/revisionen/{frozen.public_id}/druck.pdf'


def state(owner):
    result = snapshot(owner)
    with owner.connect() as connection:
        result['settings'] = connection.execute(text(
            'SELECT to_jsonb(s)::text FROM cafeteria.settings s ORDER BY to_jsonb(s)::text')).all()
    return result


def extracted(response):
    pdf = PdfReader(BytesIO(response.data))
    return pdf, '\n'.join(page.extract_text() for page in pdf.pages)


def assert_error(response, status):
    assert response.status_code == status, response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.mimetype == 'text/html'
    assert 'PRIVATE_DETAIL' not in response.text
    assert 'X-Recipe-Revision' not in response.headers
    assert not response.data.startswith(b'%PDF')


def test_actual_pdf_headers_scaled_decimal_images_and_single_readonly_snapshot(pdf_http, monkeypatch):
    app, owner, client, _, _, frozen, digest = pdf_http
    engine = app.extensions['cafeteria_db']
    connections, rendered, statements = [], [], []
    for name in ('recipe_print_input', 'active_template', 'load_pdf_branding'):
        original = getattr(routes, name)
        def observe(connection, *args, original=original):
            connections.append(connection)
            assert connection.execute(text('SHOW transaction_read_only')).scalar_one() == 'on'
            assert connection.execute(text('SHOW transaction_isolation')).scalar_one() == 'repeatable read'
            return original(connection, *args)
        monkeypatch.setattr(routes, name, observe)
    original_render = routes.render_recipe_pdf
    def render(revision, **kwargs):
        rendered.append((revision, kwargs))
        assert kwargs['images'][digest].data == png()
        return original_render(revision, **kwargs)
    monkeypatch.setattr(routes, 'render_recipe_pdf', render)
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    before = state(owner)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.get(path(frozen), query_string={'yield': '6'})
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert response.status_code == 200, response.text
    assert response.mimetype == 'application/pdf' and response.data.startswith(b'%PDF')
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Content-Disposition'] == (
        f'inline; filename="rezept-{frozen.recipe_public_id}-{frozen.public_id}.pdf"')
    assert response.headers['X-Recipe-Revision'] == frozen.public_id
    assert response.headers['X-Recipe-Content-SHA256'] == frozen.content_hash_sha256
    assert response.headers['X-Print-Template-Revision'] == 'standard:2'
    assert response.headers['X-Brand-Revision'] == '1'
    assert len(connections) == 3 and all(connection is connections[0] for connection in connections)
    assert len(rendered) == 1 and rendered[0][1]['target'] == '6'
    assert not any('recipe_payload_v22' in statement for statement in statements)
    pdf, contents = extracted(response)
    assert all(value in contents for value in ('Aktive Rezeptvorlage', 'Suppe', 'Gewünscht: 6',
                                              '0.1875 KG', 'Salz', 'Originalbild'))
    assert '0 Salz' not in contents and 'Markenrevision 1' in pdf.metadata.subject
    assert any(list(page.images) for page in pdf.pages)
    assert state(owner) == before
    assert client.get(path(frozen), query_string={'yield': '6'}).data == response.data
    assert sum(rule.endpoint == 'admin.recipe_revision_pdf' for rule in app.url_map.iter_rules()) == 1


def test_revision_link_preserves_only_valid_selected_yield(pdf_http):
    _, owner, client, _, _, frozen, _ = pdf_http
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []
        def handle_starttag(self, tag, attrs):
            if tag == 'a' and '/druck.pdf' in dict(attrs).get('href', ''):
                self.urls.append(dict(attrs)['href'])
    before = state(owner)
    for requested, expected, status in [('6.500', '6.5', 200), ('NaN', '4', 400)]:
        response = client.get(path(frozen).removesuffix('/druck.pdf'), query_string={'yield': requested})
        assert response.status_code == status and 'PDF öffnen' in response.text
        links = Links()
        links.feed(response.text)
        assert len(links.urls) == 1
        assert urlparse(links.urls[0]).path == path(frozen)
        assert parse_qs(urlparse(links.urls[0]).query) == {'yield': [expected]}
        assert client.get(links.urls[0]).status_code == 200
    assert state(owner) == before


@pytest.mark.parametrize('query', ['yield=0', 'yield=-1', 'yield=NaN', 'yield=Infinity', 'yield=',
    'yield=1.0000001', 'yield=1000000000000', 'yield=PRIVATE_DETAIL', 'yield=1&yield=2',
    'template=standard', 'revision=2', 'profile=patient', 'location=2', 'week=2026-09-07'])
def test_invalid_or_overriding_queries_fail_before_snapshot_read(pdf_http, monkeypatch, query):
    _, owner, client, _, _, frozen, _ = pdf_http
    monkeypatch.setattr(routes, 'recipe_print_input', lambda *args: pytest.fail('Invalid query reached reader'))
    before = state(owner)
    assert_error(client.get(path(frozen) + '?' + query), 400)
    assert state(owner) == before


@pytest.mark.parametrize('selection', ['unknown_recipe', 'unknown_revision', 'foreign_recipe', 'foreign_location', 'missing_asset', 'foreign_asset'])
def test_unknown_or_foreign_selection_and_assets_are_inaccessible(pdf_http, selection):
    app, owner, client, actor, _, frozen, digest = pdf_http
    url = path(frozen)
    if selection == 'unknown_recipe':
        url = url.replace(frozen.recipe_public_id, str(uuid4()))
    elif selection == 'unknown_revision':
        url = url.replace(frozen.public_id, str(uuid4()))
    elif selection == 'foreign_recipe':
        with signed_in(app.extensions['cafeteria_db'], actor):
            other = store.create_recipe(app.extensions['cafeteria_db'], actor, payload(),
                expected_location_id=store.get_location(app.extensions['cafeteria_db']))
        url = url.replace(frozen.recipe_public_id, other.public_id)
    else:
        with owner.begin() as connection:
            if selection == 'foreign_location':
                connection.execute(text('UPDATE cafeteria.locations SET active=false'))
                connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Andere Küche',true)"))
            else:
                connection.execute(text('ALTER TABLE cafeteria.recipe_assets DISABLE TRIGGER ALL'))
                if selection == 'missing_asset':
                    connection.execute(text('DELETE FROM cafeteria.recipe_assets WHERE sha256=:sha'), {'sha': digest})
                else:
                    other = connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Andere Küche',false) RETURNING id")).scalar_one()
                    connection.execute(text('UPDATE cafeteria.recipe_assets SET location_id=:id WHERE sha256=:sha'),
                                       {'id': other, 'sha': digest})
                connection.execute(text('ALTER TABLE cafeteria.recipe_assets ENABLE TRIGGER ALL'))
    before = state(owner)
    assert_error(client.get(url), 404)
    assert state(owner) == before


def test_live_editor_authority_is_rechecked_for_every_download(pdf_http, monkeypatch):
    _, owner, client, actor, _, frozen, _ = pdf_http
    assert client.get(path(frozen)).status_code == 200  # Real Editor, no settings.write.
    with monkeypatch.context() as patch:
        patch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.write'})
        assert_error(client.get(path(frozen)), 403)  # Synthetic capability denial, actual PG identity.
    with owner.begin() as connection:
        connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    before = state(owner)
    assert_error(client.get(path(frozen)), 401)
    assert state(owner) == before


@pytest.mark.parametrize('mode', ['anonymous', 'disabled'])
def test_anonymous_and_disabled_current_actor_cannot_download(pdf_http, mode):
    app, owner, client, actor, _, frozen, _ = pdf_http
    if mode == 'anonymous':
        client = app.test_client()
    else:
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:id'), {'id': actor.user_id})
    before = state(owner)
    assert_error(client.get(path(frozen)), 401)
    assert state(owner) == before


@pytest.mark.parametrize('failure', ['auth', 'reader', 'template', 'branding'])
def test_unavailable_context_never_reloads_database_for_error_html(pdf_http, monkeypatch, failure):
    app, owner, client, _, _, frozen, _ = pdf_http
    if failure in ('auth', 'reader'):
        def offline(*args, **kwargs):
            raise OperationalError('PRIVATE_DETAIL', {}, RuntimeError('PRIVATE_DETAIL'))
        monkeypatch.setattr(roles if failure == 'auth' else routes,
                            'load_user_authorization' if failure == 'auth' else 'recipe_print_input', offline)
    else:
        key = 'branding.v1' if failure == 'branding' else 'print_templates.v1.recipe'
        with owner.begin() as connection:
            connection.execute(text('INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES(:key,CAST(:value AS jsonb)) '
                'ON CONFLICT(location_id,profile_id,setting_key) DO UPDATE SET setting_value=excluded.setting_value'),
                {'key': key, 'value': json.dumps({'PRIVATE_DETAIL': 'broken'})})
    @app.context_processor
    def forbidden_context():
        pytest.fail('Error page attempted context enrichment')
    before = state(owner)
    assert_error(client.get(path(frozen)), 503)
    assert state(owner) == before


def rewrite_snapshot(owner, frozen, data):
    # Deliberate owner-only corruption fixture; runtime privileges are unchanged.
    with owner.begin() as connection:
        connection.execute(text('ALTER TABLE cafeteria.recipe_revisions DISABLE TRIGGER USER'))
        connection.execute(text('UPDATE cafeteria.recipe_revisions SET snapshot_json=CAST(:value AS jsonb), '
            "content_hash_sha256=encode(public.digest(convert_to(CAST(:value AS jsonb)::text,'UTF8'),'sha256'),'hex') "
            'WHERE public_id=CAST(:id AS uuid)'), {'value': json.dumps(data), 'id': frozen.public_id})
        connection.execute(text('ALTER TABLE cafeteria.recipe_revisions ENABLE TRIGGER USER'))


@pytest.mark.parametrize('failure,status', [('stored_quantity', 503), ('malformed_image', 503), ('fit', 422)])
def test_corrupt_stored_data_and_real_renderer_failure_are_controlled(pdf_http, failure, status):
    app, owner, client, actor, _, frozen, digest = pdf_http
    with signed_in(app.extensions['cafeteria_db'], actor):
        data = mutable(store.get_revision(app.extensions['cafeteria_db'], frozen.public_id).snapshot)
    if failure == 'stored_quantity':
        data['recipe']['servings'] = '0'
    elif failure == 'fit':
        data['recipe']['title'] = 'Rezept 🥜'
    else:
        bad = b'\x89PNG\r\n\x1a\ninvalid'
        bad_hash = hashlib.sha256(bad).hexdigest()
        with owner.begin() as connection:
            connection.execute(text('INSERT INTO cafeteria.recipe_assets(location_id,sha256,image_data,content_type,width,height,created_by) '
                'SELECT location_id,:sha,:data,content_type,width,height,created_by FROM cafeteria.recipe_assets WHERE sha256=:original'),
                {'sha': bad_hash, 'data': bad, 'original': digest})
        data['recipe']['images'][0]['sha256'] = bad_hash
        data['recipe']['steps'][0]['image_sha256'] = bad_hash
    rewrite_snapshot(owner, frozen, data)
    before = state(owner)
    response = client.get(path(frozen))
    assert_error(response, status)
    if status == 422:
        assert 'nicht vollständig als PDF' in response.text
    assert state(owner) == before


def test_current_recipe_and_template_draft_edits_cannot_change_active_pdf(pdf_http):
    app, owner, client, actor, admin, frozen, _ = pdf_http
    engine = app.extensions['cafeteria_db']
    original = client.get(path(frozen), query_string={'yield': '6'})
    assert original.status_code == 200
    with signed_in(engine, actor):
        row = store.get_recipe(engine, frozen.recipe_public_id)
        data = mutable(row.payload)
        data.update(title='Neuer aktueller Entwurf', images=[])
        data['steps'][0]['image_sha256'] = None
        store.update_recipe(engine, actor, target(row), data, expected_location_id=store.get_location(engine))
    config = {**default_config(), 'logo': 'none', 'header_text': 'Neue aktive Vorlage'}
    change_template(engine, 'recipe', admin.user_id, admin.authz_version, 2, 'standard', 'save',
                    name='Unveröffentlichter Entwurf', config=config)
    before = state(owner)
    assert client.get(path(frozen), query_string={'yield': '6'}).data == original.data
    assert state(owner) == before
    change_template(engine, 'recipe', admin.user_id, admin.authz_version, 3, 'standard', 'activate',
                    revision_id=3, recipe_public_id=frozen.recipe_public_id, recipe_revision_public_id=frozen.public_id)
    before = state(owner)
    activated = client.get(path(frozen), query_string={'yield': '6'})
    assert activated.status_code == 200 and activated.data != original.data
    assert activated.headers['X-Print-Template-Revision'] == 'standard:3'
    assert 'X-Brand-Revision' not in activated.headers
    assert 'Neue aktive Vorlage' in extracted(activated)[1]
    assert 'Neuer aktueller Entwurf' not in extracted(activated)[1]
    assert state(owner) == before


def test_concurrent_activation_cannot_mix_recipe_template_and_brand_snapshots(pdf_http, monkeypatch):
    app, _, client, _, admin, frozen, _ = pdf_http
    engine = app.extensions['cafeteria_db']
    before = client.get(path(frozen))
    assert before.status_code == 200
    config = {**default_config(), 'palette': 'active_brand', 'font': 'active_brand',
              'logo': 'none', 'header_text': 'Parallel aktiviert'}
    change_template(engine, 'recipe', admin.user_id, admin.authz_version, 2, 'standard', 'save', name='Parallel', config=config)
    change_branding(engine, admin.user_id, admin.authz_version, 0, 'save', name='Neue Marke',
                    config={**brand_defaults(), 'font_body': 'fira'})
    original = routes.recipe_print_input
    def activate_after_revision(connection, *args):
        selected = original(connection, *args)
        change_template(engine, 'recipe', admin.user_id, admin.authz_version, 3, 'standard', 'activate',
                        revision_id=3, recipe_public_id=frozen.recipe_public_id, recipe_revision_public_id=frozen.public_id)
        change_branding(engine, admin.user_id, admin.authz_version, 1, 'activate', revision_id=2)
        return selected
    with monkeypatch.context() as patch:
        patch.setattr(routes, 'recipe_print_input', activate_after_revision)
        during = client.get(path(frozen))
    assert during.status_code == 200 and during.data == before.data
    assert during.headers['X-Print-Template-Revision'] == 'standard:2'
    assert during.headers['X-Brand-Revision'] == '1'
    after = client.get(path(frozen))
    assert after.status_code == 200 and after.data != before.data
    assert after.headers['X-Print-Template-Revision'] == 'standard:3'
    assert after.headers['X-Brand-Revision'] == '2'
