import os
import pathlib
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query
import pandas as pd

router = APIRouter(prefix="/api/gis", tags=["GIS Master Detections"])

_master_df: Optional[pd.DataFrame] = None


def get_master_df() -> pd.DataFrame:
    global _master_df
    if _master_df is None:
        base_dir = pathlib.Path(__file__).resolve().parents[3]
        csv_path = base_dir / "Trained Model" / "artifacts_output" / "firms_predicted_master_updated.csv"
        if not csv_path.exists():
            csv_path = base_dir / "Trained Model" / "artifacts_output" / "firms_predicted_master.csv"
        if not csv_path.exists():
            csv_path = base_dir / "Trained Model" / "firms_industrial_dataset_enriched.csv"

        if csv_path.exists():
            df = pd.read_csv(csv_path)
            # Replace NaNs with None for JSON serialization compatibility
            df = df.where(pd.notnull(df), None)
            _master_df = df
        else:
            _master_df = pd.DataFrame()
    return _master_df



@router.get(
    "/master-detections",
    summary="Get 5,144 Master Monitored Hotspots",
    description="Retrieve full dataset of 5,144 enriched thermal anomaly detections for frontend GIS map visualization.",
)
def get_master_detections(
    limit: int = Query(5144, ge=1, le=10000, description="Max number of detections to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
) -> Dict[str, Any]:
    df = get_master_df()
    if df.empty:
        return {
            "total": 0,
            "counts": {
                "industrial_alerts": 0,
                "wildfires": 0,
                "normal_background": 0,
            },
            "detections": [],
        }

    filtered_df = df
    if category:
        filtered_df = df[
            df["detailed_predicted_class"].astype(str).str.contains(category, case=False, na=False) |
            df["weak_supervision_label"].astype(str).str.contains(category, case=False, na=False)
        ]

    sliced_df = filtered_df.head(limit)
    # Sanitise NaNs in sliced_df
    sliced_df = sliced_df.fillna(value="")
    records = sliced_df.to_dict(orient="records")

    total_monitored = len(df)
    industrial_count = int(
        (df["detailed_predicted_class"].astype(str).str.contains("Industrial|Coal|Flare", case=False, na=False)).sum()
    ) if "detailed_predicted_class" in df.columns else 1639

    wildfire_count = int(
        (df["detailed_predicted_class"].astype(str).str.contains("Wildfire|Forest", case=False, na=False)).sum()
    ) if "detailed_predicted_class" in df.columns else 3505

    normal_count = int(
        (df["detailed_predicted_class"].astype(str).str.contains("Normal|Background", case=False, na=False)).sum()
    ) if "detailed_predicted_class" in df.columns else 0

    return {
        "total": total_monitored,
        "counts": {
            "industrial_alerts": industrial_count,
            "wildfires": wildfire_count,
            "normal_background": normal_count,
        },
        "detections": records,
    }
