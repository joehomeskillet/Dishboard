from __future__ import annotations

# ruff: noqa: F811

from datetime import date, timedelta
from dataclasses import dataclass

import pytest
from sqlalchemy import text

from cafeteria.component_assignment_store import (
    AutoOriginConflictError,
    ComponentAssignmentConflictError,
    ComponentAssignmentValidationError,
    assign_component,
    replace_component_links,
    replace_component_links_connection,
    resolve_component_effects,
)
from cafeteria.component_catalog_store import (
    AdminScope,
    ComponentNotFoundError,
    archive_component,
    create_component,
)
from test_component_catalog_db import CatalogDatabase, catalog_database  # noqa: F401


@dataclass(frozen=True)
class Item:
    id: int
    week_id: int
    service_id: int
    version: int
    scope: AdminScope


def _item(
    database: CatalogDatabase,
    *,
    profile: str = 'patient',
    location_id: int | None = None,
    modes: tuple[str, str, str] = ('auto', 'auto', 'auto'),
    review: str = 'checked',
    suffix: str = 'A',
    week_offset: int = 0,
) -> Item:
    target_location = location_id or database.location_id
    week_start = date(2026, 9, 7) + timedelta(weeks=week_offset)
    with database.owner.begin() as connection:
        row = connection.execute(
            text(
                '''
                WITH profile AS (
                    SELECT id FROM cafeteria.offer_profiles WHERE code=:profile
                ), period AS (
                    SELECT id FROM cafeteria.meal_periods WHERE code='LUNCH'
                ), kind AS (
                    SELECT id FROM cafeteria.menu_types WHERE code='MENU_1'
                ), week_row AS (
                    INSERT INTO cafeteria.menu_weeks(
                        location_id, profile_id, week_start, created_by, updated_by
                    ) SELECT :location_id, profile.id, :week_start, 1, 1 FROM profile
                    RETURNING id
                ), service_row AS (
                    INSERT INTO cafeteria.menu_services(
                        menu_week_id, service_date, meal_period_id
                    ) SELECT week_row.id, :week_start, period.id
                      FROM week_row CROSS JOIN period RETURNING id, menu_week_id
                )
                INSERT INTO cafeteria.menu_items(
                    service_id, menu_type_id, external_id, title, allergen_review_status,
                    sort_order, allergen_mode, origin_mode, label_mode
                ) SELECT service_row.id, kind.id, :external_id, 'Testmenu', :review,
                         1, :allergen_mode, :origin_mode, :label_mode
                    FROM service_row CROSS JOIN kind
                RETURNING id, service_id, row_version,
                          (SELECT menu_week_id FROM service_row) AS week_id
                '''
            ),
            {
                'profile': profile,
                'location_id': target_location,
                'week_start': week_start,
                'external_id': f'ASSIGN-{profile}-{suffix}',
                'review': review,
                'allergen_mode': modes[0],
                'origin_mode': modes[1],
                'label_mode': modes[2],
            },
        ).mappings().one()
    return Item(
        int(row['id']),
        int(row['week_id']),
        int(row['service_id']),
        int(row['row_version']),
        AdminScope(actor_id=1, location_id=database.location_id, profile_code=profile),
    )


def _component(
    database: CatalogDatabase,
    name: str,
    *,
    origin: str | None = 'CH',
    target: str = 'current',
    profile: str = 'patient',
    labels: tuple[str, ...] = (),
    allergens: tuple[tuple[str, str], ...] = (),
) -> dict[str, object]:
    scope = AdminScope(1, database.location_id, profile)
    return create_component(
        database.app, scope, 'side', name, origin, target, labels, allergens
    )


def _assignment(public_id: object = None, component_text: object = None, **extra: object):
    return {
        'component_public_id': public_id,
        'component_text': component_text,
        **extra,
    }


def _links(database: CatalogDatabase, item_id: int) -> list[tuple[object, ...]]:
    with database.owner.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text(
                    '''
                    SELECT mic.sort_order, c.public_id::text, mic.component_text,
                           mic.component_row_version
                    FROM cafeteria.menu_item_components mic
                    LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id
                    WHERE mic.menu_item_id=:item_id ORDER BY mic.sort_order
                    '''
                ),
                {'item_id': item_id},
            ).all()
        ]


