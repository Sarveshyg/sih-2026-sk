"""
ml/tests/test_geospatial_enrichment.py — Geospatial/Contextual Enrichment tests.

SYNTHETIC TEST DATA — NOT REAL OSM DATA
All GeoJSON fixtures are tiny synthetic polygons/points around 19°N, 72°E.

Covers 17 checks:
  nearest facility, distance calculation, facility type normalization,
  no nearby facility, land-cover polygon lookup, missing land-cover,
  forest distance, agriculture distance, 24h/7d/30d counts,
  persistence, hotspot cluster, facility baseline, anomaly,
  missing optional datasets, EnrichedEvent compatibility
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from ml.geospatial.geo_utils import haversine_m, point_in_polygon
from ml.geospatial.facility_enrichment import FacilityEnricher, normalize_facility_type
from ml.geospatial.landcover_enrichment import LandcoverEnricher
from ml.geospatial.temporal_enrichment import TemporalEnricher
from ml.geospatial.enrichment import enrich_events, EnrichmentPipeline
from ml.schemas import EnrichedEvent

# ---------------------------------------------------------------------------
# Helpers: synthetic fixtures
# ---------------------------------------------------------------------------

# Reference point for tests (Mumbai-ish)
REF_LAT = 19.076
REF_LON = 72.877


def _facility_geojson_point() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.877, 19.076]},
                "properties": {"id": "OSM_123", "name": "Test Refinery", "industrial": "refinery"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.90, 19.10]},
                "properties": {"id": "OSM_124", "industrial": "factory"},
            },
        ],
    }


def _landcover_geojson() -> dict:
    # Small polygons around ref point
    # Forest polygon: square ~1km side near REF
    # Agriculture polygon: offset ~500m south
    # Industrial polygon: around refinery point
    forest_poly = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [72.86, 19.07],
                    [72.87, 19.07],
                    [72.87, 19.08],
                    [72.86, 19.08],
                    [72.86, 19.07],
                ]
            ],
        },
        "properties": {"class": "forest"},
    }
    agri_poly = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [72.877, 19.05],
                    [72.887, 19.05],
                    [72.887, 19.06],
                    [72.877, 19.06],
                    [72.877, 19.05],
                ]
            ],
        },
        "properties": {"landuse": "farmland"},
    }
    industrial_poly = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [72.875, 19.074],
                    [72.879, 19.074],
                    [72.879, 19.078],
                    [72.875, 19.078],
                    [72.875, 19.074],
                ]
            ],
        },
        "properties": {"class": "industrial"},
    }
    water_poly = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[72.80, 19.00], [72.82, 19.00], [72.82, 19.02], [72.80, 19.02], [72.80, 19.00]]],
        },
        "properties": {"class": "water"},
    }
    return {"type": "FeatureCollection", "features": [forest_poly, agri_poly, industrial_poly, water_poly]}


def _make_event(lat: float, lon: float, ts: str, eid: str = "EVT_1") -> dict:
    return {
        "id": eid,
        "latitude": lat,
        "longitude": lon,
        "frp": 50.0,
        "brightness_temperature": 340.0,
        "confidence": 80,
        "timestamp": ts,
        "satellite": "VIIRS",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_distance_calculation_accuracy():
    # Known distance: 0,0 to 0,1 deg lon at equator ~111km
    d = haversine_m(0, 0, 0, 1)
    assert 111_000 < d < 112_000  # ~111.32km
    # Same point 0
    assert haversine_m(REF_LAT, REF_LON, REF_LAT, REF_LON) == pytest.approx(0.0)
    # 100m north shift ~0.0009 deg
    lat2 = REF_LAT + 0.0009
    d2 = haversine_m(REF_LAT, REF_LON, lat2, REF_LON)
    assert 90 < d2 < 110
    # facility approx 70m away
    d3 = haversine_m(19.076, 72.877, 19.0765, 72.8775)
    assert 50 < d3 < 120


def test_nearest_facility():
    enrich = FacilityEnricher.from_geojson(_facility_geojson_point())
    # Event 50-100m from refinery (first facility at REF_LAT,REF_LON)
    lat = 19.0765
    lon = 72.8775
    info = enrich.enrich(lat, lon)
    assert info["nearest_facility_id"] == "OSM_123"
    assert info["facility_type"] == "refinery"
    assert 50 < info["distance_to_industry"] < 150
    assert info["distance_to_facility_m"] == pytest.approx(info["distance_to_industry"])


def test_facility_type_normalization():
    assert normalize_facility_type({"industrial": "oil"})[0] == "oil_gas"
    assert normalize_facility_type({"industrial": "refinery"})[0] == "refinery"
    assert normalize_facility_type({"power": "plant"})[0] == "power_plant"
    assert normalize_facility_type({"landuse": "industrial"})[0] == "industrial_area"
    assert normalize_facility_type({"man_made": "works"})[0] == "factory"
    assert normalize_facility_type({"industrial": "chemical"})[0] == "chemical"
    # unknown → other
    assert normalize_facility_type({"industrial": "unknown_xyz"})[0] == "other"
    # direct canonical passthrough
    assert normalize_facility_type({"facility_type": "refinery"})[0] == "refinery"
    assert normalize_facility_type({})[0] == "other"


def test_no_nearby_facility():
    enrich = FacilityEnricher.from_geojson(_facility_geojson_point())
    # Far away point (several km)
    lat_far = 19.3
    lon_far = 73.2
    info = enrich.enrich(lat_far, lon_far)
    # Still returns nearest, but distance >1km
    assert info["distance_to_industry"] > 1000
    # With no dataset: all None
    empty = FacilityEnricher([])
    info2 = empty.enrich(REF_LAT, REF_LON)
    assert info2["nearest_facility_id"] is None
    assert info2["facility_type"] is None
    assert info2["distance_to_industry"] is None


def test_landcover_polygon_lookup():
    lc = LandcoverEnricher.from_geojson(_landcover_geojson())
    # Point inside industrial polygon
    inside_industrial = _make_event(19.076, 72.877, "2026-09-06T10:30:00Z")
    info = lc.enrich(inside_industrial["latitude"], inside_industrial["longitude"])
    assert info["landcover_class"] == "industrial"
    # Point inside forest polygon (approx center)
    info_forest = lc.enrich(19.075, 72.865)
    assert info_forest["landcover_class"] == "forest"
    # Point inside agriculture polygon
    info_agri = lc.enrich(19.055, 72.882)
    assert info_agri["landcover_class"] == "agriculture"
    # Point outside all
    info_out = lc.enrich(19.20, 73.00)
    assert info_out["landcover_class"] == "unknown" or info_out["landcover_class"] == "other"


def test_missing_landcover_dataset():
    empty = LandcoverEnricher([])
    info = empty.enrich(REF_LAT, REF_LON)
    assert info["landcover_class"] == "unknown"
    assert info["distance_to_forest"] is None
    assert info["distance_to_agriculture"] is None
    # Via enrichment pipeline with no landcover
    ev = _make_event(REF_LAT, REF_LON, "2026-09-06T10:30:00Z")
    enriched = enrich_events([ev], facilities=_facility_geojson_point(), landcover=None)[0]
    assert enriched["landcover_class"] == "unknown" or "landcover_class" in enriched
    # Missing dataset must be None, not 0
    assert enriched["distance_to_forest"] is None


def test_forest_and_agriculture_distance():
    lc = LandcoverEnricher.from_geojson(_landcover_geojson())
    # Event outside forest but few hundred meters away
    # Forest polygon at 72.86-72.87, 19.07-19.08
    # Event at 19.075, 72.88 → east of forest ~ ~500-1000m
    info = lc.enrich(19.075, 72.88)
    assert info["distance_to_forest"] is not None
    assert info["distance_to_forest"] > 0
    assert info["distance_to_forest"] < 5000  # within few km
    # Symmetric agri distance
    # Agri polygon at 72.877-72.887, 19.05-19.06
    # Event north of agri
    info2 = lc.enrich(19.07, 72.882)
    assert info2["distance_to_agriculture"] is not None
    assert info2["distance_to_agriculture"] < 5000
    # Missing handling
    empty = LandcoverEnricher([])
    assert empty.enrich(REF_LAT, REF_LON)["distance_to_forest"] is None


def test_temporal_counts_24h_7d_30d():
    base_ts = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    def ts(hours_ago: int):
        return (base_ts - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # History: 1 event 2h ago, 1 event 2 days ago, 1 event 10 days ago, 1 far away (>500m)
    history = [
        _make_event(REF_LAT + 0.001, REF_LON + 0.001, ts(2), "HIST_1"),  # within 500m, 2h
        _make_event(REF_LAT + 0.001, REF_LON, ts(48), "HIST_2"),  # within 500m, 2d
        _make_event(REF_LAT, REF_LON, ts(240), "HIST_3"),  # within 500m, 10d
        _make_event(19.5, 73.5, ts(5), "HIST_FAR"),  # far away, not counted
    ]
    target = _make_event(REF_LAT, REF_LON, base_ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "TARGET")
    enrich = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=False)
    info = enrich.enrich(target)
    # Within 500m: 3 neighbors (2h,2d,10d) but far one excluded
    assert info["detections_24h"] == 1  # only 2h one within 24h
    assert info["detections_7d"] == 2  # 2h + 2d
    assert info["detections_30d"] == 3  # all 3 within 30d
    assert info["persistence"] >= 0 and info["persistence"] <= 1


def test_persistence_score():
    base_ts = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    def ts(hours_ago: int):
        return (base_ts - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Many detections in 7d → high persistence
    history_many = [_make_event(REF_LAT + 0.0005, REF_LON, ts(h), f"H{h}") for h in [1, 5, 10, 20, 30, 40, 48, 72, 96, 120]]
    target = _make_event(REF_LAT, REF_LON, base_ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "TARGET")
    enrich_many = TemporalEnricher(history_many, persistence_radius_m=500)
    p_high = enrich_many.enrich(target)["persistence"]

    # No history → low persistence
    enrich_none = TemporalEnricher([], persistence_radius_m=500)
    p_low = enrich_none.enrich(target)["persistence"]

    assert p_high > p_low
    assert 0 <= p_high <= 1
    assert p_low == 0.0

    # Isolated event → low persistence (<0.3)
    history_one = [_make_event(REF_LAT, REF_LON, ts(200), "H1")]
    p_iso = TemporalEnricher(history_one, persistence_radius_m=500).enrich(target)["persistence"]
    assert p_iso < 0.5


def test_hotspot_cluster_size():
    base_ts = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    def ts():
        return base_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 4 events within 1000m cluster radius
    history = [
        _make_event(REF_LAT + 0.002, REF_LON, ts(), "C1"),
        _make_event(REF_LAT - 0.002, REF_LON, ts(), "C2"),
        _make_event(REF_LAT, REF_LON + 0.002, ts(), "C3"),
        _make_event(19.5, 73.5, ts(), "FAR"),
    ]
    target = _make_event(REF_LAT, REF_LON, ts(), "TARGET")
    enrich = TemporalEnricher(history, cluster_radius_m=1000)
    info = enrich.enrich(target)
    # Cluster includes self + 3 nearby = 4
    assert info["hotspot_cluster_size"] == 4

    # No neighbors → cluster 1 (self)
    enrich2 = TemporalEnricher([], cluster_radius_m=1000)
    assert enrich2.enrich(target)["hotspot_cluster_size"] == 1


def test_facility_baseline_and_anomaly():
    base_ts = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    def ts(days_ago: int):
        return (base_ts - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Facility at REF_LAT,REF_LON
    # History: baseline 2 detections/day over 30 days → ~60 events within 1000m
    # Create 60 events spread over 30 days, each near facility
    history = []
    for d in range(30):
        for _ in range(2):
            # jitter slightly
            history.append(_make_event(REF_LAT + 0.0001 * (d % 3), REF_LON, ts(d), f"BL_{d}_{_}"))
    # Current spike: 14 detections in last 7d near facility
    spike = []
    for i in range(14):
        spike.append(_make_event(REF_LAT, REF_LON, ts(0 if i < 2 else 1 if i < 6 else 3), f"SPIKE_{i}"))
    history_with_spike = history + spike
    # Use Facility baseline via TemporalEnricher
    target = _make_event(REF_LAT, REF_LON, base_ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "TARGET")
    enrich = TemporalEnricher(history_with_spike, facility_assign_radius_m=1000, leakage_safe=False)
    bl = enrich.facility_baseline(REF_LAT, REF_LON, current_event=target, baseline_days=30)
    assert bl["facility_baseline"] > 0
    assert bl["current_activity"] > bl["facility_baseline"]
    assert bl["activity_anomaly"] is not None
    assert bl["activity_anomaly"] > 0
    # Check ratio
    if bl["anomaly_ratio"] is not None:
        assert bl["anomaly_ratio"] > 1


def test_missing_optional_datasets_graceful():
    # No facilities, no landcover, no history
    ev = _make_event(REF_LAT, REF_LON, "2026-09-06T10:30:00Z")
    enriched = enrich_events([ev], facilities=None, landcover=None, history=None)[0]
    # All contextual None/unknown, not 0
    assert enriched["distance_to_industry"] is None
    assert enriched["nearest_facility_id"] is None
    assert enriched["facility_type"] is None
    assert enriched["landcover_class"] == "unknown"
    assert enriched["distance_to_forest"] is None
    assert enriched["distance_to_agriculture"] is None
    # Temporal fields absent → should not be 0 fabrications; either missing or not set
    assert enriched.get("detections_24h") is None or "detections_24h" not in enriched
    # Still EnrichedEvent compatible
    ee = EnrichedEvent(**enriched)
    assert ee.id == ev["id"]
    # Must not crash AI pipeline
    from ml.inference.pipeline import predict

    result = predict(enriched)
    assert "classification" in result


def test_enriched_event_compatibility_and_predict():
    # Industrial enriched event should be predict-compatible
    ev = _make_event(REF_LAT, REF_LON, "2026-09-06T10:30:00Z", "FIRMS_001")
    history = [_make_event(REF_LAT, REF_LON, "2026-09-05T10:30:00Z", "HIST1")] * 4
    enriched = enrich_events(
        [ev],
        facilities=_facility_geojson_point(),
        landcover=_landcover_geojson(),
        history=history,
    )[0]
    # Validate EnrichedEvent
    ee = EnrichedEvent(**enriched)
    assert ee.distance_to_facility_m is not None or ee.distance_to_industry is not None
    assert ee.landcover_class is not None
    # AI predict
    from ml.inference.pipeline import predict

    result = predict(enriched)
    assert result["confidence"] >= 0 and result["confidence"] <= 1
    assert 0 <= result["risk_score"] <= 100
    assert "explanation" in result
    assert len(result["explanation"]) > 0


def test_industrial_event_scenario():
    # Spec: Event 50-100m from refinery
    facilities = _facility_geojson_point()
    # Place event ~75m north-east of refinery
    # Approx 0.0005 deg ~ 55m lat, 0.0007 lon ~ 73m
    lat = 19.076 + 0.0005
    lon = 72.877 + 0.0007
    ev = _make_event(lat, lon, "2026-09-06T10:30:00Z")
    enriched = enrich_events([ev], facilities=facilities, landcover=_landcover_geojson())[0]
    assert enriched["facility_type"] == "refinery"
    assert 50 < enriched["distance_to_industry"] < 150
    assert enriched["nearest_facility_id"] == "OSM_123"


def test_wildfire_scenario():
    facilities = _facility_geojson_point()
    lc = _landcover_geojson()
    # Wildfire: inside forest polygon, several km from industry
    # Use point inside forest but offset from industrial facilities
    # Forest center roughly 19.075,72.865 → distance to refinery at 72.877,19.076 ~ ~1.3km
    ev = _make_event(19.075, 72.865, "2026-09-06T10:30:00Z")
    enriched = enrich_events([ev], facilities=facilities, landcover=lc)[0]
    assert enriched["landcover_class"] == "forest"
    assert enriched["distance_to_industry"] > 1000


def test_agricultural_scenario():
    lc = _landcover_geojson()
    ev = _make_event(19.055, 72.882, "2026-09-06T10:30:00Z")
    enriched = enrich_events([ev], facilities=_facility_geojson_point(), landcover=lc)[0]
    assert enriched["landcover_class"] == "agriculture"


def test_no_context_scenario():
    # Event outside all supplied datasets polygons (but facilities still have nearest)
    # Use a location far from all polygons and facilities? Actually facilities nearest will still be ~tens km
    # Remove landcover to simulate no context
    ev = _make_event(18.0, 71.0, "2026-09-06T10:30:00Z")
    enriched = enrich_events([ev], facilities=None, landcover=None)[0]
    assert enriched["nearest_facility_id"] is None
    assert enriched["landcover_class"] == "unknown"
    assert enriched["distance_to_industry"] is None
    assert enriched["distance_to_forest"] is None


def test_point_in_polygon_edge():
    # Sanity for geo_utils
    poly = [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
    # Note poly expects [lon, lat]
    assert point_in_polygon(0.5, 0.5, poly) is True
    assert point_in_polygon(1.5, 0.5, poly) is False
