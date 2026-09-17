"""Shared soup/dessert persist, resolve, copy independence, CSV restore."""
from __future__ import annotations

import secrets
from datetime import timedelta

import pytest
from sqlalchemy import text

from cafeteria.course_store import (
    capture_week_courses,
    effective_course,
    load_week_courses,
    persist_service_courses,
    restore_week_courses,
    unplanned,
)
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import PartialWorkflowValidationError, persist_menu_item
from prepared_food_fixtures import create_food, create_recipe, execute, freeze
from test_workflow_partial_store_db import WEEK, WorkflowDatabase, _payload, _scope

pytest_plugins = ['test_workflow_partial_store_db']


def _ids(db: WorkflowDatabase) -> dict[str, object]:
    with db.owner.connect() as connection:
        authz = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': db.actor_id},
        ).scalar_one()
    ids = {'actor': db.actor_id, 'authz': authz, 'location': db.location_id}
    storage = execute(
        db.app,
        '''SELECT cafeteria.create_storage_location_v21(
            :actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))''',
        ids, {'code': 'COURSE_' + secrets.token_hex(3).upper(), 'name': 'Gangtestlager', 'sort_order': 1},
    )
    ids['storage'] = storage['public_id']
    return ids


def _freeze_named(db: WorkflowDatabase, name: str) -> dict[str, object]:
    ids = _ids(db)
    food = create_food(db.app, ids, name + '-zutat', unit='G')
    recipe = create_recipe(db.app, ids, [food], name=name, unit='G', quantity='1')
    frozen = freeze(db.app, ids, recipe)
    return {
        'recipe_public_id': recipe['public_id'],
        'revision_public_id': frozen['public_id'],
        'title': name,
    }


def test_shared_course_once_for_two_mains(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Gemüsesuppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
    )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    shared = packed[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']
    assert shared['state'] == 'planned'
    assert shared['title'] == 'Gemüsesuppe'
    veggie = effective_course(shared, packed[(WEEK.isoformat(), 'LUNCH')]['exceptions'].get('VEGGIE', {}).get('soup'))
    menu1 = effective_course(shared, packed[(WEEK.isoformat(), 'LUNCH')]['exceptions'].get('MENU_1', {}).get('soup'))
    assert veggie['title'] == menu1['title'] == shared['title']


def test_unplanned_planned_not_offered_roundtrip(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    dessert = _freeze_named(db, 'Fruchtsalat')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'not_offered'},
        dessert={'state': 'planned', 'recipe_public_id': dessert['recipe_public_id']},
    )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    assert packed['shared']['soup']['state'] == 'not_offered'
    assert packed['shared']['dessert']['state'] == 'planned'
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'unplanned'}, dessert={'state': 'unplanned'},
    )
    again = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    assert again['shared']['soup'] == unplanned()
    assert again['shared']['dessert']['state'] == 'unplanned'


def test_variant_exception_does_not_overwrite_shared(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Tagessuppe')
    other = _freeze_named(db, 'Tomatensuppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
        exceptions=[{
            'option': 'VEGGIE', 'kind': 'soup', 'state': 'planned',
            'recipe_public_id': other['recipe_public_id'],
        }],
    )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    shared = packed['shared']['soup']
    veggie = effective_course(shared, packed['exceptions']['VEGGIE']['soup'])
    menu1 = effective_course(shared, packed['exceptions'].get('MENU_1', {}).get('soup'))
    assert veggie['title'] == 'Tomatensuppe'
    assert menu1['title'] == shared['title'] == 'Tagessuppe'


def test_not_offered_does_not_fall_back_until_reset(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Klare Suppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
        exceptions=[{'option': 'VEGGIE', 'kind': 'soup', 'state': 'not_offered'}],
    )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    veggie = effective_course(packed['shared']['soup'], packed['exceptions']['VEGGIE']['soup'])
    assert veggie['state'] == 'not_offered'
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
        exceptions=[{'option': 'VEGGIE', 'kind': 'soup', 'state': 'inherit'}],
    )
    reset = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    veggie2 = effective_course(reset['shared']['soup'], reset['exceptions'].get('VEGGIE', {}).get('soup'))
    assert veggie2['state'] == 'planned'
    assert veggie2['title'] == reset['shared']['soup']['title']


