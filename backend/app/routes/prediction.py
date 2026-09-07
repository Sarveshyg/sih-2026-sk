from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.prediction import PredictRequest, PredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/predict", tags=["AI Prediction"])


@router.post(
    "",
    response_model=PredictionResponse,
    summary="Run AI prediction for a thermal event",
    description="Trigger AI classification and risk analysis for a specified thermal event ID.",
)
def predict_event(
    request: PredictRequest,
    db: Session = Depends(get_db),
):
    result = PredictionService.predict(db=db, event_id=request.event_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Thermal event with id '{request.event_id}' not found for prediction",
        )
    return result
