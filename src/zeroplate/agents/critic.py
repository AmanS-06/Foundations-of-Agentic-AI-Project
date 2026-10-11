"""Critic agent: validates the plan, then approves it, sends it back, or escalates to a human.

The Critic does not trust the Executor's numbers: it fetches the budget, menu, history and
leftover batches itself and runs the six rules (plus a schema check) on them. The VERDICT is
decided by the rules alone; the language model only writes the feedback in plain words, which
the Executor then reads to decide its revision.

Verdict logic
- every check passes                          -> approve
- a check fails and no plan can satisfy it    -> escalate (a human must decide)
- a check fails after MAX_REVISIONS revisions -> escalate
- otherwise                                   -> revise (send back with feedback)
"""

from __future__ import annotations

from zeroplate import config
from zeroplate.agents.base import AgentContext, Steps, calendar_events
from zeroplate.guardrails import rules
from zeroplate.schemas import HistoryRow, LeftoverBatch, MenuItem, Review, RuleCheck
from zeroplate.state import PlanState

FEEDBACK_SYSTEM = (
    "You are the Critic of a canteen-planning team. Explain to the Executor, in 2-3 sentences, "
    "which checks failed and what must change. Be specific and use only the details given."
)


def feedback_template(failed: list[RuleCheck]) -> str:
    """Deterministic policy for the feedback text."""
    if not failed:
        return "All checks passed. Approved."
    return "Please revise: " + " ".join(f"[{c.rule_id} {c.name}] {c.detail}." for c in failed)


def run(state: PlanState, ctx: AgentContext) -> dict:
    steps = Steps("critic", ctx)
    plan = state["plan"]
    iso = plan.plan_date.isoformat()
    revision = state.get("revision", 0)

    budget = steps.tool("finance.get_daily_budget", {"date": iso}, "Check the budget myself")[
        "daily_budget"
    ] * state.get("budget_factor", 1.0)
    menu = {
        m["dish"]: MenuItem.model_validate(m)
        for m in steps.tool("supply.get_menu", {}, "Menu minimums for fairness")["rows"]
    }
    history = [
        HistoryRow.model_validate(r)
        for r in steps.tool("supply.get_history", {"before": iso}, "Past days for the range check")[
            "rows"
        ]
    ]
    batches = [
        LeftoverBatch.model_validate(r)
        for r in steps.tool("supply.get_leftover_batches", {}, "Leftovers the plan reuses")["rows"]
    ]
    events = calendar_events(ctx)

    citation = ""
    research = state.get("research")
    safety = [c for c in (research.citations if research else []) if "safety" in c.source.lower()]
    if safety:
        citation = f"{safety[0].source} > {safety[0].section}"

    checks = rules.run_all(
        plan, history, events, menu, budget, batches, citation, extra_numbers={budget}
    )
    for c in checks:
        steps.think(f"Rule {c.rule_id}: {c.name}", ("PASS: " if c.passed else "FAIL: ") + c.detail)
    failed = [c for c in checks if not c.passed]

    if not failed:
        verdict = "approve"
    elif not plan.feasible or revision >= config.MAX_REVISIONS:
        verdict = "escalate"
    else:
        verdict = "revise"

    result = ctx.llm.ask(
        "critic.feedback",
        f"Verdict: {verdict}\nFailed checks: {[f'{c.rule_id} {c.name}: {c.detail}' for c in failed]}",
        fallback=lambda: feedback_template(failed),
        system=FEEDBACK_SYSTEM,
    )
    feedback = steps.llm("Explain the verdict to the Executor", result)
    review = Review(verdict=verdict, checks=checks, feedback=feedback, attempt=revision + 1)
    attempt = {
        "attempt": revision + 1,
        "buffer": plan.chosen_buffer,
        "food_cost": plan.food_cost,
        "budget": budget,
        "reused": plan.reused_batches,
        "failed": [c.rule_id for c in failed],
        "verdict": verdict,
        "feedback": feedback,
    }

    if verdict == "approve":
        steps.say("automation", "request", "Plan approved. Please act on it.")
        return steps.out(review=review, status="approved", attempts=[attempt])
    if verdict == "escalate":
        why = (
            "no plan can satisfy the rules"
            if not plan.feasible
            else "still failing after revisions"
        )
        steps.say("human", "escalate", f"Needs a human decision ({why}): {feedback}")
        return steps.out(review=review, status="escalated", attempts=[attempt])
    steps.say("executor", "feedback", feedback)
    return steps.out(review=review, revision=revision + 1, attempts=[attempt])
