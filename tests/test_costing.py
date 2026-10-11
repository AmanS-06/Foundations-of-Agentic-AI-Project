"""Costing: recipe maths, usable stock, use-first flags, cheapest in-time supplier."""

from datetime import date

import pytest

from zeroplate.domain import costing
from zeroplate.domain.data import load_table
from zeroplate.schemas import InventoryItem, SupplierOffer

FEST = date(2026, 10, 16)


@pytest.fixture(scope="module")
def plan():
    quantities = {"veg_thali": 376, "chicken_biryani": 255, "jain_khichdi": 72, "masala_chai": 612}
    required = costing.ingredients_required(quantities, load_table("recipes"))
    needs = costing.ingredient_needs(required, load_table("inventory"), FEST)
    return quantities, required, {n.ingredient: n for n in needs}


def test_recipe_maths():
    required = costing.ingredients_required({"veg_thali": 10}, load_table("recipes"))
    assert required["rice"] == (1.5, "kg")  # 10 plates x 0.15 kg


def test_shared_ingredients_are_summed(plan):
    _, required, _ = plan
    # rice is used by thali (0.15), biryani (0.18) and khichdi (0.10)
    assert required["rice"][0] == pytest.approx(376 * 0.15 + 255 * 0.18 + 72 * 0.10)


def test_use_first_flags(plan):
    _, _, needs = plan
    assert {i for i, n in needs.items() if n.expires_soon} == {"milk", "chicken", "mixed_veg"}


def test_expired_stock_is_not_usable():
    stale = [
        InventoryItem(
            ingredient="milk", stock_qty=50, unit="l", expiry_date="2026-10-15", reorder_point=0
        )
    ]
    need = costing.ingredient_needs({"milk": (10.0, "l")}, stale, FEST)[0]
    assert need.in_stock == 0 and need.to_order == 10.0


def test_order_tops_up_to_reorder_point(plan):
    _, _, needs = plan
    chicken = needs["chicken"]  # stock 15, reorder point 20
    assert chicken.to_order == pytest.approx(chicken.required + 20 - 15)


def test_cheapest_supplier_that_delivers_in_time(plan):
    _, _, needs = plan
    lines, problems = costing.purchase_lines(list(needs.values()), load_table("suppliers"))
    by_ing = {line.ingredient: line for line in lines}
    # Metro sells chicken at 255 but needs 2 days; FreshFarm sells at 240 next day
    assert by_ing["chicken"].supplier == "FreshFarm Daily"
    assert by_ing["rice"].supplier == "Pune Grains Co"
    assert problems == []


def test_missing_supplier_is_reported():
    needs = costing.ingredient_needs({"saffron": (0.1, "kg")}, [], FEST)
    slow = [
        SupplierOffer(supplier="Far Away", ingredient="saffron", lead_time_days=5, price_per_unit=1)
    ]
    lines, problems = costing.purchase_lines(needs, slow)
    assert lines == [] and "saffron" in problems[0]


def test_food_cost(plan):
    quantities, _, _ = plan
    menu = {m.dish: m for m in load_table("menu")}
    assert costing.food_cost(quantities, menu) == 376 * 32 + 255 * 55 + 72 * 26 + 612 * 5
