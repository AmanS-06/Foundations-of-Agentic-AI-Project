"""Draw how ZeroPlate works inside, as four detail diagrams and one overview, as SVG and PNG.

The five pictures use the real names from the code, with a plain-words description under each part:

  01_langgraph      State, nodes and edges of the LangGraph       (state.py, graph.py)
  02_orchestration  What each agent calls: tools, local code, LLM  (agents/, guardrails/)
  03_mcp            Host, MCP client and the three MCP servers     (mcp_client/, mcp_servers/)
  04_rag            Indexing and search of the knowledge base      (rag/retriever.py)
  05_overview       All four on one page

Run:  .venv\\Scripts\\python docs\\diagrams\\build_architecture_system.py
The files are written to docs/diagrams/system/. PNGs need Chrome or Edge; without one only the SVGs
are written (open them in a browser and save as PNG).
"""

from __future__ import annotations

import subprocess
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "system"

AGENT = ("#E3F1E9", "#1E7A55")
SERVER = ("#E4EEF6", "#2F6F8F")
LOCAL = ("#FDF1DC", "#B7791F")
GUARD = ("#FBE4E1", "#C0392B")
MODEL = ("#EEE8F6", "#6B4FA3")
UI = ("#F0F2F1", "#5B6B66")
HOST = ("#F8FAF9", "#8FA39A")
INK = "#1B2B26"
MUTED = "#5B6B66"
RED = GUARD[1]

MARKERS = {"grey": MUTED, "red": RED, "blue": SERVER[1], "gold": LOCAL[1], "green": AGENT[1]}


class Canvas:
    """A tiny SVG canvas with the few shapes these diagrams need."""

    def __init__(self, width: int, height: int) -> None:
        self.w, self.h = width, height
        self.parts: list[str] = []

    # -- shapes
    def rect(self, x, y, w, h, colour, dashed=False, sw=3, rx=14, fill=None):
        fill_c, stroke_c = colour
        dash = ' stroke-dasharray="10 6"' if dashed else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill or fill_c}" '
            f'stroke="{stroke_c}" stroke-width="{sw}"{dash}/>'
        )

    def text(self, x, y, s, cls="b", fill=None, anchor="start"):
        colour = f' fill="{fill}"' if fill else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{colour}>{escape(s)}</text>'
        )

    def box(self, x, y, w, h, colour, title, lines=(), dashed=False, title_cls="t", sw=3):
        """A rounded box with a bold title and up to a few body lines."""
        self.rect(x, y, w, h, colour, dashed=dashed, sw=sw)
        self.text(x + 16, y + 34, title, title_cls, fill=colour[1])
        for i, line in enumerate(lines):
            self.text(x + 16, y + 64 + i * 25, line, "s")

    def line(self, d, colour="grey", width=3):
        """A plain connector without arrowheads."""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{MARKERS[colour]}" stroke-width="{width}"/>'
        )

    def arrow(self, d, colour="grey", width=3, dashed=False, both=False):
        dash = ' stroke-dasharray="9 6"' if dashed else ""
        start = f' marker-start="url(#h-{colour})"' if both else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{MARKERS[colour]}" stroke-width="{width}"{dash} '
            f'marker-end="url(#h-{colour})"{start}/>'
        )

    # -- output
    def svg(self) -> str:
        markers = "".join(
            f'<marker id="h-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{colour}"/></marker>'
            for name, colour in MARKERS.items()
        )
        body = "\n".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">\n<defs>{markers}\n<style>\n'
            "text { font-family: 'Segoe UI', Arial, sans-serif; fill: " + INK + "; }\n"
            ".t { font-size: 26px; font-weight: 700; }\n"
            ".h { font-size: 30px; font-weight: 700; }\n"
            ".b { font-size: 23px; }\n"
            ".u { font-size: 23px; font-weight: 700; }\n"
            ".s { font-size: 20px; }\n"
            ".i { font-size: 20px; font-style: italic; }\n"
            "</style></defs>\n"
            f'<rect width="{self.w}" height="{self.h}" fill="#FFFFFF"/>\n{body}\n</svg>\n'
        )


