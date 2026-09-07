"""
ml/features/engineering.py — Deterministic feature engineering.

No future leakage: only uses fields present in the enriched event at prediction time.
Missing contextual fields are handled with None -> 0 / neutral values and flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ml.schemas import EnrichedEvent
from ml import config as cfg


@dataclass
class FeatureVector:
    # Raw
    frp: float
    brightness_temperature: float
    firms_confidence: float  # 0-100

    # Normalised 0-1 helpers
    frp_norm: float = 0.0
    bt_norm: float = 0.0

    # Spatial
    distance_to_facility_m: Optional[float] = None
    distance_to_forest_m: Optional[float] = None
    distance_to_agriculture_m: Optional[float] = None
    facility_type: Optional[str] = None
    inside_industrial_area: Optional[bool] = None
    is_flare_facility: bool = False
    is_industrial_facility: bool = False

    # Temporal
    persistence_score: Optional[float] = None
    detections_24h: Optional[int] = None
    detections_7d: Optional[int] = None
    detections_30d: Optional[int] = None
    hotspot_cluster_size: Optional[int] = None

    # Land cover
    ndvi: Optional[float] = None
    ndbi: Optional[float] = None

    # Anomaly
    facility_baseline: Optional[float] = None
    current_activity: Optional[float] = None
    activity_anomaly: Optional[float] = None  # (current-baseline)/baseline or 0 if baseline=0
    anomaly_ratio: Optional[float] = None  # current / baseline

    # Flags for missing data
    has_industrial_context: bool = False
    has_forest_context: bool = False
    has_agri_context: bool = False
    has_temporal_context: bool = False
    has_landcover_context: bool = False
    has_anomaly_context: bool = False

    # For explainability
    raw_features: dict = field(default_factory=dict)


class FeatureEngineer:
    """Stateless engineer — can be instantiated once and reused."""

    def engineer(self, event: EnrichedEvent) -> FeatureVector:
        frp = float(event.frp)
        bt = float(event.brightness_temperature)
        conf = float(event.confidence)

        # Normalise FRP: clip at 250 MW -> 1.0
        frp_norm = min(frp / 250.0, 1.0)
        # Normalise BT: 300K ->0, 420K->1
        bt_norm = max(0.0, min((bt - 300) / 120.0, 1.0))

        dist_fac = event.resolved_distance_to_facility()
        dist_forest = event.resolved_distance_to_forest()
        dist_agri = event.resolved_distance_to_agriculture()
        persistence = event.resolved_persistence()
        facility_type = (event.facility_type or "").lower().strip() or None

        # Anomaly — deterministic, no leakage
        baseline = event.facility_baseline
        current = event.current_activity
        anomaly = event.activity_anomaly
        anomaly_ratio = None
        if anomaly is None and baseline is not None and current is not None:
            if baseline > 0:
                anomaly = (current - baseline) / baseline
                anomaly_ratio = current / baseline if baseline else None
            else:
                # No baseline -> if current >0 treat as anomaly
                anomaly = float(current) if current > 0 else 0.0
                anomaly_ratio = None
        elif anomaly is not None and baseline is not None and current is not None and anomaly_ratio is None:
            if baseline and baseline != 0:
                anomaly_ratio = current / baseline if current is not None else None

        # Flags
        is_flare = facility_type in cfg.FLARE_FACILITY_TYPES if facility_type else False
        is_industrial = facility_type in cfg.INDUSTRIAL_FACILITY_TYPES if facility_type else False

        fv = FeatureVector(
            frp=frp,
            brightness_temperature=bt,
            firms_confidence=conf,
            frp_norm=frp_norm,
            bt_norm=bt_norm,
            distance_to_facility_m=dist_fac,
            distance_to_forest_m=dist_forest,
            distance_to_agriculture_m=dist_agri,
            facility_type=facility_type,
            inside_industrial_area=event.inside_industrial_area,
            is_flare_facility=is_flare,
            is_industrial_facility=is_industrial,
            persistence_score=persistence,
            detections_24h=event.detections_24h,
            detections_7d=event.detections_7d,
            detections_30d=event.detections_30d,
            hotspot_cluster_size=event.hotspot_cluster_size,
            ndvi=event.ndvi,
            ndbi=event.ndbi,
            facility_baseline=baseline,
            current_activity=current,
            activity_anomaly=anomaly,
            anomaly_ratio=anomaly_ratio,
            has_industrial_context=dist_fac is not None or facility_type is not None,
            has_forest_context=dist_forest is not None,
            has_agri_context=dist_agri is not None,
            has_temporal_context=any(v is not None for v in [persistence, event.detections_24h, event.detections_7d]),
            has_landcover_context=any(v is not None for v in [event.ndvi, event.ndbi]),
            has_anomaly_context=anomaly is not None,
            raw_features={
                "frp": frp,
                "brightness_temperature": bt,
                "firms_confidence": conf,
                "distance_to_facility_m": dist_fac,
                "facility_type": facility_type,
                "persistence_score": persistence,
                "ndvi": event.ndvi,
                "ndbi": event.ndbi,
                "detections_24h": event.detections_24h,
                "detections_7d": event.detections_7d,
                "detections_30d": event.detections_30d,
                "hotspot_cluster_size": event.hotspot_cluster_size,
                "facility_baseline": baseline,
                "current_activity": current,
                "activity_anomaly": anomaly,
            },
        )
        return fv

    @staticmethod
    def compute_anomaly_ratio(baseline: Optional[float], current: Optional[float]) -> tuple[Optional[float], Optional[float]]:
        """Return (anomaly, ratio)."""
        if baseline is None or current is None:
            return None, None
        if baseline == 0:
            return (float(current) if current > 0 else 0.0), None
        anomaly = (current - baseline) / baseline
        ratio = current / baseline
        return anomaly, ratio
