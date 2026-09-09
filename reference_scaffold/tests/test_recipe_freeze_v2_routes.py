"""Native HTTP binds exactly the shown dependency state; POST never refreshes it."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from cafeteria import recipe_store as store, master_data_store as masters, roles
from cafeteria.admin import recipe_forms as forms
from test_master_data_db import signed_in
from test_master_data_routes import Forms
from test_recipe_freeze_v2_db import full_state
from test_recipe_revision_routes import (  # noqa: F401
    a3, b3, app_engine, pg16, installed_pg16, seeded_pg16, complete_a3, edit, fields,
)
from test_recipe_store_db import target, mutable


@pytest.fixture
def ready(a3):  # noqa: F811
    complete_a3(a3)
    return a3


def revision_path(fixture):
    return f'/admin/rezepte/{fixture[4]}/revisionen'


def rename_food(fixture):
    app, _, _, actor, public_id = fixture
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        recipe = store.get_recipe(engine, public_id)
        food_id = recipe.payload['ingredients'][0]['food_public_id']
        food = masters.get_food(engine, food_id)
        with app.extensions['cafeteria_db'].connect() as connection:
            storage = connection.execute(text('SELECT public_id::text FROM cafeteria.storage_locations')).scalar_one()
        masters.update_food(engine, actor, target(food), {'name': 'Frisch umbenannt', 'base_unit_code': 'KG',
            'storage_location_public_ids': [storage]}, original_location=store.get_location(engine))


def test_real_preview_exact_signed_hash_and_freeze_never_refreshes_on_post(ready, monkeypatch):
    app, owner, client, _, public_id = ready
    path = revision_path(ready)
    before = full_state(owner)
    shown = client.get(path)
    assert shown.status_code == 200 and shown.headers['Cache-Control'] == 'no-store'
    assert 'Zutatenstand prüfen' in shown.text and 'Testlager' in shown.text and '0.125 KG' in shown.text
    original = Forms(shown.text).forms[path]
    assert set(original) == {'_csrf', '_form_context', 'row_version'}
    with app.app_context():
        signed = forms._signer().loads(original['_form_context'])
    assert set(signed) == {'action', 'actor', 'actor_version', 'target', 'version', 'location', 'csrf', 'labels',
                           'dependency_hash_sha256'}
    assert signed['target'] == public_id and signed['version'] == int(original['row_version'])
    assert full_state(owner) == before
    real = store.freeze_revision
    calls = []
    def write(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail('POST must not reload or sign original expectations')
    with monkeypatch.context() as patch:
        patch.setattr(store, 'get_dependency_preview', forbidden)
        patch.setattr(store, 'get_recipe', forbidden)
        patch.setattr(forms, 'sign_context', forbidden)
        patch.setattr(store, 'freeze_revision', write)
        response = client.post(path, data=original)
    assert response.status_code == 303 and response.location.startswith(path + '/')
    assert calls == [{'expected_location_id': signed['location'], 'expected_dependency_hash': signed['dependency_hash_sha256']}]
    assert client.get(response.location).status_code == 200
    with owner.connect() as connection:
        assert connection.execute(text('SELECT snapshot_json->>\'schema_version\' FROM cafeteria.recipe_revisions')).scalar_one() == '2'
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='recipe.freeze'")).scalar_one() == 1


def test_changed_dependency_is_409_and_only_deliberate_new_get_can_sign_again(ready, monkeypatch):
    app, owner, client, _, _ = ready
    path = revision_path(ready)
    original = fields(client, path)
    rename_food(ready)
    before = full_state(owner)
    with monkeypatch.context() as patch:
        patch.setattr(forms, 'sign_context', lambda **kwargs: pytest.fail('Conflict must not re-sign'))
        patch.setattr(store, 'get_dependency_preview', lambda *args, **kwargs: pytest.fail('POST must not preview'))
        response = client.post(path, data=original)
    assert response.status_code == 409 and response.headers['Cache-Control'] == 'no-store'
    recovered = Forms(response.text).forms['']
    assert recovered['_form_context'] == original['_form_context']
    assert 'Aktuellen Stand bewusst neu laden' in response.text and full_state(owner) == before
    listing = client.get('/admin/rezepte')
    assert listing.status_code == 200 and f'href="{path}"' in listing.text
    newer = fields(client, path)
    with app.app_context():
        old, new = [forms._signer().loads(data['_form_context']) for data in (original, newer)]
    assert old['version'] == new['version'] and old['dependency_hash_sha256'] != new['dependency_hash_sha256']
    assert full_state(owner) == before
    assert client.post(path, data=newer).status_code == 303


@pytest.mark.parametrize('bad,status', [('missing', 400), ('null', 400), ('uppercase', 400),
    ('other_hash', 409), ('action', 400), ('signed_extra', 400), ('unsigned_hash', 400)])
def test_invalid_original_dependency_never_mutates_or_silently_refreshes(ready, monkeypatch, bad, status):
    app, owner, client, _, _ = ready
    path = revision_path(ready)
    original = fields(client, path)
    with app.app_context():
        signer = forms._signer()
        signed = signer.loads(original['_form_context'])
        if bad == 'missing':
            signed.pop('dependency_hash_sha256')
        elif bad == 'null':
            signed['dependency_hash_sha256'] = None
        elif bad == 'uppercase':
            signed['dependency_hash_sha256'] = 'A' * 64
        elif bad == 'other_hash':
            signed['dependency_hash_sha256'] = '0' * 64
        elif bad == 'action':
            signed['action'] = 'recipe.update'
        elif bad == 'signed_extra':
            signed['extra'] = 'unexpected'
        else:
            original['dependency_hash_sha256'] = signed['dependency_hash_sha256']
        original['_form_context'] = signer.dumps(signed)
    before = full_state(owner)
    monkeypatch.setattr(store, 'get_dependency_preview', lambda *args, **kwargs: pytest.fail('POST preview'))
    monkeypatch.setattr(forms, 'sign_context', lambda **kwargs: pytest.fail('POST signing'))
    response = client.post(path, data=original)
    assert response.status_code == status and full_state(owner) == before


@pytest.mark.parametrize('missing', ['food', 'quantity', 'all'])
def test_incomplete_preview_returns_400_without_token_but_draft_and_history_remain_readable(ready, missing):
    app, owner, client, actor, public_id = ready
    path = revision_path(ready)
    frozen = client.post(path, data=fields(client, path))
    assert frozen.status_code == 303
    with signed_in(app.extensions['cafeteria_db'], actor):
        row = store.get_recipe(app.extensions['cafeteria_db'], public_id)
        data = mutable(row.payload)
    if missing == 'all':
        data['ingredients'] = []
    else:
        data['ingredients'][0].update({'food_public_id': None} if missing == 'food' else {'quantity': None, 'unit_code': None})
    edit(ready, ingredients=data['ingredients'])
    before = full_state(owner)
    response = client.get(path)
    assert response.status_code == 400 and 'noch unvollständig' in response.text
    assert 'name="_form_context"' not in response.text and frozen.location in response.text
    assert client.get(frozen.location).status_code == 200
    listing = client.get('/admin/rezepte')
    assert 'Entwurf · Angaben fehlen' in listing.text
    assert client.get(f'/admin/rezepte/{public_id}').status_code == 200
    assert full_state(owner) == before


def test_preview_read_role_and_safe_database_outage_are_separate_from_write(ready, monkeypatch):
    app, owner, client, _, _ = ready
    path = revision_path(ready)
    original = fields(client, path)
    before = full_state(owner)
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    shown = client.get(path)
    assert shown.status_code == 200 and 'Zutatenstand prüfen' in shown.text
    assert 'name="_form_context"' not in shown.text
    assert client.post(path, data=original).status_code == 403
    def unavailable(*args, **kwargs):
        raise OperationalError('sql-secret-sentinel', {}, RuntimeError('private-dsn-sentinel'))
    monkeypatch.setattr(store, 'get_dependency_preview', unavailable)
    response = client.get(path)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'private-dsn-sentinel' not in response.text and 'sql-secret-sentinel' not in response.text
    assert full_state(owner) == before
