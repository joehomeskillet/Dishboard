from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from cafeteria import db as database


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'database' / 'schema.sql'
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-16-Testdatenbank fehlt.',
)


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
def migrated_owner_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.provision_database_roles(
        engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    database.run_migrations(engine, SCHEMA)
    database._execute_script(engine, str(ROOT / 'database' / 'seed.sql'))
    database._execute_script(engine, str(ROOT / 'database' / 'permissions.sql'))
    try:
        with engine.connect() as connection:
            server_version = int(connection.execute(text('SHOW server_version_num')).scalar_one())
        assert 160_000 <= server_version < 170_000
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


@pytest.fixture
def app_engine(migrated_owner_engine: Engine) -> Iterator[Engine]:
    engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        yield engine
    finally:
        engine.dispose()


def _seed_scope_probe(owner_engine: Engine) -> dict[str, int]:
    with owner_engine.begin() as connection:
        location_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.locations WHERE code='KIRCHLINDACH'")
            ).scalar_one()
        )
        other_location_id = int(
            connection.execute(
                text(
                    "INSERT INTO cafeteria.locations(code, name, timezone) "
                    "VALUES ('SCOPE-OTHER', 'Scope Other', 'Europe/Zurich') RETURNING id"
                )
            ).scalar_one()
        )
        patient_profile_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.offer_profiles WHERE code='patient'")
            ).scalar_one()
        )
        lunch_id = int(
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
                {'location_id': location_id, 'profile_id': patient_profile_id},
            ).scalar_one()
        )
        service_id = int(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_services('
                    'menu_week_id, service_date, meal_period_id'
                    ") VALUES (:week_id, DATE '2026-09-07', :meal_period_id) RETURNING id"
                ),
                {'week_id': week_id, 'meal_period_id': lunch_id},
            ).scalar_one()
        )
        item_id = int(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_items('
                    'service_id, menu_type_id, external_id, title, sort_order'
                    ") VALUES (:service_id, :menu_type_id, 'SCOPE-PROBE', 'Scope Probe', 1) "
                    'RETURNING id'
                ),
                {'service_id': service_id, 'menu_type_id': menu_type_id},
            ).scalar_one()
        )

        component_ids: dict[str, int] = {}
        for key, component_location_id, profile_scope, name in (
            ('exact', location_id, 'patient', 'Exact Patient'),
            ('common', location_id, 'common', 'Common Component'),
            ('wrong_scope', location_id, 'staff_guest', 'Wrong Scope'),
            ('wrong_location', other_location_id, 'patient', 'Wrong Location'),
        ):
            component_ids[key] = int(
                connection.execute(
                    text(
                        'INSERT INTO cafeteria.menu_components('
                        'location_id, profile_scope, category, name'
                        ') VALUES (:location_id, :profile_scope, :category, :name) RETURNING id'
                    ),
                    {
                        'location_id': component_location_id,
                        'profile_scope': profile_scope,
                        'category': 'side',
                        'name': name,
                    },
                ).scalar_one()
            )

    return {
        'location': location_id,
        'other_location': other_location_id,
        'week': week_id,
        'item': item_id,
        **component_ids,
    }


def _assert_check_violation(
    engine: Engine,
    statement: str,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(IntegrityError) as exc_info:
        with engine.begin() as connection:
            connection.execute(text(statement), parameters)
    assert exc_info.value.orig.sqlstate == '23514'


def test_migrated_scope_links_and_identity_fields_resist_app_role_mutation(
    migrated_owner_engine: Engine,
    app_engine: Engine,
) -> None:
    ids = _seed_scope_probe(migrated_owner_engine)

    with app_engine.begin() as connection:
        for sort_order, key in ((1, 'exact'), (2, 'common')):
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_item_components('
                    'menu_item_id, sort_order, component_text, component_id, component_row_version'
                    ') VALUES (:item_id, :sort_order, :component_text, :component_id, 1)'
                ),
                {
                    'item_id': ids['item'],
                    'sort_order': sort_order,
                    'component_text': key,
                    'component_id': ids[key],
                },
            )
        connection.execute(
            text(
                'INSERT INTO cafeteria.menu_item_components('
                'menu_item_id, sort_order, component_text'
                ") VALUES (:item_id, 3, 'Freitext')"
            ),
            {'item_id': ids['item']},
        )

    for key in ('wrong_scope', 'wrong_location'):
        _assert_check_violation(
            app_engine,
            'INSERT INTO cafeteria.menu_item_components('
            'menu_item_id, sort_order, component_text, component_id, component_row_version'
            ') VALUES (:item_id, :sort_order, :component_text, :component_id, 1)',
            {
                'item_id': ids['item'],
                'sort_order': 10 if key == 'wrong_scope' else 11,
                'component_text': key,
                'component_id': ids[key],
            },
        )
        _assert_check_violation(
            app_engine,
            'UPDATE cafeteria.menu_item_components '
            'SET component_id=:component_id, component_row_version=1 '
            'WHERE menu_item_id=:item_id AND sort_order=1',
            {'component_id': ids[key], 'item_id': ids['item']},
        )

    _assert_check_violation(
        app_engine,
        'UPDATE cafeteria.menu_components SET location_id=:location_id WHERE id=:component_id',
        {'location_id': ids['other_location'], 'component_id': ids['exact']},
    )
    _assert_check_violation(
        app_engine,
        'UPDATE cafeteria.menu_components SET profile_scope=:profile_scope WHERE id=:component_id',
        {'profile_scope': 'staff_guest', 'component_id': ids['exact']},
    )
    _assert_check_violation(
        app_engine,
        'UPDATE cafeteria.menu_weeks SET location_id=:location_id WHERE id=:week_id',
        {'location_id': ids['other_location'], 'week_id': ids['week']},
    )

    with app_engine.begin() as connection:
        component_identity = connection.execute(
            text(
                'UPDATE cafeteria.menu_components '
                'SET location_id=:location_id, profile_scope=:profile_scope '
                'WHERE id=:component_id RETURNING location_id, profile_scope'
            ),
            {
                'location_id': ids['location'],
                'profile_scope': 'patient',
                'component_id': ids['exact'],
            },
        ).one()
        week_location = int(
            connection.execute(
                text(
                    'UPDATE cafeteria.menu_weeks SET location_id=:location_id '
                    'WHERE id=:week_id RETURNING location_id'
                ),
                {'location_id': ids['location'], 'week_id': ids['week']},
            ).scalar_one()
        )
        linked_rows = int(
            connection.execute(
                text(
                    'SELECT count(*) FROM cafeteria.menu_item_components '
                    'WHERE menu_item_id=:item_id'
                ),
                {'item_id': ids['item']},
            ).scalar_one()
        )

    assert component_identity == (ids['location'], 'patient')
    assert week_location == ids['location']
    assert linked_rows == 3
