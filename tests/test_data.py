"""The fixture data follows the contract, and the loader catches files that do not."""

from datetime import date

import pytest

from zeroplate import config
from zeroplate.domain.data import DataError, check_all, load_table

PLAN_DATE = date(2026, 10, 16)


def test_conftest_points_config_at_fixtures():
    assert config.RAW_DIR.parts[-2:] == ("fixtures", "raw")


def test_every_contract_table_loads():
    counts = check_all()
    assert counts["calendar"] == 210  # 180 past days + 30 future days
    assert counts["history"] == 180 * counts["menu"]
    assert all(n > 0 for n in counts.values())


def test_plan_date_is_a_fest():
    day = next(r for r in load_table("calendar") if r.date == PLAN_DATE)
    assert day.event.value == "fest"


def test_history_shows_waste_and_shortage():
    # the old process both over- and under-produces, which is the problem we solve
    rows = load_table("history")
    assert any(r.wasted_plates > 0 for r in rows)
    assert any(r.demand > r.sold for r in rows)  # censored demand: ran out
    assert all(r.sold == min(r.demand, r.prepared) for r in rows)


def test_every_recipe_ingredient_is_stocked_and_supplied():
    stocked = {r.ingredient for r in load_table("inventory")}
    supplied = {r.ingredient for r in load_table("suppliers")}
    needed = {r.ingredient for r in load_table("recipes")}
    assert needed <= stocked and needed <= supplied


def test_wrong_columns_are_rejected(tmp_path):
    (tmp_path / "budget.csv").write_text("date,budget\n2026-10-16,100\n", encoding="utf-8")
    with pytest.raises(DataError, match="contract says"):
        load_table("budget", tmp_path)


def test_bad_row_reports_line_number(tmp_path):
    (tmp_path / "budget.csv").write_text(
        "date,daily_budget\n2026-10-16,100\n2026-10-17,-5\n", encoding="utf-8"
    )
    with pytest.raises(DataError, match="line 3"):
        load_table("budget", tmp_path)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(DataError, match="missing data file"):
        load_table("menu", tmp_path)
