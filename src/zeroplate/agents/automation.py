"""Business Automation agent: acts on an approved plan (the only agent with write tools).

Actions:
- raise one purchase order per supplier on the Supply server (write tool)
- log the plan's expected waste cost on the Finance server (write tool)
- write the kitchen prep sheet and the full plan to outputs/<run_id>/
- save a short lesson to long-term memory, so future runs for the same kind of day learn
Escalated runs are not acted on; they only leave a lesson in memory.
"""

from __future__ import annotations

from collections import defaultdict

from zeroplate import config
from zeroplate.agents.base import AgentContext, Steps
from zeroplate.schemas import ActionReport, ProductionPlan
from zeroplate.state import PlanState


def prep_sheet(plan: ProductionPlan) -> str:
    """The kitchen's to-do list as Markdown."""
    lines = [
        f"# Prep sheet for {plan.plan_date:%A %d %B %Y}",
        "",
        "| Dish | Cook | Reuse | Total | Why |",
        "|---|---:|---:|---:|---|",
    ]
    lines += [
        f"| {d.dish} | {d.cooked} | {d.reused} | {d.planned} | {d.reason} |" for d in plan.dishes
    ]
    first = [n.ingredient for n in plan.ingredients if n.expires_soon and n.required > 0]
    if first:
        lines += ["", f"**Use first (expires within 24 h):** {', '.join(first)}"]
    if plan.reused_batches:
        lines += ["", f"**Reheat once to 75 C before serving:** {', '.join(plan.reused_batches)}"]
    lines += ["", f"Food cost: Rs {plan.food_cost:,.0f}"]
    return "\n".join(lines) + "\n"


def lesson(state: PlanState) -> str:
    """One-line memory of this run for future runs of the same kind of day."""
    research, plan, review = state["research"], state["plan"], state["review"]
    failed = sorted({c.rule_id for c in review.checks if not c.passed})
    if state.get("status") == "escalated":
        return f"{research.event.value} {plan.plan_date}: escalated to a human ({', '.join(failed)} failing)"
    return (
        f"{research.event.value} {plan.plan_date}: approved after {state.get('revision', 0)} "
        f"revision(s) on the +{plan.chosen_buffer:.0%} branch, food cost Rs {plan.food_cost:,.0f}"
    )


def remember(state: PlanState, ctx: AgentContext, steps: Steps) -> None:
    if ctx.memory is None:
        return
    text = lesson(state)
    plan = state["plan"]
    ctx.memory.save_run(
        run_id=state["run_id"],
        plan_date=plan.plan_date.isoformat(),
        event=state["research"].event.value,
        status=state.get("status", "approved"),
        buffer=plan.chosen_buffer,
        food_cost=plan.food_cost,
        revisions=state.get("revision", 0),
        lesson=text,
    )
    steps.think("Save a lesson to long-term memory", text)


def run(state: PlanState, ctx: AgentContext) -> dict:
    steps = Steps("automation", ctx)
    plan = state["plan"]
    iso = plan.plan_date.isoformat()

    by_supplier: dict[str, list[dict]] = defaultdict(list)
    for line in plan.purchases:
        by_supplier[line.supplier].append(line.model_dump(mode="json"))
    po_ids = []
    for supplier, lines in sorted(by_supplier.items()):
        po = steps.tool(
            "supply.create_purchase_order",
            {"plan_date": iso, "lines": lines},
            f"Raise a purchase order with {supplier}",
        )
        po_ids.append(po["id"])

    chosen = next(c for c in plan.candidates if c.buffer == plan.chosen_buffer)
    steps.tool(
        "finance.log_waste_cost",
        {
            "date": iso,
            "amount": chosen.expected_waste_cost,
            "note": f"expected, run {state['run_id']}",
        },
        "Log the expected waste cost with accounts",
    )

    folder = config.OUTPUTS_DIR / state["run_id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "prep_sheet.md").write_text(prep_sheet(plan), encoding="utf-8")
    (folder / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    files = [str(folder / "prep_sheet.md"), str(folder / "plan.json")]
    steps.think("Write the prep sheet and the plan", ", ".join(files))

    remember(state, ctx, steps)
    report = ActionReport(
        purchase_order_ids=po_ids,
        prep_sheet=plan.dishes,
        waste_cost_logged=chosen.expected_waste_cost,
        files=files,
    )
    steps.say("planner", "result", f"Done: {len(po_ids)} purchase orders, prep sheet written.")
    return steps.out(actions=report, status="approved")


def escalate(state: PlanState, ctx: AgentContext) -> dict:
    """Escalation path: nothing is ordered; the run is remembered for next time."""
    steps = Steps("human", ctx)
    steps.think("Escalated to the canteen manager", state["review"].feedback)
    remember(state, ctx, steps)
    return steps.out(status="escalated")
