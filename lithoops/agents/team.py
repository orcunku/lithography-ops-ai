"""The LithoOps agent team.

Six specialists + a coordinator. Design principles:
  * Every agent reaches data ONLY through the read-only tool registry.
  * Every agent returns a structured result that includes its *evidence*.
  * Every agent declares and enforces its *guardrail*.
  * The coordinator never acts autonomously: it produces a recommendation
    that must be approved by a human (written to the audit trail).

These are deliberately transparent (rule + ML based, no LLM required) so the
prototype runs on any hardware.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from lithoops.agents.subsystems import SIGNAL_SUBSYSTEM, top_signals
from lithoops.mcp import registry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AgentResult:
    agent: str
    guardrail: str
    data: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)


class MonitoringAgent:
    name = "Monitoring"
    guardrail = "Cannot change machine settings (read-only)."

    def run(self, machine_id: str) -> AgentResult:
        rows = registry.call_tool("get_telemetry", machine_id=machine_id, last_n=60)
        df = pd.DataFrame(rows)
        if df.empty:
            return AgentResult(self.name, self.guardrail, {"health": None})
        health = round(df["health_score"].mean(), 1)
        anomalies = int(df["is_anomaly_pred"].sum())
        risk = round(df["failure_risk"].mean(), 3)
        rul = round(df["rul_pred"].min(), 1)
        signals = top_signals(df, k=3)
        return AgentResult(
            self.name, self.guardrail,
            data={"machine_id": machine_id, "health": health,
                  "anomalies_last_hour": anomalies, "failure_risk": risk,
                  "rul_minutes": rul, "top_signals": signals},
            evidence=[f"{n}: deviation {d}" for n, d in signals],
        )


class IncidentTriageAgent:
    name = "Incident Triage"
    guardrail = "Must show supporting signals for every ranking."

    def run(self, mon: AgentResult) -> AgentResult:
        d = mon.data
        health = d.get("health") or 100
        anomalies = d.get("anomalies_last_hour", 0)
        risk = d.get("failure_risk", 0)
        if health < 50 or anomalies > 20 or risk > 0.6:
            urgency = "high"
        elif health < 70 or anomalies > 5 or risk > 0.3:
            urgency = "medium"
        else:
            urgency = "low"
        signals = d.get("top_signals", [])
        subsystem = SIGNAL_SUBSYSTEM.get(signals[0][0]) if signals else None
        return AgentResult(
            self.name, self.guardrail,
            data={"urgency": urgency, "suspected_subsystem": subsystem,
                  "supporting_signals": signals},
            evidence=[f"urgency driven by health={health}, anomalies={anomalies}, risk={risk}"],
        )


class KnowledgeAgent:
    name = "Knowledge"
    guardrail = "Must cite the source document for every procedure."

    def run(self, subsystem: str | None, symptoms: str | None = None) -> AgentResult:
        if not subsystem and not symptoms:
            return AgentResult(self.name, self.guardrail,
                               {"docs": [], "retrieval": "none"},
                               ["no subsystem identified"])

        # Prefer semantic RAG retrieval if an index has been built; otherwise
        # fall back to keyword search via the read-only registry. This keeps the
        # project runnable even if the (optional, heavier) RAG deps aren't set up.
        docs, mode = [], "keyword"
        try:
            from lithoops.rag.engine import Retriever, index_exists
            if index_exists():
                query = symptoms or f"{subsystem} fault procedure"
                hits = Retriever().search(query, k=3)
                docs = [{"doc_id": h["doc_id"], "title": h["title"],
                         "content": h["content"], "score": h.get("score")}
                        for h in hits]
                mode = "semantic"
        except Exception:
            docs = []  # any RAG issue -> fall back cleanly

        if not docs:
            docs = registry.call_tool("search_knowledge", subsystem=subsystem)
            mode = "keyword"

        return AgentResult(
            self.name, self.guardrail,
            data={"docs": docs, "retrieval": mode},
            evidence=[f"cited {d['doc_id']}: {d['title']}" for d in docs],
        )


class PlanningAgent:
    name = "Planning"
    guardrail = "Uses only approved read-only data tools."

    def run(self, subsystem: str | None) -> AgentResult:
        parts = registry.call_tool("get_inventory", subsystem=subsystem) if subsystem else []
        engineers = registry.call_tool("get_engineers", available_only=True)
        matched = [{"engineer_id": e["engineer_id"], "name": e["name"]}
                   for e in engineers
                   if subsystem and subsystem.lower() in str(e["skills"]).lower()]
        parts_status = [{"part_id": p["part_id"], "name": p["name"],
                         "in_stock": int(p["qty_on_hand"]) > 0,
                         "qty": int(p["qty_on_hand"]),
                         "lead_time_days": int(p["lead_time_days"])}
                        for p in parts]
        escalate = (not matched) or any(not p["in_stock"] for p in parts_status)
        return AgentResult(
            self.name, self.guardrail,
            data={"parts": parts_status, "available_specialists": matched,
                  "escalate": escalate},
            evidence=[f"{len(matched)} specialist(s) available",
                      f"{sum(p['in_stock'] for p in parts_status)}/{len(parts_status)} parts in stock"],
        )


class ShiftHandoverAgent:
    name = "Shift Handover"
    guardrail = "Separates verified facts from suggestions."

    def run(self, machine_id, mon, triage, planning) -> AgentResult:
        facts = [f"{machine_id}: health {mon.data.get('health')}, "
                 f"{mon.data.get('anomalies_last_hour')} anomalies/hr, "
                 f"failure risk {mon.data.get('failure_risk')}, "
                 f"RUL ~{mon.data.get('rul_minutes')} min."]
        for n, dv in mon.data.get("top_signals", []):
            facts.append(f"Signal {n} deviates by {dv} from healthy baseline.")
        for p in planning.data.get("parts", []):
            state = "in stock" if p["in_stock"] else f"OUT (lead {p['lead_time_days']}d)"
            facts.append(f"Part {p['name']} ({p['part_id']}): {state}.")

        suggestions = []
        if triage.data.get("suspected_subsystem"):
            suggestions.append(f"Investigate {triage.data['suspected_subsystem']} "
                               f"(urgency {triage.data['urgency']}).")
        if planning.data.get("escalate"):
            suggestions.append("Escalate: specialist or part unavailable.")
        return AgentResult(self.name, self.guardrail,
                           {"facts": facts, "suggestions": suggestions},
                           evidence=[f"{len(facts)} facts, {len(suggestions)} suggestions"])


class CoordinatorAgent:
    name = "Coordinator"
    guardrail = "Requires human approval before any action."

    def run(self, machine_id: str, tracer=None) -> dict:
        # Optional observability: if a tracer is passed, each step is timed and
        # recorded as a nested span. If not, behaviour is unchanged.
        from contextlib import nullcontext

        def span(name, **attrs):
            return tracer.span(name, **attrs) if tracer else nullcontext()

        with span("coordinator", machine_id=machine_id):
            with span("agent:Monitoring"):
                mon = MonitoringAgent().run(machine_id)
            with span("agent:IncidentTriage"):
                triage = IncidentTriageAgent().run(mon)
            subsystem = triage.data.get("suspected_subsystem")
            sig = mon.data.get("top_signals", [])
            symptoms = ", ".join(f"{n} rising" for n, _ in sig) or None
            with span("agent:Knowledge", subsystem=subsystem or "none"):
                knowledge = KnowledgeAgent().run(subsystem, symptoms=symptoms)
                if tracer:
                    tracer.spans[-1].attributes["retrieval"] = knowledge.data.get("retrieval")
                    tracer.spans[-1].attributes["docs"] = len(knowledge.data.get("docs", []))
            with span("agent:Planning"):
                planning = PlanningAgent().run(subsystem)
            with span("agent:ShiftHandover"):
                handover = ShiftHandoverAgent().run(machine_id, mon, triage, planning)

        all_evidence = (mon.evidence + triage.evidence + knowledge.evidence +
                        planning.evidence + handover.evidence)
        rec = {
            "rec_id": f"REC-{uuid.uuid4().hex[:8]}",
            "machine_id": machine_id,
            "created_at": _now(),
            "monitoring": mon.data,
            "triage": triage.data,
            "knowledge": knowledge.data,
            "planning": planning.data,
            "handover": handover.data,
            "evidence": all_evidence,
            "evidence_complete": len(all_evidence) > 0,
            "status": "AWAITING_HUMAN_APPROVAL",
            "guardrails": {a.agent: a.guardrail for a in
                           [mon, triage, knowledge, planning, handover]},
        }
        if tracer:
            rec["trace_id"] = tracer.run_id
        return rec
