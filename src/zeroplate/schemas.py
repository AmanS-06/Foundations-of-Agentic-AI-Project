"""Data shapes for everything that crosses a boundary in ZeroPlate.

Three kinds of models live here:
1. Records returned by MCP tools (one per CSV in PROJECT_PLAN 8.1). These are the contract with
   the data generator and the Education server: field names must match the CSV columns.
2. Outputs of the agents (plan, research report, production plan, review, actions).
3. Messages and trace steps, which is how agents talk to each other and how the UI shows a run.

Every model is validated by Pydantic: wrong types or missing fields raise an error immediately,
which is the "output validation" guardrail from Unit 5.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt


class Strict(BaseModel):
    """Base model: reject unknown fields so typos in tool output or model JSON are caught."""

    model_config = ConfigDict(extra="forbid")


# ================================================================== enums


class Event(str, Enum):
    """Kind of day, from the academic calendar."""

    NORMAL = "normal"
    EXAM = "exam"
    HOLIDAY = "holiday"
    FEST = "fest"
    WEEKEND = "weekend"


class Weather(str, Enum):
    SUNNY = "sunny"
    RAINY = "rainy"
    HOT = "hot"


class Diet(str, Enum):
    VEG = "veg"
    NONVEG = "nonveg"
    JAIN = "jain"


class Holding(str, Enum):
    """How a cooked leftover batch is being kept."""

    HOT = "hot"
    CHILLED = "chilled"
    AMBIENT = "ambient"


# ================================================================== 1. tool records (CSV rows)


class CalendarEvent(Strict):
    """calendar.csv row. Returned by education.get_calendar_event(date)."""

    date: date
    weekday: str
    event: Event
    weather: Weather


class Attendance(Strict):
    """attendance.csv row. Returned by education.get_expected_attendance(date)."""

    date: date
    enrolled: NonNegativeInt
    expected_present: NonNegativeInt


class MenuItem(Strict):
    """menu.csv row."""

    dish: str
    category: str
    diet: Diet
    price: NonNegativeFloat
    cost_per_plate: NonNegativeFloat
    shelf_life_hrs: NonNegativeFloat
    min_portions: NonNegativeInt  # fairness minimum (our assumption), used by rule C5


class RecipeLine(Strict):
    """recipes.csv row: how much of one ingredient one plate needs."""

    dish: str
    ingredient: str
    qty_per_plate: NonNegativeFloat
    unit: str


class InventoryItem(Strict):
    """inventory.csv row."""

    ingredient: str
    stock_qty: NonNegativeFloat
    unit: str
    expiry_date: date
    reorder_point: NonNegativeFloat


class SupplierOffer(Strict):
    """suppliers.csv row: one supplier's price for one ingredient."""

    supplier: str
    ingredient: str
    lead_time_days: NonNegativeInt
    price_per_unit: NonNegativeFloat


class DailyBudget(Strict):
    """budget.csv row. Returned by finance.get_daily_budget(date)."""

    date: date
    daily_budget: NonNegativeFloat


class HistoryRow(Strict):
    """history.csv row: one dish on one past day.

    `demand` is the synthetic true demand. Real canteens only see `sold`, which cannot exceed
    `prepared`; the generator records demand so the forecaster can be evaluated honestly.
    """

    date: date
    dish: str
    prepared: NonNegativeInt
    sold: NonNegativeInt
    demand: NonNegativeInt
    wasted_plates: NonNegativeInt
    waste_cost: NonNegativeFloat


class LeftoverBatch(Strict):
    """batches.csv row: a cooked batch with plates left over. Used by rule C9."""

    batch_id: str
    dish: str
    cooked_at: datetime
    plates_left: NonNegativeInt
    holding: Holding
    temp_c: float
    reheated_count: NonNegativeInt


# ================================================================== 2. agent outputs


AgentName = Literal["planner", "research", "executor", "critic", "automation", "human"]


class Task(Strict):
    """One subtask produced by the Planner's goal decomposition."""

    id: int
    agent: AgentName
    description: str


class TaskPlan(Strict):
    """Planner output."""

    goal: str
    plan_date: date
    tasks: list[Task] = Field(min_length=1)


class NoteEvent(Strict):
    """One structured fact the model extracted from the manager's free-text note."""

    kind: Literal["demand_change", "dish_unavailable", "extra_event", "other"]
    dish: str | None = None
    factor: float | None = Field(default=None, gt=0, le=3)  # e.g. 1.2 = +20% demand
    text: str


