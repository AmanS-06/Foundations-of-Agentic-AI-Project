"""Supply MCP server: the canteen store (menu, recipes, stock, suppliers, history, leftovers).

Run as a separate process (stdio transport):  python -m zeroplate.mcp_servers.supply_server

Every tool is an ordinary function registered with FastMCP. The MCP hub calls them over the
protocol; if MCP is switched off, the hub calls the very same functions in-process.
Read tools return JSON-friendly dicts. The one write tool, create_purchase_order, is only
allowed for the Business Automation agent (enforced by the hub's allowlist).
"""

from __future__ import annotations

import json
import re
import uuid

from mcp.server.fastmcp import FastMCP

from zeroplate import config
from zeroplate.domain.data import load_table
from zeroplate.schemas import PurchaseLine

mcp = FastMCP("supply", log_level="WARNING")


def _dump(rows) -> list[dict]:
    return [r.model_dump(mode="json") for r in rows]


@mcp.tool()
def get_menu() -> dict:
    """All dishes on the menu with diet, price, cost per plate and fairness minimum."""
    return {"rows": _dump(load_table("menu"))}


@mcp.tool()
def get_history(dish: str | None = None, before: str | None = None) -> dict:
    """Past production per dish (prepared, sold, demand, waste). Optional filters: dish name,
    and `before` (ISO date) to return only days before it."""
    rows = [
        r
        for r in load_table("history")
        if (dish is None or r.dish == dish) and (before is None or r.date.isoformat() < before)
    ]
    return {"rows": _dump(rows)}


@mcp.tool()
def get_recipes(dish: str | None = None) -> dict:
    """Ingredient quantity per plate for one dish, or for all dishes."""
    return {"rows": _dump(r for r in load_table("recipes") if dish is None or r.dish == dish)}


@mcp.tool()
def get_inventory() -> dict:
    """Current stock of every ingredient with expiry date and reorder point."""
    return {"rows": _dump(load_table("inventory"))}


@mcp.tool()
def get_suppliers() -> dict:
    """Every supplier offer: ingredient, lead time in days, price per unit."""
    return {"rows": _dump(load_table("suppliers"))}


@mcp.tool()
def get_leftover_batches() -> dict:
    """Cooked batches with plates left over: when cooked, how held, temperature, reheats."""
    return {"rows": _dump(load_table("batches"))}


@mcp.tool()
def create_purchase_order(plan_date: str, lines: list[dict]) -> dict:
    """WRITE TOOL. Raise a purchase order for `plan_date`; returns its id and total.
    Each line: supplier, ingredient, qty, unit, unit_price, cost."""
    parsed = [PurchaseLine.model_validate(line) for line in lines]
    # a random suffix, not the clock: on Windows the clock only ticks every few milliseconds,
    # so two orders raised in the same tick would get the same id and overwrite each other
    supplier = (
        re.sub(r"[^a-z0-9]+", "-", parsed[0].supplier.lower()).strip("-") if parsed else "empty"
    )
    po_id = f"PO-{plan_date}-{supplier}-{uuid.uuid4().hex[:6]}"
    folder = config.OUTPUTS_DIR / "purchase_orders"
    folder.mkdir(parents=True, exist_ok=True)
    total = round(sum(line.cost for line in parsed), 2)
    record = {"id": po_id, "plan_date": plan_date, "total": total, "lines": _dump(parsed)}
    (folder / f"{po_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"id": po_id, "total": total, "lines": len(parsed)}


@mcp.resource("supply://supplier_catalog")
def supplier_catalog() -> str:
    """Read-only resource: the supplier price list as JSON."""
    return json.dumps(_dump(load_table("suppliers")), indent=2)


if __name__ == "__main__":
    mcp.run()
