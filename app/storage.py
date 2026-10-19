"""SQLite storage: the AI model inventory ("Model Inventory") and audit run history.

Everything a bank governance team expects to persist: every model/bot under test
with owner, risk tier, data classification, last-tested date and status, plus a
record of every audit run (score, rating, pass counts, full result JSON).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner TEXT,
    risk_tier TEXT,
    data_classification TEXT,
    endpoint TEXT,
    status TEXT DEFAULT 'registered',
    last_tested TEXT,
    last_rating TEXT,
    last_risk_score REAL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id TEXT,
    bot_version TEXT,
    created_at TEXT NOT NULL,
    rating TEXT,
    risk_score REAL,
    passed INTEGER,
    failed INTEGER,
    total INTEGER,
    control_failures INTEGER,
    result_json TEXT
);
"""

SEED_INVENTORY = [
    ("abc-bank-assistant-v1", "ABC Bank Assistant (v1, ungoverned)", "AI Engineering",
     "Tier 1", "Synthetic", "mock://v1"),
    ("abc-bank-assistant-v2", "ABC Bank Assistant (v2, governed)", "AI Engineering",
     "Tier 1", "Synthetic", "mock://v2"),
]


@contextmanager
def _conn():
    s = get_settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(s.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(seed: bool = True) -> None:
    with _conn() as c:
        c.executescript(SCHEMA)
        if seed:
            for row in SEED_INVENTORY:
                c.execute(
                    "INSERT OR IGNORE INTO inventory (id,name,owner,risk_tier,data_classification,endpoint) "
                    "VALUES (?,?,?,?,?,?)", row)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_run(result, inventory_id: str | None = None) -> int:
    sc = result.scorecard
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO runs (inventory_id,bot_version,created_at,rating,risk_score,passed,failed,total,"
            "control_failures,result_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (inventory_id, result.bot_version, _now(), sc.rating, sc.risk_score, sc.passed, sc.failed,
             sc.total, sc.control_failures, json.dumps(result.to_dict())))
        if inventory_id:
            c.execute(
                "UPDATE inventory SET status='tested', last_tested=?, last_rating=?, last_risk_score=? WHERE id=?",
                (_now(), sc.rating, sc.risk_score, inventory_id))
        return cur.lastrowid


def list_inventory() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM inventory ORDER BY risk_tier, name")]


def list_runs(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id,inventory_id,bot_version,created_at,rating,risk_score,passed,failed,total,control_failures "
            "FROM runs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT result_json FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None