def test_cafeteria_lunch_does_not_copy_to_patient_dinner(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    cafeteria = _scope(db, 'staff_guest')
    patient = _scope(db, 'patient')
    soup = _freeze_named(db, 'Cafeteriasuppe')
    persist_menu_item(db.app, cafeteria, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(db.app, patient, WEEK, WEEK.isoformat(), 'DINNER', 'MENU_1', _payload(), 0)
    persist_service_courses(
        db.app, cafeteria, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
    )
    staff = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    sick = load_week_courses(db.app, db.location_id, WEEK, 'patient')
    assert staff[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']['state'] == 'planned'
    dinner = sick.get((WEEK.isoformat(), 'DINNER'), {'shared': {'soup': unplanned()}})
    assert dinner['shared']['soup']['state'] == 'unplanned'
    lunch = sick.get((WEEK.isoformat(), 'LUNCH'), {'shared': {'soup': unplanned()}})
    assert lunch['shared']['soup']['state'] == 'unplanned'


def test_invalid_assignment_is_rejected_without_partial_write(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Gültige Suppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    with pytest.raises(PartialWorkflowValidationError):
        persist_service_courses(
            db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
            soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
            dessert={'state': 'planned'},
        )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    assert packed['shared']['soup']['state'] == 'unplanned'
    assert packed['shared']['dessert']['state'] == 'unplanned'


def test_copy_creates_independent_assignments(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Kopiersuppe')
    other = _freeze_named(db, 'Neue Suppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'not_offered'},
        exceptions=[{'option': 'VEGGIE', 'kind': 'soup', 'state': 'not_offered'}],
    )
    with db.owner.connect() as connection:
        version = connection.execute(text(
            '''SELECT w.row_version FROM cafeteria.menu_weeks w
               JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               WHERE w.location_id=:loc AND p.code='staff_guest' AND w.week_start=:week'''
        ), {'loc': db.location_id, 'week': WEEK}).scalar_one()
    target = WEEK + timedelta(days=7)
    copy_previous_week(db.app, scope, target, 0, source_row_version=int(version))
    source = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    copied = load_week_courses(db.app, db.location_id, target, 'staff_guest')[(target.isoformat(), 'LUNCH')]
    assert copied['shared']['soup']['title'] == source['shared']['soup']['title'] == 'Kopiersuppe'
    assert copied['shared']['dessert']['state'] == 'not_offered'
    assert copied['exceptions']['VEGGIE']['soup']['state'] == 'not_offered'
    persist_service_courses(
        db.app, scope, target, target.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': other['recipe_public_id']},
        dessert={'state': 'unplanned'},
        exceptions=[],
    )
    source_again = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    assert source_again['shared']['soup']['title'] == 'Kopiersuppe'
    assert source_again['shared']['dessert']['state'] == 'not_offered'


def test_capture_restore_keeps_courses_after_item_rewrite(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Restoresuppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'not_offered'},
    )
    with db.owner.connect() as connection:
        week_id = connection.execute(text(
            '''SELECT w.id FROM cafeteria.menu_weeks w
               JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               WHERE w.location_id=:loc AND p.code='staff_guest' AND w.week_start=:week'''
        ), {'loc': db.location_id, 'week': WEEK}).scalar_one()
        captured = capture_week_courses(connection, int(week_id))
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'unplanned'}, dessert={'state': 'unplanned'}, exceptions=[],
    )
    cleared = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    assert cleared['shared']['soup']['state'] == 'unplanned'
    restore_week_courses(db.app, scope, WEEK, captured)
    restored = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    assert restored['shared']['soup']['title'] == 'Restoresuppe'
    assert restored['shared']['dessert']['state'] == 'not_offered'
