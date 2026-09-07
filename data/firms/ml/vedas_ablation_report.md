# VEDAS Ablation Report

Generated: 2026-09-07T16:20:09.845979Z

## Baseline vs VEDAS

| Metric | Baseline | VEDAS | Delta |
|--------|----------|-------|-------|
| Accuracy | 0.985 | 0.985 | +0.000 |
| Macro F1 | 0.564 | 0.558 | -0.006 |
| Weighted F1 | 0.984 | 0.984 | -0.000 |

## Per-class F1

| Class | Baseline F1 | VEDAS F1 | Delta | Support |
|-------|-------------|----------|-------|---------|
| agricultural_fire | 0.993 | 0.994 | +0.001 | 892 |
| gas_flare | 0.000 | 0.000 | +0.000 | 0 |
| industrial_fire | 0.937 | 0.937 | +0.000 | 64 |
| persistent_industrial_thermal_source | 0.889 | 0.857 | -0.032 | 18 |
| wildfire | 0.000 | 0.000 | +0.000 | 3 |
| unknown | 0.000 | 0.000 | +0.000 | 1 |

## Feature counts
- Baseline: 19
- VEDAS: 37
- VEDAS industrial subset: 31

## Top VEDAS features
{
  "nearest_oil_refinery_present": 0.0245,
  "nearest_power_plant_present": 0.0208,
  "nearest_power_plant_distance_m": 0.012,
  "oil_well_count_1km": 0.0119,
  "nearest_oil_well_distance_m": 0.01
}

## Oil well dominance
Oil well features importance: 0.0274

## Conclusion
See `vedas_ablation_report.json` for full metrics. Remember: weak labels, not ground truth. VEDAS is contextual, not causal.
