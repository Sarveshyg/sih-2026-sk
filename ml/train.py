"""
ml/train.py — Prototype training pipeline (weak supervision, no ground truth).

Steps:
 1. load FIRMS India
 2. build training dataset (if not exists, calls dataset builder)
 3. split leakage-aware (spatial + temporal)
 4. train XGBoost
 5. evaluate vs BaselineClassifier
 6. save model, metrics, predictions, explanations

Deterministic, no API keys, no labels fabricated as ground truth.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from collections import Counter

# Ensure project root in path
sys.path.insert(0, ".")

from ml.training.dataset import build_training_dataset
from ml.training.split import spatial_temporal_split
from ml.models.xgboost_classifier import XGBoostClassifier
from ml.models.classifier import BaselineClassifier
from ml.features.engineering import FeatureEngineer
from ml.schemas import EnrichedEvent
from ml.models.risk import RiskScorer

DEFAULT_INPUT = Path("data/firms/processed/firms_india.csv")
DEFAULT_OUTPUT_DIR = Path("data/firms/ml")
DEFAULT_MODEL_DIR = Path("models")

def evaluate_metrics(y_true, y_pred, labels):
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, f1_score
    acc = accuracy_score(y_true, y_pred)
    # macro and weighted
    precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(y_true, y_pred, average='macro', zero_division=0)
    precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(y_true, y_pred, average='weighted', zero_division=0)
    # per class
    precision_per, recall_per, f1_per, support = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    per_class = {}
    for i, lbl in enumerate(labels):
        per_class[lbl] = {
            "precision": float(precision_per[i]),
            "recall": float(recall_per[i]),
            "f1": float(f1_per[i]),
            "support": int(support[i]),
        }
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    return {
        "accuracy": float(acc),
        "macro_precision": float(precision_macro),
        "macro_recall": float(recall_macro),
        "macro_f1": float(f1_macro),
        "weighted_f1": float(f1_weighted),
        "per_class": per_class,
        "confusion_matrix": cm,
        "labels": labels,
    }

def run(
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    model_dir: Path = DEFAULT_MODEL_DIR,
    test_size: float = 0.15,
    val_size: float = 0.15,
    random_state: int = 42,
):
    print("=== Prototype Training Pipeline (Weak Supervision) ===", flush=True)
    print(f"Input: {input_path}", flush=True)

    # 1. Build dataset if not exists
    dataset_csv = output_dir / "training_dataset.csv"
    if not dataset_csv.exists():
        print("Building training dataset...", flush=True)
        build_training_dataset(input_path=input_path, output_dir=output_dir)
    else:
        print(f"Using existing {dataset_csv}", flush=True)

    df = pd.read_csv(dataset_csv)
    print(f"Loaded training dataset {len(df)} rows", flush=True)
    # Check for weak labels
    if "weak_label" not in df.columns:
        raise ValueError("training_dataset.csv missing weak_label; rebuild dataset")

    # 2. Split leakage-aware
    print("Splitting (spatial grouping + temporal)...", flush=True)
    train, val, test, split_report = spatial_temporal_split(df, test_size=test_size, val_size=val_size, random_state=random_state)
    print(f"Train {len(train)} Val {len(val)} Test {len(test)}", flush=True)
    # Save splits for reproducibility
    train.to_csv(output_dir / "train.csv", index=False)
    val.to_csv(output_dir / "val.csv", index=False)
    test.to_csv(output_dir / "test.csv", index=False)
    (output_dir / "split_report.json").write_text(json.dumps(split_report, indent=2))

    # 3. Prepare features for XGBoost
    # Use same feature set as dataset builder
    feature_cols = [
        "latitude","longitude","frp","brightness_temperature","confidence",
        "hour_utc","day_of_week","month",
        "detections_24h","detections_7d","detections_30d","persistence","hotspot_cluster_size",
        "facility_baseline","facility_current_activity","facility_anomaly",
        "_cluster_size_500","_distinct_dates","_span_days",
    ]
    # Filter to available
    feature_cols = [c for c in feature_cols if c in df.columns]
    print(f"Features used: {feature_cols}", flush=True)

    # Encode labels for training
    # Map weak_label to index via XGBoost's internal mapping (it handles unknown too)
    # For training, we include all classes, but if some have very few samples (<10), we may keep them but warn
    class_counts = Counter(train["weak_label"])
    print(f"Train class distribution: {class_counts}", flush=True)
    # Warn if any class <10
    for cls, cnt in class_counts.items():
        if cnt < 10:
            print(f"WARNING: class {cls} has only {cnt} training samples — metrics will be unstable", flush=True)

    # Train XGBoost
    print("Training XGBoost...", flush=True)
    xgb = XGBoostClassifier(random_state=random_state)
    # Fit on train
    train_report = xgb.fit(train, label_col="weak_label")
    print(f"Feature importance: {train_report['feature_importance']}", flush=True)

    # Save model
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "xgboost_prototype.json"
    xgb.save(model_path)
    print(f"Saved XGBoost to {model_path}", flush=True)

    # Evaluate on val and test
    labels = ["agricultural_fire","gas_flare","industrial_fire","persistent_industrial_thermal_source","wildfire","unknown"]
    # Filter to labels present in data
    # For evaluation, we use weak labels as ground truth (weak supervision)
    # This is a baseline, not independent evaluation
    def eval_split(split_df, name):
        y_true = split_df["weak_label"].tolist()
        # XGBoost predictions
        y_pred_xgb = xgb.predict(split_df)
        # Baseline predictions (rule-based)
        baseline = BaselineClassifier()
        # Need to convert each row to EnrichedEvent-like dict for baseline
        # Baseline uses FeatureEngineer internally, but we can call via inference pipeline
        from ml.inference.pipeline import InferencePipeline
        pipe = InferencePipeline(classifier=baseline)
        y_pred_base = []
        for _, row in split_df.iterrows():
            # Build enriched dict
            enriched = {
                "id": row["id"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "frp": row["frp"],
                "brightness_temperature": row["brightness_temperature"],
                "confidence": row["confidence"],
                "timestamp": row["timestamp"],
                "satellite": row["satellite"],
                "distance_to_facility_m": None,  # no OSM
                "persistence_score": row.get("persistence"),
                "detections_24h": row.get("detections_24h"),
                "detections_7d": row.get("detections_7d"),
                "detections_30d": row.get("detections_30d"),
                "hotspot_cluster_size": row.get("hotspot_cluster_size"),
                "facility_baseline": row.get("facility_baseline"),
                "current_activity": row.get("facility_current_activity"),
                "activity_anomaly": row.get("facility_anomaly"),
            }
            pred = pipe.predict(enriched)
            y_pred_base.append(pred["classification"])
        # Metrics
        metrics_xgb = evaluate_metrics(y_true, y_pred_xgb, labels)
        metrics_base = evaluate_metrics(y_true, y_pred_base, labels)
        return metrics_xgb, metrics_base, y_pred_xgb, y_pred_base

    print("Evaluating on val...", flush=True)
    metrics_val_xgb, metrics_val_base, _, _ = eval_split(val, "val")
    print(f"Val XGBoost macro F1: {metrics_val_xgb['macro_f1']:.3f}, accuracy: {metrics_val_xgb['accuracy']:.3f}", flush=True)
    print(f"Val Baseline macro F1: {metrics_val_base['macro_f1']:.3f}", flush=True)

    print("Evaluating on test (held-out)...", flush=True)
    metrics_test_xgb, metrics_test_base, y_pred_test_xgb, y_pred_test_base = eval_split(test, "test")
    print(f"Test XGBoost macro F1: {metrics_test_xgb['macro_f1']:.3f}", flush=True)
    print(f"Test Baseline macro F1: {metrics_test_base['macro_f1']:.3f}", flush=True)

    # Save test predictions
    test_out = test.copy()
    test_out["xgb_predicted"] = y_pred_test_xgb
    # Also add probabilities
    proba = xgb.predict_proba(test)
    for i, cls in enumerate(["agricultural_fire","gas_flare","industrial_fire","persistent_industrial_thermal_source","wildfire","unknown"]):
        test_out[f"prob_{cls}"] = proba[:, i]
    # Risk scoring integration
    risk_scorer = RiskScorer()
    from ml.features.engineering import FeatureEngineer
    engineer = FeatureEngineer()
    risk_scores = []
    risk_levels = []
    for _, row in test_out.iterrows():
        # Build EnrichedEvent for risk (use same as baseline)
        enriched = {
            "id": row["id"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "frp": row["frp"],
            "brightness_temperature": row["brightness_temperature"],
            "confidence": row["confidence"],
            "timestamp": row["timestamp"],
            "satellite": row["satellite"],
            "persistence_score": row.get("persistence"),
            "detections_7d": row.get("detections_7d"),
            "hotspot_cluster_size": row.get("hotspot_cluster_size"),
            "facility_baseline": row.get("facility_baseline"),
            "current_activity": row.get("facility_current_activity"),
            "activity_anomaly": row.get("facility_anomaly"),
        }
        # Use feature engineering to get risk (need classification for risk)
        fv = engineer.engineer(EnrichedEvent(**{**enriched, "id": row["id"]})) if "EnrichedEvent" in dir() else None
        # Simpler: use risk scorer directly with fv and predicted class
        try:
            from ml.schemas import EnrichedEvent
            ev = EnrichedEvent(**{k: v for k, v in enriched.items() if k in EnrichedEvent.model_fields}, id=row["id"])
            fv = FeatureEngineer().engineer(ev)
            score, level = risk_scorer.score(fv, row["xgb_predicted"])
            risk_scores.append(score)
            risk_levels.append(level.value)
        except Exception:
            risk_scores.append(50)
            risk_levels.append("MODERATE")
    test_out["risk_score"] = risk_scores
    test_out["risk_level"] = risk_levels
    test_pred_path = output_dir / "test_predictions.csv"
    test_out.to_csv(test_pred_path, index=False)
    print(f"Wrote test predictions {test_pred_path}", flush=True)

    # Training report
    training_report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "input": str(input_path),
        "total_samples": len(df),
        "split": split_report,
        "features_used": feature_cols,
        "label_method": "weak_rule_v1",
        "class_counts_train": dict(Counter(train["weak_label"])),
        "class_counts_val": dict(Counter(val["weak_label"])),
        "class_counts_test": dict(Counter(test["weak_label"])),
        "xgboost_params": {"n_estimators": xgb.n_estimators, "max_depth": xgb.max_depth, "learning_rate": xgb.learning_rate, "random_state": xgb.random_state},
        "feature_importance": train_report["feature_importance"],
        "metrics_val_xgboost": metrics_val_xgb,
        "metrics_val_baseline": metrics_val_base,
        "metrics_test_xgboost": metrics_test_xgb,
        "metrics_test_baseline": metrics_test_base,
        "model_path": str(model_path),
        "test_predictions": str(test_pred_path),
        "leakage_note": "Weak labels derived from persistence/detections/hotspot; same features used for training => weak-supervision baseline, not independent. Test set held out via spatial grouping + temporal sorting, untouched during development.",
        "scientific_honesty": "FIRMS are real, weak labels are NOT ground truth, OSM 0% (synthetic not used), land-cover 0%, evaluation preliminary, requires human verification.",
    }
    report_path = output_dir / "training_report.json"
    report_path.write_text(json.dumps(training_report, indent=2), encoding="utf-8")
    print(f"Wrote training report {report_path}", flush=True)

    # Example predictions (first 3 test rows)
    examples = []
    for i in range(min(3, len(test_out))):
        row = test_out.iloc[i]
        examples.append({
            "id": row["id"],
            "true_weak_label": row["weak_label"],
            "xgb_predicted": row["xgb_predicted"],
            "probabilities": {c: float(row[f"prob_{c}"]) for c in ["agricultural_fire","gas_flare","industrial_fire","persistent_industrial_thermal_source","wildfire","unknown"]},
            "risk_score": int(row["risk_score"]),
            "risk_level": row["risk_level"],
        })
    print(f"Example predictions: {examples[:1]}", flush=True)

    return training_report

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Prototype training pipeline")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    args = parser.parse_args()
    run(input_path=Path(args.input), output_dir=Path(args.output_dir), model_dir=Path(args.model_dir))

if __name__ == "__main__":
    main()
