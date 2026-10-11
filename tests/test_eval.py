"""The evaluation harness: every scenario behaves as expected, and the backtest beats the habit."""

from zeroplate.eval.run_eval import backtest, run_scenarios
from zeroplate.graph import run_plan


def test_every_scenario_passes(ctx):
    results = run_scenarios(ctx)
    assert [r["id"] for r in results if not r["passed"]] == []


def test_revisions_reuse_observations(ctx):
    # S1 needs 2 revisions, but each past day's attendance is fetched only once per run:
    # the Executor keeps its observations in the run's short-term memory (the graph state)
    history = ctx.hub.call("executor", "supply.get_history", {"before": "2026-10-16"})["rows"]
    days = len({r["date"] for r in history}) + 1  # past days plus the plan date
    before = len(ctx.hub.calls)
    state = run_plan(ctx, "2026-10-16")
    calls = [c for c in ctx.hub.calls[before:] if c.tool == "education.get_expected_attendance"]
    assert state["revision"] == 2
    assert len(calls) == days + 1  # each day once (Executor) + the plan date once (Research)


def test_backtest_beats_the_old_habit():
    b = backtest(days=30)
    assert b["waste_plates_reduction_pct"] > 0
    assert b["agents"]["short"] < b["old_habit"]["short"]
    assert b["forecast_mape_pct"] < 15
