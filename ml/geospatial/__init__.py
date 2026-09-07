"""
ml/geospatial — Geospatial/contextual enrichment layer.

Supports local GeoJSON files (no live Overpass/NASA).
Yash can provide `industrial_facilities.geojson` / `landcover.geojson`
without changing AI architecture.
"""

from .enrichment import EnrichmentPipeline, enrich_events  # noqa: F401
from .facility_enrichment import FacilityEnricher, normalize_facility_type  # noqa: F401
from .landcover_enrichment import LandcoverEnricher, normalize_landcover_class  # noqa: F401
from .temporal_enrichment import TemporalEnricher  # noqa: F401
from .geo_utils import haversine_m  # noqa: F401

__all__ = [
    "EnrichmentPipeline",
    "enrich_events",
    "FacilityEnricher",
    "LandcoverEnricher",
    "TemporalEnricher",
    "haversine_m",
]
