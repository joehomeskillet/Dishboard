from __future__ import annotations

# ruff: noqa: F401, F811

import re

import pytest
from sqlalchemy import event, text

from cafeteria import workflow
from cafeteria.component_assignment_store import AutoOriginConflictError, StaleItemError
from cafeteria.component_catalog_store import AdminScope, ComponentNotFoundError, update_component
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


TOKEN_PATTERN = re.compile(r'sha256:[0-9a-f]{64}')


def _version(database: CatalogDatabase, item_id: int) -> int:
    with database.owner.connect() as connection:
        return int(
            connection.execute(
                text('SELECT row_version FROM cafeteria.menu_items WHERE id=:id'),
                {'id': item_id},
            ).scalar_one()
        )


def _mark_checked(database: CatalogDatabase, *item_ids: int) -> None:
    with database.owner.begin() as connection:
        connection.execute(
            text(
                "UPDATE cafeteria.menu_items SET allergen_review_status='checked' "
                'WHERE id=ANY(CAST(:ids AS bigint[]))'
            ),
            {'ids': list(item_ids)},
        )


def _scope(database: CatalogDatabase, profile: str = 'patient') -> AdminScope:
    with database.owner.connect() as connection:
        actor_id = int(
            connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id DESC')).scalars().first()
        )
    return AdminScope(actor_id, database.location_id, profile)


def _full_state(database: CatalogDatabase, item_id: int) -> tuple[object, ...]:
    with database.owner.connect() as connection:
        ownership = tuple(
            connection.execute(
                text(
                    '''
                    SELECT w.row_version, w.updated_by
                    FROM cafeteria.menu_items i
                    JOIN cafeteria.menu_services s ON s.id=i.service_id
                    JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                    WHERE i.id=:id
                    '''
                ),
                {'id': item_id},
            ).one()
        )
    return (*_item_state(database, item_id), ownership)


def _is_review_open(database: CatalogDatabase, item_id: int) -> bool:
    return workflow.review_open(database.app, _scope(database), item_id)


def _allergens(database: CatalogDatabase, item_id: int) -> tuple[tuple[str, str], ...]:
    with database.owner.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    '''
                    SELECT a.code, ia.presence
                    FROM cafeteria.menu_item_allergens ia
                    JOIN cafeteria.allergens a ON a.id=ia.allergen_id
                    WHERE ia.menu_item_id=:item_id ORDER BY a.code, ia.presence
                    '''
                ),
                {'item_id': item_id},
            ).all()
        )


def test_review_open_is_bound_to_location_profile_and_item(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database, review='checked', suffix='SCOPED-PREDICATE')

    assert not workflow.review_open(catalog_database.app, item.scope, item.id)
    with pytest.raises(ComponentNotFoundError):
        workflow.review_open(
            catalog_database.app,
            AdminScope(item.scope.actor_id, item.scope.location_id, 'staff_guest'),
            item.id,
        )


def test_review_open_conceals_wrong_location_and_missing_item_identically(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database, review='checked', suffix='SCOPED-NOT-FOUND')
    wrong_location = AdminScope(
        item.scope.actor_id,
        item.scope.location_id + 1,
        item.scope.profile_code,
    )

    messages = []
    for scope, item_id in (
        (wrong_location, item.id),
        (item.scope, 9_223_372_036_854_775_807),
    ):
        with pytest.raises(ComponentNotFoundError) as caught:
            workflow.review_open(catalog_database.app, scope, item_id)
        messages.append(str(caught.value))

    assert messages == ['Menü nicht gefunden.', 'Menü nicht gefunden.']


