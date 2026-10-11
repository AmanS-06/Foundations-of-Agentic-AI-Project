"""Every setting and threshold in one place.

Rule: no magic numbers anywhere else in the code. If a number affects a decision, it lives here
with a comment saying where it comes from (a source, or "our assumption").
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # CSVs from the data generator (contract: PROJECT_PLAN 8.1)
KB_DIR = DATA_DIR / "kb"  # knowledge-base markdown files
MEMORY_DB = Path(os.environ.get("ZEROPLATE_MEMORY_DB", DATA_DIR / "memory.db"))  # git-ignored
CHROMA_DIR = DATA_DIR / "chroma"  # vector index (git-ignored)
RECORDINGS_DIR = DATA_DIR / "recordings"  # recorded model answers for replay
OUTPUTS_DIR = Path(os.environ.get("ZEROPLATE_OUTPUTS_DIR", ROOT / "outputs"))  # git-ignored

# Data directory can be overridden, e.g. tests point it at tests/fixtures.
# Until Anhad's generator has produced data/raw and data/kb, fall back to the sample fixtures
# (the UI shows a banner when this happens).
FIXTURES_DIR = ROOT / "tests" / "fixtures"
if "ZEROPLATE_RAW_DIR" in os.environ:
    RAW_DIR = Path(os.environ["ZEROPLATE_RAW_DIR"])
elif not (RAW_DIR / "calendar.csv").exists():
    RAW_DIR = FIXTURES_DIR / "raw"
if not any(KB_DIR.glob("*.md")):
    KB_DIR = FIXTURES_DIR / "kb"
USING_FIXTURE_DATA = RAW_DIR.parent == FIXTURES_DIR

# ---------------------------------------------------------------- language model
# "deterministic": fixed rules, no model (tests).  "ollama": live local model.
# "replay": answers recorded earlier from the model (the demo: fast and offline).
LLM_MODE = os.environ.get("ZEROPLATE_LLM_MODE", "replay")
OLLAMA_MODEL = os.environ.get("ZEROPLATE_OLLAMA_MODEL", "mistral")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
LLM_TIMEOUT_S = 120

# ---------------------------------------------------------------- MCP
USE_MCP = os.environ.get("ZEROPLATE_USE_MCP", "1") == "1"  # 0 = call the same functions in-process
# Anhad's Education server. Until it exists, the hub uses the test stand-in in
# tests/fixtures/education_stub.py.
EDUCATION_SERVER = "zeroplate.mcp_servers.edu_server"

# ---------------------------------------------------------------- orchestration
MAX_REVISIONS = 2  # Critic may send a plan back at most twice, then a human decides

# ---------------------------------------------------------------- forecast and stocking
CANDIDATE_BUFFERS = (0.00, 0.05, 0.10, 0.15)  # Tree-of-Thought branches: forecast + x%
WASTE_WEIGHT = 1.0  # cost weight of one leftover plate (our assumption)
SHORTAGE_WEIGHT = 3.0  # a missing plate counts 3x a leftover one (our assumption)
DEMAND_SAMPLES = 500  # simulated demands per candidate
RANDOM_SEED = 42
MIN_SPREAD_FRACTION = 0.05  # spread never below 5% of the mean (avoid zero uncertainty)

# ---------------------------------------------------------------- Critic rules (PROJECT_PLAN 6)
C1_MIN_RATIO = 0.5  # dish vs past days of the same event type: lower bound
C1_MAX_RATIO = 1.5  # upper bound
C2_MAX_BUFFER = 0.15  # planned <= forecast mean x (1 + this)
EXPIRY_WINDOW_HOURS = 24  # ingredients expiring within this are "use first"
FACT_CHECK_TOLERANCE = 0.01  # numbers in model text must match tool output within 1%

# C9, FSSAI "Food Industry Guide to implement GMP/GHP requirements: Catering" (Oct 2017)
HOT_HOLD_MIN_C = 65  # hot food must be held at or above 65 C
BELOW_HOT_HOLD_MAX_HOURS = 2  # below 65 C: eat within 2 h or reheat
REHEAT_TEMP_C = 75  # reheat to 75 C
MAX_REHEATS = 1  # gravies, meat, poultry, fish: reheated only once
MAX_AGE_HOURS = 24  # cooked food eaten within 24 h of preparation
CHILL_MAX_C = 5  # chilled high-risk food kept at 5 C or below
SERVICE_HOUR = 12  # reused food would be served at lunch on the plan date

# ---------------------------------------------------------------- guardrails
SUSPICIOUS_PATTERNS = (  # input guardrail for the manager's free-text note
    "ignore previous",
    "ignore the rules",
    "ignore all",
    "disregard",
    "you are now",
    "system prompt",
    "approve everything",
    "set budget",
    "override",
)
