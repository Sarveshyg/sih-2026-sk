"""
ml/schemas.py — Typed data contracts for AI Core.

Follows MASTER.md §6-8 contracts. Uses Pydantic for validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator


class ClassificationLabel(str, Enum):
    industrial_fire = "industrial_fire"
    # MASTER.md canonical: persistent_industrial_source
    # Task asks: persistent_industrial_thermal_source — support both via alias
    persistent_industrial_thermal_source = "persistent_industrial_thermal_source"
    persistent_industrial_source = "persistent_industrial_source"
    gas_flare = "gas_flare"
    wildfire = "wildfire"
    agricultural_fire = "agricultural_fire"
    unknown = "unknown"

    @classmethod
    def canonical(cls, value: str) -> str:
        """Normalise alias: persistent_industrial_source <-> persistent_industrial_thermal_source."""
        if value == cls.persistent_industrial_source.value:
            return cls.persistent_industrial_thermal_source.value
        return value


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ThermalEvent(BaseModel):
    """Raw FIRMS thermal anomaly — MASTER §6.1"""

    id: str = Field(..., description="Unique event ID")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    frp: float = Field(..., ge=0, description="Fire Radiative Power MW")
    brightness_temperature: float = Field(..., ge=0, description="Brightness temperature K")
    confidence: float = Field(..., ge=0, le=100, description="FIRMS confidence 0-100 or 0-1*100")
    timestamp: datetime
    satellite: str = Field(default="VIIRS")

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> float:
        # Accept "h"/"l"/"n" style from FIRMS if accidentally passed
        if isinstance(v, str):
            mapping = {"h": 90, "n": 60, "l": 30}
            lower = v.lower().strip()
            if lower in mapping:
                return float(mapping[lower])
            try:
                return float(v)
            except ValueError:
                return 0
        return float(v)

    @field_validator("satellite", mode="before")
    @classmethod
    def _upper_sat(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)


class EnrichedEvent(ThermalEvent):
    """
    GIS + temporal enriched event — MASTER §7.
    All contextual fields are OPTIONAL; pipeline must not crash if missing.
    """

    # Facility / spatial
    nearest_facility_id: Optional[str] = None
    nearest_facility_name: Optional[str] = None
    facility_type: Optional[str] = None
    distance_to_facility_m: Optional[float] = Field(default=None, ge=0)
    # Aliases that GIS team may send
    distance_to_industry: Optional[float] = Field(default=None, ge=0)
    distance_to_forest: Optional[float] = Field(default=None, ge=0)
    distance_to_forest_m: Optional[float] = Field(default=None, ge=0)
    distance_to_agriculture: Optional[float] = Field(default=None, ge=0)
    distance_to_agriculture_m: Optional[float] = Field(default=None, ge=0)
    inside_industrial_area: Optional[bool] = None

    # Temporal
    persistence_score: Optional[float] = Field(default=None, ge=0, le=1)
    persistence: Optional[float] = Field(default=None, ge=0, le=1)
    detections_24h: Optional[int] = Field(default=None, ge=0)
    detections_7d: Optional[int] = Field(default=None, ge=0)
    detections_30d: Optional[int] = Field(default=None, ge=0)

    # Land cover / satellite
    ndvi: Optional[float] = Field(default=None, ge=-1, le=1)
    ndbi: Optional[float] = Field(default=None, ge=-1, le=1)
    landcover_class: Optional[str] = Field(default=None, description="forest|agriculture|industrial/built-up|water|bare land|other|unknown")
    forest_fraction: Optional[float] = Field(default=None, ge=0, le=1, description="Fraction forest within radius")
    agriculture_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    industrial_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    builtup_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    water_fraction: Optional[float] = Field(default=None, ge=0, le=1)
    bare_fraction: Optional[float] = Field(default=None, ge=0, le=1)

    # Anomaly / facility intelligence
    hotspot_cluster_size: Optional[int] = Field(default=None, ge=0)
    facility_baseline: Optional[float] = Field(default=None, ge=0, description="Avg detections/day")
    current_activity: Optional[float] = Field(default=None, ge=0, description="Current detections/day")
    activity_anomaly: Optional[float] = None  # pre-computed if available

    # Population / extra context
    nearby_population: Optional[int] = Field(default=None, ge=0)

    # OSM enrichment (new) — all optional
    nearest_facility_distance_m: Optional[float] = Field(default=None, ge=0)
    nearest_facility_osm_id: Optional[str] = None
    facility_count_500m: Optional[int] = Field(default=None, ge=0)
    facility_count_1km: Optional[int] = Field(default=None, ge=0)
    industrial_facility_count_500m: Optional[int] = Field(default=None, ge=0)
    industrial_facility_count_1km: Optional[int] = Field(default=None, ge=0)
    power_facility_count_1km: Optional[int] = Field(default=None, ge=0)
    oil_gas_facility_count_1km: Optional[int] = Field(default=None, ge=0)
    nearest_powerplant_distance_m: Optional[float] = Field(default=None, ge=0)
    nearest_refinery_distance_m: Optional[float] = Field(default=None, ge=0)
    nearest_oil_gas_distance_m: Optional[float] = Field(default=None, ge=0)
    nearest_steel_facility_distance_m: Optional[float] = Field(default=None, ge=0)
    nearest_cement_facility_distance_m: Optional[float] = Field(default=None, ge=0)

    # Time derived
    hour_utc: Optional[int] = Field(default=None, ge=0, le=23)
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6, description="0=Monday")
    month: Optional[int] = Field(default=None, ge=1, le=12)
    daynight: Optional[str] = Field(default=None, description="D/N from FIRMS or derived")

    def resolved_distance_to_facility(self) -> Optional[float]:
        if self.distance_to_facility_m is not None:
            return self.distance_to_facility_m
        if self.distance_to_industry is not None:
            return self.distance_to_industry
        return None

    def resolved_persistence(self) -> Optional[float]:
        if self.persistence_score is not None:
            return self.persistence_score
        return self.persistence

    def resolved_distance_to_forest(self) -> Optional[float]:
        if self.distance_to_forest_m is not None:
            return self.distance_to_forest_m
        return self.distance_to_forest

    def resolved_distance_to_agriculture(self) -> Optional[float]:
        if self.distance_to_agriculture_m is not None:
            return self.distance_to_agriculture_m
        return self.distance_to_agriculture


class TriageRecommendation(BaseModel):
    triage_required: bool
    recommended_tier: Optional[int] = Field(default=None, ge=1, le=3)
    action: str  # "tier1_alert" | "monitoring" | "store_only"


class PredictionOutput(BaseModel):
    """MASTER §8 AI Prediction Contract + Step 9 output"""

    event_id: str
    classification: str  # canonical label
    confidence: float = Field(..., ge=0, le=1)
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str  # RiskLevel value
    recommended_tier: Optional[int] = Field(default=None, ge=1, le=3)
    triage_required: bool
    explanation: List[str]
    # Optional enriched diagnostics for frontend / debugging
    anomaly_ratio: Optional[float] = None
    persistence_score: Optional[float] = None
    model_version: str = "baseline-v0"

    def model_dump_canonical(self) -> dict:
        d = self.model_dump()
        # Ensure classification is canonical
        d["classification"] = ClassificationLabel.canonical(d["classification"])
        return d
