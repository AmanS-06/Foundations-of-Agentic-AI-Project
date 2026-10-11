"""MCP client hub: starts the three department servers, routes tool calls, enforces the allowlist.

How it works
- Each server is a separate Python process speaking MCP over stdio (JSON-RPC messages on
  stdin/stdout). The hub is the MCP *client*: it opens one session per server, discovers the
  server's tools with list_tools, and calls them with call_tool.
- All sessions live on one asyncio event loop in a background thread. Every connection is
  opened and closed inside ONE long-running task (`_serve`), because the MCP library's
  transports must be closed by the same task that opened them. Other threads (Streamlit,
  the agents) submit calls to that loop with run_coroutine_threadsafe and wait for the result.
- If MCP cannot start (or is switched off with ZEROPLATE_USE_MCP=0), the hub falls back to
  calling the very same tool functions in-process, so the demo never dies. `mode` says which.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import os
import sys
import threading
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

from zeroplate import config
from zeroplate.mcp_client.allowlist import ToolNotAllowed, check

EDUCATION_STUB = config.ROOT / "tests" / "fixtures" / "education_stub.py"


class ToolError(RuntimeError):
    """A tool ran but failed (bad arguments, missing data, ...)."""


@dataclass(frozen=True)
class ServerSpec:
    """A server to start: a module name (python -m) or a path to a .py file."""

    name: str
    target: str

    @property
    def args(self) -> list[str]:
        return [self.target] if self.target.endswith(".py") else ["-m", self.target]

    def load_module(self) -> ModuleType:
        if not self.target.endswith(".py"):
            return importlib.import_module(self.target)
        spec = importlib.util.spec_from_file_location(f"_zp_{self.name}", self.target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


@dataclass
class CallRecord:
    """One tool call, for the trace and the tool-efficiency metrics."""

    agent: str
    tool: str
    ms: int
    ok: bool
    blocked: bool = False
    error: str = ""


def default_servers() -> list[ServerSpec]:
    """The three department servers. Education is Anhad's; until it exists, use the test stub."""
    education = os.environ.get("ZEROPLATE_EDUCATION_SERVER", config.EDUCATION_SERVER)
    if not education.endswith(".py") and importlib.util.find_spec(education) is None:
        education = str(EDUCATION_STUB)
    return [
        ServerSpec("education", education),
        ServerSpec("supply", "zeroplate.mcp_servers.supply_server"),
        ServerSpec("finance", "zeroplate.mcp_servers.finance_server"),
    ]


