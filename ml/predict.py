"""
ml/predict.py — Convenience top-level for backend integration.

Backend team (Anway) can:
    from ml.predict import predict
    result = predict(enriched_event_dict)

or:
    from ml.inference.pipeline import InferencePipeline
"""
from ml.inference.pipeline import predict, get_pipeline, InferencePipeline  # noqa: F401

__all__ = ["predict", "get_pipeline", "InferencePipeline"]
