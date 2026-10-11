"""Education domain: the academic calendar and expected attendance (pure functions).

No MCP imports here. The Education MCP server is a thin wrapper around these functions, and the
in-process fallback (ZEROPLATE_USE_MCP=0) calls them directly, so both paths give the same answer.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import cast

from zeroplate.domain.data import load_table
from zeroplate.schemas import Attendance, CalendarEvent, Event


def _calendar() -> list[CalendarEvent]:
    """All calendar rows, typed. load_table caches, so repeated calls are cheap."""
    return cast(list[CalendarEvent], load_table("calendar"))


def get_calendar_event(day: date) -> CalendarEvent:
    """Return the calendar entry (event type, weekday, weather) for `day`.

    Raises LookupError if the calendar has no row for that date; callers must handle it rather than
    guess, because a made-up event type would silently corrupt the forecast.
    """
    for row in _calendar():
        if row.date == day:
            return row
    raise LookupError(f"no calendar entry for {day.isoformat()}")


def get_expected_attendance(day: date) -> Attendance:
    """Return enrolled students and expected number present on `day`.

    Raises LookupError if there is no attendance row for that date.
    """
    for row in cast(list[Attendance], load_table("attendance")):
        if row.date == day:
            return row
    raise LookupError(f"no attendance entry for {day.isoformat()}")


def similar_past_days(day: date, limit: int = 10) -> list[CalendarEvent]:
    """Return up to `limit` days before `day` with the same event type, most recent first.

    The forecaster uses these as "similar days". Only strictly earlier days count: a future day's
    demand is unknown, and the day itself must never be its own evidence.
    Raises LookupError if `day` itself is not in the calendar (its event type is then unknown).
    """
    if limit < 0:
        raise ValueError(f"limit must be 0 or more, got {limit}")
    event = get_calendar_event(day).event
    earlier = [row for row in _calendar() if row.event == event and row.date < day]
    earlier.sort(key=lambda row: row.date, reverse=True)
    return earlier[:limit]


def calendar_summary() -> str:
    """Short plain-text description of the academic calendar (served as an MCP resource)."""
    rows = _calendar()
    if not rows:
        return "The academic calendar is empty."
    counts = Counter(row.event for row in rows)
    first = min(row.date for row in rows)
    last = max(row.date for row in rows)
    lines = [
        "Academic calendar",
        f"Covers {first.isoformat()} to {last.isoformat()} ({len(rows)} days).",
        "Days per event type:",
    ]
    # iterate the enum, not the counter, so every type is listed even when its count is 0
    lines += [f"- {event.value}: {counts.get(event, 0)}" for event in Event]
    return "\n".join(lines)
