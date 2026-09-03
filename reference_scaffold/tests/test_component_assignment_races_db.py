from __future__ import annotations

# ruff: noqa: F811

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.pool import NullPool

from cafeteria.component_assignment_store import (
    StaleItemError,
    assign_component,
    replace_component_links,
)
from cafeteria.component_catalog_store import update_component
from test_component_assignment_db import (
    CatalogDatabase,
    _assignment,
    _component,
    _item,
    _links,
    _row_versions,
    catalog_database,  # noqa: F401
)


def _separate_engine(database: CatalogDatabase) -> Engine:
    return create_engine(database.app.url, poolclass=NullPool, pool_pre_ping=True)


def _ordered_same_item_race(
    observer_engine: Engine,
    first_engine: Engine,
    second_engine: Engine,
    first: Callable[[], int],
    second: Callable[[], int],
) -> list[tuple[str, object]]:
    week_locked = Event()
    release = Event()
    loser_attempted = Event()
    backend_pids: dict[str, int] = {}

    def first_after(_conn, _cursor, statement, _params, _ctx, _many):
        if '/* assignment_week_lock */' in statement:
            backend_pids['winner'] = int(_cursor.connection.info.backend_pid)
            week_locked.set()
            assert release.wait(10)

    def second_before(_conn, _cursor, statement, _params, _ctx, _many):
        if '/* assignment_week_lock */' in statement:
            backend_pids['loser'] = int(_cursor.connection.info.backend_pid)
            loser_attempted.set()

    event.listen(first_engine, 'after_cursor_execute', first_after)
    event.listen(second_engine, 'before_cursor_execute', second_before)

    def result(call: Callable[[], int]) -> tuple[str, object]:
        try:
            return 'ok', call()
        except Exception as error:  # asserted by exact class below
            return 'error', error

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            winner = pool.submit(result, first)
            assert week_locked.wait(10)
            loser = pool.submit(result, second)
            assert loser_attempted.wait(10)
            try:
                blockers: list[int] = []
                with observer_engine.connect() as connection:
                    for _ in range(1_000):
                        blockers = connection.execute(
                            text('SELECT pg_blocking_pids(:pid)'),
                            {'pid': backend_pids['loser']},
                        ).scalar_one()
                        if blockers:
                            break
                assert blockers == [backend_pids['winner']]
                assert not loser.done()
            finally:
                release.set()
            return [winner.result(timeout=15), loser.result(timeout=15)]
    finally:
        event.remove(first_engine, 'after_cursor_execute', first_after)
        event.remove(second_engine, 'before_cursor_execute', second_before)


@pytest.mark.parametrize('operation', ['assign', 'replace'])
def test_same_item_races_have_one_winner_and_stale_loser_without_deadlock(
    catalog_database: CatalogDatabase, operation: str
) -> None:
    item = _item(catalog_database)
    first_engine = _separate_engine(catalog_database)
    second_engine = _separate_engine(catalog_database)
    try:
        if operation == 'assign':
            def first() -> int:
                return assign_component(
                    first_engine, item.scope, item.id, None, 'erster', item.version
                )

            def second() -> int:
                return assign_component(
                    second_engine, item.scope, item.id, None, 'zweiter', item.version
                )
        else:
            def first() -> int:
                return replace_component_links(
                    first_engine,
                    item.scope,
                    item.id,
                    [_assignment(None, 'erster')],
                    item.version,
                )

            def second() -> int:
                return replace_component_links(
                    second_engine,
                    item.scope,
                    item.id,
                    [_assignment(None, 'zweiter')],
                    item.version,
                )
        results = _ordered_same_item_race(
            catalog_database.owner, first_engine, second_engine, first, second
        )
    finally:
        first_engine.dispose()
        second_engine.dispose()
    assert results[0] == ('ok', item.version + 1)
    assert results[1][0] == 'error'
    assert isinstance(results[1][1], StaleItemError)
    assert _links(catalog_database, item.id) == [(1, None, 'erster', None)]


def _catalog_race(
    database: CatalogDatabase,
    *,
    operation: str,
    catalog_first: bool,
) -> None:
    item = _item(database)
    component = _component(database, f'Alt-{operation}-{catalog_first}')
    public_id = str(component['public_id'])
    expected_item_version = item.version
    if operation == 'unassign':
        expected_item_version = assign_component(
            database.app, item.scope, item.id, public_id, None, item.version
        )
    assign_engine = _separate_engine(database)
    catalog_engine = _separate_engine(database)
    first_locked = Event()
    release = Event()
    second_attempted = Event()
    first_engine = catalog_engine if catalog_first else assign_engine
    second_engine = assign_engine if catalog_first else catalog_engine
    def matches(statement: str, *, catalog: bool) -> bool:
        if catalog:
            return (
                'FROM cafeteria.menu_components' in statement
                and 'public_id=' in statement
                and 'FOR UPDATE' in statement
            )
        return '/* assignment_component_lock */' in statement

    def after_first(_conn, _cursor, statement, _params, _ctx, _many):
        if matches(statement, catalog=catalog_first):
            first_locked.set()
            assert release.wait(10)

    def before_second(_conn, _cursor, statement, _params, _ctx, _many):
        if matches(statement, catalog=not catalog_first):
            second_attempted.set()

    event.listen(first_engine, 'after_cursor_execute', after_first)
    event.listen(second_engine, 'before_cursor_execute', before_second)
    new_name = f'Neu-{operation}-{catalog_first}'

    def catalog_edit() -> int:
        return update_component(
            catalog_engine,
            item.scope,
            public_id,
            {
                'category': 'side',
                'name': new_name,
                'origin_country_code': 'DE',
                'label_codes': [],
                'allergens': [],
            },
            1,
        )

    def assignment_edit() -> int:
        target = [] if operation == 'unassign' else [_assignment(public_id, None)]
        return replace_component_links(
            assign_engine,
            item.scope,
            item.id,
            target,
            expected_item_version,
        )

    before_week = _row_versions(database, item, public_id)[0]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(catalog_edit if catalog_first else assignment_edit)
            assert first_locked.wait(10)
            second = pool.submit(assignment_edit if catalog_first else catalog_edit)
            assert second_attempted.wait(10)
            release.set()
            first_expected = 2 if catalog_first else expected_item_version + 1
            second_expected = expected_item_version + 1 if catalog_first else 2
            assert first.result(timeout=15) == first_expected
            assert second.result(timeout=15) == second_expected
    finally:
        event.remove(first_engine, 'after_cursor_execute', after_first)
        event.remove(second_engine, 'before_cursor_execute', before_second)
        assign_engine.dispose()
        catalog_engine.dispose()
    assert _row_versions(database, item, public_id)[0] == before_week
    links = _links(database, item.id)
    if operation == 'unassign':
        assert links == []
    elif catalog_first:
        assert links == [(1, public_id, new_name, 2)]
    else:
        assert links == [(1, public_id, str(component['name']), 1)]


@pytest.mark.parametrize('operation', ['assign', 'unassign'])
@pytest.mark.parametrize('catalog_first', [True, False])
def test_catalog_edit_assignment_races_bind_one_consistent_component_version(
    catalog_database: CatalogDatabase,
    operation: str,
    catalog_first: bool,
) -> None:
    _catalog_race(
        catalog_database, operation=operation, catalog_first=catalog_first
    )