def legend(c: Canvas, y: int, items: list[tuple[tuple[str, str], str]], x: int = 20) -> None:
    for colour, label in items:
        c.parts.append(
            f'<rect x="{x}" y="{y}" width="26" height="26" rx="6" fill="{colour[0]}" '
            f'stroke="{colour[1]}" stroke-width="2.5"/>'
        )
        c.text(x + 36, y + 21, label, "s", fill=MUTED)
        x += 36 + int(10.6 * len(label)) + 40


# ---------------------------------------------------------------------------- 01 LangGraph
def langgraph() -> Canvas:
    c = Canvas(1600, 800)
    # the state
    c.rect(20, 15, 1560, 255, UI, fill="#F7F9F8")
    c.text(
        40,
        52,
        "State: one shared PlanState (state.py). Every agent reads it and writes back what it changes.",
        "t",
    )
    cols = [
        (40, "Inputs", ["goal, plan_date, run_id", "manager_note, budget_factor"], SERVER),
        (
            440,
            "Outputs of the agents",
            ["task_plan, research, plan,", "review, decision, actions"],
            AGENT,
        ),
        (
            840,
            "Control",
            ["revision: times sent back", "status: running / approved /", "escalated (+ 2 caches)"],
            GUARD,
        ),
        (
            1240,
            "Append-only lists",
            [
                "messages, trace, timings,",
                "attempts: merged with",
                "operator.add, so nothing",
                "is overwritten",
            ],
            LOCAL,
        ),
    ]
    for x, title, lines, colour in cols:
        c.box(x, 80, 330, 175, colour, title, lines)
    # nodes and edges
    c.text(40, 316, "Nodes and edges (graph.py)", "t")
    c.text(40, 344, "Each node reads the state and returns its changes.", "s", fill=MUTED)
    y, h = 415, 110
    xs = {"planner": 130, "research": 360, "executor": 590, "critic": 820}
    c.rect(20, 442, 80, 56, UI, rx=28)
    c.text(60, 478, "START", "s", anchor="middle")
    nodes = [
        ("planner", "planner", ["splits the goal", "into tasks"]),
        ("research", "research", ["gathers facts,", "rules, past runs"]),
        ("executor", "executor", ["forecasts, picks", "a plan"]),
        ("critic", "critic", ["checks the plan,", "chooses the route"]),
    ]
    for key, title, lines in nodes:
        c.box(xs[key], y, 200, h, AGENT, title, lines)
    c.arrow("M100,470 L130,470")
    for a, b in (("planner", "research"), ("research", "executor"), ("executor", "critic")):
        c.arrow(f"M{xs[a] + 200},470 L{xs[b]},470")
    # branches from the critic (conditional edges, route_after_critic)
    c.box(1130, 295, 220, 110, AGENT, "automation", ["orders, prep sheet,", "saves a lesson"])
    c.box(1130, 535, 220, 110, GUARD, "human", ["the manager decides;", "nothing is ordered"])
    c.rect(1450, 442, 110, 56, UI, rx=28)
    c.text(1505, 478, "END", "s", anchor="middle")
    c.arrow("M1020,455 L1130,370", colour="green", dashed=True)
    c.text(1062, 452, "approve", "i", fill=AGENT[1])
    c.arrow("M1020,485 L1130,575", colour="red", dashed=True)
    c.text(945, 550, "escalate", "i", fill=RED)
    c.arrow("M920,415 L920,372 L690,372 L690,415", colour="red", dashed=True)
    c.text(805, 360, "revise (at most 2 times)", "i", fill=RED, anchor="middle")
    c.arrow("M1350,370 L1450,458", colour="green")
    c.arrow("M1350,575 L1450,485", colour="red")
    c.text(780, 612, "route_after_critic reads review.verdict", "i", fill=MUTED)
    # legend and the label for sequential agents
    c.arrow("M40,640 L110,640")
    c.text(125, 647, "fixed edge", "s", fill=MUTED)
    c.arrow("M40,676 L110,676", colour="green", dashed=True)
    c.text(125, 683, "conditional edge (chosen by route_after_critic)", "s", fill=MUTED)
    c.rect(20, 715, 1560, 65, AGENT, fill="#EEF7F1")
    c.text(
        800,
        757,
        "Sequential multi-agent pipeline with a revision loop (Critic to Executor). Nothing runs in parallel.",
        "t",
        anchor="middle",
    )
    return c


