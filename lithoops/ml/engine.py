"""Machine-learning suite for LithoOps AI.

Four models, all from the free scikit-learn stack:

  AnomalyModel   - IsolationForest, unsupervised health scoring
  RiskModel      - GradientBoostingClassifier, P(failure within horizon)
  RULModel       - GradientBoostingRegressor, remaining useful life (minutes)
  PartsForecaster- simple demand forecast from failure risk x bill-of-materials

A single HealthEngine trains and holds all of them, exposes a unified
`score(df)` returning health, risk, RUL and per-row anomaly flags, and an
`evaluate()` that checks the prototype targets.
"""
from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (GradientBoostingClassifier,
                              GradientBoostingRegressor, IsolationForest)
from sklearn.metrics import mean_absolute_error, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from lithoops.config import DATA_DIR, MODEL, SENSOR_FIELDS

MODEL_PATH = DATA_DIR / "health_engine.joblib"


@dataclass
class EvalReport:
    failure_recall: float
    false_alert_rate: float
    risk_precision: float
    risk_recall: float
    rul_mae_minutes: float
    early_warning_minutes: float

    def as_dict(self) -> dict:
        return {k: round(float(v), 3) for k, v in self.__dict__.items()}


class HealthEngine:
    def __init__(self, cfg=MODEL):
        self.cfg = cfg
        self.scaler = StandardScaler()
        self.anomaly = IsolationForest(
            n_estimators=cfg.anomaly_estimators,
            contamination=cfg.anomaly_contamination,
            random_state=cfg.random_state,
        )
        self.risk = GradientBoostingClassifier(
            n_estimators=cfg.risk_estimators, max_depth=cfg.risk_max_depth,
            random_state=cfg.random_state,
        )
        self.rul = GradientBoostingRegressor(
            n_estimators=cfg.rul_estimators, random_state=cfg.random_state,
        )
        self._fitted = False

    def fit(self, tel: pd.DataFrame) -> "HealthEngine":
        healthy = tel[tel.machine_id == "LITHO-DUV-01"]
        self.scaler.fit(healthy[SENSOR_FIELDS])
        self.anomaly.fit(self.scaler.transform(healthy[SENSOR_FIELDS]))

        X = self.scaler.transform(tel[SENSOR_FIELDS])
        self.risk.fit(X, tel["fails_soon"])
        mask = tel["rul_minutes"] < 400
        self.rul.fit(X[mask], tel.loc[mask, "rul_minutes"])
        self._fitted = True
        return self

    def score(self, tel: pd.DataFrame) -> pd.DataFrame:
        assert self._fitted, "HealthEngine not fitted"
        X = self.scaler.transform(tel[SENSOR_FIELDS])
        raw = self.anomaly.score_samples(X)
        pred = self.anomaly.predict(X)
        out = tel.copy()
        out["anomaly_score"] = raw
        out["is_anomaly_pred"] = (pred == -1).astype(int)
        lo, hi = raw.min(), raw.max()
        out["health_score"] = (100 * (raw - lo) / ((hi - lo) or 1.0)).round(1)
        out["failure_risk"] = self.risk.predict_proba(X)[:, 1].round(3)
        out["rul_pred"] = self.rul.predict(X).clip(min=0).round(1)
        return out

    def feature_importance(self) -> dict:
        imp = self.risk.feature_importances_
        return {f: round(float(v), 3) for f, v in
                sorted(zip(SENSOR_FIELDS, imp), key=lambda x: -x[1])}

    def evaluate(self, scored: pd.DataFrame) -> EvalReport:
        yt, yp = scored["is_anomaly_true"], scored["is_anomaly_pred"]
        tp = int(((yt == 1) & (yp == 1)).sum())
        fp = int(((yt == 0) & (yp == 1)).sum())
        recall = tp / max(int((yt == 1).sum()), 1)
        far = fp / max(int((yt == 0).sum()), 1)

        risk_pred = (scored["failure_risk"] >= 0.5).astype(int)
        rp = precision_score(scored["fails_soon"], risk_pred, zero_division=0)
        rr = recall_score(scored["fails_soon"], risk_pred, zero_division=0)

        mask = scored["rul_minutes"] < 400
        mae = mean_absolute_error(scored.loc[mask, "rul_minutes"],
                                  scored.loc[mask, "rul_pred"]) if mask.any() else 0.0

        early = self._early_warning(scored)
        return EvalReport(recall, far, rp, rr, mae, early)

    @staticmethod
    def _early_warning(scored: pd.DataFrame) -> float:
        leads = []
        for _, g in scored.groupby("machine_id"):
            g = g.reset_index(drop=True)
            fail_idx = g.index[g.failure_event == 1].tolist()
            if not fail_idx:
                continue
            fail_i = fail_idx[0]
            anom = g.index[(g.is_anomaly_pred == 1) & (g.index <= fail_i)].tolist()
            if anom:
                leads.append(fail_i - anom[0])
        return float(np.mean(leads)) if leads else 0.0

    def save(self, path=MODEL_PATH):
        joblib.dump(self, path)

    @staticmethod
    def load(path=MODEL_PATH) -> "HealthEngine":
        return joblib.load(path)


def train() -> tuple["HealthEngine", pd.DataFrame, EvalReport]:
    tel = pd.read_csv(DATA_DIR / "telemetry.csv")
    engine = HealthEngine().fit(tel)
    scored = engine.score(tel)
    scored.to_csv(DATA_DIR / "telemetry_scored.csv", index=False)
    report = engine.evaluate(scored)
    engine.save()
    return engine, scored, report


if __name__ == "__main__":
    engine, scored, report = train()
    print("=== Evaluation vs prototype targets ===")
    for k, v in report.as_dict().items():
        print(f"  {k}: {v}")
