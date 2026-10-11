"""The evaluation harness: every scenario behaves as expected, and the backtest beats the habit."""

from zeroplate.eval.run_eval import backtest, run_scenarios


def test_every_scenario_passes(ctx):
    results = run_scenarios(ctx)
    assert [r["id"] for r in results if not r["passed"]] == []


def test_revisions_reuse_observations(ctx):
    s1 = next(r for r in run_scenarios(ctx) if r["id"] == "S1")
    # 2 revisions, but past attendance is fetched only once (short-term memory)
    assert s1["revisions"] == 2 and s1["tool_calls"] < 300


def test_backtest_beats_the_old_habit():
    b = backtest(days=30)
    assert b["waste_plates_reduction_pct"] > 0
    assert b["agents"]["short"] < b["old_habit"]["short"]
    assert b["forecast_mape_pct"] < 15
