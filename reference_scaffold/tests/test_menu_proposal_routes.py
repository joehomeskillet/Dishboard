"""Native proposal transitions retain source authority and create-only target CAS."""
from dataclasses import asdict, replace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import text

from cafeteria.admin.workflow_scope import _sign_template_context, read_template_context
from test_admin_workflow_routes import DAY, WEEK, _hidden, _login, _menu_form, _scope
from test_master_data_db import make_actor
from test_master_data_routes import Forms
from test_menu_recipe_selection_browser import _foreign_revision, _insert_revision
from test_menu_template_binding_db import make_template, stored_state
from test_rendered_ui import admin_app, admin_engine  # noqa: F401


def planning(client, template, **changes):
    path = f'/admin/gerichtvorlagen/{template["public_id"]}/einplanen'
    response = client.get(path + f'?week={DAY}')
    assert response.status_code == 200, response.text
    form = Forms(response.text).forms[path]
    for key, value in changes.items():
        form[key] = value
    return path, form, response


def editor_form(client, location, family='patienten'):
    response = client.get(location)
    assert response.status_code == 200, response.text
    action = f'/admin/{family}/menu'
    native = Forms(response.text).forms[action]
    form = _menu_form(_csrf=native['_csrf'], title=native['title'],
        description=native['description'], component_public_id='', component_text='Rösti',
        recipe_revision_public_id=native.get('recipe_revision_public_id', ''),
        dish_template_public_id=native['dish_template_public_id'],
        template_context=native['template_context'], day=native['day'],
        week=native['week'], meal=native['meal'], option=native['option'])
    if family == 'cafeteria':
        form.update(internal_chf='9.50', external_chf='14.50')
    return form, response


@pytest.mark.parametrize('family', ('patienten', 'cafeteria'))
def test_native_source_target_editor_save_and_duplicate(admin_app, admin_engine, family):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    first = _insert_revision(admin_engine, actor, 'Erster Rezeptstand')
    newest = _insert_revision(admin_engine, actor, 'Aktueller Rezeptstand',
        recipe_id=int(first['recipe_id']), revision_number=2)
    template = make_template(admin_engine, recipe=int(first['recipe_id']))
    with admin_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.dish_templates SET description='Mit Gemüse' WHERE id=:id"), template)
    area = 'patient' if family == 'patienten' else 'staff_guest'
    path, source_form, _ = planning(client, template, area=area)
    before = stored_state(admin_engine)
    response = client.post(path, data=source_form)
    assert response.status_code == 303, response.text
    assert client.post(path, data=source_form).status_code == 303
    query = parse_qs(urlsplit(response.location).query)
    assert '_csrf' not in query and 'workflow-csrf' not in response.location
    with admin_app.test_request_context():
        source = asdict(read_template_context(source_form['template_context'], target=False))
        target = asdict(read_template_context(query['template_context'][0], target=True))
    assert all(target[key] == value for key, value in source.items() if value is not None)
    assert target['expected_item_row_version'] == 0 and target['recipe_active'] is True
    form, editor = editor_form(client, response.location, family)
    assert form['title'] == 'Rösti' and form['description'] == 'Mit Gemüse'
    assert form['recipe_revision_public_id'] == newest['public_id']
    assert 'Neues Menü aus Vorlage «Rösti»' in editor.text
    assert 'Vorgeschlagen: Stand 2' in editor.text
    assert 'Anderen Stand wählen oder ohne Rezeptbindung speichern' in editor.text
    if family == 'patienten':
        assert 'name="internal_chf"' not in editor.text and 'name="external_chf"' not in editor.text
    else:
        native = Forms(editor.text).forms[f'/admin/{family}/menu']
        assert native['internal_chf'] == native['external_chf'] == ''
    assert stored_state(admin_engine) == before
    form['title'] = 'Eigenes Rösti-Menü'
    save = f'/admin/{family}/menu?return_to=week'
    saved = client.post(save, data=form)
    assert saved.status_code == 303
    week = client.get(saved.location)
    assert 'Menü «Eigenes Rösti-Menü» aus Vorlage «Rösti» für Montag' in week.text
    assert 'Mittag, Menü 1 gespeichert.' in week.text and 'Aus Vorlage «Rösti»' in week.text
    after = stored_state(admin_engine)
    assert after['dish_templates'] == before['dish_templates']
    for _ in range(2):
        conflict = client.post(save, data=form)
        assert conflict.status_code == 409
        assert _hidden(conflict.text, 'row_version') == '0'
        assert _hidden(conflict.text, 'template_context') == form['template_context']
        assert 'Bestehendes Menü öffnen' in conflict.text
    assert stored_state(admin_engine) == after


