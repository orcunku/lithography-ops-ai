"""Synthetic maintenance knowledge base for the RAG system.

IMPORTANT: every document here is INVENTED for this educational prototype from
general public domain knowledge about lithography operations. Nothing is a real
ASML document and no confidential information is used. The content is
plausible-but-fictional, sized to give semantic retrieval something realistic
to search.

Running this module writes one .md file per document into data/knowledge_docs/
and returns the list of documents (id, subsystem, title, content).
"""
from __future__ import annotations

import json
from pathlib import Path

from lithoops.config import DATA_DIR

DOCS_DIR = DATA_DIR / "knowledge_docs"

# (doc_id, subsystem, title, body)
KNOWLEDGE: list[tuple[str, str, str, str]] = [
    ("KB-OVL-01", "reticle stage", "Overlay error drift diagnosis",
     "Rising overlay error over several hours commonly indicates reticle stage "
     "calibration drift rather than a sudden fault. Begin by reviewing the stage "
     "position sensor trend and comparing left/right mark residuals. Re-run the "
     "overlay calibration sequence; if residuals persist above 3 nm, inspect the "
     "reticle stage sensor (part P-STG-04) for contamination or aging. Confirm the "
     "correction model has not saturated. Escalate to a stage specialist if drift "
     "resumes within one shift of recalibration."),
    ("KB-OVL-02", "reticle stage", "Reticle stage vibration signature analysis",
     "Elevated vibration on the reticle stage typically appears first as increased "
     "high-frequency content during acceleration phases. Capture a vibration "
     "spectrum and look for peaks near the stage resonance band. Persistent "
     "broadband vibration suggests bearing wear or a loose counterbalance; narrow "
     "peaks suggest a control-loop tuning issue. Cross-check with overlay residuals, "
     "since stage vibration frequently degrades overlay before it trips any alarm."),
    ("KB-OVL-03", "reticle stage", "Overlay calibration procedure",
     "Standard overlay recalibration: place the calibration reticle, run the mark "
     "detection routine across all field points, and let the system compute the "
     "correction grid. Verify the reported model error is within specification "
     "before releasing the tool. If the routine fails mark detection repeatedly, "
     "the illumination on the alignment sensor may be low; clean the sensor window "
     "and retry before replacing hardware."),
    ("KB-COOL-01", "cooling", "Cooling system temperature rise",
     "Temperature and focus error rising together is a classic signature of a "
     "cooling fault. The thermal expansion from inadequate cooling shifts the focal "
     "plane, so focus error tracks the temperature climb. Inspect the pump seals "
     "(part P-COOL-01), verify coolant flow rate against the nominal setpoint, and "
     "check for air entrainment in the loop. If alarms persist after flow is "
     "restored, schedule a maintenance window before the temperature reaches the "
     "interlock threshold."),
    ("KB-COOL-02", "cooling", "Coolant pump seal replacement",
     "A degraded pump seal shows as a slow decline in coolant flow and occasional "
     "pressure oscillation. To replace seal kit P-COOL-01: isolate the loop, relieve "
     "pressure, drain to the service level, and swap the seal following the torque "
     "sequence. Bleed air from the loop before returning to service and confirm flow "
     "stabilizes at setpoint. Log the coolant top-up volume for trend tracking."),
    ("KB-COOL-03", "cooling", "Focus error caused by thermal drift",
     "When focus error climbs without any optical fault, suspect thermal drift in "
     "the frame or wafer chuck. Confirm by correlating focus error against the "
     "temperature sensor: a lag of a few minutes between temperature and focus is "
     "expected. Once cooling is restored, focus error should recover within the "
     "thermal time constant. If it does not recover, escalate to optics."),
    ("KB-COOL-04", "cooling", "Coolant flow interlock troubleshooting",
     "A coolant flow interlock trip halts exposure to protect the system. First "
     "verify the flow sensor reading against a manual gauge to rule out a faulty "
     "sensor. If flow is genuinely low, check for a clogged filter, a failing pump, "
     "or a closed isolation valve. Do not bypass the interlock; restore flow and "
     "clear the alarm through the normal reset path."),
    ("KB-SRC-01", "source", "Source power degradation",
     "Sagging source power together with throughput loss points to a source module "
     "problem rather than a stage or cooling issue. Verify the power module "
     "(part P-SRC-02) output against its commanded level and inspect the collector "
     "for contamination that reduces transmitted power. A gradual decline usually "
     "means collector degradation; a sudden step suggests a module fault."),
    ("KB-SRC-02", "source", "Collector contamination cleaning",
     "Collector contamination reduces delivered source power and lowers wafer "
     "throughput because dose targets take longer to reach. Follow the collector "
     "inspection routine, and if reflectivity is below threshold, schedule the "
     "cleaning procedure. After cleaning, re-measure delivered power and update the "
     "dose calibration before resuming production."),
    ("KB-SRC-03", "source", "Source power module fault isolation",
     "To isolate a source power module fault, compare commanded versus delivered "
     "power across a range of setpoints. A consistent offset at all setpoints points "
     "to a calibration issue; instability or dropouts point to the module hardware "
     "(part P-SRC-02). Replace the module only after confirming cabling and the "
     "control signal are healthy."),
    ("KB-SRC-04", "source", "Throughput loss root-cause checklist",
     "Wafer throughput loss has several possible roots. Rank them: reduced source "
     "power (dose takes longer), stage settling delays, increased alarm-driven "
     "pauses, and wafer-handling slowdowns. Check delivered source power first since "
     "it is the most common cause, then review the alarm log for repeated brief "
     "stoppages that erode throughput without a single obvious fault."),
    ("KB-VAC-01", "vacuum", "Vacuum pressure excursion response",
     "A vacuum pressure excursion can disturb both source performance and "
     "contamination control. On a pressure rise, check for a leak at recently "
     "serviced flanges, verify pump status, and review the outgassing history if a "
     "new component was installed. Small slow rises are often outgassing; sharp "
     "rises indicate a leak or pump fault."),
    ("KB-VAC-02", "vacuum", "Vacuum pump maintenance schedule",
     "Vacuum pumps follow a preventive schedule based on run hours and observed "
     "base pressure. Track base pressure over time; a rising trend at constant load "
     "signals approaching service need. Perform the scheduled service before base "
     "pressure crosses the action limit to avoid an unplanned interruption."),
    ("KB-VAC-03", "vacuum", "Leak detection procedure",
     "For suspected vacuum leaks, isolate sections and observe the pressure rate of "
     "rise. Use the tracer-gas method around suspect flanges. Document which section "
     "shows the fastest rise. Re-torque or reseal the identified flange, then confirm "
     "base pressure returns to nominal before releasing the tool."),
    ("KB-WFR-01", "wafer handler", "Wafer handler alarm recovery",
     "A single transient wafer-handler alarm that auto-recovers is usually benign, "
     "often a sensor debounce or a marginal grip event. Review the handler log for "
     "repetition. Isolated events need no action beyond logging; repeated events in "
     "the same position indicate a mechanical or sensor problem needing inspection."),
    ("KB-WFR-02", "wafer handler", "Wafer chuck contamination",
     "Chuck contamination causes clamping errors and can manifest as focus or "
     "overlay noise. Inspect the chuck surface, run the cleaning routine, and verify "
     "flatness after cleaning. Persistent clamping errors after cleaning suggest a "
     "worn chuck or a vacuum-clamp leak."),
    ("KB-WFR-03", "wafer handler", "Robot handoff timing errors",
     "Handoff timing errors between the wafer robot and the chuck slow throughput "
     "and can trigger alarms. Check the handoff position calibration and the grip "
     "confirmation sensor. Small timing drifts are usually recalibrated in software; "
     "repeated grip failures point to worn end-effector pads."),
    ("KB-ALM-01", "general", "Alarm flood triage",
     "During an alarm flood, group alarms by subsystem and timestamp rather than "
     "reacting to each individually. The earliest alarm in a cluster is usually the "
     "root cause and later alarms are consequences. Silence non-safety nuisance "
     "alarms only after the root cause is identified, never before."),
    ("KB-ALM-02", "general", "Alarm count trend interpretation",
     "A rising alarm-count trend, even below the alert threshold, is an early "
     "warning that a subsystem is degrading. Correlate the alarm-count rise with "
     "sensor trends: alarms rising alongside temperature suggest cooling; alongside "
     "overlay suggest the stage. Use the trend to schedule proactive inspection."),
    ("KB-PM-01", "general", "Preventive maintenance planning",
     "Preventive maintenance scheduling balances time-since-maintenance against "
     "observed health indicators. A tool well past its nominal interval with a "
     "declining health score should be prioritized. Confirm required parts are in "
     "stock and a qualified specialist is available before opening a maintenance "
     "window to avoid extended downtime."),
    ("KB-PM-02", "general", "Time-since-maintenance risk factors",
     "As time since maintenance grows, the probability of drift-related faults "
     "increases, particularly on the reticle stage and cooling loop. Treat a high "
     "time-since-maintenance value combined with any anomalous sensor trend as an "
     "elevated-risk condition warranting earlier intervention."),
    ("KB-HND-01", "general", "Shift handover best practices",
     "An effective shift handover separates verified facts from suggested actions. "
     "State each open issue, the supporting evidence, the owner, and the current "
     "status. Avoid mixing speculation with confirmed observations so the incoming "
     "shift can act on facts and evaluate suggestions independently."),
    ("KB-HND-02", "general", "Escalation criteria",
     "Escalate when a required specialist is unavailable, a needed part is out of "
     "stock with a long lead time, or a health score continues to decline after "
     "corrective action. Escalation should include the evidence gathered so the next "
     "tier does not repeat the investigation from scratch."),
    ("KB-FOC-01", "cooling", "Focus error versus overlay error differentiation",
     "Focus error and overlay error have different root causes and should not be "
     "confused. Focus error most often tracks thermal and optical issues, while "
     "overlay error tracks stage and alignment issues. When both rise together, "
     "thermal drift affecting both the focal plane and stage positioning is a common "
     "shared cause worth checking first."),
    ("KB-THR-01", "source", "Wafer throughput baseline and deviation",
     "Establish a wafer-throughput baseline per tool and product. A sustained "
     "deviation below baseline, once wafer mix is accounted for, indicates a "
     "developing problem. Pair throughput deviation with source power and alarm "
     "trends to distinguish a source issue from a handling or stage issue."),
    ("KB-VIB-01", "reticle stage", "Vibration threshold and early warning",
     "Vibration rising steadily toward its threshold is a reliable early-warning "
     "indicator for stage mechanical wear. Trend the vibration RMS; a monotonic rise "
     "over multiple shifts warrants inspection before the threshold trips, creating "
     "time to plan rather than react."),
    ("KB-DRIFT-01", "general", "Slow sensor drift detection",
     "Slow sensor drift is dangerous precisely because it stays below alarm limits "
     "until it suddenly does not. Anomaly detection on combinations of sensors "
     "catches drift earlier than single-sensor thresholds. When an anomaly model "
     "flags drift, review the contributing sensors to localize the subsystem."),
    ("KB-INC-01", "general", "Incident prioritization framework",
     "Prioritize incidents by severity and by remaining useful life. A high-severity "
     "incident on a machine with low remaining useful life demands immediate "
     "attention; a low-severity transient that auto-recovered can be logged and "
     "monitored. Always attach the supporting sensor evidence to the incident "
     "record so prioritization is traceable."),
    ("KB-RUL-01", "general", "Remaining useful life interpretation",
     "A short predicted remaining useful life means intervention should be planned "
     "now, while a long value supports normal operation. Treat remaining useful life "
     "as a planning aid alongside the health score and failure risk, not as a "
     "guarantee. Confirm the prediction against the underlying sensor trends before "
     "acting on it."),
]


def write_docs() -> list[dict]:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for doc_id, subsystem, title, body in KNOWLEDGE:
        text = f"# {title}\n\nSubsystem: {subsystem}\nDocument ID: {doc_id}\n\n{body}\n"
        (DOCS_DIR / f"{doc_id}.md").write_text(text, encoding="utf-8")
        records.append({"doc_id": doc_id, "subsystem": subsystem,
                        "title": title, "content": body})
    (DATA_DIR / "knowledge_base.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8")
    return records


if __name__ == "__main__":
    recs = write_docs()
    print(f"Wrote {len(recs)} synthetic knowledge documents to {DOCS_DIR}")
    subs = {}
    for r in recs:
        subs[r["subsystem"]] = subs.get(r["subsystem"], 0) + 1
    print("By subsystem:", subs)
