"""Automated test suite for LithoOps AI.

Run:  pytest -q          (or)   pytest --cov=lithoops -q
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from lithoops.agents.team import (CoordinatorAgent, IncidentTriageAgent,
                                  MonitoringAgent)
from lithoops.api.app import api
from lithoops.business import ValueInputs, compute_value
from lithoops.config import DATA_DIR, MACHINES, TARGETS
from lithoops.data import generate_all
from lithoops.ml.engine import HealthEngine, train
from lithoops.mcp import registry


@pytest.fixture(scope="session", autouse=True)
def built():
    generate_all()
    train()


@pytest.fixture
def client():
    return TestClient(api)


def test_three_machines():
    tel = pd.read_csv(DATA_DIR / "telemetry.csv")
    assert tel.machine_id.nunique() == 3


def test_labels_present():
    tel = pd.read_csv(DATA_DIR / "telemetry.csv")
    for col in ["is_anomaly_true", "fails_soon", "rul_minutes"]:
        assert col in tel.columns


def test_model_meets_targets():
    scored = pd.read_csv(DATA_DIR / "telemetry_scored.csv")
    report = HealthEngine.load().evaluate(scored).as_dict()
    assert report["failure_recall"] >= TARGETS.failure_recall
    assert report["false_alert_rate"] < TARGETS.false_alert_rate


def test_rul_reasonable():
    scored = pd.read_csv(DATA_DIR / "telemetry_scored.csv")
    report = HealthEngine.load().evaluate(scored).as_dict()
    assert report["rul_mae_minutes"] < 30


def test_tools_readonly_return_lists():
    for spec in registry.list_tools():
        assert isinstance(registry.call_tool(spec["name"]), list)


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        registry.call_tool("delete_everything")


def test_coordinator_requires_approval():
    rec = CoordinatorAgent().run("LITHO-EUV-03")
    assert rec["status"] == "AWAITING_HUMAN_APPROVAL"


def test_triage_always_shows_signals():
    mon = MonitoringAgent().run("LITHO-EUV-03")
    triage = IncidentTriageAgent().run(mon)
    assert "supporting_signals" in triage.data


def test_evidence_coverage_all_machines():
    for m in MACHINES:
        rec = CoordinatorAgent().run(m)
        assert rec["evidence_complete"] is True


def test_high_urgency_on_failing_machine():
    rec = CoordinatorAgent().run("LITHO-EUV-03")
    assert rec["triage"]["urgency"] in {"medium", "high"}
    assert rec["triage"]["suspected_subsystem"] == "cooling"


def test_value_formula():
    out = compute_value(ValueInputs(
        incidents_avoided_per_year=10,
        downtime_hours_avoided_per_incident=5,
        value_per_equipment_hour=1000,
        operating_cost_annual=10000))
    assert out["gross_annual_value"] == 50000
    assert out["net_annual_value"] == 40000


def test_api_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_api_fleet(client):
    fleet = client.get("/fleet").json()
    assert len(fleet) == 3


def test_api_recommend_approve_audit(client):
    r = client.post("/machine/LITHO-EUV-03/recommend").json()
    rid = r["rec_id"]
    assert r["status"] == "AWAITING_HUMAN_APPROVAL"
    client.post(f"/recommendations/{rid}/approve",
                json={"actor": "tester", "note": "ok"})
    trail = client.get(f"/audit?rec_id={rid}").json()
    actions = {a["action"] for a in trail}
    assert {"created", "approved"} <= actions


def test_api_unknown_machine(client):
    assert client.post("/machine/NOPE/recommend").status_code == 404


def test_mcp_server_registers_tools():
    import asyncio
    from lithoops.mcp.server import app
    tools = asyncio.run(app.list_tools())
    assert len(tools) == 5
