"""Tool access restrictions (Unit 5 guardrail): which agent may call which MCP tool.

Principle of least privilege: each agent gets only the tools its job needs. Write tools (the
ones that change something in the world) belong to the Business Automation agent alone, so a
confused or manipulated Research or Critic agent cannot raise a purchase order.
Read-only MCP resources (documents) may be read by any agent.
"""

from __future__ import annotations

WRITE_TOOLS = frozenset({"supply.create_purchase_order", "finance.log_waste_cost"})

ALLOWLIST: dict[str, frozenset[str]] = {
    "planner": frozenset(),  # plans only; uses no tools
    "research": frozenset(
        {
            "education.get_calendar_event",
            "education.get_expected_attendance",
            "supply.get_menu",
            "supply.get_leftover_batches",
        }
    ),
    "executor": frozenset(
        {
            "education.get_calendar_event",
            "education.get_expected_attendance",
            "supply.get_menu",
            "supply.get_history",
            "supply.get_recipes",
            "supply.get_inventory",
            "supply.get_suppliers",
            "supply.get_leftover_batches",
            "finance.get_daily_budget",
            "finance.cost_plan",
        }
    ),
    "critic": frozenset(
        {
            "education.get_calendar_event",
            "supply.get_menu",
            "supply.get_history",
            "supply.get_leftover_batches",
            "finance.get_daily_budget",
            "finance.cost_plan",
        }
    ),
    "automation": frozenset(
        {"supply.get_menu", "supply.create_purchase_order", "finance.log_waste_cost"}
    ),
}


class ToolNotAllowed(PermissionError):
    """An agent tried to call a tool outside its allowlist."""


def check(agent: str, tool: str) -> None:
    """Raise ToolNotAllowed unless `agent` may call `tool` (e.g. "supply.get_menu")."""
    if tool not in ALLOWLIST.get(agent, frozenset()):
        kind = "write tool" if tool in WRITE_TOOLS else "tool"
        raise ToolNotAllowed(f"{agent} is not allowed to call {kind} {tool}")
