"""Executor agent: turns the research into a costed production plan (ReAct style).

Reason-act-observe: each tool call is preceded by a thought ("I need past demand per dish")
and followed by an observation, all recorded in the trace. The numbers come only from tools
and the pure domain functions; the model writes the plan's summary and, on a revision, reads
the Critic's feedback and decides what to change (RevisionDecision).

Division of labour with the Critic: the Executor optimises expected utility and tries to save
money by reusing leftovers; the Critic enforces budget, fairness and food safety. When the
Critic objects, the Executor revises within the new constraints.
"""

from __future__ import annotations

import math
import time
from datetime import date

from zeroplate.agents.base import AgentContext, Steps, calendar_events
from zeroplate.domain import costing, stocking
from zeroplate.domain.forecast import forecast_dish
from zeroplate.guardrails.food_safety import relevant_batches
from zeroplate.schemas import (
    DishForecast,
    DishPlan,
    HistoryRow,
    InventoryItem,
    LeftoverBatch,
    MenuItem,
    ProductionPlan,
    RecipeLine,
    RevisionDecision,
    SupplierOffer,
    TraceStep,
)
from zeroplate.state import PlanState

DECISION_SYSTEM = (
    "You are the Executor of a canteen-planning team. The Critic rejected your plan. Read its "
    "feedback and decide how to revise: a maximum food cost to stay within (only if the budget "
    "was exceeded), leftover batch ids that must not be reused (only those the Critic called "
    "unsafe), and whether the summary must be rewritten (if a number was wrong). Answer only "
    "with JSON matching the schema."
)
SUMMARY_SYSTEM = (
    "You are the Executor. Write a 2-3 sentence summary of the production plan for the kitchen "
    "manager. Copy numbers exactly from the plan data; do not add, total or round numbers."
)


def derive_decision(state: PlanState, budget: float) -> RevisionDecision:
    """Deterministic policy: read the failed rules and turn them into constraints."""
    review, plan = state["review"], state["plan"]
    previous = state.get("decision") or RevisionDecision(reasoning="")
    failed = {c.rule_id for c in review.checks if not c.passed}
    drop = set(previous.drop_batches)
    if "C9" in failed:
        unsafe = next(c.detail for c in review.checks if c.rule_id == "C9")
        drop |= {b for b in plan.reused_batches if b in unsafe}
    max_cost = budget if "C4" in failed else previous.max_food_cost
    reasons = []
    if "C9" in failed:
        reasons.append(f"stop reusing {', '.join(sorted(drop))}")
    if "C4" in failed:
        reasons.append(f"keep food cost within Rs {budget:,.0f}")
    if "C6" in failed:
        reasons.append("rewrite the summary from the plan data")
    return RevisionDecision(
        max_food_cost=max_cost,
        drop_batches=sorted(drop),
        regenerate_summary="C6" in failed,
        reasoning="; ".join(reasons) or "no change needed",
    )


def decide_revision(
    state: PlanState, ctx: AgentContext, steps: Steps, budget: float
) -> RevisionDecision:
    """Read the Critic's feedback (model, or deterministic policy) into constraints."""
    review, plan = state["review"], state["plan"]
    failed = [f"{c.rule_id}: {c.detail}" for c in review.checks if not c.passed]
    prompt = (
        f"Critic feedback: {review.feedback}\nFailed checks: {failed}\nDaily budget: {budget}\n"
        f"Leftover batches currently reused: {plan.reused_batches}"
    )
    result = ctx.llm.ask(
        "executor.revise",
        prompt,
        fallback=lambda: derive_decision(state, budget),
        schema=RevisionDecision,
        system=DECISION_SYSTEM,
    )
    decision = steps.llm("Read the Critic's feedback and decide what to change", result)
    # guardrail: a model may only tighten constraints, never loosen them
    rule_based = derive_decision(state, budget)
    if decision.max_food_cost is not None:
        decision.max_food_cost = min(decision.max_food_cost, budget)
    decision.max_food_cost = min(
        filter(None, [decision.max_food_cost, rule_based.max_food_cost]), default=None
    )
    decision.drop_batches = sorted(set(decision.drop_batches) | set(rule_based.drop_batches))
    decision.regenerate_summary = decision.regenerate_summary or rule_based.regenerate_summary
    return decision


def note_factors(state: PlanState, dishes: list[str]) -> dict[str, float]:
    """Demand multiplier per dish from the (clean) manager's note."""
    factors = dict.fromkeys(dishes, 1.0)
    note = state["research"].note
    if note.suspicious:
        return factors
    for event in note.events:
        if event.kind == "demand_change" and event.factor:
            for dish in [event.dish] if event.dish else dishes:
                factors[dish] *= event.factor
    return factors