def _item_state(database: CatalogDatabase, item_id: int) -> tuple[object, ...]:
    with database.owner.connect() as connection:
        item = tuple(
            connection.execute(
                text(
                    'SELECT row_version, allergen_review_status FROM cafeteria.menu_items '
                    'WHERE id=:item_id'
                ),
                {'item_id': item_id},
            ).one()
        )
        labels = tuple(
            connection.execute(
                text(
                    'SELECT label_id FROM cafeteria.menu_item_labels '
                    'WHERE menu_item_id=:item_id ORDER BY label_id'
                ),
                {'item_id': item_id},
            ).scalars()
        )
        allergens = tuple(
            connection.execute(
                text(
                    'SELECT allergen_id, presence FROM cafeteria.menu_item_allergens '
                    'WHERE menu_item_id=:item_id ORDER BY allergen_id, presence'
                ),
                {'item_id': item_id},
            ).all()
        )
        origins = tuple(
            connection.execute(
                text(
                    'SELECT ingredient, country_code, declaration_text '
                    'FROM cafeteria.origin_declarations WHERE menu_item_id=:item_id '
                    'ORDER BY ingredient, country_code, declaration_text'
                ),
                {'item_id': item_id},
            ).all()
        )
    return item, tuple(_links(database, item_id)), labels, allergens, origins


def _set_manual_effects(database: CatalogDatabase, item_id: int) -> tuple[object, ...]:
    with database.owner.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO cafeteria.menu_item_labels(menu_item_id, label_id) '
                "SELECT :item_id, id FROM cafeteria.dietary_labels WHERE code='GLUTEN_FREE'"
            ),
            {'item_id': item_id},
        )
        connection.execute(
            text(
                'INSERT INTO cafeteria.menu_item_allergens('
                'menu_item_id, allergen_id, presence) '
                "SELECT :item_id, id, 'may_contain' FROM cafeteria.allergens WHERE code='SOY'"
            ),
            {'item_id': item_id},
        )
        connection.execute(
            text(
                'INSERT INTO cafeteria.origin_declarations('
                'menu_item_id, ingredient, country_code, declaration_text) '
                "VALUES (:item_id, ' Manuell ', 'CH', ' exakt ')"
            ),
            {'item_id': item_id},
        )
    return _item_state(database, item_id)[2:]


def _row_versions(
    database: CatalogDatabase, item: Item, component_public_id: str
) -> tuple[tuple[object, ...], tuple[object, ...], tuple[object, ...]]:
    with database.owner.connect() as connection:
        week = tuple(connection.execute(text(
            'SELECT row_version, updated_by, updated_at FROM cafeteria.menu_weeks WHERE id=:id'
        ), {'id': item.week_id}).one())
        service = tuple(connection.execute(text(
            'SELECT row_version, updated_at FROM cafeteria.menu_services WHERE id=:id'
        ), {'id': item.service_id}).one())
        component = tuple(connection.execute(text(
            'SELECT row_version, name, updated_at FROM cafeteria.menu_components '
            'WHERE public_id=CAST(:id AS uuid)'
        ), {'id': component_public_id}).one())
    return week, service, component


