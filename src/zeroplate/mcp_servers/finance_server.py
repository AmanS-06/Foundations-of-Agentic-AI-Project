"""Finance MCP server: accounts (daily budget, plan costing, waste-cost log).

Run as a separate process (stdio transport):  python -m zeroplate.mcp_servers.finance_server
The write tool log_waste_cost is only allowed for the Business Automation agent.
"""

from __future__ import annotations

import csv
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from zeroplate import config
from zeroplate.domain.costing import food_cost
from zeroplate.domain.data import load_table

mcp = FastMCP("finance", log_level="WARNING")

BUDGET_POLICY = """Daily food budget policy (ZeroPlate demo)
- Accounts sets a fixed daily food budget (budget.csv).
- The food cost of a plan (plates x cost per plate) must not exceed it.
- Plates reused from safe leftovers cost nothing today.
- A plan over budget needs the manager's sign-off (escalation)."""


@mcp.tool()
def get_daily_budget(date: str) -> dict:
    """The food budget for an ISO date."""
    for row in load_table("budget"):
        if row.date.isoformat() == date:
            return row.model_dump(mode="json")
    raise ValueError(f"no budget set for {date}")


@mcp.tool()
def cost_plan(quantities: dict[str, int]) -> dict:
    """Food cost of cooking the given plates per dish (dish -> plates)."""
    menu = {m.dish: m for m in load_table("menu")}
    unknown = sorted(set(quantities) - set(menu))
    if unknown:
        raise ValueError(f"unknown dishes: {unknown}")
    per_dish = {d: round(q * menu[d].cost_per_plate, 2) for d, q in quantities.items()}
    return {"food_cost": food_cost(quantities, menu), "per_dish": per_dish}


@mcp.tool()
def log_waste_cost(date: str, amount: float, note: str = "") -> dict:
    """WRITE TOOL. Append the expected or actual waste cost for a date to the waste log."""
    if amount < 0:
        raise ValueError("amount must be >= 0")
    path = config.OUTPUTS_DIR / "waste_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["logged_at", "date", "amount", "note"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), date, round(amount, 2), note])
    return {"logged": True, "date": date, "amount": round(amount, 2)}


@mcp.resource("finance://budget_policy")
def budget_policy() -> str:
    """Read-only resource: the budget rules the Critic applies."""
    return BUDGET_POLICY


if __name__ == "__main__":
    mcp.run()
