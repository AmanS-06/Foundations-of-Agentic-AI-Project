"""Long-term memory: what happened on past planning runs, kept in SQLite.

Short-term memory is the graph state of the current run (it disappears when the run ends).
Long-term memory survives between runs: after every run the Business Automation agent saves a
short record and a lesson, and the Research agent recalls runs for the same kind of day
("last fest: the budget forced the +0% branch"). This gives the agents experience without
putting the whole history into the language model's limited context window.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from zeroplate import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    plan_date   TEXT NOT NULL,
    event       TEXT NOT NULL,
    status      TEXT NOT NULL,      -- approved / escalated
    buffer      REAL,
    food_cost   REAL,
    revisions   INTEGER NOT NULL,
    lesson      TEXT NOT NULL
)
"""


class Memory:
    def __init__(self, path: Path = config.MEMORY_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def save_run(
        self,
        run_id: str,
        plan_date: str,
        event: str,
        status: str,
        buffer: float | None,
        food_cost: float | None,
        revisions: int,
        lesson: str,
    ) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    datetime.now().isoformat(timespec="seconds"),
                    plan_date,
                    event,
                    status,
                    buffer,
                    food_cost,
                    revisions,
                    lesson,
                ),
            )

    def similar(self, event: str, limit: int = 3) -> list[dict]:
        """Most recent runs for the same kind of day (fest, exam, ...)."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM runs WHERE event = ? ORDER BY created_at DESC LIMIT ?",
                (event, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
