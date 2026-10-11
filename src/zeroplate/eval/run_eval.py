"""Evaluation harness (Unit 5): scenario benchmark + held-out backtest against the old process.

Two parts:
1. Scenario benchmark. Run the whole agent team on the six scenarios and measure
   task completion (did it reach the expected outcome?), revisions, latency per agent, tool
   calls (tool efficiency), blocked calls, and where model answers came from. Cost is Rs 0:
   everything runs locally.
2. Held-out backtest. For each of the last N days of history, plan that day using only the
   data before it, and compare with the true demand: waste and shortage of the stocking
   calculation vs the canteen's old habit (last week's sales + 15%), plus forecast error.
   Run it on a dataset the forecaster was not designed on (another seed) for an honest result.

Usage:  python -m zeroplate.eval.run_eval [--raw-dir PATH] [--days 30] [--mcp]
Writes outputs/eval/report.json and report.md.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path

from zeroplate import config
from zeroplate.agents.base import AgentContext
from zeroplate.domain import stocking
from zeroplate.domain.data import load_table
from zeroplate.domain.forecast import forecast_dish
from zeroplate.eval.scenarios import SCENARIOS
from zeroplate.graph import run_plan
from zeroplate.llm.client import LLM
from zeroplate.mcp_client.hub import MCPHub
from zeroplate.memory.long_term import Memory
from zeroplate.rag.retriever import KnowledgeBase


def run_scenarios(ctx: AgentContext) -> list[dict]:
    """Run each scenario once and score it."""
    results = []
    for sc in SCENARIOS:
        calls_before = len(ctx.hub.calls)
        started = time.perf_counter()
        state = run_plan(ctx, **sc.options)
        elapsed = int((time.perf_counter() - started) * 1000)
        calls = ctx.hub.calls[calls_before:]
        per_agent: Counter = Counter()
        for t in state["timings"]:
            per_agent[t["agent"]] += t["ms"]
        sources = Counter(
            s.tool.split(":", 1)[1] for s in state["trace"] if s.tool and s.tool.startswith("llm:")
        )
        results.append(
            {
                "id": sc.id,
                "name": sc.name,
                "expected": sc.expected,
                "passed": bool(sc.check(state)),
                "status": state["status"],
                "revisions": state["revision"],
                "attempts": [
                    {k: a[k] for k in ("attempt", "buffer", "food_cost", "failed", "verdict")}
                    for a in state["attempts"]
                ],
                "latency_ms": elapsed,
                "latency_by_agent_ms": dict(per_agent),
                "tool_calls": len(calls),
                "failed_tool_calls": sum(not c.ok and not c.blocked for c in calls),
                "blocked_tool_calls": sum(c.blocked for c in calls),
                "llm_answers": dict(sources),
            }
        )
    return results


def backtest(raw_dir: Path | None = None, days: int = 30) -> dict:
    """Plan each of the last `days` days from earlier data only; compare with true demand."""
    history = load_table("history", raw_dir)
    events = {r.date: r.event for r in load_table("calendar", raw_dir)}
    present = {r.date: r.expected_present for r in load_table("attendance", raw_dir)}
    menu = {m.dish: m for m in load_table("menu", raw_dir)}
    test_days = sorted({r.date for r in history})[-days:]
    truth = {(r.date, r.dish): r for r in history}

    agent = {"waste": 0, "short": 0, "waste_cost": 0.0, "short_cost": 0.0}
    habit = dict(agent)
    abs_pct_errors = []
    for day in test_days:
        forecasts = [forecast_dish(d, history, events, present, day) for d in menu]
        best = stocking.choose(stocking.generate_candidates(forecasts, menu))
        for f in forecasts:
            row, cost = truth[(day, f.dish)], menu[f.dish].cost_per_plate
            abs_pct_errors.append(abs(f.mean - row.demand) / max(row.demand, 1))
            for result, cooked in ((agent, best.quantities[f.dish]), (habit, row.prepared)):
                waste, short = max(cooked - row.demand, 0), max(row.demand - cooked, 0)
                result["waste"] += waste
                result["short"] += short
                result["waste_cost"] += waste * cost
                result["short_cost"] += short * cost

    def reduction(key: str) -> float:
        return round(100 * (habit[key] - agent[key]) / habit[key], 1) if habit[key] else 0.0

    return {
        "days": len(test_days),
        "from": test_days[0].isoformat(),
        "to": test_days[-1].isoformat(),
        "forecast_mape_pct": round(100 * statistics.fmean(abs_pct_errors), 1),
        "agents": {k: round(v, 1) for k, v in agent.items()},
        "old_habit": {k: round(v, 1) for k, v in habit.items()},
        "waste_plates_reduction_pct": reduction("waste"),
        "waste_cost_reduction_pct": reduction("waste_cost"),
        "shortage_plates_reduction_pct": reduction("short"),
    }


def to_markdown(report: dict) -> str:
    lines = ["# ZeroPlate evaluation (simulation on synthetic data)", ""]
    lines += [
        f"Data: `{report['raw_dir']}` | hub mode: {report['hub_mode']} | LLM mode: {report['llm_mode']}",
        "",
    ]
    lines += [
        "## Scenario benchmark",
        "",
        "| ID | Scenario | Passed | Status | Revisions | Latency (ms) | Tool calls | Blocked |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for r in report["scenarios"]:
        lines.append(
            f"| {r['id']} | {r['name']} | {'yes' if r['passed'] else 'NO'} | {r['status']} | "
            f"{r['revisions']} | {r['latency_ms']} | {r['tool_calls']} | {r['blocked_tool_calls']} |"
        )
    s = report["summary"]
    completion = (
        f"Task completion: **{s['passed']}/{s['total']}** scenarios behaved as expected. "
        f"Average latency {s['avg_latency_ms']} ms per run, "
        f"{s['avg_tool_calls']} tool calls per run. API cost: Rs 0 (local)."
    )
    lines += ["", completion, ""]

    b = report["backtest"]

    def row(label: str, r: dict) -> str:
        return (
            f"| {label} | {r['waste']:g} | {r['short']:g} | "
            f"{r['waste_cost']:,.0f} | {r['short_cost']:,.0f} |"
        )

    verdict = (
        f"Waste reduced by **{b['waste_plates_reduction_pct']}%** (plates) and "
        f"{b['waste_cost_reduction_pct']}% (cost); shortages reduced by "
        f"{b['shortage_plates_reduction_pct']}%. Forecast error (MAPE): {b['forecast_mape_pct']}%."
    )
    lines += [
        f"## Held-out backtest ({b['days']} days, {b['from']} to {b['to']})",
        "",
        "| | Wasted plates | Short plates | Waste cost (Rs) | Shortage cost (Rs) |",
        "|---|---:|---:|---:|---:|",
        row("Old habit (last week + 15%)", b["old_habit"]),
        row("ZeroPlate (forecast + stocking calc.)", b["agents"]),
        "",
        verdict,
    ]
    return "\n".join(lines) + "\n"


def evaluate(ctx: AgentContext, raw_dir: Path | None = None, days: int = 30) -> dict:
    scenarios = run_scenarios(ctx)
    report = {
        "raw_dir": str(raw_dir or config.RAW_DIR),
        "hub_mode": ctx.hub.mode,
        "llm_mode": ctx.llm.mode,
        "scenarios": scenarios,
        "summary": {
            "passed": sum(r["passed"] for r in scenarios),
            "total": len(scenarios),
            "avg_latency_ms": int(statistics.fmean(r["latency_ms"] for r in scenarios)),
            "avg_tool_calls": round(statistics.fmean(r["tool_calls"] for r in scenarios), 1),
        },
        "backtest": backtest(raw_dir, days),
    }
    out = config.OUTPUTS_DIR / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=None, help="dataset for the backtest")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--mcp", action="store_true", help="use real MCP servers (slower start)")
    parser.add_argument("--llm", default="deterministic", help="deterministic / replay / ollama")
    args = parser.parse_args()
    with MCPHub(use_mcp=args.mcp) as hub:
        memory = Memory(config.OUTPUTS_DIR / "eval" / "memory.db")
        ctx = AgentContext(hub, LLM(args.llm), KnowledgeBase(config.KB_DIR), memory)
        report = evaluate(ctx, args.raw_dir, args.days)
    print(to_markdown(report))
    print(f"(written to {config.OUTPUTS_DIR / 'eval'})")


if __name__ == "__main__":
    main()
