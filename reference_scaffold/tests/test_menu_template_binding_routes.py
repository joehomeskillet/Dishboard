"""Signed source -> target -> editor -> save transitions keep the original authority."""
from dataclasses import asdict
from urllib.parse import urlencode

import pytest
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from cafeteria.admin.workflow_scope import (
    bind_template_target, issue_template_source, read_template_context,
)
from cafeteria.workflow_write_context import WriteConflictError
from test_admin_workflow_routes import DAY, WEEK, _hidden, _login, _menu_form, _scope
from test_menu_template_binding_db import make_template, stored_state
from test_rendered_ui import admin_app, admin_engine  # noqa: F401
from test_menu_recipe_selection_browser import _foreign_revision, _insert_revision
from test_master_data_db import make_actor


def proposal(app, engine, actor, template, family='patienten'):
    scope = _scope(engine, actor, 'patient' if family == 'patienten' else 'staff_guest')
    with app.test_request_context():
        source = issue_template_source(scope, template['public_id'])
        token = bind_template_target(source, scope, WEEK, DAY, 'LUNCH', 'MENU_1')
    return source, token, f'/admin/{family}/menu?' + urlencode({
        'week': DAY, 'day': DAY, 'meal': 'LUNCH', 'option': 'MENU_1',
        'template': template['public_id'], 'template_context': token,
    })


def proposal_form(client, url, token, template, family='patienten'):
    response = client.get(url)
    assert response.status_code == 200
    form = _menu_form(_csrf=_hidden(response.text, '_csrf', form_action=f'/admin/{family}/menu'),
        dish_template_public_id=template['public_id'], template_context=token,
        component_public_id='', component_text='Rösti', recipe_revision_public_id='',
        origin_ingredient='Kartoffel', origin_country_code='CH')
    if family == 'cafeteria':
        form.update(internal_chf='9.50', external_chf='14.50')
    return form


@pytest.mark.parametrize('family', ('patienten', 'cafeteria'))
def test_original_context_roundtrip_and_duplicate_submission(admin_app, admin_engine, family):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    before = stored_state(admin_engine)
    source, token, url = proposal(admin_app, admin_engine, actor, template, family)
    with admin_app.test_request_context():
        source_data = asdict(read_template_context(source, target=False))
        target_data = asdict(read_template_context(token, target=True))
    assert {key: target_data[key] for key in source_data if source_data[key] is not None} == {
        key: value for key, value in source_data.items() if value is not None}
    assert 'workflow-csrf' not in source and '_csrf' not in source_data and '_csrf' not in target_data
    form = proposal_form(client, url, token, template, family)
    assert stored_state(admin_engine) == before
    action = f'/admin/{family}/menu'
    assert client.post(action, data=form).status_code == 303
    before = stored_state(admin_engine)
    conflict = client.post(action, data=form)
    assert conflict.status_code == 409
    assert _hidden(conflict.text, 'row_version') == '0'
    assert _hidden(conflict.text, 'template_context') == token
    assert _hidden(conflict.text, '_csrf', form_action=action) == form['_csrf']
    assert 'Bestehendes Menü öffnen' in conflict.text
    assert client.post(action, data=form).status_code == 409
    assert stored_state(admin_engine) == before
    week = client.get(f'/admin/{family}?week={DAY}')
    assert 'Aus Vorlage «Rösti»' in week.text


@pytest.mark.parametrize('stage', ('source', 'target', 'editor'))
@pytest.mark.parametrize('change', ('version', 'archive', 'authz'))
def test_transition_conflicts_keep_source_expectations(admin_app, admin_engine, stage, change):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    source, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template) if stage == 'editor' else None
    with admin_engine.begin() as connection:
        if change == 'authz':
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': actor})
        else:
            connection.execute(text('UPDATE cafeteria.dish_templates SET title=:title,active=:active WHERE id=:id'),
                               {**template, 'title': 'Geändert', 'active': change != 'archive'})
    # Emulate a refreshed live session while keeping the original source/form expectations.
    if change == 'authz':
        current = _scope(admin_engine, actor)
        with client.session_transaction() as session:
            session['authz_version'] = current.expected_authz_version
    before = stored_state(admin_engine)
    if stage == 'source':
        with admin_app.test_request_context(), pytest.raises(WriteConflictError):
            bind_template_target(source, _scope(admin_engine, actor), WEEK, DAY, 'LUNCH', 'MENU_1')
    else:
        response = client.post('/admin/patienten/menu', data=form) if form else client.get(url)
        assert response.status_code == 409
        assert _hidden(response.text, 'row_version') == '0'
        assert _hidden(response.text, 'template_context') == token
        if form:
            assert _hidden(response.text, '_csrf', form_action='/admin/patienten/menu') == form['_csrf']
    assert stored_state(admin_engine) == before


@pytest.mark.parametrize('change', ('token_removed', 'token_changed', 'template', 'day', 'mode', 'detach'))
def test_final_form_cannot_change_proposal_authority(admin_app, admin_engine, change):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    _, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template)
    if change == 'token_removed':
        form.pop('template_context')
    elif change == 'token_changed':
        form['template_context'] += 'x'
    else:
        form.update({'template': {'dish_template_public_id': make_template(admin_engine)['public_id']},
                     'day': {'day': '2026-09-01'}, 'mode': {'row_version': '1'},
                     'detach': {'dish_template_detach': '1'}}[change])
    before = stored_state(admin_engine)
    response = client.post('/admin/patienten/menu', data=form)
    assert response.status_code == (400 if change.startswith('token_') else 409)
    if response.status_code == 409:
        assert _hidden(response.text, 'template_context') == token
        assert _hidden(response.text, 'row_version') == '0'
        assert _hidden(response.text, 'day') == DAY
    assert stored_state(admin_engine) == before


