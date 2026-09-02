from __future__ import annotations

import os
import re
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.component_catalog_store import (
    AdminScope,
    ComponentCatalogConfigurationError,
    ComponentCatalogValidationError,
    ComponentConflictError,
    ComponentNotFoundError,
    StaleComponentError,
    archive_component,
    create_component,
    find_components,
    get_component,
    resolve_single_active_location_connection,
    unarchive_component,
    update_component,
)


ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
OUTPUT_KEYS = {
    'public_id',
    'profile_scope',
    'category',
    'name',
    'origin_country_code',
    'active',
    'row_version',
    'usage_count',
}

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-16-Testdatenbank fehlt.',
)


@dataclass(frozen=True)
class CatalogDatabase:
    owner: Engine
    app: Engine
    location_id: int
    other_location_id: int


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


@pytest.fixture
def catalog_database() -> Iterator[CatalogDatabase]:
    assert DATABASE_URL is not None
    owner = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(owner)
    app_password = secrets.token_urlsafe(24)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=app_password,
        backup_password=secrets.token_urlsafe(24),
        auth_issuer_password=secrets.token_urlsafe(24),
    )
    app = create_engine(
        _role_database_url('cafeteria_app', app_password),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    with owner.begin() as connection:
        server_version = int(connection.execute(text('SHOW server_version_num')).scalar_one())
        location_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.locations WHERE active ORDER BY id")
            ).scalar_one()
        )
        other_location_id = int(
            connection.execute(
                text(
                    "INSERT INTO cafeteria.locations(code, name, timezone, active) "
                    "VALUES ('CATALOG-OTHER', 'Catalog Other', 'Europe/Zurich', false) "
                    'RETURNING id'
                )
            ).scalar_one()
        )
    assert 160_000 <= server_version < 170_000
    try:
        yield CatalogDatabase(owner, app, location_id, other_location_id)
    finally:
        app.dispose()
        _drop_schema(owner)
        owner.dispose()


def _scope(database: CatalogDatabase, profile: str = 'patient') -> AdminScope:
    return AdminScope(actor_id=1, location_id=database.location_id, profile_code=profile)


def _create(
    database: CatalogDatabase,
    *,
    category: str = 'side',
    name: str = 'Kartoffelstock',
    origin: str | None = 'CH',
    target: str = 'current',
    profile: str = 'patient',
) -> dict[str, object]:
    return create_component(
        database.app,
        _scope(database, profile),
        category,
        name,
        origin,
        target,
    )


def _insert_foreign_component(
    database: CatalogDatabase,
    *,
    location_id: int,
    profile_scope: str,
    name: str,
) -> str:
    with database.owner.begin() as connection:
        return str(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_components('
                    'location_id, profile_scope, category, name'
                    ') VALUES (:location_id, :profile_scope, :category, :name) '
                    'RETURNING public_id'
                ),
                {
                    'location_id': location_id,
                    'profile_scope': profile_scope,
                    'category': 'side',
                    'name': name,
                },
            ).scalar_one()
        )


