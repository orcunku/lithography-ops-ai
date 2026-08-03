"""Stage D - observability / tracing.

A lightweight, dependency-free tracer that records every step of a pipeline run
as a timed "span". Spans nest (a coordinator span contains agent spans, which
contain tool-call spans), so a finished trace is a full, replayable record of
what happened: which agent ran, which tool it called, what it retrieved, and how
long each step took.

Traces are saved to SQLite (a new `traces` table) so they are queryable and
auditable alongside the existing audit trail. This mirrors how production
systems use OpenTelemetry-style spans, but with zero external dependencies so it
runs anywhere.

Usage:
    tracer = Tracer(run_id)
    with tracer.span("coordinator", machine_id="LITHO-EUV-03"):
        with tracer.span("agent:Monitoring"):
            ...
    tracer.save()          # persists to SQLite
    print(tracer.summary())
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from lithoops.db import store


@dataclass
class Span:
    name: str
    start_ms: float
    end_ms: float = 0.0
    depth: int = 0
    attributes: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return round((self.end_ms - self.start_ms), 2)


class Tracer:
    """Collects nested, timed spans for one pipeline run."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or f"RUN-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.spans: list[Span] = []
        self._depth = 0

    @contextmanager
    def span(self, name: str, **attributes):
        s = Span(name=name, start_ms=time.perf_counter() * 1000,
                 depth=self._depth, attributes=attributes)
        self.spans.append(s)
        self._depth += 1
        try:
            yield s
        finally:
            self._depth -= 1
            s.end_ms = time.perf_counter() * 1000

    def add_attribute(self, span: Span, **kw):
        span.attributes.update(kw)

    # ---- reporting ----
    def total_ms(self) -> float:
        roots = [s for s in self.spans if s.depth == 0]
        return round(sum(s.duration_ms for s in roots), 2)

    def summary(self) -> str:
        lines = [f"Trace {self.run_id}  (total {self.total_ms()} ms)"]
        for s in self.spans:
            indent = "  " * s.depth
            attr = ""
            if s.attributes:
                attr = "  " + ", ".join(f"{k}={v}" for k, v in s.attributes.items())
            lines.append(f"{indent}\u2514 {s.name}: {s.duration_ms} ms{attr}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "total_ms": self.total_ms(),
            "spans": [asdict(s) | {"duration_ms": s.duration_ms} for s in self.spans],
        }

    # ---- persistence ----
    def save(self, db_path=store.DB_PATH) -> None:
        _ensure_table(db_path)
        with store.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces (run_id, created_at, total_ms, payload) "
                "VALUES (?,?,?,?)",
                (self.run_id, self.created_at, self.total_ms(),
                 json.dumps(self.as_dict())),
            )


def _ensure_table(db_path=store.DB_PATH) -> None:
    with store.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS traces ("
            "run_id TEXT PRIMARY KEY, created_at TEXT, total_ms REAL, payload TEXT)"
        )


def get_trace(run_id: str, db_path=store.DB_PATH) -> dict | None:
    _ensure_table(db_path)
    rows = store.query("SELECT payload FROM traces WHERE run_id=?", (run_id,), db_path)
    return json.loads(rows[0]["payload"]) if rows else None


def list_traces(limit: int = 50, db_path=store.DB_PATH) -> list[dict]:
    _ensure_table(db_path)
    return store.query(
        "SELECT run_id, created_at, total_ms FROM traces "
        "ORDER BY created_at DESC LIMIT ?", (limit,), db_path)
