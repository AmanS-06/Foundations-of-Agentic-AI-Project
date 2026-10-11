"""Education MCP server (stdio): academic calendar and expected attendance.

Run as `python -m zeroplate.mcp_servers.edu_server` (needs src on PYTHONPATH) or as a script,
`python src/zeroplate/mcp_servers/edu_server.py`. The hub qualifies each tool with the server
name, so these tools appear to agents as education.get_calendar_event and so on.

stdout is the protocol channel of a stdio MCP server: nothing may print there. Logging goes to
stderr only.

This file is a thin wrapper: it parses the text arguments and calls zeroplate.domain.education.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import date as Date
from pathlib import Path
from typing import Any

# Running as a plain script puts this folder, not src/, on sys.path, so `import zeroplate` would
# fail. Adding src/ here makes both launch styles work without installing the package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP

from zeroplate.domain import education

SERVER_NAME = "education"
CALENDAR_RESOURCE_URI = "education://academic_calendar"
ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")  # strict: fromisoformat alone accepts more

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
mcp = FastMCP(SERVER_NAME)


def _parse_date(text: str) -> Date:
    """Turn 'YYYY-MM-DD' into a date; raise ValueError with a clear message otherwise."""
    if not ISO_DATE_PATTERN.fullmatch(text):
        raise ValueError(f"invalid date {text!r}: expected format YYYY-MM-DD, e.g. 2026-10-16")
    try:
        return Date.fromisoformat(text)
    except ValueError as exc:  # right shape, impossible date such as 2026-02-30
        raise ValueError(f"invalid date {text!r}: {exc}") from exc


@mcp.tool()
def get_calendar_event(date: str) -> dict[str, Any]:
    """Calendar entry for an ISO date (YYYY-MM-DD): weekday, event type and weather."""
    return education.get_calendar_event(_parse_date(date)).model_dump(mode="json")


@mcp.tool()
def get_expected_attendance(date: str) -> dict[str, Any]:
    """Enrolled students and expected number present on an ISO date (YYYY-MM-DD)."""
    return education.get_expected_attendance(_parse_date(date)).model_dump(mode="json")


@mcp.tool()
def similar_past_days(date: str, limit: int = 10) -> list[dict[str, Any]]:
    """Earlier days with the same event type as the ISO date, most recent first."""
    days = education.similar_past_days(_parse_date(date), limit)
    return [day.model_dump(mode="json") for day in days]


@mcp.resource(CALENDAR_RESOURCE_URI)
def academic_calendar() -> str:
    """Read-only plain-text description of the academic calendar."""
    return education.calendar_summary()


if __name__ == "__main__":
    mcp.run(transport="stdio")
