"""Smoke tests of the Education MCP server, started as a real subprocess over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TextIO, TypeVar

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

REPO = Path(__file__).resolve().parents[1]
FIXTURE_RAW = REPO / "tests" / "fixtures" / "raw"
TEST_TIMEOUT_S = 30  # a hung server must fail the test, not freeze the suite
FEST_DAY = "2026-10-16"
EXPECTED_TOOLS = {"get_calendar_event", "get_expected_attendance", "similar_past_days"}
RESOURCE_URI = "education://academic_calendar"

T = TypeVar("T")


def _run_with_session(body: Callable[[ClientSession], Awaitable[T]], errlog_path: Path) -> T:
    """Start the server, run `body(session)`, shut the server down; hard timeout throughout."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "zeroplate.mcp_servers.edu_server"],
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


def test_get_expected_attendance_and_similar_days(tmp_path: Path) -> None:
    async def body(session: ClientSession) -> tuple[Any, Any]:
        attendance = await session.call_tool("get_expected_attendance", {"date": FEST_DAY})
        similar = await session.call_tool("similar_past_days", {"date": FEST_DAY, "limit": 2})
        return attendance, similar

    attendance, similar = _run_with_session(body, tmp_path / "err.log")
    assert not attendance.isError and not similar.isError
    assert json.loads(_text(attendance))["expected_present"] > 0
    # list results arrive as one text block per item
    days = [json.loads(block.text) for block in similar.content]
    assert len(days) == 2
    assert all(d["event"] == "fest" and d["date"] < FEST_DAY for d in days)
    assert days[0]["date"] > days[1]["date"]


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


def test_resource_mentions_fest(tmp_path: Path) -> None:
    async def body(session: ClientSession) -> Any:
        return await session.read_resource(AnyUrl(RESOURCE_URI))

    result = _run_with_session(body, tmp_path / "err.log")
    text = "".join(getattr(c, "text", "") for c in result.contents)
    assert "fest" in text
