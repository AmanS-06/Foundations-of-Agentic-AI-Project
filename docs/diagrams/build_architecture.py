"""Draw the ZeroPlate architecture diagram as an SVG, and render it to PNG with Chrome.

Edit the text in this file and run it again; the picture is regenerated.

Run:  .venv\\Scripts\\python docs\\diagrams\\build_architecture.py
"""

from __future__ import annotations

import subprocess
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1920, 1110

# colours: (fill, stroke) for each kind of part
BLUE = ("#E8F0FE", "#1A56DB")  # agents
GREEN = ("#E6F4EA", "#1E8E3E")  # MCP servers (the three departments)
AMBER = ("#FEF3E2", "#B45309")  # local tools: knowledge base, memory
RED = ("#FDE8E8", "#C81E1E")  # guardrails and decisions
PURPLE = ("#F3E8FF", "#7E22CE")  # language model
GREY = ("#F1F5F9", "#475569")  # interface, outputs
INK = "#0F172A"
MUTED = "#475569"

parts: list[str] = []


def box(x, y, w, h, colour, title, lines, tag=None, dashed=False):
    """A rounded box with a bold title, body lines and an optional italic tag at the bottom."""
    fill, stroke = colour
    dash = ' stroke-dasharray="8 5"' if dashed else ""
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2.5"{dash}/>'
    )
    parts.append(
        f'<text x="{x + 16}" y="{y + 30}" class="t" fill="{stroke}">{escape(title)}</text>'
    )
    for i, line in enumerate(lines):
        parts.append(f'<text x="{x + 16}" y="{y + 58 + i * 21}" class="b">{escape(line)}</text>')
    if tag:
        base = y + h - 12 - (len(tag) - 1) * 18
        for i, line in enumerate(tag):
            parts.append(f'<text x="{x + 16}" y="{base + i * 18}" class="g">{escape(line)}</text>')


def arrow(d, colour=MUTED, dashed=False, width=2.5, both=False):
    """A path with an arrowhead at its end (and at its start too when `both` is true)."""
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    start = ' marker-start="url(#head)"' if both else ""
    parts.append(
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}"{dash} '
        f'marker-end="url(#head)"{start}/>'
    )


def label(x, y, text, anchor="middle", colour=MUTED, size=14):
    parts.append(
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
        f'fill="{colour}" font-style="italic">{escape(text)}</text>'
    )


# ---------------------------------------------------------------- heading
parts.append('<text x="135" y="48" class="h">ZeroPlate: how one planning run works</text>')
parts.append(
    '<text x="135" y="76" class="g" font-size="16">Agents (blue) reach the three departments '
    "through one MCP hub (green). Draft v1, 11 Oct 2026. All data is synthetic.</text>"
)

# ---------------------------------------------------------------- row A: entry and language model
box(135, 100, 270, 105, GREY, "Streamlit dashboard",
    ["The canteen manager picks a", "date and a goal, and may add", "a free-text note."])  # fmt: skip
box(480, 100, 270, 105, RED, "Input guardrail",
    ["Scans the note for hidden", "instructions such as", "'ignore the rules'."])  # fmt: skip
box(1170, 100, 615, 105, PURPLE, "Language model (used by the agents)",
    ["Replayed recorded answers (default), live Ollama, or fixed rules for tests.",
     "It reads the note, explains plans and writes the Critic's feedback.",
     "Numbers are decided by code and tools, never by the model."])  # fmt: skip
arrow("M405,152 L480,152")
arrow("M615,205 L615,238 L270,238 L270,270")

