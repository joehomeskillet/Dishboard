from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.db import active_snapshot
from cafeteria.workflow import (
    PublicationConfigurationError,
    StaleDraftError,
    WorkflowValidationError,
    derive_admin_status,
    load_draft,
    publish_draft,
    publish_draft_scoped,
    save_draft,
)
from cafeteria.workflow_snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)
WEEK_START = date(2026, 8, 31)

APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'



def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.init_database(
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


def _actor_id(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                text(
                    "SELECT id FROM cafeteria.users "
                    "WHERE public_id='00000000-0000-0000-0000-000000000002'"
                )
            ).scalar_one()
        )


def _patient_values(title: str = 'Herbstküche') -> dict[str, Any]:
    meals = (('LUNCH', 'Mittag'), ('DINNER', 'Abend'))
    types = (('MENU_1', 'Kartoffelgratin'), ('VEGGIE', 'Gemüseteller'))
    days = []
    for offset in range(7):
        service_date = WEEK_START + timedelta(days=offset)
        services = []
        for meal_code, _meal_name in meals:
            services.append(
                {
                    'meal_code': meal_code,
                    'service_state': 'open',
                    'notice': '',
                    'options': [
                        {
                            'type_code': type_code,
                            'title': dish_title,
                            'components': ['Blattsalat'],
                            'allergen_review_status': 'checked',
                        }
                        for type_code, dish_title in types
                    ],
                }
            )
        days.append({'date': service_date.isoformat(), 'services': services})
    return {'title': title, 'shared_note': 'Frisch gekocht', 'days': days}


def _staff_values(title: str = 'Cafeteria Herbst') -> dict[str, Any]:
    days = []
    for offset in range(5):
        service_date = WEEK_START + timedelta(days=offset)
        days.append(
            {
                'date': service_date.isoformat(),
                'services': [
                    {
                        'meal_code': 'LUNCH',
                        'service_state': 'open',
                        'notice': '',
                        'options': [
                            {
                                'type_code': 'MENU_1',
                                'title': f'Tagesmenü {offset + 1}',
                                'components': ['Salat'],
                                'allergen_review_status': 'checked',
                                'internal_rappen': 950,
                                'external_rappen': 1450,
                            },
                            {
                                'type_code': 'VEGGIE',
                                'title': f'Vegetarisch {offset + 1}',
                                'components': ['Gemüse'],
                                'allergen_review_status': 'checked',
                                'internal_rappen': 850,
                                'external_rappen': 1350,
                            },
                        ],
                    }
                ],
            }
        )
    return {'title': title, 'shared_note': 'Mittagsangebot', 'days': days}


def _save(engine: Engine, profile: str, values: dict[str, Any]) -> int:
    actor_id = _actor_id(engine)
    draft = load_draft(engine, profile, WEEK_START, actor_id=actor_id)
    return save_draft(
        engine,
        profile,
        WEEK_START,
        expected_row_version=draft['row_version'],
        actor_id=actor_id,
        values=values,
    )


def _historical_publication(engine: Engine, actor_id: int, suffix: str) -> int:
    revision_number = {'R1': 8, 'R2': 9}[suffix]
    revision_code = f'PAT-2026-KW36-R{revision_number}'
    location = {
        'R1': {'code': 'OLD_NORD', 'name': 'Altstandort Nord'},
        'R2': {'code': 'OLD_SUED', 'name': 'Altstandort Sued'},
    }[suffix]
    snapshot = build_snapshot(
        'patient',
        {**_patient_values(), 'week_start': WEEK_START.isoformat(), 'location': location},
        revision_code,
    )
    with engine.begin() as connection:
        location_id = connection.execute(
            text(
                'INSERT INTO cafeteria.locations(code, name, active) '
                'VALUES (:code, :name, false) RETURNING id'
            ),
            location,
        ).scalar_one()
        week_id = connection.execute(
            text(
                "INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start, "
                "workflow_state, title, created_by, updated_by) "
                "SELECT :location_id, id, :week_start, 'published', :title, :actor_id, :actor_id "
                "FROM cafeteria.offer_profiles WHERE code='patient' RETURNING id"
            ),
            {
                'location_id': location_id,
                'week_start': WEEK_START,
                'title': snapshot['title'],
                'actor_id': actor_id,
            },
        ).scalar_one()
        return int(
            connection.execute(
                text(
                    'INSERT INTO cafeteria.publication_revisions('
                    'menu_week_id, revision_number, revision_code, snapshot_json, published_by) '
                'VALUES (:week_id, :number, :code, CAST(:snapshot AS jsonb), :actor_id) RETURNING id'
                ),
                {
                    'week_id': week_id,
                    'number': revision_number,
                    'code': revision_code,
                    'snapshot': json.dumps(snapshot, ensure_ascii=False),
                    'actor_id': actor_id,
                },
            ).scalar_one()
        )


