"""Build the small sample dataset used by Aman's tests.

This is NOT the project's data generator (that is Anhad's, in scripts/). It is a tiny, seeded
stand-in that follows the same CSV contract (PROJECT_PLAN 8.1), so the core code can be built
and tested without waiting for anything. All numbers are invented for testing.

Run:  .venv\\Scripts\\python tests\\fixtures\\make_fixtures.py
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "raw"
SEED = 7
PLAN_DATE = date(2026, 10, 16)  # Friday, a college fest: the S1 scenario day
HISTORY_DAYS = 180
FUTURE_DAYS = 30

# dish: category, diet, price, cost_per_plate, shelf_life_hrs, min_portions, base daily demand
MENU = {
    "veg_thali": ("main", "veg", 70, 32, 6, 40, 260),
    "chicken_biryani": ("main", "nonveg", 110, 55, 6, 0, 180),
    "jain_khichdi": ("main", "jain", 60, 26, 6, 20, 45),
    "masala_chai": ("beverage", "veg", 15, 5, 3, 0, 420),
}
RECIPES = {
    "veg_thali": [("rice", 0.15, "kg"), ("toor_dal", 0.06, "kg"), ("mixed_veg", 0.12, "kg")],
    "chicken_biryani": [("rice", 0.18, "kg"), ("chicken", 0.15, "kg"), ("oil", 0.02, "l")],
    "jain_khichdi": [("rice", 0.10, "kg"), ("moong_dal", 0.07, "kg"), ("ghee", 0.01, "kg")],
    "masala_chai": [("milk", 0.12, "l"), ("tea_leaves", 0.004, "kg"), ("sugar", 0.012, "kg")],
}
# ingredient: stock, unit, days until expiry (from PLAN_DATE), reorder point
INVENTORY = {
    "rice": (60, "kg", 120, 40),
    "toor_dal": (12, "kg", 90, 10),
    "moong_dal": (5, "kg", 90, 4),
    "mixed_veg": (20, "kg", 1, 25),  # expires tomorrow: "use first"
    "chicken": (15, "kg", 1, 20),  # expires tomorrow, and below reorder point
    "oil": (25, "l", 200, 10),
    "ghee": (3, "kg", 60, 2),
    "milk": (30, "l", 0, 40),  # expires on the plan date
    "tea_leaves": (2, "kg", 180, 1),
    "sugar": (15, "kg", 365, 5),
}
# supplier: {ingredient: price per unit}, lead time in days
SUPPLIERS = {
    "Pune Grains Co": (
        {"rice": 58, "toor_dal": 135, "moong_dal": 120, "sugar": 44, "tea_leaves": 470},
        1,
    ),
    "FreshFarm Daily": ({"mixed_veg": 40, "milk": 56, "chicken": 240, "ghee": 620}, 0),
    "Metro Wholesale": ({"oil": 150, "tea_leaves": 480, "rice": 62, "chicken": 255}, 2),
}
EVENT_FACTOR = {"normal": 1.0, "exam": 0.75, "holiday": 0.3, "fest": 1.4, "weekend": 0.5}
ATTENDANCE = {"normal": 900, "exam": 700, "holiday": 160, "fest": 1150, "weekend": 330}
ENROLLED = 1200
# Fest day: the forecast +0% plan fits (about 29.5k), the best-utility +5% plan does not
# (about 31.0k). That forces scenario S1: reject over budget, revise, approve.
DAILY_BUDGET = 30000
FEST_DAYS = {date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 22), PLAN_DATE}
EXAM_WEEKS = [(date(2026, 5, 4), date(2026, 5, 15)), (date(2026, 9, 21), date(2026, 10, 2))]
HOLIDAYS = {date(2026, 5, 1), date(2026, 8, 15), date(2026, 8, 26), date(2026, 9, 14)}


def event_for(day: date) -> str:
    """Kind of day for the calendar."""
    if day in FEST_DAYS:
        return "fest"
    if day in HOLIDAYS:
        return "holiday"
    if day.weekday() >= 5:
        return "weekend"
    if any(start <= day <= end for start, end in EXAM_WEEKS):
        return "exam"
    return "normal"


def write(name: str, header: list[str], rows: list[list]) -> None:
    """Write one CSV with a header row."""
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rng = np.random.default_rng(SEED)
    start = PLAN_DATE - timedelta(days=HISTORY_DAYS)
    days = [start + timedelta(days=i) for i in range(HISTORY_DAYS + FUTURE_DAYS)]
    past = [d for d in days if d < PLAN_DATE]

    calendar, attendance, budget = [], [], []
    for d in days:
        ev = event_for(d)
        weather = rng.choice(["sunny", "rainy", "hot"], p=[0.5, 0.3, 0.2])
        calendar.append([d.isoformat(), d.strftime("%A"), ev, weather])
        present = int(ATTENDANCE[ev] * rng.normal(1, 0.04))
        attendance.append([d.isoformat(), ENROLLED, max(present, 0)])
        budget.append([d.isoformat(), DAILY_BUDGET])
    write("calendar", ["date", "weekday", "event", "weather"], calendar)
    write("attendance", ["date", "enrolled", "expected_present"], attendance)
    write("budget", ["date", "daily_budget"], budget)

    write(
        "menu",
        ["dish", "category", "diet", "price", "cost_per_plate", "shelf_life_hrs", "min_portions"],
        [[dish, *spec[:6]] for dish, spec in MENU.items()],
    )
    write(
        "recipes",
        ["dish", "ingredient", "qty_per_plate", "unit"],
        [[dish, ing, qty, unit] for dish, lines in RECIPES.items() for ing, qty, unit in lines],
    )
    write(
        "inventory",
        ["ingredient", "stock_qty", "unit", "expiry_date", "reorder_point"],
        [
            [ing, stock, unit, (PLAN_DATE + timedelta(days=exp)).isoformat(), rop]
            for ing, (stock, unit, exp, rop) in INVENTORY.items()
        ],
    )
    write(
        "suppliers",
        ["supplier", "ingredient", "lead_time_days", "price_per_unit"],
        [
            [sup, ing, lead, price]
            for sup, (prices, lead) in SUPPLIERS.items()
            for ing, price in prices.items()
        ],
    )

    # History: true demand, and what the old habit-based process cooked and sold.
    events = {row[0]: row[2] for row in calendar}
    history = []
    for dish, spec in MENU.items():
        cost, base = spec[3], spec[6]
        recent_sold: list[int] = []
        for d in past:
            ev = events[d.isoformat()]
            demand = max(round(base * EVENT_FACTOR[ev] * rng.normal(1, 0.08)), 0)
            # old process: last 7 days' average sales + 15%, ignoring the calendar
            habit = np.mean(recent_sold[-7:]) if recent_sold else base
            prepared = round(habit * 1.15)
            sold = min(demand, prepared)
            wasted = prepared - sold
            recent_sold.append(sold)
            history.append([d.isoformat(), dish, prepared, sold, demand, wasted, wasted * cost])
    write(
        "history",
        ["date", "dish", "prepared", "sold", "demand", "wasted_plates", "waste_cost"],
        history,
    )

    # Leftover batches on the morning of the plan date (used by rule C9).
    morning = datetime.combine(PLAN_DATE, datetime.min.time()).replace(hour=7)
    batches = [
        # dal gravy kept at room temperature for 6 h: must be blocked
        ["B1", "veg_thali", (morning - timedelta(hours=6)).isoformat(), 25, "ambient", 30, 0],
        # khichdi chilled overnight at 4 C, never reheated: may be reused
        ["B2", "jain_khichdi", (morning - timedelta(hours=14)).isoformat(), 12, "chilled", 4, 0],
        # biryani already reheated once: must not be reheated again
        ["B3", "chicken_biryani", (morning - timedelta(hours=10)).isoformat(), 8, "chilled", 4, 1],
    ]
    write(
        "batches",
        ["batch_id", "dish", "cooked_at", "plates_left", "holding", "temp_c", "reheated_count"],
        batches,
    )
    print(f"wrote {len(list(OUT.glob('*.csv')))} files to {OUT}")


if __name__ == "__main__":
    main()
