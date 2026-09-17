"""Week HTML shows soup/dessert once and posts an atomic course form."""
from __future__ import annotations

import secrets

from sqlalchemy import Engine, text

from cafeteria.course_store import persist_service_courses
from cafeteria.workflow_partial_store import persist_menu_item, persist_service_state
from prepared_food_fixtures import create_food, create_recipe, execute, freeze
from test_admin_workflow_routes import DAY, WEEK, _hidden, _login, _scope
from test_workflow_partial_store_db import _payload, _service_payload

pytest_plugins = ['test_admin_workflow_routes']


def _recipe(engine: Engine, user_id: int, location_id: int, name: str) -> dict:
    with engine.connect() as connection:
        authz = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user_id},
        ).scalar_one()
    ids = {'actor': user_id, 'authz': authz, 'location': location_id}
    storage = execute(
        engine,
        '''SELECT cafeteria.create_storage_location_v21(
            :actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))''',
        ids, {'code': 'COURSE_' + secrets.token_hex(3).upper(), 'name': 'Gangtestlager', 'sort_order': 1},
    )
    ids['storage'] = storage['public_id']
    food = create_food(engine, ids, name + '-zutat', unit='G')
    recipe = create_recipe(engine, ids, [food], name=name, unit='G', quantity='1')
    freeze(engine, ids, recipe)
    return recipe


def test_cafeteria_week_shows_shared_course_once(app, database_engine: Engine) -> None:
    client, user_id = _login(app, database_engine, ['Cafeteria.Admin'])
    engine = app.extensions['cafeteria_db']
    scope = _scope(database_engine, user_id, 'staff_guest')
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    recipe = _recipe(engine, user_id, scope.location_id, 'Gemüsesuppe')
    persist_service_courses(
        engine, scope, WEEK, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': recipe['public_id']},
        dessert={'state': 'not_offered'},
    )
    page = client.get(f'/admin/cafeteria?week={DAY}')
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert html.count('Suppe: Gemüsesuppe') == 1
    assert 'Kein Dessert' in html
    assert 'Gänge planen' in html
    assert 'action="/admin/cafeteria/courses"' in html
    assert 'Allergenangaben fehlen' in html
    assert 'id="course-issues"' in html
    assert 'Gänge ohne Allergenangaben' in html or 'Gang prüfen' in html
    assert 'name="recipe_search"' in html


def test_course_form_saves_atomically(app, database_engine: Engine) -> None:
    client, user_id = _login(app, database_engine, ['Cafeteria.Admin'])
    engine = app.extensions['cafeteria_db']
    scope = _scope(database_engine, user_id, 'staff_guest')
    persist_service_state(engine, scope, WEEK, DAY, 'LUNCH', _service_payload(), 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        engine, scope, WEEK, DAY, 'LUNCH',
        soup={'state': 'unplanned'}, dessert={'state': 'unplanned'}, exceptions=[],
    )
    page = client.get(f'/admin/cafeteria?week={DAY}')
    html = page.get_data(as_text=True)
    token = _hidden(html, '_csrf', form_action='/admin/cafeteria/header')
    response = client.post('/admin/cafeteria/courses', data={
        '_csrf': token, 'week': DAY, 'day': DAY, 'meal': 'LUNCH',
        'soup_state': 'not_offered', 'soup_recipe': '',
        'dessert_state': 'unplanned', 'dessert_recipe': '',
        'MENU_1_soup_state': 'inherit', 'MENU_1_soup_recipe': '',
        'MENU_1_dessert_state': 'inherit', 'MENU_1_dessert_recipe': '',
        'VEGGIE_soup_state': 'inherit', 'VEGGIE_soup_recipe': '',
        'VEGGIE_dessert_state': 'inherit', 'VEGGIE_dessert_recipe': '',
    }, follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Keine Suppe' in body
    assert 'Dessert noch nicht geplant' in body


def test_course_editor_retains_bound_recipe_outside_search_page(app, database_engine: Engine) -> None:
    client, user_id = _login(app, database_engine, ['Cafeteria.Admin'])
    engine = app.extensions['cafeteria_db']
    scope = _scope(database_engine, user_id, 'staff_guest')
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    soup = _recipe(engine, user_id, scope.location_id, 'Gemüsesuppe')
    other = _recipe(engine, user_id, scope.location_id, 'Tomatensuppe')
    persist_service_courses(
        engine, scope, WEEK, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['public_id']},
        dessert={'state': 'unplanned'},
        exceptions=[{
            'option': 'VEGGIE', 'kind': 'soup', 'state': 'planned',
            'recipe_public_id': other['public_id'],
        }],
    )
    page = client.get(f'/admin/cafeteria?week={DAY}&recipe_search=zzzz-kein-treffer')
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'name="recipe_search"' in html
    assert 'zzzz-kein-treffer' in html
    assert html.count('Weiterhin gebundene Auswahl') >= 1
    assert soup['public_id'] in html
    assert other['public_id'] in html
    assert 'Gemüsesuppe' in html
    assert 'Tomatensuppe' in html
    veggie_select = html.split('name="VEGGIE_soup_recipe"', 1)[1].split('</select>', 1)[0]
    assert 'Weiterhin gebundene Auswahl' in veggie_select
    assert other['public_id'] in veggie_select
