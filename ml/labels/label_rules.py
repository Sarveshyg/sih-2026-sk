"""
ml/labels/label_rules.py — Weak label rules (v1) for 6 classes.

Each rule set requires MULTIPLE independent signals; no single feature defines a label.
Thresholds derived from India EDA (6523 detections, 2026-08-01 to 2026-08-30):
  FRP p75=3.88, p95=9.02, p99=17.25, max 239
  BT mean 318, p95 343
  Persistence mean 0.34, max 1.0
  Detections 7d mean 3.33, max 37

Rules are intentionally conservative to avoid circular leakage.
If a feature is used to construct a weak label, that experiment must be documented
as weak-supervision baseline, not independent ML evaluation.
"""

from typing import Dict, Any, List

# Thresholds (conservative, based on EDA)
FRP_HIGH = 7.0
FRP_MODERATE_LOW = 1.0
FRP_MODERATE_HIGH = 15.0
FRP_VERY_HIGH = 20.0
BT_HIGH = 330.0
BT_VERY_HIGH = 340.0
BT_MODERATE = 310.0
PERSIST_HIGH = 0.6
PERSIST_VERY_HIGH = 0.7
PERSIST_LOW = 0.3

# Rule definitions: each class has list of (condition_name, lambda)
# Confidence = satisfied / total
RULES = {
    "persistent_industrial_thermal_source": [
        ("detections_7d>=5", lambda r: r.get("detections_7d", 0) >= 5),
        ("persistence>=0.6", lambda r: (r.get("persistence", 0) or 0) >= 0.6),
        ("hotspot_cluster_size>=5", lambda r: (r.get("hotspot_cluster_size", 0) or 0) >= 5),
        ("distinct_dates>=3", lambda r: r.get("_distinct_dates", r.get("distinct_dates", 0)) >= 3),
        ("span_days>=5", lambda r: r.get("_span_days", r.get("span_days", 0)) >= 5),
        ("frp_moderate", lambda r: 1.0 <= r.get("frp", 0) <= 15.0),
        ("bt_moderate", lambda r: 310 <= r.get("brightness_temperature", 0) <= 350),
    ],
    "industrial_fire": [
        ("frp_high", lambda r: r.get("frp", 0) >= 7.0),
        ("bt_high", lambda r: r.get("brightness_temperature", 0) >= 330),
        ("detections_24h>=2", lambda r: r.get("detections_24h", 0) >= 2),
        ("hotspot_cluster_size_3_15", lambda r: 3 <= (r.get("hotspot_cluster_size", 0) or 0) <= 15),
        ("anomaly_high", lambda r: (r.get("facility_anomaly", 0) or r.get("activity_anomaly", 0) or 0) > 1.0),
        ("persistence_mid", lambda r: 0.3 <= (r.get("persistence", 0) or 0) <= 0.8),
    ],
    "gas_flare": [
        ("persistence_very_high", lambda r: (r.get("persistence", 0) or 0) >= 0.7),
        ("detections_30d>=10", lambda r: r.get("detections_30d", 0) >= 10),
        ("hotspot_small", lambda r: 1 <= (r.get("hotspot_cluster_size", 0) or 0) <= 5),
        ("distinct_dates>=5", lambda r: r.get("_distinct_dates", r.get("distinct_dates", 0)) >= 5),
        ("span_days>=10", lambda r: r.get("_span_days", r.get("span_days", 0)) >= 10),
        ("frp_moderate", lambda r: 3.0 <= r.get("frp", 0) <= 15.0),
        ("bt_moderate", lambda r: 320 <= r.get("brightness_temperature", 0) <= 350),
    ],
    "wildfire": [
        ("hotspot_large", lambda r: (r.get("hotspot_cluster_size", 0) or 0) > 10),
        ("frp_high", lambda r: r.get("frp", 0) >= 10),
        ("bt_high", lambda r: r.get("brightness_temperature", 0) >= 340),
        ("persistence_mid_low", lambda r: 0.2 <= (r.get("persistence", 0) or 0) <= 0.6),
        ("distinct_dates_short", lambda r: 1 <= r.get("_distinct_dates", r.get("distinct_dates", 0)) <= 2),
        ("burst_ratio", lambda r: r.get("detections_7d", 0) > 0 and r.get("detections_30d", 0) > 0 and r.get("detections_7d", 0) / max(1, r.get("detections_30d", 0)) > 0.5),
    ],
    "agricultural_fire": [
        ("persistence_low", lambda r: (r.get("persistence", 0) or 0) < 0.3),
        ("span_short", lambda r: r.get("_span_days", r.get("span_days", 0)) <= 2),
        ("distinct_dates_short", lambda r: r.get("_distinct_dates", r.get("distinct_dates", 0)) <= 2),
        ("detections_7d_low", lambda r: r.get("detections_7d", 0) <= 3),
        ("frp_low_moderate", lambda r: 0.5 <= r.get("frp", 0) <= 7.0),
        ("hotspot_small", lambda r: 1 <= (r.get("hotspot_cluster_size", 0) or 0) <= 3),
        ("bt_moderate", lambda r: 300 <= r.get("brightness_temperature", 0) <= 340),
    ],
}
