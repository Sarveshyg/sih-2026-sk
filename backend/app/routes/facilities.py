from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.facility import FacilityResponse, FacilityDetailResponse
from app.services.facility_service import FacilityService

router = APIRouter(prefix="/api/facilities", tags=["Industrial Facilities"])


@router.get(
    "",
    response_model=List[FacilityResponse],
    summary="Get all industrial facilities",
    description="Retrieve all registered industrial facilities with spatial coordinates and facility type information.",
)
def get_facilities(db: Session = Depends(get_db)):
    return FacilityService.get_all_facilities(db=db)


@router.get(
    "/{facility_id}",
    response_model=FacilityDetailResponse,
    summary="Get detailed facility intelligence",
    description="Retrieve comprehensive facility intelligence including historical thermal activity, baseline comparison, associated events, active AI predictions, and abnormality status.",
)
def get_facility_detail(
    facility_id: str,
    db: Session = Depends(get_db),
):
    detail = FacilityService.get_facility_detail(db=db, facility_id=facility_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Industrial facility with id '{facility_id}' not found")
    return detail
