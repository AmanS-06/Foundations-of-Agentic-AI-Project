"""The baseline numbers for the old habit are worked out correctly.

The arithmetic is checked against a tiny dataset that can be added up by hand, so a mistake in the
code cannot hide behind a large, realistic dataset. A second group of tests ties the numbers to the
generator's own totals, and pins the headline figures that the problem statement quotes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their own module up by name
    spec.loader.exec_module(module)
    return module


baseline = _load("baseline_metrics")
gen = _load("generate_data")

# ---------------------------------------------------------------- a dataset small enough to add up
# date        type    tea (price 20, cost 10)                 thali (price 70, cost 35)
# 2026-01-01  normal  cooked 100 sold 80  demand 80           cooked 50 sold 50 demand 60 (10 unmet)
# 2026-01-02  exam    cooked 100 sold 100 demand 120 (20 unmet)  cooked 40 sold 30 demand 30
# 2026-01-03  normal  cooked 90  sold 90  demand 90            cooked 50 sold 40 demand 40
MENU = """dish,category,diet,price,cost_per_plate,shelf_life_hrs,min_portions
tea,beverage,veg,20,10,3,0
thali,main,veg,70,35,6,0
"""
CALENDAR = """date,weekday,event,weather
2026-01-01,Thursday,normal,sunny
2026-01-02,Friday,exam,sunny
2026-01-03,Saturday,normal,rainy
"""
HISTORY = """date,dish,prepared,sold,demand,wasted_plates,waste_cost
2026-01-01,tea,100,80,80,20,200
2026-01-01,thali,50,50,60,0,0
2026-01-02,tea,100,100,120,0,0
2026-01-02,thali,40,30,30,10,350
2026-01-03,tea,90,90,90,0,0
2026-01-03,thali,50,40,40,10,350
"""


@pytest.fixture()
def tiny(tmp_path):
    for name, text in (("menu", MENU), ("calendar", CALENDAR), ("history", HISTORY)):
        (tmp_path / f"{name}.csv").write_text(text, encoding="utf-8")
    return tmp_path


def test_totals_for_the_tiny_dataset_add_up_by_hand(tiny):
    m = baseline.baseline_metrics(tiny)["all"]
    assert m.days == 3
    assert (m.cooked, m.sold, m.demanded) == (430, 390, 420)
    assert (m.wasted, m.unmet) == (40, 30)
    assert m.waste_cost == 900  # 200 + 350 + 350
    assert m.lost_sales == 1100  # 10 thalis at 70 and 20 teas at 20
    assert m.waste_share == pytest.approx(40 / 430)
    assert m.unmet_share == pytest.approx(30 / 420)
    assert m.waste_cost_per_day == pytest.approx(300)
    assert m.lost_sales_per_day == pytest.approx(1100 / 3)


def test_each_type_of_day_is_counted_separately(tiny):
    result = baseline.baseline_metrics(tiny)
    normal, exam = result["normal"], result["exam"]
    assert (normal.days, normal.cooked, normal.wasted, normal.unmet) == (2, 290, 30, 10)
    assert (normal.waste_cost, normal.lost_sales) == (550, 700)
    assert (exam.days, exam.cooked, exam.wasted, exam.unmet) == (1, 140, 10, 20)
    assert (exam.waste_cost, exam.lost_sales) == (350, 400)
    assert set(result) == {"all", "normal", "exam"}  # no type that has no days


def test_the_types_of_day_add_up_to_the_total(tiny):
    result = baseline.baseline_metrics(tiny)
    parts = [m for k, m in result.items() if k != "all"]
    for field in (
        "days",
        "cooked",
        "sold",
        "demanded",
        "wasted",
        "unmet",
        "waste_cost",
        "lost_sales",
    ):
        assert sum(getattr(m, field) for m in parts) == getattr(result["all"], field), field


def test_last_days_keeps_only_the_most_recent_days(tiny):
    result = baseline.baseline_metrics(tiny, last_days=2)  # 2 January and 3 January
    m = result["all"]
    assert m.days == 2
    assert (m.cooked, m.sold, m.demanded, m.wasted, m.unmet) == (280, 260, 280, 20, 20)
    assert (m.waste_cost, m.lost_sales) == (700, 400)
    assert result["normal"].days == 1 and result["exam"].days == 1


def test_last_days_larger_than_the_history_means_all_of_it(tiny):
    assert baseline.baseline_metrics(tiny, last_days=99)["all"].days == 3


def test_last_days_must_be_at_least_one(tiny):
    with pytest.raises(ValueError, match="at least 1"):
        baseline.baseline_metrics(tiny, last_days=0)


def test_shares_are_zero_when_there_is_nothing_to_divide():
    empty = baseline.Metrics()
    assert empty.waste_share == 0 and empty.unmet_share == 0
    assert empty.waste_cost_per_day == 0 and empty.lost_sales_per_day == 0


def test_the_table_lists_every_type_of_day_present(tiny):
    text = baseline.render("tiny", baseline.baseline_metrics(tiny))
    assert "All days" in text and "Normal" in text and "Exam" in text
    assert "Holiday" not in text  # a type with no days is not listed


# ---------------------------------------------------------------- the real datasets
def test_baseline_agrees_with_the_generators_own_totals(tmp_path):
    """Two independent ways of adding up the same history must agree."""
    stats = gen.generate(tmp_path)
    m = baseline.baseline_metrics(tmp_path)["all"]
    assert m.waste_share == pytest.approx(stats["waste_share"])
    assert m.unmet_share == pytest.approx(stats["unmet_demand_share"])
    assert m.waste_cost == pytest.approx(stats["waste_cost_total"])
    assert m.days == 180


def test_the_figures_quoted_in_the_problem_statement_are_pinned():
    """docs/01_problem_statement.md and the summary PDF quote these numbers."""
    result = baseline.baseline_metrics(ROOT / "data" / "raw")
    m = result["all"]
    assert (m.cooked, m.wasted, m.unmet, m.demanded) == (267_968, 39_549, 13_745, 242_164)
    assert round(m.waste_share, 3) == 0.148 and round(m.unmet_share, 3) == 0.057
    assert round(m.waste_cost) == 1_082_661
    assert round(result["exam"].waste_share, 3) == 0.260
    assert round(result["holiday"].waste_share, 3) == 0.802
    assert round(result["fest"].unmet_share, 3) == 0.390


def test_the_heldout_dataset_gives_different_but_similar_numbers():
    main = baseline.baseline_metrics(ROOT / "data" / "raw")["all"]
    held = baseline.baseline_metrics(ROOT / "data" / "heldout")["all"]
    assert held.days == main.days == 180
    assert (held.cooked, held.wasted) != (main.cooked, main.wasted)
    assert 0.12 <= held.waste_share <= 0.25 and 0.02 <= held.unmet_share <= 0.15
