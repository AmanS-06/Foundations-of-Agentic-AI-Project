"""Orchestration: the five agents as one LangGraph state graph.

    START -> planner -> research -> executor -> critic --approve--> automation -> END
                                       ^            |--revise--> executor (at most 2 times)
                                       |____________|--escalate--> human -> END

Hierarchical, role-based collaboration: the Planner sets the work, each agent has one role and
its own tool allowlist, the Critic decides the route. Agents never call each other; they read
and write the shared state (message passing through state), and the graph moves control.
Each node is wrapped to record how long it took (latency metric for the evaluation).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from zeroplate.agents import automation, critic, executor, planner, research
from zeroplate.agents.base import DEFAULT_GOAL, AgentContext
from zeroplate.state import PlanState


def _timed(name: str, fn: Callable[[PlanState, AgentContext], dict], ctx: AgentContext):
    def node(state: PlanState) -> dict:
        started = time.perf_counter()
        update = fn(state, ctx)
        ms = int((time.perf_counter() - started) * 1000)
        return {
            **update,
            "timings": [{"agent": name, "ms": ms, "revision": state.get("revision", 0)}],
        }

    return node


def route_after_critic(state: PlanState) -> str:
    verdict = state["review"].verdict
    return {"approve": "automation", "revise": "executor", "escalate": "human"}[verdict]


def build_graph(ctx: AgentContext):
    g = StateGraph(PlanState)
    g.add_node("planner", _timed("planner", planner.run, ctx))
    g.add_node("research", _timed("research", research.run, ctx))
    g.add_node("executor", _timed("executor", executor.run, ctx))
    g.add_node("critic", _timed("critic", critic.run, ctx))
    g.add_node("automation", _timed("automation", automation.run, ctx))
    g.add_node("human", _timed("human", automation.escalate, ctx))
    g.add_edge(START, "planner")
    g.add_edge("planner", "research")
    g.add_edge("research", "executor")
    g.add_edge("executor", "critic")
    g.add_conditional_edges(
        "critic",
        route_after_critic,
        {"automation": "automation", "executor": "executor", "human": "human"},
    )
    g.add_edge("automation", END)
    g.add_edge("human", END)
    return g.compile()


def initial_state(
    plan_date: str,
    manager_note: str = "",
    budget_factor: float = 1.0,
    inject_summary_error: bool = False,
    goal: str = DEFAULT_GOAL,
) -> PlanState:
    """The state a run starts from."""
    return {
        "run_id": f"{plan_date}_{datetime.now():%H%M%S}_{uuid.uuid4().hex[:4]}",
        "goal": goal,
        "plan_date": plan_date,
        "manager_note": manager_note,
        "budget_factor": budget_factor,
        "inject_summary_error": inject_summary_error,
        "revision": 0,
        "status": "running",
        "messages": [],
        "trace": [],
        "timings": [],
        "attempts": [],
    }


def run_plan(ctx: AgentContext, plan_date: str, **options: Any) -> PlanState:
    """Run the whole team once and return the final state."""
    return build_graph(ctx).invoke(initial_state(plan_date, **options))


def stream_plan(ctx: AgentContext, plan_date: str, **options: Any) -> Iterator[tuple[str, Any]]:
    """Run the team and yield ("node", name) as each agent finishes, then ("final", state).
    Used by the UI to show progress live."""
    final = None
    for mode, chunk in build_graph(ctx).stream(
        initial_state(plan_date, **options), stream_mode=["updates", "values"]
    ):
        if mode == "updates":
            for name in chunk:
                yield "node", name
        else:
            final = chunk
    yield "final", final
