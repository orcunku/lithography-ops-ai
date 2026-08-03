# Stage C — Evaluating the RAG System

Stages A & B built retrieval and generation. Stage C **measures** them, turning
"it looks right" into defensible numbers.

## What is measured

### Retrieval quality (against a labelled test set)
A hand-labelled set of operator-style queries, each paired with the document(s)
that should be retrieved. Metrics:
- **Hit@1** — fraction where the top result is correct
- **Hit@3** — fraction where a correct result is in the top 3
- **MRR** (mean reciprocal rank) — rewards ranking the right answer near the top

Queries use plain language (not the document wording), so this tests genuine
*semantic* retrieval, not keyword overlap.

### Groundedness (for generated reports)
A lightweight, judge-model-free check that flags the two hallucination modes that
matter: **fabricated citations** (a cited doc that was never retrieved) and
**invented numbers** (a value in the report not present in the supplied facts).

## Run it

### Colab (recommended)
Upload `notebooks/StageC_RAG_evaluation.ipynb` and run top to bottom. It prints
the metric summary plus a per-query breakdown.

### Locally
```bat
python -m pip install -r requirements-rag.txt
python -m lithoops.rag.knowledge_base
python -m lithoops.rag.engine build
python -m lithoops.rag.evaluate
```

## For your interview
> "I evaluated retrieval on a labelled test set and measured Hit@3 and MRR, and I
> added a groundedness check that flags fabricated citations or invented numbers
> in generated reports — so the RAG system is not just built, it's measured."

## Next
- **Stage D:** observability — end-to-end tracing of every run.
