"""The stocking calculation (the "newsvendor problem"): how many plates to cook.

We must choose a quantity q before demand D is known. Leftovers waste money; shortages leave
students without food. With a cost per leftover plate (waste weight) and per missing plate
(shortage weight), the expected utility of cooking q plates is

    utility(q) = - waste_weight    * cost_per_plate * E[max(q - D, 0)]
                 - shortage_weight * cost_per_plate * E[max(D - q, 0)]

Classic result: utility is highest when P(D <= q) = shortage / (shortage + waste), the
"critical fractile". With weights 3 and 1 that is 0.75: cook enough to cover 75% of the
demands that could happen, i.e. about 0.67 spreads above the mean for a normal distribution.

Tree-of-Thought: instead of jumping to that answer, the agent generates candidate plans
(forecast + 0%, 5%, 10%, 15%), estimates each one's expected waste and shortage by simulating
possible demands (Monte Carlo), and keeps the best branch. The same simulated demands are used
for every candidate ("common random numbers"), so the comparison is fair.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

from zeroplate import config
from zeroplate.schemas import Candidate, DishForecast, MenuItem


def critical_fractile(
    waste_weight: float = config.WASTE_WEIGHT, shortage_weight: float = config.SHORTAGE_WEIGHT
) -> float:
    """Target probability of NOT running out: shortage / (shortage + waste)."""
    return shortage_weight / (shortage_weight + waste_weight)


def optimal_quantity(forecast: DishForecast) -> float:
    """Closed-form newsvendor answer for normal demand: mean + z * spread."""
    z = NormalDist().inv_cdf(critical_fractile())
    return forecast.mean + z * forecast.spread


def simulate_demands(
    forecasts: list[DishForecast],
    samples: int = config.DEMAND_SAMPLES,
    seed: int = config.RANDOM_SEED,
) -> dict[str, np.ndarray]:
    """Draw `samples` possible demands per dish from Normal(mean, spread), never below 0."""
    rng = np.random.default_rng(seed)
    return {
        f.dish: np.clip(np.rint(rng.normal(f.mean, f.spread, samples)), 0, None) for f in forecasts
    }


def quantities_for(
    forecasts: list[DishForecast], menu: dict[str, MenuItem], buffer: float
) -> dict[str, int]:
    """Plates per dish for one candidate: forecast x (1 + buffer), at least the fairness minimum."""
    return {
        f.dish: max(math.ceil(f.mean * (1 + buffer)), menu[f.dish].min_portions) for f in forecasts
    }


def score_candidate(
    quantities: dict[str, int],
    demands: dict[str, np.ndarray],
    menu: dict[str, MenuItem],
    buffer: float,
) -> Candidate:
    """Expected waste cost, expected shortage cost, utility and food cost of one candidate."""
    waste = shortage = 0.0
    for dish, q in quantities.items():
        cost = menu[dish].cost_per_plate
        waste += cost * float(np.mean(np.maximum(q - demands[dish], 0)))
        shortage += cost * float(np.mean(np.maximum(demands[dish] - q, 0)))
    utility = -config.WASTE_WEIGHT * waste - config.SHORTAGE_WEIGHT * shortage
    food_cost = sum(q * menu[d].cost_per_plate for d, q in quantities.items())
    return Candidate(
        buffer=buffer,
        quantities=quantities,
        expected_waste_cost=round(waste, 2),
        expected_shortage_cost=round(shortage, 2),
        utility=round(utility, 2),
        food_cost=round(food_cost, 2),
    )


def generate_candidates(
    forecasts: list[DishForecast],
    menu: dict[str, MenuItem],
    buffers: tuple[float, ...] = config.CANDIDATE_BUFFERS,
) -> list[Candidate]:
    """Score every candidate buffer against the same simulated demands."""
    demands = simulate_demands(forecasts)
    return [score_candidate(quantities_for(forecasts, menu, b), demands, menu, b) for b in buffers]


def choose(candidates: list[Candidate], max_food_cost: float | None = None) -> Candidate | None:
    """Best-utility candidate, optionally only among those within budget. None if none fit."""
    feasible = [c for c in candidates if max_food_cost is None or c.food_cost <= max_food_cost]
    return max(feasible, key=lambda c: c.utility) if feasible else None
