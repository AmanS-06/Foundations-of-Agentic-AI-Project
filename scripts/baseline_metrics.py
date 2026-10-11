"""Numbers for the old way of cooking: how much food it wastes and how much demand it leaves unserved.

This is the "before" half of the project's results. Any plan made by ZeroPlate is judged against these
numbers, on the same days. The numbers come only from history.csv, calendar.csv and menu.csv, so they
need nothing from the agents.

What is measured, for a set of days:
  plates cooked, sold and demanded; plates wasted (cooked and not sold); plates unmet (wanted and not
  served); the share of cooked plates wasted; the share of demand unmet; the cost of the wasted plates
  in rupees (cost price); and the value of the lost sales in rupees (selling price of the unmet plates).

Lost sales are an estimate: a student who finds a dish sold out may buy something else.

Run:  .venv\\Scripts\\python scripts\\baseline_metrics.py data/raw data/heldout --last-days 60
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Running as a script puts this folder on sys.path, not src/, so add it (as the MCP server does).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeroplate.domain.data import load_table

DAY_TYPE_ORDER = ("normal", "exam", "weekend", "holiday", "fest")


@dataclass
class Metrics:
    """Totals for a set of days, and the shares worked out from them."""

    days: int = 0
    cooked: int = 0
    sold: int = 0
    demanded: int = 0
    wasted: int = 0
    unmet: int = 0
    waste_cost: float = 0.0  # rupees, at cost price
    lost_sales: float = 0.0  # rupees, at selling price

    @property
    def waste_share(self) -> float:
        """Share of the plates cooked that were never sold."""
        return self.wasted / self.cooked if self.cooked else 0.0

    @property
    def unmet_share(self) -> float:
        """Share of the plates wanted that were not served."""
        return self.unmet / self.demanded if self.demanded else 0.0

    @property
    def waste_cost_per_day(self) -> float:
        return self.waste_cost / self.days if self.days else 0.0

    @property
    def lost_sales_per_day(self) -> float:
        return self.lost_sales / self.days if self.days else 0.0


def baseline_metrics(raw_dir: Path, last_days: int | None = None) -> dict[str, Metrics]:
    """Metrics for the old habit on one dataset: key "all", plus one key per type of day.

    `last_days` keeps only the most recent N days of history, which is the window a plan from
    ZeroPlate would be judged on.
    """
    history = load_table("history", raw_dir)
    event = {r.date: r.event.value for r in load_table("calendar", raw_dir)}
    price = {m.dish: m.price for m in load_table("menu", raw_dir)}

    days = sorted({r.date for r in history})
    if last_days is not None:
        if last_days < 1:
            raise ValueError(f"last_days must be at least 1, got {last_days}")
        days = days[-last_days:]
    keep = set(days)

    result: dict[str, Metrics] = defaultdict(Metrics)
    seen: dict[str, set] = defaultdict(set)
    for r in history:
        if r.date not in keep:
            continue
        unmet = r.demand - r.sold
        for key in ("all", event[r.date]):
            m = result[key]
            m.cooked += r.prepared
            m.sold += r.sold
            m.demanded += r.demand
            m.wasted += r.wasted_plates
            m.unmet += unmet
            m.waste_cost += r.waste_cost
            m.lost_sales += unmet * price[r.dish]
            seen[key].add(r.date)
    for key, m in result.items():
        m.days = len(seen[key])
    return dict(result)


def render(name: str, metrics: dict[str, Metrics]) -> str:
    """A plain-text table for one dataset."""
    rows = [("All days", metrics["all"])]
    rows += [(k.capitalize(), metrics[k]) for k in DAY_TYPE_ORDER if k in metrics]
    head = (
        f"{'':10s}{'days':>6s}{'cooked':>9s}{'wasted':>9s}{'waste %':>9s}"
        f"{'unmet':>8s}{'unmet %':>9s}{'waste Rs':>12s}{'lost sales Rs':>15s}"
    )
    lines = [f"{name}", head, "-" * len(head)]
    for label, m in rows:
        lines.append(
            f"{label:10s}{m.days:6d}{m.cooked:9,d}{m.wasted:9,d}{m.waste_share:9.1%}"
            f"{m.unmet:8,d}{m.unmet_share:9.1%}{m.waste_cost:12,.0f}{m.lost_sales:15,.0f}"
        )
    return "\n".join(lines)


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description="Baseline numbers for the old way of cooking.")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("datasets", nargs="*", type=Path, default=[root / "data" / "raw"])
    parser.add_argument("--last-days", type=int, default=None, help="only the most recent N days")
    args = parser.parse_args()
    for folder in args.datasets:
        window = f", last {args.last_days} days" if args.last_days else ""
        print(render(f"{folder}{window}", baseline_metrics(folder, args.last_days)))
        print()


if __name__ == "__main__":
    main()
