from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text

from cafeteria.component_catalog_metadata import (
    MetadataContractError,
    MetadataValidationError,
    normalize_metadata,
    resolve_metadata,
)
from cafeteria.component_catalog_store import (
    ComponentCatalogValidationError,
    ComponentConflictError,
    StaleComponentError,
    archive_component,
    create_component,
    find_components,
    get_component,
    unarchive_component,
    update_component,
)
from test_component_catalog_db import CatalogDatabase, _link_component, _scope, catalog_database


FULL_KEYS = {
    'public_id', 'profile_scope', 'category', 'name', 'origin_country_code',
    'active', 'row_version', 'usage_count', 'labels', 'allergens',
}


class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list[object]:
        return self.rows

    def scalars(self) -> list[object]:
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class _FakeConnection:
    def __init__(self, responses: list[list[object]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement: object, parameters: dict[str, object] | None = None) -> _FakeResult:
        self.calls.append((str(statement), parameters or {}))
        return _FakeResult(self.responses[len(self.calls) - 1])


def _create(
    database: CatalogDatabase,
    *,
    name: str = 'Metadaten Probe',
    labels: object = ('VEGAN',),
    allergens: object = (('MILK', 'contains'),),
) -> dict[str, object]:
    return create_component(
        database.app,
        _scope(database),
        'side',
        name,
        'CH',
        'current',
        labels,  # type: ignore[arg-type]
        allergens,  # type: ignore[arg-type]
    )


def _payload(
    *,
    name: str = 'Metadaten Probe',
    labels: object = ('VEGAN',),
    allergens: object = (('MILK', 'contains'),),
) -> dict[str, object]:
    return {
        'category': 'side',
        'name': name,
        'origin_country_code': 'CH',
        'label_codes': labels,
        'allergens': allergens,
    }


def _metadata_rows(database: CatalogDatabase, public_id: str) -> tuple[list[tuple], list[tuple]]:
    with database.owner.connect() as connection:
        labels = connection.execute(text(
            '''SELECT dl.code, dl.display_name FROM cafeteria.component_labels cl
               JOIN cafeteria.dietary_labels dl ON dl.id=cl.label_id
               JOIN cafeteria.menu_components c ON c.id=cl.component_id
               WHERE c.public_id=CAST(:public_id AS uuid) ORDER BY dl.code'''
        ), {'public_id': public_id}).all()
        allergens = connection.execute(text(
            '''SELECT a.code, a.display_name, ca.presence
               FROM cafeteria.component_allergens ca
               JOIN cafeteria.allergens a ON a.id=ca.allergen_id
               JOIN cafeteria.menu_components c ON c.id=ca.component_id
               WHERE c.public_id=CAST(:public_id AS uuid) ORDER BY a.code'''
        ), {'public_id': public_id}).all()
    return list(labels), list(allergens)


def _parent_state(database: CatalogDatabase, public_id: str) -> tuple[int, object]:
    with database.owner.connect() as connection:
        row = connection.execute(text(
            '''SELECT row_version, updated_at FROM cafeteria.menu_components
               WHERE public_id=CAST(:public_id AS uuid)'''
        ), {'public_id': public_id}).one()
    return int(row.row_version), row.updated_at


def _set_master_active(database: CatalogDatabase, table: str, code: str, active: bool) -> None:
    assert table in {'dietary_labels', 'allergens'}
    with database.owner.begin() as connection:
        connection.execute(
            text(f'UPDATE cafeteria.{table} SET active=:active WHERE code=:code'),
            {'active': active, 'code': code},
        )


def test_metadata_exact_contract_and_stable_order_across_create_get_find(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(
        catalog_database,
        labels=('VEGAN', 'GLUTEN_FREE'),
        allergens=(('MILK', 'may_contain'), ('GLUTEN', 'contains')),
    )
    expected_labels = [
        {'code': 'GLUTEN_FREE', 'name': 'Glutenfrei'},
        {'code': 'VEGAN', 'name': 'Vegan'},
    ]
    expected_allergens = [
        {'code': 'GLUTEN', 'name': 'Glutenhaltiges Getreide', 'presence': 'contains'},
        {'code': 'MILK', 'name': 'Milch', 'presence': 'may_contain'},
    ]
    assert set(component) == FULL_KEYS
    assert component['labels'] == expected_labels
    assert component['allergens'] == expected_allergens

    public_id = str(component['public_id'])
    found = find_components(catalog_database.app, _scope(catalog_database), '', None, False)
    detail = get_component(catalog_database.app, _scope(catalog_database), public_id)
    assert found == [detail] == [component]
    assert all(set(label) == {'code', 'name'} for label in component['labels'])
    assert all(set(allergen) == {'code', 'name', 'presence'} for allergen in component['allergens'])


def test_resolver_calls_secure_helper_once_with_bound_arrays_and_empty_arrays() -> None:
    connection = _FakeConnection([[], [], []])
    resolved = resolve_metadata(connection, 7, normalize_metadata((), ()))  # type: ignore[arg-type]
    assert resolved.changed is False
    assert len(connection.calls) == 3
    sql, parameters = connection.calls[0]
    assert sql.count('lock_component_metadata_masters') == 1
    assert 'CAST(:label_codes AS text[])' in sql
    assert 'CAST(:allergen_codes AS text[])' in sql
    assert parameters == {'label_codes': [], 'allergen_codes': []}


def test_resolver_allows_same_code_in_separate_master_namespaces() -> None:
    connection = _FakeConnection([
        [
            {'master_kind': 'label', 'master_id': 2, 'code': 'MILK', 'active': True},
            {'master_kind': 'allergen', 'master_id': 7, 'code': 'MILK', 'active': True},
        ],
        [],
        [],
    ])
    resolved = resolve_metadata(
        connection, 9, normalize_metadata(('MILK',), (('MILK', 'contains'),))
    )  # type: ignore[arg-type]
    assert resolved.labels == ((2, 'MILK'),)
    assert resolved.allergens == ((7, 'MILK', 'contains'),)
    assert connection.calls[0][1] == {
        'label_codes': ['MILK'], 'allergen_codes': ['MILK']
    }


@pytest.mark.parametrize(
    ('metadata', 'rows', 'error'),
    [
        (normalize_metadata((), ()), [{'master_kind': 'other', 'master_id': 1, 'code': 'X', 'active': True}], MetadataContractError),
        (normalize_metadata(('VEGAN',), ()), [
            {'master_kind': 'label', 'master_id': 1, 'code': 'VEGAN', 'active': True},
            {'master_kind': 'label', 'master_id': 1, 'code': 'VEGAN', 'active': True},
        ], MetadataContractError),
        (normalize_metadata((), ()), [
            {'master_kind': 'label', 'master_id': 1, 'code': 'VEGAN', 'active': True},
        ], MetadataContractError),
        (normalize_metadata(('VEGAN',), ()), [], MetadataValidationError),
        (normalize_metadata((), (('MILK', 'contains'),)), [], MetadataValidationError),
    ],
)
def test_resolver_rejects_broken_or_missing_helper_contract_before_child_reads(
    metadata: object,
    rows: list[object],
    error: type[Exception],
) -> None:
    connection = _FakeConnection([rows])
    with pytest.raises(error):
        resolve_metadata(connection, 4, metadata)  # type: ignore[arg-type]
    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    ('labels', 'allergens'),
    [
        ('VEGAN', ()),
        (('bad',), ()),
        (('VEGAN', 'VEGAN'), ()),
        (('UNKNOWN',), ()),
        ((), 'MILK'),
        ((), (('MILK',),)),
        ((), (('MILK', 'sometimes'),)),
        ((), (('MILK', 'contains'), ('MILK', 'may_contain'))),
        ((), (('UNKNOWN', 'contains'),)),
    ],
)
def test_create_rejects_invalid_metadata_without_parent_or_child_mutation(
    catalog_database: CatalogDatabase,
    labels: object,
    allergens: object,
) -> None:
    with pytest.raises(ComponentCatalogValidationError):
        _create(catalog_database, labels=labels, allergens=allergens)
    with catalog_database.owner.connect() as connection:
        counts = connection.execute(text(
            '''SELECT (SELECT count(*) FROM cafeteria.menu_components),
                      (SELECT count(*) FROM cafeteria.component_labels),
                      (SELECT count(*) FROM cafeteria.component_allergens)'''
        )).one()
    assert tuple(counts) == (0, 0, 0)


def test_metadata_size_cap_rejects_65_before_db_and_allows_64_to_normal_validation(
    catalog_database: CatalogDatabase,
) -> None:
    codes_65 = tuple(f'X{i:02d}' for i in range(65))
    helper_calls: list[dict[str, object]] = []

    def capture(
        _connection: object,
        clause: object,
        _multiparams: object,
        parameters: dict[str, object],
        _options: object,
    ) -> None:
        if 'lock_component_metadata_masters' in str(clause):
            helper_calls.append(dict(parameters))

    event.listen(catalog_database.app, 'before_execute', capture)
    try:
        with pytest.raises(ComponentCatalogValidationError, match='Zu viele'):
            _create(catalog_database, labels=codes_65, allergens=())
        assert helper_calls == []
        with pytest.raises(ComponentCatalogValidationError, match='Unbekanntes'):
            _create(catalog_database, labels=codes_65[:64], allergens=())
        assert helper_calls == [{'label_codes': list(codes_65[:64]), 'allergen_codes': []}]

        helper_calls.clear()
        allergens_65 = tuple((code, 'contains') for code in codes_65)
        with pytest.raises(ComponentCatalogValidationError, match='Zu viele'):
            _create(catalog_database, labels=(), allergens=allergens_65)
        assert helper_calls == []
        with pytest.raises(ComponentCatalogValidationError, match='Unbekanntes'):
            _create(catalog_database, labels=(), allergens=allergens_65[:64])
        assert helper_calls == [{'label_codes': [], 'allergen_codes': list(codes_65[:64])}]
    finally:
        event.remove(catalog_database.app, 'before_execute', capture)
    with catalog_database.owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_components')).scalar_one() == 0


def test_create_and_update_each_call_helper_once_with_bound_arrays(
    catalog_database: CatalogDatabase,
) -> None:
    calls: list[dict[str, object]] = []

    def capture(
        _connection: object,
        clause: object,
        _multiparams: object,
        parameters: dict[str, object],
        _options: object,
    ) -> None:
        if 'lock_component_metadata_masters' in str(clause):
            calls.append(dict(parameters))

    event.listen(catalog_database.app, 'before_execute', capture)
    try:
        component = _create(catalog_database)
        assert calls == [{'label_codes': ['VEGAN'], 'allergen_codes': ['MILK']}]
        calls.clear()
        update_component(
            catalog_database.app, _scope(catalog_database), str(component['public_id']),
            _payload(labels=('GLUTEN_FREE',), allergens=(('EGGS', 'may_contain'),)), 1,
        )
        assert calls == [{'label_codes': ['GLUTEN_FREE'], 'allergen_codes': ['EGGS']}]
    finally:
        event.remove(catalog_database.app, 'before_execute', capture)


def test_update_replaces_clears_and_noop_preserves_version_and_timestamp(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(
        catalog_database,
        labels=('VEGAN', 'GLUTEN_FREE'),
        allergens=(('MILK', 'contains'), ('GLUTEN', 'may_contain')),
    )
    public_id = str(component['public_id'])
    before = _parent_state(catalog_database, public_id)

    reordered = _payload(
        labels=('GLUTEN_FREE', 'VEGAN'),
        allergens=(('GLUTEN', 'may_contain'), ('MILK', 'contains')),
    )
    assert update_component(catalog_database.app, _scope(catalog_database), public_id, reordered, 1) == 1
    assert _parent_state(catalog_database, public_id) == before

    changed = _payload(name='Geändert', labels=('VEGETARIAN',), allergens=(('EGGS', 'contains'),))
    assert update_component(catalog_database.app, _scope(catalog_database), public_id, changed, 1) == 2
    assert _metadata_rows(catalog_database, public_id) == (
        [('VEGETARIAN', 'Vegetarisch')], [('EGGS', 'Eier', 'contains')]
    )
    assert update_component(
        catalog_database.app, _scope(catalog_database), public_id,
        _payload(name='Geändert', labels=(), allergens=()), 2,
    ) == 3
    assert _metadata_rows(catalog_database, public_id) == ([], [])


def test_update_validates_complete_replacement_before_delete(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    before = _metadata_rows(catalog_database, public_id)
    for invalid in (
        _payload(labels=('UNKNOWN',), allergens=()),
        _payload(labels=(), allergens=(('UNKNOWN', 'contains'),)),
        _payload(labels=('VEGAN', 'VEGAN'), allergens=()),
        _payload(labels=(), allergens=(('MILK', 'contains'), ('MILK', 'may_contain'))),
    ):
        with pytest.raises(ComponentCatalogValidationError):
            update_component(catalog_database.app, _scope(catalog_database), public_id, invalid, 1)
        assert _metadata_rows(catalog_database, public_id) == before
        assert _parent_state(catalog_database, public_id)[0] == 1


def test_inactive_existing_links_may_remain_or_be_removed_but_not_added_or_changed(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    _set_master_active(catalog_database, 'dietary_labels', 'VEGAN', False)
    _set_master_active(catalog_database, 'allergens', 'MILK', False)

    assert update_component(
        catalog_database.app, _scope(catalog_database), public_id, _payload(), 1
    ) == 1
    assert update_component(
        catalog_database.app, _scope(catalog_database), public_id,
        _payload(labels=(), allergens=()), 1,
    ) == 2
    for invalid in (
        _payload(labels=('VEGAN',), allergens=()),
        _payload(labels=(), allergens=(('MILK', 'contains'),)),
        _payload(labels=(), allergens=(('MILK', 'may_contain'),)),
    ):
        with pytest.raises(ComponentCatalogValidationError):
            update_component(catalog_database.app, _scope(catalog_database), public_id, invalid, 2)


def test_inactive_allergen_presence_cannot_change_while_linked(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    _set_master_active(catalog_database, 'allergens', 'MILK', False)
    with pytest.raises(ComponentCatalogValidationError):
        update_component(
            catalog_database.app, _scope(catalog_database), public_id,
            _payload(allergens=(('MILK', 'may_contain'),)), 1,
        )
    assert _metadata_rows(catalog_database, public_id)[1] == [('MILK', 'Milch', 'contains')]


def test_stale_and_name_conflict_roll_back_both_child_sets(
    catalog_database: CatalogDatabase,
) -> None:
    first = _create(catalog_database, name='Erste')
    second = _create(catalog_database, name='Zweite', labels=('VEGETARIAN',), allergens=(('EGGS', 'contains'),))
    public_id = str(second['public_id'])
    before = _metadata_rows(catalog_database, public_id)
    with pytest.raises(ComponentConflictError):
        update_component(
            catalog_database.app, _scope(catalog_database), public_id,
            _payload(name=str(first['name']), labels=('GLUTEN_FREE',), allergens=()), 1,
        )
    assert _metadata_rows(catalog_database, public_id) == before
    with pytest.raises(StaleComponentError):
        update_component(
            catalog_database.app, _scope(catalog_database), public_id,
            _payload(labels=(), allergens=()), 99,
        )
    assert _metadata_rows(catalog_database, public_id) == before


def test_synchronized_updates_have_one_winner_and_no_mixed_child_state(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database, labels=(), allergens=())
    public_id = str(component['public_id'])
    barrier = Barrier(2)

    def update(payload: dict[str, object]) -> object:
        barrier.wait(timeout=5)
        try:
            return update_component(catalog_database.app, _scope(catalog_database), public_id, payload, 1)
        except StaleComponentError as error:
            return error

    candidates = (
        _payload(name='Sieger A', labels=('VEGAN',), allergens=(('MILK', 'contains'),)),
        _payload(name='Sieger B', labels=('GLUTEN_FREE',), allergens=(('EGGS', 'may_contain'),)),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(update, candidates))
    assert sum(outcome == 2 for outcome in outcomes) == 1
    assert sum(isinstance(outcome, StaleComponentError) for outcome in outcomes) == 1
    result = get_component(catalog_database.app, _scope(catalog_database), public_id)
    states = {
        ('Sieger A', 'VEGAN', 'MILK', 'contains'),
        ('Sieger B', 'GLUTEN_FREE', 'EGGS', 'may_contain'),
    }
    assert (result['name'], result['labels'][0]['code'], result['allergens'][0]['code'], result['allergens'][0]['presence']) in states


def test_archive_unarchive_retains_metadata_and_never_mutates_linked_item_state(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    _link_component(catalog_database, public_id)
    with catalog_database.owner.connect() as connection:
        before = connection.execute(text(
            '''SELECT mi.row_version, mi.allergen_review_status, mw.row_version,
                      mic.component_row_version, mic.component_text
               FROM cafeteria.menu_item_components mic
               JOIN cafeteria.menu_items mi ON mi.id=mic.menu_item_id
               JOIN cafeteria.menu_services ms ON ms.id=mi.service_id
               JOIN cafeteria.menu_weeks mw ON mw.id=ms.menu_week_id
               WHERE mic.component_id=(SELECT id FROM cafeteria.menu_components
                                       WHERE public_id=CAST(:public_id AS uuid))'''
        ), {'public_id': public_id}).one()

    assert update_component(
        catalog_database.app, _scope(catalog_database), public_id,
        _payload(labels=('GLUTEN_FREE',), allergens=(('EGGS', 'may_contain'),)), 1,
    ) == 2
    assert archive_component(catalog_database.app, _scope(catalog_database), public_id, 2) == 3
    assert unarchive_component(catalog_database.app, _scope(catalog_database), public_id, 3) == 4
    with catalog_database.owner.connect() as connection:
        after = connection.execute(text(
            '''SELECT mi.row_version, mi.allergen_review_status, mw.row_version,
                      mic.component_row_version, mic.component_text
               FROM cafeteria.menu_item_components mic
               JOIN cafeteria.menu_items mi ON mi.id=mic.menu_item_id
               JOIN cafeteria.menu_services ms ON ms.id=mi.service_id
               JOIN cafeteria.menu_weeks mw ON mw.id=ms.menu_week_id
               WHERE mic.component_id=(SELECT id FROM cafeteria.menu_components
                                       WHERE public_id=CAST(:public_id AS uuid))'''
        ), {'public_id': public_id}).one()
    assert tuple(after) == tuple(before)
    detail = get_component(catalog_database.app, _scope(catalog_database), public_id)
    assert detail['labels'] == [{'code': 'GLUTEN_FREE', 'name': 'Glutenfrei'}]
    assert detail['allergens'] == [{'code': 'EGGS', 'name': 'Eier', 'presence': 'may_contain'}]
