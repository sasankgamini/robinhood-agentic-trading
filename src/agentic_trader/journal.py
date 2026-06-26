from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS journal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    trading_day TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    symbol TEXT,
    order_id TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_journal_events_day_type
ON journal_events (trading_day, event_type);

CREATE INDEX IF NOT EXISTS idx_journal_events_symbol
ON journal_events (symbol);
"""


def init_journal(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)


def record_event(
    path: Path,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    symbol: str | None = None,
    order_id: str | None = None,
    created_at: datetime | None = None,
) -> int:
    init_journal(path)
    timestamp = created_at or datetime.now(timezone.utc)
    trading_day = str(payload.get("trading_day") or timestamp.astimezone().date())
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO journal_events (
                created_at, trading_day, source, event_type, symbol, order_id, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp.isoformat(),
                trading_day,
                source,
                event_type,
                symbol or payload.get("symbol"),
                order_id or payload.get("order_id"),
                payload_json,
            ),
        )
        return int(cursor.lastrowid)


def summarize(path: Path, limit: int = 50) -> dict[str, Any]:
    init_journal(path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT created_at, trading_day, source, event_type, symbol, order_id, payload_json
            FROM journal_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        counts = connection.execute(
            """
            SELECT event_type, COUNT(*) AS count
            FROM journal_events
            GROUP BY event_type
            ORDER BY count DESC, event_type ASC
            """
        ).fetchall()

    events = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        events.append(
            {
                "created_at": row["created_at"],
                "trading_day": row["trading_day"],
                "source": row["source"],
                "event_type": row["event_type"],
                "symbol": row["symbol"],
                "order_id": row["order_id"],
                "summary": _event_summary(payload),
                "payload": payload,
            }
        )

    return {
        "journal": str(path),
        "event_counts": {row["event_type"]: row["count"] for row in counts},
        "recent_events": events,
    }


def _event_summary(payload: dict[str, Any]) -> str:
    for key in ("summary", "thesis", "reason", "decision", "exit_reason"):
        value = payload.get(key)
        if value:
            return str(value)
    symbol = payload.get("symbol")
    action = payload.get("action") or payload.get("side")
    if symbol and action:
        return f"{action} {symbol}"
    return "No summary provided"
