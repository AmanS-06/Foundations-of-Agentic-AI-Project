"""Forecast: event-aware, no peeking at the future, honest spread, low-confidence flag."""

from datetime import date

import pytest

from zeroplate.domain.data import load_table
from zeroplate.domain.forecast import forecast_dish
from zeroplate.schemas import Event, HistoryRow

FEST = date(2026, 10, 16)
NORMAL = date(2026, 10, 14)


@pytest.fixture(scope="module")
def tables():
    history = load_table("history")
    events = {r.date: r.event for r in load_table("calendar")}
    present = {r.date: r.expected_present for r in load_table("attendance")}
    return history, events, present


def test_fest_forecast_is_close_to_true_mean(tables):
    # fixture truth: thali base demand 260 x fest factor 1.4 = 364
    f = forecast_dish("veg_thali", *tables, FEST)
    assert f.mean == pytest.approx(364, rel=0.08)
    assert set(f.methods) == {"event_average", "event_trend", "attendance_ratio"}


def test_forecast_is_event_aware(tables):
    fest = forecast_dish("veg_thali", *tables, FEST).mean
    normal = forecast_dish("veg_thali", *tables, NORMAL).mean
    assert 1.2 < fest / normal < 1.6  # fixture fest factor is 1.4


def test_future_rows_are_never_used(tables):
    history, events, present = tables
    leak = HistoryRow(
        date=FEST, dish="veg_thali", prepared=0, sold=0, demand=99999, wasted_plates=0, waste_cost=0
    )
    before = forecast_dish("veg_thali", history, events, present, FEST)
    after = forecast_dish("veg_thali", [*history, leak], events, present, FEST)
    assert before == after


def test_spread_reflects_past_errors(tables):
    f = forecast_dish("masala_chai", *tables, FEST)
    # fixture noise is 8%; the backtest should find a spread of that order
    assert 0.05 <= f.spread / f.mean <= 0.15


def test_manager_note_scales_the_forecast(tables):
    base = forecast_dish("masala_chai", *tables, FEST).mean
    more = forecast_dish("masala_chai", *tables, FEST, note_factor=1.2).mean
    assert more == pytest.approx(base * 1.2, rel=0.01)


def test_unseen_event_type_gives_low_confidence(tables):
    history, events, present = tables
    # pretend the plan date is the first holiday ever: no same-event history exists
    relabelled = {d: (Event.NORMAL if e is Event.HOLIDAY else e) for d, e in events.items()}
    relabelled[FEST] = Event.HOLIDAY
    f = forecast_dish("veg_thali", history, relabelled, present, FEST)
    assert list(f.methods) == ["attendance_ratio"]
    assert f.low_confidence


def test_unknown_dish_raises(tables):
    with pytest.raises(ValueError, match="no history"):
        forecast_dish("pizza", *tables, FEST)
