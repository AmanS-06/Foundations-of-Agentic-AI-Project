"""The Critic's six rules (PROJECT_PLAN 6). Each takes plain data and returns a RuleCheck.

C1  each dish within 0.5x-1.5x of past days of the SAME event type (sanity, event-aware)
C2  planned between the forecast mean and mean x 1.15; "use first" ingredients are used
C4  food cost within the daily budget (from the Finance server)
C5  veg and Jain dishes keep at least their fairness minimum (responsible AI)
C6  every number in the model-written summary matches a tool output (hallucination check)
C9  reused leftovers pass the FSSAI reuse rule (food safety, grounded in the knowledge base)
plus a schema check: the plan re-validates against its Pydantic model (output validation).
"""

from __future__ import annotations

import math
import statistics
from datetime import date

from pydantic import ValidationError

from zeroplate import config
from zeroplate.guardrails.fact_check import collect_numbers, unsupported_numbers
from zeroplate.guardrails.food_safety import reuse_verdict
from zeroplate.schemas import (
    Diet,
    Event,
    HistoryRow,
    LeftoverBatch,
    MenuItem,
    ProductionPlan,
    RuleCheck,
)


def c1_event_aware_range(
    plan: ProductionPlan, history: list[HistoryRow], events: dict[date, Event]
) -> RuleCheck:
    event = events[plan.plan_date]
    problems, compared = [], 0
    for d in plan.dishes:
        past = [r.demand for r in history if r.dish == d.dish and events.get(r.date) == event]
        if not past:
            continue  # nothing comparable: the forecast is already flagged low-confidence
        compared += 1
        ratio = d.planned / statistics.fmean(past)
        if not config.C1_MIN_RATIO <= ratio <= config.C1_MAX_RATIO:
            problems.append(f"{d.dish} is {ratio:.2f}x the average {event.value} day")
    detail = "; ".join(problems) or f"{compared} dishes within range of past {event.value} days"
    return RuleCheck(rule_id="C1", name="Event-aware range", passed=not problems, detail=detail)


def c2_forecast_band(plan: ProductionPlan, menu: dict[str, MenuItem]) -> RuleCheck:
    problems = []
    for d in plan.dishes:
        low, high = d.forecast_mean, math.ceil(d.forecast_mean * (1 + config.C2_MAX_BUFFER)) + 1
        at_minimum = d.planned == menu[d.dish].min_portions
        if not (low <= d.planned <= high or at_minimum):
            problems.append(f"{d.dish}: {d.planned} plates outside {low:.0f}-{high}")
    unused = [n.ingredient for n in plan.ingredients if n.expires_soon and n.required == 0]
    if unused:
        problems.append(f"expiring stock not used: {', '.join(unused)}")
    detail = "; ".join(problems) or "all dishes between forecast and +15%; expiring stock used"
    return RuleCheck(rule_id="C2", name="Forecast band", passed=not problems, detail=detail)


def c4_budget(plan: ProductionPlan, budget: float) -> RuleCheck:
    ok = plan.food_cost <= budget
    detail = f"food cost Rs {plan.food_cost:,.0f} vs budget Rs {budget:,.0f}"
    if not ok:
        detail += f" (over by Rs {plan.food_cost - budget:,.0f})"
    return RuleCheck(rule_id="C4", name="Budget", passed=ok, detail=detail)


def c5_fairness(plan: ProductionPlan, menu: dict[str, MenuItem]) -> RuleCheck:
    problems = [
        f"{d.dish} has {d.planned}, minimum {menu[d.dish].min_portions}"
        for d in plan.dishes
        if menu[d.dish].diet in (Diet.VEG, Diet.JAIN) and d.planned < menu[d.dish].min_portions
    ]
    missing = [
        m.dish
        for m in menu.values()
        if m.diet in (Diet.VEG, Diet.JAIN) and m.dish not in {d.dish for d in plan.dishes}
    ]
    problems += [f"{dish} missing from the plan" for dish in missing]
    detail = "; ".join(problems) or "veg and Jain dishes at or above their minimum portions"
    return RuleCheck(rule_id="C5", name="Dietary fairness", passed=not problems, detail=detail)


def c6_fact_check(plan: ProductionPlan, extra_numbers: set[float] | None = None) -> RuleCheck:
    allowed = collect_numbers(plan.model_dump(mode="json", exclude={"summary"}))
    allowed |= extra_numbers or set()
    d = plan.plan_date
    allowed |= {float(d.year), float(d.month), float(d.day)}
    bad = unsupported_numbers(plan.summary, allowed)
    detail = (
        f"numbers not backed by any tool output: {', '.join(f'{n:g}' for n in bad)}"
        if bad
        else "every number in the summary matches a tool output"
    )
    return RuleCheck(rule_id="C6", name="Fact check", passed=not bad, detail=detail)


def c9_leftover_safety(
    plan: ProductionPlan, batches: list[LeftoverBatch], citation: str = ""
) -> RuleCheck:
    by_id = {b.batch_id: b for b in batches}
    problems = []
    for batch_id in plan.reused_batches:
        safe, reason = reuse_verdict(by_id[batch_id], plan.plan_date)
        if not safe:
            problems.append(f"{batch_id} ({by_id[batch_id].dish}): {reason}")
    if problems:
        detail = "unsafe to reuse: " + "; ".join(problems)
    else:
        detail = f"{len(plan.reused_batches)} reused batch(es) pass the FSSAI rule"
    if citation:
        detail += f" [source: {citation}]"
    return RuleCheck(rule_id="C9", name="Leftover safety", passed=not problems, detail=detail)


def schema_check(plan: ProductionPlan) -> RuleCheck:
    try:
        ProductionPlan.model_validate(plan.model_dump())
        return RuleCheck(rule_id="schema", name="Schema", passed=True, detail="plan is valid")
    except ValidationError as exc:
        return RuleCheck(rule_id="schema", name="Schema", passed=False, detail=str(exc)[:200])


def run_all(
    plan: ProductionPlan,
    history: list[HistoryRow],
    events: dict[date, Event],
    menu: dict[str, MenuItem],
    budget: float,
    batches: list[LeftoverBatch],
    citation: str = "",
    extra_numbers: set[float] | None = None,
) -> list[RuleCheck]:
    """Every rule, in a fixed order."""
    return [
        schema_check(plan),
        c1_event_aware_range(plan, history, events),
        c2_forecast_band(plan, menu),
        c4_budget(plan, budget),
        c5_fairness(plan, menu),
        c6_fact_check(plan, extra_numbers),
        c9_leftover_safety(plan, batches, citation),
    ]
