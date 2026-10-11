"""Demand forecast for one dish: an ensemble of three simple methods, plus a measured spread.

Ensemble consensus: three different methods each estimate tomorrow's demand, and the median
is used. (This is an ensemble, not "self-consistency", which means sampling one language model
several times and taking the majority answer.)

1. event_average     mean demand on recent past days of the SAME event type (fest vs fests).
2. event_trend       the same days, but recent ones weigh more (exponential smoothing).
3. attendance_ratio  plates per student present on recent days x tomorrow's expected attendance.
                     Attendance already reflects the event, so no event factor is applied here
                     (applying one would count the event twice).

Spread: how wrong this kind of forecast has been in the past. We replay history ("backtest"):
for each recent day, forecast it from the days before it, and record the relative error.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import date

from zeroplate import config
from zeroplate.schemas import DishForecast, Event, HistoryRow

EVENT_WINDOW = 8  # same-event days used by methods 1 and 2
TREND_ALPHA = 0.5  # smoothing weight of the most recent day in method 2
UPTAKE_WINDOW = 28  # recent days used for plates-per-student in method 3
BACKTEST_DAYS = 90  # recent days replayed to measure the spread
DISAGREEMENT_LIMIT = 0.20  # methods differing by more than 20% -> low confidence


def event_average(demands: list[float]) -> float:
    """Method 1: plain mean of the most recent same-event demands."""
    return statistics.fmean(demands[-EVENT_WINDOW:])


def event_trend(demands: list[float]) -> float:
    """Method 2: exponentially smoothed same-event demands (oldest first)."""
    level = demands[-EVENT_WINDOW:][0]
    for d in demands[-EVENT_WINDOW:][1:]:
        level = TREND_ALPHA * d + (1 - TREND_ALPHA) * level
    return level


def attendance_ratio(uptakes: list[float], expected_present: int) -> float:
    """Method 3: median plates-per-student (recent days) x tomorrow's attendance."""
    return statistics.median(uptakes[-UPTAKE_WINDOW:]) * expected_present


def _same_event_demands(rows: list[HistoryRow], events: dict[date, Event], event: Event):
    return [float(r.demand) for r in rows if events.get(r.date) == event]


def _uptakes(rows: list[HistoryRow], present: dict[date, int]) -> list[float]:
    return [r.demand / present[r.date] for r in rows if present.get(r.date)]


def _methods(rows, events, present, event, expected_present) -> dict[str, float]:
    """Run every method that has enough data. `rows` must be sorted oldest first."""
    out: dict[str, float] = {}
    same = _same_event_demands(rows, events, event)
    if same:
        out["event_average"] = event_average(same)
        out["event_trend"] = event_trend(same)
    uptakes = _uptakes(rows, present)
    if uptakes and expected_present:
        out["attendance_ratio"] = attendance_ratio(uptakes, expected_present)
    return out


def relative_errors(
    rows: list[HistoryRow], events: dict[date, Event], present: dict[date, int]
) -> list[float]:
    """Backtest: forecast each of the last BACKTEST_DAYS days from the days before it."""
    errors = []
    for i in range(max(len(rows) - BACKTEST_DAYS, 1), len(rows)):
        day = rows[i]
        est = _methods(rows[:i], events, present, events[day.date], present.get(day.date, 0))
        if est:
            pred = statistics.median(est.values())
            if pred > 0:
                errors.append((day.demand - pred) / pred)
    return errors


def forecast_dish(
    dish: str,
    history: Iterable[HistoryRow],
    events: dict[date, Event],
    present: dict[date, int],
    plan_date: date,
    note_factor: float = 1.0,
) -> DishForecast:
    """Forecast `dish` for `plan_date` using only history from before that date.

    `events` and `present` map dates to the calendar event and expected attendance; they must
    include `plan_date`. `note_factor` is a manager adjustment read from the free-text note
    (e.g. 1.2 = "expect 20% more"), already validated to lie in (0, 3].
    """
    rows = sorted(
        (r for r in history if r.dish == dish and r.date < plan_date), key=lambda r: r.date
    )
    if not rows:
        raise ValueError(f"no history for {dish!r} before {plan_date}")
    methods = _methods(rows, events, present, events[plan_date], present.get(plan_date, 0))
    if not methods:
        raise ValueError(f"not enough data to forecast {dish!r} on {plan_date}")

    mean = statistics.median(methods.values()) * note_factor
    errors = relative_errors(rows, events, present)
    rel_spread = statistics.pstdev(errors) if len(errors) > 1 else 0.0
    spread = mean * max(rel_spread, config.MIN_SPREAD_FRACTION)

    spread_of_methods = (max(methods.values()) - min(methods.values())) / max(mean, 1e-9)
    low_confidence = len(methods) < 3 or spread_of_methods > DISAGREEMENT_LIMIT
    return DishForecast(
        dish=dish,
        mean=round(mean, 1),
        spread=round(spread, 1),
        methods={k: round(v, 1) for k, v in methods.items()},
        low_confidence=low_confidence,
    )
