"""LithoOps AI — operations dashboard (Streamlit).

Run:  streamlit run scripts/dashboard.py

Design identity: a fab "control room" — dark instrument panel, monospace data
type, amber/cyan status accents. Everything shown here is synthetic and every
operational action requires explicit human approval.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lithoops.agents.team import CoordinatorAgent
from lithoops.business import ValueInputs, compute_value
from lithoops.config import DATA_DIR, MACHINES
from lithoops.db import store
from lithoops.ml.engine import HealthEngine

st.set_page_config(page_title="LithoOps AI", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --bg:#0d1117; --panel:#161b22; --amber:#f0a020; --cyan:#39c5cf; --red:#e5484d; }
.stApp { background:#0d1117; }
h1,h2,h3 { font-family:'DejaVu Sans Mono',monospace; letter-spacing:.5px; }
[data-testid="stMetricValue"] { font-family:'DejaVu Sans Mono',monospace; }
.block-container { padding-top:2rem; }
</style>
""", unsafe_allow_html=True)

st.title("\u25e2 LithoOps AI — EUV/DUV Operations Intelligence")
st.caption("PROTOTYPE · SYNTHETIC DATA · recommendations are read-only until a human approves")


@st.cache_data
def load_scored():
    p = DATA_DIR / "telemetry_scored.csv"
    return pd.read_csv(p) if p.exists() else None


scored = load_scored()
if scored is None:
    st.error("No trained model found. Run:  python scripts/build.py")
    st.stop()

tab_fleet, tab_machine, tab_value, tab_audit = st.tabs(
    ["\U0001f6f0 Fleet", "\U0001f52c Machine detail", "\U0001f4b6 Business value", "\U0001f4cb Audit trail"])

with tab_fleet:
    st.subheader("Fleet status")
    summary = (scored.groupby("machine_id")
               .agg(health=("health_score", "mean"),
                    anomalies=("is_anomaly_pred", "sum"),
                    risk=("failure_risk", "mean"),
                    rul=("rul_pred", "min")).round(2).reset_index())
    cols = st.columns(len(summary))
    for col, r in zip(cols, summary.itertuples()):
        dot = "\U0001f7e2" if r.health > 70 else ("\U0001f7e0" if r.health > 50 else "\U0001f534")
        col.metric(f"{dot} {r.machine_id}", f"{r.health:.0f}/100",
                   f"risk {r.risk:.2f} · RUL {r.rul:.0f}m", delta_color="off")
    st.markdown("**Model quality vs prototype targets**")
    report = HealthEngine.load().evaluate(scored).as_dict()
    m = st.columns(4)
    m[0].metric("Anomaly recall", f"{report['failure_recall']:.0%}", "target \u226580%")
    m[1].metric("False-alert rate", f"{report['false_alert_rate']:.0%}", "target <10%")
    m[2].metric("Risk precision", f"{report['risk_precision']:.0%}")
    m[3].metric("RUL error", f"{report['rul_mae_minutes']:.1f} min")

with tab_machine:
    machine = st.selectbox("Machine", list(MACHINES), index=2)
    mt = scored[scored.machine_id == machine].reset_index(drop=True)

    st.subheader(f"Health timeline — {machine}")
    fig = go.Figure()
    fig.add_scatter(x=mt.index, y=mt.health_score, mode="lines",
                    line=dict(color="#39c5cf", width=2), name="health")
    anom = mt[mt.is_anomaly_pred == 1]
    fig.add_scatter(x=anom.index, y=anom.health_score, mode="markers",
                    marker=dict(color="#e5484d", size=5), name="anomaly")
    fig.update_layout(template="plotly_dark", height=280,
                      margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#161b22")
    st.plotly_chart(fig, use_container_width=True)

    sensor = st.selectbox("Sensor", ["overlay_error", "temperature", "focus_error",
                                     "vibration", "source_power", "wafer_throughput"])
    fig2 = go.Figure()
    fig2.add_scatter(x=mt.index, y=mt[sensor], mode="lines",
                     line=dict(color="#f0a020", width=1.5))
    fig2.update_layout(template="plotly_dark", height=220,
                       margin=dict(l=0, r=0, t=10, b=0),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#161b22")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Coordinator recommendation")
    if st.button("\u25b6 Run agent team", type="primary"):
        st.session_state["rec"] = CoordinatorAgent().run(machine)
        store.save_recommendation(st.session_state["rec"])

    rec = st.session_state.get("rec")
    if rec and rec["machine_id"] == machine:
        c = st.columns(4)
        c[0].metric("Urgency", rec["triage"]["urgency"].upper())
        c[1].metric("Subsystem", rec["triage"]["suspected_subsystem"] or "—")
        c[2].metric("Health", rec["monitoring"]["health"])
        c[3].metric("Failure risk", rec["monitoring"]["failure_risk"])

        st.markdown("**Facts (evidence)**")
        for f in rec["handover"]["facts"]:
            st.text("• " + f)
        st.markdown("**Suggestions**")
        for s in rec["handover"]["suggestions"]:
            st.text("• " + s)
        for d in rec["knowledge"]["docs"]:
            st.info(f"[{d['doc_id']}] {d['title']} — {d['content']}")

        st.markdown(f"**Status:** `{rec['status']}` — human approval required")
        a1, a2 = st.columns(2)
        if a1.button("\u2705 Approve"):
            store.set_recommendation_status(rec["rec_id"], "APPROVED", actor="dashboard_operator")
            st.success(f"{rec['rec_id']} approved and logged to audit trail.")
        if a2.button("\u274c Reject"):
            store.set_recommendation_status(rec["rec_id"], "REJECTED", actor="dashboard_operator")
            st.warning(f"{rec['rec_id']} rejected and logged.")

with tab_value:
    st.subheader("Business-value calculator")
    st.caption("Hypothetical illustration only — not real ASML or customer financials.")
    c = st.columns(4)
    inc = c[0].number_input("Incidents avoided/yr", 0.0, 100.0, 12.0)
    dt = c[1].number_input("Downtime hrs/incident", 0.0, 48.0, 6.0)
    vph = c[2].number_input("Value/equipment hr (€)", 0.0, 1e6, 12000.0, step=1000.0)
    oc = c[3].number_input("Operating cost/yr (€)", 0.0, 1e7, 150000.0, step=10000.0)
    out = compute_value(ValueInputs(inc, dt, vph, oc))
    v = st.columns(3)
    v[0].metric("Gross annual value", f"€{out['gross_annual_value']:,.0f}")
    v[1].metric("Operating cost", f"€{out['operating_cost_annual']:,.0f}")
    v[2].metric("Net annual value", f"€{out['net_annual_value']:,.0f}")

with tab_audit:
    st.subheader("Audit trail (most recent)")
    trail = store.get_audit_trail()
    if trail:
        st.dataframe(pd.DataFrame(trail)[["ts", "rec_id", "action", "actor", "detail"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No actions logged yet. Run a recommendation and approve it.")