@pytest.mark.parametrize('state', ('no_recipe', 'no_revision', 'archived'))
def test_missing_or_archived_recipe_keeps_explicit_unbound_choice(admin_app, admin_engine, state):  # noqa: F811
    from test_menu_recipe_choices_reader import create_recipe
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    recipe_id = None
    revision = None
    if state == 'no_revision':
        recipe_id = create_recipe(admin_engine, actor, 'Noch nicht festgehalten')
    elif state == 'archived':
        revision = _insert_revision(admin_engine, actor, 'Historisches Rezept')
        recipe_id = int(revision['recipe_id'])
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:id'), {'id': recipe_id})
    template = make_template(admin_engine, recipe=recipe_id)
    path, form, _ = planning(client, template, area='patient')
    response = client.post(path, data=form)
    assert response.status_code == 303
    menu, editor = editor_form(client, response.location)
    assert not menu['recipe_revision_public_id']
    assert {'no_recipe': 'Ohne verknüpftes Rezept', 'no_revision': 'Noch kein gespeicherter Stand',
            'archived': 'Rezept archiviert'}[state] in editor.text
    if revision:
        assert f'value="{revision["public_id"]}"' not in editor.text
    if state == 'no_revision':
        assert 'Stand festhalten' in editor.text
    before = stored_state(admin_engine)
    assert client.post('/admin/patienten/menu?return_to=week', data=menu).status_code == 303
    assert stored_state(admin_engine)['dish_templates'] == before['dish_templates']


@pytest.mark.parametrize('stage', ('planning', 'redirect', 'editor'))
@pytest.mark.parametrize('change', ('actor', 'authz', 'location', 'version', 'archive',
                                  'recipe', 'foreign_recipe', 'recipe_archive', 'expiry', 'occupied'))
def test_each_transition_rejects_discarded_authority_without_redisplay_reads(
    admin_app, admin_engine, monkeypatch, stage, change,  # noqa: F811
):
    from cafeteria.admin import dish_template_routes, workflow_routes
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    revision = _insert_revision(admin_engine, actor, 'Originalrezept')
    template = make_template(admin_engine, recipe=int(revision['recipe_id']))
    path, source, _ = planning(client, template, area='patient')
    redirected = client.post(path, data=source)
    assert redirected.status_code == 303
    menu, _ = editor_form(client, redirected.location)
    menu.update(title='Meine <em>Eingabe</em>', description='Ursprüngliche Beschreibung',
                recipe_revision_public_id='')
    if change == 'actor':
        replacement = make_actor(admin_engine, 'Cafeteria.Admin')
        with client.session_transaction() as session:
            session['user'] = {'id': replacement.user_id, 'name': 'Andere Küche'}
            session['authz_version'] = replacement.authz_version
    elif change == 'authz':
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': actor})
        with client.session_transaction() as session:
            session['authz_version'] = _scope(admin_engine, actor).expected_authz_version
    elif change == 'location':
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('ANDERS','Anderer Standort',true)"))
    elif change in ('recipe', 'foreign_recipe'):
        other = (_foreign_revision(admin_engine, actor) if change == 'foreign_recipe'
                 else _insert_revision(admin_engine, actor, 'Anderes Rezept'))
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.dish_templates SET recipe_id=:recipe WHERE id=:id'),
                               {'id': template['id'], 'recipe': int(other['recipe_id'])})
    elif change == 'recipe_archive':
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:id'), {'id': int(revision['recipe_id'])})
    elif change == 'expiry':
        monkeypatch.setattr('cafeteria.menu_template_binding.time', lambda: 2**40)
    elif change == 'occupied':
        assert client.post('/admin/patienten/menu', data=menu).status_code == 303
    else:
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.dish_templates SET title=:title,active=:active WHERE id=:id'),
                {**template, 'title': 'Neue vertrauliche Vorlagenangabe', 'active': change != 'archive'})
    # No fresh display, recipe, catalog or source-payload readers after a rejection.
    for module, name in ((workflow_routes, '_proposal_values'), (workflow_routes, 'get_recipe'),
                         (workflow_routes, 'list_recipe_links'), (dish_template_routes.store, 'get_template'),
                         (workflow_routes, '_catalog_choices'), (workflow_routes, '_recipe_choice_page'),
                         (workflow_routes, '_master_choices')):
        monkeypatch.setattr(module, name, Mock(side_effect=AssertionError(f'Discarded context read: {name}')))
    before = stored_state(admin_engine)
    for _ in range(2):
        response = (client.post(path, data=source) if stage == 'planning' else
                    client.get(redirected.location) if stage == 'redirect' else
                    client.post('/admin/patienten/menu', data=menu))
        assert response.status_code == 409, response.text
        token = source['template_context'] if stage == 'planning' else menu['template_context']
        assert _hidden(response.text, 'template_context') == token
        assert 'Neue vertrauliche Vorlagenangabe' not in response.text
        if stage != 'planning':
            assert _hidden(response.text, 'row_version') == '0'
        if stage == 'editor':
            assert 'Meine &lt;em&gt;Eingabe&lt;/em&gt;' in response.text
            assert 'Ursprüngliche Beschreibung' in response.text
            assert _hidden(response.text, '_csrf', form_action='/admin/patienten/menu') == menu['_csrf']
    assert stored_state(admin_engine) == before


