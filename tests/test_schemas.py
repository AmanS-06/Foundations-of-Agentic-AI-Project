"""The schemas accept valid data, convert CSV strings to proper types, and reject bad data."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from zeroplate import config
from zeroplate.schemas import (
    CalendarEvent,
    Event,
    LeftoverBatch,
    NoteEvent,
    ProductionPlan,
    Review,
    TraceStep,
)


def test_csv_strings_are_converted_to_types():
    # CSV readers give strings; Pydantic turns them into date / enum values.
    row = CalendarEvent(date="2026-10-16", weekday="Friday", event="fest", weather="sunny")
    assert row.date == date(2026, 10, 16)
    assert row.event is Event.FEST


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CalendarEvent(date="2026-10-16", weekday="Fri", event="fest", weather="sunny", temp=31)


def test_unknown_event_is_rejected():
    with pytest.raises(ValidationError):
        CalendarEvent(date="2026-10-16", weekday="Fri", event="party", weather="sunny")


def test_review_verdict_is_restricted():
    with pytest.raises(ValidationError):
        Review(verdict="highly_unfavorable", checks=[], feedback="", attempt=0)
    assert (
        Review(verdict="revise", checks=[], feedback="over budget", attempt=1).verdict == "revise"
    )


def test_note_factor_must_be_plausible():
    assert NoteEvent(kind="demand_change", factor=1.2, text="+20%").factor == 1.2
    with pytest.raises(ValidationError):
        NoteEvent(kind="demand_change", factor=50, text="cook 50x")  # injection-style value


def test_negative_quantities_are_rejected():
    with pytest.raises(ValidationError):
        LeftoverBatch(
            batch_id="B1",
            dish="dal",
            cooked_at=datetime(2026, 10, 15, 12),
            plates_left=-3,
            holding="hot",
            temp_c=60,
            reheated_count=0,
        )


def test_production_plan_needs_at_least_one_dish():
    with pytest.raises(ValidationError):
        ProductionPlan(
            plan_date="2026-10-16",
            dishes=[],
            ingredients=[],
            purchases=[],
            food_cost=0,
            purchase_cost=0,
            total_cost=0,
            candidates=[],
            chosen_buffer=0,
            summary="",
        )


def test_models_round_trip_through_json():
    # Agents exchange JSON; a model must survive model -> JSON -> model unchanged.
    step = TraceStep(
        agent="research", thought="check calendar", tool="education.get_calendar_event"
    )
    assert TraceStep.model_validate_json(step.model_dump_json()) == step


def test_config_weights_give_three_quarter_quantile():
    # Stocking calculation: optimal service level = shortage / (shortage + waste) = 0.75.
    level = config.SHORTAGE_WEIGHT / (config.SHORTAGE_WEIGHT + config.WASTE_WEIGHT)
    assert level == pytest.approx(0.75)
    assert max(config.CANDIDATE_BUFFERS) <= config.C2_MAX_BUFFER
