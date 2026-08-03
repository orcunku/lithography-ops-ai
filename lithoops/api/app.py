"""FastAPI application for LithoOps AI.

Endpoints
  GET  /health                     - liveness
  GET  /fleet                      - per-machine health summary
  GET  /machine/{id}/telemetry     - recent telemetry
  POST /machine/{id}/recommend     - run agent team, persist recommendation
  GET  /recommendations/{rec_id}   - fetch a saved recommendation
  POST /recommendations/{rec_id}/approve  - human approval -> audit trail
  POST /recommendations/{rec_id}/reject   - human rejection -> audit trail
  GET  /audit                      - recent audit-log entries
  POST /value                      - business-value calculator
  GET  /metrics                    - model evaluation vs prototype targets
"""
from __future__ import annotations

import json

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lithoops.agents.team import CoordinatorAgent
from lithoops.business import ValueInputs, compute_value
from lithoops.config import DATA_DIR, MACHINES
from lithoops.db import store
from lithoops.ml.engine import HealthEngine

api = FastAPI(title="LithoOps AI", version="1.0.0",
              description="EUV/DUV operations intelligence prototype (synthetic data).")


class ApprovalBody(BaseModel):
    actor: str = "operator"
    note: str = ""


class ValueBody(BaseModel):
    incidents_avoided_per_year: float = 12.0
    downtime_hours_avoided_per_incident: float = 6.0
    value_per_equipment_hour: float = 12000.0
    operating_cost_annual: float = 150000.0


@api.get("/health")
def health() -> dict:
    return {"status": "ok", "machines": list(MACHINES)}


@api.get("/fleet")
def fleet() -> list[dict]:
    path = DATA_DIR / "telemetry_scored.csv"
    if not path.exists():
        raise HTTPException(503, "Model not trained yet. Run scripts/build.py.")
    df = pd.read_csv(path)
    summary = (df.groupby("machine_id")
               .agg(health=("health_score", "mean"),
                    anomalies=("is_anomaly_pred", "sum"),
                    failure_risk=("failure_risk", "mean"),
                    rul_min=("rul_pred", "min"))
               .round(3).reset_index())
    return summary.to_dict(orient="records")


@api.get("/machine/{machine_id}/telemetry")
def telemetry(machine_id: str, last_n: int = 60) -> list[dict]:
    if machine_id not in MACHINES:
        raise HTTPException(404, "Unknown machine")
    from lithoops.mcp import registry
    return registry.call_tool("get_telemetry", machine_id=machine_id, last_n=last_n)


@api.post("/machine/{machine_id}/recommend")
def recommend(machine_id: str) -> dict:
    if machine_id not in MACHINES:
        raise HTTPException(404, "Unknown machine")
    rec = CoordinatorAgent().run(machine_id)
    store.save_recommendation(rec)
    return rec


@api.get("/recommendations/{rec_id}")
def get_recommendation(rec_id: str) -> dict:
    rows = store.query("SELECT * FROM recommendations WHERE rec_id=?", (rec_id,))
    if not rows:
        raise HTTPException(404, "Unknown recommendation")
    row = rows[0]
    row["payload"] = json.loads(row["payload"])
    return row


@api.post("/recommendations/{rec_id}/approve")
def approve(rec_id: str, body: ApprovalBody) -> dict:
    if not store.query("SELECT 1 FROM recommendations WHERE rec_id=?", (rec_id,)):
        raise HTTPException(404, "Unknown recommendation")
    store.set_recommendation_status(rec_id, "APPROVED", actor=body.actor)
    if body.note:
        store.audit(rec_id, "note", actor=body.actor, detail=body.note)
    return {"rec_id": rec_id, "status": "APPROVED", "actor": body.actor}


@api.post("/recommendations/{rec_id}/reject")
def reject(rec_id: str, body: ApprovalBody) -> dict:
    if not store.query("SELECT 1 FROM recommendations WHERE rec_id=?", (rec_id,)):
        raise HTTPException(404, "Unknown recommendation")
    store.set_recommendation_status(rec_id, "REJECTED", actor=body.actor)
    if body.note:
        store.audit(rec_id, "note", actor=body.actor, detail=body.note)
    return {"rec_id": rec_id, "status": "REJECTED", "actor": body.actor}


@api.get("/audit")
def audit(rec_id: str | None = None) -> list[dict]:
    return store.get_audit_trail(rec_id)


@api.post("/value")
def value(body: ValueBody) -> dict:
    return compute_value(ValueInputs(**body.model_dump()))


@api.get("/metrics")
def metrics() -> dict:
    path = DATA_DIR / "telemetry_scored.csv"
    if not path.exists():
        raise HTTPException(503, "Model not trained yet.")
    engine = HealthEngine.load()
    scored = pd.read_csv(path)
    return engine.evaluate(scored).as_dict()
