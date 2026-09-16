"""CAL-READ range reader against real PostgreSQL menu_services."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

from cafeteria.calendar_reads import list_calendar_range
from prepared_food_fixtures import app_engine, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe


def test_list_calendar_range_returns_only_inclusive_service_dates(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    with seeded_pg16.connect() as connection:
        bounds = connection.execute(text(
            'SELECT min(s.service_date), max(s.service_date) FROM cafeteria.menu_services s '
            'JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id WHERE w.location_id=:location'
        ), {'location': ids['location']}).one()
    start, end = bounds
    assert start is not None and end is not None
    inner_end = min(end, start + timedelta(days=2))
    rows = list_calendar_range(app_engine, ids['location'], start, inner_end)
    assert rows
    dates = {row['service_date'] if not isinstance(row['service_date'], date)
             else row['service_date'] for row in rows}
    # asyncpg/psycopg may return datetime.date
    as_dates = {value if isinstance(value, date) else value for value in dates}
    assert all(start <= value <= inner_end for value in as_dates)
    outside = list_calendar_range(
        app_engine, ids['location'], inner_end + timedelta(days=30), inner_end + timedelta(days=40),
    )
    assert outside == ()