# ---------------------------------------------------------------- row B: the five agents
AX = [135, 480, 825, 1170, 1515]
AY, AW, AH = 270, 270, 190
agents = [
    ("1  Planner", ["Breaks the goal into", "subtasks and routes the", "work. Passes problems to", "a human."],
     ["Tools: none", "(reads the run state)"]),
    ("2  Research", ["Gathers evidence: calendar,", "attendance, stock, rules,", "past runs. Reads the note."],
     ["Reads: Education, Supply,", "knowledge base, memory"]),
    ("3  Executor", ["Forecasts demand, tries four", "cooking amounts, picks the", "best, works out ingredients", "and cost."],
     ["Reads: Supply", "Costs the plan: Finance"]),
    ("4  Critic", ["Checks the plan against six", "rules, then approves, sends", "it back, or escalates."],
     ["Reads: Finance, Supply,", "knowledge base"]),
    ("5  Business Automation", ["Acts on the approved plan:", "prep sheet, purchase orders,", "waste-cost log."],
     ["Writes: Supply, Finance,", "memory"]),
]  # fmt: skip
for x, (title, lines, tag) in zip(AX, agents):
    box(x, AY, AW, AH, BLUE, title, lines, tag)
mid = AY + 62
for i, text in enumerate(["tasks", "facts", "plan", "approved"]):
    x0 = AX[i] + AW
    arrow(f"M{x0},{mid} L{AX[i + 1]},{mid}")
    label(x0 + 37, mid - 8, text, size=12)

# the revise loop (Critic back to Executor) and the escalation
arrow(
    f"M{AX[3] + 135},{AY} L{AX[3] + 135},{AY - 24} L{AX[2] + 135},{AY - 24} L{AX[2] + 135},{AY}",
    RED[1],
)
label(
    (AX[2] + AX[3] + 270) / 2,
    AY - 32,
    "revise, at most twice, with the Critic's feedback",
    colour=RED[1],
    size=14,
)
PILL_X, PILL_W = AX[3] + 70, AW - 70  # leaves room on the left for the hub arrow
parts.append(
    f'<rect x="{PILL_X}" y="{AY + AH + 10}" width="{PILL_W}" height="28" rx="14" '
    f'fill="{RED[0]}" stroke="{RED[1]}" stroke-width="2"/>'
)
parts.append(
    f'<text x="{PILL_X + PILL_W // 2}" y="{AY + AH + 29}" text-anchor="middle" font-size="14" '
    f'fill="{RED[1]}">escalate: manager decides</text>'
)

# ---------------------------------------------------------------- row C: the MCP hub
HY, HH = AY + AH + 62, 56
parts.append(
    f'<rect x="135" y="{HY}" width="1650" height="{HH}" rx="12" fill="#FFFFFF" '
    f'stroke="{GREEN[1]}" stroke-width="3"/>'
)
parts.append(
    f'<text x="155" y="{HY + 24}" class="t" fill="{GREEN[1]}" font-size="17">MCP hub (the client)</text>'
)
parts.append(
    f'<text x="355" y="{HY + 24}" class="b">Every tool call goes through here. Each agent has an allowlist, '
    f"so a call it is not allowed to make is refused and logged.</text>"
)
parts.append(
    f'<text x="355" y="{HY + 44}" class="b">Only the Business Automation agent may use tools that change '
    f"something (purchase orders, waste-cost log).</text>"
)
for x in AX:
    arrow(f"M{x + 35},{AY + AH} L{x + 35},{HY}", GREEN[1], width=2, both=True)

# ---------------------------------------------------------------- row D: department servers and local tools
SY, SH = HY + HH + 50, 150
box(135, SY, 270, SH, GREEN, "Education server",
    ["The academic office.", "Calendar: exam, holiday, fest", "and weather. Expected", "attendance. Similar past days."])  # fmt: skip
box(480, SY, 270, SH, GREEN, "Supply server",
    ["The canteen store.", "Stock and expiry dates, recipes,", "supplier prices, leftovers.", "Writes purchase orders."])  # fmt: skip
box(825, SY, 270, SH, GREEN, "Finance server",
    ["The accounts office.", "Daily budget and the cost of a", "plan. Writes the waste-cost", "log."])  # fmt: skip
box(1170, SY, 270, SH, AMBER, "Knowledge base",
    ["Local tool, same allowlist.", "FSSAI food-safety rules, SOP,", "recipe yields, budget policy.", "Search results carry citations."], dashed=True)  # fmt: skip
box(1515, SY, 270, SH, AMBER, "Long-term memory",
    ["Local tool, same allowlist.", "SQLite: past runs and what", "really happened, so later", "plans can learn from them."], dashed=True)  # fmt: skip