@pytest.mark.parametrize('changes', ({'week': '2026-09-01'}, {'day': '8'}, {'area': 'foreign'},
    {'area': 'staff_guest', 'meal': 'DINNER'}, {'option': 'MENU_3'}, {'area': 'staff_guest', 'day': '6'}))
def test_invalid_target_keeps_original_form_and_csrf(admin_app, admin_engine, changes):  # noqa: F811
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    path, form, _ = planning(client, template)
    for key, value in changes.items():
        form[key] = value
    before = stored_state(admin_engine)
    response = client.post(path, data=form)
    assert response.status_code == 400
    returned = Forms(response.text).forms[path]
    assert all(returned[key] == value for key, value in form.items())
    assert stored_state(admin_engine) == before


def test_native_refresh_and_occupied_target_have_separate_actions(admin_app, admin_engine):  # noqa: F811
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    path, form, _ = planning(client, template, area='patient', action='refresh')
    refreshed = client.post(path, data=form)
    assert refreshed.status_code == 200 and '>Abend</option>' in refreshed.text
    returned = Forms(refreshed.text).forms[path]
    assert returned['template_context'] == form['template_context']
    assert returned['_csrf'] == form['_csrf']
    response = client.post(path, data=returned)
    menu, _ = editor_form(client, response.location)
    assert client.post('/admin/patienten/menu', data=menu).status_code == 303
    before = stored_state(admin_engine)
    conflict = client.post(path, data=returned)
    assert conflict.status_code == 409 and 'Bereits belegt mit «Rösti»' in conflict.text
    assert 'Bestehendes Menü öffnen' in conflict.text and 'Anderes Ziel wählen' in conflict.text
    assert 'template_context=' not in conflict.text.split('Bestehendes Menü öffnen')[0].split('<a class="btn"')[-1]
    assert stored_state(admin_engine) == before


def test_legacy_recipe_context_fails_closed_and_does_not_refresh(admin_app, admin_engine):  # noqa: F811
    from cafeteria.admin.workflow_scope import bind_template_target
    from cafeteria.workflow_write_context import WriteConflictError
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    revision = _insert_revision(admin_engine, actor, 'Vorlagenrezept')
    template = make_template(admin_engine, recipe=int(revision['recipe_id']))
    _, form, _ = planning(client, template)
    with admin_app.test_request_context():
        source = read_template_context(form['template_context'], target=False)
        legacy = _sign_template_context(replace(source, recipe_active=None))
        with pytest.raises(WriteConflictError, match='veraltet'):
            bind_template_target(legacy, _scope(admin_engine, actor), WEEK, DAY, 'LUNCH', 'MENU_1')


@pytest.mark.parametrize('tamper', ('csrf', 'source_token', 'token_duplicate', 'route', 'source_profile'))
def test_planning_transport_rejects_tampering_before_business_reads(
    admin_app, admin_engine, monkeypatch, tamper,  # noqa: F811
):
    from cafeteria.admin import dish_template_routes
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    path, form, _ = planning(client, template)
    if tamper == 'csrf':
        form['_csrf'] = 'invalid'
    elif tamper == 'source_token':
        form['template_context'] += 'invalid'
    elif tamper == 'token_duplicate':
        form.add('template_context', form['template_context'])
    elif tamper == 'route':
        path = path.replace(template['public_id'], '00000000-0000-4000-8000-000000000001')
    else:
        form['source_profile'] = 'patient'
    reader = Mock(side_effect=AssertionError('Business read before original authority'))
    monkeypatch.setattr(dish_template_routes, 'lock_templates', reader)
    before = stored_state(admin_engine)
    response = client.post(path, data=form)
    assert response.status_code == (409 if tamper == 'route' else 400)
    reader.assert_not_called()
    assert stored_state(admin_engine) == before
