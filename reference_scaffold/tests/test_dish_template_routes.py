"""HTTP and store contracts for dish-template writers; CAS is updated_at."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from cafeteria import dish_template_store as store
from cafeteria import recipe_store as recipes
from cafeteria.recipe_commands import ERRORS
from cafeteria.recipe_reads import get_location
from cafeteria.recipe_types import RecipeConflictError, RecipeNotFoundError, RecipeValidationError
from cafeteria.master_data_types import ObjectExpectation
from test_master_data_db import signed_in
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import payload as recipe_payload

COLUMNS = ('Titel', 'Menüart', 'Geltungsbereich', 'Gebundenes Rezept', 'Dazu', 'Aktivstatus')


def snapshot(owner):
    with owner.connect() as connection:
        return {table: connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
        )).all() for table in ('dish_templates', 'audit_events')}


def fields(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert path in Forms(response.text).forms, Forms(response.text).forms.keys()
    values = Forms(response.text).forms[path]
    checked = re.search(
        r'name="accompaniment_default" value="(none|soup|salad)" checked', response.text,
    )
    if checked:
        values.setlist('accompaniment_default', [checked.group(1)])
    return values


def create(client, title='Mittagssuppe', **values):
    path = '/admin/gerichtvorlagen/neu'
    data = fields(client, path)
    data['title'] = title
    for key, value in values.items():
        data[key] = value
    response = client.post(path, data=data)
    assert response.status_code == 303, response.text
    listing = client.get('/admin/gerichtvorlagen')
    match = re.search(rf'href="(/admin/gerichtvorlagen/[0-9a-f-]{{36}})">{re.escape(title)}', listing.text)
    assert match, listing.text
    return match.group(1)


def make_recipe(engine, actor, title='Gebundenes Rezept'):
    with signed_in(engine, actor):
        location = recipes.get_location(engine)
        return recipes.create_recipe(
            engine, actor, recipe_payload(title=title), expected_location_id=location,
        )


def foreign_recipe(owner, actor):
    with owner.begin() as connection:
        location = connection.execute(text(
            "INSERT INTO cafeteria.locations(code,name,active) VALUES('FOREIGN','Fremd',false) RETURNING id"
        )).scalar_one()
        public_id = connection.execute(text("""INSERT INTO cafeteria.recipes(
            location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
            VALUES(:loc,:actor,:actor,'Fremdsuppe',4,
            (SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'),'manual')
            RETURNING public_id"""), {'loc': location, 'actor': actor.user_id}).scalar_one()
    return str(public_id)


def test_p1901_is_the_validation_class():
    assert ERRORS['P1901'] is RecipeValidationError
    assert ERRORS['55000'] is RecipeConflictError
    assert ERRORS['22023'] is RecipeNotFoundError


def test_list_columns_sidebar_and_create_without_target(b3):  # noqa: F811
    app, owner, client, _ = b3
    assert sum(rule.endpoint == 'admin.dish_templates_list' for rule in app.url_map.iter_rules()) == 1
    listing = client.get('/admin/gerichtvorlagen')
    assert listing.status_code == 200
    assert 'Gerichtvorlagen' in listing.text
    assert 'Noch keine Gerichtvorlagen' in listing.text
    before = snapshot(owner)
    path = create(client, title='Ohne Ziel')
    filled = client.get('/admin/gerichtvorlagen')
    assert path.startswith('/admin/gerichtvorlagen/')
    assert 'Ohne Ziel' in filled.text
    assert all(column in filled.text for column in COLUMNS)
    assert len(snapshot(owner)['dish_templates']) == len(before['dish_templates']) + 1
    assert len(snapshot(owner)['audit_events']) == len(before['audit_events']) + 1


def test_create_with_target_is_p1901(b3):  # noqa: F811
    _, owner, client, _ = b3
    data = fields(client, '/admin/gerichtvorlagen/neu')
    data['title'] = 'Mit Ziel'
    data['public_id'] = str(uuid4())
    data['updated_at'] = datetime.now(timezone.utc).isoformat()
    before = snapshot(owner)
    response = client.post('/admin/gerichtvorlagen/neu', data=data)
    assert response.status_code == 400
    assert 'Ungültige neue Gerichtvorlage' in response.text
    assert snapshot(owner) == before


def test_stale_updated_at_is_409_with_preserved_context(b3):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Ursprung')
    stale = fields(client, path)
    fresh = fields(client, path)
    fresh['title'] = 'Erste Sitzung'
    assert client.post(path, data=fresh).status_code == 303
    stale['title'] = 'Zweite Sitzung'
    before = snapshot(owner)
    conflict = client.post(path, data=stale)
    assert conflict.status_code == 409
    assert conflict.headers['Cache-Control'] == 'no-store'
    assert 'Gerichtvorlage wurde geändert' in conflict.text
    assert 'Zweite Sitzung' in conflict.text
    assert 'Aktuellen Stand neu laden' in conflict.text
    returned = Forms(conflict.text).forms[path]
    assert returned['updated_at'] == stale['updated_at']
    assert snapshot(owner) == before


def test_noop_update_returns_same_row_without_second_audit(b3):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Unverändert')
    data = fields(client, path)
    before = snapshot(owner)
    assert client.post(path, data=data).status_code == 303
    assert snapshot(owner) == before
    again = fields(client, path)
    assert again['updated_at'] == data['updated_at']
    assert again['title'] == 'Unverändert'


def test_accompaniment_create_update_validation_and_reader_view(b3, monkeypatch):  # noqa: F811
    from cafeteria import roles

    app, owner, client, _ = b3
    engine = app.extensions['cafeteria_db']

    default_data = fields(client, '/admin/gerichtvorlagen/neu')
    assert default_data['accompaniment_default'] == 'none'
    default_data.pop('accompaniment_default')
    default_data['title'] = 'Ohne Vorschlag'
    assert client.post('/admin/gerichtvorlagen/neu', data=default_data).status_code == 303
    assert store.list_templates(engine)[0].accompaniment_default == 'none'

    path = create(client, title='Mit Salat', accompaniment_default='salad')
    edit_values = fields(client, path)
    assert edit_values['accompaniment_default'] == 'salad'
    listing = client.get('/admin/gerichtvorlagen')
    assert 'Dazu' in listing.text and 'Salat' in listing.text
    assert '#tabler-salad' in listing.text

    before = snapshot(owner)
    edit_values.pop('accompaniment_default')
    assert client.post(path, data=edit_values).status_code == 303
    assert store.get_template(engine, path.rsplit('/', 1)[-1]).accompaniment_default == 'salad'
    assert snapshot(owner) == before

    invalid = fields(client, path)
    invalid['title'] = 'Eingabe bleibt erhalten'
    invalid['accompaniment_default'] = 'both'
    rejected = client.post(path, data=invalid)
    assert rejected.status_code == 400
    assert 'Bitte eine gültige Beilage wählen.' in rejected.text
    assert 'Eingabe bleibt erhalten' in rejected.text
    assert 'aria-invalid="true"' in rejected.text
    assert 'href="#accompaniment-none"' in rejected.text
    assert snapshot(owner) == before

    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    def unexpected_list_templates(*_args, **_kwargs):
        raise AssertionError('list rendering must use the link-reader projection')
    monkeypatch.setattr(store, 'list_templates', unexpected_list_templates)
    reader = client.get('/admin/gerichtvorlagen')
    assert reader.status_code == 200
    assert 'data-label="Dazu"' in reader.text and 'Salat' in reader.text and '#tabler-salad' in reader.text
    assert 'Vorlage anlegen</a>' not in reader.text and 'name="action"' not in reader.text


def test_unchanged_active_is_55000(b3):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Schon aktiv')
    data = fields(client, path)
    data['action'] = 'reactivate'
    before = snapshot(owner)
    response = client.post(path, data=data)
    assert response.status_code == 409
    assert 'Aktivstatus ist unverändert' in response.text
    assert snapshot(owner) == before


def test_profile_scope_outside_contract_is_p1901(b3):  # noqa: F811
    _, owner, client, _ = b3
    data = fields(client, '/admin/gerichtvorlagen/neu')
    data['title'] = 'Falscher Scope'
    data['profile_scope'] = 'kitchen'
    before = snapshot(owner)
    response = client.post('/admin/gerichtvorlagen/neu', data=data)
    assert response.status_code == 400
    assert 'Ungültige Vorlagenfelder' in response.text
    assert snapshot(owner) == before


def test_archived_recipe_cannot_be_rebound(b3):  # noqa: F811
    _, owner, client, actor = b3
    engine = b3[0].extensions['cafeteria_db']
    recipe = make_recipe(engine, actor, 'Archivrezept')
    with signed_in(engine, actor):
        recipes.set_recipe_active(
            engine, actor, ObjectExpectation(recipe.public_id, recipe.row_version),
            active=False, expected_location_id=recipes.get_location(engine),
        )
    path = create(client, title='Ohne Rezept')
    data = fields(client, path)
    data['recipe_public_id'] = recipe.public_id
    before = snapshot(owner)
    response = client.post(path, data=data)
    assert response.status_code == 409
    assert 'Archiviertes Rezept kann nicht neu zugeordnet werden' in response.text
    assert snapshot(owner) == before


def test_recipe_of_other_location_is_22023(b3):  # noqa: F811
    _, owner, client, actor = b3
    foreign = foreign_recipe(owner, actor)
    data = fields(client, '/admin/gerichtvorlagen/neu')
    data['title'] = 'Fremdes Rezept'
    data['recipe_public_id'] = foreign
    before = snapshot(owner)
    response = client.post('/admin/gerichtvorlagen/neu', data=data)
    assert response.status_code == 400
    assert 'Unbekanntes Rezept' in response.text
    assert snapshot(owner) == before


def test_store_create_with_target_and_bad_scope(b3):  # noqa: F811
    app, _, _, actor = b3
    engine = app.extensions['cafeteria_db']
    location = get_location(engine)
    payload = {
        'menu_type_code': 'MENU_1', 'profile_scope': 'common', 'title': 'Direkt',
        'description': None, 'recipe_public_id': None,
    }
    with pytest.raises(RecipeValidationError, match='Ungültige neue Gerichtvorlage'):
        store.create_template(
            engine, actor, payload, expected_location_id=location, target=str(uuid4()),
        )
    created = store.create_template(engine, actor, payload, expected_location_id=location)
    assert created['active'] is True
    payload['profile_scope'] = 'kitchen'
    with pytest.raises(RecipeValidationError, match='Ungültige Vorlagenfelder'):
        store.create_template(engine, actor, payload, expected_location_id=location)


def test_prefill_get_does_not_write_and_uses_the_existing_recipe_editor(b3):  # noqa: F811
    app, owner, client, actor = b3
    recipe = make_recipe(app.extensions['cafeteria_db'], actor, 'Vorbelegte Suppe')
    before = snapshot(owner)
    response = client.get('/admin/gerichtvorlagen/neu', query_string={'recipe': recipe.public_id})
    assert response.status_code == 200
    values = Forms(response.text).forms['/admin/gerichtvorlagen/neu']
    assert values['recipe_public_id'] == recipe.public_id and values['title'] == 'Vorbelegte Suppe'
    assert snapshot(owner) == before
    path = create(client, recipe_public_id=recipe.public_id)
    listing = client.get('/admin/gerichtvorlagen')
    assert f'href="/admin/rezepte/{recipe.public_id}/ansicht"' in listing.text
    assert 'Rezept: Vorbelegte Suppe' in listing.text
    assert 'Noch kein gespeicherter Stand' in listing.text and 'In 0 Menüs verwendet' in listing.text
    assert client.get('/admin/rezepte/' + recipe.public_id + '/ansicht').status_code == 200
    assert client.get(path).status_code == 200


def test_unknown_foreign_and_archived_prefill(b3):  # noqa: F811
    app, owner, client, actor = b3
    for public_id in (str(uuid4()), foreign_recipe(owner, actor), 'not-a-uuid'):
        before = snapshot(owner)
        response = client.get('/admin/gerichtvorlagen/neu', query_string={'recipe': public_id})
        assert response.status_code == 404 and 'Rezept nicht gefunden.' in response.text
        values = Forms(response.text).forms['/admin/gerichtvorlagen/neu']
        assert values['recipe_public_id'] == values['title'] == ''
        assert snapshot(owner) == before
    engine = app.extensions['cafeteria_db']
    recipe = make_recipe(engine, actor, 'Archiv für Vorbelegung')
    with signed_in(engine, actor):
        recipes.set_recipe_active(engine, actor, ObjectExpectation(recipe.public_id, recipe.row_version),
                                  active=False, expected_location_id=recipes.get_location(engine))
    before = snapshot(owner)
    response = client.get('/admin/gerichtvorlagen/neu', query_string={'recipe': recipe.public_id})
    assert response.status_code == 200 and 'Rezept archiviert' in response.text
    values = Forms(response.text).forms['/admin/gerichtvorlagen/neu']
    assert client.post('/admin/gerichtvorlagen/neu', data=values).status_code == 409
    assert snapshot(owner) == before


def test_search_intents_preserve_unsaved_fields_and_original_cas_without_writes(b3):  # noqa: F811
    from test_recipe_link_reads_db import seed_recipe_page
    _, owner, client, actor = b3
    ids = seed_recipe_page(owner, actor)
    path = create(client, recipe_public_id=ids[-1])
    original = fields(client, path)
    newer = original.copy()
    newer['title'] = 'Andere Sitzung'
    assert client.post(path, data=newer).status_code == 303
    for name, value in {'title': '', 'description': 'Ungespeichert\nZweite Zeile', 'menu_type_code': 'VEGGIE',
                        'profile_scope': 'patient', 'action': 'recipe_search', 'recipe_search': '205'}.items():
        original[name] = value
    before = snapshot(owner)
    response = client.post(path, data=original)
    assert response.status_code == 200
    returned = Forms(response.text).forms[path]
    for name in ('title', 'description', 'menu_type_code', 'profile_scope', 'recipe_public_id', 'updated_at'):
        assert returned[name] == original[name]
    assert snapshot(owner) == before
    returned['title'] = 'Mein Titel'
    returned['description'] = 'Gültige Beschreibung'
    returned['action'] = 'save'
    assert client.post(path, data=returned).status_code == 409
    assert snapshot(owner) == before
    no_csrf = original.copy()
    no_csrf.pop('_csrf')
    assert client.post(path, data=no_csrf).status_code == 400
    original['updated_at'] = 'invalid-original-token'
    invalid = client.post(path, data=original)
    assert invalid.status_code == 400
    assert Forms(invalid.text).forms[path]['updated_at'] == original['updated_at']
    assert snapshot(owner) == before


def test_read_only_navigation_has_no_write_actions(b3, monkeypatch):  # noqa: F811
    from cafeteria import roles
    app, _, client, actor = b3
    recipe = make_recipe(app.extensions['cafeteria_db'], actor)
    path = create(client, recipe_public_id=recipe.public_id)
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    for target in ('/admin/gerichtvorlagen', path):
        response = client.get(target)
        assert response.status_code == 200 and 'Rezept: Gebundenes Rezept' in response.text
        assert 'Vorlage anlegen</a>' not in response.text and 'name="action"' not in response.text
        assert 'Als Menü einplanen' not in response.text
    viewed = client.get('/admin/rezepte/' + recipe.public_id + '/ansicht')
    assert viewed.status_code == 200 and 'name="_form_context"' not in viewed.text
    assert '>Bearbeiten</a>' not in viewed.text
    assert client.post(path, data={'action': 'recipe_search'}).status_code == 403
    assert client.get(path + '/einplanen').status_code == 403
    assert client.post(path + '/einplanen').status_code == 403


@pytest.mark.parametrize('recipe_state', ('none', 'no_revision', 'active', 'archived'))
def test_native_proposal_real_runtime_role(b3, recipe_state):  # noqa: F811
    from test_menu_proposal_routes import editor_form, planning
    from test_menu_recipe_selection_browser import _insert_revision
    from test_menu_template_binding_db import make_template, stored_state
    app, owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with engine.connect() as connection:
        assert connection.execute(text('SELECT current_user')).scalar_one() == 'cafeteria_app'
    recipe_id = None
    if recipe_state == 'no_revision':
        recipe = make_recipe(engine, actor)
        with owner.connect() as connection:
            recipe_id = connection.execute(text(
                'SELECT id FROM cafeteria.recipes WHERE public_id=CAST(:public_id AS uuid)'
            ), {'public_id': recipe.public_id}).scalar_one()
    elif recipe_state in ('active', 'archived'):
        revision = _insert_revision(owner, actor.user_id, 'Einplanbares Rezept')
        recipe_id = int(revision['recipe_id'])
        if recipe_state == 'archived':
            with owner.begin() as connection:
                connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:id'),
                                   {'id': recipe_id})
    template = make_template(owner, recipe=recipe_id)
    before = stored_state(owner)
    path, source, _ = planning(client, template, area='patient')
    selected = client.post(path, data=source)
    assert selected.status_code == 303, selected.text
    menu, _ = editor_form(client, selected.location)
    assert bool(menu['recipe_revision_public_id']) == (recipe_state == 'active')
    assert stored_state(owner) == before
    target = '/admin/patienten/menu?return_to=week'
    saved = client.post(target, data=menu)
    assert saved.status_code == 303, saved.text
    assert 'Aus Vorlage «Rösti»' in client.get(saved.location).text
    after = stored_state(owner)
    assert after['dish_templates'] == before['dish_templates']
    assert len(after['menu_items']) == len(before['menu_items']) + 1
    assert len(after['audit_events']) == len(before['audit_events']) + 1
    assert client.post(target, data=menu).status_code == 409
    assert stored_state(owner) == after