def test_patient_draft_persists_sunday_lunch_and_dinner_without_cost_rows(
    database_engine: Engine,
) -> None:
    row_version = _save(database_engine, 'patient', _patient_values())

    with database_engine.connect() as connection:
        sunday = connection.execute(
            text(
                '''
                SELECT mp.code, count(i.id) AS item_count, count(pr.menu_item_id) AS cost_count
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                WHERE p.code='patient' AND s.service_date=DATE '2026-09-06'
                GROUP BY mp.code
                ORDER BY mp.code
                '''
            )
        ).all()
        totals = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id), count(DISTINCT i.id), count(pr.menu_item_id)
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                WHERE p.code='patient'
                '''
            )
        ).one()

    assert row_version == 2
    assert [(row.code, row.item_count, row.cost_count) for row in sunday] == [
        ('DINNER', 2, 0),
        ('LUNCH', 2, 0),
    ]
    assert tuple(totals) == (14, 28, 0)


def test_staff_draft_has_only_five_lunches_and_closed_service_has_no_items(
    database_engine: Engine,
) -> None:
    values = _staff_values()
    values['days'][2]['services'][0]['service_state'] = 'closed'
    values['days'][2]['services'][0]['notice'] = 'Cafeteria geschlossen'
    _save(database_engine, 'staff_guest', values)

    with database_engine.connect() as connection:
        shape = connection.execute(
            text(
                '''
                SELECT count(DISTINCT s.id) AS services,
                       count(DISTINCT i.id) AS items,
                       count(DISTINCT pr.menu_item_id) AS costs,
                       count(*) FILTER (WHERE EXTRACT(ISODOW FROM s.service_date) > 5) AS weekends,
                       count(*) FILTER (WHERE mp.code <> 'LUNCH') AS non_lunch
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id
                WHERE p.code='staff_guest'
                '''
            )
        ).one()
        closed = connection.execute(
            text(
                '''
                SELECT s.service_state, s.notice, count(i.id) AS items
                FROM cafeteria.menu_services s
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                WHERE p.code='staff_guest' AND s.service_date=DATE '2026-09-02'
                GROUP BY s.id
                '''
            )
        ).one()

    assert tuple(shape) == (5, 8, 8, 0, 0)
    assert tuple(closed) == ('closed', 'Cafeteria geschlossen', 0)


def test_stale_row_version_rejects_entire_update(database_engine: Engine) -> None:
    actor_id = _actor_id(database_engine)
    draft = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    first_version = save_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=draft['row_version'],
        actor_id=actor_id,
        values=_patient_values('Herbstküche'),
    )

    with pytest.raises(StaleDraftError):
        save_draft(
            database_engine,
            'patient',
            WEEK_START,
            expected_row_version=draft['row_version'],
            actor_id=actor_id,
            values=_patient_values('Winterküche'),
        )

    current = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    assert first_version == 2
    assert current['row_version'] == 2
    assert current['title'] == 'Herbstküche'
    assert current['days'][6]['services'][1]['options'][1]['title'] == 'Gemüseteller'


def test_profile_publications_are_independent_and_unsent_draft_is_not_public(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    patient_version = _save(database_engine, 'patient', _patient_values())
    staff_version = _save(database_engine, 'staff_guest', _staff_values())

    patient_first = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=patient_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    staff_first = publish_draft(
        database_engine,
        'staff_guest',
        WEEK_START,
        expected_row_version=staff_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    published_patient = active_snapshot(database_engine, 'patient', '2026-09-02')
    published_staff = active_snapshot(database_engine, 'staff_guest', '2026-09-02')

    patient_draft = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    draft_version = save_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=patient_draft['row_version'],
        actor_id=actor_id,
        values=_patient_values('Winterküche'),
    )
    still_public = active_snapshot(database_engine, 'patient', '2026-09-02')
    patient_second = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=draft_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )

    assert published_patient == patient_first
    assert published_staff == staff_first
    assert still_public == patient_first
    assert patient_second['revision_id'] != patient_first['revision_id']
    assert patient_second['title'] == 'Winterküche'
    assert active_snapshot(database_engine, 'staff_guest', '2026-09-02') == staff_first
    assert active_snapshot(database_engine, 'patient')['revision_id'] == patient_second['revision_id']
    assert active_snapshot(database_engine, 'patient', '2026-09-06')['revision_id'] == patient_second['revision_id']


def test_admin_status_is_derived_from_saved_content_not_workflow_enum(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'empty'

    _save(database_engine, 'patient', _patient_values())
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'ready'
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE cafeteria.menu_items SET allergen_review_status='not_checked' "
                'WHERE id=(SELECT min(id) FROM cafeteria.menu_items)'
            )
        )
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'review_open'
    with database_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))

    current = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    publish_draft(
        database_engine, 'patient', WEEK_START,
        expected_row_version=current['row_version'], actor_id=actor_id,
        issuer_engine=database_engine,
    )
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'live'
    changed = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    save_draft(
        database_engine, 'patient', WEEK_START,
        expected_row_version=changed['row_version'], actor_id=actor_id,
        values=_patient_values('Geänderte Woche'),
    )
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'changed'
    with database_engine.begin() as connection:
        connection.execute(
            text('DELETE FROM cafeteria.menu_items WHERE id=(SELECT min(id) FROM cafeteria.menu_items)')
        )
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'incomplete'


def test_publish_ignores_multiple_active_revisions_from_inactive_locations(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    historical_ids = {
        _historical_publication(database_engine, actor_id, 'R1'),
        _historical_publication(database_engine, actor_id, 'R2'),
    }
    version = _save(database_engine, 'patient', _patient_values('Aktiver Standort'))

    published = publish_draft(
        database_engine, 'patient', WEEK_START,
        expected_row_version=version, actor_id=actor_id, issuer_engine=None,
    )

    with database_engine.connect() as connection:
        still_active = set(
            connection.execute(
                text(
                    'SELECT id FROM cafeteria.publication_revisions '
                    'WHERE id=ANY(CAST(:ids AS bigint[])) AND withdrawn_at IS NULL'
                ),
                {'ids': sorted(historical_ids)},
            ).scalars()
        )
        active_location_code = connection.execute(
            text(
                'SELECT l.code FROM cafeteria.publication_revisions r '
                'JOIN cafeteria.locations l ON l.id=r.location_id '
                'WHERE r.revision_code=:code'
            ),
            {'code': published['revision_id']},
        ).scalar_one()
    assert still_active == historical_ids
    assert active_location_code == 'KIRCHLINDACH'


def test_publish_scope_rejects_location_cutover_without_mutation(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    version = _save(database_engine, 'patient', _patient_values('Alter Standort'))
    with database_engine.begin() as connection:
        old_location_id = int(
            connection.execute(
                text("SELECT id FROM cafeteria.locations WHERE code='KIRCHLINDACH'")
            ).scalar_one()
        )
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(
            text("INSERT INTO cafeteria.locations(code, name) VALUES ('NORD', 'Nordküche')")
        )

    with pytest.raises(StaleDraftError, match='Standort'):
        publish_draft_scoped(
            database_engine,
            'patient',
            WEEK_START,
            expected_row_version=version,
            actor_id=actor_id,
            issuer_engine=database_engine,
            expected_location_id=old_location_id,
        )

    with database_engine.connect() as connection:
        assert connection.execute(
            text('SELECT count(*) FROM cafeteria.publication_revisions')
        ).scalar_one() == 0


def test_revision_sequence_is_global_across_location_cutover(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    first_values = _staff_values('Süd')
    first_version = _save(database_engine, 'staff_guest', first_values)
    first = publish_draft(
        database_engine,
        'staff_guest',
        WEEK_START,
        expected_row_version=first_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(
            text("INSERT INTO cafeteria.locations(code, name) VALUES ('NORD', 'Nordküche')")
        )

    north_values = _staff_values('Nord')
    for day in north_values['days']:
        for service in day['services']:
            for option in service['options']:
                option['external_id'] = (
                    f"NORD-{day['date']}-{service['meal_code']}-{option['type_code']}"
                )
    second_version = _save(database_engine, 'staff_guest', north_values)
    second = publish_draft(
        database_engine,
        'staff_guest',
        WEEK_START,
        expected_row_version=second_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )

    assert first['revision_id'] == 'CAF-2026-KW36-R1'
    assert second['revision_id'] == 'CAF-2026-KW36-R2'
    assert re.fullmatch(r'(?:PAT|CAF)-\d{4}-KW\d{2}-R[1-9]\d*', second['revision_id'])


def test_revision_code_uses_iso_year_across_december_30_boundary(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    snapshots = []
    for week_start, title, expected_code in (
        (date(2024, 1, 1), 'Winterwoche', 'PAT-2024-KW01-R1'),
        (date(2024, 12, 30), 'Jahreswechsel', 'PAT-2025-KW01-R1'),
    ):
        values = _patient_values(title)
        for offset, day in enumerate(values['days']):
            day['date'] = (week_start + timedelta(days=offset)).isoformat()
        draft = load_draft(database_engine, 'patient', week_start, actor_id=actor_id)
        version = save_draft(
            database_engine,
            'patient',
            week_start,
            expected_row_version=int(draft['row_version']),
            actor_id=actor_id,
            values=values,
        )
        snapshots.append(
            publish_draft(
                database_engine,
                'patient',
                week_start,
                expected_row_version=version,
                actor_id=actor_id,
                issuer_engine=database_engine,
            )
        )
        assert snapshots[-1]['revision_id'] == expected_code

    assert [snapshot['revision_id'] for snapshot in snapshots] == [
        'PAT-2024-KW01-R1',
        'PAT-2025-KW01-R1',
    ]


def test_published_payloads_keep_profile_shapes_and_patient_has_no_cost_tokens(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    patient_version = _save(database_engine, 'patient', _patient_values())
    staff_version = _save(database_engine, 'staff_guest', _staff_values())
    patient = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=patient_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    staff = publish_draft(
        database_engine,
        'staff_guest',
        WEEK_START,
        expected_row_version=staff_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )

    patient_text = json.dumps(patient, ensure_ascii=False).casefold()
    assert len(patient['days']) == 7
    assert all(
        {service['meal_code'] for service in day['services']} == {'LUNCH', 'DINNER'}
        for day in patient['days']
    )
    assert re.search(r'\b(chf|intern|extern|rappen|preis)\b|0\.00', patient_text) is None
    assert [len(day['services']) for day in staff['days']] == [1, 1, 1, 1, 1, 0, 0]
    assert all(
        option['prices']['external_rappen'] >= option['prices']['internal_rappen']
        for day in staff['days'][:5]
        for option in day['services'][0]['options']
    )


def test_publish_rejects_open_option_without_allergen_review_status(
    database_engine: Engine,
) -> None:
    actor_id = _actor_id(database_engine)
    values = _patient_values()
    option = values['days'][0]['services'][0]['options'][0]
    del option['allergen_review_status']
    version = _save(database_engine, 'patient', values)

    with pytest.raises(
        WorkflowValidationError,
        match='Allergendeklaration ist nicht geprüft',
    ) as error:
        publish_draft(
            database_engine,
            'patient',
            WEEK_START,
            expected_row_version=version,
            actor_id=actor_id,
            issuer_engine=database_engine,
        )

    assert error.value.field_name == 'service_0_LUNCH_MENU_1_allergen_reviewed'


def test_closure_is_scoped_to_date_profile_and_meal(database_engine: Engine) -> None:
    values = _patient_values()
    sunday_dinner = values['days'][6]['services'][1]
    sunday_dinner['service_state'] = 'closed'
    sunday_dinner['notice'] = 'Küche geschlossen'
    _save(database_engine, 'patient', values)

    draft = load_draft(
        database_engine,
        'patient',
        WEEK_START,
        actor_id=_actor_id(database_engine),
    )
    sunday = draft['days'][6]
    lunch, dinner = sunday['services']
    assert lunch['meal_code'] == 'LUNCH'
    assert lunch['service_state'] == 'open'
    assert len(lunch['options']) == 2
    assert dinner['meal_code'] == 'DINNER'
    assert dinner['service_state'] == 'closed'
    assert dinner['notice'] == 'Küche geschlossen'
    assert all(not option['title'] for option in dinner['options'])


def test_failed_publish_does_not_withdraw_previous_revision(database_engine: Engine) -> None:
    actor_id = _actor_id(database_engine)
    version = _save(database_engine, 'patient', _patient_values())
    first = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    draft = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor_id)
    changed = deepcopy(_patient_values('Winterküche'))
    changed['days'][0]['services'][0]['options'][0]['title'] = 'CHF Menü'

    with pytest.raises(ValueError):
        save_draft(
            database_engine,
            'patient',
            WEEK_START,
            expected_row_version=draft['row_version'],
            actor_id=actor_id,
            values=changed,
        )

    assert active_snapshot(database_engine, 'patient', '2026-09-02') == first


def test_missing_replacement_capability_fails_explicitly_without_mutation(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id = _actor_id(database_engine)
    first_version = _save(database_engine, 'patient', _patient_values('Erste Revision'))
    first = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=first_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    second_version = _save(database_engine, 'patient', _patient_values('Zweite Revision'))
    monkeypatch.setattr(
        'cafeteria.workflow.issue_publication_capability',
        lambda *_args: None,
    )

    with pytest.raises(PublicationConfigurationError, match='Capability'):
        publish_draft(
            database_engine,
            'patient',
            WEEK_START,
            expected_row_version=second_version,
            actor_id=actor_id,
            issuer_engine=database_engine,
        )

    assert active_snapshot(database_engine, 'patient', '2026-09-02') == first
    with database_engine.connect() as connection:
        revisions = connection.execute(
            text(
                'SELECT count(*), count(*) FILTER (WHERE withdrawn_at IS NULL) '
                'FROM cafeteria.publication_revisions'
            )
        ).one()
    assert tuple(revisions) == (1, 1)


def test_snapshot_keeps_distinct_notice_for_each_closed_meal(
    database_engine: Engine,
) -> None:
    """Dropping service.notice collapses two closures into one day-level notice."""
    actor_id = _actor_id(database_engine)
    values = _patient_values()
    lunch, dinner = values['days'][0]['services']
    lunch.update(service_state='closed', notice='Mittagsservice geschlossen')
    dinner.update(service_state='holiday', notice='Abendservice entfällt')
    version = _save(database_engine, 'patient', values)

    published = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )

    services = published['days'][0]['services']
    assert [(service['meal_code'], service['service_state'], service['notice']) for service in services] == [
        ('LUNCH', 'closed', 'Mittagsservice geschlossen'),
        ('DINNER', 'holiday', 'Abendservice entfällt'),
    ]
    assert all(service['options'] == [] for service in services)


@pytest.mark.parametrize('profile_code', ('patient', 'staff_guest'))
@pytest.mark.parametrize('overflow_kind', ('title', 'components'))
def test_publish_rejects_signage_overflow_without_replacing_active_revision(
    database_engine: Engine,
    profile_code: str,
    overflow_kind: str,
) -> None:
    actor_id = _actor_id(database_engine)
    values_factory = _patient_values if profile_code == 'patient' else _staff_values
    initial_version = _save(database_engine, profile_code, values_factory())
    initial = publish_draft(
        database_engine,
        profile_code,
        WEEK_START,
        expected_row_version=initial_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    draft = load_draft(database_engine, profile_code, WEEK_START, actor_id=actor_id)
    changed = values_factory()
    option = changed['days'][0]['services'][0]['options'][0]
    if overflow_kind == 'title':
        option['title'] = 'G' * 37
    else:
        option['components'] = ['B' * 49]
    changed_version = save_draft(
        database_engine,
        profile_code,
        WEEK_START,
        expected_row_version=draft['row_version'],
        actor_id=actor_id,
        values=changed,
    )

    with pytest.raises(WorkflowValidationError):
        publish_draft(
            database_engine,
            profile_code,
            WEEK_START,
            expected_row_version=changed_version,
            actor_id=actor_id,
            issuer_engine=database_engine,
        )

    with database_engine.connect() as connection:
        revision_count = connection.execute(
            text('SELECT count(*) FROM cafeteria.publication_revisions')
        ).scalar_one()
    assert revision_count == 1
    assert active_snapshot(database_engine, profile_code, '2026-09-02') == initial


@pytest.mark.parametrize('profile_code', ('patient', 'staff_guest'))
def test_publish_accepts_strict_shared_signage_boundaries(
    database_engine: Engine,
    profile_code: str,
) -> None:
    actor_id = _actor_id(database_engine)
    values = _patient_values() if profile_code == 'patient' else _staff_values()
    option = values['days'][0]['services'][0]['options'][0]
    option['title'] = 'G' * 36
    option['components'] = ['B' * 48]
    version = _save(database_engine, profile_code, values)

    published = publish_draft(
        database_engine,
        profile_code,
        WEEK_START,
        expected_row_version=version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )

    published_option = published['days'][0]['services'][0]['options'][0]
    assert published_option['title'] == 'G' * 36
    assert published_option['components'] == ['B' * 48]
