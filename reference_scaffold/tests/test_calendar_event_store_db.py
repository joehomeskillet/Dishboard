"""CAL-EVENTS-SCHEMA: kitchen event header store on real PostgreSQL."""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import text

from cafeteria.calendar_event_store import (
    CalendarEventConflictError, CalendarEventValidationError, EventScope,
    create_event, get_event, list_events, update_event,
)
from prepared_food_fixtures import app_engine, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor


def _scope(ids) -> EventScope:
    return EventScope(ids['actor'], ids['location'], ids['authz'])


def test_create_list_and_guest_count_does_not_create_recipe_link(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        connection.execute(text(
            'UPDATE cafeteria.locations SET active=false WHERE id=:other_location'
        ), ids)
    public_id = create_event(
        app_engine, _scope(ids), event_date=date(2026, 9, 20), title='Betriebsausflug',
        profile_scope='both', guest_count=12, note='Nur Küche', starts_at=time(11, 0), ends_at=time(14, 0),
    )
    row = get_event(app_engine, ids['location'], public_id)
    assert row['title'] == 'Betriebsausflug'
    assert row['guest_count'] == 12
    assert row['profile_scope'] == 'both'
    listed = list_events(app_engine, ids['location'], date(2026, 9, 1), date(2026, 9, 30))
    assert any(item['public_id'] == row['public_id'] for item in listed)
    with seeded_pg16.connect() as connection:
        columns = connection.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='cafeteria' AND table_name='kitchen_events'"
        )).scalars().all()
        week_state = connection.execute(text(
            'SELECT workflow_state FROM cafeteria.menu_weeks WHERE location_id=:location LIMIT 1'
        ), ids).scalar_one()
    assert 'recipe_revision_id' not in columns
    assert 'menu_item_id' not in columns
    assert week_state in ('draft', 'ready', 'published', 'archived')


def test_update_cas_and_invalid_scope(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as connection:
        connection.execute(text(
            'UPDATE cafeteria.locations SET active=false WHERE id=:other_location'
        ), ids)
    public_id = create_event(
        app_engine, _scope(ids), event_date=date(2026, 9, 21), title='Mittag',
        profile_scope='patient', guest_count=0,
    )
    with pytest.raises(CalendarEventValidationError):
        create_event(
            app_engine, _scope(ids), event_date=date(2026, 9, 21), title='X',
            profile_scope='cafeteria',
        )
    row = get_event(app_engine, ids['location'], public_id)
    with pytest.raises(CalendarEventConflictError):
        update_event(
            app_engine, _scope(ids), public_id, expected_row_version=int(row['row_version']) + 9,
            title='Mittag', profile_scope='patient', guest_count=1, note=None,
            event_date=date(2026, 9, 21), starts_at=None, ends_at=None,
        )
    update_event(
        app_engine, _scope(ids), public_id, expected_row_version=int(row['row_version']),
        title='Mittag intern', profile_scope='staff_guest', guest_count=3, note=None,
        event_date=date(2026, 9, 21), starts_at=None, ends_at=None,
    )
    updated = get_event(app_engine, ids['location'], public_id)
    assert updated['title'] == 'Mittag intern'
    assert updated['profile_scope'] == 'staff_guest'
    assert updated['guest_count'] == 3
    assert int(updated['row_version']) == int(row['row_version']) + 1
