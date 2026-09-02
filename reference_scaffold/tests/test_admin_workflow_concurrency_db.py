from __future__ import annotations

import threading

from sqlalchemy import Engine, event, text

from cafeteria.db import active_snapshot
from cafeteria.workflow import StaleDraftError, load_draft, publish_draft, save_draft
import test_admin_workflow_db as workflow_db_support

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