def test_review_rebases_catalog_state_once_and_heals_only_scoped_item(
    catalog_database: CatalogDatabase,
) -> None:
    first = _item(
        catalog_database,
        modes=('auto', 'manual', 'manual'),
        review='checked',
        suffix='REVIEW-A',
    )
    other = _item(
        catalog_database,
        modes=('auto', 'manual', 'manual'),
        review='checked',
        suffix='REVIEW-B',
        week_offset=1,
    )
    component = _component(
        catalog_database,
        'Rind alt',
        labels=('VEGETARIAN',),
        allergens=(('MILK', 'contains'),),
    )
    public_id = str(component['public_id'])
    first_version = workflow.replace_component_links(
        catalog_database.app,
        first.scope,
        first.id,
        [_assignment(public_id, None), _assignment(None, '  Freitext\t')],
        first.version,
    )
    workflow.replace_component_links(
        catalog_database.app,
        other.scope,
        other.id,
        [_assignment(public_id, None)],
        other.version,
    )
    manual_before = _set_manual_effects(catalog_database, first.id)
    _mark_checked(catalog_database, first.id, other.id)
    first_version = _version(catalog_database, first.id)
    update_component(
        catalog_database.app,
        first.scope,
        public_id,
        {
            'category': 'meat',
            'name': 'Rind neu',
            'origin_country_code': 'DE',
            'label_codes': ['VEGAN'],
            'allergens': [('GLUTEN', 'may_contain')],
        },
        int(component['row_version']),
    )
    assert _is_review_open(catalog_database, first.id)
    assert _is_review_open(catalog_database, other.id)

    token = workflow.get_component_review_token(catalog_database.app, _scope(catalog_database), first.id)
    assert TOKEN_PATTERN.fullmatch(token)
    lock_order: list[str] = []

    def record_lock(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        markers = (
            ('assignment_week_lock', 'week'),
            ('SELECT id FROM cafeteria.menu_services', 'service'),
            ('SELECT id, row_version, allergen_mode', 'item'),
            ('review_component_lock', 'components'),
            ('review_links_lock', 'links'),
        )
        for marker, name in markers:
            if marker in statement:
                lock_order.append(name)

    event.listen(catalog_database.app, 'before_cursor_execute', record_lock)
    try:
        new_version = workflow.review_component(
            catalog_database.app,
            _scope(catalog_database),
            first.id,
            token,
            first_version,
        )
    finally:
        event.remove(catalog_database.app, 'before_cursor_execute', record_lock)

    assert lock_order[:5] == ['week', 'service', 'item', 'components', 'links']
    assert new_version == first_version + 1
    assert _links(catalog_database, first.id) == [
        (1, public_id, 'Rind neu', 2),
        (2, None, '  Freitext\t', None),
    ]
    state = _item_state(catalog_database, first.id)
    assert state[0] == (new_version, 'checked')
    assert state[2] == manual_before[0]
    assert state[4] == manual_before[2]
    assert _allergens(catalog_database, first.id) == (('GLUTEN', 'may_contain'),)
    assert not _is_review_open(catalog_database, first.id)
    assert _links(catalog_database, other.id) == [(1, public_id, 'Rind alt', 1)]
    assert _is_review_open(catalog_database, other.id)
    assert _full_state(catalog_database, first.id)[-1][1] == _scope(catalog_database).actor_id


def test_review_rejects_bad_scope_versions_tokens_and_repeat_without_mutation(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database, suffix='REVIEW-CONFLICT')
    component = _component(catalog_database, 'Konfliktfrei')
    public_id = str(component['public_id'])
    current_version = workflow.replace_component_links(
        catalog_database.app,
        item.scope,
        item.id,
        [_assignment(public_id, None)],
        item.version,
    )
    scope = _scope(catalog_database)
    token = workflow.get_component_review_token(catalog_database.app, scope, item.id)
    before = _full_state(catalog_database, item.id)

    with pytest.raises(ValueError):
        workflow.review_component(catalog_database.app, scope, item.id, 'SHA256:bad', current_version)
    with pytest.raises(StaleItemError):
        workflow.review_component(
            catalog_database.app, scope, item.id, f"sha256:{'0' * 64}", current_version
        )
    with pytest.raises(StaleItemError):
        workflow.review_component(catalog_database.app, scope, item.id, token, current_version + 1)
    with pytest.raises(ComponentNotFoundError):
        workflow.review_component(
            catalog_database.app,
            AdminScope(scope.actor_id, scope.location_id, 'staff_guest'),
            item.id,
            token,
            current_version,
        )
    assert _full_state(catalog_database, item.id) == before

    new_version = workflow.review_component(
        catalog_database.app, scope, item.id, token, current_version
    )
    reviewed = _full_state(catalog_database, item.id)
    with pytest.raises(StaleItemError):
        workflow.review_component(catalog_database.app, scope, item.id, token, current_version)
    assert _full_state(catalog_database, item.id) == reviewed
    assert new_version == current_version + 1


def test_auto_origin_conflict_is_atomic_while_manual_origin_review_succeeds(
    catalog_database: CatalogDatabase,
) -> None:
    auto_item = _item(catalog_database, suffix='AUTO-ORIGIN')
    manual_item = _item(
        catalog_database,
        modes=('manual', 'manual', 'manual'),
        suffix='MANUAL-ORIGIN',
        week_offset=1,
    )
    common = _component(catalog_database, 'Kartoffel', origin='CH', target='common')
    current = _component(catalog_database, 'Reis', origin='DE')
    assignments = [
        _assignment(str(common['public_id']), None),
        _assignment(str(current['public_id']), None),
    ]
    auto_version = workflow.replace_component_links(
        catalog_database.app, auto_item.scope, auto_item.id, assignments, auto_item.version
    )
    manual_version = workflow.replace_component_links(
        catalog_database.app,
        manual_item.scope,
        manual_item.id,
        assignments,
        manual_item.version,
    )
    manual_before = _set_manual_effects(catalog_database, manual_item.id)
    auto_token = workflow.get_component_review_token(
        catalog_database.app, auto_item.scope, auto_item.id
    )
    update_component(
        catalog_database.app,
        auto_item.scope,
        str(current['public_id']),
        {
            'category': 'side',
            'name': 'Kartoffel',
            'origin_country_code': 'DE',
            'label_codes': [],
            'allergens': [],
        },
        int(current['row_version']),
    )
    auto_before = _full_state(catalog_database, auto_item.id)

    with pytest.raises(AutoOriginConflictError):
        workflow.get_component_review_token(catalog_database.app, auto_item.scope, auto_item.id)
    with pytest.raises(AutoOriginConflictError):
        workflow.review_component(
            catalog_database.app,
            auto_item.scope,
            auto_item.id,
            auto_token,
            auto_version,
        )
    assert _full_state(catalog_database, auto_item.id) == auto_before
    assert _is_review_open(catalog_database, auto_item.id)

    manual_token = workflow.get_component_review_token(
        catalog_database.app, manual_item.scope, manual_item.id
    )
    workflow.review_component(
        catalog_database.app,
        manual_item.scope,
        manual_item.id,
        manual_token,
        manual_version,
    )
    manual_after = _item_state(catalog_database, manual_item.id)[2:]
    assert manual_after == manual_before
    assert not _is_review_open(catalog_database, manual_item.id)