@dataclass
class MCPHub:
    servers: list[ServerSpec] = field(default_factory=default_servers)
    use_mcp: bool = config.USE_MCP
    timeout_s: float = 60
    mode: str = "stopped"  # "mcp", "in-process" or "stopped"
    start_error: str = ""
    calls: list[CallRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._modules: dict[str, ModuleType] = {}
        self._tools: dict[str, list[str]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._serve_future = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ lifecycle
    def start(self) -> MCPHub:
        """Connect to every server over MCP, or fall back to in-process calls."""
        if self.mode != "stopped":
            return self
        if self.use_mcp:
            try:
                self._start_mcp()
                self.mode = "mcp"
                return self
            except Exception as exc:  # noqa: BLE001 - any failure means: use the fallback
                self.start_error = f"{type(exc).__name__}: {exc}"
                self._shutdown_loop()
        for spec in self.servers:
            module = spec.load_module()
            self._modules[spec.name] = module
            self._tools[spec.name] = sorted(t.name for t in asyncio.run(module.mcp.list_tools()))
        self.mode = "in-process"
        return self

    def _start_mcp(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="mcp-hub", daemon=True).start()
        ready = threading.Event()
        self._serve_future = asyncio.run_coroutine_threadsafe(self._serve(ready), self._loop)
        if not ready.wait(self.timeout_s):
            raise TimeoutError("MCP servers did not start in time")
        if self._serve_future.done():  # _serve ended early: it failed while connecting
            self._serve_future.result()

    async def _serve(self, ready: threading.Event) -> None:
        """Open every session, signal ready, then hold them open until close()."""
        src = str(config.ROOT / "src")
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(filter(None, [src, os.environ.get("PYTHONPATH")])),
            "FASTMCP_LOG_LEVEL": "WARNING",  # servers otherwise log every request to stderr
        }
        self._stop = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                # server logs go to a file, not the console
                log_dir = config.OUTPUTS_DIR / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                # opened once at start-up (a blocking open is fine here) and closed by the stack
                log = log_dir / "mcp_servers.log"
                f = open(log, "a", encoding="utf-8")  # noqa: ASYNC230, SIM115
                errlog = stack.enter_context(f)
                for spec in self.servers:
                    params = StdioServerParameters(command=sys.executable, args=spec.args, env=env)
                    read, write = await stack.enter_async_context(
                        stdio_client(params, errlog=errlog)
                    )
                    session = await stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    tools = await session.list_tools()
                    self._sessions[spec.name] = session
                    self._tools[spec.name] = sorted(t.name for t in tools.tools)
                ready.set()
                await self._stop.wait()
        finally:
            ready.set()  # never leave start() waiting if connecting failed

    def close(self) -> None:
        """Stop the servers (MCP mode) and the background loop."""
        if self.mode == "mcp" and self._loop and self._stop:
            self._loop.call_soon_threadsafe(self._stop.set)
            try:
                self._serve_future.result(timeout=10)
            except Exception:  # noqa: BLE001, S110 - closing must never raise
                pass
        self._shutdown_loop()
        self._sessions.clear()
        self.mode = "stopped"

    def _shutdown_loop(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------ discovery
    def tools(self) -> dict[str, list[str]]:
        """Tools discovered on each server, e.g. {"supply": ["get_menu", ...]}."""
        return dict(self._tools)

    # ------------------------------------------------------------ calls
    def call(self, agent: str, tool: str, args: dict[str, Any] | None = None) -> Any:
        """Call `tool` ("server.name") on behalf of `agent`; returns the tool's JSON result."""
        args = args or {}
        started = time.perf_counter()
        try:
            check(agent, tool)
        except ToolNotAllowed as exc:
            self._record(agent, tool, started, ok=False, blocked=True, error=str(exc))
            raise
        server, name = tool.split(".", 1)
        try:
            result = (
                self._call_mcp(server, name, args)
                if self.mode == "mcp"
                else self._call_local(server, name, args)
            )
        except Exception as exc:
            self._record(agent, tool, started, ok=False, error=str(exc))
            raise ToolError(f"{tool} failed: {exc}") from exc
        self._record(agent, tool, started, ok=True)
        return result

    def _call_mcp(self, server: str, name: str, args: dict) -> Any:
        session = self._sessions[server]
        fut = asyncio.run_coroutine_threadsafe(session.call_tool(name, args), self._loop)
        res = fut.result(timeout=self.timeout_s)
        text = "".join(getattr(c, "text", "") for c in res.content)
        if res.isError:
            raise ToolError(text)
        data = res.structuredContent
        if data is None:
            return json.loads(text)
        return data["result"] if set(data) == {"result"} else data

    def _call_local(self, server: str, name: str, args: dict) -> Any:
        fn = getattr(self._modules[server], name)
        # round-trip through JSON so in-process results look exactly like MCP results
        return json.loads(json.dumps(fn(**args), default=str))

    def read_resource(self, uri: str) -> str:
        """Read a read-only MCP resource, e.g. "education://academic_calendar"."""
        server = uri.split("://", 1)[0]
        if self.mode == "mcp":
            fut = asyncio.run_coroutine_threadsafe(
                self._sessions[server].read_resource(AnyUrl(uri)), self._loop
            )
            return fut.result(timeout=self.timeout_s).contents[0].text
        contents = asyncio.run(self._modules[server].mcp.read_resource(uri))
        return next(iter(contents)).content

    def _record(self, agent, tool, started, ok, blocked=False, error="") -> None:
        ms = int((time.perf_counter() - started) * 1000)
        with self._lock:
            self.calls.append(CallRecord(agent, tool, ms, ok, blocked, error))


def module_path(name: str) -> Path:
    """Filesystem path of a server module (used by the UI to show where tools live)."""
    spec = importlib.util.find_spec(name)
    return Path(spec.origin) if spec and spec.origin else Path(name)
