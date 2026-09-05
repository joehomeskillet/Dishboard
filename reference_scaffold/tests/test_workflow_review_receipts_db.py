from __future__ import annotations

# ruff: noqa: F401, F811

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import workflow
from cafeteria.component_assignment_store import StaleItemError
from cafeteria.component_catalog_store import AdminScope, ComponentNotFoundError
from cafeteria.db import active_snapshot
from cafeteria.workflow_review_context import (
    get_week_review, review_week_context, week_context_review_open_connection,
)
from cafeteria.workflow_partial_store import persist_week_header
from test_workflow_copy_store_db import _blocked_pair, _separate_engine
from test_admin_workflow_db import WEEK_START, _actor_id, _save, _staff_values
from test_component_catalog_db import CatalogDatabase, catalog_database


def _scope(database: CatalogDatabase, profile='staff_guest') -> AdminScope:
    return AdminScope(_actor_id(database.owner), database.location_id, profile)


def _items(database):
    with database.owner.connect() as connection:
        return connection.execute(text(
            'SELECT id,row_version,allergen_review_status,note FROM cafeteria.menu_items ORDER BY id'
        )).all()


def _review_item(database, scope, item_id):
    with database.owner.connect() as connection:
        version = connection.execute(text(
            'SELECT row_version FROM cafeteria.menu_items WHERE id=:id'
        ), {'id': item_id}).scalar_one()
    token = workflow.get_component_review_token(database.app, scope, item_id)
    return workflow.review_component(database.app, scope, item_id, token, version)


def _week(database):
    with database.owner.connect() as connection:
        return connection.execute(text(
            'SELECT id,row_version,title,shared_note,header_revision FROM cafeteria.menu_weeks'
        )).one()


def test_independent_item_and_context_receipts_do_not_invalidate_other_menus(catalog_database):
    db = catalog_database
    _save(db.owner, 'staff_guest', _staff_values())
    scope = _scope(db)
    first, second = _items(db)[:2]
    # A historical checked flag is not a revision-bound receipt.
    assert first.allergen_review_status == 'checked'
    assert workflow.review_open(db.app, scope, first.id)
    new_version = _review_item(db, scope, first.id)
    assert not workflow.review_open(db.app, scope, first.id)
    assert workflow.review_open(db.app, scope, second.id)
    with db.app.connect() as connection:
        receipt = connection.execute(text(
            "SELECT actor_user_id,entity_type,profile_code,details FROM cafeteria.audit_events "
            "WHERE action='workflow.menu_reviewed'"
        )).one()
    assert receipt[:3] == (scope.actor_id, 'menu_item', 'staff_guest')
    assert receipt.details['reviewed_item_row_version'] == new_version
    assert receipt.details['source_item_row_version'] == first.row_version
    assert receipt.details['submitted_token'] != receipt.details['reviewed_token']

    context = get_week_review(db.app, scope, WEEK_START)
    review_week_context(db.app, scope, WEEK_START, context['token'])
    with db.app.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_items SET title='Anderes Menü' WHERE id=:id"), {'id': second.id})
    assert get_week_review(db.app, scope, WEEK_START)['token'] == context['token']
    assert get_week_review(db.app, scope, WEEK_START)['receipt'] is not None
    assert not workflow.review_open(db.app, scope, first.id)
    with db.app.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_items SET note='Neue Notiz' WHERE id=:id"), {'id': first.id})
    assert workflow.review_open(db.app, scope, first.id)


def test_header_and_service_edits_including_revert_reject_stale_context(catalog_database):
    db = catalog_database
    _save(db.owner, 'staff_guest', _staff_values())
    scope = _scope(db)
    original = get_week_review(db.app, scope, WEEK_START)
    review_week_context(db.app, scope, WEEK_START, original['token'])
    with db.app.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_weeks SET shared_note='Neu'"))
        connection.execute(text('UPDATE cafeteria.menu_weeks SET shared_note=:old'), {'old': original['context']['shared_note']})
    changed = get_week_review(db.app, scope, WEEK_START)
    assert changed['context']['header_revision'] == original['context']['header_revision'] + 2
    assert changed['token'] != original['token'] and changed['receipt'] is None
    with pytest.raises(workflow.StaleDraftError):
        review_week_context(db.app, scope, WEEK_START, original['token'])
    review_week_context(db.app, scope, WEEK_START, changed['token'])
    with db.app.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_services SET notice='Service geändert' WHERE id=(SELECT min(id) FROM cafeteria.menu_services)"))
    latest = get_week_review(db.app, scope, WEEK_START)
    assert latest['token'] != changed['token'] and latest['receipt'] is None
    assert latest['context']['header_revision'] == changed['context']['header_revision']