def summary_template(plan: ProductionPlan, budget: float, best_utility: float) -> str:
    dishes = ", ".join(f"{d.dish} {d.planned}" for d in plan.dishes)
    reuse = (
        f" Reusing leftover batches {', '.join(plan.reused_batches)}."
        if plan.reused_batches
        else ""
    )
    return (
        f"Plan for {plan.plan_date}: {dishes} plates, using the +{plan.chosen_buffer * 100:g}% "
        f"branch (expected utility {best_utility:g}). Food cost Rs {plan.food_cost:,.0f} against "
        f"a budget of Rs {budget:,.0f}.{reuse} Purchase orders worth Rs {plan.purchase_cost:,.0f}."
    )


def run(state: PlanState, ctx: AgentContext) -> dict:
    steps = Steps("executor", ctx)
    plan_date = date.fromisoformat(state["plan_date"])
    iso = plan_date.isoformat()
    revision = state.get("revision", 0)

    budget_row = steps.tool("finance.get_daily_budget", {"date": iso}, "What may tomorrow cost?")
    budget = budget_row["daily_budget"] * state.get("budget_factor", 1.0)
    decision = state.get("decision")
    if revision > 0:
        decision = decide_revision(state, ctx, steps, budget)
        steps.say("critic", "result", f"Revising: {decision.reasoning}")

    # --- observe: everything the calculation needs
    history = [
        HistoryRow.model_validate(r)
        for r in steps.tool("supply.get_history", {"before": iso}, "I need past demand per dish")[
            "rows"
        ]
    ]
    events = calendar_events(ctx)
    steps.think("Read the academic calendar resource for past event types", f"{len(events)} days")
    days = sorted({r.date for r in history} | {plan_date})
    cache = state.get("attendance_cache") or {}
    if all(d.isoformat() in cache for d in days):
        present = {d: cache[d.isoformat()] for d in days}
        steps.think("Reuse past attendance from short-term memory", f"{len(days)} days, 0 calls")
    else:
        present = _attendance(ctx, steps, days)
        cache = {d.isoformat(): n for d, n in present.items()}
    menu = {
        m["dish"]: MenuItem.model_validate(m)
        for m in steps.tool("supply.get_menu", {}, "Which dishes?")["rows"]
    }
    recipes = [
        RecipeLine.model_validate(r)
        for r in steps.tool("supply.get_recipes", {}, "Recipes per plate")["rows"]
    ]
    inventory = [
        InventoryItem.model_validate(r)
        for r in steps.tool("supply.get_inventory", {}, "What is in stock?")["rows"]
    ]
    suppliers = [
        SupplierOffer.model_validate(r)
        for r in steps.tool("supply.get_suppliers", {}, "Who can deliver?")["rows"]
    ]
    batches = relevant_batches(
        [
            LeftoverBatch.model_validate(r)
            for r in steps.tool("supply.get_leftover_batches", {}, "Leftovers to reuse?")["rows"]
        ],
        plan_date,
    )

    # --- reason: forecast and choose quantities
    unavailable = {e.dish for e in state["research"].note.events if e.kind == "dish_unavailable"}
    dishes = [d for d in menu if d not in unavailable]
    factors = note_factors(state, dishes)
    forecasts = [forecast_dish(d, history, events, present, plan_date, factors[d]) for d in dishes]
    steps.think(
        "Forecast each dish (ensemble consensus of 3 methods, spread from backtest)",
        "; ".join(f"{f.dish} {f.mean:g}±{f.spread:g}" for f in forecasts),
    )
    candidates = stocking.generate_candidates(forecasts, menu)
    steps.think(
        "Tree-of-Thought: score each candidate buffer by expected utility (500 simulated days)",
        "; ".join(
            f"+{c.buffer:.0%}: utility {c.utility:g}, cost {c.food_cost:g}" for c in candidates
        ),
    )

    dropped = set(decision.drop_batches) if decision else set()
    reuse = [b for b in batches if b.batch_id not in dropped]
    reuse_by_dish: dict[str, int] = {}
    for b in reuse:
        reuse_by_dish[b.dish] = reuse_by_dish.get(b.dish, 0) + b.plates_left
    if reuse:
        steps.think(
            "Reuse leftover plates to save cost",
            ", ".join(f"{b.batch_id} ({b.dish}, {b.plates_left} plates)" for b in reuse),
        )

    def cooked_cost(c) -> float:
        cooked = {d: max(q - reuse_by_dish.get(d, 0), 0) for d, q in c.quantities.items()}
        return costing.food_cost(cooked, menu)

    max_cost = decision.max_food_cost if decision else None
    feasible = [c for c in candidates if max_cost is None or cooked_cost(c) <= max_cost]
    chosen = (
        max(feasible, key=lambda c: c.utility) if feasible else min(candidates, key=cooked_cost)
    )
    steps.think(
        "Choose the best branch" + (f" within Rs {max_cost:,.0f}" if max_cost else ""),
        f"+{chosen.buffer:.0%}" + ("" if feasible else " (NO branch fits the constraint)"),
    )

    # --- act: ingredients, purchases, cost (cost confirmed by the Finance server)
    cooked = {d: max(q - reuse_by_dish.get(d, 0), 0) for d, q in chosen.quantities.items()}
    required = costing.ingredients_required(cooked, recipes)
    needs = costing.ingredient_needs(required, inventory, plan_date)
    purchases, problems = costing.purchase_lines(needs, suppliers)
    cost = steps.tool("finance.cost_plan", {"quantities": cooked}, "Confirm the food cost")[
        "food_cost"
    ]

    by_dish = {f.dish: f for f in forecasts}
    plan = ProductionPlan(
        plan_date=plan_date,
        dishes=[
            _dish_plan(by_dish[d], q, cooked[d], chosen.buffer, menu[d])
            for d, q in chosen.quantities.items()
        ],
        ingredients=needs,
        purchases=purchases,
        food_cost=cost,
        purchase_cost=round(sum(p.cost for p in purchases), 2),
        candidates=candidates,
        chosen_buffer=chosen.buffer,
        reused_batches=sorted(b.batch_id for b in reuse),
        feasible=bool(feasible),
        notes=problems
        + ([] if feasible else [f"no candidate fits a food cost of Rs {max_cost:,.0f}"]),
        summary="",
    )

    # --- the model words the summary; the Critic fact-checks every number in it
    template = summary_template(plan, budget, chosen.utility)
    if decision and decision.regenerate_summary:
        plan.summary = template
        steps.think(
            "Rewrite the summary from the plan data (Critic found a wrong number)", template
        )
    else:
        result = ctx.llm.ask(
            "executor.summary",
            f"Plan data: {plan.model_dump_json(exclude={'candidates', 'ingredients', 'summary'})}\n"
            f"Budget: {budget}\nChosen utility: {chosen.utility}",
            fallback=lambda: template,
            system=SUMMARY_SYSTEM,
        )
        plan.summary = steps.llm("Write the plan summary", result)
    if state.get("inject_summary_error") and revision == 0:
        wrong = f"{plan.food_cost * 0.8:,.0f}"
        plan.summary += f" Total spend today is only Rs {wrong}."
        steps.trace.append(
            TraceStep(
                agent="executor",
                thought="[scenario] simulate a hallucinated number",
                observation=f"added 'Rs {wrong}'",
            )
        )

    steps.say("critic", "request", f"Please review: {plan.summary}")
    return steps.out(plan=plan, decision=decision, attendance_cache=cache)


