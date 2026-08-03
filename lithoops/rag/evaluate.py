"""Stage C — evaluation of the RAG system.

Turns "it looks right" into measured numbers. Two things are evaluated:

1. RETRIEVAL QUALITY (does semantic search fetch the correct document?)
   - Hit@k       : fraction of queries where a correct doc appears in the top k
   - MRR         : mean reciprocal rank of the first correct doc (rewards putting
                   the right answer near the top)
   These use a hand-labelled test set: operator-style queries paired with the
   document id(s) that SHOULD be retrieved.

2. GROUNDEDNESS (does a generated report stick to its evidence?)
   - a lightweight, LLM-free check: every cited doc id in the report must be one
     that was actually retrieved, and the report must not contain numbers that
     were not in the supplied facts. This catches the two failure modes that
     matter -- fabricated citations and invented values -- without needing a
     judge model.

Run:  python -m lithoops.rag.evaluate      (retrieval eval; needs a built index)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Labelled retrieval test set: (query, set-of-acceptable-correct-doc-ids).
# Queries are deliberately in plain operator language, not the document wording,
# so this tests SEMANTIC retrieval rather than keyword overlap.
TEST_SET: list[tuple[str, set[str]]] = [
    ("the machine is getting hot and the image is blurry",
     {"KB-COOL-01", "KB-COOL-03", "KB-FOC-01"}),
    ("wafers are coming out slower than usual",
     {"KB-SRC-04", "KB-THR-01", "KB-SRC-01"}),
    ("how do I hand over open issues to the next shift",
     {"KB-HND-01"}),
    ("the alignment is slowly getting worse over the day",
     {"KB-OVL-01", "KB-OVL-03", "KB-FOC-01"}),
    ("coolant is not flowing and exposure stopped",
     {"KB-COOL-04", "KB-COOL-02"}),
    ("the light source seems weaker than before",
     {"KB-SRC-01", "KB-SRC-02", "KB-SRC-03"}),
    ("too many alarms going off at once",
     {"KB-ALM-01", "KB-ALM-02"}),
    ("the stage is shaking during moves",
     {"KB-OVL-02", "KB-VIB-01"}),
    ("pressure in the vacuum chamber is climbing",
     {"KB-VAC-01", "KB-VAC-02", "KB-VAC-03"}),
    ("the robot keeps dropping or mis-handling wafers",
     {"KB-WFR-01", "KB-WFR-03", "KB-WFR-02"}),
    ("when should we do preventive maintenance",
     {"KB-PM-01", "KB-PM-02"}),
    ("how long until this machine fails",
     {"KB-RUL-01", "KB-DRIFT-01"}),
]


@dataclass
class RetrievalReport:
    n_queries: int
    hit_at_1: float
    hit_at_3: float
    mrr: float

    def as_dict(self) -> dict:
        return {"n_queries": self.n_queries,
                "hit_at_1": round(self.hit_at_1, 3),
                "hit_at_3": round(self.hit_at_3, 3),
                "mrr": round(self.mrr, 3)}


def evaluate_retrieval(retriever, k: int = 3) -> RetrievalReport:
    """retriever must have .search(query, k) -> list of dicts with 'doc_id'."""
    hits1 = hits3 = 0
    rr_sum = 0.0
    for query, correct in TEST_SET:
        results = retriever.search(query, k=k)
        ids = [r["doc_id"] for r in results]
        if ids and ids[0] in correct:
            hits1 += 1
        if any(i in correct for i in ids):
            hits3 += 1
        # reciprocal rank of first correct hit
        rr = 0.0
        for rank, i in enumerate(ids, start=1):
            if i in correct:
                rr = 1.0 / rank
                break
        rr_sum += rr
    n = len(TEST_SET)
    return RetrievalReport(n, hits1 / n, hits3 / n, rr_sum / n)


# ----------------------------------------------------------- groundedness
_NUM = re.compile(r"\d+\.?\d*")


def evaluate_groundedness(report_text: str, allowed_numbers: set[str],
                          retrieved_ids: set[str], cited_ids: set[str]) -> dict:
    """LLM-free groundedness checks.

    - fabricated_citation: a cited doc id that was never retrieved.
    - invented_number: a number in the report that was not among the facts.
      (Common safe tokens like the health scale are whitelisted by the caller
      via allowed_numbers.)
    """
    fabricated = sorted(cited_ids - retrieved_ids)
    # strip document-id codes (e.g. KB-COOL-01) before scanning for numbers, so
    # digits inside citation codes aren't mistaken for invented values.
    cleaned = re.sub(r"KB-[A-Z]+-\d+", " ", report_text)
    nums_in_report = set(_NUM.findall(cleaned))
    invented = sorted(nums_in_report - allowed_numbers)
    return {
        "grounded": not fabricated and not invented,
        "fabricated_citations": fabricated,
        "invented_numbers": invented,
    }


if __name__ == "__main__":
    from lithoops.rag.engine import Retriever, index_exists
    if not index_exists():
        print("No RAG index found. Build it first:")
        print("  python -m lithoops.rag.engine build")
        raise SystemExit(1)
    report = evaluate_retrieval(Retriever(), k=3)
    print("=== RAG retrieval evaluation ===")
    for key, val in report.as_dict().items():
        print(f"  {key}: {val}")
