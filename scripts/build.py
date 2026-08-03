"""One-command build: generate data, train models, print a status report.

Usage:  python scripts/build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project importable even without setting PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lithoops.config import TARGETS
from lithoops.data import generate_all
from lithoops.ml.engine import train


def main() -> int:
    print("[1/2] Generating synthetic data + loading database ...")
    tel = generate_all()
    print(f"      {len(tel)} telemetry rows, {tel.machine_id.nunique()} machines.")

    print("[2/2] Training ML suite (anomaly, risk, RUL) ...")
    _, _, report = train()
    r = report.as_dict()

    print("\n=== Prototype targets ===")
    checks = [
        ("failure_recall", r["failure_recall"], TARGETS.failure_recall, ">="),
        ("false_alert_rate", r["false_alert_rate"], TARGETS.false_alert_rate, "<"),
    ]
    ok = True
    for name, got, target, op in checks:
        passed = got >= target if op == ">=" else got < target
        ok &= passed
        print(f"  {'PASS' if passed else 'FAIL'}  {name}={got} ({op} {target})")
    print(f"  info  risk_precision={r['risk_precision']} risk_recall={r['risk_recall']} "
          f"rul_mae={r['rul_mae_minutes']}min")

    print("\nBuild complete." if ok else "\nBuild complete (some targets missed).")
    print("Next:  uvicorn lithoops.api.app:api --reload    # API")
    print("       streamlit run scripts/dashboard.py       # dashboard")
    print("       python -m lithoops.mcp.server            # MCP server")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
