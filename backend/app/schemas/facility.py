from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class FacilityBase(BaseModel):
    id: str = Field(..., description="Unique facility ID (e.g. FAC_001)")
    name: str = Field(..., description="Facility name")
    type: str = Field(..., description="Facility type (e.g. refinery, petrochemical, steel_plant, power_plant, mine)")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class FacilityCreate(FacilityBase):
    geometry: Optional[str] = None


class FacilityResponse(FacilityBase):
    model_config = ConfigDict(from_attributes=True)


class FacilityDetailResponse(FacilityBase):
    model_config = ConfigDict(from_attributes=True)

    geometry: Optional[Any] = None
    historical_activity: Dict[str, Any] = Field(default_factory=dict)
    associated_events: List[Dict[str, Any]] = Field(default_factory=list)
    active_predictions: List[Dict[str, Any]] = Field(default_factory=list)
    abnormality_info: Dict[str, Any] = Field(default_factory=dict)

