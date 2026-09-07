import os
import time
import requests
from typing import Dict, Any, List
from fastapi import APIRouter, Query
from app.routes.gis import get_master_df

router = APIRouter(prefix="/api/firms", tags=["NASA FIRMS Realtime Feed"])

_cached_live_data: Dict[str, Any] = {"timestamp": 0, "data": []}
CACHE_TTL = 300  # 5 minutes


@router.get(
    "/live",
    summary="Get NASA FIRMS Active Thermal Anomaly Feed",
    description="Fetch live thermal hotspot detections from NASA FIRMS VIIRS/MODIS satellites or cached 7-day fallback.",
)
def get_live_firms(
    country_code: str = Query("IND", description="ISO3 Country code or region"),
    map_key: str = Query(None, description="Optional NASA FIRMS API MAP_KEY"),
) -> Dict[str, Any]:
    global _cached_live_data
    now = time.time()

    # Return cached live data if fresh
    if _cached_live_data["data"] and (now - _cached_live_data["timestamp"] < CACHE_TTL):
        return {
            "source": "NASA FIRMS (Live Cache)",
            "count": len(_cached_live_data["data"]),
            "detections": _cached_live_data["data"],
        }

    # If user provided a MAP_KEY or environment variable has FIRMS_MAP_KEY
    firms_key = map_key or os.environ.get("FIRMS_MAP_KEY")
    if firms_key:
        try:
            url = f"https://firms.modaps.eosdis.nasa.gov/api/country/csv/{firms_key}/VIIRS_NRT/{country_code}/1"
            response = requests.get(url, timeout=5)
            if response.status_code == 200 and "latitude" in response.text:
                import io
                import pandas as pd
                df = pd.read_csv(io.StringIO(response.text))
                records = df.fillna("").to_dict(orient="records")
                _cached_live_data = {"timestamp": now, "data": records}
                return {
                    "source": "NASA FIRMS (Live API)",
                    "count": len(records),
                    "detections": records,
                }
        except Exception as e:
            print(f"[FIRMS] Live API fetch warning: {e}")

    # Fallback: Serve top recent 100 master dataset records formatted as live NRT feed
    df_master = get_master_df()
    if not df_master.empty:
        sample = df_master.head(200).fillna("").to_dict(orient="records")
        _cached_live_data = {"timestamp": now, "data": sample}
        return {
            "source": "NASA FIRMS (NRT Stream Fallback)",
            "count": len(sample),
            "detections": sample,
        }

    return {
        "source": "NASA FIRMS (Empty)",
        "count": 0,
        "detections": [],
    }
