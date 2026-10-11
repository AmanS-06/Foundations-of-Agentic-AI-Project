"""What every agent shares: the context (tools, model, knowledge, memory) and a step recorder.

Agents never call each other. Each one is a function `run(state, ctx) -> dict` that reads the
shared state, uses tools through the MCP hub, and returns only the keys it changes plus its
trace steps and messages. This is the observation-action cycle of a tool-using agent:
think (record a thought), act (call a tool), observe (record the result).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from zeroplate.llm.client import LLM, LLMResult
from zeroplate.mcp_client.allowlist import ToolNotAllowed
from zeroplate.mcp_client.hub import MCPHub
from zeroplate.memory.long_term import Memory
from zeroplate.rag.retriever import KnowledgeBase
from zeroplate.schemas import AgentMessage, Event, TraceStep

DEFAULT_GOAL = (
    "Plan tomorrow's canteen production with minimum waste and no shortages, "
    "within the daily budget and food-safety rules."
)


@dataclass
class AgentContext:
    hub: MCPHub
    llm: LLM
    kb: KnowledgeBase | None = None
    memory: Memory | None = None


class Steps:
    """Records one agent's thoughts, tool calls and messages during a run."""

    def __init__(self, agent: str, ctx: AgentContext) -> None:
        self.agent, self.ctx = agent, ctx
        self.trace: list[TraceStep] = []
        self.messages: list[AgentMessage] = []

    def think(self, thought: str, observation: str = "") -> None:
        self.trace.append(TraceStep(agent=self.agent, thought=thought, observation=observation))

    def tool(self, tool: str, args: dict[str, Any] | None = None, thought: str = "") -> Any:
        """Act: call an MCP tool through the hub (allowlist enforced) and record the step."""
        started = time.perf_counter()
        try:
            result = self.ctx.hub.call(self.agent, tool, args or {})
        except ToolNotAllowed as exc:
            self.trace.append(
                TraceStep(
                    agent=self.agent,
                    thought=thought,
                    tool=tool,
                    args=args or {},
                    observation=str(exc),
                    blocked=True,
                )
            )
            raise
        self.trace.append(
            TraceStep(
                agent=self.agent,
                thought=thought,
                tool=tool,
                args=args or {},
                observation=_short(result),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )
        return result

    def llm(self, what: str, result: LLMResult) -> Any:
        """Record where a model answer came from (model / replay / deterministic policy)."""
        note = f" ({result.note})" if result.note else ""
        agree = f", {result.agreement:.0%} of samples agreed" if result.agreement < 1 else ""
        self.trace.append(
            TraceStep(
                agent=self.agent,
                thought=what,
                tool=f"llm:{result.source}",
                observation=f"{_short(result.value)}{note}{agree}",
            )
        )
        return result.value

    def say(self, receiver: str, intent: str, content: str) -> None:
        self.messages.append(
            AgentMessage(sender=self.agent, receiver=receiver, intent=intent, content=content)
        )

    def out(self, **updates: Any) -> dict:
        return {**updates, "trace": self.trace, "messages": self.messages}


def _short(value: Any, limit: int = 240) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def calendar_events(
    ctx: AgentContext, agent: str, days: list[date], cache: dict[str, str] | None = None
) -> tuple[dict[date, Event], dict[str, str]]:
    """Event type of every day in `days`, plus the updated cache (ISO date -> event).

    Cheapest source first: the run's short-term memory (cache); then the calendar resource, if
    the Education server publishes it as a JSON list of days; otherwise one
    education.get_calendar_event call per missing day.
    """
    cache = dict(cache or {})
    if any(d.isoformat() not in cache for d in days):
        try:
            rows = json.loads(ctx.hub.read_resource("education://academic_calendar"))
            cache.update({r["date"]: r["event"] for r in rows})
        except (ValueError, TypeError, KeyError):
            pass  # the resource is a text summary, not a list of days: ask day by day
        for d in days:
            if d.isoformat() not in cache:
                row = ctx.hub.call(agent, "education.get_calendar_event", {"date": d.isoformat()})
                cache[d.isoformat()] = row["event"]
    return {d: Event(cache[d.isoformat()]) for d in days}, cache