def _link_component(database: CatalogDatabase, public_id: str) -> None:
    with database.owner.begin() as connection:
        profile_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.offer_profiles WHERE code='patient'")
            ).scalar_one()
        )
        meal_period_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.meal_periods WHERE code='LUNCH'")
            ).scalar_one()
        )
        menu_type_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.menu_types WHERE code='MENU_1'")
            ).scalar_one()
        )
        week_id = int(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start) '
                    "VALUES (:location_id, :profile_id, DATE '2026-09-07') RETURNING id"
                ),
                {'location_id': database.location_id, 'profile_id': profile_id},
            ).scalar_one()
        )
        service_id = int(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_services('
                    'menu_week_id, service_date, meal_period_id'
                    ") VALUES (:week_id, DATE '2026-09-07', :meal_period_id) RETURNING id"
                ),
                {'week_id': week_id, 'meal_period_id': meal_period_id},
            ).scalar_one()
        )
        item_id = int(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_items('
                    'service_id, menu_type_id, external_id, title, sort_order'
                    ") VALUES (:service_id, :menu_type_id, 'CATALOG-USE', 'Probe', 1) "
                    'RETURNING id'
                ),
                {'service_id': service_id, 'menu_type_id': menu_type_id},
            ).scalar_one()
        )
        component = connection.execute(
            text(
                'SELECT id, row_version, name FROM cafeteria.menu_components '
                'WHERE public_id=CAST(:public_id AS uuid)'
            ),
            {'public_id': public_id},
        ).mappings().one()
        connection.execute(
            text(
                'INSERT INTO cafeteria.menu_item_components('
                'menu_item_id, sort_order, component_text, component_id, component_row_version'
                ') VALUES (:item_id, 1, :name, :component_id, :row_version)'
            ),
            {
                'item_id': item_id,
                'name': component['name'],
                'component_id': component['id'],
                'row_version': component['row_version'],
            },
        )


def test_create_maps_scope_and_returns_only_public_contract(
    catalog_database: CatalogDatabase,
) -> None:
    common = _create(catalog_database, name='  Rösti  ', origin='')
    current = _create(catalog_database, name='Poulet', category='meat')

    assert set(common) == OUTPUT_KEYS
    assert set(current) == OUTPUT_KEYS
    assert re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', str(common['public_id']))
    assert common == {
        'public_id': common['public_id'],
        'profile_scope': 'patient',
        'category': 'side',
        'name': 'Rösti',
        'origin_country_code': None,
        'active': True,
        'row_version': 1,
        'usage_count': 0,
    }
    assert current['profile_scope'] == 'patient'

    shared = _create(catalog_database, name='Bouillon', category='sauce', target='common')
    assert shared['profile_scope'] == 'common'


@pytest.mark.parametrize(
    ('scope_args', 'call_args'),
    [
        ({'actor_id': True, 'location_id': 1, 'profile_code': 'patient'}, None),
        ({'actor_id': 1, 'location_id': 0, 'profile_code': 'patient'}, None),
        ({'actor_id': 1, 'location_id': 1, 'profile_code': 'Patient'}, None),
        (None, ('MEAT', 'Name', 'CH', 'current')),
        (None, ('meat', '   ', 'CH', 'current')),
        (None, ('meat', 'Name', 'ch', 'current')),
        (None, ('meat', 'Name', ' CH ', 'current')),
        (None, ('meat', 'Name', 'CH', 'patient')),
    ],
)
def test_create_rejects_non_exact_input_without_mutation(
    catalog_database: CatalogDatabase,
    scope_args: dict[str, object] | None,
    call_args: tuple[object, object, object, object] | None,
) -> None:
    with pytest.raises(ComponentCatalogValidationError):
        if scope_args is not None:
            AdminScope(**scope_args)  # type: ignore[arg-type]
        else:
            assert call_args is not None
            create_component(catalog_database.app, _scope(catalog_database), *call_args)

    with catalog_database.owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_components')).scalar_one() == 0


def test_resolver_requires_exactly_one_active_location(
    catalog_database: CatalogDatabase,
) -> None:
    with catalog_database.app.begin() as connection:
        assert resolve_single_active_location_connection(connection) == catalog_database.location_id

    with catalog_database.owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
    with catalog_database.app.begin() as connection:
        with pytest.raises(ComponentCatalogConfigurationError):
            resolve_single_active_location_connection(connection)

    with catalog_database.owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=true'))
    with catalog_database.app.begin() as connection:
        with pytest.raises(ComponentCatalogConfigurationError):
            resolve_single_active_location_connection(connection)