def test_fully_closed_week_requires_context_review_and_retains_old_publication(catalog_database):
    db = catalog_database
    values = _staff_values()
    for day in values['days']:
        for service in day['services']:
            service.update(service_state='closed', notice='Geschlossen am ' + day['date'])
    _save(db.owner, 'staff_guest', values)
    scope = _scope(db)
    assert _items(db) == []
    assert workflow.derive_admin_status(db.app, 'staff_guest', WEEK_START) == 'review_open'

    def publish():
        return workflow.publish_draft_scoped(
            db.app, 'staff_guest', WEEK_START, expected_row_version=_week(db).row_version,
            actor_id=scope.actor_id, issuer_engine=db.owner, expected_location_id=scope.location_id,
        )

    with pytest.raises(workflow.WorkflowValidationError, match='Wochenkopf'):
        publish()
    saved = get_week_review(db.app, scope, WEEK_START)
    assert len(saved['context']['services']) == 5
    review_week_context(db.app, scope, WEEK_START, saved['token'])
    with pytest.raises(workflow.StaleDraftError, match='bereits'):
        review_week_context(db.app, scope, WEEK_START, saved['token'])
    publish()
    first_snapshot = active_snapshot(db.app, 'staff_guest', WEEK_START)
    with db.app.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_services SET notice='Neuer Schliesshinweis' WHERE id=(SELECT min(id) FROM cafeteria.menu_services)"))
    with pytest.raises(workflow.WorkflowValidationError, match='Wochenkopf'):
        publish()
    assert active_snapshot(db.app, 'staff_guest', WEEK_START) == first_snapshot
    saved = get_week_review(db.app, scope, WEEK_START)
    review_week_context(db.app, scope, WEEK_START, saved['token'])
    publish()
    assert active_snapshot(db.app, 'staff_guest', WEEK_START) != first_snapshot
    with db.app.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.publication_revisions')).scalar_one() == 2
        assert connection.execute(text('SELECT snapshot_json FROM cafeteria.publication_revisions ORDER BY id LIMIT 1')).scalar_one() == first_snapshot


def test_receipt_permissions_actor_scope_and_failure_are_atomic(catalog_database):
    db = catalog_database
    _save(db.owner, 'staff_guest', _staff_values())
    scope = _scope(db)
    first = _items(db)[0]
    token = workflow.get_component_review_token(db.app, scope, first.id)
    with pytest.raises(ComponentNotFoundError):
        workflow.review_component(db.app, AdminScope(scope.actor_id, scope.location_id, 'patient'), first.id, token, first.row_version)
    with pytest.raises(DBAPIError) as denied:
        workflow.review_component(db.app, AdminScope(1, scope.location_id, 'staff_guest'), first.id, token, first.row_version)
    assert denied.value.orig.sqlstate == '42501'
    assert _items(db)[0] == first
    _review_item(db, scope, first.id)
    with pytest.raises(StaleItemError):
        workflow.review_component(db.app, scope, first.id, token, first.row_version)
    with db.app.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE 'workflow.%'")).scalar_one() == 1
        grants = connection.execute(text("SELECT has_table_privilege('cafeteria_app','cafeteria.audit_events','INSERT'), has_table_privilege('cafeteria_app','cafeteria.audit_events','UPDATE'), has_table_privilege('cafeteria_app','cafeteria.audit_events','DELETE')")).one()
        assert grants == (False, False, False)
    for statement in (
        "INSERT INTO cafeteria.audit_events(action,entity_type) VALUES ('fake','menu_item')",
        "UPDATE cafeteria.audit_events SET action='fake' WHERE action='workflow.menu_reviewed'",
        "DELETE FROM cafeteria.audit_events WHERE action='workflow.menu_reviewed'",
    ):
        with pytest.raises(DBAPIError) as denied, db.app.begin() as connection:
            connection.execute(text(statement))
        assert denied.value.orig.sqlstate == '42501'
    with pytest.raises(DBAPIError) as immutable, db.owner.begin() as connection:
        connection.execute(text("DELETE FROM cafeteria.audit_events WHERE action='workflow.menu_reviewed'"))
    assert immutable.value.orig.sqlstate == '55000'


@pytest.mark.parametrize('winner', ['review', 'header'])
def test_week_review_and_header_save_hold_real_week_lock_in_both_orders(catalog_database, winner):
    db = catalog_database
    _save(db.owner, 'staff_guest', _staff_values())
    scope = _scope(db)
    saved = get_week_review(db.app, scope, WEEK_START)
    expected_version = _week(db).row_version
    review_engine, header_engine = _separate_engine(db), _separate_engine(db)

    def review():
        return review_week_context(review_engine, scope, WEEK_START, saved['token'])

    def header():
        return persist_week_header(header_engine, scope, WEEK_START,
                                   {'title': 'Neuer Wochenkopf', 'shared_note': ''}, expected_version)

    try:
        if winner == 'review':
            results = _blocked_pair(db, review_engine, header_engine, 'FOR UPDATE OF w',
                                    'FOR UPDATE OF w', review, header)
            assert all(result[0] == 'ok' for result in results)
        else:
            results = _blocked_pair(db, header_engine, review_engine, 'FOR UPDATE OF w',
                                    'FOR UPDATE OF w', header, review)
            assert results[0][0] == 'ok'
            assert results[1][0] == 'error' and isinstance(results[1][1], workflow.StaleDraftError)
        assert get_week_review(db.app, scope, WEEK_START)['receipt'] is None
    finally:
        review_engine.dispose()
        header_engine.dispose()
