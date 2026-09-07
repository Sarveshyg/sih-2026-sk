"""
Master Pipeline Orchestrator for Geospatial Thermal Anomaly Classification & GIS Visualization
"""
import os
import time
from src.spatial_join import build_enriched_dataset
from src.train import assign_multi_evidence_labels, run_training_experiment
from src.gis_map import create_gis_map

def run_full_pipeline():
    start_time = time.time()
    print("="*70)
    print("AI-ENABLED GEOSPATIAL SYSTEM: INDUSTRIAL FIRE CLASSIFICATION PIPELINE")
    print("="*70)
    
    # 1. Spatial Join & Feature Extraction
    print("\n[STEP 1/3] Spatial Join & BallTree Haversine Ingestion...")
    if not os.path.exists("firms_industrial_dataset_enriched.csv"):
        df_enriched = build_enriched_dataset(
            firms_file="J1_VIIRS_C2_South_Asia_7d.csv",
            plants_file="Global Oil and Gas Plant Tracker (GOGPT) - August 2026.xlsx",
            flares_file="2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx",
            coal_file="Global Coal Mine Tracker, August 2026.xlsx",
            output_file="firms_industrial_dataset_enriched.csv"
        )
    else:
        import pandas as pd
        print("Found existing 'firms_industrial_dataset_enriched.csv'. Loading...")
        df_enriched = pd.read_csv("firms_industrial_dataset_enriched.csv")

    # 2. Multi-Evidence Labeling & ML Training
    print("\n[STEP 2/3] Weak Supervision Labeling & ML Model Training...")
    df_labeled = assign_multi_evidence_labels(df_enriched)
    metrics = run_training_experiment(df_labeled, output_dir="artifacts_output")

    # 3. Interactive GIS Map Generation
    print("\n[STEP 3/3] Generating Interactive GIS Map Solution...")
    pred_path = "artifacts_output/firms_predicted_master_updated.csv" if os.path.exists("artifacts_output/firms_predicted_master_updated.csv") else "artifacts_output/firms_predicted_master.csv"
    create_gis_map(
        predicted_csv=pred_path,
        output_html="artifacts_output/industrial_fire_gis_map.html"
    )

    elapsed = time.time() - start_time
    print("\n" + "="*70)
    print(f"PIPELINE COMPLETED SUCCESSFULLY in {elapsed:.1f}s!")
    print("Deliverables generated in './artifacts_output/':")
    print(" 1. firms_predicted_master.csv (Full master predictions for all 5,144 detections)")
    print(" 2. radiometric_only_model.joblib (Trained model with zero distance leakage)")
    print(" 3. fused_geospatial_model.joblib (Trained model with fused physics + proximity)")
    print(" 4. model_comparison_confusion_matrices.png")
    print(" 5. feature_importance_comparison.png")
    print(" 6. industrial_fire_gis_map.html (Interactive GIS web overlay)")
    print(" 7. metrics_summary.json (Detailed performance metrics)")
    print("="*70)

if __name__ == "__main__":
    run_full_pipeline()
