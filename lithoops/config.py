"""Central configuration for LithoOps AI.

Keeping paths, model hyperparameters and prototype targets in one typed place
makes the system reproducible and easy to tune. Everything downstream imports
from here rather than hard-coding constants.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "lithoops.db"

# Simulated fleet
MACHINES = {
    "LITHO-DUV-01": "DUV",   # healthy baseline
    "LITHO-EUV-02": "EUV",   # gradual drift
    "LITHO-EUV-03": "EUV",   # approaching maintenance event
}

# Sensor fields (from the project summary)
SENSOR_FIELDS = [
    "vacuum_pressure", "source_power", "temperature", "vibration",
    "overlay_error", "focus_error", "wafer_throughput",
    "alarm_count", "time_since_maintenance",
]

# Healthy baseline (mean, std) per sensor
BASELINE = {
    "vacuum_pressure":  (5.0e-4, 2.0e-5),
    "source_power":     (250.0, 3.0),
    "temperature":      (22.0, 0.3),
    "vibration":        (0.15, 0.02),
    "overlay_error":    (1.2, 0.15),
    "focus_error":      (2.0, 0.25),
    "wafer_throughput": (160.0, 4.0),
    "alarm_count":      (0.2, 0.5),
}

SEED = 42
MINUTES_PER_MACHINE = 720  # 12h of per-minute telemetry


@dataclass(frozen=True)
class ModelConfig:
    anomaly_contamination: float = 0.03
    anomaly_estimators: int = 200
    risk_estimators: int = 150
    risk_max_depth: int = 4
    rul_estimators: int = 150
    random_state: int = SEED


@dataclass(frozen=True)
class Targets:
    """Prototype success targets from the project summary."""
    early_warning_minutes: int = 30
    failure_recall: float = 0.80
    false_alert_rate: float = 0.10
    triage_speedup: float = 0.50
    evidence_coverage: float = 1.00
    human_approval: float = 1.00


MODEL = ModelConfig()
TARGETS = Targets()


@dataclass(frozen=True)
class BusinessDefaults:
    value_per_equipment_hour: float = 12000.0   # hypothetical EUR/h, adjustable
    downtime_hours_per_incident: float = 6.0
    operating_cost_annual: float = 150000.0


BUSINESS = BusinessDefaults()
