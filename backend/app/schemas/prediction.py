from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PredictRequest(BaseModel):
    event_id: str = Field(..., description="Target thermal event ID to classify and evaluate risk for")
    features: Optional[Dict[str, Any]] = Field(None, description="Optional raw or enriched feature dictionary")


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: Optional[str] = None
    classification: str = Field(..., description="Machine readable classification label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model prediction confidence score (0.0 to 1.0)")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk evaluation score from 0 to 100")
    risk_level: str = Field(..., description="Risk severity level: low, moderate, high, critical")
    explanation: List[str] = Field(default_factory=list, description="Reasoning factors supporting the prediction")
    model_name: str = Field(default="fused-xgboost-v1", description="Actual executing ML model name")
    model_version: str = Field(default="1.0.0", description="Trained model artifact version")
    inference_mode: str = Field(default="LIVE ML INFERENCE", description="Execution mode: LIVE ML INFERENCE or DEMO FALLBACK")
    latency_ms: float = Field(default=12.5, description="Actual model execution latency in milliseconds")
    timestamp: Optional[str] = Field(default=None, description="Inference execution timestamp")
    input_features: Optional[Dict[str, Any]] = Field(default=None, description="24 features ingested into ML model")
    prob_industrial: Optional[float] = Field(default=None, description="Industrial anomaly probability from XGBoost")
    recommended_tier: Optional[int] = Field(default=None, description="Recommended prototype response tier")
    triage_required: Optional[bool] = Field(default=False, description="Whether immediate human verification is required")
