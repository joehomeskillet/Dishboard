from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, local

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from cafeteria.component_catalog_store import (
    ComponentConflictError,
    StaleComponentError,
    archive_component,
    create_component,
    find_components,
    get_component,
    unarchive_component,
    update_component,
)
from test_component_catalog_db import CatalogDatabase, _scope, catalog_database


Operation = Callable[[], object]
Outcome = tuple[object | None, Exception | None]
_INSERT_MARKER = 'INSERT INTO cafeteria.menu_components'
_LOCK_MARKER = 'SELECT id, active, row_version, category, name, origin_country_code'


def _run_ordered_race(
    engine: Engine,
    operations: tuple[Operation, Operation],
    winner: int,
    statement_marker: str,
) -> tuple[Outcome, Outcome]:
    start = Barrier(2)
    loser_waiting = Event()
    winner_finished = Event()
    actor = local()

    def hold_loser(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if getattr(actor, 'index', None) != 1 - winner or statement_marker not in statement:
            return
        loser_waiting.set()
        assert winner_finished.wait(timeout=10), 'winner did not finish while loser was held'

    def invoke(index: int) -> Outcome:
        actor.index = index
        try:
            start.wait(timeout=10)
            if index == winner:
                assert loser_waiting.wait(timeout=10), 'loser did not reach mutation statement'
            return operations[index](), None
        except Exception as error:
            return None, error
        finally:
            if index == winner:
                winner_finished.set()

    event.listen(engine, 'before_cursor_execute', hold_loser)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(invoke, index) for index in range(2)]
            return futures[0].result(timeout=15), futures[1].result(timeout=15)
    finally:
        event.remove(engine, 'before_cursor_execute', hold_loser)


def _assert_expected_outcomes(
    outcomes: tuple[Outcome, Outcome],
    winner: int,
    winner_value: object,
    loser_error: type[Exception],
) -> None:
    assert outcomes[winner] == (winner_value, None)
    assert outcomes[1 - winner][0] is None
    error = outcomes[1 - winner][1]
    assert isinstance(error, loser_error)
    assert getattr(getattr(error, 'orig', None), 'sqlstate', None) != '40P01'


def _component_state(
    public_id: str,
    *,
    category: str,
    name: str,
    origin: str | None,
    active: bool,
    version: int,
    label: tuple[str, str],
    allergen: tuple[str, str, str],
) -> dict[str, object]:
    return {
        'public_id': public_id,
        'profile_scope': 'patient',
        'category': category,
        'name': name,
        'origin_country_code': origin,
        'active': active,
        'row_version': version,
        'usage_count': 0,
        'labels': [{'code': label[0], 'name': label[1]}],
        'allergens': [
            {'code': allergen[0], 'name': allergen[1], 'presence': allergen[2]}
        ],
    }


@pytest.mark.parametrize('winner', [0, 1])
def test_create_race_is_atomic_in_both_winner_orders(
    catalog_database: CatalogDatabase,
    winner: int,
) -> None:
    candidates = (
        ('side', 'CH', ('VEGAN',), (('MILK', 'contains'),)),
        ('meat', 'DE', ('GLUTEN_FREE',), (('EGGS', 'may_contain'),)),
    )
    operations = tuple(
        lambda candidate=candidate: create_component(
            catalog_database.app,
            _scope(catalog_database),
            candidate[0],
            'Gleicher Racename',
            candidate[1],
            'current',
            candidate[2],
            candidate[3],
        )
        for candidate in candidates
    )
    outcomes = _run_ordered_race(catalog_database.app, operations, winner, _INSERT_MARKER)

    winner_result = outcomes[winner][0]
    assert isinstance(winner_result, dict)
    _assert_expected_outcomes(outcomes, winner, winner_result, ComponentConflictError)
    public_id = str(winner_result['public_id'])
    expected = _component_state(
        public_id,
        category=candidates[winner][0],
        name='Gleicher Racename',
        origin=candidates[winner][1],
        active=True,
        version=1,
        label=('VEGAN', 'Vegan') if winner == 0 else ('GLUTEN_FREE', 'Glutenfrei'),
        allergen=('MILK', 'Milch', 'contains') if winner == 0 else ('EGGS', 'Eier', 'may_contain'),
    )
    assert winner_result == expected
    assert find_components(catalog_database.app, _scope(catalog_database), '', None, True) == [expected]