# ---------------------------------------------------------------------------- 02 orchestration
def orchestration() -> Canvas:
    c = Canvas(1600, 800)
    c.text(
        20,
        38,
        "Orchestration: LangGraph calls each agent in turn, and each agent calls tools, local code or the AI model",
        "t",
    )
    # column headers
    c.text(470, 92, "MCP tools: allowlist checks every call", "s", fill=RED)
    c.text(850, 92, "Local code and tools (not MCP)", "s", fill=LOCAL[1])
    c.text(1230, 92, "AI language model (LLM)", "s", fill=MODEL[1])
    # allowlist guardrail around the MCP column
    c.rect(462, 100, 376, 618, GUARD, dashed=True, sw=2.5, rx=12, fill="none")
    # LangGraph spine
    c.rect(15, 108, 80, 604, AGENT, fill="#EEF7F1")
    c.parts.append(
        '<text transform="translate(66,410) rotate(-90)" class="t" text-anchor="middle" '
        f'fill="{AGENT[1]}">LangGraph runs the agents in this order</text>'
    )
    agents = [
        ("1 Planner", ["breaks the goal into tasks", "uses no tools"], ""),
        (
            "2 Research",
            ["gathers the facts", "(perceives the world)"],
            "Guardrail: note scanner first",
        ),
        (
            "3 Executor",
            ["builds and costs the plan", "ReAct: think, call, observe"],
            "Guardrail: AI cannot loosen limits",
        ),
        (
            "4 Critic",
            ["checks the plan; can send", "it back to the Executor"],
            "Guardrail: fact check (C6)",
        ),
        (
            "5 Automation",
            ["acts on the approved plan", "the only agent that writes"],
            "Guardrail: write tools only here",
        ),
    ]
    pills = [
        # (MCP pill, local pill, LLM pill), each pill is (title, lines) or None
        (
            ("No tools", ["plans only"]),
            None,
            ("LLM", ["breaks the goal", "into tasks"]),
        ),
        (
            ("MCP tools", ["calendar, attendance,", "menu, leftover batches"]),
            ("RAG + memory", ["food-safety and budget rules;", "past runs of the same day type"]),
            ("LLM", ["reads the note (3 votes),", "writes the summary"]),
        ),
        (
            ("MCP tools", ["history, recipes, stock,", "suppliers, budget, cost_plan"]),
            ("Forecast and choice", ["3 forecasts, newsvendor,", "Tree-of-Thought +0/5/10/15%"]),
            ("LLM", ["writes the summary; reads", "the Critic's feedback"]),
        ),
        (
            ("MCP tools", ["budget, menu, history,", "leftovers (checks itself)"]),
            ("6 rules + schema check", ["C1 C2 C4 C5 C6 C9;", "the rules decide the verdict"]),
            ("LLM", ["writes the feedback", "in plain words"]),
        ),
        (
            ("MCP write tools", ["purchase orders (Supply),", "waste log (Finance)"]),
            ("Files + memory", ["prep sheet and plan files;", "saves a lesson"]),
            None,
        ),
    ]
    colours = [SERVER, LOCAL, MODEL]
    xs = [470, 850, 1230]
    widths = [360, 360, 350]
    for i, ((title, lines, guard), row) in enumerate(zip(agents, pills)):
        y = 108 + i * 122
        c.rect(115, y, 330, 112, AGENT)
        c.text(131, y + 32, title, "t", fill=AGENT[1])
        c.text(131, y + 58, lines[0], "s")
        c.text(131, y + 80, lines[1], "s")
        if guard:
            c.text(131, y + 103, guard, "i", fill=RED)
        for col, x, w, pill in zip(colours, xs, widths, row):
            if pill is None:
                continue
            colour = GUARD if pill[0] == "No tools" else col
            if pill[0] == "No tools":
                colour = UI
            c.box(x + 6, y, w - 12, 112, colour, pill[0], pill[1], title_cls="t")
        # arrows from the agent to its pills
        c.arrow(f"M445,{y + 56} L{xs[0] + 6},{y + 56}", colour="grey", width=2.5)
    legend(
        c,
        748,
        [
            (SERVER, "MCP tools (the offices' data)"),
            (LOCAL, "local code, not MCP"),
            (MODEL, "AI model"),
            (GUARD, "guardrail"),
            (AGENT, "agent"),
        ],
    )
    return c


