from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analytics import AnalyticsResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get(
    "",
    response_model=AnalyticsResponse,
    summary="Get dashboard analytics",
    description="Retrieve high-level statistics including total thermal events, industrial events count, critical risk events, and persistent sources count.",
)
def get_analytics(db: Session = Depends(get_db)):
    return AnalyticsService.get_analytics(db=db)
