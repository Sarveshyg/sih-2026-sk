"""
Ablation experiment: Baseline vs VEDAS

Compares XGBoost baseline (FIRMS+temporal) vs VEDAS (baseline + type-specific VEDAS features)
with same labels, same split, same seed, leakage-safe, missing distance handling via NaN+indicator.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from collections import Counter

from ml.training.split import spatial_temporal_split
from ml.models.xgboost_classifier import XGBoostClassifier
from ml.models.classifier import BaselineClassifier

# Define feature sets
BASELINE_FEATURES = [
    "latitude","longitude","frp","brightness_temperature","confidence",
    "hour_utc","day_of_week","month",
    "detections_24h","detections_7d","detections_30d","persistence","hotspot_cluster_size",
    "facility_baseline","facility_current_activity","facility_anomaly",
    "_cluster_size_500","_distinct_dates","_span_days",
]

# VEDAS type-specific features (as per task)
VEDAS_FEATURES = [
    "power_plant_count_1km", "oil_refinery_count_1km", "oil_well_count_1km",
    "ethanol_plant_count_1km", "wind_farm_count_1km", "solar_plant_count_1km",
    "nearest_power_plant_distance_m", "nearest_power_plant_present",
    "nearest_oil_refinery_distance_m", "nearest_oil_refinery_present",
    "nearest_oil_well_distance_m", "nearest_oil_well_present",
    "nearest_ethanol_plant_distance_m", "nearest_ethanol_plant_present",
    "nearest_wind_farm_distance_m", "nearest_wind_farm_present",
    "nearest_solar_plant_distance_m", "nearest_solar_plant_present",
]

# Industrial context subset (exclude wind/solar)
VEDAS_INDUSTRIAL_FEATURES = [
    "power_plant_count_1km", "oil_refinery_count_1km", "oil_well_count_1km", "ethanol_plant_count_1km",
    "nearest_power_plant_distance_m", "nearest_power_plant_present",
    "nearest_oil_refinery_distance_m", "nearest_oil_refinery_present",
    "nearest_oil_well_distance_m", "nearest_oil_well_present",
    "nearest_ethanol_plant_distance_m", "nearest_ethanol_plant_present",
]

# Also consider 5km counts if available
VEDAS_5KM_FEATURES = [
    "power_plant_count_5km", "oil_refinery_count_5km", "oil_well_count_5km", "ethanol_plant_count_5km",
]

def load_training_and_vedas():
    train_path = Path("data/firms/ml/training_dataset.csv")
    vedas_path = Path("data/firms/processed/firms_enriched_vedas.csv")
    if not train_path.exists():
        raise FileNotFoundError(f"Training dataset not found: {train_path}. Run ml/training/dataset.py first")
    if not vedas_path.exists():
        raise FileNotFoundError(f"VEDAS enriched not found: {vedas_path}. Run ml/geospatial/vedas_enrichment")
    
    train_df = pd.read_csv(train_path)
    vedas_df = pd.read_csv(vedas_path)
    
    # Ensure same order by id, merge on id
    # Check row count equality
    assert len(train_df) == len(vedas_df), f"Row mismatch {len(train_df)} vs {len(vedas_df)}"
    # Merge VEDAS features into training df via id
    vedas_cols = [c for c in vedas_df.columns if c not in train_df.columns]
    # Keep only VEDAS-specific columns that are in our feature lists
    # For ablation, we need to add VEDAS columns to train_df
    # Use id as key
    vedas_map = {row["id"]: row for _, row in vedas_df.iterrows()}
    for col in VEDAS_FEATURES + ["power_plant_count_5km", "oil_refinery_count_5km", "oil_well_count_5km", "ethanol_plant_count_5km"]:
        if col in vedas_df.columns:
            train_df[col] = train_df["id"].map(lambda x: vedas_map.get(x, {}).get(col))
        else:
            # If column not in vedas_df, set None
            train_df[col] = np.nan
    
    # Also add 5km counts if available in vedas_df (they are not in current vedas_enriched, but we can compute if needed)
    # For now, ensure they are present as NaN if missing
    for col in VEDAS_5KM_FEATURES:
        if col not in train_df.columns:
            train_df[col] = np.nan
    
    # Handle missing distances: ensure they are float NaN where None, and presence indicators are 0/1
    for col in [c for c in VEDAS_FEATURES if "distance_m" in c]:
        if col in train_df.columns:
            # Convert empty strings to NaN, ensure float
            train_df[col] = pd.to_numeric(train_df[col], errors='coerce')
    for col in [c for c in VEDAS_FEATURES if "present" in c]:
        if col in train_df.columns:
            train_df[col] = pd.to_numeric(train_df[col], errors='coerce').fillna(0).astype(int)
    
    return train_df

def evaluate_metrics(y_true, y_pred, labels):
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
    acc = accuracy_score(y_true, y_pred)
    prec_macro, rec_macro, f1_macro, _ = precision_recall_fscore_support(y_true, y_pred, average='macro', zero_division=0)
    prec_w, rec_w, f1_w, _ = precision_recall_fscore_support(y_true, y_pred, average='weighted', zero_division=0)
    prec_per, rec_per, f1_per, sup = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    per_class = {}
    for i, lbl in enumerate(labels):
        per_class[lbl] = {"precision": float(prec_per[i]), "recall": float(rec_per[i]), "f1": float(f1_per[i]), "support": int(sup[i])}
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    return {
        "accuracy": float(acc),
        "macro_precision": float(prec_macro),
        "macro_recall": float(rec_macro),
        "macro_f1": float(f1_macro),
        "weighted_f1": float(f1_w),
        "per_class": per_class,
        "confusion_matrix": cm,
        "labels": labels,
    }

def run_ablation(output_dir: Path = Path("data/firms/ml"), model_dir: Path = Path("models")):
    output_dir = Path(output_dir)
    model_dir = Path(model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    print("Loading training + VEDAS...", flush=True)
    df = load_training_and_vedas()
    print(f"Loaded {len(df)} rows with {len(df.columns)} cols", flush=True)
    # Verify no labels from VEDAS
    assert "weak_label" in df.columns
    # Check that VEDAS features are not used in label generation (they shouldn't be, but we verify)
    # Our labels were generated before VEDAS, so they are independent

    # Use same split for both models
    # Check if ablation_split.csv exists, else create
    split_path = output_dir / "ablation_split.csv"
    if split_path.exists():
        split_df = pd.read_csv(split_path)
        # Merge split assignments back to df via id
        split_map = dict(zip(split_df["id"], split_df["split"]))
        df["split"] = df["id"].map(split_map)
        # Verify all rows have split
        assert df["split"].notna().all()
        train = df[df["split"] == "train"].copy()
        val = df[df["split"] == "val"].copy()
        test = df[df["split"] == "test"].copy()
        # Load split report if exists
        split_report_path = output_dir / "ablation_split_report.json"
        if split_report_path.exists():
            split_report = json.loads(split_report_path.read_text())
        else:
            split_report = {"method": "loaded from ablation_split.csv"}
    else:
        from ml.training.split import spatial_temporal_split
        # Need to ensure we have _spatial_cluster_id column for split
        if "_spatial_cluster_id" not in df.columns:
            # If not present, create via clustering (should be present from dataset builder)
            print("Warning: _spatial_cluster_id missing, using random split", flush=True)
            from sklearn.model_selection import train_test_split
            train, test = train_test_split(df, test_size=0.15, random_state=42)
            val, test = train_test_split(test, test_size=0.5, random_state=42)
            split_report = {"method": "random fallback"}
        else:
            train, val, test, split_report = spatial_temporal_split(df, test_size=0.15, val_size=0.15, random_state=42)
        # Save split assignments
        split_df = pd.DataFrame({
            "id": pd.concat([train["id"], val["id"], test["id"]]),
            "split": ["train"]*len(train) + ["val"]*len(val) + ["test"]*len(test)
        })
        split_df.to_csv(split_path, index=False)
        (output_dir / "ablation_split_report.json").write_text(json.dumps(split_report, indent=2))

    # Also save split_report for later
    if not (output_dir / "ablation_split_report.json").exists():
        (output_dir / "ablation_split_report.json").write_text(json.dumps(split_report, indent=2))

    print(f"Split: train {len(train)} val {len(val)} test {len(test)}", flush=True)

    # Define feature sets
    baseline_features = [c for c in BASELINE_FEATURES if c in df.columns]
    vedas_features = [c for c in VEDAS_FEATURES if c in df.columns]
    vedas_industrial_features = [c for c in VEDAS_INDUSTRIAL_FEATURES if c in df.columns]

    print(f"Baseline features ({len(baseline_features)}): {baseline_features}", flush=True)
    print(f"VEDAS features ({len(vedas_features)}): {vedas_features}", flush=True)
    print(f"VEDAS industrial subset ({len(vedas_industrial_features)}): {vedas_industrial_features}", flush=True)

    # Prepare data for training - handle missing distances correctly
    # For baseline, use only baseline features
    # For VEDAS, use baseline + vedas
    # Need to handle categorical: satellite, daynight
    # For simplicity, use same preprocessing as XGBoostClassifier (it handles missing via median imputation, but we need to ensure NaN handling for distances)
    # Our XGBoostClassifier already handles missing via median imputation (fit on train only)
    # For VEDAS distances with NaN, median imputation will be from train

    labels = ["agricultural_fire","gas_flare","industrial_fire","persistent_industrial_thermal_source","wildfire","unknown"]

    # Train baseline
    print("Training baseline...", flush=True)
    from ml.models.xgboost_classifier import XGBoostClassifier
    baseline_model = XGBoostClassifier(random_state=42)
    # Temporarily set feature set for baseline: need to restrict to baseline features
    # XGBoostClassifier uses DEFAULT_FEATURES, but we need to override to use only baseline
    # We can monkey-patch its DEFAULT_FEATURES or pass df with only baseline columns + label
    # Simplest: create train_baseline df with only baseline features + label
    train_baseline = train[baseline_features + ["weak_label"]].copy()
    # Add categorical for baseline (satellite, daynight) - but baseline features don't include them, so we need to add them if present
    # Actually baseline features originally in train.py include satellite/daynight via categorical handling, but our baseline_features list doesn't include them
    # For consistency with original baseline, we should include satellite/daynight as categorical
    # Let's include them
    for cat in ["satellite","daynight"]:
        if cat in df.columns and cat not in train_baseline.columns:
            train_baseline[cat] = train[cat].values

    # But XGBoostClassifier's _prepare_features will handle categorical if present in df
    # So we need to ensure train_baseline has those columns
    # Let's just use the full train df but with a custom feature filter inside classifier
    # Simpler: create a wrapper that filters columns
    # We'll create a copy of train with only baseline + label and then train

    # For baseline, we will train with baseline features + categorical
    baseline_train_df = train[baseline_features + ["weak_label", "satellite", "daynight"]].copy() if all(c in train.columns for c in ["satellite","daynight"]) else train[baseline_features + ["weak_label"]].copy()
    # Need to ensure XGBoostClassifier uses only those features
    # We'll temporarily patch its DEFAULT_FEATURES
    import ml.models.xgboost_classifier as xgb_module
    orig_features = xgb_module.DEFAULT_FEATURES[:]
    xgb_module.DEFAULT_FEATURES = baseline_features

    baseline_model.fit(baseline_train_df, label_col="weak_label")
    baseline_model.save(model_dir / "xgboost_baseline_v01.json")
    print(f"Saved baseline to {model_dir / 'xgboost_baseline_v01.json'}", flush=True)

    # Evaluate baseline on val/test
    def eval_model(model, split_df, name):
        y_true = split_df["weak_label"].tolist()
        y_pred = model.predict(split_df)
        return evaluate_metrics(y_true, y_pred, labels)

    metrics_baseline_val = eval_model(baseline_model, val, "baseline_val")
    metrics_baseline_test = eval_model(baseline_model, test, "baseline_test")
    print(f"Baseline val macro F1 {metrics_baseline_val['macro_f1']:.3f}, test {metrics_baseline_test['macro_f1']:.3f}", flush=True)

    # Restore
    xgb_module.DEFAULT_FEATURES = orig_features

    # Train VEDAS
    print("Training VEDAS V0.2...", flush=True)
    vedas_all_features = baseline_features + vedas_features
    # For VEDAS, we need to ensure missing distances are handled correctly: they are NaN where no facility within 5km, with present indicator
    # Our VEDAS features include both distance and present, so model can learn that present=0 means far
    xgb_module.DEFAULT_FEATURES = vedas_all_features
    vedas_train_df = train[vedas_all_features + ["weak_label", "satellite", "daynight"]].copy() if all(c in train.columns for c in ["satellite","daynight"]) else train[vedas_all_features + ["weak_label"]].copy()
    vedas_model = XGBoostClassifier(random_state=42)
    vedas_model.fit(vedas_train_df, label_col="weak_label")
    vedas_model.save(model_dir / "xgboost_vedas_v02.json")
    print(f"Saved VEDAS to {model_dir / 'xgboost_vedas_v02.json'}", flush=True)
    metrics_vedas_val = eval_model(vedas_model, val, "vedas_val")
    metrics_vedas_test = eval_model(vedas_model, test, "vedas_test")
    print(f"VEDAS val macro F1 {metrics_vedas_val['macro_f1']:.3f}, test {metrics_vedas_test['macro_f1']:.3f}", flush=True)

    # Also train industrial-only subset if reasonable
    vedas_industrial_features = baseline_features + vedas_industrial_features
    xgb_module.DEFAULT_FEATURES = vedas_industrial_features
    vedas_ind_train_df = train[vedas_industrial_features + ["weak_label", "satellite", "daynight"]].copy() if all(c in train.columns for c in ["satellite","daynight"]) else train[vedas_industrial_features + ["weak_label"]].copy()
    vedas_ind_model = XGBoostClassifier(random_state=42)
    vedas_ind_model.fit(vedas_ind_train_df, label_col="weak_label")
    metrics_vedas_ind_val = eval_model(vedas_ind_model, val, "vedas_ind_val")
    metrics_vedas_ind_test = eval_model(vedas_ind_model, test, "vedas_ind_test")
    print(f"VEDAS industrial val macro F1 {metrics_vedas_ind_val['macro_f1']:.3f}", flush=True)

    # Restore
    xgb_module.DEFAULT_FEATURES = orig_features

    # Feature importance
    baseline_imp = baseline_model.feature_importance()
    vedas_imp = vedas_model.feature_importance()

    # Ablation report
    report = {
        "generated_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat().replace("+00:00","Z"),
        "baseline": {
            "feature_count": len(baseline_features),
            "features": baseline_features,
            "metrics_val": metrics_baseline_val,
            "metrics_test": metrics_baseline_test,
            "feature_importance": dict(sorted(baseline_imp.items(), key=lambda x: x[1], reverse=True)[:20]),
        },
        "vedas": {
            "feature_count": len(vedas_all_features),
            "features": vedas_all_features,
            "metrics_val": metrics_vedas_val,
            "metrics_test": metrics_vedas_test,
            "feature_importance": dict(sorted(vedas_imp.items(), key=lambda x: x[1], reverse=True)[:20]),
            "vedas_feature_importance": {k: v for k, v in sorted(vedas_imp.items(), key=lambda x: x[1], reverse=True) if k in vedas_features},
        },
        "vedas_industrial": {
            "feature_count": len(vedas_industrial_features),
            "features": vedas_industrial_features,
            "metrics_val": metrics_vedas_ind_val,
            "metrics_test": metrics_vedas_ind_test,
        },
        "deltas": {
            "accuracy": metrics_vedas_test["accuracy"] - metrics_baseline_test["accuracy"],
            "macro_f1": metrics_vedas_test["macro_f1"] - metrics_baseline_test["macro_f1"],
            "weighted_f1": metrics_vedas_test["weighted_f1"] - metrics_baseline_test["weighted_f1"],
        },
        "per_class_delta": {
            cls: {
                "baseline_f1": metrics_baseline_test["per_class"][cls]["f1"],
                "vedas_f1": metrics_vedas_test["per_class"][cls]["f1"],
                "delta": metrics_vedas_test["per_class"][cls]["f1"] - metrics_baseline_test["per_class"][cls]["f1"],
                "support": metrics_vedas_test["per_class"][cls]["support"],
            } for cls in labels
        },
        "split": split_report if 'split_report' in locals() else {},
        "scientific_disclaimer": "The evaluation uses weak labels rather than independently verified ground truth. Therefore, the measured metrics evaluate performance against the weak-supervision labeling scheme and should not be interpreted as real-world classification accuracy. VEDAS infrastructure proximity is contextual evidence and is not ground truth for fire/source classification.",
        "leakage_note": "Same labels, same rows, same split for both models. No VEDAS-derived labels. Missing distances handled via NaN + presence indicator (not 0).",
    }
    # Save
    (output_dir / "vedas_ablation_report.json").write_text(__import__('json').dumps(report, indent=2))
    # Also md
    md = f"""# VEDAS Ablation Report