# ---------------------------------------------------------------------------- 03 MCP
def mcp() -> Canvas:
    c = Canvas(1600, 800)
    c.rect(20, 15, 700, 585, HOST, sw=3.5, rx=18)
    c.text(40, 50, "HOST: the ZeroPlate app (one process)", "t", fill=MUTED)
    c.box(
        40,
        75,
        300,
        100,
        AGENT,
        "Agents + LangGraph",
        ["the 5 agents; they ask for", "a tool by name"],
    )
    c.box(
        40, 190, 300, 100, MODEL, "LLM", ["local Mistral; its answers", "are replayed in the demo"]
    )
    c.box(40, 305, 300, 100, UI, "Streamlit UI", ["the manager picks a date,", "a goal and a note"])
    c.arrow("M340,125 L365,125", width=2.5)
    # the MCP client
    c.rect(365, 70, 335, 510, SERVER, fill="#F0F6FA")
    c.text(381, 104, "MCP client: MCPHub", "t", fill=SERVER[1])
    c.text(381, 132, "(hub.py)", "s", fill=MUTED)
    c.box(
        381,
        150,
        303,
        75,
        GUARD,
        "Allowlist check",
        ["may this agent use this tool?"],
        title_cls="t",
    )
    sess_y = [250, 345, 440]
    for y, name in zip(sess_y, ("education", "supply", "finance")):
        c.rect(381, y, 303, 62, SERVER, fill="#FFFFFF")
        c.text(397, y + 27, "ClientSession", "t", fill=SERVER[1])
        c.text(397, y + 52, "for the " + name + " server", "s")
    c.text(381, 530, "If MCP cannot start, MCPHub", "i", fill=MUTED)
    c.text(381, 555, "calls the same functions in-process.", "i", fill=MUTED)
    c.arrow("M340,355 L365,355", width=2.5)  # UI and agents feed the client
    # the three servers
    servers = [
        (
            15,
            160,
            "Education server",
            "edu_server.py, a FastMCP subprocess",
            [
                "tools: get_calendar_event, get_expected_attendance",
                "resources: academic_calendar, calendar_summary",
            ],
        ),
        (
            195,
            215,
            "Supply server",
            "supply_server.py, a FastMCP subprocess",
            [
                "tools: get_menu, get_history, get_recipes,",
                "get_inventory, get_suppliers, get_leftover_batches",
                "write tool: create_purchase_order",
                "resource: supplier_catalog",
            ],
        ),
        (
            430,
            170,
            "Finance server",
            "finance_server.py, a FastMCP subprocess",
            [
                "tools: get_daily_budget, cost_plan",
                "write tool: log_waste_cost",
                "resource: budget_policy",
            ],
        ),
    ]
    centres = []
    for y, h, name, sub, lines in servers:
        c.rect(1000, y, 580, h, SERVER)
        c.text(1016, y + 34, name, "t", fill=SERVER[1])
        c.text(1016, y + 60, sub, "s", fill=MUTED)
        for i, line in enumerate(lines):
            c.text(1016, y + 92 + i * 25, line, "s")
        centres.append(y + h // 2)
    # stdio links: elbows from each ClientSession to its server
    for sy, cy, vx in zip(sess_y, centres, (830, 860, 890)):
        mid = sy + 31
        c.arrow(f"M684,{mid} H{vx} V{cy} H1000", colour="blue", width=3.5, both=True)
    for cy in centres:
        c.text(915, cy - 10, "stdio", "i", fill=SERVER[1])
    # one sample call
    c.text(20, 640, "One tool call, step by step", "t")
    steps = [
        ["1 Executor asks", "for supply.", "get_menu"],
        ["2 Allowlist", "check: is this", "agent allowed?"],
        ["3 MCPHub picks", "the supply", "ClientSession"],
        ["4 stdio: a JSON", "message goes to", "the server process"],
        ["5 FastMCP server", "runs get_menu", "and replies"],
        ["6 The result", "goes back to", "the agent"],
        ["7 Saved in the", "trace: tool,", "time, who"],
    ]
    for i, lines in enumerate(steps):
        x = 20 + i * 227
        colour = GUARD if i == 1 else SERVER if i in (2, 3, 4) else AGENT
        c.rect(x, 660, 205, 112, colour)
        c.text(x + 14, 692, lines[0], "s", fill=colour[1])
        c.text(x + 14, 720, lines[1], "s")
        c.text(x + 14, 746, lines[2], "s")
        if i < 6:
            c.arrow(f"M{x + 205},716 L{x + 227},716", width=2.5)
    return c


# ---------------------------------------------------------------------------- 04 RAG
def rag() -> Canvas:
    c = Canvas(1600, 800)
    c.text(20, 38, "Indexing: done once, when the app starts", "t")
    row = [
        (
            20,
            "data/kb/*.md",
            ["4 files: FSSAI food", "safety, canteen SOP,", "recipe yields, budget", "policy"],
            UI,
        ),
        (
            365,
            "Split by heading",
            ["39 chunks. Each section", "is one self-contained", "rule, so it can be cited"],
            AGENT,
        ),
        (
            710,
            "TF-IDF vectors",
            ["one vector per chunk,", "built locally, so it", "works offline"],
            LOCAL,
        ),
        (
            1055,
            "ChromaDB",
            ["stores the vectors in an", "HNSW index (cosine", "similarity)"],
            LOCAL,
        ),
    ]
    for x, title, lines, colour in row:
        c.box(x, 60, 300, 155, colour, title, lines)
    for x in (320, 665, 1010):
        c.arrow(f"M{x},137 L{x + 45},137")
    c.box(
        710,
        245,
        300,
        100,
        LOCAL,
        "BM25 index",
        ["keyword index over the", "same chunks (rank_bm25)"],
    )
    c.arrow("M515,215 V295 H710")
    c.text(1055, 282, "Both indexes live in memory", "i", fill=MUTED)
    c.text(1055, 308, "and are rebuilt at start-up.", "i", fill=MUTED)

    c.text(20, 410, "Query: every time an agent asks a question", "t")
    c.box(
        20,
        440,
        260,
        125,
        UI,
        "A question",
        ["from the Research", "agent, e.g. 'reheating", "leftovers'"],
    )
    c.box(
        305,
        430,
        320,
        100,
        LOCAL,
        "Vector search",
        ["ChromaDB finds the chunks", "closest to the question"],
    )
    c.box(
        305,
        545,
        320,
        100,
        LOCAL,
        "BM25 keyword search",
        ["ranks chunks by the", "words they share"],
    )
    c.box(
        650,
        480,
        290,
        125,
        AGENT,
        "Fuse with RRF",
        ["Reciprocal Rank Fusion:", "score = sum of", "1 / (60 + rank)"],
    )
    c.box(
        965,
        480,
        310,
        125,
        AGENT,
        "Top chunks",
        ["Research asks for 2 per", "question. Each has a", "citation: file > section"],
    )
    c.box(
        1300, 430, 280, 100, AGENT, "Research agent", ["reads the budget and", "food-safety rules"]
    )
    c.box(
        1300,
        545,
        280,
        100,
        GUARD,
        "Critic (rule C9)",
        ["quotes the food-safety", "source in its verdict"],
    )
    c.arrow("M280,502 L305,480")
    c.arrow("M280,520 L305,595")
    c.arrow("M625,480 L650,520")
    c.arrow("M625,595 L650,570")
    c.arrow("M940,542 L965,542")
    c.arrow("M1275,520 L1300,480")
    c.arrow("M1275,560 L1300,595")
    c.rect(20, 695, 1560, 85, LOCAL, fill="#FEF7E8")
    c.text(
        800,
        746,
        "The RAG knowledge base and the memory are local tools inside the host. They are not MCP servers.",
        "t",
        anchor="middle",
    )
    return c


# ---------------------------------------------------------------------------- 05 overview
def overview() -> Canvas:
    c = Canvas(1600, 860)
    c.rect(15, 15, 1120, 830, HOST, sw=3.5, rx=18)
    c.text(35, 50, "HOST: the ZeroPlate app (Streamlit + LangGraph, one process)", "t", fill=MUTED)
    c.box(
        35,
        70,
        420,
        105,
        UI,
        "Streamlit UI",
        ["the manager picks a date, a goal", "and a note, and sees every step"],
    )
    c.box(
        640,
        70,
        480,
        105,
        MODEL,
        "AI language model (LLM)",
        ["local Mistral; its answers are replayed", "in the demo; numbers come from tools"],
    )
    c.line("M200,175 V210")
    c.line("M880,175 V210")
    # LangGraph band
    c.rect(35, 210, 1085, 270, AGENT, fill="#F1F8F4")
    c.text(55, 247, "LangGraph (graph.py) + PlanState", "t", fill=AGENT[1])
    agents = [
        ("1 Planner", ["splits the goal", "into tasks"]),
        ("2 Research", ["gathers facts,", "rules, past runs"]),
        ("3 Executor", ["forecasts and", "picks a plan"]),
        ("4 Critic", ["checks the plan,", "6 rules + schema"]),
        ("5 Automation", ["places orders,", "writes prep sheet"]),
    ]
    xs = [55 + i * 215 for i in range(5)]
    for x, (title, lines) in zip(xs, agents):
        c.box(x, 275, 190, 115, AGENT, title, lines, title_cls="u")
    for i in range(4):
        c.arrow(f"M{xs[i] + 190},332 L{xs[i + 1]},332", width=2.5)
    c.arrow(f"M{xs[3] + 95},275 V245 H{xs[2] + 95} V275", colour="red", dashed=True)
    c.text(
        (xs[2] + xs[3]) // 2 + 95, 236, "revise, at most 2 times", "i", fill=RED, anchor="middle"
    )
    c.text(55, 428, "Escalate: a person decides, nothing is ordered.", "i", fill=RED)
    c.text(
        55,
        460,
        "Sequential pipeline with a revision loop. Nothing runs in parallel.",
        "s",
        fill=AGENT[1],
    )
    # toolbox row
    for x in (190, 510, 900):
        c.line(f"M{x},480 V515")
    c.box(
        35,
        515,
        305,
        175,
        LOCAL,
        "RAG knowledge base",
        ["local tool, not MCP", "39 chunks, ChromaDB + BM25,", "fused with RRF"],
    )
    c.box(
        360,
        515,
        305,
        175,
        LOCAL,
        "Memory (SQLite)",
        [
            "local tool, not MCP",
            "past runs and lessons;",
            "Research reads it,",
            "Automation writes it",
        ],
    )
    c.box(
        685,
        515,
        435,
        175,
        SERVER,
        "MCP client: MCPHub",
        [
            "checks the allowlist on every call,",
            "keeps one ClientSession per",
            "server, talks to them over stdio",
        ],
    )
    # guardrails
    guards = [
        (35, "Note scanner", ["checks the manager's note", "before anyone uses it"]),
        (
            395,
            "Allowlist (in MCPHub)",
            ["checks every tool call:", "may this agent use this tool?"],
        ),
        (755, "Fact check (rule C6)", ["every number in the summary", "must match a tool output"]),
    ]
    for x, title, lines in guards:
        c.box(x, 715, 345, 115, GUARD, title, lines)
    # servers
    servers = [
        (60, "Education server", ["FastMCP subprocess", "calendar and", "expected attendance"]),
        (
            320,
            "Supply server",
            ["FastMCP subprocess", "stock, recipes, suppliers,", "leftovers, purchase orders"],
        ),
        (580, "Finance server", ["FastMCP subprocess", "budget, plan costing,", "waste-cost log"]),
    ]
    for y, name, lines in servers:
        c.box(1260, y, 320, 180, SERVER, name, lines)
    for y0, vx, ty in ((560, 1170, 150), (605, 1190, 410), (650, 1210, 670)):
        c.arrow(f"M1120,{y0} H{vx} V{ty} H1260", colour="blue", width=3.5, both=True)
    return c


DIAGRAMS = [
    ("01_langgraph", langgraph),
    ("02_orchestration", orchestration),
    ("03_mcp", mcp),
    ("04_rag", rag),
    ("05_overview", overview),
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    browsers = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    exe = next((b for b in browsers if Path(b).exists()), None)
    if exe is None:
        print("no Chrome or Edge found: open the SVGs in a browser and save them as PNG")
    for name, build in DIAGRAMS:
        canvas = build()
        svg_path = OUT / f"{name}.svg"
        svg_path.write_text(canvas.svg(), encoding="utf-8")
        print(f"wrote {svg_path}")
        if exe:
            png_path = OUT / f"{name}.png"
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
                 f"--window-size={canvas.w},{canvas.h}", f"--screenshot={png_path}", svg_path.as_uri()],
                check=True, capture_output=True, timeout=90,
            )  # fmt: skip
            print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
