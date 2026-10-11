"""The whole system, run on the project's real (synthetic) dataset, behaves as the demo and the report claim.

Every other test runs on the small sample data in tests/fixtures. These run the six benchmark scenarios on
data/raw, with the knowledge base in data/kb and the recorded model answers in data/recordings, each in a
fresh process (so the sample-data settings of tests/conftest.py do not leak in). They protect the things
that were checked by hand on 11 October:

  - all six scenarios behave as expected on the real data;
  - in replay mode every model answer comes from the recording, none falls back to the fixed rules;
  - the leftovers that are reused are exactly the ones the knowledge base says are safe (B2 and B4), and
    never the unsafe ones (B1, B3, B5), judged by the knowledge base and not by the code under test;
  - a scenario needs about 215 tool calls, not 400 (the calendar must reach the agents in one read);
  - starting the real MCP servers gives the same results as the in-process fallback;
  - the held-out backtest keeps its headline result.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The leftover batches in data/raw/batches.csv and what data/kb/food_safety_fssai.md says about each
# ("Project interpretation (ours)"): may it be served again on the plan date?
KB_SAYS_REUSABLE = {"B1": False, "B2": True, "B3": False, "B4": True, "B5": False}

RUN_SCENARIOS = """
import json, sys
from zeroplate import config
from zeroplate.agents.base import AgentContext
from zeroplate.eval.scenarios import SCENARIOS
from zeroplate.graph import run_plan
from zeroplate.llm.client import LLM
from zeroplate.mcp_client.hub import MCPHub
from zeroplate.memory.long_term import Memory
from zeroplate.rag.retriever import KnowledgeBase

out = []
with MCPHub(use_mcp=sys.argv[1] == "mcp") as hub:
    ctx = AgentContext(hub, LLM("replay"), KnowledgeBase(config.KB_DIR),
                       Memory(config.OUTPUTS_DIR / "system_test.db"))
    for sc in SCENARIOS:
        before = len(hub.calls)
        state = run_plan(ctx, **sc.options)
        sources = {}
        for step in state["trace"]:
            if step.tool and step.tool.startswith("llm:"):
                key = step.tool.split(":", 1)[1]
                sources[key] = sources.get(key, 0) + 1
        plan = state.get("plan")
        out.append({
            "id": sc.id, "passed": bool(sc.check(state)), "status": state["status"],
            "reused": sorted(plan.reused_batches) if plan else None,
            "plan_date": sc.options["plan_date"], "llm": sources, "calls": len(hub.calls) - before,
        })
    mode = hub.mode
print(json.dumps({"hub": mode, "scenarios": out}))
"""


def _env(tmp_path: Path, raw: str = "raw") -> dict[str, str]:
    """A clean environment that points the code at the real data, not at the test fixtures."""
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "ZEROPLATE_RAW_DIR": str(ROOT / "data" / raw),
            "ZEROPLATE_OUTPUTS_DIR": str(tmp_path / "outputs"),
            "ZEROPLATE_MEMORY_DB": str(tmp_path / "memory.db"),
            "ZEROPLATE_LLM_MODE": "replay",
        }
    )
    return env


def _run_scenarios(tmp_path: Path, hub_mode: str) -> dict:
    done = subprocess.run(
        [sys.executable, "-c", RUN_SCENARIOS, hub_mode],
        env=_env(tmp_path),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def in_process(tmp_path_factory):
    return _run_scenarios(tmp_path_factory.mktemp("inproc"), "inprocess")


@pytest.fixture(scope="module")
def over_mcp(tmp_path_factory):
    return _run_scenarios(tmp_path_factory.mktemp("mcp"), "mcp")


def test_all_six_scenarios_behave_as_expected_on_the_real_data(in_process):
    results = in_process["scenarios"]
    assert [r["id"] for r in results] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    failed = [r["id"] for r in results if not r["passed"]]
    assert not failed, f"scenarios that did not behave as expected: {failed}"
    assert {r["id"]: r["status"] for r in results} == {
        "S1": "approved",
        "S2": "approved",
        "S3": "escalated",
        "S4": "approved",
        "S5": "approved",
        "S6": "approved",
    }


def test_every_model_answer_comes_from_the_recording(in_process):
    """If a prompt or the data changes, replay silently falls back to the fixed rules. This catches that."""
    for r in in_process["scenarios"]:
        assert r["llm"], f"{r['id']}: no model answers at all"
        assert set(r["llm"]) == {
            "replay"
        }, f"{r['id']}: answers from {r['llm']}, expected only replay"
    assert sum(sum(r["llm"].values()) for r in in_process["scenarios"]) == 42


def test_the_batches_that_are_reused_are_the_ones_the_knowledge_base_allows(in_process):
    approved_on_the_fest = [
        r
        for r in in_process["scenarios"]
        if r["status"] == "approved" and r["plan_date"] == "2026-10-16"
    ]
    assert len(approved_on_the_fest) >= 4
    for r in approved_on_the_fest:
        reused = set(r["reused"])
        wrong = {b for b in reused if not KB_SAYS_REUSABLE[b]}
        missed = {b for b, ok in KB_SAYS_REUSABLE.items() if ok and b not in reused}
        assert (
            not wrong
        ), f"{r['id']}: reused batches the knowledge base says are unsafe: {sorted(wrong)}"
        assert not missed, f"{r['id']}: did not reuse safe batches: {sorted(missed)}"


def test_the_batch_list_in_the_data_is_the_one_the_knowledge_base_describes():
    import csv

    with open(ROOT / "data" / "raw" / "batches.csv", newline="", encoding="utf-8") as f:
        ids = [row["batch_id"] for row in csv.DictReader(f)]
    assert sorted(ids) == sorted(KB_SAYS_REUSABLE)


def test_a_scenario_needs_about_215_tool_calls_not_400(in_process):
    """The Critic and Executor must get the calendar from one JSON read of the Education server, not
    one call per day (393 calls per scenario when the calendar resource was text)."""
    calls = [r["calls"] for r in in_process["scenarios"]]
    assert sum(calls) / len(calls) <= 260, f"calls per scenario: {calls}"


def test_the_real_mcp_servers_give_the_same_results_as_the_in_process_fallback(
    in_process, over_mcp
):
    assert over_mcp["hub"] == "mcp" and in_process["hub"] == "in-process"
    keep = ("id", "passed", "status", "reused", "calls")
    assert [{k: r[k] for k in keep} for r in over_mcp["scenarios"]] == [
        {k: r[k] for k in keep} for r in in_process["scenarios"]
    ]


@pytest.mark.parametrize(
    ("dataset", "waste_range", "mape_range"),
    [("raw", (45, 58), (8, 14)), ("heldout", (35, 48), (10, 17))],
)
def test_the_backtest_keeps_its_headline_result(tmp_path, dataset, waste_range, mape_range):
    """On 11 Oct: waste -51.3% on the main data, -41.1% on the held-out data (the one to quote)."""
    done = subprocess.run(
        [sys.executable, "-m", "zeroplate.eval.run_eval", "--llm", "deterministic", "--days", "30"]
        + ["--raw-dir", str(ROOT / "data" / dataset)],
        env=_env(tmp_path, dataset),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    backtest = json.loads(
        (tmp_path / "outputs" / "eval" / "report.json").read_text(encoding="utf-8")
    )["backtest"]
    assert waste_range[0] <= backtest["waste_plates_reduction_pct"] <= waste_range[1], backtest
    assert mape_range[0] <= backtest["forecast_mape_pct"] <= mape_range[1], backtest
    assert backtest["shortage_plates_reduction_pct"] > 30, backtest
    assert backtest["days"] == 30
