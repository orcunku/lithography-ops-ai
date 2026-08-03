# Stage B — Grounded LLM Report Writer

Stage A retrieved the right documents. Stage B adds a **small, free, local LLM**
that reads the retrieved documents **plus the machine's sensor/ML evidence** and
writes a fluent, cited **shift-handover report**.

## The core safety principle
The LLM is a **writer, not a decider**. It is given only the facts (from the ML
models and agents) and the semantically-retrieved procedures, and is instructed
to **cite sources and never invent numbers**. Every value in the report traces
back to a sensor or model; every recommendation to a cited document. This is how
you get fluent output without hallucination — and it's the thing to emphasise in
an interview.

## Two ways to run it

### Option 1 — Google Colab (recommended on low-RAM machines)
Upload `notebooks/StageB_LLM_grounded_report.ipynb` to
https://colab.research.google.com and run top to bottom. It builds the retriever,
loads `google/flan-t5-base` (free, no key), and generates grounded reports for
two example machines.

### Option 2 — Locally
```bat
python -m pip install transformers torch
```
Then in code:
```python
from lithoops.agents.team import CoordinatorAgent
from lithoops.rag.report import write_report
rec = CoordinatorAgent().run("LITHO-EUV-03")
print(write_report(rec)["report"])   # uses LLM if available, else template
```
If `transformers` isn't installed (or on very low RAM), `write_report` falls
back to a clean deterministic template automatically — the project always
produces a cited report either way.

## Model choice
`google/flan-t5-base` is tiny, instruction-tuned, free, ungated, and runs on
Colab's free CPU in seconds. The notebook includes an optional upgrade to
`flan-t5-large` if a free GPU is available.

## Next stages
- **Stage C:** evaluation — did retrieval fetch the right doc? did the report
  stay grounded to the facts?
- **Stage D:** observability — end-to-end tracing of every run.
