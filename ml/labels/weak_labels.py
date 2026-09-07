"""
ml/labels/weak_labels.py — Weak label generator (prototype, not ground truth).

Each label is derived from MULTIPLE independent signals; no single feature defines a label.
Confidence = satisfied_conditions / total_conditions for that class.

Leakage audit: features used for labeling vs training must be documented.
If a feature is used to directly construct a weak label, exclude it from training
or classify experiment as weak-supervision baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import math

from .label_rules import RULES

@dataclass
class WeakLabelResult:
    label: str
    label_confidence: float  # 0-1
    label_source: str  # e.g., weak_rule_v1
    label_reasons: List[str]
    # For calibration
    confidence_level: str  # high/medium/low
    scores: Dict[str, float]  # per-class satisfied ratio


def _evaluate_rules(row: Dict[str, Any]) -> Dict[str, Tuple[int, int, List[str]]]:
    """Returns per-class (satisfied, total, reasons)"""
    results = {}
    for cls, rules in RULES.items():
        satisfied = 0
        reasons = []
        for name, fn in rules:
            try:
                if fn(row):
                    satisfied += 1
                    reasons.append(name)
            except Exception:
                continue
        results[cls] = (satisfied, len(rules), reasons)
    return results


def _confidence_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


class WeakLabeler:
    def __init__(self, version: str = "weak_rule_v1"):
        self.version = version
        # For persistence, we need to enrich row with distinct_dates/span_days if not present
        # These are derived from 500m clustering (persist_clusters) — caller should provide _distinct_dates/_span_days
        # If not provided, we will use detections_7d etc. as proxy

    def label_one(self, row: Dict[str, Any]) -> WeakLabelResult:
        # Enrich row with helper fields if missing
        # Map distinct_dates from hotspot? For prototype, use detections_7d as proxy if not provided
        # But we expect caller to have added _distinct_dates/_span_days via spatial clustering
        # If not present, fallback to detections_7d based approximations
        if "_distinct_dates" not in row and "distinct_dates" not in row:
            # Approximate: distinct_dates ~ min(detections_7d, 7) // 2 +1
            row["_distinct_dates"] = min(int(row.get("detections_7d", 0) / 2) + 1, 7)
        if "_span_days" not in row and "span_days" not in row:
            row["_span_days"] = row.get("_distinct_dates", 1) * 2

        per_class = _evaluate_rules(row)
        # Compute scores
        scores = {}
        for cls, (sat, tot, _) in per_class.items():
            scores[cls] = sat / tot if tot else 0

        # Find best class with threshold
        # Require at least 3 satisfied and score >=0.5 to be considered
        best_label = "unknown"
        best_score = 0
        best_reasons: List[str] = []
        for cls, (sat, tot, reasons) in per_class.items():
            score = sat / tot if tot else 0
            # Require at least 3 conditions and score >=0.5
            if sat >= 3 and score >= 0.5 and score > best_score:
                best_label = cls
                best_score = score
                best_reasons = reasons
            elif sat >= 4 and score >= 0.4 and score > best_score:
                # Alternative for gas_flare etc. with many conditions but slightly lower threshold
                best_label = cls
                best_score = score
                best_reasons = reasons

        # If no class meets threshold, unknown with low confidence
        if best_label == "unknown":
            # Confidence based on max score but capped low
            max_score = max(scores.values()) if scores else 0
            return WeakLabelResult(
                label="unknown",
                label_confidence=round(max_score * 0.5, 3),  # low
                label_source=self.version,
                label_reasons=["insufficient_evidence"],
                confidence_level="low",
                scores={k: round(v, 3) for k, v in scores.items()},
            )

        # Confidence is score, but also calibrated by number of satisfied
        # For prototype, confidence = score
        conf = round(best_score, 3)
        level = _confidence_level(best_score)
        return WeakLabelResult(
            label=best_label,
            label_confidence=conf,
            label_source=self.version,
            label_reasons=best_reasons,
            confidence_level=level,
            scores={k: round(v, 3) for k, v in scores.items()},
        )

    def label_batch(self, rows: List[Dict[str, Any]]) -> List[WeakLabelResult]:
        return [self.label_one(dict(r)) for r in rows]

    def label_dataframe(self, df):
        """Add weak label columns to DataFrame (in-place copy)."""
        import pandas as pd

        results = self.label_batch(df.to_dict(orient="records"))
        df = df.copy()
        df["weak_label"] = [r.label for r in results]
        df["label_confidence"] = [r.label_confidence for r in results]
        df["label_source"] = [r.label_source for r in results]
        df["label_reasons"] = [",".join(r.label_reasons) for r in results]
        df["confidence_level"] = [r.confidence_level for r in results]
        return df, results
