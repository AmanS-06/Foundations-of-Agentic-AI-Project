"""Numeric fact-check (hallucination mitigation, Unit 5): rule C6.

A language model writes the plan's summary in plain English. Models sometimes state numbers
that are not true. Rule: every number in the summary must match a number that a tool actually
produced (within 1%). Numbers come from tools; the model only puts them into words.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from zeroplate import config

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """Every number written in the text (commas removed: 30,989 -> 30989)."""
    return [float(m.replace(",", "")) for m in NUMBER.findall(text)]


def collect_numbers(obj: Any) -> set[float]:
    """Every number anywhere inside a nested dict/list/str (e.g. a dumped plan), plus each
    number also as a percentage (0.05 -> 5) because text writes buffers as percent."""
    found: set[float] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            v = abs(float(x))  # text writes "-3,211" as a sign plus a number
            found.update({v, round(v * 100, 6)})
        elif isinstance(x, str):
            found.update(numbers_in(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple, set)):
            for v in x:
                walk(v)

    walk(obj)
    return found


def unsupported_numbers(text: str, allowed: Iterable[float]) -> list[float]:
    """Numbers in `text` that match no allowed number within the tolerance."""
    allowed = list(allowed)
    tol = config.FACT_CHECK_TOLERANCE
    bad = []
    for n in numbers_in(text):
        if not any(abs(n - a) <= max(tol * abs(a), 0.5) for a in allowed):
            bad.append(n)
    return bad
