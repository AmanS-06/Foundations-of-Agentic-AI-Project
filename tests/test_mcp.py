"""MCP layer: real stdio servers, tool discovery, allowlist, errors, in-process fallback."""

import pytest

from zeroplate.mcp_client.allowlist import ALLOWLIST, WRITE_TOOLS, ToolNotAllowed
from zeroplate.mcp_client.hub import MCPHub, ToolError

EXPECTED_TOOLS = {
    "education": ["get_calendar_event", "get_expected_attendance"],
    "supply": [
        "create_purchase_order",
        "get_history",
        "get_inventory",
        "get_leftover_batches",
        "get_menu",
        "get_recipes",
        "get_suppliers",
    ],
    "finance": ["cost_plan", "get_daily_budget", "log_waste_cost"],
}


@pytest.fixture(scope="module")
def live_hub():
    """Three real server processes over stdio (takes about two seconds)."""
    with MCPHub(use_mcp=True) as h:
        assert h.mode == "mcp", h.start_error
        yield h


def test_servers_are_discovered_over_mcp(live_hub):
    # each server offers at least the contract's tools (the real Education server has extras)
    found = live_hub.tools()
    assert set(found) == set(EXPECTED_TOOLS)
    for server, tools in EXPECTED_TOOLS.items():
        assert set(tools) <= set(found[server]), server


def test_tool_call_over_mcp(live_hub):
    day = live_hub.call("research", "education.get_calendar_event", {"date": "2026-10-16"})
    assert day["event"] == "fest"


def test_resource_over_mcp(live_hub):
    assert "budget" in live_hub.read_resource("finance://budget_policy")


def test_tool_error_is_reported(live_hub):
    with pytest.raises(ToolError, match="no budget"):
        live_hub.call("executor", "finance.get_daily_budget", {"date": "1999-01-01"})


def test_mcp_and_in_process_give_identical_results(live_hub, hub):
    args = {"quantities": {"veg_thali": 376, "masala_chai": 612}}
    assert live_hub.call("executor", "finance.cost_plan", args) == hub.call(
        "executor", "finance.cost_plan", args
    )


def test_research_cannot_raise_a_purchase_order(hub):
    with pytest.raises(ToolNotAllowed, match="write tool"):
        hub.call("research", "supply.create_purchase_order", {"plan_date": "x", "lines": []})
    assert hub.calls[-1].blocked


def test_only_automation_has_write_tools():
    for agent, tools in ALLOWLIST.items():
        assert bool(tools & WRITE_TOOLS) == (agent == "automation"), agent


def test_planner_has_no_tools(hub):
    with pytest.raises(ToolNotAllowed):
        hub.call("planner", "supply.get_menu")


def test_fallback_when_mcp_cannot_start(monkeypatch):
    def broken(self):
        raise OSError("server process could not start")

    monkeypatch.setattr(MCPHub, "_start_mcp", broken)
    with MCPHub(use_mcp=True) as h:
        assert h.mode == "in-process" and "could not start" in h.start_error
        assert h.call("research", "supply.get_menu")["rows"]  # still works


def test_purchase_orders_raised_together_get_unique_ids(hub):
    line = {"ingredient": "rice", "qty": 1, "unit": "kg", "unit_price": 58, "cost": 58}
    ids = {
        hub.call(
            "automation",
            "supply.create_purchase_order",
            {"plan_date": "2026-10-16", "lines": [{**line, "supplier": s}]},
        )["id"]
        for s in ["Pune Grains Co", "FreshFarm Daily", "Pune Grains Co"]
    }
    assert len(ids) == 3
