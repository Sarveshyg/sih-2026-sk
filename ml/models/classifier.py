"""
ml/models/classifier.py — Classification interface + deterministic baseline.

Design: interface-first so a trained XGBoost/RF can replace BaselineClassifier later
without changing pipeline or API contracts.

Labels (MASTER §8 canonical):
  industrial_fire
  persistent_industrial_source  (alias)
  persistent_industrial_thermal_source
  gas_flare
  wildfire
  agricultural_fire
  unknown

We canonicalise to `persistent_industrial_thermal_source` internally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple, Dict

from ml.features.engineering import FeatureVector
from ml.schemas import ClassificationLabel
from ml import config as cfg


CANONICAL_PERSISTENT = ClassificationLabel.persistent_industrial_thermal_source.value


class BaseClassifier(ABC):
    @abstractmethod
    def predict(self, fv: FeatureVector) -> Tuple[str, float]:
        """Return (classification, confidence 0-1)."""
        ...

    @property
    def model_name(self) -> str:
        return self.__class__.__name__


class BaselineClassifier(BaseClassifier):
    """
    Deterministic baseline classifier — prototype, NOT a trained ML model.

    Scores each class with hand-crafted evidence weights, then converts
    max-score vs total to confidence. Transparent and demo-friendly.
    """

    @property
    def model_name(self) -> str:
        return "baseline-v0"

    def predict(self, fv: FeatureVector) -> Tuple[str, float]:
        scores: Dict[str, float] = {
            ClassificationLabel.industrial_fire.value: 0.0,
            CANONICAL_PERSISTENT: 0.0,
            ClassificationLabel.gas_flare.value: 0.0,
            ClassificationLabel.wildfire.value: 0.0,
            ClassificationLabel.agricultural_fire.value: 0.0,
            ClassificationLabel.unknown.value: 0.2,  # small prior
        }

        # Helper: distance evidence
        dist_fac = fv.distance_to_facility_m
        dist_forest = fv.distance_to_forest_m
        dist_agri = fv.distance_to_agriculture_m

        # --- Industrial fire evidence ---
        ind_score = 0
        if dist_fac is not None:
            if dist_fac < cfg.INDUSTRIAL_CLOSE_M:
                ind_score += 2.5
            elif dist_fac < cfg.INDUSTRIAL_NEAR_M:
                ind_score += 1.2
            elif dist_fac < cfg.INDUSTRIAL_FAR_M:
                ind_score += 0.3
            else:
                ind_score -= 0.5
        # facility type
        if fv.is_industrial_facility:
            ind_score += 1.5
        if fv.inside_industrial_area:
            ind_score += 1.0
        # thermal intensity
        if fv.frp >= cfg.FRP_HIGH:
            ind_score += 1.5
        elif fv.frp >= cfg.FRP_MEDIUM:
            ind_score += 0.8
        elif fv.frp >= cfg.FRP_LOW:
            ind_score += 0.3
        # persistence boosts industrial fire but not as strongly as persistent source
        pers = fv.persistence_score
        if pers is not None:
            if pers >= cfg.PERSISTENCE_HIGH:
                ind_score += 0.5
            elif pers >= cfg.PERSISTENCE_MODERATE:
                ind_score += 0.3
        # NDBI / NDVI
        if fv.ndbi is not None and fv.ndbi > cfg.NDBI_BUILTUP:
            ind_score += 0.6
        if fv.ndvi is not None and fv.ndvi < cfg.NDVI_LOW:
            ind_score += 0.4
        elif fv.ndvi is not None and fv.ndvi > cfg.NDVI_VEGETATION:
            ind_score -= 0.5
        # anomaly
        if fv.activity_anomaly is not None and fv.activity_anomaly > 1.0:
            ind_score += 1.0
        elif fv.activity_anomaly is not None and fv.activity_anomaly > 0.5:
            ind_score += 0.5
        # FIRMS confidence
        if fv.firms_confidence >= 80:
            ind_score += 0.3
        # If facility is a known flare type and very persistent, reduce industrial_fire
        # to let gas_flare dominate (avoid misclassifying routine flare as fire)
        if fv.is_flare_facility and pers is not None and pers >= 0.75:
            # routine flare: penalise industrial fire score
            ind_score -= 1.2
            # but if anomaly is high, it IS a fire at flare facility -> keep industrial
            if fv.activity_anomaly is not None and fv.activity_anomaly >= 2:
                ind_score += 1.0

        scores[ClassificationLabel.industrial_fire.value] = max(0, ind_score)

        # --- Persistent industrial source ---
        pers_score = 0
        has_persistence = pers is not None
        if has_persistence:
            if pers >= cfg.PERSISTENCE_HIGH:  # type: ignore
                pers_score += 2.5
            elif pers >= cfg.PERSISTENCE_MODERATE:  # type: ignore
                pers_score += 1.2
            elif pers >= cfg.PERSISTENCE_LOW:  # type: ignore
                pers_score += 0.4
            else:
                pers_score -= 0.3
        # detections_7d / 30d
        if fv.detections_7d is not None and fv.detections_7d >= 10:
            pers_score += 1.2
        elif fv.detections_7d is not None and fv.detections_7d >= 5:
            pers_score += 0.6
        if fv.detections_30d is not None and fv.detections_30d >= 20:
            pers_score += 1.0
        # also 24h
        if fv.detections_24h is not None and fv.detections_24h >= 5:
            pers_score += 0.5
        # industrial proximity strengthens persistent
        if dist_fac is not None and dist_fac < cfg.INDUSTRIAL_CLOSE_M:
            pers_score += 1.5
        elif dist_fac is not None and dist_fac < cfg.INDUSTRIAL_NEAR_M:
            pers_score += 0.8
        # BUT persistent should penalize high FRP that looks like active fire? No, keep moderate
        # facility type industrial boosts
        if fv.is_industrial_facility:
            pers_score += 0.8
        # if no temporal context at all, heavily penalize persistent
        if not fv.has_temporal_context:
            pers_score -= 1.5
        # If cluster size small and not near industry, unlikely persistent
        # Keep low floor

        scores[CANONICAL_PERSISTENT] = max(0, pers_score)

        # --- Gas flare ---
        flare_score = 0
        if fv.is_flare_facility:
            flare_score += 3.5  # stronger base to outrank industrial_fire for flare facilities
            if pers is not None and pers >= 0.85:
                flare_score += 1.8
            elif pers is not None and pers >= cfg.PERSISTENCE_MODERATE:
                flare_score += 1.2
            if fv.frp >= 10 and fv.frp <= 120:  # flare FRP band
                flare_score += 0.8
            if dist_fac is not None and dist_fac < 1000:
                flare_score += 0.9
            # NDBI high supports
            if fv.ndbi is not None and fv.ndbi > 0.2:
                flare_score += 0.4
            # high detections over 7d/30d boost flare (persistent)
            if fv.detections_7d is not None and fv.detections_7d >= 15:
                flare_score += 0.9
            elif fv.detections_7d is not None and fv.detections_7d >= 7:
                flare_score += 0.4
            if fv.detections_30d is not None and fv.detections_30d >= 30:
                flare_score += 0.6
        else:
            flare_score -= 0.5  # without flare facility, unlikely
            # but allow weak flare if extremely persistent near industrial?
            if dist_fac is not None and dist_fac < 500 and pers is not None and pers >= 0.7:
                flare_score += 0.5

        scores[ClassificationLabel.gas_flare.value] = max(0, flare_score)

        # --- Wildfire ---
        wild_score = 0
        if dist_forest is not None and dist_forest < cfg.FOREST_CLOSE_M:
            wild_score += 2.0
            # if very close to forest stronger
            if dist_forest < 500:
                wild_score += 0.8
        if fv.ndvi is not None and fv.ndvi > cfg.NDVI_VEGETATION:
            wild_score += 1.2
        elif fv.ndvi is not None and fv.ndvi > cfg.NDVI_LOW:
            wild_score += 0.4
        if fv.hotspot_cluster_size is not None and fv.hotspot_cluster_size >= 5:
            wild_score += 1.2
        elif fv.hotspot_cluster_size is not None and fv.hotspot_cluster_size >= 3:
            wild_score += 0.6
        if dist_fac is None or (dist_fac is not None and dist_fac > cfg.INDUSTRIAL_FAR_M):
            wild_score += 0.8  # no industrial nearby
        elif dist_fac is not None and dist_fac < cfg.INDUSTRIAL_CLOSE_M:
            wild_score -= 1.0
        if fv.frp >= cfg.FRP_MEDIUM:
            wild_score += 0.5
        # wildfire less persistent daily, more cluster spread
        if fv.ndbi is not None and fv.ndbi < 0:
            wild_score += 0.3
        if fv.is_industrial_facility:
            wild_score -= 0.5

        scores[ClassificationLabel.wildfire.value] = max(0, wild_score)

        # --- Agricultural fire ---
        agri_score = 0
        if dist_agri is not None and dist_agri < cfg.AGRI_CLOSE_M:
            agri_score += 2.0
            if dist_agri < 500:
                agri_score += 0.5
        # seasonal / temporary persistence
        if pers is not None:
            if pers < cfg.PERSISTENCE_MODERATE:
                agri_score += 0.6
            elif pers >= cfg.PERSISTENCE_HIGH:
                agri_score -= 0.5
        if dist_fac is not None and dist_fac > cfg.INDUSTRIAL_NEAR_M:
            agri_score += 0.8
        elif dist_fac is not None and dist_fac < cfg.INDUSTRIAL_CLOSE_M:
            agri_score -= 0.8
        if fv.frp < cfg.FRP_MEDIUM:
            agri_score += 0.5
        elif fv.frp > cfg.FRP_HIGH:
            agri_score -= 0.4
        if fv.ndvi is not None and 0.2 < fv.ndvi < 0.6:
            agri_score += 0.3
        # detections temporal short
        if fv.detections_7d is not None and fv.detections_7d <= 3:
            agri_score += 0.3

        scores[ClassificationLabel.agricultural_fire.value] = max(0, agri_score)

        # --- Unknown handling ---
        # If all scores low (<0.8) unknown should win
        max_score = max(scores.values())
        if max_score < 0.8:
            scores[ClassificationLabel.unknown.value] = 1.0
        else:
            # unknown stays low
            scores[ClassificationLabel.unknown.value] = max(0, 0.3 if max_score < 1.5 else 0.1)

        # If absolutely no contextual evidence, force unknown
        has_any_context = fv.has_industrial_context or fv.has_forest_context or fv.has_agri_context or fv.has_temporal_context or fv.has_landcover_context
        if not has_any_context:
            # Only FRP and location known — boost unknown unless FRP extremely indicative?
            # For pure thermal anomaly with no context -> unknown
            scores[ClassificationLabel.unknown.value] = max(scores[ClassificationLabel.unknown.value], 1.2)

        # Choose winner
        winner = max(scores, key=lambda k: scores[k])
        total = sum(scores.values())
        max_s = scores[winner]

        # Confidence: gap-based + total-normalised
        # confidence = 0.5 * (max/total) + 0.5 * (gap / max) style
        sorted_scores = sorted(scores.values(), reverse=True)
        gap = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else sorted_scores[0]
        # Normalize
        share = max_s / total if total > 0 else 0
        gap_norm = min(gap / max(1.0, max_s), 1.0) if max_s > 0 else 0

        raw_conf = 0.55 * share + 0.45 * gap_norm
        # Boost confidence if FIRMS confidence high
        firms_factor = fv.firms_confidence / 100.0
        raw_conf = 0.8 * raw_conf + 0.2 * firms_factor

        # Clamp and ensure unknown never gets >0.65 confidence unless truly no context
        if winner == ClassificationLabel.unknown.value:
            raw_conf = min(raw_conf, 0.62)
            if not has_any_context:
                raw_conf = max(0.45, raw_conf)

        # Expand to 0.5-0.97 range for demo polish (avoid 0.3 confidence for clear cases)
        confidence = 0.5 + raw_conf * 0.47  # 0.5 to 0.97
        # If winner is clear (gap large), push higher
        if gap >= 1.5:
            confidence = min(0.97, confidence + 0.05)
        confidence = max(0.0, min(1.0, confidence))
        # Round to 3 decimals for stability
        confidence = round(confidence, 3)

        return winner, confidence