def test_get_and_find_hide_foreign_location_profile_and_unknown_ids(
    catalog_database: CatalogDatabase,
) -> None:
    visible = _create(catalog_database)
    foreign_profile = _insert_foreign_component(
        catalog_database,
        location_id=catalog_database.location_id,
        profile_scope='staff_guest',
        name='Foreign Profile',
    )
    foreign_location = _insert_foreign_component(
        catalog_database,
        location_id=catalog_database.other_location_id,
        profile_scope='patient',
        name='Foreign Location',
    )

    assert get_component(catalog_database.app, _scope(catalog_database), str(visible['public_id'])) == visible
    assert [row['name'] for row in find_components(
        catalog_database.app, _scope(catalog_database), '', None, False
    )] == ['Kartoffelstock']
    for hidden in (foreign_profile, foreign_location, 'not-a-uuid', '00000000-0000-0000-0000-000000000000'):
        with pytest.raises(ComponentNotFoundError):
            get_component(catalog_database.app, _scope(catalog_database), hidden)


def test_find_uses_literal_case_insensitive_search_exact_filter_and_business_sort(
    catalog_database: CatalogDatabase,
) -> None:
    for category, name in (
        ('other', 'z Schluss'),
        ('side', 'Älpler Beilage'),
        ('meat', 'braten'),
        ('meat', 'A Braten'),
        ('sauce', 'Sauce 100%'),
        ('sauce', 'Sauce 100A'),
        ('vegetable', 'Under_score'),
        ('vegetable', 'UnderXscore'),
        ('dessert', r'Back\slash'),
        ('dessert', 'Backslash'),
    ):
        _create(catalog_database, category=category, name=name, origin=None)
    archived = _create(catalog_database, category='meat', name='B Braten', origin=None)
    archive_component(
        catalog_database.app,
        _scope(catalog_database),
        str(archived['public_id']),
        int(archived['row_version']),
    )

    all_rows = find_components(catalog_database.app, _scope(catalog_database), '', None, True)
    assert [(row['category'], row['name'], row['active']) for row in all_rows[:4]] == [
        ('meat', 'A Braten', True),
        ('meat', 'braten', True),
        ('meat', 'B Braten', False),
        ('side', 'Älpler Beilage', True),
    ]
    assert [row['name'] for row in find_components(
        catalog_database.app, _scope(catalog_database), 'BRATEN', 'meat', False
    )] == ['A Braten', 'braten']
    assert [row['name'] for row in find_components(
        catalog_database.app, _scope(catalog_database), '%', 'sauce', False
    )] == ['Sauce 100%']
    assert [row['name'] for row in find_components(
        catalog_database.app, _scope(catalog_database), '_', 'vegetable', False
    )] == ['Under_score']
    assert [row['name'] for row in find_components(
        catalog_database.app, _scope(catalog_database), '\\', 'dessert', False
    )] == [r'Back\slash']


@pytest.mark.parametrize(
    ('query', 'category', 'include_archived'),
    [(1, None, False), ('', 'MEAT', False), ('', None, 1)],
)
def test_find_rejects_invalid_filter_types(
    catalog_database: CatalogDatabase,
    query: object,
    category: object,
    include_archived: object,
) -> None:
    with pytest.raises(ComponentCatalogValidationError):
        find_components(
            catalog_database.app,
            _scope(catalog_database),
            query,  # type: ignore[arg-type]
            category,  # type: ignore[arg-type]
            include_archived,  # type: ignore[arg-type]
        )