def test_exact_mapping_append_replace_unassign_and_archived_rules(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database)
    component = _component(catalog_database, 'Kartoffelstock')
    public_id = str(component['public_id'])
    version = assign_component(
        catalog_database.app, item.scope, item.id, public_id, None, item.version
    )
    assert _links(catalog_database, item.id) == [(1, public_id, 'Kartoffelstock', 1)]

    version = assign_component(
        catalog_database.app, item.scope, item.id, None, '  Freitext\t', version
    )
    assert _links(catalog_database, item.id)[1] == (2, None, '  Freitext\t', None)
    version = replace_component_links(
        catalog_database.app,
        item.scope,
        item.id,
        [_assignment(None, 'zweite'), _assignment(public_id, None)],
        version,
    )
    assert _links(catalog_database, item.id) == [
        (1, None, 'zweite', None),
        (2, public_id, 'Kartoffelstock', 1),
    ]

    before = _item_state(catalog_database, item.id)
    invalid = [
        {'component_public_id': None, 'component_text': None},
        {'component_public_id': public_id, 'component_text': 'beides'},
        _assignment(None, '   '),
        _assignment(42, None),
        _assignment(None, 'x', component_id=1),
        _assignment(None, 'x', component_row_version=1),
        _assignment(None, 'x', internal_rappen=100),
        _assignment(None, 'x', sort_order=9),
        {'component_public_id': None, 'component_text': 'x', 'price': 1},
    ]
    for payload in invalid:
        with pytest.raises(ComponentAssignmentValidationError):
            replace_component_links(
                catalog_database.app, item.scope, item.id, [payload], version
            )
        assert _item_state(catalog_database, item.id) == before

    with pytest.raises(ComponentAssignmentConflictError, match='doppelt'):
        replace_component_links(
            catalog_database.app,
            item.scope,
            item.id,
            [_assignment(public_id, None), _assignment(public_id, None)],
            version,
        )
    archive_component(catalog_database.app, item.scope, public_id, 1)
    version = replace_component_links(
        catalog_database.app, item.scope, item.id, [_assignment(public_id, None)], version
    )
    with pytest.raises(ComponentAssignmentConflictError, match='rchiviert'):
        assign_component(
            catalog_database.app, item.scope, item.id, public_id, None, version
        )
    version = replace_component_links(
        catalog_database.app, item.scope, item.id, [], version
    )
    assert _links(catalog_database, item.id) == []
    with pytest.raises(ComponentAssignmentConflictError, match='rchiviert'):
        replace_component_links(
            catalog_database.app, item.scope, item.id, [_assignment(public_id, None)], version
        )


