"""SQLite persistence layer with an audit trail.

Tables:
  incidents, inventory, engineers, knowledge  - operational reference data
  recommendations                             - every coordinator output
  audit_log                                   - append-only trail of actions

The audit trail is what makes recommendations *traceable*: nothing is
"actioned" without a human-approval row here.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from lithoops.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY, machine_id TEXT, opened TEXT,
    severity TEXT, subsystem TEXT, status TEXT, summary TEXT
);
CREATE TABLE IF NOT EXISTS inventory (
    part_id TEXT PRIMARY KEY, name TEXT, subsystem TEXT,
    qty_on_hand INTEGER, lead_time_days INTEGER
);
CREATE TABLE IF NOT EXISTS engineers (
    engineer_id TEXT PRIMARY KEY, name TEXT, skills TEXT,
    shift TEXT, available INTEGER
);
CREATE TABLE IF NOT EXISTS knowledge (
    doc_id TEXT PRIMARY KEY, subsystem TEXT, title TEXT, content TEXT
);
CREATE TABLE IF NOT EXISTS recommendations (
    rec_id TEXT PRIMARY KEY, machine_id TEXT, created_at TEXT,
    urgency TEXT, subsystem TEXT, status TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, rec_id TEXT,
    action TEXT, actor TEXT, detail TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def bulk_load(table: str, rows: list[dict], db_path: Path | str = DB_PATH) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    with connect(db_path) as conn:
        conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])


def query(sql: str, params: tuple = (), db_path: Path | str = DB_PATH) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def save_recommendation(rec: dict[str, Any], db_path: Path | str = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO recommendations "
            "(rec_id, machine_id, created_at, urgency, subsystem, status, payload) "
            "VALUES (?,?,?,?,?,?,?)",
            (rec["rec_id"], rec["machine_id"], rec["created_at"],
             rec["triage"]["urgency"], rec["triage"]["suspected_subsystem"],
             rec["status"], json.dumps(rec)),
        )
    audit(rec["rec_id"], "created", actor="system",
          detail=f"urgency={rec['triage']['urgency']}", db_path=db_path)


def audit(rec_id: str, action: str, actor: str = "system",
          detail: str = "", db_path: Path | str = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_log (ts, rec_id, action, actor, detail) VALUES (?,?,?,?,?)",
            (_now(), rec_id, action, actor, detail),
        )


def set_recommendation_status(rec_id: str, status: str, actor: str,
                              db_path: Path | str = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE recommendations SET status=? WHERE rec_id=?",
                     (status, rec_id))
    audit(rec_id, status.lower(), actor=actor, db_path=db_path)


def get_audit_trail(rec_id: str | None = None, db_path: Path | str = DB_PATH) -> list[dict]:
    if rec_id:
        return query("SELECT * FROM audit_log WHERE rec_id=? ORDER BY id", (rec_id,), db_path)
    return query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200", (), db_path)