def test_validation_redisplay_keeps_signature_and_values(admin_app, admin_engine):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    _, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template)
    form.update(title='', description='Noch nicht gespeichert')
    before = stored_state(admin_engine)
    response = client.post('/admin/patienten/menu', data=form)
    assert response.status_code == 400
    assert _hidden(response.text, '_csrf', form_action='/admin/patienten/menu') == form['_csrf']
    assert _hidden(response.text, 'template_context') == token
    assert 'Noch nicht gespeichert' in response.text
    assert stored_state(admin_engine) == before


def test_bare_template_and_duplicate_fields_are_rejected(admin_app, admin_engine):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    _, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template)
    bare = f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1&template={template["public_id"]}'
    assert client.get(bare).status_code == 400
    duplicate = MultiDict(form)
    duplicate.add('dish_template_public_id', template['public_id'])
    before = stored_state(admin_engine)
    assert client.post('/admin/patienten/menu', data=duplicate).status_code == 400
    assert stored_state(admin_engine) == before


@pytest.mark.parametrize('stage', ('source', 'target', 'editor'))
@pytest.mark.parametrize('change', ('actor', 'location', 'expired', 'recipe', 'slot'))
def test_other_original_transitions_are_conflicts(admin_app, admin_engine, monkeypatch, stage, change):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    source, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template)
    current_actor = actor
    if change == 'actor':
        replacement = make_actor(admin_engine, 'Cafeteria.Admin')
        current_actor = replacement.user_id
        with client.session_transaction() as session:
            session['user'] = {'id': replacement.user_id, 'name': 'Andere Küche'}
            session['authz_version'] = replacement.authz_version
    elif change == 'location':
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEU','Neues Haus',true)"))
    elif change == 'expired':
        monkeypatch.setattr('cafeteria.menu_template_binding.time', lambda: 2**40)
    elif change == 'recipe':
        recipe = _insert_revision(admin_engine, actor, 'Neue Zuordnung')
        with admin_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.dish_templates SET recipe_id=:recipe WHERE id=:id'),
                               {'id': template['id'], 'recipe': int(recipe['recipe_id'])})
    else:
        assert client.post('/admin/patienten/menu', data=form).status_code == 303
    before = stored_state(admin_engine)
    if stage == 'source':
        with admin_app.test_request_context(), pytest.raises(WriteConflictError):
            bind_template_target(source, _scope(admin_engine, current_actor), WEEK, DAY, 'LUNCH', 'MENU_1')
    else:
        response = client.post('/admin/patienten/menu', data=form) if stage == 'editor' else client.get(url)
        assert response.status_code == 409
        assert _hidden(response.text, 'template_context') == token
        assert _hidden(response.text, 'row_version') == '0'
        if stage == 'editor':
            assert _hidden(response.text, '_csrf', form_action='/admin/patienten/menu') == form['_csrf']
    assert stored_state(admin_engine) == before


def test_recipe_archived_after_proposal_and_foreign_template_are_rejected(admin_app, admin_engine):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    revision = _insert_revision(admin_engine, actor, 'Vorlagenrezept')
    template = make_template(admin_engine, recipe=int(revision['recipe_id']))
    _, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template)
    form['recipe_revision_public_id'] = revision['public_id']
    with admin_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:id'), {'id': int(revision['recipe_id'])})
    before = stored_state(admin_engine)
    response = client.post('/admin/patienten/menu', data=form)
    assert response.status_code == 409
    assert revision['public_id'] in response.text
    assert stored_state(admin_engine) == before
    foreign = _foreign_revision(admin_engine, actor)
    inaccessible = make_template(admin_engine, recipe=int(foreign['recipe_id']))
    normal = client.get(f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    csrf = _hidden(normal.text, '_csrf', form_action='/admin/patienten/menu')
    before = stored_state(admin_engine)
    assert client.post('/admin/patienten/menu', data=_menu_form(_csrf=csrf,
        dish_template_public_id=inaccessible['public_id'])).status_code == 404
    assert stored_state(admin_engine) == before


@pytest.mark.parametrize('field,value', (('day','2026-09-01'), ('option','VEGGIE'), ('meal','DINNER'), ('week','2026-09-07')))
def test_get_cannot_change_signed_target(admin_app, admin_engine, field, value):  # noqa: F811
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    _, token, url = proposal(admin_app, admin_engine, actor, template)
    original = {'day': DAY, 'option': 'MENU_1', 'meal': 'LUNCH', 'week': DAY}
    url = url.replace(f'{field}={original[field]}', f'{field}={value}')
    if field == 'week':
        url = url.replace(f'day={DAY}', 'day=2026-09-07')
    before = stored_state(admin_engine)
    response = client.get(url)
    assert response.status_code == 409
    assert _hidden(response.text, 'template_context') == token
    for name, expected in original.items():
        assert _hidden(response.text, name) == expected
    assert stored_state(admin_engine) == before
