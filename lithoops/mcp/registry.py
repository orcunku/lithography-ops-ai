"""Read-only data tools — the single source of truth for data access.

Every tool here is read-only and pulls from SQLite (reference data) or the
scored telemetry CSV. Both the local client and the MCP server expose exactly
these tools, so agent behavior is identical regardless of transport. This is
the guardrail that makes access explicit, testable and secure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from lithoops.config import DATA_DIR
from lithoops.db import store


def _telemetry_path() -> Path:
    scored = DATA_DIR / "telemetry_scored.csv"
    return scored if scored.exists() else DATA_DIR / "telemetry.csv"


def get_telemetry(machine_id: str | None = None, last_n: int | None = None) -> list[dict]:
    df = pd.read_csv(_telemetry_path())
    if machine_id:
        df = df[df.machine_id == machine_id]
    if last_n:
        df = df.tail(last_n)
    return df.to_dict(orient="records")


def get_incidents(status: str | None = None) -> list[dict]:
    if status:
        return store.query("SELECT * FROM incidents WHERE status=?", (status,))
    return store.query("SELECT * FROM incidents")


def search_knowledge(subsystem: str | None = None, query: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM knowledge WHERE 1=1", []
    if subsystem:
        sql += " AND lower(subsystem)=lower(?)"; params.append(subsystem)
    if query:
        sql += " AND (lower(title) LIKE ? OR lower(content) LIKE ?)"
        params += [f"%{query.lower()}%", f"%{query.lower()}%"]
    return store.query(sql, tuple(params))


def get_inventory(subsystem: str | None = None) -> list[dict]:
    if subsystem:
        return store.query("SELECT * FROM inventory WHERE lower(subsystem)=lower(?)", (subsystem,))
    return store.query("SELECT * FROM inventory")


def get_engineers(available_only: bool = False) -> list[dict]:
    if available_only:
        return store.query("SELECT * FROM engineers WHERE available=1")
    return store.query("SELECT * FROM engineers")


TOOLS: dict[str, dict[str, Any]] = {
    "get_telemetry": {
        "fn": get_telemetry,
        "desc": "Read-only telemetry rows, optionally filtered by machine_id and last_n.",
        "args": {"machine_id": "string?", "last_n": "integer?"},
    },
    "get_incidents": {
        "fn": get_incidents,
        "desc": "Incident records, optionally filtered by status.",
        "args": {"status": "string?"},
    },
    "search_knowledge": {
        "fn": search_knowledge,
        "desc": "Maintenance knowledge base search by subsystem and/or keyword.",
        "args": {"subsystem": "string?", "query": "string?"},
    },
    "get_inventory": {
        "fn": get_inventory,
        "desc": "Spare-parts inventory, optionally filtered by subsystem.",
        "args": {"subsystem": "string?"},
    },
    "get_engineers": {
        "fn": get_engineers,
        "desc": "Engineer roster, optionally only those available now.",
        "args": {"available_only": "boolean?"},
    },
}


def call_tool(name: str, **kwargs) -> list[dict]:
    if name not in TOOLS:
        raise KeyError(f"Unknown tool: {name}")
    return TOOLS[name]["fn"](**kwargs)


def list_tools() -> list[dict]:
    return [{"name": n, "description": t["desc"], "args": t["args"]}
            for n, t in TOOLS.items()]