def test_scope_effect_resolution_and_independent_auto_manual_modes(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database, modes=('auto', 'auto', 'auto'))
    common = _component(
        catalog_database,
        'Rind',
        target='common',
        labels=('VEGETARIAN', 'VEGAN'),
        allergens=(('MILK', 'contains'), ('GLUTEN', 'may_contain')),
    )
    current = _component(
        catalog_database,
        'Reis',
        origin='DE',
        labels=('VEGETARIAN',),
        allergens=(('MILK', 'may_contain'), ('GLUTEN', 'contains')),
    )
    no_origin = _component(catalog_database, 'Wasser', origin=None, labels=('VEGETARIAN',))
    version = replace_component_links(
        catalog_database.app,
        item.scope,
        item.id,
        [
            _assignment(str(common['public_id']), None),
            _assignment(str(current['public_id']), None),
            _assignment(str(no_origin['public_id']), None),
            _assignment(None, ' Freier Text '),
        ],
        item.version,
    )
    effects = resolve_component_effects(catalog_database.app, item.scope, item.id)
    assert effects == {
        'labels': [{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
        'allergens': [
            {'code': 'GLUTEN', 'name': 'Glutenhaltiges Getreide', 'presence': 'contains'},
            {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
        ],
        'origins': [
            {'ingredient': 'Reis', 'country_code': 'DE', 'text': 'Reis: DE'},
            {'ingredient': 'Rind', 'country_code': 'CH', 'text': 'Rind: CH'},
        ],
    }
    assert _item_state(catalog_database, item.id)[0] == (version, 'not_checked')

    manual = _item(
        catalog_database,
        modes=('auto', 'manual', 'manual'),
        suffix='MANUAL',
        week_offset=1,
    )
    manual_before = _set_manual_effects(catalog_database, manual.id)
    replace_component_links(
        catalog_database.app,
        manual.scope,
        manual.id,
        [_assignment(str(common['public_id']), None)],
        manual.version,
    )
    after = _item_state(catalog_database, manual.id)[2:]
    assert after[0] == manual_before[0]
    assert after[2] == manual_before[2]
    assert after[1] != manual_before[1]

    staff_component = _component(
        catalog_database, 'Nur Personal', profile='staff_guest'
    )
    before = _item_state(catalog_database, item.id)
    with pytest.raises(ComponentNotFoundError):
        assign_component(
            catalog_database.app,
            item.scope,
            item.id,
            str(staff_component['public_id']),
            None,
            version,
        )
    assert _item_state(catalog_database, item.id) == before
    foreign_item = _item(
        catalog_database,
        location_id=catalog_database.other_location_id,
        suffix='FOREIGN',
    )
    with pytest.raises(ComponentNotFoundError):
        resolve_component_effects(catalog_database.app, item.scope, foreign_item.id)


def test_origin_conflict_and_component_scope_fail_atomically(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database)
    common = _component(catalog_database, 'Kartoffel', origin='CH', target='common')
    current = _component(catalog_database, 'Kartoffel', origin='DE')
    before = _item_state(catalog_database, item.id)
    with pytest.raises(AutoOriginConflictError):
        replace_component_links(
            catalog_database.app,
            item.scope,
            item.id,
            [
                _assignment(str(common['public_id']), None),
                _assignment(str(current['public_id']), None),
            ],
            item.version,
        )
    assert _item_state(catalog_database, item.id) == before

    foreign_id = None
    with catalog_database.owner.begin() as connection:
        foreign_id = str(connection.execute(text(
            "INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name) "
            "VALUES (:location, 'patient', 'side', 'Fremd') RETURNING public_id"
        ), {'location': catalog_database.other_location_id}).scalar_one())
    with pytest.raises(ComponentNotFoundError):
        replace_component_links(
            catalog_database.app,
            item.scope,
            item.id,
            [_assignment(foreign_id, None)],
            item.version,
        )
    assert _item_state(catalog_database, item.id) == before


def test_connection_helper_never_commits_or_changes_item_effects_or_review(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database, modes=('manual', 'manual', 'manual'))
    component = _component(catalog_database, 'Helper')
    before = _item_state(catalog_database, item.id)
    connection = catalog_database.app.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            text('SELECT id FROM cafeteria.menu_weeks WHERE id=:id FOR UPDATE'),
            {'id': item.week_id},
        ).one()
        connection.execute(
            text('SELECT id FROM cafeteria.menu_services WHERE id=:id FOR UPDATE'),
            {'id': item.service_id},
        ).one()
        connection.execute(
            text('SELECT id FROM cafeteria.menu_items WHERE id=:id FOR UPDATE'),
            {'id': item.id},
        ).one()
        replace_component_links_connection(
            connection,
            item.scope,
            item.id,
            [_assignment(str(component['public_id']), None)],
        )
        inside = connection.execute(text(
            'SELECT row_version, allergen_review_status FROM cafeteria.menu_items WHERE id=:id'
        ), {'id': item.id}).one()
        assert tuple(inside) == before[0]
        assert _links(catalog_database, item.id) == []
    finally:
        transaction.rollback()
        connection.close()
    assert _item_state(catalog_database, item.id) == before


def test_success_bumps_only_item_once_and_preserves_other_rows(
    catalog_database: CatalogDatabase,
) -> None:
    item = _item(catalog_database, modes=('auto', 'manual', 'manual'))
    component = _component(
        catalog_database, 'Unverändert', allergens=(('MILK', 'contains'),)
    )
    public_id = str(component['public_id'])
    manual_before = _set_manual_effects(catalog_database, item.id)
    rows_before = _row_versions(catalog_database, item, public_id)
    new_version = replace_component_links(
        catalog_database.app,
        item.scope,
        item.id,
        [_assignment(public_id, None)],
        item.version,
    )
    assert new_version == item.version + 1
    assert _item_state(catalog_database, item.id)[0] == (new_version, 'not_checked')
    assert _row_versions(catalog_database, item, public_id) == rows_before
    effects_after = _item_state(catalog_database, item.id)[2:]
    assert effects_after[0] == manual_before[0]
    assert effects_after[2] == manual_before[2]
    assert effects_after[1] != manual_before[1]
