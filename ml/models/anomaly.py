"""
ml/models/anomaly.py — Facility anomaly scoring.

Purely deterministic; no future leakage.
"""

from __future__ import annotations

from typing import Optional

from ml.features.engineering import FeatureVector


class AnomalyCalculator:
    """Computes anomaly evidence from historical baseline vs current activity."""

    @staticmethod
    def compute(fv: FeatureVector) -> dict:
        baseline = fv.facility_baseline
        current = fv.current_activity
        anomaly = fv.activity_anomaly
        ratio = fv.anomaly_ratio

        if baseline is None or current is None:
            return {"anomaly": None, "ratio": None, "increase_pct": None, "level": "unknown"}

        if baseline == 0:
            # Fresh facility or no history
            level = "high" if current and current > 3 else "moderate" if current else "unknown"
            return {"anomaly": anomaly, "ratio": ratio, "increase_pct": None, "level": level}

        increase_pct = anomaly * 100 if anomaly is not None else 0
        if anomaly is None:
            level = "unknown"
        elif anomaly >= 5:
            level = "critical"
        elif anomaly >= 2:
            level = "high"
        elif anomaly >= 0.5:
            level = "moderate"
        elif anomaly >= 0:
            level = "low"
        else:
            level = "low"

        return {"anomaly": anomaly, "ratio": ratio, "increase_pct": increase_pct, "level": level}

    @staticmethod
    def compute_from_values(baseline: Optional[float], current: Optional[float]) -> tuple[Optional[float], Optional[float]]:
        if baseline is None or current is None:
            return None, None
        if baseline == 0:
            return (float(current) if current else 0.0), None
        return (current - baseline) / baseline, current / baseline
