"""Shared soup/dessert persist, resolve, copy independence, CSV restore."""
from __future__ import annotations

import logging
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy import text

from cafeteria import course_store
from cafeteria.course_store import (
    capture_week_courses,
    course_issue_flags,
    effective_course,
    load_week_courses,
    persist_service_courses,
    restore_week_courses,
    summarize_course_issues,
    unplanned,
)
from cafeteria.workflow import (
    WorkflowValidationError,
    _draft_values,
    import_draft,
    load_draft,
    validate_publication_fit,
)
from cafeteria.workflow_partial_store import PartialWorkflowConflictError
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import PartialWorkflowValidationError, persist_menu_item
from prepared_food_fixtures import create_food, create_recipe, execute, freeze
from review_support import write_expectations
from test_admin_workflow_db import _staff_values
from test_admin_workflow_routes import app as app  # noqa: F401
from test_admin_workflow_routes import database_engine as database_engine  # noqa: F401
from test_workflow_partial_store_db import WEEK, WorkflowDatabase, _payload, _scope
from test_workflow_partial_store_db import workflow_database as workflow_database  # noqa: F401


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


def test_new_inactive_course_recipe_binding_is_rejected_without_disclosure(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Archivierte Suppe')
    persist_menu_item(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0,
    )
    with db.owner.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.recipes SET active=false WHERE public_id=:recipe'),
            {'recipe': soup['recipe_public_id']},
        )

    with pytest.raises(PartialWorkflowValidationError) as caught:
        persist_service_courses(
            db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
            soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
            dessert={'state': 'unplanned'},
            soup_row_version=0,
            dessert_row_version=0,
        )

    assert str(caught.value) == 'Rezeptangabe ist ungültig oder nicht zugänglich.'
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    assert packed[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']['state'] == 'unplanned'


def test_existing_inactive_course_recipe_binding_can_be_saved_unchanged(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Retained Suppe')
    persist_menu_item(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0,
    )
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
        soup_row_version=0,
        dessert_row_version=0,
    )
    before = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    soup_version = int(before[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']['row_version'])
    with db.owner.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.recipes SET active=false WHERE public_id=:recipe'),
            {'recipe': soup['recipe_public_id']},
        )

    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
        soup_row_version=soup_version,
        dessert_row_version=0,
    )

    after = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    assert after[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']['title'] == 'Retained Suppe'


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


def test_shared_course_with_two_problems_counted_once(workflow_database: WorkflowDatabase) -> None:
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
    flags = course_issue_flags(shared)
    assert flags['missing_allergens'] is True
    assert flags['missing_nutrition'] is True
    summary = summarize_course_issues(packed)
    assert summary['affected_assignments'] == 1
    assert summary['missing_allergens'] == 1
    assert summary['missing_nutrition'] == 1
    assert len(summary['items']) == 1
    assert summary['items'][0]['kind'] == 'soup'
    assert summary['items'][0]['scope'] == 'shared'
    assert summary['items'][0]['problems'] == ('missing_allergens', 'missing_nutrition')


def test_missing_allergens_do_not_invent_positive_label_or_auto_review(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'Gemüsesuppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
    )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    shared = packed[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']
    flags = course_issue_flags(shared)
    assert flags['positive_labels'] == ()
    assert flags['allergen_review_status'] == 'not_checked'
    assert shared['allergen_review_status'] == 'not_checked'
    summary = summarize_course_issues(packed)
    assert summary['items'][0]['positive_labels'] == ()
    assert summary['items'][0]['allergen_review_status'] == 'not_checked'
    invented = course_issue_flags({
        'state': 'planned', 'title': 'Gemüsesuppe', 'allergens': None, 'labels': None,
        'nutrition': None,
    })
    assert invented['positive_labels'] == ()
    assert invented['allergen_review_status'] == 'not_checked'
    assert invented['missing_allergens'] is True


def test_inaccessible_csv_course_uuid_rolls_back_draft_and_earlier_days(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    original = _freeze_named(db, 'AlteSuppe')
    replacement = _freeze_named(db, 'NeueSuppe')
    monday = WEEK.isoformat()
    tuesday = (WEEK + timedelta(days=1)).isoformat()
    persist_menu_item(db.app, scope, WEEK, monday, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(db.app, scope, WEEK, tuesday, 'LUNCH', 'MENU_1', _payload(title='Dienstag', staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, monday, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': original['recipe_public_id']},
        dessert={'state': 'unplanned'},
    )
    with db.owner.connect() as connection:
        version = connection.execute(text(
            '''SELECT w.row_version FROM cafeteria.menu_weeks w
               JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               WHERE w.location_id=:loc AND p.code='staff_guest' AND w.week_start=:week'''
        ), {'loc': db.location_id, 'week': WEEK}).scalar_one()
    csv_courses = {
        (monday, 'LUNCH'): {
            'soup': {
                'state': 'planned', 'recipe_public_id': replacement['recipe_public_id'],
                'line': 2, 'field': 'soup',
            },
            'dessert': {'state': 'unplanned', 'line': 2, 'field': 'dessert'},
            'exceptions': [],
        },
        (tuesday, 'LUNCH'): {
            'soup': {
                'state': 'planned',
                'recipe_public_id': '00000000-0000-4000-8000-000000000099',
                'line': 4, 'field': 'soup',
            },
            'dessert': {'state': 'unplanned', 'line': 4, 'field': 'dessert'},
            'exceptions': [],
        },
    }
    with pytest.raises(WorkflowValidationError, match='Zeile 4: Rezeptangabe ist ungültig oder nicht zugänglich'):
        import_draft(
            db.app, 'staff_guest', WEEK,
            expected_row_version=int(version),
            actor_id=db.actor_id,
            values=_staff_values(title='Import darf nicht bleiben'),
            csv_courses=csv_courses,
            **write_expectations(db.app, db.actor_id),
        )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    assert packed[(monday, 'LUNCH')]['shared']['soup']['title'] == 'AlteSuppe'
    tuesday_block = packed.get((tuesday, 'LUNCH'), {'shared': {'soup': unplanned()}})
    assert tuesday_block['shared']['soup']['state'] == 'unplanned'
    draft = load_draft(
        db.app, 'staff_guest', WEEK, actor_id=db.actor_id, **write_expectations(db.app, db.actor_id),
    )
    assert draft['title'] != 'Import darf nicht bleiben'
    monday_title = draft['days'][0]['services'][0]['options'][0]['title']
    assert monday_title == 'Rindsgeschnetzeltes'

def test_schema3_import_captures_courses_after_week_lock_blocks_concurrent_writer(
    workflow_database: WorkflowDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    soup = _freeze_named(db, 'ErfassSuppe')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['recipe_public_id']},
        dessert={'state': 'unplanned'},
    )
    with db.owner.connect() as connection:
        week_id, version = connection.execute(text(
            '''SELECT w.id, w.row_version FROM cafeteria.menu_weeks w
               JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               WHERE w.location_id=:loc AND p.code='staff_guest' AND w.week_start=:week'''
        ), {'loc': db.location_id, 'week': WEEK}).one()
    capture_started = Event()
    release_capture = Event()
    original_capture = capture_week_courses

    def spy_capture(connection, week_id):
        capture_started.set()
        assert release_capture.wait(timeout=10), 'Gang-Erfassung wurde nicht freigegeben.'
        return original_capture(connection, week_id)

    monkeypatch.setattr(course_store, 'capture_week_courses', spy_capture)

    def run_import() -> int:
        return import_draft(
            db.app, 'staff_guest', WEEK,
            expected_row_version=int(version),
            actor_id=db.actor_id,
            values=_staff_values(title='Schema-3-Import'),
            **write_expectations(db.app, db.actor_id),
        )

    writer_started = Event()
    writer_pid: list[int] = []

    def concurrent_week_writer() -> None:
        with db.owner.begin() as connection:
            writer_pid.append(int(connection.execute(text('SELECT pg_backend_pid()')).scalar_one()))
            writer_started.set()
            connection.execute(text(
                'UPDATE cafeteria.menu_weeks SET title=title WHERE id=:week RETURNING id'
            ), {'week': int(week_id)}).scalar_one()

    with ThreadPoolExecutor(max_workers=2) as pool:
        import_future = pool.submit(run_import)
        assert capture_started.wait(timeout=10), 'Gang-Erfassung wurde nicht erreicht.'
        try:
            writer_future = pool.submit(concurrent_week_writer)
            assert writer_started.wait(timeout=10), 'Paralleler Schreiber wurde nicht gestartet.'
            deadline = monotonic() + 10
            wait_event = None
            while monotonic() < deadline:
                with db.owner.connect() as connection:
                    wait_event = connection.execute(text(
                        '''SELECT wait_event_type || ':' || wait_event
                           FROM pg_stat_activity WHERE pid=:pid'''
                    ), {'pid': writer_pid[0]}).scalar_one_or_none()
                if wait_event and wait_event.startswith('Lock:'):
                    break
                sleep(0.02)
            assert wait_event and wait_event.startswith('Lock:'), wait_event
        finally:
            release_capture.set()
        import_future.result(timeout=20)
        writer_future.result(timeout=20)


def test_shared_course_rejects_delete_reinsert_aba(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    first = _freeze_named(db, 'ABA-Suppe A')
    second = _freeze_named(db, 'ABA-Suppe B')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': first['recipe_public_id']},
        dessert={'state': 'unplanned'},
    )
    loaded = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    stale = loaded['shared']['soup']

    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'unplanned', 'public_id': stale['public_id']},
        dessert={'state': 'unplanned', 'public_id': ''},
        soup_row_version=int(stale['row_version']), dessert_row_version=0,
    )
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': second['recipe_public_id'], 'public_id': ''},
        dessert={'state': 'unplanned', 'public_id': ''},
        soup_row_version=0, dessert_row_version=0,
    )
    replacement = load_week_courses(
        db.app, db.location_id, WEEK, 'staff_guest',
    )[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']

    with pytest.raises(PartialWorkflowConflictError, match='Suppe wurde zwischenzeitlich geändert'):
        persist_service_courses(
            db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
            soup={
                'state': 'planned', 'recipe_public_id': first['recipe_public_id'],
                'public_id': stale['public_id'],
            },
            dessert={'state': 'unplanned', 'public_id': ''},
            soup_row_version=int(stale['row_version']), dessert_row_version=0,
        )
    with pytest.raises(PartialWorkflowConflictError, match='Suppe wurde zwischenzeitlich geändert'):
        persist_service_courses(
            db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
            soup={'state': 'not_offered', 'public_id': ''},
            dessert={'state': 'unplanned', 'public_id': ''},
            soup_row_version=int(replacement['row_version']), dessert_row_version=0,
        )
    with pytest.raises(PartialWorkflowConflictError, match='Suppe wurde zwischenzeitlich geändert'):
        persist_service_courses(
            db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
            soup={'state': 'planned', 'recipe_public_id': 'manipuliert', 'public_id': ''},
            dessert={'state': 'unplanned', 'public_id': ''},
            soup_row_version=int(replacement['row_version']), dessert_row_version=0,
        )
    current = load_week_courses(
        db.app, db.location_id, WEEK, 'staff_guest',
    )[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']
    assert current['public_id'] == replacement['public_id']
    assert current['title'] == 'ABA-Suppe B'


def test_course_exception_rejects_delete_reinsert_aba(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    first = _freeze_named(db, 'ABA-Ausnahme A')
    second = _freeze_named(db, 'ABA-Ausnahme B')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'unplanned'}, dessert={'state': 'unplanned'},
        exceptions=[{
            'option': 'MENU_1', 'kind': 'soup', 'state': 'planned',
            'recipe_public_id': first['recipe_public_id'],
        }],
    )
    loaded = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')[(WEEK.isoformat(), 'LUNCH')]
    stale = loaded['exceptions']['MENU_1']['soup']

    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'unplanned', 'public_id': ''}, dessert={'state': 'unplanned', 'public_id': ''},
        exceptions=[{
            'option': 'MENU_1', 'kind': 'soup', 'state': 'inherit',
            'row_version': stale['row_version'], 'public_id': stale['public_id'],
        }],
        soup_row_version=0, dessert_row_version=0,
    )
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'unplanned', 'public_id': ''}, dessert={'state': 'unplanned', 'public_id': ''},
        exceptions=[{
            'option': 'MENU_1', 'kind': 'soup', 'state': 'planned',
            'recipe_public_id': second['recipe_public_id'], 'row_version': 0, 'public_id': '',
        }],
        soup_row_version=0, dessert_row_version=0,
    )
    replacement = load_week_courses(
        db.app, db.location_id, WEEK, 'staff_guest',
    )[(WEEK.isoformat(), 'LUNCH')]['exceptions']['MENU_1']['soup']

    with pytest.raises(PartialWorkflowConflictError, match='Suppe wurde zwischenzeitlich geändert'):
        persist_service_courses(
            db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
            soup={'state': 'unplanned', 'public_id': ''}, dessert={'state': 'unplanned', 'public_id': ''},
            exceptions=[{
                'option': 'MENU_1', 'kind': 'soup', 'state': 'planned',
                'recipe_public_id': first['recipe_public_id'],
                'row_version': stale['row_version'], 'public_id': stale['public_id'],
            }],
            soup_row_version=0, dessert_row_version=0,
        )
    current = load_week_courses(
        db.app, db.location_id, WEEK, 'staff_guest',
    )[(WEEK.isoformat(), 'LUNCH')]['exceptions']['MENU_1']['soup']
    assert current['public_id'] == replacement['public_id']
    assert current['title'] == 'ABA-Ausnahme B'


