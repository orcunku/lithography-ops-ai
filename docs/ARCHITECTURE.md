# Architecture

LithoOps AI is layered so each concern is independent and testable.

```
                         ┌──────────────────────────────────────────┐
                         │              INTERFACES                   │
                         │  Streamlit dashboard   FastAPI service    │
                         │  MCP server (stdio, official SDK)         │
                         └───────────────┬──────────────────────────┘
                                         │
                         ┌───────────────▼──────────────────────────┐
                         │            AGENT TEAM                      │
                         │  Monitoring → Triage → Knowledge →         │
                         │  Planning → Shift Handover → Coordinator   │
                         │  (each: guardrail + structured evidence)   │
                         └───────────────┬──────────────────────────┘
                                         │  reads ONLY through
                         ┌───────────────▼──────────────────────────┐
                         │        READ-ONLY TOOL REGISTRY            │
                         │  get_telemetry · get_incidents ·          │
                         │  search_knowledge · get_inventory ·       │
                         │  get_engineers   (single source of truth) │
                         └───────┬───────────────────────┬──────────┘
                                 │                        │
                   ┌─────────────▼────────┐   ┌───────────▼───────────┐
                   │      ML ENGINE        │   │      PERSISTENCE      │
                   │  IsolationForest      │   │  SQLite: reference    │
                   │  (anomaly/health)     │   │  data, recommendations│
                   │  GBClassifier (risk)  │   │  + append-only        │
                   │  GBRegressor  (RUL)   │   │  AUDIT TRAIL          │
                   │  parts forecaster     │   └───────────────────────┘
                   └───────────────────────┘
                                 ▲
                   ┌─────────────┴────────┐
                   │   SYNTHETIC DATA      │
                   │  3 machines, labelled │
                   │  anomaly/fail/RUL     │
                   └───────────────────────┘
```

## Key design decisions

**One read-only registry.** Every agent, the API, and the MCP server all reach
data through the same five functions in `lithoops/mcp/registry.py`. Nothing
writes through them. This is the security and testability guardrail.

**Human-in-the-loop is enforced, not suggested.** The coordinator only ever
produces `AWAITING_HUMAN_APPROVAL`. Approval/rejection happens via the API or
dashboard and is written to an append-only `audit_log` table.

**ML is honest about labels.** Synthetic data carries ground-truth labels for
all three learning tasks, so evaluation numbers are real measurements.

**Transparent agents.** Agents are rule + ML based (no LLM required), so the
prototype runs anywhere and every recommendation is explainable.

## Request lifecycle (a recommendation)

1. `POST /machine/{id}/recommend` → CoordinatorAgent.run(id)
2. Monitoring reads last 60 telemetry rows via the registry.
3. Triage ranks urgency and names the suspected subsystem (with signals).
4. Knowledge retrieves the matching procedure and cites its doc id.
5. Planning checks parts + available specialists via the registry.
6. Shift Handover splits verified facts from suggestions.
7. Coordinator assembles everything, status `AWAITING_HUMAN_APPROVAL`,
   persists it and logs `created`.
8. A human approves/rejects → status update + audit entry.
