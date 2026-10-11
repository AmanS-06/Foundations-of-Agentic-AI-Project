"""Unit tests of the Education domain functions on the fixture data (tests/fixtures/raw)."""

from datetime import date, timedelta

import pytest

from zeroplate.domain import education
from zeroplate.domain.data import load_table
from zeroplate.schemas import Attendance, CalendarEvent, Event

PLAN_DAY = date(2026, 10, 16)  # fixture plan date, a fest
UNKNOWN_DAY = date(2026, 1, 1)  # before the fixture calendar starts
FUTURE_DAYS = 30  # fixture holds the plan date plus 29 more days (30 days to forecast)


def test_fest_day_is_fest() -> None:
    row = education.get_calendar_event(PLAN_DAY)
    assert isinstance(row, CalendarEvent)
    assert row.date == PLAN_DAY
    assert row.event == Event.FEST


def test_attendance_fits_contract() -> None:
    row = education.get_expected_attendance(PLAN_DAY)
    assert isinstance(row, Attendance)
    assert row.date == PLAN_DAY
    assert 0 < row.expected_present <= row.enrolled


def test_similar_past_days_are_earlier_fest_days_most_recent_first() -> None:
    days = education.similar_past_days(PLAN_DAY)
    assert days, "fixture has earlier fest days"
    assert all(d.event == Event.FEST and d.date < PLAN_DAY for d in days)
    dates = [d.date for d in days]
    assert dates == sorted(dates, reverse=True)
    assert PLAN_DAY not in dates


def test_similar_past_days_respects_limit() -> None:
    assert len(education.similar_past_days(PLAN_DAY, limit=1)) == 1
    assert education.similar_past_days(PLAN_DAY, limit=0) == []
    all_days = education.similar_past_days(PLAN_DAY, limit=1000)
    assert education.similar_past_days(PLAN_DAY, limit=2) == all_days[:2]


def test_similar_past_days_rejects_negative_limit() -> None:
    with pytest.raises(ValueError):
        education.similar_past_days(PLAN_DAY, limit=-1)


@pytest.mark.parametrize("func", [education.get_calendar_event, education.get_expected_attendance])
def test_unknown_date_raises_lookup_error(func) -> None:
    with pytest.raises(LookupError, match="no .* entry for 2026-01-01"):
        func(UNKNOWN_DAY)


def test_similar_past_days_unknown_date_raises_lookup_error() -> None:
    with pytest.raises(LookupError, match="2026-01-01"):
        education.similar_past_days(UNKNOWN_DAY)


def test_every_future_date_has_attendance() -> None:
    for offset in range(FUTURE_DAYS):
        day = PLAN_DAY + timedelta(days=offset)
        assert education.get_expected_attendance(day).date == day


def test_every_calendar_date_has_attendance() -> None:
    for row in load_table("calendar"):
        assert education.get_expected_attendance(row.date).date == row.date


def test_summary_mentions_every_event_type_and_date_range() -> None:
    text = education.calendar_summary()
    for event in Event:
        assert event.value in text
    rows = load_table("calendar")
    assert min(r.date for r in rows).isoformat() in text
    assert max(r.date for r in rows).isoformat() in text


def test_all_calendar_events_returns_every_row_once():
    rows = education.all_calendar_events()
    assert len(rows) == len({r.date for r in rows}) == len(load_table("calendar"))
    assert education.get_calendar_event(date(2026, 10, 16)) in rows


def test_all_calendar_events_returns_a_copy():
    """Changing the returned list must not change the cached calendar."""
    first = education.all_calendar_events()
    first.clear()
    assert education.all_calendar_events()
