# Stage D — Observability / Tracing

Stages A-C built and evaluated the intelligence. Stage D makes every run
**observable**: a lightweight tracer records each step as a timed, nested span,
so a finished run is a full, replayable record of what happened.

## What gets traced
For each recommendation:
- the coordinator span (total run)
- one span per agent (Monitoring, Incident Triage, Knowledge, Planning, Shift Handover)
- attributes such as the suspected subsystem, retrieval mode (semantic vs keyword),
  and how many documents were retrieved
- the duration of every step in milliseconds

Traces are saved to a `traces` table in SQLite, alongside the audit trail, so they
are queryable and auditable. No external observability service is required — the
design mirrors OpenTelemetry-style spans with zero dependencies.

## How to see it
- **Dashboard:** the "Traces" tab shows a timeline bar chart of the most recent
  runs (which step took how long).
- **API:** `GET /traces` lists runs; `GET /traces/{run_id}` returns the full trace.
- **Code:**
  ```python
  from lithoops.agents.team import CoordinatorAgent
  from lithoops.obs.tracer import Tracer
  tracer = Tracer()
  rec = CoordinatorAgent().run("LITHO-EUV-03", tracer=tracer)
  tracer.save()
  print(tracer.summary())
  ```

## Design note
Tracing is **optional and backward-compatible**: the coordinator runs exactly as
before when no tracer is passed. This is the same pattern real systems use —
instrumentation that can be turned on without changing behaviour.

## For your interview
> "Every run is traced end to end — I can show which agent fired, whether it used
> semantic or keyword retrieval, how many docs it pulled, and the timing of each
> step, all persisted next to the audit trail."
