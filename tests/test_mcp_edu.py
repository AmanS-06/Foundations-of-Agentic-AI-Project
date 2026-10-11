"""Smoke tests of the Education MCP server, started as a real subprocess over stdio."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any, TextIO, TypeVar

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

from zeroplate.schemas import Event

REPO = Path(__file__).resolve().parents[1]
FIXTURE_RAW = REPO / "tests" / "fixtures" / "raw"
TEST_TIMEOUT_S = 30  # a hung server must fail the test, not freeze the suite
FEST_DAY = "2026-10-16"
# The contract with the MCP hub: exactly these tools, and no others (the hub's tests compare).
EXPECTED_TOOLS = {"get_calendar_event", "get_expected_attendance"}
CALENDAR_URI = "education://academic_calendar"  # the whole calendar as JSON rows
SUMMARY_URI = "education://calendar_summary"  # a short text description
MODULE = "zeroplate.mcp_servers.edu_server"  # the module path the hub starts

T = TypeVar("T")


def _run_with_session(body: Callable[[ClientSession], Awaitable[T]], errlog_path: Path) -> T:
    """Start the server, run `body(session)`, shut the server down; hard timeout throughout."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", MODULE],
        # the child inherits only a minimal environment, so say where code and data are
        env={"PYTHONPATH": str(REPO / "src"), "ZEROPLATE_RAW_DIR": str(FIXTURE_RAW)},
    )

    async def main(errlog: TextIO) -> T:
        with anyio.fail_after(TEST_TIMEOUT_S):
            async with (
                stdio_client(params, errlog=errlog) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await body(session)

    # a real file for stderr: pytest's capture object has no fileno(), which Popen needs
    with open(errlog_path, "w", encoding="utf-8") as errlog:
        return asyncio.run(main(errlog))


def _text(result: Any) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


def test_tools_are_listed(tmp_path: Path) -> None:
    async def body(session: ClientSession) -> set[str]:
        return {tool.name for tool in (await session.list_tools()).tools}

    assert _run_with_session(body, tmp_path / "err.log") == EXPECTED_TOOLS


def test_get_calendar_event_returns_fest(tmp_path: Path) -> None:
    async def body(session: ClientSession) -> Any:
        return await session.call_tool("get_calendar_event", {"date": FEST_DAY})

    result = _run_with_session(body, tmp_path / "err.log")
    assert not result.isError
    payload = json.loads(_text(result))
    assert payload["date"] == FEST_DAY
    assert payload["event"] == "fest"


def test_get_expected_attendance(tmp_path: Path) -> None:
    async def body(session: ClientSession) -> Any:
        return await session.call_tool("get_expected_attendance", {"date": FEST_DAY})

    result = _run_with_session(body, tmp_path / "err.log")
    assert not result.isError
    payload = json.loads(_text(result))
    assert payload["date"] == FEST_DAY
    assert payload["expected_present"] > 0 and payload["enrolled"] >= payload["expected_present"]


def test_similar_past_days_is_not_offered_over_mcp(tmp_path: Path) -> None:
    """It exists as a plain function, but the contract is exactly two tools, so it is not a tool."""

    async def body(session: ClientSession) -> Any:
        return await session.call_tool("similar_past_days", {"date": FEST_DAY})

    result = _run_with_session(body, tmp_path / "err.log")
    assert result.isError  # unknown tool


def test_unknown_date_is_an_error_not_a_hang(tmp_path: Path) -> None:
    async def body(session: ClientSession) -> Any:
        return await session.call_tool("get_calendar_event", {"date": "2026-01-01"})

    result = _run_with_session(body, tmp_path / "err.log")
    assert result.isError
    assert "no calendar entry for 2026-01-01" in _text(result)


@pytest.mark.parametrize("bad_date", ["16/10/2026", "2026-10-16T00:00", "not a date", "2026-02-30"])
def test_invalid_date_format_is_an_error(tmp_path: Path, bad_date: str) -> None:
    async def body(session: ClientSession) -> Any:
        return await session.call_tool("get_calendar_event", {"date": bad_date})

    result = _run_with_session(body, tmp_path / "err.log")
    assert result.isError
    assert "YYYY-MM-DD" in _text(result) or "invalid date" in _text(result)


def _read_resource(uri: str, errlog_path: Path) -> str:
    async def body(session: ClientSession) -> Any:
        return await session.read_resource(AnyUrl(uri))

    result = _run_with_session(body, errlog_path)
    return "".join(getattr(c, "text", "") for c in result.contents)


def test_calendar_resource_is_the_whole_calendar_as_json(tmp_path: Path) -> None:
    """The hub's agents json.loads this resource, so it must be JSON rows, one per calendar day."""
    rows = json.loads(_read_resource(CALENDAR_URI, tmp_path / "err.log"))
    with open(FIXTURE_RAW / "calendar.csv", newline="", encoding="utf-8") as f:
        expected = list(csv.DictReader(f))
    assert isinstance(rows, list) and len(rows) == len(expected)
    assert all(set(r) == {"date", "weekday", "event", "weather"} for r in rows)
    assert [r["date"] for r in rows] == [r["date"] for r in expected]
    assert next(r for r in rows if r["date"] == FEST_DAY)["event"] == "fest"


def test_calendar_resource_converts_the_way_the_agents_convert_it(tmp_path: Path) -> None:
    """The same one-line conversion the Critic and Executor apply: date -> type of day."""
    rows = json.loads(_read_resource(CALENDAR_URI, tmp_path / "err.log"))
    events = {date.fromisoformat(r["date"]): Event(r["event"]) for r in rows}
    assert events[date(2026, 10, 16)] is Event.FEST
    assert set(events.values()) <= set(Event)


def test_summary_resource_is_readable_text(tmp_path: Path) -> None:
    text = _read_resource(SUMMARY_URI, tmp_path / "err.log")
    assert "Days per event type" in text and "fest" in text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)  # it is text for people, not the machine-readable calendar
