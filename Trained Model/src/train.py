"""
Model Training & Evaluation with Multi-Evidence Labeling and Anti-Leakage Radiometric Ablation
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    f1_score, precision_score, recall_score, roc_auc_score
)
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

# Set plot aesthetics
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({'font.sans-serif': 'Arial', 'font.size': 11})

def assign_multi_evidence_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Multi-Evidence Labeling with Normal / Background Surface State Separation:
    
    1. 'NORMAL_OR_BACKGROUND_HEAT': Low FRP (< 3.0 MW) AND low thermal contrast (delta_T < 20K) AND Daytime
       -> Representing normal ambient solar heating / non-fire surface radiation.
    2. 'PERSISTENT_FLARE_HOTSPOT': Tight flare proximity (<= 1.5 km) + high thermal contrast (delta_T >= 20K or Night)
    3. 'INDUSTRIAL_FACILITY_ALERT': Tight plant/mine proximity (<= 2.0 km) + elevated FRP (>= 3.0 MW)
    4. 'COAL_MINE_THERMAL_SOURCE': Active mine proximity (<= 3.5 km) + elevated heat signature
    5. 'ACTIVE_WILDFIRE_OR_FOREST_FIRE': Remote hotspot (> 15 km away from industrial sites) with significant FRP
    6. 'UNCONFIRMED_INTERMEDIATE': Intermediate transition zone
    """
    df = df.copy()
    
    # Calculate temporal persistence: cluster coordinates by ~1km grid
    df["lat_grid"] = (df["latitude"] * 100).round() / 100
    df["lon_grid"] = (df["longitude"] * 100).round() / 100
    cluster_counts = df.groupby(["lat_grid", "lon_grid"])["acq_date"].transform("count")
    df["spatial_persistence_count"] = cluster_counts
    
    # Normal / Background surface heating (solar glint / low-energy ambient noise)
    is_normal_background = (
        (df["frp"] < 3.0) & 
        (df["temp_diff_ti4_ti5"] < 20.0) & 
        (df["is_night"] == 0) &
        (df["min_distance_to_industrial_km"] > 3.0)
    )
    
    is_flare = (
        (df["distance_to_flare_km"] <= 1.5) & 
        ((df["temp_diff_ti4_ti5"] >= 20.0) | (df["is_night"] == 1) | (df["spatial_persistence_count"] >= 2))
    )
    
    is_plant = (
        (df["distance_to_plant_km"] <= 2.0) &
        (df["frp"] >= 3.0) &
        (~is_flare)
    )
    
    is_mine = (
        (df["distance_to_coal_mine_km"] <= 3.5) &
        (df["frp"] >= 3.0) &
        (~is_flare) & (~is_plant)
    )
    
    is_wildfire = (
        (df["min_distance_to_industrial_km"] >= 15.0) &
        ((df["frp"] >= 3.0) | (df["temp_diff_ti4_ti5"] >= 25.0))
    )
    
    conditions = [
        is_normal_background,
        is_flare,
        is_plant,
        is_mine,
        is_wildfire
    ]
    choices = [
        "NORMAL_OR_BACKGROUND_HEAT",
        "PERSISTENT_FLARE_HOTSPOT",
        "INDUSTRIAL_FACILITY_ALERT",
        "COAL_MINE_THERMAL_SOURCE",
        "ACTIVE_WILDFIRE_OR_FOREST_FIRE"
    ]
    
    df["weak_supervision_label"] = np.select(conditions, choices, default="UNCONFIRMED_INTERMEDIATE")
    
    # Binary status: 1 for Industrial Thermal Alert, 0 for Natural / Background
    df["is_industrial_candidate"] = np.where(
        df["weak_supervision_label"].isin([
            "PERSISTENT_FLARE_HOTSPOT",
            "INDUSTRIAL_FACILITY_ALERT",
            "COAL_MINE_THERMAL_SOURCE"
        ]),
        1,
        np.where(
            df["weak_supervision_label"].isin([
                "NORMAL_OR_BACKGROUND_HEAT",
                "ACTIVE_WILDFIRE_OR_FOREST_FIRE"
            ]),
            0,
            -1
        )
    )
    
    print("\n" + "="*60)
    print(">>> MULTI-EVIDENCE WEAK SUPERVISION LABEL BREAKDOWN (With Normal/Background Zone)")
    print("="*60)
    print(df["weak_supervision_label"].value_counts())
    print("\nClean training subset count:", (df["is_industrial_candidate"] != -1).sum())
    
    return df

