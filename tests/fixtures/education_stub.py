"""TEST STAND-IN for Anhad's Education MCP server. Not part of the product.

It follows the contract (PROJECT_PLAN 8.2) so Aman's hub and agents can be built and tested
before the real server exists. The real one lives at zeroplate.mcp_servers.education_server
(Anhad's); the hub uses it automatically once it is present.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from zeroplate.domain.data import load_table

mcp = FastMCP("education", log_level="WARNING")


@mcp.tool()
def get_calendar_event(date: str) -> dict:
    """Event type, weekday and weather for an ISO date."""
    for row in load_table("calendar"):
        if row.date.isoformat() == date:
            return row.model_dump(mode="json")
    raise ValueError(f"date {date} is not in the academic calendar")


@mcp.tool()
def get_expected_attendance(date: str) -> dict:
    """Enrolled students and expected attendance for an ISO date."""
    for row in load_table("attendance"):
        if row.date.isoformat() == date:
            return row.model_dump(mode="json")
    raise ValueError(f"no attendance figure for {date}")


@mcp.resource("education://academic_calendar")
def academic_calendar() -> str:
    """Read-only resource: the whole academic calendar as JSON."""
    return json.dumps([r.model_dump(mode="json") for r in load_table("calendar")])


if __name__ == "__main__":
    mcp.run()
