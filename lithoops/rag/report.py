"""Grounded report writer (Stage B).

Turns the Coordinator's structured recommendation into a fluent shift-handover
report. Two modes:

  * LLM mode  - if `transformers` is installed and a small model is available,
                a local flan-t5 model phrases the report. The model is given
                ONLY the facts + retrieved documents and told not to invent
                numbers (grounded generation, no hallucinated values).
  * Template  - otherwise a clean deterministic template is used, so the
                project always produces a report even without the heavy deps.

This mirrors the Stage B Colab notebook. On low-RAM machines, prefer the
notebook; locally this falls back to the template automatically.
"""
from __future__ import annotations


def _facts_block(rec: dict) -> str:
    mon, tri, plan = rec["monitoring"], rec["triage"], rec["planning"]
    sig = ", ".join(f"{n} (deviation {v})" for n, v in mon.get("top_signals", []))
    parts = "; ".join(
        f"{p['name']} ({p['part_id']}) {'in stock' if p['in_stock'] else 'OUT OF STOCK'}"
        for p in plan.get("parts", [])) or "no parts flagged"
    docs = " ".join(f"[{d['doc_id']}] {d.get('content','')}"
                    for d in rec["knowledge"].get("docs", []))
    return (
        f"- Machine {rec['machine_id']} health {mon.get('health')}/100, "
        f"failure risk {mon.get('failure_risk')}, RUL about {mon.get('rul_minutes')} minutes.\n"
        f"- Urgency {tri.get('urgency')}; suspected subsystem {tri.get('suspected_subsystem')}.\n"
        f"- Abnormal signals: {sig}.\n"
        f"- Parts: {parts}.\n"
        f"REFERENCE TEXT: {docs}"
    )


def build_prompt(rec: dict) -> str:
    return (
        "You are writing a concise shift-handover note for a lithography machine.\n"
        "Use ONLY the facts and reference text provided. Do not invent numbers.\n"
        "Cite the reference document id in brackets when you give guidance.\n\n"
        f"FACTS:\n{_facts_block(rec)}\n\n"
        "Write 3 to 4 sentences: state the situation, the likely cause with a "
        "citation, and the recommended next step."
    )


def template_report(rec: dict) -> str:
    mon, tri = rec["monitoring"], rec["triage"]
    cited = ", ".join(d["doc_id"] for d in rec["knowledge"].get("docs", [])) or "none"
    lines = [
        f"{rec['machine_id']} is at health {mon.get('health')}/100 with failure "
        f"risk {mon.get('failure_risk')} and about {mon.get('rul_minutes')} minutes "
        f"of remaining useful life (urgency: {tri.get('urgency')}).",
        f"The evidence points to the {tri.get('suspected_subsystem')} subsystem; "
        f"see cited procedure(s): {cited}.",
    ]
    for s in rec["handover"].get("suggestions", []):
        lines.append(f"Recommended: {s}")
    lines.append("This recommendation is read-only and requires human approval.")
    return " ".join(lines)


def write_report(rec: dict, use_llm: bool = True) -> dict:
    """Return {'report': str, 'mode': 'llm'|'template', 'citations': [...]}."""
    citations = [d["doc_id"] for d in rec["knowledge"].get("docs", [])]
    if use_llm:
        try:
            from transformers import pipeline
            llm = pipeline("text2text-generation", model="google/flan-t5-base")
            text = llm(build_prompt(rec), max_new_tokens=220,
                       do_sample=False)[0]["generated_text"].strip()
            return {"report": text, "mode": "llm", "citations": citations}
        except Exception:
            pass  # fall back cleanly
    return {"report": template_report(rec), "mode": "template", "citations": citations}
