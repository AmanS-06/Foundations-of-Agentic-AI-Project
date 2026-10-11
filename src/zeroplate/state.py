"""The shared state of one planning run (short-term memory), passed between the agents.

LangGraph gives every node the current state and merges each node's returned dict into it.
Most keys are replaced by the newest value; `messages`, `trace` and `timings` are lists that
grow (their reducer is list concatenation), so every agent's messages and steps are kept.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from zeroplate.schemas import (
    ActionReport,
    AgentMessage,
    ProductionPlan,
    ResearchReport,
    Review,
    RevisionDecision,
    TaskPlan,
    TraceStep,
)


class PlanState(TypedDict, total=False):
    # inputs
    run_id: str
    goal: str
    plan_date: str  # ISO date
    manager_note: str
    budget_factor: float  # scenario: accounts cut the budget (0.7 = 30% cut)
    inject_summary_error: bool  # scenario: simulate a hallucinated number in the summary
    # agent outputs
    task_plan: TaskPlan
    research: ResearchReport
    plan: ProductionPlan
    review: Review
    decision: RevisionDecision
    actions: ActionReport
    # control
    revision: int  # how many times the Critic has sent the plan back
    attendance_cache: dict[str, int]  # observations kept between revisions (short-term memory)
    calendar_cache: dict[str, str]  # ISO date -> event type, also reused between revisions
    status: str  # running / approved / escalated
    # communication and observability (append-only)
    messages: Annotated[list[AgentMessage], operator.add]
    trace: Annotated[list[TraceStep], operator.add]
    timings: Annotated[list[dict[str, Any]], operator.add]
    attempts: Annotated[list[dict[str, Any]], operator.add]  # one entry per Critic review
