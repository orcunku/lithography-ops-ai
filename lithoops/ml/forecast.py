"""Spare-parts demand forecast.

Turns per-machine failure risk into an expected spare-parts demand over a
planning horizon, using a subsystem -> part mapping (a simple bill of
materials). Flags parts where expected demand exceeds stock-on-hand.
"""
from __future__ import annotations

import pandas as pd

from lithoops.agents.subsystems import infer_subsystem
from lithoops.db import store

SUBSYSTEM_PART = {
    "cooling": "P-COOL-01",
    "reticle stage": "P-STG-04",
    "source": "P-SRC-02",
}


def forecast_parts(scored: pd.DataFrame, horizon_days: int = 30) -> list[dict]:
    """Expected demand = mean recent failure_risk per machine, mapped to parts."""
    inv = {r["part_id"]: r for r in store.query("SELECT * FROM inventory")}

    demand: dict[str, float] = {}
    for mid, g in scored.groupby("machine_id"):
        recent = g.tail(60)
        risk = float(recent["failure_risk"].mean())
        subsystem = infer_subsystem(recent)
        part = SUBSYSTEM_PART.get(subsystem)
        if part:
            demand[part] = demand.get(part, 0.0) + round(risk * horizon_days / 30, 2)

    rows = []
    for part_id, exp in demand.items():
        rec = inv.get(part_id, {})
        on_hand = int(rec.get("qty_on_hand", 0))
        rows.append({
            "part_id": part_id,
            "name": rec.get("name", part_id),
            "expected_demand": round(exp, 2),
            "on_hand": on_hand,
            "lead_time_days": int(rec.get("lead_time_days", 0)),
            "reorder": exp > on_hand,
        })
    return sorted(rows, key=lambda r: -r["expected_demand"])
