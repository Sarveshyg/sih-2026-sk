from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ThermalEventBase(BaseModel):
    id: str = Field(..., description="Unique event identifier (e.g. FIRMS_001)")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    frp: float = Field(..., ge=0.0, description="Fire Radiative Power in MW")
    brightness_temperature: float = Field(..., ge=0.0, description="Brightness temperature in Kelvin")
    confidence: float = Field(..., ge=0.0, le=100.0, description="FIRMS confidence percentage")
    timestamp: str = Field(..., description="ISO 8601 acquisition timestamp")
    satellite: str = Field(..., description="Satellite sensor (e.g. VIIRS, MODIS)")


class ThermalEventCreate(ThermalEventBase):
    facility_id: Optional[str] = None
    nearest_facility_name: Optional[str] = None
    facility_type: Optional[str] = None
    distance_to_facility_m: Optional[float] = None
    persistence_score: Optional[float] = None
    detections_24h: Optional[int] = None
    detections_7d: Optional[int] = None
    ndvi: Optional[float] = None
    ndbi: Optional[float] = None


class EnrichedThermalEvent(ThermalEventBase):
    model_config = ConfigDict(from_attributes=True)

    nearest_facility_id: Optional[str] = None
    nearest_facility_name: Optional[str] = None
    facility_type: Optional[str] = None
    distance_to_facility_m: Optional[float] = None
    persistence_score: Optional[float] = None
    detections_24h: Optional[int] = None
    detections_7d: Optional[int] = None
    ndvi: Optional[float] = None
    ndbi: Optional[float] = None


class ThermalEventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    latitude: float
    longitude: float
    classification: Optional[str] = "unknown"
    confidence: Optional[float] = 0.0
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "low"
    frp: Optional[float] = 0.0
    brightness_temperature: Optional[float] = 0.0
    timestamp: Optional[str] = None
    satellite: Optional[str] = None
    facility_id: Optional[str] = None
    facility_name: Optional[str] = None
    facility_type: Optional[str] = None



class EventIntelligenceResponse(BaseModel):
    event: Dict[str, Any]
    prediction: Dict[str, Any]
    facility: Dict[str, Any]
    temporal: Dict[str, Any]
