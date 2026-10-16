"""ZeroPlate: Streamlit interface for the cross-domain agentic canteen planner.

Run:  .venv\\Scripts\\streamlit run app.py
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from zeroplate import config
from zeroplate.agents.base import AgentContext
from zeroplate.eval.run_eval import evaluate, to_markdown
from zeroplate.eval.scenarios import SCENARIOS
from zeroplate.graph import stream_plan
from zeroplate.llm.client import LLM
from zeroplate.mcp_client.allowlist import ALLOWLIST, WRITE_TOOLS
from zeroplate.mcp_client.hub import EDUCATION_STUB, MCPHub
from zeroplate.memory.long_term import Memory
from zeroplate.rag.retriever import KnowledgeBase

st.set_page_config(page_title="ZeroPlate", page_icon=":material/restaurant:", layout="wide")
st.markdown(
    f"<style>{(ROOT / 'ui' / 'styles.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

AGENT_ICONS = {
    "planner": ":material/account_tree:",
    "research": ":material/travel_explore:",
    "executor": ":material/calculate:",
    "critic": ":material/gavel:",
    "automation": ":material/local_shipping:",
    "human": ":material/person:",
}
AGENT_NAMES = {
    "planner": "Planner",
    "research": "Research",
    "executor": "Executor",
    "critic": "Critic",
    "automation": "Business Automation",
    "human": "Canteen manager",
}
PLOT_LAYOUT = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": "Geist, system-ui, sans-serif", "color": "#b6c2cf"},
    "title_font": {"size": 14, "color": "#e6edf3"},
    "xaxis": {"gridcolor": "rgba(148,163,184,0.08)", "zerolinecolor": "rgba(148,163,184,0.15)"},
    "yaxis": {"gridcolor": "rgba(148,163,184,0.08)", "zerolinecolor": "rgba(148,163,184,0.15)"},
    "legend": {"bgcolor": "rgba(0,0,0,0)"},
    "margin": {"l": 10, "r": 10, "t": 44, "b": 10},
    "height": 330,
}


# ---------------------------------------------------------------- shared resources
@st.cache_resource(show_spinner="Starting the three MCP servers...")
def get_hub() -> MCPHub:
    """One hub per app process. It owns a background thread with the MCP sessions."""
    return MCPHub().start()


@st.cache_resource
def get_kb() -> KnowledgeBase:
    return KnowledgeBase(config.KB_DIR)


@st.cache_resource
def get_memory() -> Memory:
    return Memory(config.MEMORY_DB)


def recordings_count() -> int:
    path = config.RECORDINGS_DIR / "answers.json"
    return len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0


hub, kb, memory = get_hub(), get_kb(), get_memory()


# ---------------------------------------------------------------- header
def badge(label: str, value: str, color: str) -> str:
    dot = f'<span class="zp-dot" style="background:{color}"></span>'
    return f'<span class="zp-badge">{dot}{label} <b>{escape(value)}</b></span>'


def header(llm_mode: str) -> None:
    st.markdown('<div class="zp-title">ZeroPlate</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="zp-sub">A cross-domain agentic AI planner for the college canteen: five agents, '
        "three departments, one goal: cook what will be eaten.</p>",
        unsafe_allow_html=True,
    )
    edu_stub = any(s.name == "education" and s.target == str(EDUCATION_STUB) for s in hub.servers)
    rec = recordings_count()
    llm_value = llm_mode if llm_mode != "replay" or rec else "replay (no recordings: rules)"
    badges = [
        badge(
            "Tools",
            f"{hub.mode.upper()} · {len(hub.tools())} servers",
            "#34d399" if hub.mode == "mcp" else "#fbbf24",
        ),
        badge("Model", llm_value, "#7dd3fc"),
        badge(
            "Data",
            "sample fixtures" if config.USING_FIXTURE_DATA else "data/raw",
            "#fbbf24" if config.USING_FIXTURE_DATA else "#34d399",
        ),
        badge(
            "Education server",
            "test stand-in" if edu_stub else "real",
            "#fbbf24" if edu_stub else "#34d399",
        ),
        badge("Knowledge base", f"{len(kb)} chunks", "#7dd3fc"),
        badge("Memory", f"{memory.count()} past runs", "#7dd3fc"),
    ]
    st.markdown(f'<div class="zp-badges">{"".join(badges)}</div>', unsafe_allow_html=True)
    if hub.start_error:
        st.warning(f"MCP could not start, using in-process tools instead: {hub.start_error}")


# ---------------------------------------------------------------- sidebar
def sidebar() -> dict:
    with st.sidebar:
        st.subheader("Plan a day")
        names = [f"{s.id}  {s.name}" for s in SCENARIOS] + ["Custom"]
        choice = st.selectbox("Scenario", names, index=0)
        sc = next((s for s in SCENARIOS if choice.startswith(s.id)), None)
        opts = dict(sc.options) if sc else {"plan_date": "2026-10-16"}
        if sc:
            st.caption(f"{sc.description}  \n**Expected:** {sc.expected}")
        key = sc.id if sc else "custom"
        plan_date = st.date_input(
            "Plan date", value=pd.Timestamp(opts["plan_date"]).date(), key=f"d{key}"
        )
        note = st.text_area(
            "Manager's note (optional)",
            value=opts.get("manager_note", ""),
            placeholder="e.g. It is raining, expect 20% more chai",
            key=f"n{key}",
        )
        budget_pct = st.slider(
            "Budget available (%)",
            50,
            120,
            int(opts.get("budget_factor", 1.0) * 100),
            5,
            key=f"b{key}",
        )
        with st.expander("Advanced"):
            inject = st.checkbox(
                "Simulate a wrong number in the summary",
                value=opts.get("inject_summary_error", False),
                key=f"i{key}",
            )
            modes = ["replay", "deterministic", "ollama"]
            llm_mode = st.selectbox(
                "Language model",
                modes,
                index=modes.index(config.LLM_MODE) if config.LLM_MODE in modes else 0,
            )
            st.caption(
                "replay = recorded model answers · deterministic = rule-based policy · ollama = live local model"
            )
        run = st.button(
            "Run the agents", type="primary", width="stretch", icon=":material/play_arrow:"
        )
    return {
        "run": run,
        "llm_mode": llm_mode,
        "options": {
            "plan_date": plan_date.isoformat(),
            "manager_note": note,
            "budget_factor": budget_pct / 100,
            "inject_summary_error": inject,
        },
    }


# ---------------------------------------------------------------- run
def run_agents(llm_mode: str, options: dict) -> dict:
    ctx = AgentContext(hub=hub, llm=LLM(llm_mode), kb=kb, memory=memory)
    final = None
    with st.status("The agents are working...", expanded=True) as status:
        for kind, value in stream_plan(ctx, **options):
            if kind == "node":
                st.write(f"{AGENT_NAMES[value]} finished")
            else:
                final = value
        label = (
            "Plan approved" if final["status"] == "approved" else "Escalated to the canteen manager"
        )
        status.update(
            label=label,
            state="complete" if final["status"] == "approved" else "error",
            expanded=False,
        )
    return final


# ---------------------------------------------------------------- result views
def card(label: str, value: str, detail: str = "", color: str = "#7d8a99") -> str:
    return (
        f'<div class="zp-card"><div class="k">{label}</div><div class="v">{value}</div>'
        f'<div class="d" style="color:{color}">{detail}</div></div>'
    )


def view_overview(s: dict) -> None:
    plan, attempts = s["plan"], s["attempts"]
    budget = attempts[-1]["budget"]
    if s["status"] == "approved":
        st.markdown(
            f'<div class="zp-verdict ok"><h4>Approved after {s["revision"]} revision(s)</h4>'
            f"<p>{escape(plan.summary)}</p></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="zp-verdict esc"><h4>Escalated to the canteen manager</h4>'
            f'<p>{escape(s["review"].feedback)}</p></div>',
            unsafe_allow_html=True,
        )
    chosen = next(c for c in plan.candidates if c.buffer == plan.chosen_buffer)
    over = plan.food_cost - budget
    cols = st.columns(5)
    cards = [
        card(
            "Food cost",
            f"Rs {plan.food_cost:,.0f}",
            f"Rs {abs(over):,.0f} {'over' if over > 0 else 'under'} budget",
            "#fb7185" if over > 0 else "#34d399",
        ),
        card("Budget", f"Rs {budget:,.0f}", "from the Finance server"),
        card("Chosen branch", f"+{plan.chosen_buffer:.0%}", f"utility {chosen.utility:,.0f}"),
        card(
            "Expected waste",
            f"Rs {chosen.expected_waste_cost:,.0f}",
            f"shortage Rs {chosen.expected_shortage_cost:,.0f}",
        ),
        (
            card("Purchase orders", f"Rs {plan.purchase_cost:,.0f}", f"{len(plan.purchases)} lines")
            if s["status"] == "approved"
            else card(
                "Proposed purchases", f"Rs {plan.purchase_cost:,.0f}", "not ordered: escalated"
            )
        ),
    ]
    for col, html in zip(cols, cards, strict=True):
        col.markdown(html, unsafe_allow_html=True)

    st.markdown("#### Production plan")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Dish": d.dish,
                    "Cook": d.cooked,
                    "Reuse": d.reused,
                    "Total": d.planned,
                    "Forecast": d.forecast_mean,
                    "Spread": d.forecast_spread,
                    "Low confidence": d.low_confidence,
                    "Why": d.reason,
                }
                for d in plan.dishes
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("#### Attempts")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Attempt": a["attempt"],
                    "Branch": f"+{a['buffer']:.0%}",
                    "Food cost": a["food_cost"],
                    "Budget": a["budget"],
                    "Leftovers reused": ", ".join(a["reused"]) or "-",
                    "Failed rules": ", ".join(a["failed"]) or "none",
                    "Verdict": a["verdict"],
                }
                for a in attempts
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if plan.notes:
        st.info("Notes: " + "; ".join(plan.notes))


def view_conversation(s: dict) -> None:
    st.caption("Agents never call each other; they post messages to the shared state.")
    for m in s["messages"]:
        with st.chat_message(m.sender, avatar=AGENT_ICONS[m.sender]):
            st.markdown(
                f"**{AGENT_NAMES[m.sender]}** <span class='muted'>to {AGENT_NAMES[m.receiver]} · {m.intent}</span>",
                unsafe_allow_html=True,
            )
            st.write(m.content)


def view_decision(s: dict) -> None:
    plan = s["plan"]
    st.markdown("#### Forecast per dish (ensemble consensus)")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Dish": d.dish,
                    "Mean": d.forecast_mean,
                    "Spread": d.forecast_spread,
                    "Why": d.reason,
                }
                for d in plan.dishes
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("#### Tree-of-Thought: candidate branches scored by expected utility")
    cands = plan.candidates
    x = [f"+{c.buffer:.0%}" for c in cands]
    left, right = st.columns(2)
    fig = go.Figure()
    fig.add_bar(
        x=x,
        y=[c.expected_waste_cost for c in cands],
        name="Expected waste (Rs)",
        marker_color="#fbbf24",
    )
    fig.add_bar(
        x=x,
        y=[c.expected_shortage_cost for c in cands],
        name="Expected shortage (Rs)",
        marker_color="#fb7185",
    )
    fig.add_scatter(
        x=x,
        y=[-c.utility for c in cands],
        name="Cost to minimise (-utility)",
        mode="lines+markers",
        line={"color": "#7dd3fc", "width": 3},
    )
    fig.update_layout(
        title="Waste vs shortage trade-off",
        barmode="group",
        **{**PLOT_LAYOUT, "legend": {"orientation": "h", "y": -0.2, "bgcolor": "rgba(0,0,0,0)"}},
    )
    left.plotly_chart(fig, width="stretch")
    budget = s["attempts"][-1]["budget"]
    fig2 = go.Figure()
    fig2.add_bar(
        x=x,
        y=[c.food_cost for c in cands],
        marker_color=["#34d399" if c.food_cost <= budget else "#3b4655" for c in cands],
        name="Food cost",
    )
    fig2.add_hline(
        y=budget, line_dash="dash", line_color="#fb7185", annotation_text=f"budget Rs {budget:,.0f}"
    )
    fig2.update_layout(title="Food cost of each branch (before reusing leftovers)", **PLOT_LAYOUT)
    right.plotly_chart(fig2, width="stretch")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Branch": f"+{c.buffer:.0%}",
                    "Expected waste (Rs)": c.expected_waste_cost,
                    "Expected shortage (Rs)": c.expected_shortage_cost,
                    "Utility": c.utility,
                    "Food cost (Rs)": c.food_cost,
                    "Chosen": c.buffer == plan.chosen_buffer,
                }
                for c in cands
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "utility = - 1 x waste cost - 3 x shortage cost (the weights are our assumption). "
        "The best quantity covers about 75% of possible demands."
    )


def view_critic(s: dict) -> None:
    checks_by_attempt: list[list] = []
    for step in s["trace"]:
        if step.agent == "critic" and step.thought.startswith("Rule "):
            if step.thought.startswith("Rule schema"):
                checks_by_attempt.append([])
            checks_by_attempt[-1].append(step)
    for i, (steps, attempt) in enumerate(
        zip(checks_by_attempt, s["attempts"], strict=True), start=1
    ):
        with st.expander(
            f"Attempt {i}: {attempt['verdict']}", expanded=i == len(checks_by_attempt)
        ):
            for step in steps:
                ok = step.observation.startswith("PASS")
                cls, word = ("pass", "PASS") if ok else ("fail", "FAIL")
                st.markdown(
                    f"<span class='{cls}'>{word}</span> &nbsp;**{escape(step.thought[5:])}** "
                    f"<span class='muted'>{escape(step.observation[6:])}</span>",
                    unsafe_allow_html=True,
                )
            st.markdown(f"**Feedback:** {attempt['feedback']}")


def view_trace(s: dict) -> None:
    st.caption("Every thought, tool call and observation, in order (ReAct: reason, act, observe).")
    agents = list(dict.fromkeys(t.agent for t in s["trace"]))
    pick = st.multiselect("Agents", agents, default=agents, format_func=lambda a: AGENT_NAMES[a])
    for step in s["trace"]:
        if step.agent not in pick:
            continue
        cls = "zp-step blocked" if step.blocked else "zp-step"
        meta = f"{AGENT_NAMES[step.agent]}"
        if step.tool:
            meta += f" · {step.tool}"
        if step.duration_ms:
            meta += f" · {step.duration_ms} ms"
        if step.blocked:
            meta += " · BLOCKED"
        st.markdown(
            f'<div class="{cls}"><div class="m">{escape(meta)}</div>'
            f'<div class="t">{escape(step.thought)}</div>'
            f'<div class="o">{escape(step.observation)}</div></div>',
            unsafe_allow_html=True,
        )


def view_documents(s: dict) -> None:
    if "actions" not in s:
        st.info("Nothing was ordered: the plan was escalated to the canteen manager.")
        return
    actions = s["actions"]
    prep = Path(actions.files[0])
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Kitchen prep sheet")
        # the file's title is a level-1 heading; drop it here, the section already has a title
        body = prep.read_text(encoding="utf-8").split("\n", 1)[1]
        st.markdown(body)
    with right:
        st.markdown("#### Purchase orders")
        for po_id in actions.purchase_order_ids:
            po = json.loads(
                (config.OUTPUTS_DIR / "purchase_orders" / f"{po_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            supplier = po["lines"][0]["supplier"]
            st.markdown(
                f"**{supplier}** <span class='muted'>{po_id} · Rs {po['total']:,.0f}</span>",
                unsafe_allow_html=True,
            )
            st.dataframe(
                pd.DataFrame(po["lines"])[["ingredient", "qty", "unit", "unit_price", "cost"]],
                hide_index=True,
                width="stretch",
            )
        st.markdown(
            f"Expected waste cost logged with accounts: **Rs {actions.waste_cost_logged:,.0f}**"
        )
    with st.expander("Full plan (JSON)"):
        st.json(json.loads(s["plan"].model_dump_json()), expanded=False)


def heldout_dir() -> Path | None:
    """The held-out dataset (different seed) if it exists, else the main data."""
    path = config.DATA_DIR / "heldout"
    return path if (path / "history.csv").exists() else None


def view_evaluation() -> None:
    st.caption(
        "Runs all six scenarios, then a 30-day backtest against the canteen's old habit (last "
        "week's sales + 15%) on the held-out dataset, generated with a different seed than the "
        "data the system was built on. Simulation on synthetic data."
    )
    if st.button("Run the benchmark", icon=":material/science:"):
        ctx = AgentContext(
            hub=hub,
            llm=LLM("deterministic"),
            kb=kb,
            memory=Memory(config.OUTPUTS_DIR / "eval" / "memory.db"),
        )
        with st.spinner("Running six scenarios and the backtest..."):
            st.session_state["report"] = evaluate(ctx, raw_dir=heldout_dir())
    report = st.session_state.get("report")
    if not report:
        return
    s, b = report["summary"], report["backtest"]
    cols = st.columns(4)
    cols[0].markdown(
        card("Task completion", f"{s['passed']}/{s['total']}", "scenarios as expected"),
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        card(
            "Waste reduction",
            f"{b['waste_plates_reduction_pct']}%",
            "plates vs old habit",
            "#34d399",
        ),
        unsafe_allow_html=True,
    )
    cols[2].markdown(
        card(
            "Shortage reduction",
            f"{b['shortage_plates_reduction_pct']}%",
            "plates vs old habit",
            "#34d399",
        ),
        unsafe_allow_html=True,
    )
    cols[3].markdown(
        card("Forecast error", f"{b['forecast_mape_pct']}%", "MAPE, held-out dataset"),
        unsafe_allow_html=True,
    )
    fig = go.Figure()
    for label, key, color in (
        ("Old habit", "old_habit", "#3b4655"),
        ("ZeroPlate", "agents", "#34d399"),
    ):
        fig.add_bar(
            x=["Wasted plates", "Short plates"],
            y=[b[key]["waste"], b[key]["short"]],
            name=label,
            marker_color=color,
        )
    fig.update_layout(
        title=f"Backtest on the held-out dataset: {b['days']} days", barmode="group", **PLOT_LAYOUT
    )
    st.plotly_chart(fig, width="stretch")
    # the report's first line is its own title; the view already has one
    st.markdown(to_markdown(report).split("\n", 1)[1])


def view_system() -> None:
    st.markdown("#### MCP servers and their tools (discovered at start-up)")
    rows = [
        {"Server": server, "Tool": tool, "Write tool": f"{server}.{tool}" in WRITE_TOOLS}
        for server, tools in hub.tools().items()
        for tool in tools
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown("#### Tool allowlist (least privilege)")
    tools = sorted({t for ts in ALLOWLIST.values() for t in ts} | WRITE_TOOLS)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Tool": t,
                    **{AGENT_NAMES[a]: ("yes" if t in ALLOWLIST[a] else "") for a in ALLOWLIST},
                }
                for t in tools
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    calls = hub.calls
    st.markdown(
        f"Tool calls this session: **{len(calls)}** · failed: **{sum(not c.ok and not c.blocked for c in calls)}** · "
        f"blocked by the allowlist: **{sum(c.blocked for c in calls)}**"
    )
    st.markdown("#### Architecture")
    st.graphviz_chart(
        """digraph {
        rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="#141c26" color="#2a3644" fontcolor="#e6edf3" fontname="Helvetica"]; edge [color="#34d399" fontcolor="#7d8a99" fontname="Helvetica" fontsize=10];
        ui [label="Streamlit UI"]; planner [label="Planner"]; research [label="Research"]; executor [label="Executor"]; critic [label="Critic" shape=diamond]; automation [label="Business\\nAutomation"]; human [label="Human decision"];
        node [shape=cylinder fillcolor="#2a2214" color="#7a5a2a"]; edu [label="Education\\nMCP server"]; sup [label="Supply\\nMCP server"]; fin [label="Finance\\nMCP server"];
        node [fillcolor="#14261c" color="#2e6b4a"]; kb [label="Knowledge base\\n(Chroma + BM25)"]; mem [label="Memory\\n(SQLite)"];
        ui -> planner -> research -> executor -> critic; critic -> automation [label="approve"]; critic -> executor [label="revise"]; critic -> human [label="escalate"];
        research -> edu [style=dashed]; research -> sup [style=dashed]; executor -> sup [style=dashed]; executor -> fin [style=dashed]; critic -> fin [style=dashed];
        automation -> sup [label="write" color="#fbbf24"]; automation -> fin [label="write" color="#fbbf24"];
        research -> kb [style=dashed]; research -> mem [style=dashed]; automation -> mem;
        }"""
    )


# ---------------------------------------------------------------- page
inputs = sidebar()
header(inputs["llm_mode"])
if config.USING_FIXTURE_DATA:
    st.caption("Using the sample fixture data until the project dataset (data/raw) is generated.")

if inputs["run"]:
    st.session_state["state"] = run_agents(inputs["llm_mode"], inputs["options"])

state = st.session_state.get("state")
VIEWS = {
    "Overview": view_overview,
    "Conversation": view_conversation,
    "Decision": view_decision,
    "Critic": view_critic,
    "Trace": view_trace,
    "Documents": view_documents,
}
# a segmented control keeps the selected view across reruns (tabs reset to the first one)
view = st.segmented_control(
    "View",
    [*VIEWS, "Evaluation", "System"],
    default="Overview",
    key="view",
    label_visibility="collapsed",
)
st.write("")
if view == "Evaluation":
    view_evaluation()
elif view == "System":
    view_system()
elif state is None:
    st.markdown(
        "Pick a scenario in the sidebar and press **Run the agents**. "
        "Scenario S1 (college fest) shows the whole loop: the Critic rejects the plan twice "
        "(unsafe leftovers, then over budget) before approving it."
    )
else:
    VIEWS[view or "Overview"](state)