def build_feature_pipelines():
    """Build preprocessors for Radiometric-Only (No Leakage) and Fused-Spatial models."""
    # Radiometric-only features (Strictly physical sensor observations, ZERO distance leakage)
    radiometric_numeric = [
        "bright_ti4", "bright_ti5", "temp_diff_ti4_ti5",
        "frp", "log_frp", "scan", "track",
        "confidence_numeric", "acq_hour", "is_night"
    ]
    
    # Full fused features (Radiometric + Spatial + Metadata)
    fused_numeric = radiometric_numeric + [
        "distance_to_plant_km", "log_distance_to_plant",
        "distance_to_flare_km", "log_distance_to_flare",
        "distance_to_coal_mine_km", "log_distance_to_coal_mine",
        "min_distance_to_industrial_km", "log_min_industrial_distance",
        "nearest_plant_capacity_mw", "nearest_flare_mean_vol", "nearest_flare_active_years"
    ]
    
    fused_categorical = ["nearest_plant_fuel", "nearest_flare_level", "nearest_mine_type"]
    
    rad_pipe = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), radiometric_numeric)
        ],
        remainder="drop"
    )
    
    fused_pipe = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), fused_numeric),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")), ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), fused_categorical)
        ],
        remainder="drop"
    )
    
    return {
        "radiometric_features": radiometric_numeric,
        "fused_numeric": fused_numeric,
        "fused_categorical": fused_categorical,
        "rad_preprocessor": rad_pipe,
        "fused_preprocessor": fused_pipe
    }

