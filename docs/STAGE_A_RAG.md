# Stage A — Semantic RAG (Retrieval-Augmented Generation)

This stage upgrades the **Knowledge agent** from exact-keyword lookup to true
**semantic retrieval**: it finds the right maintenance document by *meaning*, so
plain-language symptoms ("machine getting hot and blurry") retrieve the correct
technical procedure.

**Free tools, no API keys:** `sentence-transformers` (local embedding model) +
`FAISS` (local vector store). All 29 maintenance documents are **synthetic** —
invented for this educational prototype, not real ASML data.

## Two ways to run it

### Option 1 — Google Colab (recommended on low-RAM machines)
1. Go to https://colab.research.google.com
2. File → Upload notebook → choose `notebooks/StageA_RAG_semantic_search.ipynb`
3. Run the cells top to bottom (Shift+Enter). No install needed on your machine.

### Option 2 — Locally (needs ~1 GB free + internet for first download)
```bat
python -m pip install -r requirements-rag.txt
python -m lithoops.rag.knowledge_base      :: writes the 29 synthetic docs
python -m lithoops.rag.engine build        :: builds the FAISS index
python -m lithoops.rag.engine query "temperature rising and focus error"
```
Once the index exists, the Knowledge agent (and the dashboard/API) automatically
switch from keyword search to semantic RAG. If the index is absent or the deps
aren't installed, everything falls back to keyword search — the project always
runs either way.

## How it connects to the agents
The Coordinator sends the detected symptoms (from the Monitoring agent's top
signals) to the Knowledge agent, which retrieves the most relevant procedures
and cites them by document id — keeping the "must cite the source" guardrail.

## Next stages
- **Stage B:** a small free LLM (on Colab) reads the retrieved docs + sensor
  evidence and writes a grounded, cited shift-handover report.
- **Stage C:** evaluation (retrieval hit-rate, groundedness).
- **Stage D:** observability / end-to-end run tracing.
