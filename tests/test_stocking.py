"""Stocking calculation: the candidates genuinely differ, and the choice matches the theory."""

from datetime import date

import pytest

from zeroplate.domain import stocking
from zeroplate.domain.data import load_table
from zeroplate.domain.forecast import forecast_dish
from zeroplate.schemas import DishForecast

FEST = date(2026, 10, 16)
BUDGET = 30000  # fixture budget on the fest day


@pytest.fixture(scope="module")
def menu():
    return {m.dish: m for m in load_table("menu")}


@pytest.fixture(scope="module")
def candidates(menu):
    history = load_table("history")
    events = {r.date: r.event for r in load_table("calendar")}
    present = {r.date: r.expected_present for r in load_table("attendance")}
    forecasts = [forecast_dish(d, history, events, present, FEST) for d in menu]
    return forecasts, stocking.generate_candidates(forecasts, menu)


def test_critical_fractile_is_three_quarters():
    assert stocking.critical_fractile() == pytest.approx(0.75)


def test_closed_form_quantity_is_mean_plus_0_67_spreads():
    f = DishForecast(dish="x", mean=100, spread=10, methods={})
    assert stocking.optimal_quantity(f) == pytest.approx(106.74, abs=0.01)


def test_more_buffer_means_more_waste_and_less_shortage(candidates):
    _, cands = candidates
    waste = [c.expected_waste_cost for c in cands]
    shortage = [c.expected_shortage_cost for c in cands]
    assert waste == sorted(waste) and shortage == sorted(shortage, reverse=True)


def test_utility_is_a_real_trade_off(candidates):
    # neither the smallest nor the largest buffer wins: the choice is not a foregone result
    _, cands = candidates
    best = stocking.choose(cands)
    assert best.buffer == 0.05
    assert best.buffer not in (min(c.buffer for c in cands), max(c.buffer for c in cands))


def test_simulated_choice_agrees_with_closed_form(candidates, menu):
    forecasts, cands = candidates
    best = stocking.choose(cands)
    for f in forecasts:
        target = stocking.optimal_quantity(f)
        assert abs(best.quantities[f.dish] - target) / target < 0.05


def test_budget_forces_a_cheaper_branch(candidates):
    # scenario S1: the best plan is over budget, so the best plan that fits is chosen
    _, cands = candidates
    assert stocking.choose(cands).food_cost > BUDGET
    within = stocking.choose(cands, max_food_cost=BUDGET)
    assert within.buffer == 0.0 and within.food_cost <= BUDGET


def test_no_candidate_fits_a_deep_cut(candidates):
    # scenario S3: a 30% budget cut cannot be met without cooking below the forecast
    _, cands = candidates
    assert stocking.choose(cands, max_food_cost=BUDGET * 0.7) is None


def test_fairness_minimum_is_respected(menu):
    tiny = [DishForecast(dish="jain_khichdi", mean=3, spread=1, methods={})]
    q = stocking.quantities_for(tiny, menu, buffer=0.0)
    assert q["jain_khichdi"] == menu["jain_khichdi"].min_portions