def run_training_experiment(
    df: pd.DataFrame,
    output_dir: str = "artifacts_output"
) -> dict:
    """
    Execute dual-track training:
    1. Radiometric Physical Model (Tests whether satellite thermal properties alone differentiate industrial vs forest fires)
    2. Fused Geospatial Model (Combines thermal physics with geospatial proximity context)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Filter high-confidence clean subset for supervised training
    clean_df = df[df["is_industrial_candidate"] != -1].copy().reset_index(drop=True)
    print(f"\nTraining dataset size: {len(clean_df)} labeled samples ({len(clean_df[clean_df['is_industrial_candidate']==1])} Industrial, {len(clean_df[clean_df['is_industrial_candidate']==0])} Forest/Natural).")
    
    pipe_info = build_feature_pipelines()
    
    # Ensure numeric columns are strictly float in clean_df and df
    for col in pipe_info["fused_numeric"]:
        if col in clean_df.columns:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce").fillna(0.0)
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            
    for col in pipe_info["fused_categorical"]:
        if col in clean_df.columns:
            clean_df[col] = clean_df[col].astype(str).fillna("Unknown")
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("Unknown")
    
    y = clean_df["is_industrial_candidate"].values
    
    # -------------------------------------------------------------
    # TRACK 1: Radiometric Physical Classifier (ZERO Spatial Distance)
    # -------------------------------------------------------------
    print("\n" + "="*60)
    print(">>> TRACK 1: RADIOMETRIC PHYSICAL MODEL (Zero Distance Features)")
    print("Goal: Test if satellite thermal physics (TI4, TI5, Delta-T, FRP, Day/Night) classify events")
    print("="*60)
    
    X_rad = clean_df[pipe_info["radiometric_features"]]
    X_tr_rad, X_te_rad, y_tr, y_te = train_test_split(
        X_rad, y, test_size=0.20, random_state=42, stratify=y
    )
    
    rad_xgb = Pipeline([
        ("preprocessor", pipe_info["rad_preprocessor"]),
        ("clf", XGBClassifier(n_estimators=150, max_depth=4, learning_rate=0.05, random_state=42, eval_metric="logloss"))
    ])
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_rad = cross_validate(rad_xgb, X_tr_rad, y_tr, cv=cv, scoring=["accuracy", "f1_macro", "roc_auc"])
    
    rad_xgb.fit(X_tr_rad, y_tr)
    y_pred_rad = rad_xgb.predict(X_te_rad)
    y_prob_rad = rad_xgb.predict_proba(X_te_rad)[:, 1]
    
    print(f"Radiometric Model - CV Macro F1: {np.mean(cv_rad['test_f1_macro']):.4f} (+/- {np.std(cv_rad['test_f1_macro']):.4f}) | CV ROC-AUC: {np.mean(cv_rad['test_roc_auc']):.4f}")
    print(f"Radiometric Model - Test Accuracy: {accuracy_score(y_te, y_pred_rad):.4f} | Test F1: {f1_score(y_te, y_pred_rad, average='macro'):.4f} | Test AUC: {roc_auc_score(y_te, y_prob_rad):.4f}")
    
    # -------------------------------------------------------------
    # TRACK 2: Fused Geospatial & Physical Classifier
    # -------------------------------------------------------------
    print("\n" + "="*60)
    print(">>> TRACK 2: FUSED GEOSPATIAL & RADIOMETRIC MODEL")
    print("Goal: Combine thermal physics with geospatial proximity context")
    print("="*60)
    
    fused_cols = pipe_info["fused_numeric"] + pipe_info["fused_categorical"]
    X_fused = clean_df[fused_cols]
    X_tr_fus, X_te_fus, _, _ = train_test_split(
        X_fused, y, test_size=0.20, random_state=42, stratify=y
    )
    
    fused_xgb = Pipeline([
        ("preprocessor", pipe_info["fused_preprocessor"]),
        ("clf", XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=42, eval_metric="logloss"))
    ])
    
    cv_fus = cross_validate(fused_xgb, X_tr_fus, y_tr, cv=cv, scoring=["accuracy", "f1_macro", "roc_auc"])
    fused_xgb.fit(X_tr_fus, y_tr)
    y_pred_fus = fused_xgb.predict(X_te_fus)
    y_prob_fus = fused_xgb.predict_proba(X_te_fus)[:, 1]
    
    print(f"Fused Model - CV Macro F1: {np.mean(cv_fus['test_f1_macro']):.4f} (+/- {np.std(cv_fus['test_f1_macro']):.4f}) | CV ROC-AUC: {np.mean(cv_fus['test_roc_auc']):.4f}")
    print(f"Fused Model - Test Accuracy: {accuracy_score(y_te, y_pred_fus):.4f} | Test F1: {f1_score(y_te, y_pred_fus, average='macro'):.4f} | Test AUC: {roc_auc_score(y_te, y_prob_fus):.4f}")
    print("\nFused Model Classification Report:")
    print(classification_report(y_te, y_pred_fus, target_names=["Natural / Forest Fire", "Industrial Anomaly"]))

    # Save models
    joblib.dump(rad_xgb, os.path.join(output_dir, "radiometric_only_model.joblib"))
    joblib.dump(fused_xgb, os.path.join(output_dir, "fused_geospatial_model.joblib"))

    # -------------------------------------------------------------
    # TRACK 3: Predict Over the Complete 5,144 Master Hotspots
    # -------------------------------------------------------------
    df["prob_industrial_radiometric"] = rad_xgb.predict_proba(df[pipe_info["radiometric_features"]])[:, 1]
    df["prob_industrial_fused"] = fused_xgb.predict_proba(df[fused_cols])[:, 1]
    df["pred_class_fused"] = np.where(
        df["prob_industrial_fused"] >= 0.50,
        "INDUSTRIAL_THERMAL_SOURCE",
        "FOREST_OR_NATURAL_FIRE"
    )
    
    # Multi-class sub-categorization for all detections
    def categorize_anomaly(row):
        # 1. Normal / Low-Intensity Ambient Zone
        if row["frp"] < 3.0 and row["temp_diff_ti4_ti5"] < 20.0 and row["is_night"] == 0 and row["min_distance_to_industrial_km"] > 3.0:
            return "Normal Background / Non-Fire Solar Heating"
            
        if row["pred_class_fused"] == "FOREST_OR_NATURAL_FIRE":
            return "Active Wildfire / Forest Fire"
            
        # 2. Industrial Source Subtypes
        d_flare = row["distance_to_flare_km"]
        d_plant = row["distance_to_plant_km"]
        d_mine = row["distance_to_coal_mine_km"]
        
        min_d = min(d_flare, d_plant, d_mine)
        if min_d == d_flare:
            return "Gas Flare / Upstream Thermal Source"
        elif min_d == d_plant:
            return f"Industrial Facility Alert ({row.get('nearest_plant_fuel', 'Plant')})"
        else:
            return "Coal Mine Thermal Alert"
            
    df["detailed_predicted_class"] = df.apply(categorize_anomaly, axis=1)
    
    master_csv_path = os.path.join(output_dir, "firms_predicted_master.csv")
    try:
        df.to_csv(master_csv_path, index=False)
    except PermissionError:
        master_csv_path = os.path.join(output_dir, "firms_predicted_master_updated.csv")
        df.to_csv(master_csv_path, index=False)
    print(f"\nSaved full master predictions ({len(df)} records) to: {master_csv_path}")
    print("\nDetailed Class Breakdown across all 5,144 detections:")
    print(df["detailed_predicted_class"].value_counts())

    # -------------------------------------------------------------
    # VISUALIZATIONS & PLOTS
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    
    # 1. Comparison of ROC Curves / Metrics
    cm_rad = confusion_matrix(y_te, y_pred_rad)
    cm_fus = confusion_matrix(y_te, y_pred_fus)
    
    sns.heatmap(cm_rad, annot=True, fmt="d", cmap="Purples", ax=axes[0], cbar=False,
                xticklabels=["Natural Fire", "Industrial"], yticklabels=["Natural Fire", "Industrial"], annot_kws={"size": 13, "weight": "bold"})
    axes[0].set_title(f"Radiometric Model (No Distance Leakage)\nTest Acc: {accuracy_score(y_te, y_pred_rad):.2%} | AUC: {roc_auc_score(y_te, y_prob_rad):.2%}", fontsize=12, weight="bold")
    axes[0].set_xlabel("Predicted", fontsize=11)
    axes[0].set_ylabel("True Label", fontsize=11)
    
    sns.heatmap(cm_fus, annot=True, fmt="d", cmap="Blues", ax=axes[1], cbar=False,
                xticklabels=["Natural Fire", "Industrial"], yticklabels=["Natural Fire", "Industrial"], annot_kws={"size": 13, "weight": "bold"})
    axes[1].set_title(f"Fused Geospatial Model (Physics + Proximity)\nTest Acc: {accuracy_score(y_te, y_pred_fus):.2%} | AUC: {roc_auc_score(y_te, y_prob_fus):.2%}", fontsize=12, weight="bold")
    axes[1].set_xlabel("Predicted", fontsize=11)
    axes[1].set_ylabel("True Label", fontsize=11)
    
    plt.tight_layout()
    cm_path = os.path.join(output_dir, "model_comparison_confusion_matrices.png")
    plt.savefig(cm_path, dpi=300)
    plt.close()

    # 2. Feature Importance for Radiometric Model vs Fused Model
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    rad_features = pipe_info["radiometric_features"]
    rad_importances = rad_xgb.named_steps["clf"].feature_importances_
    rad_imp_df = pd.DataFrame({"Feature": rad_features, "Importance": rad_importances}).sort_values(by="Importance", ascending=False)
    
    sns.barplot(data=rad_imp_df, x="Importance", y="Feature", palette="magma", ax=axes[0])
    axes[0].set_title("Radiometric Model: Physical Feature Importance\n(Thermal Physics Only)", fontsize=12, weight="bold")
    axes[0].set_xlabel("Relative Importance (Gain)", fontsize=11)
    
    # Fused Feature names
    fused_preprocessor = fused_xgb.named_steps["preprocessor"]
    cat_feature_names = fused_preprocessor.named_transformers_["cat"].named_steps["onehot"].get_feature_names_out(pipe_info["fused_categorical"])
    all_fused_names = pipe_info["fused_numeric"] + list(cat_feature_names)
    fus_importances = fused_xgb.named_steps["clf"].feature_importances_
    fus_imp_df = pd.DataFrame({"Feature": all_fused_names, "Importance": fus_importances}).sort_values(by="Importance", ascending=False).head(12)
    
    sns.barplot(data=fus_imp_df, x="Importance", y="Feature", palette="viridis", ax=axes[1])
    axes[1].set_title("Fused Model: Top 12 Geospatial + Physical Features", fontsize=12, weight="bold")
    axes[1].set_xlabel("Relative Importance (Gain)", fontsize=11)
    
    plt.tight_layout()
    feat_path = os.path.join(output_dir, "feature_importance_comparison.png")
    plt.savefig(feat_path, dpi=300)
    plt.close()
    
    # Export metrics JSON
    metrics_summary = {
        "radiometric_only_model": {
            "cv_f1_macro_mean": float(np.mean(cv_rad["test_f1_macro"])),
            "cv_roc_auc_mean": float(np.mean(cv_rad["test_roc_auc"])),
            "test_accuracy": float(accuracy_score(y_te, y_pred_rad)),
            "test_f1_macro": float(f1_score(y_te, y_pred_rad, average="macro")),
            "test_roc_auc": float(roc_auc_score(y_te, y_prob_rad)),
            "feature_importance": rad_imp_df.to_dict(orient="records")
        },
        "fused_geospatial_model": {
            "cv_f1_macro_mean": float(np.mean(cv_fus["test_f1_macro"])),
            "cv_roc_auc_mean": float(np.mean(cv_fus["test_roc_auc"])),
            "test_accuracy": float(accuracy_score(y_te, y_pred_fus)),
            "test_f1_macro": float(f1_score(y_te, y_pred_fus, average="macro")),
            "test_roc_auc": float(roc_auc_score(y_te, y_prob_fus)),
            "classification_report": classification_report(y_te, y_pred_fus, target_names=["Natural / Forest Fire", "Industrial Anomaly"], output_dict=True),
            "feature_importance": fus_imp_df.to_dict(orient="records")
        }
    }
    with open(os.path.join(output_dir, "metrics_summary.json"), "w") as f:
        json.dump(metrics_summary, f, indent=2)
        
    print(f"\nSaved all evaluation artifacts and plots to: {output_dir}")
    return metrics_summary

if __name__ == "__main__":
    if os.path.exists("firms_industrial_dataset_enriched.csv"):
        df = pd.read_csv("firms_industrial_dataset_enriched.csv")
        df_labeled = assign_multi_evidence_labels(df)
        run_training_experiment(df_labeled)
    else:
        print("Enriched dataset not found. Please run spatial_join.py first.")
