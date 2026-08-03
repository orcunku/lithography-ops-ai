"""Shared logic to map anomalous sensor deviations to a suspected subsystem.

Used by the triage agent and the parts forecaster so the mapping lives in one
place. Deviation is measured against the healthy-machine baseline.
"""
from __future__ import annotations

import pandas as pd

from lithoops.config import BASELINE

SIGNAL_SUBSYSTEM = {
    "overlay_error": "reticle stage",
    "focus_error": "cooling",
    "temperature": "cooling",
    "vibration": "reticle stage",
    "source_power": "source",
    "wafer_throughput": "source",
}

_CHECK_FIELDS = ["overlay_error", "temperature", "focus_error",
                 "vibration", "source_power", "wafer_throughput"]


def top_signals(rows: pd.DataFrame, k: int = 3) -> list[tuple[str, float]]:
    """Largest deviations from healthy baseline among anomalous rows."""
    anom = rows[rows.get("is_anomaly_pred", 0) == 1]
    src = anom if not anom.empty else rows
    if src.empty:
        return []
    devs = []
    for f in _CHECK_FIELDS:
        base = BASELINE.get(f, (src[f].mean(), 1))[0]
        devs.append((f, round(abs(src[f].mean() - base), 3)))
    devs.sort(key=lambda x: -x[1])
    return devs[:k]


def infer_subsystem(rows: pd.DataFrame) -> str | None:
    sig = top_signals(rows, k=1)
    if not sig:
        return None
    return SIGNAL_SUBSYSTEM.get(sig[0][0])
