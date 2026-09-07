import os
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, Body
from app.services.firms_service import FirmsService

router = APIRouter(prefix="/api/firms", tags=["NASA FIRMS Realtime Feed & Pipeline"])


@router.get("/status", summary="Get NASA FIRMS Ingestion & Pipeline Status")
def get_status() -> Dict[str, Any]:
    return FirmsService.get_status()


@router.get("/pipeline-monitor", summary="Get 7-Stage FIRMS Pipeline Monitor Counts")
def get_pipeline_monitor() -> Dict[str, Any]:
    return FirmsService.get_pipeline_monitor()


@router.post("/refresh", summary="Trigger NASA FIRMS Area API Fetch & ML Ingestion")
def refresh_firms(
    map_key: Optional[str] = Body(None, embed=True, description="Optional FIRMS MAP_KEY"),
    force: bool = Body(True, embed=True, description="Force refresh ignoring TTL"),
) -> Dict[str, Any]:
    return FirmsService.refresh_data(force=force, map_key=map_key)


@router.get("/detections", summary="Get Monitored Detections from FIRMS")
def get_detections(
    limit: int = Query(2600, ge=1, le=10000),
    priority_only: bool = Query(False),
) -> Dict[str, Any]:
    items = FirmsService.get_detections(limit=limit, priority_only=priority_only)
    return {
        "source": "NASA FIRMS",
        "count": len(items),
        "detections": items,
    }


@router.get("/live", summary="Get NASA FIRMS Active Thermal Anomaly Feed")
def get_live_firms(
    country_code: str = Query("IND", description="ISO3 Country code or region"),
    map_key: str = Query(None, description="Optional NASA FIRMS API MAP_KEY"),
) -> Dict[str, Any]:
    items = FirmsService.get_detections(limit=2600, priority_only=False)
    return {
        "source": "NASA FIRMS",
        "count": len(items),
        "detections": items,
    }
