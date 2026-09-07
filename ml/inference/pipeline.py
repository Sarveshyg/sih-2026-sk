"""
ml/inference/pipeline.py — High-level inference interface.

Pipeline:
  Input event (dict / EnrichedEvent)
    ↓ Validation
    ↓ Feature engineering
    ↓ Classification
    ↓ Risk scoring
    ↓ Triage recommendation
    ↓ Explanation
    ↓ PredictionOutput
"""

from __future__ import annotations

from typing import Union, Dict, Any

from ml.schemas import EnrichedEvent, PredictionOutput, ClassificationLabel, RiskLevel
from ml.features.engineering import FeatureEngineer
from ml.models.classifier import BaselineClassifier, BaseClassifier
from ml.models.risk import RiskScorer
from ml.models.anomaly import AnomalyCalculator
from ml.explainability.explanation import Explainer
from ml import config as cfg


class InferencePipeline:
    """
    Single clean interface for backend/GIS/frontend integration.

    Usage:
        pipeline = InferencePipeline()
        result = pipeline.predict(enriched_event_dict)
        # or
        result = pipeline.predict_typed(enriched_event)
    """

    def __init__(
        self,
        classifier: BaseClassifier | None = None,
        risk_scorer: RiskScorer | None = None,
        explainer: Explainer | None = None,
    ):
        self.engineer = FeatureEngineer()
        self.classifier = classifier or BaselineClassifier()
        self.risk_scorer = risk_scorer or RiskScorer()
        self.explainer = explainer or Explainer()
        self.anomaly_calc = AnomalyCalculator()

    def predict_typed(self, event: EnrichedEvent) -> PredictionOutput:
        # 1. Feature engineering
        fv = self.engineer.engineer(event)

        # 2. Classification
        raw_label, confidence = self.classifier.predict(fv)
        label = ClassificationLabel.canonical(raw_label)

        # 3. Risk scoring (independent)
        risk_score, risk_level = self.risk_scorer.score(fv, label)

        # 4. Triage (prototype thresholds, NOT official)
        if risk_score >= cfg.TRIAGE_TIER1_RISK:
            triage_required = True
            recommended_tier = 1
            action = "tier1_alert"
        elif risk_score >= cfg.TRIAGE_MONITOR_RISK:
            triage_required = False
            recommended_tier = None
            action = "monitoring"
            # For 50-74 we set triage_required False but frontend may still show monitoring
            # Spec says triage_required flag; keep True only for Tier1
        else:
            triage_required = False
            recommended_tier = None
            action = "store_only"

        # Alternative: triage_required true for monitoring? Spec example says triage_required for Tier1.
        # Keep as above — Tier1 true, else false.
        # But expose action for backend flexibility.

        # 5. Explanation (grounded)
        explanation = self.explainer.explain(fv, label, confidence, risk_score)

        # Add triage context to explanation if Tier1
        # (not hallucinated — derived from risk_score)
        # Keep explanation focused on why classification/risk, not triage.

        return PredictionOutput(
            event_id=event.id,
            classification=label,
            confidence=confidence,
            risk_score=risk_score,
            risk_level=risk_level.value,
            recommended_tier=recommended_tier,
            triage_required=triage_required,
            explanation=explanation,
            anomaly_ratio=fv.anomaly_ratio,
            persistence_score=fv.persistence_score,
            model_version=self.classifier.model_name,
        )

    def predict(self, event: Union[Dict[str, Any], EnrichedEvent]) -> Dict[str, Any]:
        """
        JSON-friendly entry point for backend team (Anway).

        Accepts dict (from API) or EnrichedEvent.
        Returns dict ready for JSON serialization.
        """
        if isinstance(event, dict):
            enriched = EnrichedEvent(**event)
        elif isinstance(event, EnrichedEvent):
            enriched = event
        else:
            raise TypeError("event must be dict or EnrichedEvent")

        result = self.predict_typed(enriched)
        return result.model_dump()

    # Alias for spec compatibility
    def __call__(self, event: Union[Dict[str, Any], EnrichedEvent]) -> Dict[str, Any]:
        return self.predict(event)


# Module-level singleton + convenience function
_default_pipeline: InferencePipeline | None = None


def get_pipeline() -> InferencePipeline:
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = InferencePipeline()
    return _default_pipeline


def predict(event: Union[Dict[str, Any], EnrichedEvent]) -> Dict[str, Any]:
    """Top-level `predict(event)` as specified in MASTER §8."""
    return get_pipeline().predict(event)
