"""CAL-READ: Zurich today and a single inclusive service_date range query."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from cafeteria import calendar_reads
from cafeteria.calendar_reads import effective_today, list_calendar_range


def test_effective_today_uses_europe_zurich() -> None:
    utc = datetime(2026, 9, 16, 22, 30, tzinfo=ZoneInfo('UTC'))
    assert effective_today(now=utc) == date(2026, 9, 17)


def test_list_calendar_range_sql_is_one_between_query() -> None:
    assert calendar_reads._SERVICES.count('SELECT') == 1
    assert 'BETWEEN :start AND :end' in calendar_reads._SERVICES
    assert list_calendar_range.__doc__ is not None

