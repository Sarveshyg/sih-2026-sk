"""
ml/explainability/explanation.py — Human-readable evidence generation.

Each string is grounded in actual feature values, not hallucinated.
"""

from __future__ import annotations

from typing import List

from ml.features.engineering import FeatureVector
from ml import config as cfg


class Explainer:
    def explain(self, fv: FeatureVector, classification: str, confidence: float, risk_score: int) -> List[str]:
        reasons: List[str] = []

        # Thermal intensity
        if fv.frp >= cfg.FRP_VERY_HIGH:
            reasons.append(f"Very high thermal intensity (FRP {fv.frp:.1f} MW)")
        elif fv.frp >= cfg.FRP_HIGH:
            reasons.append(f"High thermal intensity (FRP {fv.frp:.1f} MW)")
        elif fv.frp >= cfg.FRP_MEDIUM:
            reasons.append(f"Elevated thermal intensity (FRP {fv.frp:.1f} MW)")
        elif fv.frp < 10:
            reasons.append(f"Low thermal intensity (FRP {fv.frp:.1f} MW)")

        if fv.brightness_temperature >= cfg.BT_HIGH:
            reasons.append(f"High brightness temperature ({fv.brightness_temperature:.0f} K)")

        # Industrial proximity
        dist = fv.distance_to_facility_m
        if dist is not None:
            if dist < 100:
                reasons.append(f"Thermal anomaly is {dist:.0f}m from an industrial facility — very close proximity")
            elif dist < cfg.INDUSTRIAL_CLOSE_M:
                reasons.append(f"Thermal anomaly is {dist:.0f}m from an industrial facility")
            elif dist < cfg.INDUSTRIAL_NEAR_M:
                reasons.append(f"Industrial facility within {dist:.0f}m")
            elif dist > cfg.INDUSTRIAL_FAR_M:
                reasons.append(f"No industrial facility within {dist/1000:.1f} km")
        elif fv.is_industrial_facility:
            reasons.append(f"Associated with {fv.facility_type} facility type")

        if fv.inside_industrial_area:
            reasons.append("Event is inside a mapped industrial area")

        if fv.facility_type:
            # Add facility type context for relevant classes
            if fv.is_flare_facility and classification == "gas_flare":
                reasons.append(f"Facility type '{fv.facility_type}' is associated with gas flaring")
            elif fv.is_industrial_facility and classification in ("industrial_fire", "persistent_industrial_thermal_source", "persistent_industrial_source"):
                reasons.append(f"Nearby facility type '{fv.facility_type}' matches industrial thermal activity")

        # Persistence / temporal
        pers = fv.persistence_score
        if pers is not None:
            if pers >= cfg.PERSISTENCE_HIGH:
                reasons.append("Thermal activity has persisted across multiple detections (high persistence)")
            elif pers >= cfg.PERSISTENCE_MODERATE:
                reasons.append("Persistent thermal activity detected over recent days")
            elif pers < cfg.PERSISTENCE_LOW:
                reasons.append("Isolated/temporary thermal detection — low persistence")
        # detections backup
        if fv.detections_7d is not None and fv.detections_7d >= 10 and pers is None:
            reasons.append(f"{fv.detections_7d} detections in last 7 days indicate persistent activity")
        if fv.detections_24h is not None and fv.detections_24h >= 4:
            reasons.append(f"{fv.detections_24h} detections in last 24h")

        # Anomaly
        if fv.activity_anomaly is not None:
            if fv.activity_anomaly >= 5:
                if fv.anomaly_ratio:
                    reasons.append(f"Current activity is {fv.anomaly_ratio:.1f}x the facility baseline — highly anomalous")
                else:
                    reasons.append(f"Activity is {fv.activity_anomaly*100:.0f}% above baseline — highly anomalous")
            elif fv.activity_anomaly >= 1:
                ratio = fv.anomaly_ratio if fv.anomaly_ratio else (1 + fv.activity_anomaly)
                reasons.append(f"Activity exceeds historical facility baseline by {fv.activity_anomaly*100:.0f}% ({ratio:.1f}x)")
            elif fv.activity_anomaly >= 0.5:
                reasons.append(f"Activity is {fv.activity_anomaly*100:.0f}% above facility baseline")
            elif fv.activity_anomaly < 0:
                reasons.append("Activity is below historical baseline")

        # Land cover
        if fv.ndvi is not None:
            if fv.ndvi > cfg.NDVI_VEGETATION:
                reasons.append(f"High vegetation context (NDVI {fv.ndvi:.2f})")
            elif fv.ndvi < cfg.NDVI_LOW:
                reasons.append(f"Low vegetation / built-up context (NDVI {fv.ndvi:.2f})")
        if fv.ndbi is not None:
            if fv.ndbi > cfg.NDBI_BUILTUP:
                reasons.append(f"Built-up / industrial land signature (NDBI {fv.ndbi:.2f})")
            elif fv.ndbi < 0:
                reasons.append(f"Vegetated / non-built-up land (NDBI {fv.ndbi:.2f})")

        # Forest / agri
        if fv.distance_to_forest_m is not None and fv.distance_to_forest_m < cfg.FOREST_CLOSE_M:
            reasons.append(f"Close to forest/vegetated area ({fv.distance_to_forest_m:.0f}m)")
        if fv.distance_to_agriculture_m is not None and fv.distance_to_agriculture_m < cfg.AGRI_CLOSE_M:
            reasons.append(f"Agricultural land nearby ({fv.distance_to_agriculture_m:.0f}m)")

        # Cluster
        if fv.hotspot_cluster_size is not None:
            if fv.hotspot_cluster_size >= 5:
                reasons.append(f"Clustered thermal anomalies — {fv.hotspot_cluster_size} hotspots in vicinity suggests spreading fire")
            elif fv.hotspot_cluster_size >= 3:
                reasons.append(f"Multiple hotspots detected (cluster size {fv.hotspot_cluster_size})")

        # Confidence note for low confidence
        if confidence < 0.6:
            reasons.append("Low model confidence — limited contextual evidence available")

        if classification == "unknown" and not reasons:
            reasons.append("Insufficient contextual information to determine thermal source type")

        # Fallback if still empty
        if not reasons:
            reasons.append(f"Classification based on thermal and spatial features (FRP {fv.frp:.1f}, confidence {fv.firms_confidence:.0f})")

        # Deduplicate while preserving order
        seen = set()
        uniq = []
        for r in reasons:
            if r not in seen:
                uniq.append(r)
                seen.add(r)
        # Limit to 6 most relevant
        return uniq[:6]
