"""The synthetic data generator keeps its promises.

These tests do not just check that files appear. They check the properties the project's story
depends on: the data follows the contract, the old process wastes and runs out, the demo day
creates a budget conflict, and the scenario days have the right kind of day and weather.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from zeroplate.domain.data import check_all, load_table

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_data.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_data"] = module  # dataclasses look their own module up by name
    spec.loader.exec_module(module)
    return module


gen = _load_generator()


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    """Generate once per test module; return (folder, summary numbers)."""
    out = tmp_path_factory.mktemp("generated")
    return out, gen.generate(out)


def test_every_table_follows_the_contract(data):
    out, _ = data
    counts = check_all(out)  # raises DataError on any wrong column or invalid row
    assert counts["calendar"] == counts["attendance"] == counts["budget"] == 210
    assert counts["menu"] == 10
    assert counts["history"] == 180 * counts["menu"]


def test_same_seed_gives_identical_files(tmp_path):
    gen.generate(tmp_path / "a", seed=42)
    gen.generate(tmp_path / "b", seed=42)
    for file in (tmp_path / "a").glob("*.csv"):
        assert file.read_bytes() == (tmp_path / "b" / file.name).read_bytes()


def test_different_seed_gives_different_history(tmp_path):
    gen.generate(tmp_path / "a", seed=42)
    gen.generate(tmp_path / "b", seed=7)
    assert (tmp_path / "a" / "history.csv").read_bytes() != (
        tmp_path / "b" / "history.csv"
    ).read_bytes()


def test_committed_data_matches_the_generator(tmp_path):
    """data/raw in the repository must be exactly what `generate_data.py` produces."""
    gen.generate(tmp_path)
    committed = Path(__file__).resolve().parents[1] / "data" / "raw"
    for file in tmp_path.glob("*.csv"):
        assert (committed / file.name).read_bytes() == file.read_bytes(), file.name


# ---------------------------------------------------------------- the history is internally honest
def test_history_arithmetic_is_consistent(data):
    out, _ = data
    cost = {m.dish: m.cost_per_plate for m in load_table("menu", out)}
    for row in load_table("history", out):
        assert row.sold == min(row.demand, row.prepared)  # you cannot sell what you did not cook
        assert row.wasted_plates == row.prepared - row.sold
        assert row.waste_cost == pytest.approx(row.wasted_plates * cost[row.dish])


def test_history_covers_the_180_days_before_the_plan_date(data):
    out, _ = data
    days = sorted({r.date for r in load_table("history", out)})
    assert days[0] == gen.PLAN_DATE - timedelta(days=180)
    assert days[-1] == gen.PLAN_DATE - timedelta(days=1)
    assert len(days) == 180


def test_old_process_wastes_food_and_runs_out(data):
    """The problem we solve: waste in a believable range, and real shortages too."""
    _, stats = data
    assert 0.12 <= stats["waste_share"] <= 0.25  # the literature we cite reports 15-18%
    assert 0.02 <= stats["unmet_demand_share"] <= 0.15
    assert stats["days_with_shortage"] > 10


def test_old_process_ignores_the_calendar(data):
    """Exam days and holidays are over-produced, fest days under-produced."""
    out, _ = data
    event = {r.date: r.event.value for r in load_table("calendar", out)}
    totals: dict[str, list[int]] = {}
    for r in load_table("history", out):
        t = totals.setdefault(event[r.date], [0, 0, 0, 0])
        t[0] += r.prepared
        t[1] += r.wasted_plates
        t[2] += r.demand
        t[3] += r.demand - r.sold
    waste = {k: v[1] / v[0] for k, v in totals.items()}
    unmet = {k: v[3] / v[2] for k, v in totals.items()}
    assert waste["holiday"] > 0.5
    assert waste["exam"] > waste["normal"]
    assert unmet["fest"] > 0.2
    assert unmet["fest"] > unmet["normal"]


# ---------------------------------------------------------------- the calendar and scenario days
def test_every_event_type_appears_in_history_and_future(data):
    out, _ = data
    cal = load_table("calendar", out)
    for part in (
        [r for r in cal if r.date < gen.PLAN_DATE],
        [r for r in cal if r.date >= gen.PLAN_DATE],
    ):
        assert {r.event.value for r in part} >= {"normal", "exam", "holiday", "fest", "weekend"}


@pytest.mark.parametrize(
    ("day", "event", "weather"),
    [
        (date(2026, 10, 16), "fest", "sunny"),  # S4, the demo
        (date(2026, 10, 19), "normal", "sunny"),  # S1
        (date(2026, 10, 20), "normal", "rainy"),  # S5
        (date(2026, 10, 22), "holiday", "sunny"),  # S3
        (date(2026, 10, 27), "exam", "sunny"),  # S2
    ],
)
def test_scenario_days_are_set_up(data, day, event, weather):
    out, _ = data
    row = next(r for r in load_table("calendar", out) if r.date == day)
    assert (row.event.value, row.weather.value) == (event, weather)


def test_attendance_follows_the_event_without_double_counting(data):
    out, _ = data
    event = {r.date: r.event.value for r in load_table("calendar", out)}
    att = load_table("attendance", out)
    avg: dict[str, list[int]] = {}
    for r in att:
        avg.setdefault(event[r.date], []).append(r.expected_present)
        assert r.expected_present <= r.enrolled
    mean = {k: sum(v) / len(v) for k, v in avg.items()}
    assert mean["holiday"] < mean["weekend"] < mean["exam"] < mean["normal"] < mean["fest"]


# ---------------------------------------------------------------- menu, recipes, store, suppliers
def test_menu_covers_each_diet_and_prices_exceed_costs(data):
    out, _ = data
    menu = load_table("menu", out)
    assert {m.diet.value for m in menu} == {"veg", "nonveg", "jain"}
    assert all(m.price > m.cost_per_plate for m in menu)
    jain = [m for m in menu if m.diet.value == "jain"]
    assert len(jain) == 1 and jain[0].min_portions > 0  # the only Jain dish: rule C5 protects it


def test_jain_dish_has_no_forbidden_ingredients(data):
    out, _ = data
    jain = {m.dish for m in load_table("menu", out) if m.diet.value == "jain"}
    forbidden = {"onion", "garlic", "potato", "carrot", "tomato", "chicken", "paneer"}
    used = {r.ingredient for r in load_table("recipes", out) if r.dish in jain}
    assert not used & forbidden


def test_every_dish_has_a_recipe_and_every_ingredient_is_stocked_and_supplied(data):
    out, _ = data
    recipes = load_table("recipes", out)
    assert {m.dish for m in load_table("menu", out)} == {r.dish for r in recipes}
    needed = {r.ingredient for r in recipes}
    stocked = {i.ingredient for i in load_table("inventory", out)}
    supplied = {s.ingredient for s in load_table("suppliers", out)}
    assert needed == stocked == supplied
    assert len(needed) == 20


def test_store_has_the_situations_the_scenarios_need(data):
    out, _ = data
    inv = load_table("inventory", out)
    tomorrow = gen.PLAN_DATE + timedelta(days=1)
    assert sorted(i.ingredient for i in inv if i.expiry_date == tomorrow) == [
        "mixed_veg",
        "paneer",
        "tomato",
    ]
    assert not [i for i in inv if i.expiry_date <= gen.PLAN_DATE]  # nothing already expired
    assert [i.ingredient for i in inv if i.stock_qty < i.reorder_point] == ["chicken"]


def test_fest_day_needs_more_than_the_store_holds_for_perishables(data):
    out, _ = data
    short = {
        i.ingredient
        for i in load_table("inventory", out)
        if i.stock_qty < gen.ingredient_need(i.ingredient, gen.BASE_PRESENT["fest"], "sunny")
    }
    assert {"chicken", "paneer", "milk"} <= short  # something must be ordered
    assert "rice" not in short  # but not everything


def test_suppliers_differ_in_price_and_lead_time(data):
    out, _ = data
    offers = load_table("suppliers", out)
    assert {s.lead_time_days for s in offers} >= {0, 1, 2}
    by_ing: dict[str, list] = {}
    for s in offers:
        by_ing.setdefault(s.ingredient, []).append(s)
    assert any(len(v) > 1 for v in by_ing.values())  # a real choice exists


# ---------------------------------------------------------------- finance: the demo conflict
def test_fest_budget_fits_the_forecast_but_not_forecast_plus_5_percent(data):
    """The demo: the best-utility plan (about forecast +5%) is over budget, so the Critic must
    reject it, and the plan that cooks exactly the forecast fits. Checked against Aman's real
    forecast and stocking code on 11 Oct: forecast cost 59,398, +5% cost 62,385, budget 60,900."""
    out, _ = data
    budget = next(b for b in load_table("budget", out) if b.date == gen.PLAN_DATE).daily_budget
    cost = gen.food_cost(gen.BASE_PRESENT["fest"], "sunny")  # cost of cooking the average demand
    assert cost <= budget < cost * 1.05


def test_budget_ignores_real_headcount_so_accounts_and_academics_disagree(data):
    out, _ = data
    event = {r.date: r.event.value for r in load_table("calendar", out)}
    budgets = {}
    for b in load_table("budget", out):
        budgets.setdefault(event[b.date], set()).add(b.daily_budget)
    assert all(len(v) == 1 for v in budgets.values())  # one fixed amount per type of day
    assert budgets["fest"] != budgets["normal"]


# ---------------------------------------------------------------- leftovers for rule C9
def test_leftover_batches_cover_every_reuse_decision(data):
    out, _ = data
    batches = {b.batch_id: b for b in load_table("batches", out)}
    plan_morning = gen.PLAN_DATE
    assert len(batches) == 5
    assert {b.holding.value for b in batches.values()} == {"hot", "chilled", "ambient"}
    assert batches["B1"].dish == "paneer_curry"  # S11: the curry left out for 6 hours
    assert (batches["B1"].holding.value, batches["B1"].temp_c) == ("ambient", 30)
    assert batches["B3"].reheated_count == 1
    assert all(b.cooked_at.date() <= plan_morning for b in batches.values())
    assert min(b.cooked_at for b in batches.values()).date() < plan_morning  # one older than 24 h
