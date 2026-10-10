"""Shared test setup: every test reads the sample data in tests/fixtures, never real data."""

import os
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

# Must be set before zeroplate.config is imported anywhere.
os.environ["ZEROPLATE_RAW_DIR"] = str(FIXTURES / "raw")
os.environ["ZEROPLATE_LLM_MODE"] = "deterministic"