def test_concurrent_course_writes_second_gets_stale_conflict(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    first = _freeze_named(db, 'KonkurrenzSuppeA')
    second = _freeze_named(db, 'KonkurrenzSuppeB')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': first['recipe_public_id']},
        dessert={'state': 'unplanned'},
        soup_row_version=0,
        dessert_row_version=0,
    )
    packed = load_week_courses(db.app, db.location_id, WEEK, 'staff_guest')
    soup_version = int(packed[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']['row_version'])
    soup_public_id = str(packed[(WEEK.isoformat(), 'LUNCH')]['shared']['soup']['public_id'])
    outcomes: list[str] = []

    def write(recipe: dict[str, object]) -> None:
        try:
            persist_service_courses(
                db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH',
                soup={
                    'state': 'planned', 'recipe_public_id': recipe['recipe_public_id'],
                    'public_id': soup_public_id,
                },
                dessert={'state': 'unplanned', 'public_id': ''},
                soup_row_version=soup_version,
                dessert_row_version=0,
            )
            outcomes.append('ok')
        except PartialWorkflowConflictError:
            outcomes.append('stale')

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, first), pool.submit(write, second)]
        for future in futures:
            future.result()
    assert sorted(outcomes) == ['ok', 'stale']


def test_publication_rejects_planned_course_without_title(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    draft = load_draft(
        db.app, 'staff_guest', WEEK, actor_id=db.actor_id, **write_expectations(db.app, db.actor_id),
    )
    service = draft['days'][0]['services'][0]
    service['shared_courses'] = {
        'soup': {'state': 'planned', 'title': ''},
        'dessert': {'state': 'unplanned'},
    }
    service['course_exceptions'] = {}
    with pytest.raises(WorkflowValidationError, match='Titel fehlt'):
        validate_publication_fit('staff_guest', _draft_values(draft), draft=draft)


def test_snapshot_course_passes_allergens() -> None:
    from cafeteria.course_store import snapshot_course
    assert snapshot_course({'state': 'not_offered'}) == {'state': 'not_offered', 'title': ''}
    assert snapshot_course({
        'state': 'planned', 'title': 'Test',
        'allergens': [{'code': 'MILK'}], 'labels': [{'code': 'VEGAN'}], 'nutrition': {'kcal': 100}
    }) == {
        'state': 'planned', 'title': 'Test',
        'allergens': [{'code': 'MILK'}], 'labels': [{'code': 'VEGAN'}], 'nutrition': {'kcal': 100}
    }



def test_defektes_snapshot_json_loggt(caplog) -> None:
    from cafeteria.course_store import _flags_from_snapshot

    caplog.set_level(logging.WARNING, logger='cafeteria.course_store')
    res = _flags_from_snapshot('{defekt', {'recipe_public_id': '1234'})
    assert res == {'allergens': None, 'labels': None, 'nutrition': None}
    assert 'Defektes Snapshot-JSON für Rezept/Revision 1234' in caplog.text


def test_defektes_snapshot_json_loggt_ohne_app_kontext(caplog) -> None:
    from cafeteria.course_store import _flags_from_snapshot

    caplog.set_level(logging.WARNING, logger='cafeteria.course_store')
    res = _flags_from_snapshot('{defekt', {'recipe_public_id': '5678'})
    assert res == {'allergens': None, 'labels': None, 'nutrition': None}
    assert 'Defektes Snapshot-JSON für Rezept/Revision 5678' in caplog.text
