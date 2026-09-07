"""
ml/models/risk.py — Independent risk scoring (0-100) with LOW/MODERATE/HIGH/CRITICAL levels.

Independent from classification: industrial_fire != auto critical.
"""

from __future__ import annotations

from ml.features.engineering import FeatureVector
from ml import config as cfg
from ml.schemas import RiskLevel


def _level_from_score(score: int) -> RiskLevel:
    if score >= 75:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 30:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


class RiskScorer:
    """
    Deterministic risk scorer.

    Factors:
    - thermal intensity (FRP, BT, FIRMS confidence)
    - persistence
    - industrial proximity / facility criticality
    - anomaly
    - classification type adjustment
    """

    def score(self, fv: FeatureVector, classification: str) -> tuple[int, RiskLevel]:
        points = 0.0

        # 1. FRP (0-25)
        if fv.frp >= cfg.FRP_VERY_HIGH:
            points += 25
        elif fv.frp >= cfg.FRP_HIGH:
            points += 18 + (fv.frp - cfg.FRP_HIGH) / (cfg.FRP_VERY_HIGH - cfg.FRP_HIGH) * 7
        elif fv.frp >= cfg.FRP_MEDIUM:
            points += 10 + (fv.frp - cfg.FRP_MEDIUM) / (cfg.FRP_HIGH - cfg.FRP_MEDIUM) * 8
        elif fv.frp >= cfg.FRP_LOW:
            points += 4 + (fv.frp - cfg.FRP_LOW) / (cfg.FRP_MEDIUM - cfg.FRP_LOW) * 6
        else:
            points += fv.frp / cfg.FRP_LOW * 4

        # BT bonus (0-5)
        if fv.brightness_temperature >= cfg.BT_VERY_HIGH:
            points += 5
        elif fv.brightness_temperature >= cfg.BT_HIGH:
            points += 3
        elif fv.brightness_temperature >= cfg.BT_LOW:
            points += 1

        # FIRMS confidence (0-5)
        points += (fv.firms_confidence / 100) * 5

        # 2. Industrial proximity (0-20)
        dist = fv.distance_to_facility_m
        if dist is not None:
            if dist < 200:
                points += 20
            elif dist < 500:
                points += 16
            elif dist < 2000:
                points += 10
            elif dist < 5000:
                points += 4
            else:
                points += 1
        else:
            # If unknown distance but industrial facility type suggests nearness
            if fv.is_industrial_facility:
                points += 8
            elif fv.inside_industrial_area:
                points += 6

        # Facility criticality bonus (0-5)
        if fv.facility_type and fv.facility_type in cfg.CRITICAL_FACILITY_TYPES:
            points += 5
        elif fv.is_industrial_facility:
            points += 2

        # Inside industrial area bonus
        if fv.inside_industrial_area:
            points += 3

        # 3. Persistence (0-15)
        pers = fv.persistence_score
        if pers is not None:
            points += pers * 15
        else:
            # fallback via detections
            if fv.detections_7d is not None:
                points += min(fv.detections_7d / 14 * 10, 10)
            if fv.detections_24h is not None and fv.detections_24h >= 3:
                points += 3

        # Cluster size for wildfire spread risk
        if fv.hotspot_cluster_size is not None and fv.hotspot_cluster_size >= 5:
            points += 5
        elif fv.hotspot_cluster_size is not None and fv.hotspot_cluster_size >= 3:
            points += 2

        # 4. Anomaly (0-20)
        anomaly = fv.activity_anomaly
        if anomaly is not None:
            if anomaly >= 5:
                points += 20
            elif anomaly >= 2:
                points += 14
            elif anomaly >= 1:
                points += 10
            elif anomaly >= 0.5:
                points += 6
            elif anomaly >= 0:
                points += 2
            # negative anomaly reduces?
            else:
                points += 0
        else:
            # No anomaly context -> no penalty/bonus
            pass

        # 5. Land cover adjustment (0-5)
        # Low NDVI + high NDBI (built-up) slightly increases industrial risk
        # but high NDVI alone is not low risk for wildfire — risk still high for large wildfire
        # So we keep adjustment small
        if fv.ndvi is not None and fv.ndvi < 0.2 and fv.ndbi is not None and fv.ndbi > 0.3:
            points += 2

        # 6. Classification adjustment (small, keeps independence)
        # industrial_fire and gas_flare slightly higher baseline
        cls_adj = {
            "industrial_fire": 4,
            "persistent_industrial_thermal_source": 2,
            "persistent_industrial_source": 2,
            "gas_flare": 1,  # flare often routine -> not high risk unless anomalous
            "wildfire": 3,
            "agricultural_fire": -4,
            "unknown": -6,
        }
        points += cls_adj.get(classification, 0)

        # Gas flare mitigation: if persistent but not anomalous and moderate FRP -> lower risk
        if classification == "gas_flare" and (anomaly is None or anomaly < 0.5) and fv.frp < 50:
            points -= 8

        # Persistent source without anomaly -> moderate risk reduction
        if classification in ("persistent_industrial_thermal_source", "persistent_industrial_source") and (anomaly is None or anomaly < 0.5):
            points -= 5

        # Clamp
        points = max(0, min(100, points))
        score = int(round(points))

        level = _level_from_score(score)
        return score, level

    @staticmethod
    def level_name(level: RiskLevel) -> str:
        return level.value