class NoteParse(Strict):
    """Result of reading the manager's note, plus the input guardrail's verdict."""

    events: list[NoteEvent] = []
    suspicious: bool = False
    reasons: list[str] = []


class Citation(Strict):
    """A knowledge-base chunk used as evidence."""

    source: str  # file name, e.g. food_safety_fssai.md
    section: str  # heading of the chunk
    text: str
    score: float


class Factor(Strict):
    """One piece of evidence the Research agent found, with where it came from."""

    name: str
    value: str | float | int
    source: str  # tool name ("education.get_calendar_event") or "kb" or "memory"


class ResearchReport(Strict):
    """Research output: everything the Executor needs, with sources."""

    plan_date: date
    event: Event
    weather: Weather
    expected_present: NonNegativeInt
    factors: list[Factor]
    citations: list[Citation] = []
    note: NoteParse = NoteParse()
    summary: str


class DishForecast(Strict):
    """Forecast for one dish: ensemble mean, spread and each method's estimate."""

    dish: str
    mean: NonNegativeFloat
    spread: NonNegativeFloat  # standard deviation of past forecast errors
    methods: dict[str, float]  # method name -> estimate (the ensemble members)


class Candidate(Strict):
    """One Tree-of-Thought branch: cook forecast + buffer, scored by expected utility."""

    buffer: float  # 0.05 = forecast + 5%
    quantities: dict[str, NonNegativeInt]  # dish -> plates
    expected_waste_cost: NonNegativeFloat
    expected_shortage_cost: NonNegativeFloat
    utility: float  # -(waste weight x waste) - (shortage weight x shortage)


class DishPlan(Strict):
    """Final plan for one dish, with its explanation for the UI's "Why?" panel."""

    dish: str
    planned: NonNegativeInt
    forecast_mean: NonNegativeFloat
    forecast_spread: NonNegativeFloat
    reason: str


class IngredientNeed(Strict):
    ingredient: str
    unit: str
    required: NonNegativeFloat
    in_stock: NonNegativeFloat
    to_order: NonNegativeFloat
    expires_soon: bool = False


class PurchaseLine(Strict):
    supplier: str
    ingredient: str
    qty: NonNegativeFloat
    unit: str
    unit_price: NonNegativeFloat
    cost: NonNegativeFloat


class ProductionPlan(Strict):
    """Executor output."""

    plan_date: date
    dishes: list[DishPlan] = Field(min_length=1)
    ingredients: list[IngredientNeed]
    purchases: list[PurchaseLine]
    food_cost: NonNegativeFloat  # cost of all plates cooked
    purchase_cost: NonNegativeFloat
    total_cost: NonNegativeFloat
    candidates: list[Candidate]
    chosen_buffer: float
    summary: str  # model-written; numbers in it are fact-checked (rule C6)


class RuleCheck(Strict):
    """Result of one Critic rule."""

    rule_id: Literal["C1", "C2", "C4", "C5", "C6", "C9", "schema"]
    name: str
    passed: bool
    detail: str


class Review(Strict):
    """Critic output. The verdict is restricted to three words: without the restriction a
    local model invented verdicts like "highly_unfavorable" in Anhad's prototype tests."""

    verdict: Literal["approve", "revise", "escalate"]
    checks: list[RuleCheck]
    feedback: str  # model-written; steers the Executor's revision
    attempt: NonNegativeInt


class ActionReport(Strict):
    """Business Automation output."""

    purchase_order_ids: list[str]
    prep_sheet: list[DishPlan]
    waste_cost_logged: NonNegativeFloat
    files: list[str]  # paths of documents written


# ================================================================== 3. messages and trace


class AgentMessage(Strict):
    """Message passing between agents (through the shared graph state)."""

    sender: AgentName
    receiver: AgentName
    intent: Literal["request", "result", "feedback", "escalate"]
    content: str
    at: datetime = Field(default_factory=datetime.now)


class TraceStep(Strict):
    """One step of a run, for the trace view and the evaluation metrics."""

    agent: AgentName
    thought: str
    tool: str | None = None
    args: dict[str, Any] = {}
    observation: str = ""
    duration_ms: NonNegativeInt = 0
    blocked: bool = False  # True if the allowlist refused the tool call
