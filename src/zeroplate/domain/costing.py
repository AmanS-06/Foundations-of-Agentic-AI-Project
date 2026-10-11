"""From plates to ingredients, stock, purchase orders and cost.

Steps for a chosen quantity of each dish:
1. ingredients_required: plates x recipe = kg / litres of each ingredient.
2. ingredient_needs: compare with usable stock (not expired on the plan date) and mark items
   expiring within 24 h as "use first". Order the shortfall, plus enough to get back up to the
   reorder point (a safety stock for the next day).
3. purchase_lines: for each ingredient to order, pick the cheapest supplier who can deliver in
   time (lead time <= 1 day, because orders are raised the day before cooking).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from zeroplate import config
from zeroplate.schemas import (
    IngredientNeed,
    InventoryItem,
    MenuItem,
    PurchaseLine,
    RecipeLine,
    SupplierOffer,
)

MAX_LEAD_DAYS = 1  # orders are placed the day before cooking


def food_cost(quantities: dict[str, int], menu: dict[str, MenuItem]) -> float:
    """Cost of cooking the plates (what the daily budget limits)."""
    return round(sum(q * menu[d].cost_per_plate for d, q in quantities.items()), 2)


def ingredients_required(
    quantities: dict[str, int], recipes: list[RecipeLine]
) -> dict[str, tuple[float, str]]:
    """Total amount and unit of each ingredient needed for the given plates."""
    total: dict[str, float] = defaultdict(float)
    units: dict[str, str] = {}
    for line in recipes:
        if line.dish in quantities:
            total[line.ingredient] += quantities[line.dish] * line.qty_per_plate
            units[line.ingredient] = line.unit
    return {ing: (round(amount, 3), units[ing]) for ing, amount in total.items()}


def ingredient_needs(
    required: dict[str, tuple[float, str]], inventory: list[InventoryItem], plan_date: date
) -> list[IngredientNeed]:
    """Required vs usable stock for each ingredient, with the amount to order."""
    stock = {item.ingredient: item for item in inventory}
    soon = plan_date + timedelta(days=config.EXPIRY_WINDOW_HOURS // 24)
    needs = []
    for ing, (amount, unit) in sorted(required.items()):
        item = stock.get(ing)
        usable = item.stock_qty if item and item.expiry_date >= plan_date else 0.0
        reorder = item.reorder_point if item else 0.0
        # order whatever keeps stock at or above the reorder point after cooking
        to_order = max(amount + reorder - usable, 0.0)
        needs.append(
            IngredientNeed(
                ingredient=ing,
                unit=unit,
                required=amount,
                in_stock=usable,
                to_order=round(to_order, 3),
                expires_soon=bool(item and plan_date <= item.expiry_date <= soon),
            )
        )
    return needs


def purchase_lines(
    needs: list[IngredientNeed], suppliers: list[SupplierOffer]
) -> tuple[list[PurchaseLine], list[str]]:
    """Cheapest in-time supplier for each ingredient to order. Also returns problems found."""
    lines, problems = [], []
    for need in needs:
        if need.to_order <= 0:
            continue
        offers = [
            o
            for o in suppliers
            if o.ingredient == need.ingredient and o.lead_time_days <= MAX_LEAD_DAYS
        ]
        if not offers:
            problems.append(f"no supplier can deliver {need.ingredient} within {MAX_LEAD_DAYS} day")
            continue
        best = min(offers, key=lambda o: o.price_per_unit)
        lines.append(
            PurchaseLine(
                supplier=best.supplier,
                ingredient=need.ingredient,
                qty=need.to_order,
                unit=need.unit,
                unit_price=best.price_per_unit,
                cost=round(need.to_order * best.price_per_unit, 2),
            )
        )
    return lines, problems
