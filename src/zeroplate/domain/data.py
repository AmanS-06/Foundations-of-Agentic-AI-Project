"""Read the contract CSVs (PROJECT_PLAN 8.1) and validate every row against its schema.

This is the only place that touches the raw files. Everything above it (MCP servers, agents)
gets typed, validated objects, never raw strings.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

from zeroplate import config
from zeroplate.schemas import (
    Attendance,
    CalendarEvent,
    DailyBudget,
    HistoryRow,
    InventoryItem,
    LeftoverBatch,
    MenuItem,
    RecipeLine,
    SupplierOffer,
)

# table name (= CSV file name without .csv) -> schema of one row
TABLES: dict[str, type[BaseModel]] = {
    "calendar": CalendarEvent,
    "attendance": Attendance,
    "menu": MenuItem,
    "recipes": RecipeLine,
    "inventory": InventoryItem,
    "suppliers": SupplierOffer,
    "budget": DailyBudget,
    "history": HistoryRow,
    "batches": LeftoverBatch,
}


class DataError(ValueError):
    """A CSV is missing, has the wrong columns, or has a row that fails validation."""


def load_table(name: str, raw_dir: Path | None = None) -> list[BaseModel]:
    """Return every row of `<raw_dir>/<name>.csv` as a validated schema object."""
    if name not in TABLES:
        raise DataError(f"unknown table {name!r}; expected one of {sorted(TABLES)}")
    path = Path(raw_dir or config.RAW_DIR) / f"{name}.csv"
    if not path.exists():
        raise DataError(f"missing data file: {path}")
    # the file's modification time is part of the cache key, so edited files are re-read
    return list(_load_cached(name, str(path), path.stat().st_mtime))


@lru_cache(maxsize=64)
def _load_cached(name: str, path: str, _mtime: float) -> tuple[BaseModel, ...]:
    schema = TABLES[name]
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        expected = list(schema.model_fields)
        if reader.fieldnames != expected:
            raise DataError(f"{path}: columns {reader.fieldnames}, contract says {expected}")
        rows = []
        for line_no, raw in enumerate(reader, start=2):  # line 1 is the header
            try:
                rows.append(schema.model_validate(raw))
            except ValidationError as exc:
                raise DataError(f"{path} line {line_no}: {exc.errors()[0]['msg']}") from exc
    return tuple(rows)


def check_all(raw_dir: Path | None = None) -> dict[str, int]:
    """Load every table; return row counts. Raises DataError on the first problem found."""
    return {name: len(load_table(name, raw_dir)) for name in TABLES}
