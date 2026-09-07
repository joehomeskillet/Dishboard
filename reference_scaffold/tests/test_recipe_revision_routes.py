"""Real route/service/PG contracts for revision, image and scaling consumers."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from cafeteria import recipe_store as store, roles
from cafeteria.admin import recipe_revision_routes, recipe_image_routes  # noqa: F401
from cafeteria.admin import recipe_forms as forms
from test_master_data_routes import Forms, b3, pg16, installed_pg16, seeded_pg16, app_engine  # noqa: F401
from test_master_data_db import signed_in
from test_recipe_store_db import payload, line, target, snapshot, mutable


@pytest.fixture
def a3(b3):  # noqa: F811
    app, owner, client, actor = b3
    # The complete application must expose the actual A2 consumer, exactly once.
    from cafeteria.admin.recipe_routes import recipe_edit
    assert app.view_functions['admin.recipe_edit'] is recipe_edit
    assert sum(rule.endpoint == 'admin.recipe_edit' for rule in app.url_map.iter_rules()) == 1
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        row = store.create_recipe(engine, actor, payload(ingredients=[
            line(quantity='0.125', unit_code='KG'), line('Salz', quantity=None, unit_code=None)]),
            expected_location_id=store.get_location(engine))
    return app, owner, client, actor, row.public_id


def fields(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return Forms(response.text).forms[path]


def png():
    data = io.BytesIO()
    Image.new('RGB', (24, 18), 'green').save(data, format='PNG')
    return data.getvalue()


def upload(client, path, data=None, content=None, mime='image/png'):
    values = fields(client, path) if data is None else data.copy()
    values.pop('file', None)
    values['file'] = (io.BytesIO(png() if content is None else content), 'recipe.png', mime)
    return client.post(path, data=values, content_type='multipart/form-data')


def edit(a3, **changes):
    app, _, _, actor, public_id = a3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        row = store.get_recipe(engine, public_id)
        data = mutable(row.payload)
        data.update(changes)
        return store.update_recipe(engine, actor, target(row), data, expected_location_id=store.get_location(engine))


def test_freeze_exact_revision_redirect_immutable_detail_and_no_post_reload(a3, monkeypatch):
    _, owner, client, _, public_id = a3
    path = f'/admin/rezepte/{public_id}/revisionen'
    original = fields(client, path)
    before = snapshot(owner)
    for url in (path, f'/admin/rezepte/{public_id}/skalierung', f'/admin/rezepte/{public_id}/bilder'):
        assert client.get(url).status_code == 200
    assert snapshot(owner) == before
    with monkeypatch.context() as patch:
        patch.setattr(forms, 'sign_context', lambda **kwargs: pytest.fail('POST must not sign'))
        patch.setattr(store, 'get_recipe', lambda *args, **kwargs: pytest.fail('POST must not reload CAS'))
        response = client.post(path, data=original)
    assert response.status_code == 303
    with owner.connect() as connection:
        revision = connection.execute(text('SELECT public_id,content_hash_sha256,snapshot_json::text FROM cafeteria.recipe_revisions')).one()
    assert response.location == path + '/' + str(revision.public_id)
    detail = client.get(response.location)
    assert detail.status_code == 200 and revision.content_hash_sha256 in detail.text
    assert client.post(path, data=original).status_code == 409
    edit(a3, title='Changed draft')
    assert client.get(response.location).text == detail.text
    with owner.connect() as connection:
        assert connection.execute(text('SELECT content_hash_sha256,snapshot_json::text FROM cafeteria.recipe_revisions')).one() == tuple(revision)[1:]
    assert client.get(f'/admin/rezepte/{uuid4()}/revisionen/{revision.public_id}').status_code == 404


@pytest.mark.parametrize('suffix', ['revisionen', 'bilder'])
@pytest.mark.parametrize('mode,status', [('stale', 409), ('location', 409), ('csrf', 400),
                                        ('tamper', 400), ('version', 400), ('duplicate', 400),
                                        ('unknown', 400), ('logout', 401), ('revoke', 401)])
def test_original_context_errors_retain_values_without_mutation(a3, suffix, mode, status):
    _, owner, client, actor, public_id = a3
    path = f'/admin/rezepte/{public_id}/{suffix}'
    original = fields(client, path)
    if suffix == 'bilder':
        original['caption'] = 'Meine ursprüngliche Bildunterschrift'
    if mode == 'stale':
        edit(a3, title='Other tab')
    elif mode == 'location':
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Andere Küche',true)"))
    elif mode == 'csrf':
        original['_csrf'] = 'wrong'
    elif mode == 'tamper':
        original['_form_context'] += 'changed'
    elif mode == 'version':
        original['row_version'] = str(int(original['row_version']) + 1)
    elif mode == 'duplicate':
        original.add('row_version', original['row_version'])
    elif mode == 'unknown':
        original['unexpected'] = 'Unverändert kopierbar'
    elif mode == 'logout':
        with client.session_transaction() as session:
            session.clear()
    else:
        with owner.begin() as connection:
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    before = snapshot(owner)
    response = upload(client, path, original) if suffix == 'bilder' else client.post(path, data=original)
    assert response.status_code == status and response.headers['Cache-Control'] == 'no-store'
    assert snapshot(owner) == before
    if status in (400, 409):
        recovered = Forms(response.text).forms['']
        for key, value in original.items(multi=True):
            if key != 'file':
                assert value in recovered.getlist(key)
        if suffix == 'bilder':
            assert original['caption'] in response.text
        assert 'Aktuellen Stand bewusst neu laden' in response.text


@pytest.mark.parametrize('suffix', ['revisionen', 'bilder', 'skalierung'])
@pytest.mark.parametrize('boundary', ['auth', 'reader'])
def test_outer_auth_and_reader_outage_is_safe_503(a3, monkeypatch, suffix, boundary):
    app, _, client, _, public_id = a3
    def offline(*args, **kwargs):
        raise OperationalError('private statement', {}, Exception('private database detail'))
    @app.context_processor
    def no_enrichment():
        pytest.fail('503 must not enrich templates from database')
    monkeypatch.setattr(roles if boundary == 'auth' else store,
                        'load_user_authorization' if boundary == 'auth' else 'get_recipe', offline)
    response = client.get(f'/admin/rezepte/{public_id}/{suffix}')
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'private database detail' not in response.text and 'tabler.min.css' in response.text


def test_upload_real_asset_provenance_and_historical_bytes(a3):
    app, owner, client, actor, public_id = a3
    path = f'/admin/rezepte/{public_id}/bilder'
    data = fields(client, path)
    for key, value in dict(caption='Original image', source_url='https://example.test/origin',
                          source_license='CC0', fetched_at='2026-09-07T10:00:00+02:00').items():
        data[key] = value
    assert upload(client, path, data).status_code == 303
    with owner.connect() as connection:
        sha = connection.execute(text('SELECT sha256 FROM cafeteria.recipe_images')).scalar_one()
    asset_path = path + '/' + sha
    response = client.get(asset_path)
    assert response.status_code == 200 and response.data == png() and response.content_type == 'image/png'
    assert response.headers['Cache-Control'] == 'no-store' and response.headers['X-Content-Type-Options'] == 'nosniff'
    listing = client.get(path)
    assert 'Original image' in listing.text and 'CC0' in listing.text
    freeze_path = f'/admin/rezepte/{public_id}/revisionen'
    revision = client.post(freeze_path, data=fields(client, freeze_path))
    assert revision.status_code == 303
    historical = client.get(revision.location).text
    edit(a3, images=[])
    assert client.get(asset_path).data == response.data
    assert client.get(revision.location).text == historical
    with signed_in(app.extensions['cafeteria_db'], actor):
        other = store.create_recipe(app.extensions['cafeteria_db'], actor, payload(title='Other'),
                                    expected_location_id=store.get_location(app.extensions['cafeteria_db']))
    assert client.get(f'/admin/rezepte/{other.public_id}/bilder/{sha}').status_code == 404
    assert client.get(path + '/' + '0' * 64).status_code == 404


@pytest.mark.parametrize('content,mime', [(b'broken', 'image/png'), (b'x' * 1048577, 'image/png'),
                                         (None, 'image/jpeg'), (None, 'image/svg+xml')])
def test_invalid_upload_cannot_mutate(a3, content, mime):
    _, owner, client, _, public_id = a3
    path = f'/admin/rezepte/{public_id}/bilder'
    data = fields(client, path)
    data['caption'] = 'Must remain copyable'
    before = snapshot(owner)
    response = upload(client, path, data, content, mime)
    assert response.status_code == 400 and data['caption'] in response.text
    assert snapshot(owner) == before


def test_read_only_scaling_invalid_target_and_archived_recipe(a3):
    app, owner, client, actor, public_id = a3
    path = f'/admin/rezepte/{public_id}/skalierung'
    before = snapshot(owner)
    response = client.get(path + '?yield=6')
    assert response.status_code == 200 and '0.1875' in response.text and 'Ohne Mengenangabe' in response.text
    bad = client.get(path + '?yield=NaN')
    assert bad.status_code == 400 and 'value="NaN"' in bad.text and 'aria-invalid="true"' in bad.text
    assert client.get(path + '?yield=1&yield=2').status_code == 400
    assert snapshot(owner) == before
    with signed_in(app.extensions['cafeteria_db'], actor):
        row = store.get_recipe(app.extensions['cafeteria_db'], public_id)
        store.set_recipe_active(app.extensions['cafeteria_db'], actor, target(row), active=False,
                                expected_location_id=store.get_location(app.extensions['cafeteria_db']))
    before = snapshot(owner)
    for suffix in ['skalierung', 'bilder', 'revisionen']:
        result = client.get(f'/admin/rezepte/{public_id}/{suffix}')
        assert result.status_code == 200
        assert 'name="_form_context"' not in result.text
    assert snapshot(owner) == before
