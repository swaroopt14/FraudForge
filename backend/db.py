"""SQLite persistence for hypotheses, generated attacks, and evaluation runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hypotheses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attack_name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                family TEXT,
                n_rows INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metrics TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def save_hypotheses(hypotheses: list[dict[str, Any]]) -> None:
    init_db()
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO hypotheses (attack_name, payload, created_at) VALUES (?, ?, ?)",
            [
                (h.get("attack_name", "unnamed"), json.dumps(h), _now())
                for h in hypotheses
            ],
        )


def save_attacks(source: str, family: str | None, rows: list[dict[str, Any]]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO attacks (source, family, n_rows, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (source, family, len(rows), json.dumps(rows[:50]), _now()),
        )


def save_evaluation(metrics: dict[str, Any]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO evaluation_runs (metrics, created_at) VALUES (?, ?)",
            (json.dumps(metrics), _now()),
        )


def recent_hypotheses(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT attack_name, payload, created_at FROM hypotheses ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for row in rows:
        payload = json.loads(row["payload"])
        payload["created_at"] = row["created_at"]
        out.append(payload)
    return out