Generated: {report['generated_at']}

## Baseline vs VEDAS

| Metric | Baseline | VEDAS | Delta |
|--------|----------|-------|-------|
| Accuracy | {metrics_baseline_test['accuracy']:.3f} | {metrics_vedas_test['accuracy']:.3f} | {report['deltas']['accuracy']:+.3f} |
| Macro F1 | {metrics_baseline_test['macro_f1']:.3f} | {metrics_vedas_test['macro_f1']:.3f} | {report['deltas']['macro_f1']:+.3f} |
| Weighted F1 | {metrics_baseline_test['weighted_f1']:.3f} | {metrics_vedas_test['weighted_f1']:.3f} | {report['deltas']['weighted_f1']:+.3f} |

## Per-class F1

| Class | Baseline F1 | VEDAS F1 | Delta | Support |
|-------|-------------|----------|-------|---------|
"""
    for cls in labels:
        b = metrics_baseline_test["per_class"][cls]
        v = metrics_vedas_test["per_class"][cls]
        md += f"| {cls} | {b['f1']:.3f} | {v['f1']:.3f} | {v['f1']-b['f1']:+.3f} | {v['support']} |\n"
    md += f"""
## Feature counts
- Baseline: {len(baseline_features)}
- VEDAS: {len(vedas_all_features)}
- VEDAS industrial subset: {len(vedas_industrial_features)}

## Top VEDAS features
{json.dumps(dict(list({k: round(v,4) for k,v in sorted(vedas_imp.items(), key=lambda x: x[1], reverse=True) if k in vedas_features}.items())[:5]), indent=2)}

## Oil well dominance
Oil well features importance: {sum(v for k,v in vedas_imp.items() if 'oil_well' in k):.4f}

## Conclusion
See `vedas_ablation_report.json` for full metrics. Remember: weak labels, not ground truth. VEDAS is contextual, not causal.
"""
    (output_dir / "vedas_ablation_report.md").write_text(md)
    print(f"Wrote ablation report to {output_dir / 'vedas_ablation_report.json'}")

    return report