for x in AX:
    arrow(f"M{x + 135},{HY + HH} L{x + 135},{SY}", GREEN[1], width=2, both=True)

# ---------------------------------------------------------------- row E: decisions and outputs
PY, PH, PW = SY + SH + 30, 200, 530
PX = [135, 695, 1255]


def panel(x, colour, title, lines, bold_last=False):
    fill, stroke = colour
    parts.append(
        f'<rect x="{x}" y="{PY}" width="{PW}" height="{PH}" rx="12" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2.5"/>'
    )
    parts.append(
        f'<text x="{x + 16}" y="{PY + 30}" class="t" fill="{stroke}">{escape(title)}</text>'
    )
    for i, line in enumerate(lines):
        weight = ' font-weight="600"' if bold_last and i == len(lines) - 1 else ""
        parts.append(
            f'<text x="{x + 16}" y="{PY + 58 + i * 23}" class="b"{weight}>{escape(line)}</text>'
        )


panel(PX[0], BLUE, "How the Executor decides (utility, Tree-of-Thought)", [
    "1. Three forecasting methods give a mean and a spread per dish.",
    "2. Four candidate plans: cook the forecast plus 0, 5, 10 or 15%.",
    "3. Each candidate is tested against 500 simulated demands.",
    "4. Score = minus the waste cost, minus 3 times the shortage cost.",
    "5. The best-scoring candidate goes to the Critic."])  # fmt: skip
panel(PX[1], RED, "What the Critic checks (six rules)", [
    "C1  Quantities are sane next to similar past days.",
    "C2  The extra buffer stays within the allowed limit.",
    "C4  The total cost fits the daily budget.",
    "C5  Vegetarian and Jain dishes keep their minimum portions.",
    "C6  Numbers in written text match the tool results.",
    "C9  Leftover reuse follows the FSSAI food-safety rules."], )  # fmt: skip
panel(PX[2], GREY, "What comes out", [
    "A kitchen prep sheet: plates of each dish.",
    "Purchase orders for what the store is missing.",
    "The cost of leftovers that cannot be reused.",
    "Leftover reuse suggestions that passed the rule.",
    "The dashboard shows the whole trace: each thought,",
    "tool call and rule result, plus run metrics."])  # fmt: skip

# ---------------------------------------------------------------- legend
LY = PY + PH + 38
legend = [(BLUE, "agent"), (GREEN, "department system (MCP server)"), (AMBER, "local tool"),
          (RED, "guardrail or decision"), (PURPLE, "language model"), (GREY, "interface and output")]  # fmt: skip
x = 135
for colour, text in legend:
    parts.append(
        f'<rect x="{x}" y="{LY - 14}" width="18" height="18" rx="4" fill="{colour[0]}" '
        f'stroke="{colour[1]}" stroke-width="2"/>'
    )
    parts.append(f'<text x="{x + 26}" y="{LY}" class="g" font-size="14">{escape(text)}</text>')
    x += 26 + 8 * len(text) + 28

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>
<style>
text {{ font-family: 'Segoe UI', Arial, sans-serif; }}
.h {{ font-size: 30px; font-weight: 700; fill: {INK}; }}
.t {{ font-size: 19px; font-weight: 700; }}
.b {{ font-size: 15px; fill: {INK}; }}
.g {{ font-size: 14px; fill: {MUTED}; font-style: italic; }}
</style>
</defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(parts)}
</svg>
"""


def main() -> None:
    """Write the SVG and render the PNG (needs Chrome or Edge; skipped if neither is found)."""
    svg_path = HERE / "architecture.svg"
    svg_path.write_text(SVG, encoding="utf-8")
    print(f"wrote {svg_path}")
    browsers = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    exe = next((b for b in browsers if Path(b).exists()), None)
    if exe is None:
        print("no Chrome or Edge found: open the SVG in a browser and save it as PNG")
        return
    png_path = HERE / "architecture.png"
    subprocess.run(
        [exe, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
         f"--screenshot={png_path}", svg_path.as_uri()],
        check=True, capture_output=True, timeout=90,
    )  # fmt: skip
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
