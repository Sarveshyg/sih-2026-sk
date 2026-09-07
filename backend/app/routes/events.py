from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.thermal_event import ThermalEventSummary, EventIntelligenceResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/api/events", tags=["Thermal Events"])


@router.get(
    "",
    response_model=List[ThermalEventSummary],
    summary="Get list of thermal events",
    description="Retrieve all thermal events enriched with prediction and facility summary information. Supports optional filtering.",
)
def get_events(
    classification: Optional[str] = Query(None, description="Filter by classification label (e.g. industrial_fire, wildfire)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk severity level (e.g. low, moderate, high, critical)"),
    facility_id: Optional[str] = Query(None, description="Filter by associated facility ID"),
    db: Session = Depends(get_db),
):
    return EventService.get_events(
        db=db,
        classification=classification,
        risk_level=risk_level,
        facility_id=facility_id,
    )


@router.get(
    "/{event_id}",
    response_model=EventIntelligenceResponse,
    summary="Get detailed event intelligence",
    description="Retrieve full intelligence object for a specific thermal event, including event parameters, AI prediction details, nearest facility details, and temporal metrics.",
)
def get_event_detail(
    event_id: str,
    db: Session = Depends(get_db),
):
    detail = EventService.get_event_detail(db=db, event_id=event_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Thermal event with id '{event_id}' not found")
    return detail
