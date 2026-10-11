"""Input guardrail for the manager's free-text note (prompt-injection defence, Unit 5).

The note is DATA about tomorrow ("expect 20% more chai, it's raining"), never instructions to
the agents. This scanner is a simple reflex agent: condition -> action rules that flag text
trying to give orders ("ignore the rules", "approve") or demanding absurd quantities. A flagged
note is not passed to the model at all, and the Critic's rules apply unchanged either way.
"""

from __future__ import annotations

import re

from zeroplate import config

MAX_PLAIN_NUMBER = 300  # a note asking for hundreds of plates of something is not a forecast hint
MAX_PERCENT = 100


def scan(note: str) -> list[str]:
    """Reasons the note looks like an injection attempt; empty list if it looks safe."""
    text = note.lower()
    reasons = [f"contains '{p}'" for p in config.SUSPICIOUS_PATTERNS if p in text]
    for pct in re.findall(r"(\d+(?:\.\d+)?)\s*%", text):
        if float(pct) > MAX_PERCENT:
            reasons.append(f"asks for a {pct}% change")
    for num in re.findall(r"(?<![\d.%])(\d{3,})(?![\d%])", text):
        if int(num) > MAX_PLAIN_NUMBER:
            reasons.append(f"mentions an absolute quantity ({num})")
    if re.search(r"\b(approve|bypass|skip)\b.*\b(check|rule|critic|budget|review)", text):
        reasons.append("tries to bypass the review")
    return reasons
