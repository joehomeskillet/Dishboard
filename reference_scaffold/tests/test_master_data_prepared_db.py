"""Actual v27 storage/preparation consumers through native signed HTTP forms."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria import master_data_store as masters, recipe_store as recipes
from cafeteria.master_data_types import ObjectExpectation
from test_master_data_db import signed_in, STORAGE_PUBLIC_ID, audit_count
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, create, fields, Forms, installed_pg16, pg16, save, seeded_pg16, snapshot,
)
from test_recipe_store_db import payload as recipe_payload, line, mutable


def freeze_fixture(engine, actor, location, row):
    """Use the actual new SQL API; production Recipe writer is owned by another lane."""
    values = {'actor': actor.user_id, 'authz': actor.authz_version, 'location': location,
              'recipe': row.public_id, 'version': row.row_version}
    with engine.begin() as connection:
        preview = connection.execute(text('''SELECT cafeteria.recipe_dependency_preview_v27(
            :location,CAST(:recipe AS uuid),:version)'''), values).scalar_one()
        assert preview['complete'] and not preview['issues']
        values['hash'] = preview['dependency_hash_sha256']
        return connection.execute(text('''SELECT cafeteria.freeze_recipe_v27(
            :actor,:authz,:location,CAST(:recipe AS uuid),:version,:hash)'''), values).scalar_one()


@pytest.fixture
def prepared(b3):  # noqa: F811
    app, owner, client, actor = b3
    raw = create(client, name='Kichererbsen').rsplit('/', 1)[1]
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = recipes.get_location(engine)
        row = recipes.create_recipe(engine, actor, recipe_payload(title='Hummus festgeschrieben',
            servings='1000', servings_unit_code='G',
            ingredients=[line('Kichererbsen', food_public_id=raw, quantity='700')]),
            expected_location_id=location)
        frozen = freeze_fixture(engine, actor, location, row)
    return app, owner, client, actor, location, frozen


def preparation_choice(frozen):
    return str(frozen['public_id']) + ':' + frozen['content_hash_sha256']


def read_food(prepared, path):
    app, _, _, actor, _, _ = prepared
    with signed_in(app.extensions['cafeteria_db'], actor):
        return masters.get_food(app.extensions['cafeteria_db'], path.rsplit('/', 1)[1])


def test_combined_native_save_is_one_bump_one_audit_and_noop_zero(prepared):
    _, owner, client, _, _, frozen = prepared
    before = audit_count(owner)
    path = create(client, name='Hummus vorbereitet', prepared_recipe_choice=preparation_choice(frozen))
    assert audit_count(owner) == before + 1
    row = read_food(prepared, path)
    assert row.row_version == 1
    assert [item.public_id for item in row.storage_locations] == [STORAGE_PUBLIC_ID]
    assert row.prepared_recipe.revision_public_id == str(frozen['public_id'])
    assert row.prepared_recipe.content_hash_sha256 == frozen['content_hash_sha256']
    assert row.prepared_recipe.yield_quantity == Decimal('1000') and row.prepared_recipe.yield_unit_code == 'G'
    assert row.allergen_review_status == 'not_checked'
    before_state = snapshot(owner)
    assert save(client, path, 'stammdaten').status_code == 303
    assert snapshot(owner) == before_state
    assert save(client, path, 'stammdaten', name='Hummus für morgen').status_code == 303
    changed = read_food(prepared, path)
    assert changed.row_version == row.row_version + 1 and audit_count(owner) == before + 2
    assert changed.prepared_recipe == row.prepared_recipe


def test_missing_pin_preserves_and_explicit_empty_removes(prepared):
    _, owner, client, _, _, frozen = prepared
    path = create(client, name='Hummus vorbereitet', prepared_recipe_choice=preparation_choice(frozen))
    original = read_food(prepared, path)
    data = fields(client, path, 'stammdaten')
    del data['prepared_recipe_choice']
    data['name'] = 'Alter Formularstand ohne neues Feld'
    assert client.post(path + '/stammdaten', data=data).status_code == 303
    kept = read_food(prepared, path)
    assert kept.prepared_recipe == original.prepared_recipe
    before = audit_count(owner)
    assert save(client, path, 'stammdaten', prepared_recipe_choice='').status_code == 303
    removed = read_food(prepared, path)
    assert removed.prepared_recipe is None and removed.row_version == kept.row_version + 1
    assert removed.storage_locations == kept.storage_locations and audit_count(owner) == before + 1


@pytest.mark.parametrize('choice,status', [
    ('wrong_hash', 409), ('55555555-5555-4555-8555-555555555555:' + 'a' * 64, 404),
    ('latest', 400),
])
def test_bad_pin_does_not_change_food_links_audits_or_original_expectations(prepared, choice, status):
    _, owner, client, _, _, frozen = prepared
    path = create(client, name='Hummus vorbereitet', prepared_recipe_choice=preparation_choice(frozen))
    data = fields(client, path, 'stammdaten')
    data['prepared_recipe_choice'] = str(frozen['public_id']) + ':' + 'b' * 64 if choice == 'wrong_hash' else choice
    before = snapshot(owner)
    response = client.post(path + '/stammdaten', data=data)
    assert response.status_code == status and response.headers['Cache-Control'] == 'no-store'
    assert snapshot(owner) == before
    if status != 404:
        returned = Forms(response.text).forms[path + '/stammdaten']
        for key in ('prepared_recipe_choice', '_form_context', 'row_version'):
            assert returned[key] == data[key]


def test_historical_pin_survives_new_head_and_archive_but_cannot_be_newly_selected(prepared):
    app, owner, client, actor, location, frozen = prepared
    path = create(client, name='Hummus vorbereitet', prepared_recipe_choice=preparation_choice(frozen))
    original = read_food(prepared, path)
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        head = recipes.get_recipe(engine, frozen['recipe_public_id'])
        changed_payload = mutable(head.payload)
        changed_payload.update(title='Neue Hummusfassung', servings='2000')
        changed = recipes.update_recipe(engine, actor, ObjectExpectation(head.public_id, head.row_version),
                                        changed_payload, expected_location_id=location)
        freeze_fixture(engine, actor, location, changed)
        head = recipes.get_recipe(engine, head.public_id)
        recipes.set_recipe_active(engine, actor, ObjectExpectation(head.public_id, head.row_version),
                                  active=False, expected_location_id=location)
    row = read_food(prepared, path)
    assert row.prepared_recipe.revision_public_id == original.prepared_recipe.revision_public_id
    assert row.prepared_recipe.title == 'Hummus festgeschrieben' and row.prepared_recipe.yield_quantity == Decimal(1000)
    assert not row.prepared_recipe.recipe_active
    response = client.get(path)
    assert 'archiviertes Rezept, bestehende Auswahl' in response.text
    assert Forms(response.text).forms[path + '/stammdaten']['prepared_recipe_choice'] == preparation_choice(frozen)
    before = snapshot(owner)
    assert save(client, path, 'stammdaten').status_code == 303
    assert snapshot(owner) == before
    new_path = '/admin/grundlagen/zutaten/neu'
    data = fields(client, new_path)
    data.update(name='Neue Verbindung', storage_location_public_ids=STORAGE_PUBLIC_ID,
                prepared_recipe_choice=preparation_choice(frozen))
    assert client.post(new_path, data=data).status_code == 409
    assert snapshot(owner) == before


def test_storage_crud_archive_guard_and_last_storage_rejection(prepared):
    _, owner, client, _, _, frozen = prepared
    storage = create(client, 'lagerorte', name='Kühlraum', code='COOL', sort_order='2')
    storage_id = storage.rsplit('/', 1)[1]
    path = create(client, name='Hummus vorbereitet', prepared_recipe_choice=preparation_choice(frozen),
                  storage_location_public_ids=storage_id)
    before = snapshot(owner)
    response = save(client, storage, 'archivieren')
    assert response.status_code == 409 and '1 Zutaten' in response.text
    assert snapshot(owner) == before
    data = fields(client, path, 'stammdaten')
    del data['storage_location_public_ids']
    response = client.post(path + '/stammdaten', data=data)
    assert response.status_code == 400 and 'Mindestens einen Lagerort auswählen' in response.text
    assert snapshot(owner) == before
    assert save(client, path, 'stammdaten', storage_location_public_ids=STORAGE_PUBLIC_ID).status_code == 303
    assert save(client, storage, 'archivieren').status_code == 303
    assert save(client, storage, 'reaktivieren').status_code == 303
    assert save(client, storage, 'name', name='Kühlraum Süd', sort_order='3').status_code == 303
    assert 'Kühlraum Süd' in client.get('/admin/grundlagen?kind=storage_locations').text