def _attendance(ctx: AgentContext, steps: Steps, days: list[date]) -> dict[date, int]:
    """Expected attendance for every past day (one MCP call per day, traced as one step)."""
    started, present = time.perf_counter(), {}
    for d in days:
        row = ctx.hub.call("executor", "education.get_expected_attendance", {"date": d.isoformat()})
        present[d] = row["expected_present"]
    steps.trace.append(
        TraceStep(
            agent="executor",
            thought="Past attendance for the plates-per-student method",
            tool="education.get_expected_attendance",
            args={"days": len(days)},
            observation=f"{len(days)} calls",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    )
    return present


def _dish_plan(
    f: DishForecast, planned: int, cooked: int, buffer: float, item: MenuItem
) -> DishPlan:
    reused = planned - cooked
    if planned == item.min_portions and planned > math.ceil(f.mean * (1 + buffer)):
        why = f"fairness minimum of {item.min_portions} plates"
    else:
        names = {
            "event_average": "event avg",
            "event_trend": "trend",
            "attendance_ratio": "attendance",
        }
        methods = ", ".join(f"{names.get(k, k)} {v:.0f}" for k, v in f.methods.items())
        why = f"forecast {f.mean:.0f} ± {f.spread:.0f} ({methods}) + {buffer:.0%} buffer"
    if reused:
        why += f"; {reused} plates from safe leftovers"
    return DishPlan(
        dish=f.dish,
        planned=planned,
        cooked=cooked,
        reused=reused,
        forecast_mean=f.mean,
        forecast_spread=f.spread,
        low_confidence=f.low_confidence,
        reason=why,
    )
