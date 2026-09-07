# Training Dataset — Prototype (Weak Labels, Not Ground Truth)

Generated: 2026-09-07T12:20:33.865162Z
Input: data\firms\processed\firms_india.csv (6523 India FIRMS detections, 2026-08-01 to 2026-08-30)
Output: `training_dataset.csv` (6523 rows, leakage_safe=True)

## Features Genuinely Available
- FIRMS: frp, brightness_temperature, confidence, lat/lon, satellite, daynight (recovered), hour_utc, day_of_week, month
- Temporal (leakage_safe): detections_24h/7d/30d, persistence, hotspot_cluster_size, facility_baseline/current_activity/anomaly
- Spatial: 500m cluster size, distinct_dates, span_days, spatial_cluster_id

Excluded (synthetic or 0% coverage): OSM distances/counts, landcover fractions, ndvi/ndbi

## Weak Labels
- Version: weak_rule_v1
- Classes: industrial_fire, persistent_industrial_thermal_source, gas_flare, wildfire, agricultural_fire, unknown
- Method: multi-signal rules (see `ml/labels/label_rules.py`), confidence = satisfied/total
- No single feature defines a label; at least 3 conditions required, score >=0.5
- Unknown when insufficient evidence

## Class Distribution
{
  "agricultural_fire": 3093,
  "industrial_fire": 436,
  "gas_flare": 63,
  "persistent_industrial_thermal_source": 2795,
  "unknown": 121,
  "wildfire": 15
}
Unknown: 121 (1.85%)
Low confidence (<0.5): 121

## Leakage
Overlap between label-generating and training features: ['detections_24h', 'detections_30d', 'detections_7d', 'hotspot_cluster_size', 'persistence']
This is a weak-supervision baseline, not independent evaluation.

## Files
- training_dataset.csv — full features + weak labels
- labels.csv — id, weak_label, confidence, reasons
- dataset_report.json — counts, missingness, features
- leakage_report.json — overlap analysis
