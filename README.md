# Lithography Ops AI — EUV/DUV Operations Intelligence
## 🔗 Links

- 🌐 **Live landing page:** https://orcunku.github.io/lithography-ops-ai/
- 📊 **Live dashboard demo:** _coming soon_
- 📄 **Project report (PDF):** [docs/LithoOps_AI_Explanation_Report.pdf](docs/LithoOps_AI_Explanation_Report.pdf)

A portfolio-grade prototype that detects equipment anomalies, triages incidents,
retrieves maintenance knowledge, forecasts resource needs, and produces
shift-handover reports for a simulated lithography fleet.

**Multi-agent · machine-learning · MCP · FastAPI · human-in-the-loop.**
Synthetic data only. Every operational action requires human approval.
Independent educational project — not affiliated with, endorsed by, or based on
confidential information from ASML.

Measured results (checked in tests): anomaly recall ≈ 93 % (target ≥ 80 %),
false-alert rate ≈ 8 % (target < 10 %), RUL error ≈ 2.5 min.

---

## Setup on Windows (step by step, no experience needed)

Open **PowerShell** or **Command Prompt** in this folder, then:

```bat
:: 1. create an isolated environment (a private toolbox for this project)
python -m venv .venv

:: 2. turn it on  (you should then see (.venv) at the start of your line)
::    Command Prompt (cmd):
.venv\Scripts\activate.bat
::    PowerShell:
::    .venv\Scripts\Activate.ps1

:: 3. install everything (a few minutes; lots of scrolling text is normal)
python -m pip install -r requirements.txt

:: 4. build it: generate data + train the AI (a few seconds)
python scripts\build.py
```

Success = you see two `PASS` lines under "Prototype targets".

> Note: `scripts\build.py` and `scripts\dashboard.py` already add this folder to
> Python's path, so you do NOT need to set PYTHONPATH for them.

### Run any of the three interfaces

```bat
:: A) the visual dashboard -> opens in your browser
streamlit run scripts\dashboard.py

:: B) the REST API -> interactive docs at http://localhost:8000/docs
uvicorn lithoops.api.app:api --reload

:: C) the MCP server -> for AI clients like Claude Desktop
python -m lithoops.mcp.server
```

### Run the tests

```bat
python -m pytest -q
```

---

## macOS / Linux setup

Same as above, but activate with `source .venv/bin/activate` and use forward
slashes (`scripts/build.py`).

---

## Project layout

```
lithography-ops-ai/
├── lithoops/                 # the Python package (code lives here)
│   ├── config.py             # all settings, targets, hyperparameters
│   ├── data.py               # synthetic data generator (+ ML labels)
│   ├── business.py           # business-value calculator
│   ├── db/store.py           # SQLite + audit trail
│   ├── ml/engine.py          # 3 models + evaluation + persistence
│   ├── ml/forecast.py        # spare-parts demand forecast
│   ├── agents/team.py        # 6 agents + coordinator
│   ├── agents/subsystems.py  # shared signal→subsystem logic
│   ├── mcp/registry.py       # read-only tool registry (source of truth)
│   ├── mcp/server.py         # official-SDK MCP server
│   └── api/app.py            # FastAPI service
├── scripts/build.py          # one-command build
├── scripts/dashboard.py      # Streamlit dashboard
├── tests/test_lithoops.py    # full test suite
├── docs/ARCHITECTURE.md      # design + diagram
├── pyproject.toml            # installable package
└── requirements.txt
```

## The agent team

| Agent | Job | Guardrail |
|---|---|---|
| Monitoring | health, anomalies, risk, RUL, top signals | read-only, cannot change settings |
| Incident Triage | rank urgency, name subsystem | must show supporting signals |
| Knowledge | retrieve repair procedures | must cite source document |
| Planning | check parts + specialists | approved read-only tools only |
| Shift Handover | summarize open issues | separate facts from suggestions |
| Coordinator | assemble recommendation | requires human approval |

## Safety & honesty

- **Read-only** access everywhere; nothing controls a machine.
- **Human approval** required for 100 % of operational actions, via the audit trail.
- **Synthetic data** only; the business calculator is labelled hypothetical.

See `docs/ARCHITECTURE.md` for the full design and request lifecycle.
