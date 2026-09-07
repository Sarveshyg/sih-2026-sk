"""
ml.data — FIRMS ingestion and preprocessing pipeline.

Exposes:
  - firms_schema: column mappings and normalization docs
  - firms_loader: CSV ingestion
  - firms_cleaner: validation/cleaning
  - pipeline: high-level orchestration + CLI
"""

# Lazy re-export to avoid `runpy` warning when executing `python -m ml.data.pipeline`
# (importing ml.data.pipeline while ml.data is already loaded).
try:
    from .pipeline import FirmsReport, process_firms_file  # noqa: F401
except ImportError:
    pass

__all__ = ["process_firms_file", "FirmsReport"]
