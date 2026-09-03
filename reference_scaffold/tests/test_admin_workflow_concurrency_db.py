from __future__ import annotations

import threading

from sqlalchemy import Engine, event, text

from cafeteria import workflow
from cafeteria.component_assignment_store import StaleItemError
from cafeteria.component_catalog_store import update_component
from cafeteria.db import active_snapshot
from cafeteria.workflow import StaleDraftError, load_draft, publish_draft, save_draft
import test_admin_workflow_db as workflow_db_support
from test_component_assignment_db import (
    CatalogDatabase,
    _assignment,
    _component,
    _item,
    _item_state,
    _links,
    _set_manual_effects,
    catalog_database,
)

import pytest
import os

DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


WEEK_START = workflow_db_support.WEEK_START
database_engine = workflow_db_support.database_engine


def test_publish_locks_week_before_snapshot_reads_against_concurrent_save(
    database_engine: Engine,
) -> None:
    """Removing the week-row lock lets save finish while publish holds an old week row."""
    actor_id = workflow_db_support._actor_id(database_engine)
    expected_version = workflow_db_support._save(
        database_engine,
        'patient',
        workflow_db_support._patient_values('Herbstküche'),
    )
    week_read = threading.Event()
    release_publish = threading.Event()
    save_lock_attempted = threading.Event()
    save_done = threading.Event()
    results: dict[str, object] = {}

    def pause_after_week_read(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if (
            threading.current_thread().name == 'workflow-publisher'
            and 'SELECT w.id, w.week_start' in statement
        ):
            week_read.set()
            if not release_publish.wait(timeout=10):
                raise AssertionError('publisher test barrier timed out')

    def observe_save_lock(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if (
            threading.current_thread().name == 'workflow-saver'
            and 'SELECT w.id, w.row_version' in statement
        ):
            save_lock_attempted.set()

    def publish() -> None:
        try:
            results['published'] = publish_draft(
                database_engine,
                'patient',
                WEEK_START,
                expected_row_version=expected_version,
                actor_id=actor_id,
                issuer_engine=database_engine,
            )
        except Exception as error:  # pragma: no cover - asserted below
            results['publish_error'] = error

    def save() -> None:
        try:
            results['saved_version'] = save_draft(
                database_engine,
                'patient',
                WEEK_START,
                expected_row_version=expected_version,
                actor_id=actor_id,
                values=workflow_db_support._patient_values('Winterküche'),
            )
        except Exception as error:  # pragma: no cover - asserted below
            results['save_error'] = error
        finally:
            save_done.set()

    event.listen(database_engine, 'after_cursor_execute', pause_after_week_read)
    event.listen(database_engine, 'before_cursor_execute', observe_save_lock)
    publisher = threading.Thread(target=publish, name='workflow-publisher')
    saver = threading.Thread(target=save, name='workflow-saver')
    try:
        publisher.start()
        assert week_read.wait(timeout=10)
        saver.start()
        assert save_lock_attempted.wait(timeout=10)
        assert not save_done.wait(timeout=1), 'save crossed publish snapshot boundary'
    finally:
        release_publish.set()
        publisher.join(timeout=10)
        saver.join(timeout=10)
        event.remove(database_engine, 'after_cursor_execute', pause_after_week_read)
        event.remove(database_engine, 'before_cursor_execute', observe_save_lock)

    assert not publisher.is_alive()
    assert not saver.is_alive()
    assert 'publish_error' not in results
    assert isinstance(results.get('save_error'), StaleDraftError)
    published = results['published']
    assert isinstance(published, dict)
    assert published['title'] == 'Herbstküche'
    assert {
        option['title']
        for day in published['days']
        for service in day['services']
        for option in service['options']
    } == {'Kartoffelgratin', 'Gemüseteller'}
    assert active_snapshot(database_engine, 'patient', '2026-09-02') == published
    current = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    assert current['title'] == 'Herbstküche'


def test_concurrent_publishes_are_serialized_as_one_revision_and_one_stale_error(
    database_engine: Engine,
) -> None:
    """Removing serialization makes both publishers allocate revision one."""
    actor_id = workflow_db_support._actor_id(database_engine)
    expected_version = workflow_db_support._save(
        database_engine,
        'patient',
        workflow_db_support._patient_values(),
    )
    initial_read_barrier = threading.Barrier(2)
    outcomes: list[object] = []

    def synchronize_initial_revision_read(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if (
            threading.current_thread().name.startswith('parallel-publisher-')
            and 'FROM cafeteria.publication_revisions r' in statement
        ):
            initial_read_barrier.wait(timeout=10)

    def publish() -> None:
        try:
            outcomes.append(
                publish_draft(
                    database_engine,
                    'patient',
                    WEEK_START,
                    expected_row_version=expected_version,
                    actor_id=actor_id,
                    issuer_engine=database_engine,
                )
            )
        except Exception as error:  # pragma: no cover - asserted below
            outcomes.append(error)

    event.listen(database_engine, 'after_cursor_execute', synchronize_initial_revision_read)
    threads = [
        threading.Thread(target=publish, name=f'parallel-publisher-{index}')
        for index in range(2)
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
    finally:
        event.remove(database_engine, 'after_cursor_execute', synchronize_initial_revision_read)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(isinstance(outcome, dict) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, StaleDraftError) for outcome in outcomes) == 1
    with database_engine.connect() as connection:
        revisions = connection.execute(
            text(
                '''
                SELECT revision_number, revision_code, count(*) OVER ()
                FROM cafeteria.publication_revisions
                '''
            )
        ).all()
    assert revisions == [(1, 'PAT-2026-KW36-R1', 1)]


@pytest.mark.parametrize('winner', ['review', 'catalog'])
def test_common_component_catalog_edit_and_review_serialize_in_both_orders(
    catalog_database: CatalogDatabase,
    winner: str,
) -> None:
    reviewed_item = _item(
        catalog_database,
        modes=('auto', 'manual', 'manual'),
        suffix=f'RACE-{winner}',
    )
    other_profile_item = _item(
        catalog_database,
        profile='staff_guest',
        modes=('auto', 'manual', 'manual'),
        suffix=f'RACE-STAFF-{winner}',
    )
    component = _component(
        catalog_database,
        'Gemeinsam alt',
        target='common',
        allergens=(('MILK', 'contains'),),
    )
    public_id = str(component['public_id'])
    reviewed_version = workflow.replace_component_links(
        catalog_database.app,
        reviewed_item.scope,
        reviewed_item.id,
        [_assignment(public_id, None)],
        reviewed_item.version,
    )
    workflow.replace_component_links(
        catalog_database.app,
        other_profile_item.scope,
        other_profile_item.id,
        [_assignment(public_id, None)],
        other_profile_item.version,
    )
    manual_before = _set_manual_effects(catalog_database, reviewed_item.id)
    token = workflow.get_component_review_token(
        catalog_database.app, reviewed_item.scope, reviewed_item.id
    )
    item_before = _item_state(catalog_database, reviewed_item.id)
    first_locked = threading.Event()
    second_attempted = threading.Event()
    release_first = threading.Event()
    second_done = threading.Event()
    results: dict[str, object] = {}

    def pause_first(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        thread_name = threading.current_thread().name
        review_hit = winner == 'review' and thread_name == 'race-review'
        catalog_hit = winner == 'catalog' and thread_name == 'race-catalog'
        if review_hit and 'review_component_lock' in statement:
            first_locked.set()
        elif catalog_hit and 'FROM cafeteria.menu_components' in statement and 'FOR UPDATE' in statement:
            first_locked.set()
        else:
            return
        if not release_first.wait(timeout=10):
            raise AssertionError('first transaction barrier timed out')

    def observe_second(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        thread_name = threading.current_thread().name
        if (
            winner == 'review'
            and thread_name == 'race-catalog'
            and 'FROM cafeteria.menu_components' in statement
            and 'FOR UPDATE' in statement
        ) or (
            winner == 'catalog'
            and thread_name == 'race-review'
            and 'review_component_lock' in statement
        ):
            second_attempted.set()

    def review() -> None:
        try:
            results['review'] = workflow.review_component(
                catalog_database.app,
                reviewed_item.scope,
                reviewed_item.id,
                token,
                reviewed_version,
            )
        except Exception as error:  # pragma: no cover - asserted below
            results['review'] = error
        finally:
            if winner == 'catalog':
                second_done.set()

    def edit_catalog() -> None:
        try:
            results['catalog'] = update_component(
                catalog_database.app,
                reviewed_item.scope,
                public_id,
                {
                    'category': 'side',
                    'name': 'Gemeinsam neu',
                    'origin_country_code': 'DE',
                    'label_codes': [],
                    'allergens': [('GLUTEN', 'may_contain')],
                },
                int(component['row_version']),
            )
        except Exception as error:  # pragma: no cover - asserted below
            results['catalog'] = error
        finally:
            if winner == 'review':
                second_done.set()

    event.listen(catalog_database.app, 'after_cursor_execute', pause_first)
    event.listen(catalog_database.app, 'before_cursor_execute', observe_second)
    first_target = review if winner == 'review' else edit_catalog
    second_target = edit_catalog if winner == 'review' else review
    first = threading.Thread(target=first_target, name=f'race-{winner}')
    second_name = 'race-catalog' if winner == 'review' else 'race-review'
    second = threading.Thread(target=second_target, name=second_name)
    try:
        first.start()
        assert first_locked.wait(timeout=10)
        second.start()
        assert second_attempted.wait(timeout=10)
        assert not second_done.wait(timeout=1), 'second transaction crossed held component lock'
    finally:
        release_first.set()
        first.join(timeout=15)
        second.join(timeout=15)
        event.remove(catalog_database.app, 'after_cursor_execute', pause_first)
        event.remove(catalog_database.app, 'before_cursor_execute', observe_second)

    assert not first.is_alive() and not second.is_alive()
    assert results['catalog'] == 2
    if winner == 'review':
        assert results['review'] == reviewed_version + 1
        assert _links(catalog_database, reviewed_item.id) == [
            (1, public_id, 'Gemeinsam alt', 1)
        ]
    else:
        assert isinstance(results['review'], StaleItemError)
        assert _item_state(catalog_database, reviewed_item.id) == item_before
    reviewed_state = _item_state(catalog_database, reviewed_item.id)
    assert reviewed_state[2] == manual_before[0]
    assert reviewed_state[4] == manual_before[2]
    assert _links(catalog_database, other_profile_item.id) == [
        (1, public_id, 'Gemeinsam alt', 1)
    ]
    with catalog_database.app.connect() as connection:
        assert workflow.review_open(connection, reviewed_item.id)
        assert workflow.review_open(connection, other_profile_item.id)
