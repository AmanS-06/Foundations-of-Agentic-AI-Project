"""Draw a simplified, large-text version of the architecture diagram for slides, as SVG and PNG.

The full diagram (build_architecture.py) is meant to be read on paper or zoomed on screen. On a slide its
text would be far too small, so this version keeps the same parts (agents, MCP client, offices as tool servers,
rule documents, memory, note check, AI model) with fewer words, bigger type and plainer names.

Run:  .venv\\Scripts\\python docs\\diagrams\\build_architecture_slide.py
"""

from __future__ import annotations

import subprocess
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1900, 860

AGENT = ("#E3F1E9", "#1E7A55")
SERVER = ("#E4EEF6", "#2F6F8F")
LOCAL = ("#FDF1DC", "#B7791F")
GUARD = ("#FBE4E1", "#C0392B")
MODEL = ("#EEE8F6", "#6B4FA3")
UI = ("#F0F2F1", "#5B6B66")
INK = "#1B2B26"
MUTED = "#5B6B66"

parts: list[str] = []


def box(x, y, w, h, colour, title, lines, dashed=False):
    """A rounded box with a bold title and up to three body lines."""
    fill, stroke = colour
    dash = ' stroke-dasharray="10 6"' if dashed else ""
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="3"{dash}/>'
    )
    parts.append(
        f'<text x="{x + 20}" y="{y + 42}" class="t" fill="{stroke}">{escape(title)}</text>'
    )
    for i, line in enumerate(lines):
        parts.append(f'<text x="{x + 20}" y="{y + 82 + i * 32}" class="b">{escape(line)}</text>')


def arrow(d, colour=MUTED, width=3, both=False):
    start = ' marker-start="url(#head)"' if both else ""
    parts.append(
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
        f'marker-end="url(#head)"{start}/>'
    )


# ---- row 1: entry, guardrail, language model
box(40, 20, 360, 135, UI, "The app", ["Manager picks a date,", "a goal and a note"])
box(470, 20, 360, 135, GUARD, "Note check", ["Flags notes that", "try to give orders"])
box(
    1040, 20, 820, 135, MODEL, "AI language model (replayed in the demo)",
    ["Reads the note and helps write explanations.", "Every number comes from a tool, never the AI."],
)  # fmt: skip
arrow("M400,87 L470,87")
arrow("M650,155 L650,190 L205,190 L205,228")

# ---- row 2: the five agents
AX = [40 + i * 370 for i in range(5)]
AY, AW, AH = 230, 330, 160
agents = [
    ("1  Planner", ["Splits the goal", "into tasks"]),
    ("2  Research", ["Gathers facts and", "rules, with sources"]),
    ("3  Executor", ["Forecasts, tries four", "plans, picks the best"]),
    ("4  Critic", ["Checks six rules and", "can send a plan back"]),
    ("5  Automation", ["Places orders and", "writes the prep sheet"]),
]
for x, (title, lines) in zip(AX, agents):
    box(x, AY, AW, AH, AGENT, title, lines)
for i in range(4):
    arrow(f"M{AX[i] + AW},{AY + 70} L{AX[i + 1]},{AY + 70}")

# the revise loop and the escalation
arrow(
    f"M{AX[3] + 165},{AY} L{AX[3] + 165},{AY - 30} L{AX[2] + 165},{AY - 30} L{AX[2] + 165},{AY}",
    GUARD[1],
)
parts.append(
    f'<text x="{(AX[2] + AX[3]) / 2 + 165}" y="{AY - 40}" text-anchor="middle" font-size="24" '
    f'font-style="italic" fill="{GUARD[1]}">revise, at most twice</text>'
)
parts.append(
    f'<rect x="{AX[3] + 90}" y="{AY + AH + 10}" width="240" height="38" rx="19" fill="{GUARD[0]}" '
    f'stroke="{GUARD[1]}" stroke-width="2.5"/>'
)
parts.append(
    f'<text x="{AX[3] + 210}" y="{AY + AH + 36}" text-anchor="middle" font-size="22" '
    f'fill="{GUARD[1]}">escalate to a person</text>'
)

# ---- row 3: the MCP hub
HY, HH = 470, 64
parts.append(
    f'<rect x="40" y="{HY}" width="1820" height="{HH}" rx="16" fill="#FFFFFF" '
    f'stroke="{SERVER[1]}" stroke-width="3.5"/>'
)
parts.append(f'<text x="64" y="{HY + 41}" class="t" fill="{SERVER[1]}">MCP client</text>')
parts.append(
    f'<text x="290" y="{HY + 41}" class="b">Inside the host. Each agent has a list of tools it may use, '
    f"checked on every call. Only Business Automation can write.</text>"
)
for x in AX:
    arrow(f"M{x + 60},{AY + AH} L{x + 60},{HY}", SERVER[1], 2.5, both=True)

# ---- row 4: department servers and local tools
SY, SH = 600, 170
box(40, SY, 330, SH, SERVER, "Education office", ["Calendar and how", "many students come"])
box(
    410,
    SY,
    330,
    SH,
    SERVER,
    "Supply office",
    ["Stock, recipes,", "suppliers, leftovers,", "orders"],
)
box(
    780,
    SY,
    330,
    SH,
    SERVER,
    "Finance office",
    ["Budget, plan cost,", "waste-cost log"],
)
box(
    1150,
    SY,
    330,
    SH,
    LOCAL,
    "Rule documents",
    ["FSSAI food-safety rules", "and canteen policies,", "with sources"],
    dashed=True,
)
box(1520, SY, 330, SH, LOCAL, "Memory", ["Past runs and what", "they taught"], dashed=True)
for cx in (205, 575, 945, 1315, 1685):
    arrow(f"M{cx},{HY + HH} L{cx},{SY}", SERVER[1], 2.5, both=True)

# ---- legend
legend = [(AGENT, "agent"), (SERVER, "office (tool server)"), (LOCAL, "documents, memory"), (GUARD, "safety check"),
          (MODEL, "AI model"), (UI, "app")]  # fmt: skip
x = 40
for colour, text in legend:
    parts.append(
        f'<rect x="{x}" y="808" width="26" height="26" rx="6" fill="{colour[0]}" '
        f'stroke="{colour[1]}" stroke-width="2.5"/>'
    )
    parts.append(f'<text x="{x + 36}" y="829" font-size="22" fill="{MUTED}">{escape(text)}</text>')
    x += 36 + 13 * len(text) + 50

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>
<style>
text {{ font-family: 'Segoe UI', Arial, sans-serif; }}
.t {{ font-size: 32px; font-weight: 700; }}
.b {{ font-size: 25px; fill: {INK}; }}
</style>
</defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(parts)}
</svg>
"""


def main() -> None:
    """Write the SVG and render the PNG (needs Chrome or Edge; skipped if neither is found)."""
    svg_path = HERE / "architecture_slide.svg"
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
    png_path = HERE / "architecture_slide.png"
    subprocess.run(
        [exe, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
         f"--screenshot={png_path}", svg_path.as_uri()],
        check=True, capture_output=True, timeout=90,
    )  # fmt: skip
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
