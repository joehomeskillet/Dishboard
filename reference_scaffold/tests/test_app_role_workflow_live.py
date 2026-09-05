"""Live PostgreSQL test for app-role publication workflow with trigger validator dependencies."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.engine.url import make_url

from cafeteria.db import init_database, upsert_entra_user
from cafeteria.workflow import import_draft, publish_draft

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


def _generate_week_days(start_date: date, num_days: int) -> list[dict]:
    """Generate a week of days for workflow import."""
    days = []
    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        day_dict = {
            'date': current_date.isoformat(),
            'services': [
                {
                    'meal_code': 'LUNCH',
                    'service_state': 'open',
                    'notice': '',
                    'options': [
                        {
                            'type_code': 'MENU_1',
                            'title': 'Gericht Eins',
                            'components': [],
                            'allergen_review_status': 'checked',
                        },
                        {
                            'type_code': 'VEGGIE',
                            'title': 'Vegetarisch',
                            'components': [],
                            'allergen_review_status': 'checked',
                        },
                    ],
                },
            ],
        }
        # Patient profile: add DINNER service
        if num_days == 7:
            day_dict['services'].append({
                'meal_code': 'DINNER',
                'service_state': 'open',
                'notice': '',
                'options': [
                    {
                        'type_code': 'MENU_1',
                        'title': 'Abendgericht',
                        'components': [],
                        'allergen_review_status': 'checked',
                    },
                    {
                        'type_code': 'VEGGIE',
                        'title': 'Abend Vegetarisch',
                        'components': [],
                        'allergen_review_status': 'checked',
                    },
                ],
            })
        days.append(day_dict)
    return days


@pytest.fixture
def owner_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


@pytest.fixture
def app_engine(owner_engine: Engine) -> Iterator[Engine]:
    """Engine connected as cafeteria_app role."""
    app_url = _role_database_url('cafeteria_app', APP_PASSWORD)
    engine = create_engine(app_url, poolclass=NullPool, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def issuer_engine(owner_engine: Engine) -> Iterator[Engine]:
    """Engine connected as cafeteria_auth_issuer role."""
    issuer_url = _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD)
    engine = create_engine(issuer_url, poolclass=NullPool, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def test_app_role_publishes_patient_and_cafeteria_without_privilege_error(
    owner_engine: Engine,
    app_engine: Engine,
    issuer_engine: Engine,
) -> None:
    """Verify app role can publish both profiles without InsufficientPrivilege on trigger validators."""
    from review_support import review_saved_week

    # Create an Entra user through issuer engine
    actor_id = upsert_entra_user(
        issuer_engine,
        claims={
            'tid': '550e8400-e29b-41d4-a716-446655440000',
            'oid': '660e8400-e29b-41d4-a716-446655440001',
            'sub': 'test-user@example.com',
            'name': 'Test Publisher',
            'email': 'test@example.com',
            'preferred_username': 'testpub',
        },
        roles=['Cafeteria.Publisher'],
    )
    assert actor_id > 0

    # Prepare patient snapshot data (no price info) - 7 days for patient profile
    patient_week_start = date(2026, 9, 7)
    patient_draft_values = {
        'title': 'Patientenwochen-Test',
        'shared_note': '',
        'days': _generate_week_days(patient_week_start, 7),
    }

    # Import patient draft through app engine
    with app_engine.begin() as connection:
        connection.execute(
            text(
                '''
                DELETE FROM cafeteria.menu_weeks
                WHERE profile_id=(SELECT id FROM cafeteria.offer_profiles WHERE code='patient')
                AND week_start=CAST(:week_start AS date)
                '''
            ),
            {'week_start': str(patient_week_start)},
        )

    row_version = import_draft(
        app_engine,
        'patient',
        patient_week_start,
        expected_row_version=0,
        actor_id=actor_id,
        values=patient_draft_values,
    )
    assert row_version >= 1
    row_version = review_saved_week(app_engine, 'patient', patient_week_start, actor_id)

    # Publish patient profile through app engine
    # This triggers validate_publication_revision() which calls jsonb_has_patient_forbidden_key()
    # and jsonb_has_patient_forbidden_value(), requiring app_engine to have EXECUTE on them
    patient_snapshot = publish_draft(
        app_engine,
        'patient',
        patient_week_start,
        expected_row_version=row_version,
        actor_id=actor_id,
        issuer_engine=None,
    )
    assert patient_snapshot is not None
    assert patient_snapshot['profile_code'] == 'patient'

    # Verify patient snapshot contains no forbidden cost tokens
    patient_json_str = json.dumps(patient_snapshot)
    for forbidden_token in ('CHF', 'Rappen', 'price', 'preis', 'kosten', 'betrag'):
        assert forbidden_token.lower() not in patient_json_str.lower()

    # Prepare cafeteria snapshot data (with prices) - only weekdays (5 days)
    cafeteria_week_start = date(2026, 9, 7)
    cafeteria_days = []
    for i in range(5):  # Monday to Friday only
        current_date = cafeteria_week_start + timedelta(days=i)
        cafeteria_days.append({
            'date': current_date.isoformat(),
            'services': [
                {
                    'meal_code': 'LUNCH',
                    'service_state': 'open',
                    'notice': '',
                    'options': [
                        {
                            'type_code': 'MENU_1',
                            'title': 'Kichererbsen-Curry',
                            'components': [],
                            'allergen_review_status': 'checked',
                            'internal_rappen': 1100,
                            'external_rappen': 1650,
                        },
                        {
                            'type_code': 'VEGGIE',
                            'title': 'Gemüse-Curry',
                            'components': [],
                            'allergen_review_status': 'checked',
                            'internal_rappen': 1100,
                            'external_rappen': 1650,
                        },
                    ],
                },
            ],
        })

    cafeteria_draft_values = {
        'title': 'Cafeteria-Wochen-Test',
        'shared_note': '',
        'days': cafeteria_days,
    }

    # Import cafeteria draft through app engine
    with app_engine.begin() as connection:
        connection.execute(
            text(
                '''
                DELETE FROM cafeteria.menu_weeks
                WHERE profile_id=(SELECT id FROM cafeteria.offer_profiles WHERE code='staff_guest')
                AND week_start=CAST(:week_start AS date)
                '''
            ),
            {'week_start': str(cafeteria_week_start)},
        )

    caf_row_version = import_draft(
        app_engine,
        'staff_guest',
        cafeteria_week_start,
        expected_row_version=0,
        actor_id=actor_id,
        values=cafeteria_draft_values,
    )
    assert caf_row_version >= 1
    caf_row_version = review_saved_week(app_engine, 'staff_guest', cafeteria_week_start, actor_id)

    # Publish cafeteria profile through app engine
    cafeteria_snapshot = publish_draft(
        app_engine,
        'staff_guest',
        cafeteria_week_start,
        expected_row_version=caf_row_version,
        actor_id=actor_id,
        issuer_engine=None,
    )
    assert cafeteria_snapshot is not None
    assert cafeteria_snapshot['profile_code'] == 'staff_guest'

    # Verify cafeteria snapshot contains price info
    cafeteria_json_str = json.dumps(cafeteria_snapshot)
    assert '1100' in cafeteria_json_str


def test_app_role_cannot_execute_privileged_functions(app_engine: Engine) -> None:
    """Verify app role cannot execute functions reserved for auth_issuer."""

    with app_engine.begin() as connection:
        # App role CAN execute patient validators
        has_normalize = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.normalize_patient_key(text)', 'EXECUTE')"
            )
        ).scalar()
        assert has_normalize is True

        has_forbidden = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.patient_key_is_forbidden(text)', 'EXECUTE')"
            )
        ).scalar()
        assert has_forbidden is True

        has_key_check = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.jsonb_has_patient_forbidden_key(jsonb)', 'EXECUTE')"
            )
        ).scalar()
        assert has_key_check is True

        has_value_check = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.jsonb_has_patient_forbidden_value(jsonb)', 'EXECUTE')"
            )
        ).scalar()
        assert has_value_check is True

        # App role CANNOT execute auth issuer functions
        cannot_provision = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.provision_local_user(text, text, text, text, text[])', 'EXECUTE')"
            )
        ).scalar()
        assert cannot_provision is False

        cannot_sync_entra = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.sync_entra_user(uuid, uuid, text, text, text, text, text[])', 'EXECUTE')"
            )
        ).scalar()
        assert cannot_sync_entra is False

        cannot_issue_capability = connection.execute(
            text(
                "SELECT has_function_privilege(current_user, 'cafeteria.issue_publication_capability(bigint, bigint, interval)', 'EXECUTE')"
            )
        ).scalar()
        assert cannot_issue_capability is False
