"""Generate the synthetic canteen dataset (the nine CSVs of the data contract).

Everything here is INVENTED. It exists so the agents have something realistic to work on, and the
brief allows synthetic data. Every number below is an assumption of ours, not a measurement of
any real canteen. Real figures, if we get them, would replace the constants at the top.

How the data is made (the story the numbers tell):

1. The calendar says what kind of day each date is (normal, exam, holiday, fest, weekend) and
   what the weather is. This is the Education department's data.
2. Attendance says how many students are expected to be on campus. The event is already inside
   this number (fewer on an exam day, more at a fest), so it is NOT applied a second time to the
   dishes.
3. Demand for a dish = students actually present x plates of that dish per student x a weather
   effect x random noise. The true demand is stored in history so a forecaster can be judged
   honestly; a real canteen would only see what it sold.
4. The old way of working ("cook what sold on the same weekday in recent weeks, plus 15%, and
   ignore the calendar") is replayed over 180 past days. It wastes food on exam days and holidays
   and runs out on fest days.
5. Accounts sets the daily budget by type of day with a small fest allowance. It does not know
   how many students will really come. That mismatch is the cross-department conflict.

Run:  .venv\\Scripts\\python scripts\\generate_data.py            (writes data/raw)
      .venv\\Scripts\\python scripts\\generate_data.py --out DIR --seed 7
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- the timeline
SEED = 42
PLAN_DATE = date(2026, 10, 16)  # Friday, a college fest: the main demo day
HISTORY_DAYS = 180  # days before PLAN_DATE with recorded history
FUTURE_DAYS = 30  # PLAN_DATE and the days after it (calendar, attendance, budget only)
ENROLLED = 1200

# Dates used by the benchmark scenarios. Weather is forced on these so scenarios are repeatable.
SCENARIO_WEATHER = {
    date(2026, 10, 16): "sunny",  # S4 college fest (the demo)
    date(2026, 10, 19): "sunny",  # S1 normal weekday
    date(2026, 10, 20): "rainy",  # S5 rainy day
    date(2026, 10, 22): "sunny",  # S3 holiday
    date(2026, 10, 27): "sunny",  # S2 exam week
}

# Illustrative calendar, NOT the real SIT Pune academic calendar.
FEST_DAYS = {
    date(2026, 6, 5),
    date(2026, 8, 20),
    date(2026, 8, 21),
    date(2026, 8, 22),
    PLAN_DATE,
}
HOLIDAYS = {
    date(2026, 5, 1),
    date(2026, 8, 15),
    date(2026, 9, 14),
    date(2026, 10, 2),
    date(2026, 10, 22),
}
EXAM_WEEKS = [
    (date(2026, 5, 4), date(2026, 5, 15)),
    (date(2026, 9, 21), date(2026, 10, 2)),
    (date(2026, 10, 26), date(2026, 11, 6)),
]

# ---------------------------------------------------------------- attendance (Education)
BASE_PRESENT = {"normal": 900, "exam": 700, "holiday": 160, "fest": 1150, "weekend": 330}
WEEKDAY_FACTOR = {0: 1.02, 1: 1.00, 2: 1.00, 3: 0.98, 4: 0.92}  # Mon..Fri, normal/exam days only
EXPECTED_NOISE = 0.03  # how far the expected headcount is from the usual for that day type
ACTUAL_NOISE = 0.04  # how far the real headcount is from the expected one

# ---------------------------------------------------------------- demand
DISH_NOISE = 0.08  # random variation of one dish's demand on one day
# weather -> season. Pune: hot Apr-May, monsoon Jun-Sep, mild Oct-Nov. (sunny, rainy, hot)
WEATHER_P = {
    "dry_hot": (0.35, 0.05, 0.60),  # Apr, May
    "monsoon": (0.25, 0.65, 0.10),  # Jun-Sep
    "mild": (0.60, 0.25, 0.15),  # Oct, Nov
}
WEATHER_EFFECT = {  # (weather, dish) -> multiplier on demand
    ("rainy", "masala_chai"): 1.25,
    ("rainy", "samosa"): 1.15,
    ("rainy", "cold_coffee"): 0.70,
    ("hot", "masala_chai"): 0.80,
    ("hot", "cold_coffee"): 1.40,
}

# ---------------------------------------------------------------- the old way of working
# The cook looks at what sold on the same weekday in recent weeks, and adds a safety margin.
# (A plain "last 7 days' average" does not work as a model of this: weekdays and weekends differ
# so much that the average sinks and the canteen runs out of food every weekday.)
HABIT_WEEKS = 3  # average of the last three same-weekday sales
HABIT_MARGIN = 1.15  # "plus 15% to be safe"

# ---------------------------------------------------------------- finance
BUDGET_HEADROOM = 1.10  # accounts budgets a normal day at 10% above its usual food cost
BUDGET_BY_DAY_TYPE = {  # multiplier on the normal-day budget; accounts ignores real headcount
    "normal": 1.00,
    "exam": 1.00,
    "weekend": 0.55,
    "holiday": 0.35,
    "fest": 1.20,  # a modest fest allowance: enough for the forecast, not for forecast +5%
}
BUDGET_ROUNDING = 100

# ---------------------------------------------------------------- menu
SUPPLIER_LEAD_DAYS = {
    "Pune Grains Co": 1,
    "FreshFarm Daily": 0,
    "Sahyadri Dairy": 0,
    "Metro Wholesale": 2,
}


@dataclass(frozen=True)
class Dish:
    """One menu item and everything the generator needs to know about it."""

    category: str
    diet: str  # veg, nonveg or jain
    price: int  # selling price, rupees
    shelf_life_hrs: float  # how long cooked food keeps (our assumption)
    min_portions: int  # fairness floor for rule C5 (our assumption, not a regulation)
    per_head: float  # plates of this dish per student present
    overhead: int  # cooking cost per plate besides ingredients (labour, gas), rupees
    recipe: tuple[tuple[str, float], ...]  # (ingredient, quantity per plate)


MENU: dict[str, Dish] = {
    "veg_thali": Dish(
        "main",
        "veg",
        70,
        6,
        40,
        0.29,
        10,
        (
            ("rice", 0.15),
            ("toor_dal", 0.06),
            ("mixed_veg", 0.12),
            ("wheat_flour", 0.06),
            ("oil", 0.01),
        ),
    ),
    "chicken_biryani": Dish(
        "main",
        "nonveg",
        110,
        6,
        0,
        0.20,
        12,
        (("rice", 0.18), ("chicken", 0.15), ("oil", 0.02), ("onion", 0.05)),
    ),
    "jain_khichdi": Dish(
        "main", "jain", 60, 6, 20, 0.05, 8, (("rice", 0.10), ("moong_dal", 0.07), ("ghee", 0.01))
    ),
    "paneer_curry": Dish(
        "main",
        "veg",
        90,
        6,
        0,
        0.12,
        10,
        (("paneer", 0.10), ("tomato", 0.10), ("butter", 0.015), ("wheat_flour", 0.06)),
    ),
    "dal_rice": Dish(
        "main", "veg", 55, 6, 0, 0.16, 8, (("rice", 0.15), ("toor_dal", 0.07), ("oil", 0.01))
    ),
    "chole_bhature": Dish(
        "main",
        "veg",
        65,
        4,
        0,
        0.10,
        10,
        (("chana", 0.10), ("maida", 0.10), ("oil", 0.04), ("onion", 0.04)),
    ),
    "veg_sandwich": Dish(
        "snack",
        "veg",
        40,
        8,
        0,
        0.14,
        4,
        (("bread", 0.10), ("mixed_veg", 0.05), ("butter", 0.01), ("tomato", 0.03)),
    ),
    "samosa": Dish(
        "snack", "veg", 20, 8, 0, 0.25, 2, (("maida", 0.05), ("potato", 0.08), ("oil", 0.03))
    ),
    "masala_chai": Dish(
        "beverage",
        "veg",
        20,
        3,
        0,
        0.45,
        2,
        (("milk", 0.12), ("tea_leaves", 0.004), ("sugar", 0.012)),
    ),
    "cold_coffee": Dish(
        "beverage",
        "veg",
        40,
        4,
        0,
        0.12,
        3,
        (("milk", 0.20), ("coffee_powder", 0.008), ("sugar", 0.02)),
    ),
}


@dataclass(frozen=True)
class Ingredient:
    """One stocked ingredient: where it is bought, and the state of the store on PLAN_DATE."""

    unit: str
    offers: tuple[tuple[str, float], ...]  # (supplier, price per unit, rupees)
    stock_fraction: float  # stock on hand as a fraction of what the fest day needs
    expiry_days: int  # days after PLAN_DATE that the stock expires


INGREDIENTS: dict[str, Ingredient] = {
    "rice": Ingredient("kg", (("Pune Grains Co", 58), ("Metro Wholesale", 54)), 1.30, 150),
    "toor_dal": Ingredient("kg", (("Pune Grains Co", 140), ("Metro Wholesale", 134)), 1.40, 120),
    "moong_dal": Ingredient("kg", (("Pune Grains Co", 120), ("Metro Wholesale", 115)), 1.50, 120),
    "chana": Ingredient("kg", (("Pune Grains Co", 95), ("Metro Wholesale", 90)), 1.40, 120),
    "wheat_flour": Ingredient("kg", (("Pune Grains Co", 40), ("Metro Wholesale", 37)), 1.30, 90),
    "maida": Ingredient("kg", (("Pune Grains Co", 44), ("Metro Wholesale", 41)), 1.30, 90),
    "sugar": Ingredient("kg", (("Pune Grains Co", 44), ("Metro Wholesale", 42)), 1.60, 365),
    "oil": Ingredient("l", (("Pune Grains Co", 150), ("Metro Wholesale", 145)), 1.40, 200),
    "mixed_veg": Ingredient("kg", (("FreshFarm Daily", 42),), 0.80, 1),  # expires tomorrow
    "tomato": Ingredient("kg", (("FreshFarm Daily", 32),), 0.85, 1),  # expires tomorrow
    "onion": Ingredient("kg", (("FreshFarm Daily", 36), ("Metro Wholesale", 34)), 1.20, 7),
    "potato": Ingredient("kg", (("FreshFarm Daily", 30), ("Metro Wholesale", 28)), 1.30, 10),
    "chicken": Ingredient("kg", (("FreshFarm Daily", 230), ("Metro Wholesale", 245)), 0.40, 2),
    "paneer": Ingredient("kg", (("Sahyadri Dairy", 370),), 0.80, 1),  # expires tomorrow
    "milk": Ingredient("l", (("Sahyadri Dairy", 56),), 0.85, 2),
    "butter": Ingredient("kg", (("Sahyadri Dairy", 540),), 1.30, 40),
    "ghee": Ingredient("kg", (("Sahyadri Dairy", 650), ("Metro Wholesale", 640)), 1.50, 120),
    "bread": Ingredient("kg", (("FreshFarm Daily", 55),), 0.90, 2),
    "tea_leaves": Ingredient("kg", (("Pune Grains Co", 480), ("Metro Wholesale", 460)), 1.60, 270),
    "coffee_powder": Ingredient(
        "kg", (("Metro Wholesale", 900), ("Pune Grains Co", 940)), 1.60, 270
    ),
}
REORDER_FRACTION = 0.90  # reorder point = this x the ingredient used on a normal day


# ================================================================== model pieces
def event_for(day: date) -> str:
    """Kind of day. A fest beats a holiday, a holiday beats a weekend, a weekend beats an exam."""
    if day in FEST_DAYS:
        return "fest"
    if day in HOLIDAYS:
        return "holiday"
    if day.weekday() >= 5:
        return "weekend"
    if any(start <= day <= end for start, end in EXAM_WEEKS):
        return "exam"
    return "normal"


def season_for(day: date) -> str:
    """Which weather pattern applies (Pune: hot, then monsoon, then mild)."""
    if day.month in (4, 5):
        return "dry_hot"
    return "monsoon" if 6 <= day.month <= 9 else "mild"


def cost_per_plate(dish: str) -> int:
    """Ingredients at the cheapest supplier plus the cooking overhead, in whole rupees."""
    spec = MENU[dish]
    ingredients = sum(qty * min(p for _, p in INGREDIENTS[ing].offers) for ing, qty in spec.recipe)
    return round(ingredients + spec.overhead)


def mean_demand(dish: str, present: float, weather: str) -> float:
    """Average plates demanded of `dish` when `present` students are on campus."""
    return present * MENU[dish].per_head * WEATHER_EFFECT.get((weather, dish), 1.0)


def food_cost(present: float, weather: str) -> float:
    """Cost of cooking exactly the average demand for every dish."""
    return sum(mean_demand(d, present, weather) * cost_per_plate(d) for d in MENU)


def budget_for(event: str) -> int:
    """Accounts' budget for a type of day (rounded). Based on a normal sunny day's cost."""
    normal = food_cost(BASE_PRESENT["normal"], "sunny") * BUDGET_HEADROOM
    value = normal * BUDGET_BY_DAY_TYPE[event]
    return int(round(value / BUDGET_ROUNDING) * BUDGET_ROUNDING)


def ingredient_need(ingredient: str, present: float, weather: str) -> float:
    """How much of an ingredient the average demand for all dishes needs."""
    return sum(
        mean_demand(d, present, weather) * qty
        for d, spec in MENU.items()
        for ing, qty in spec.recipe
        if ing == ingredient
    )


# ================================================================== writing
def _write(out: Path, name: str, header: list[str], rows: list[list]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _draw_days(rng: np.random.Generator, days: list[date]) -> list[dict]:
    """Calendar, weather and headcounts for every day. One fixed order of random draws."""
    out = []
    for d in days:
        event = event_for(d)
        weather = str(rng.choice(["sunny", "rainy", "hot"], p=WEATHER_P[season_for(d)]))
        expected_noise = rng.normal(1, EXPECTED_NOISE)
        actual_noise = rng.normal(1, ACTUAL_NOISE)
        weather = SCENARIO_WEATHER.get(d, weather)
        base = BASE_PRESENT[event]
        if event in ("normal", "exam"):
            base *= WEEKDAY_FACTOR[d.weekday()]
        expected = min(round(base * expected_noise), ENROLLED)
        if d == PLAN_DATE:
            expected = BASE_PRESENT["fest"]  # the demo day is exact so the budget maths is clean
        actual = min(round(expected * actual_noise), ENROLLED)
        out.append(
            {"date": d, "event": event, "weather": weather, "expected": max(expected, 0),
             "actual": max(actual, 0)}
        )  # fmt: skip
    return out


def _simulate_history(rng: np.random.Generator, days: list[dict]) -> list[list]:
    """Replay the old habit over the past days: cook the recent same-weekday average + 15%."""
    past = [d for d in days if d["date"] < PLAN_DATE]
    recent_sold: dict[tuple[str, int], list[int]] = {}
    rows = []
    for day in past:
        for dish in MENU:
            noise = rng.normal(1, DISH_NOISE)
            demand = max(round(mean_demand(dish, day["actual"], day["weather"]) * noise), 0)
            window = recent_sold.setdefault((dish, day["date"].weekday()), [])
            habit = (
                np.mean(window[-HABIT_WEEKS:])
                if window
                else mean_demand(dish, BASE_PRESENT["normal"], "sunny")
            )
            prepared = round(habit * HABIT_MARGIN)
            sold = min(demand, prepared)
            wasted = prepared - sold
            window.append(sold)
            rows.append(
                [day["date"].isoformat(), dish, prepared, sold, demand, wasted,
                 wasted * cost_per_plate(dish)]
            )  # fmt: skip
    return rows


def _inventory_rows() -> list[list]:
    """Store stock on the morning of PLAN_DATE, sized from what the fest day needs."""
    fest_weather = SCENARIO_WEATHER[PLAN_DATE]
    rows = []
    for name, ing in INGREDIENTS.items():
        fest_need = ingredient_need(name, BASE_PRESENT["fest"], fest_weather)
        normal_use = ingredient_need(name, BASE_PRESENT["normal"], "sunny")
        rows.append(
            [
                name,
                round(fest_need * ing.stock_fraction, 1),
                ing.unit,
                (PLAN_DATE + timedelta(days=ing.expiry_days)).isoformat(),
                round(normal_use * REORDER_FRACTION, 1),
            ]
        )
    return rows


def _batch_rows() -> list[list]:
    """Cooked leftovers on the morning of PLAN_DATE, for rule C9 (may we serve them again?)."""
    morning = datetime.combine(PLAN_DATE, datetime.min.time()).replace(hour=7)

    def cooked(hours_ago: float) -> str:
        return (morning - timedelta(hours=hours_ago)).isoformat()

    return [
        # kept at room temperature for 6 h: below 65 C for more than 2 h -> must be blocked
        ["B1", "paneer_curry", cooked(6), 18, "ambient", 30, 0],
        # chilled overnight, never reheated, under 24 h -> may be reused
        ["B2", "jain_khichdi", cooked(14), 12, "chilled", 4, 0],
        # chicken already reheated once -> must not be reheated again
        ["B3", "chicken_biryani", cooked(10), 8, "chilled", 4, 1],
        # still hot-held at 68 C, cooked 1.5 h ago -> may be served
        ["B4", "dal_rice", cooked(1.5), 30, "hot", 68, 0],
        # older than 24 h -> must be blocked
        ["B5", "veg_thali", cooked(26), 20, "chilled", 4, 0],
    ]


def generate(out: Path, seed: int = SEED) -> dict[str, float]:
    """Write all nine CSVs into `out`. Returns a few summary numbers for checking."""
    rng = np.random.default_rng(seed)
    start = PLAN_DATE - timedelta(days=HISTORY_DAYS)
    dates = [start + timedelta(days=i) for i in range(HISTORY_DAYS + FUTURE_DAYS)]
    days = _draw_days(rng, dates)

    _write(
        out,
        "calendar",
        ["date", "weekday", "event", "weather"],
        [[d["date"].isoformat(), d["date"].strftime("%A"), d["event"], d["weather"]] for d in days],
    )
    _write(
        out,
        "attendance",
        ["date", "enrolled", "expected_present"],
        [[d["date"].isoformat(), ENROLLED, d["expected"]] for d in days],
    )
    _write(
        out,
        "budget",
        ["date", "daily_budget"],
        [[d["date"].isoformat(), budget_for(d["event"])] for d in days],
    )
    _write(
        out,
        "menu",
        ["dish", "category", "diet", "price", "cost_per_plate", "shelf_life_hrs", "min_portions"],
        [
            [
                name,
                s.category,
                s.diet,
                s.price,
                cost_per_plate(name),
                s.shelf_life_hrs,
                s.min_portions,
            ]
            for name, s in MENU.items()
        ],
    )
    _write(
        out,
        "recipes",
        ["dish", "ingredient", "qty_per_plate", "unit"],
        [
            [name, ing, qty, INGREDIENTS[ing].unit]
            for name, s in MENU.items()
            for ing, qty in s.recipe
        ],
    )
    _write(
        out,
        "inventory",
        ["ingredient", "stock_qty", "unit", "expiry_date", "reorder_point"],
        _inventory_rows(),
    )
    _write(
        out,
        "suppliers",
        ["supplier", "ingredient", "lead_time_days", "price_per_unit"],
        [
            [supplier, name, SUPPLIER_LEAD_DAYS[supplier], price]
            for name, ing in INGREDIENTS.items()
            for supplier, price in ing.offers
        ],
    )
    history = _simulate_history(rng, days)
    _write(
        out,
        "history",
        ["date", "dish", "prepared", "sold", "demand", "wasted_plates", "waste_cost"],
        history,
    )
    _write(
        out,
        "batches",
        ["batch_id", "dish", "cooked_at", "plates_left", "holding", "temp_c", "reheated_count"],
        _batch_rows(),
    )

    prepared = sum(r[2] for r in history)
    demand = sum(r[4] for r in history)
    return {
        "waste_share": sum(r[5] for r in history) / prepared,
        "unmet_demand_share": (demand - sum(r[3] for r in history)) / demand,
        "waste_cost_total": sum(r[6] for r in history),
        "days_with_shortage": len({r[0] for r in history if r[4] > r[3]}),
    }


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description="Generate the synthetic canteen dataset.")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--out", type=Path, default=root / "data" / "raw")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    stats = generate(args.out, args.seed)
    print(f"wrote the nine CSVs to {args.out}")
    print(f"  history waste share      {stats['waste_share']:.1%} of plates cooked")
    print(f"  demand that went unmet   {stats['unmet_demand_share']:.1%}")
    print(f"  days with a shortage     {stats['days_with_shortage']} of {HISTORY_DAYS}")
    print(f"  total waste cost         Rs {stats['waste_cost_total']:,.0f}")


if __name__ == "__main__":
    main()
