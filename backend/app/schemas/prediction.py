from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PredictRequest(BaseModel):
    event_id: str = Field(..., description="Target thermal event ID to classify and evaluate risk for")


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: Optional[str] = None
    classification: str = Field(..., description="Machine readable classification label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model prediction confidence score (0.0 to 1.0)")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk evaluation score from 0 to 100")
    risk_level: str = Field(..., description="Risk severity level: low, moderate, high, critical")
    explanation: List[str] = Field(default_factory=list, description="Reasoning factors supporting the prediction")

