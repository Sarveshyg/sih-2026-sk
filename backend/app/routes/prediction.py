from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.prediction import PredictRequest, PredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api", tags=["AI Prediction & Provenance"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Run AI prediction for a thermal event",
    description="Trigger live ML inference (fused-xgboost-v1) and return latency, model version, features, and risk scoring.",
)
def predict_event(
    request: PredictRequest,
    db: Session = Depends(get_db),
):
    result = PredictionService.predict(db=db, event_id=request.event_id, raw_features=request.features)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Thermal event with id '{request.event_id}' could not be evaluated",
        )
    return result


@router.post(
    "/events/{event_id}/predict",
    response_model=PredictionResponse,
    summary="Trigger ML inference for specific event ID",
)
def predict_by_event_id(
    event_id: str,
    features: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db),
):
    result = PredictionService.predict(db=db, event_id=event_id, raw_features=features)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Thermal event '{event_id}' could not be evaluated",
        )
    return result
