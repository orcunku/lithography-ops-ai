"""Synthetic data generation for the simulated lithography fleet.

Produces per-minute telemetry with ground-truth labels for THREE ML targets:
  is_anomaly_true  - unsupervised anomaly ground truth
  fails_soon       - binary: a failure event occurs within FAIL_HORIZON minutes
  rul_minutes      - remaining useful life until the next failure event

Also generates operational reference data (incidents, inventory, engineers,
knowledge) and loads everything into SQLite.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from lithoops.config import BASELINE, DATA_DIR, MINUTES_PER_MACHINE, SEED
from lithoops.db import store

RNG = np.random.default_rng(SEED)
START = datetime(2026, 7, 30, 6, 0, 0)
FAIL_HORIZON = 30  # minutes: "fails_soon" lookahead


def _baseline(machine_id: str, machine_type: str, n: int) -> pd.DataFrame:
    ts = [START + timedelta(minutes=i) for i in range(n)]
    df = pd.DataFrame({"timestamp": ts})
    df["machine_id"] = machine_id
    df["machine_type"] = machine_type
    for field, (mu, sd) in BASELINE.items():
        if field == "alarm_count":
            df[field] = RNG.poisson(mu, n).astype(float)
        else:
            df[field] = RNG.normal(mu, sd, n)
    df["time_since_maintenance"] = np.linspace(50, 62, n)
    df["is_anomaly_true"] = 0
    df["failure_event"] = 0
    return df


def _healthy(mid="LITHO-DUV-01", n=MINUTES_PER_MACHINE):
    return _baseline(mid, "DUV", n)


def _drifting(mid="LITHO-EUV-02", n=MINUTES_PER_MACHINE):
    df = _baseline(mid, "EUV", n)
    ramp = np.clip((np.arange(n) - 0.4 * n) / (0.6 * n), 0, 1)
    df["overlay_error"] += ramp * 2.5
    df["vibration"] += ramp * 0.10
    df["source_power"] -= ramp * 8.0
    df["wafer_throughput"] -= ramp * 15.0
    df.loc[ramp > 0.5, "is_anomaly_true"] = 1
    df.loc[n - 1, "failure_event"] = 1
    return df


def _maintenance(mid="LITHO-EUV-03", n=MINUTES_PER_MACHINE):
    df = _baseline(mid, "EUV", n)
    event_start = int(0.75 * n)
    sev = np.clip((np.arange(n) - event_start) / (n - event_start), 0, 1)
    df["temperature"] += sev * 4.0
    df["focus_error"] += sev * 3.5
    df["vacuum_pressure"] += sev * 1.5e-4
    df["alarm_count"] += (sev * 6).astype(int)
    df["time_since_maintenance"] = np.linspace(50, 95, n)
    df.loc[event_start:, "is_anomaly_true"] = 1
    df.loc[n - 1, "failure_event"] = 1
    return df


def _add_supervised_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Derive fails_soon and rul_minutes per machine from failure_event."""
    out = []
    for mid, g in df.groupby("machine_id", sort=False):
        g = g.reset_index(drop=True).copy()
        fail_idx = g.index[g.failure_event == 1].tolist()
        fails_soon = np.zeros(len(g), dtype=int)
        if fail_idx:
            next_fail = fail_idx[0]
            rul = np.clip(next_fail - np.arange(len(g)), 0, None).astype(float)
            fails_soon = ((rul <= FAIL_HORIZON) & (rul >= 0)).astype(int)
        else:
            rul = np.full(len(g), float(len(g)))
        g["rul_minutes"] = rul
        g["fails_soon"] = fails_soon
        out.append(g)
    return pd.concat(out, ignore_index=True)


def build_reference_data() -> dict[str, list[dict]]:
    incidents = [
        dict(incident_id="INC-1001", machine_id="LITHO-EUV-02", opened="2026-07-30 09:12",
             severity="medium", subsystem="reticle stage", status="open",
             summary="Overlay error trending upward over several hours."),
        dict(incident_id="INC-1002", machine_id="LITHO-EUV-03", opened="2026-07-30 15:40",
             severity="high", subsystem="cooling", status="open",
             summary="Temperature and focus error rising; alarms increasing."),
        dict(incident_id="INC-0990", machine_id="LITHO-DUV-01", opened="2026-07-29 22:05",
             severity="low", subsystem="wafer handler", status="closed",
             summary="Single transient handler alarm, auto-recovered."),
    ]
    inventory = [
        dict(part_id="P-COOL-01", name="Cooling pump seal kit", subsystem="cooling",
             qty_on_hand=3, lead_time_days=2),
        dict(part_id="P-STG-04", name="Reticle stage sensor", subsystem="reticle stage",
             qty_on_hand=0, lead_time_days=7),
        dict(part_id="P-SRC-02", name="Source power module", subsystem="source",
             qty_on_hand=1, lead_time_days=5),
    ]
    engineers = [
        dict(engineer_id="E-01", name="A. Novak", skills="cooling;source", shift="day", available=1),
        dict(engineer_id="E-02", name="R. Silva", skills="reticle stage;overlay", shift="day", available=1),
        dict(engineer_id="E-03", name="K. Meyer", skills="cooling;wafer handler", shift="night", available=0),
    ]
    knowledge = [
        dict(doc_id="KB-OVL-01", subsystem="reticle stage", title="Overlay error drift diagnosis",
             content="Rising overlay error commonly indicates reticle stage calibration drift. "
                     "Check stage sensor readings, re-run overlay calibration, inspect sensor P-STG-04."),
        dict(doc_id="KB-COOL-01", subsystem="cooling", title="Cooling system temperature rise",
             content="Temperature and focus error rising together suggest a cooling fault. Inspect "
                     "pump seals (P-COOL-01), verify coolant flow, schedule maintenance if alarms persist."),
        dict(doc_id="KB-SRC-01", subsystem="source", title="Source power degradation",
             content="Sagging source power with throughput loss points to a source module issue. "
                     "Verify power module P-SRC-02 and collector condition."),
    ]
    return dict(incidents=incidents, inventory=inventory,
                engineers=engineers, knowledge=knowledge)


def generate_all() -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tel = pd.concat([_healthy(), _drifting(), _maintenance()], ignore_index=True)
    tel = _add_supervised_labels(tel)
    tel.to_csv(DATA_DIR / "telemetry.csv", index=False)

    store.init_db()
    ref = build_reference_data()
    for table, rows in ref.items():
        store.bulk_load(table, rows)

    return tel


if __name__ == "__main__":
    tel = generate_all()
    print(f"Telemetry rows: {len(tel)} | machines: {tel.machine_id.nunique()}")
    print(f"fails_soon positives: {int(tel.fails_soon.sum())}")
    print(f"Reference tables loaded into {store.DB_PATH.name}")