@pytest.mark.parametrize('winner', [0, 1])
def test_update_race_is_atomic_in_both_winner_orders(
    catalog_database: CatalogDatabase,
    winner: int,
) -> None:
    component = create_component(
        catalog_database.app, _scope(catalog_database), 'side', 'Update Race', 'CH',
        'current', (), (),
    )
    public_id = str(component['public_id'])
    candidates = (
        ('Sieger A', ('VEGAN',), (('MILK', 'contains'),)),
        ('Sieger B', ('GLUTEN_FREE',), (('EGGS', 'may_contain'),)),
    )
    operations = tuple(
        lambda candidate=candidate: update_component(
            catalog_database.app,
            _scope(catalog_database),
            public_id,
            {
                'category': 'side',
                'name': candidate[0],
                'origin_country_code': 'CH',
                'label_codes': candidate[1],
                'allergens': candidate[2],
            },
            1,
        )
        for candidate in candidates
    )
    outcomes = _run_ordered_race(catalog_database.app, operations, winner, _LOCK_MARKER)

    _assert_expected_outcomes(outcomes, winner, 2, StaleComponentError)
    expected = _component_state(
        public_id,
        category='side',
        name=candidates[winner][0],
        origin='CH',
        active=True,
        version=2,
        label=('VEGAN', 'Vegan') if winner == 0 else ('GLUTEN_FREE', 'Glutenfrei'),
        allergen=('MILK', 'Milch', 'contains') if winner == 0 else ('EGGS', 'Eier', 'may_contain'),
    )
    assert get_component(catalog_database.app, _scope(catalog_database), public_id) == expected


@pytest.mark.parametrize('winner', [0, 1])
def test_update_archive_race_is_atomic_in_both_winner_orders(
    catalog_database: CatalogDatabase,
    winner: int,
) -> None:
    component = create_component(
        catalog_database.app, _scope(catalog_database), 'side', 'Archive Race', 'CH',
        'current', ('VEGAN',), (('MILK', 'contains'),),
    )
    public_id = str(component['public_id'])
    updated_payload = {
        'category': 'meat',
        'name': 'Archive Race Aktualisiert',
        'origin_country_code': 'DE',
        'label_codes': ('GLUTEN_FREE',),
        'allergens': (('EGGS', 'may_contain'),),
    }
    operations = (
        lambda: update_component(
            catalog_database.app, _scope(catalog_database), public_id, updated_payload, 1,
        ),
        lambda: archive_component(catalog_database.app, _scope(catalog_database), public_id, 1),
    )
    outcomes = _run_ordered_race(catalog_database.app, operations, winner, _LOCK_MARKER)

    _assert_expected_outcomes(outcomes, winner, 2, StaleComponentError)
    expected = _component_state(
        public_id,
        category='meat' if winner == 0 else 'side',
        name='Archive Race Aktualisiert' if winner == 0 else 'Archive Race',
        origin='DE' if winner == 0 else 'CH',
        active=winner == 0,
        version=2,
        label=('GLUTEN_FREE', 'Glutenfrei') if winner == 0 else ('VEGAN', 'Vegan'),
        allergen=('EGGS', 'Eier', 'may_contain') if winner == 0 else ('MILK', 'Milch', 'contains'),
    )
    assert get_component(catalog_database.app, _scope(catalog_database), public_id) == expected


@pytest.mark.parametrize('winner', [0, 1])
def test_update_unarchive_race_is_atomic_in_both_winner_orders(
    catalog_database: CatalogDatabase,
    winner: int,
) -> None:
    component = create_component(
        catalog_database.app, _scope(catalog_database), 'side', 'Unarchive Race', 'CH',
        'current', ('VEGAN',), (('MILK', 'contains'),),
    )
    public_id = str(component['public_id'])
    assert archive_component(catalog_database.app, _scope(catalog_database), public_id, 1) == 2
    updated_payload = {
        'category': 'meat',
        'name': 'Unarchive Race Aktualisiert',
        'origin_country_code': 'DE',
        'label_codes': ('GLUTEN_FREE',),
        'allergens': (('EGGS', 'may_contain'),),
    }
    operations = (
        lambda: update_component(
            catalog_database.app, _scope(catalog_database), public_id, updated_payload, 2,
        ),
        lambda: unarchive_component(catalog_database.app, _scope(catalog_database), public_id, 2),
    )
    outcomes = _run_ordered_race(catalog_database.app, operations, winner, _LOCK_MARKER)

    _assert_expected_outcomes(outcomes, winner, 3, StaleComponentError)
    expected = _component_state(
        public_id,
        category='meat' if winner == 0 else 'side',
        name='Unarchive Race Aktualisiert' if winner == 0 else 'Unarchive Race',
        origin='DE' if winner == 0 else 'CH',
        active=winner == 1,
        version=3,
        label=('GLUTEN_FREE', 'Glutenfrei') if winner == 0 else ('VEGAN', 'Vegan'),
        allergen=('EGGS', 'Eier', 'may_contain') if winner == 0 else ('MILK', 'Milch', 'contains'),
    )
    assert get_component(catalog_database.app, _scope(catalog_database), public_id) == expected