def test_usage_count_is_derived_from_assignments(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    _link_component(catalog_database, str(component['public_id']))

    found = get_component(catalog_database.app, _scope(catalog_database), str(component['public_id']))
    assert found['usage_count'] == 1


def test_update_requires_exact_payload_and_optimistic_version(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    version = int(component['row_version'])
    assert update_component(
        catalog_database.app,
        _scope(catalog_database),
        public_id,
        {'category': 'vegetable', 'name': '  Wirz  ', 'origin_country_code': None},
        version,
    ) == 2
    assert get_component(catalog_database.app, _scope(catalog_database), public_id)['name'] == 'Wirz'

    for payload in (
        {'name': 'Missing fields'},
        {'category': 'side', 'name': 'Extra', 'origin_country_code': None, 'active': False},
    ):
        with pytest.raises(ComponentCatalogValidationError):
            update_component(catalog_database.app, _scope(catalog_database), public_id, payload, 2)
    with pytest.raises(StaleComponentError):
        update_component(
            catalog_database.app,
            _scope(catalog_database),
            public_id,
            {'category': 'side', 'name': 'Stale', 'origin_country_code': 'CH'},
            version,
        )
    assert get_component(catalog_database.app, _scope(catalog_database), public_id)['row_version'] == 2


def test_two_concurrent_updates_allow_exactly_one_version_winner(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    version = int(component['row_version'])

    def update(name: str) -> object:
        try:
            return update_component(
                catalog_database.app,
                _scope(catalog_database),
                public_id,
                {'category': 'side', 'name': name, 'origin_country_code': 'CH'},
                version,
            )
        except StaleComponentError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(update, ('Winner A', 'Winner B')))

    assert sum(result == 2 for result in outcomes) == 1
    assert sum(isinstance(result, StaleComponentError) for result in outcomes) == 1


def test_archive_unarchive_conflicts_do_not_bump_and_name_stays_reserved(
    catalog_database: CatalogDatabase,
) -> None:
    component = _create(catalog_database)
    public_id = str(component['public_id'])
    assert archive_component(catalog_database.app, _scope(catalog_database), public_id, 1) == 2
    assert find_components(catalog_database.app, _scope(catalog_database), '', None, False) == []
    assert get_component(catalog_database.app, _scope(catalog_database), public_id)['active'] is False

    with pytest.raises(ComponentConflictError):
        archive_component(catalog_database.app, _scope(catalog_database), public_id, 2)
    assert get_component(catalog_database.app, _scope(catalog_database), public_id)['row_version'] == 2
    with pytest.raises(ComponentConflictError):
        _create(catalog_database, name='  KARTOFFELSTOCK  ')

    assert unarchive_component(catalog_database.app, _scope(catalog_database), public_id, 2) == 3
    with pytest.raises(ComponentConflictError):
        unarchive_component(catalog_database.app, _scope(catalog_database), public_id, 3)
    assert get_component(catalog_database.app, _scope(catalog_database), public_id)['row_version'] == 3


def test_unique_conflict_translation_is_narrow_for_update(
    catalog_database: CatalogDatabase,
) -> None:
    first = _create(catalog_database, name='Erbsen')
    second = _create(catalog_database, name='Karotten')

    with pytest.raises(ComponentConflictError):
        update_component(
            catalog_database.app,
            _scope(catalog_database),
            str(second['public_id']),
            {'category': 'side', 'name': ' ERBSEN ', 'origin_country_code': None},
            int(second['row_version']),
        )
    assert get_component(
        catalog_database.app, _scope(catalog_database), str(first['public_id'])
    )['name'] == 'Erbsen'
    assert get_component(
        catalog_database.app, _scope(catalog_database), str(second['public_id'])
    )['name'] == 'Karotten'


@pytest.mark.parametrize('version', [True, 0, -1, '1'])
def test_mutations_reject_non_positive_real_integer_versions(
    catalog_database: CatalogDatabase,
    version: object,
) -> None:
    component = _create(catalog_database)
    with pytest.raises(ComponentCatalogValidationError):
        archive_component(
            catalog_database.app,
            _scope(catalog_database),
            str(component['public_id']),
            version,  # type: ignore[arg-type]
        )


def test_every_operation_rejects_scope_outside_single_active_location(
    catalog_database: CatalogDatabase,
) -> None:
    foreign_scope = AdminScope(actor_id=1, location_id=catalog_database.other_location_id, profile_code='patient')

    with pytest.raises(ComponentCatalogConfigurationError):
        create_component(catalog_database.app, foreign_scope, 'side', 'Fremd', None, 'current')
    with pytest.raises(ComponentCatalogConfigurationError):
        find_components(catalog_database.app, foreign_scope, '', None, False)
