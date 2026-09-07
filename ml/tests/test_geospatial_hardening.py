"""
ml/tests/test_geospatial_hardening.py — Hardening tests for production-like usage.

SYNTHETIC TEST DATA — NOT REAL OSM DATA
Extra fixture resembles real OSM tagging; no downloads at test runtime.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

import pytest

from ml.geospatial.geo_utils import haversine_m, distance_to_geometry_m
from ml.geospatial.facility_enrichment import FacilityEnricher, normalize_facility_type
from ml.geospatial.landcover_enrichment import LandcoverEnricher
from ml.geospatial.temporal_enrichment import TemporalEnricher
from ml.geospatial.enrichment import enrich_events, EnrichmentPipeline
from ml.schemas import EnrichedEvent

REF_LAT = 19.076
REF_LON = 72.877


def _make_event(lat, lon, ts, eid="EVT"):
    return {"id": eid, "latitude": lat, "longitude": lon, "frp": 50.0, "brightness_temperature": 340.0, "confidence": 80, "timestamp": ts, "satellite": "VIIRS"}


# ---------------------------------------------------------------------------
# 1. Leakage safety
# ---------------------------------------------------------------------------

def test_leakage_future_ignored():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    target_ts = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    past_ts = (base - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future_ts = (base + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    history = [
        _make_event(REF_LAT, REF_LON, past_ts, "PAST"),
        _make_event(REF_LAT, REF_LON, future_ts, "FUTURE"),
    ]
    target = _make_event(REF_LAT, REF_LON, target_ts, "TARGET")

    enr_safe = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=True)
    info = enr_safe.enrich(target)
    assert info["detections_24h"] == 1  # only past
    assert info["detections_7d"] == 1

    enr_safe_cluster = enr_safe.enrich(target)["hotspot_cluster_size"]
    # cluster = self + past (future excluded) = 2
    assert enr_safe_cluster == 2

    # Non-safe includes both past+future
    enr_nonsafe = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=False)
    info2 = enr_nonsafe.enrich(target)
    assert info2["detections_24h"] == 2
    assert enr_nonsafe.enrich(target)["hotspot_cluster_size"] == 3  # self + past + future


def test_leakage_same_time_excluded_strict():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    ts = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    history = [_make_event(REF_LAT, REF_LON, ts, "SAME")]
    target = _make_event(REF_LAT, REF_LON, ts, "TARGET")
    enr = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=True)
    info = enr.enrich(target)
    assert info["detections_24h"] == 0
    assert info["detections_7d"] == 0
    assert info["hotspot_cluster_size"] == 1  # only self, same-time not counted

    # Non-safe counts same-time
    enr2 = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=False)
    assert enr2.enrich(target)["detections_24h"] == 1


def test_leakage_historical_window_included():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "TARGET")
    # 23h ago should be inside 24h window
    h1 = _make_event(REF_LAT, REF_LON, (base - timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ"), "H1")
    h2 = _make_event(REF_LAT, REF_LON, (base - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ"), "H2")
    h3 = _make_event(REF_LAT, REF_LON, (base - timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ"), "H3")
    h4 = _make_event(REF_LAT, REF_LON, (base - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ"), "H4")
    history = [h1, h2, h3, h4]
    enr = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=True)
    info = enr.enrich(target)
    assert info["detections_24h"] == 1  # only H1 (23h)
    # H1 23h + H2 25h + H3 6d are within 7d = 3; H4 8d not
    assert info["detections_7d"] == 3
    assert info["detections_30d"] == 4


def test_leakage_deterministic():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    history = [_make_event(REF_LAT + i * 0.0001, REF_LON, (base - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), f"H{i}") for i in range(5)]
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "TARGET")
    enr = TemporalEnricher(list(reversed(history)), persistence_radius_m=500, leakage_safe=True)
    info1 = enr.enrich(target)
    # Reversed order should give same counts (deterministic, not order-dependent)
    enr2 = TemporalEnricher(history, persistence_radius_m=500, leakage_safe=True)
    info2 = enr2.enrich(target)
    assert info1 == info2

    # Through pipeline also deterministic
    fac = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.877, 19.076]}, "properties": {"industrial": "refinery"}}]}
    e1 = enrich_events([target], facilities=fac, history=history, leakage_safe=True)[0]
    e2 = enrich_events([target], facilities=fac, history=list(reversed(history)), leakage_safe=True)[0]
    assert e1["detections_24h"] == e2["detections_24h"]
    assert e1["persistence"] == e2["persistence"]


def test_leakage_facility_baseline_strict():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    target_ts = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    past = (base - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future = (base + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    history = [
        _make_event(REF_LAT, REF_LON, past, "PAST"),
        _make_event(REF_LAT, REF_LON, future, "FUTURE"),
    ]
    target = _make_event(REF_LAT, REF_LON, target_ts, "TARGET")
    enr = TemporalEnricher(history, facility_assign_radius_m=1000, leakage_safe=True)
    bl = enr.facility_baseline(REF_LAT, REF_LON, current_event=target, baseline_days=30)
    # Only past counts: baseline =1/30, current_activity counts past if within 7d
    assert bl["facility_baseline"] == pytest.approx(1 / 30)
    # Future excluded
    assert bl["facility_baseline"] != pytest.approx(2 / 30)


# ---------------------------------------------------------------------------
# 2. Persistence scoring bounds
# ---------------------------------------------------------------------------

def test_persistence_zero():
    enr = TemporalEnricher([], persistence_radius_m=500)
    target = _make_event(REF_LAT, REF_LON, "2026-09-06T12:00:00Z", "T")
    assert enr.enrich(target)["persistence"] == 0.0
    assert enr.enrich(target)["persistence_score"] == 0.0


def test_persistence_one_detection():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    h = _make_event(REF_LAT, REF_LON, (base - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "H1")
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "T")
    enr = TemporalEnricher([h], persistence_radius_m=500, leakage_safe=True)
    p = enr.enrich(target)["persistence"]
    assert 0 < p < 0.5
    assert 0 <= p <= 1


def test_persistence_repeated_and_many():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    many = [_make_event(REF_LAT, REF_LON, (base - timedelta(hours=i*6)).strftime("%Y-%m-%dT%H:%M:%SZ"), f"H{i}") for i in range(20)]
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "T")
    enr = TemporalEnricher(many, persistence_radius_m=500, leakage_safe=True)
    p = enr.enrich(target)["persistence"]
    assert 0.7 < p <= 1.0
    assert 0 <= p <= 1

    # Repeated (5 in 24h)
    five = [_make_event(REF_LAT, REF_LON, (base - timedelta(hours=i*4)).strftime("%Y-%m-%dT%H:%M:%SZ"), f"H{i}") for i in range(5)]
    p2 = TemporalEnricher(five, persistence_radius_m=500, leakage_safe=True).enrich(target)["persistence"]
    assert 0.3 < p2 < 1.0


def test_persistence_high_24h_low_7d():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    # 4 within 24h, but no older
    recent = [_make_event(REF_LAT, REF_LON, (base - timedelta(hours=i*5)).strftime("%Y-%m-%dT%H:%M:%SZ"), f"H{i}") for i in range(4)]
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "T")
    p = TemporalEnricher(recent, persistence_radius_m=500, leakage_safe=True).enrich(target)["persistence"]
    assert 0 <= p <= 1
    # Should be moderate due to 24h activity
    assert p > 0


def test_persistence_high_7d_low_24h():
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    # 8 detections spread over 7d, none within last 24h (oldest 2-7d)
    older = [_make_event(REF_LAT, REF_LON, (base - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ"), f"H{d}") for d in [2, 3, 4, 5, 6, 2.5, 3.5, 4.5]]
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "T")
    p = TemporalEnricher(older, persistence_radius_m=500, leakage_safe=True).enrich(target)["persistence"]
    assert 0 <= p <= 1
    assert p > 0.3  # 7d activity should drive persistence even without 24h


def test_persistence_bounded_0_1():
    # Stress: many detections should cap at 1
    base = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    huge = [_make_event(REF_LAT, REF_LON, (base - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), f"H{i}") for i in range(100)]
    target = _make_event(REF_LAT, REF_LON, base.strftime("%Y-%m-%dT%H:%M:%SZ"), "T")
    p = TemporalEnricher(huge, persistence_radius_m=500, leakage_safe=True).enrich(target)["persistence"]
    assert p <= 1.0
    assert p >= 0.0


# ---------------------------------------------------------------------------
# 3. Geometry distance semantics
# ---------------------------------------------------------------------------

def test_distance_point_to_point():
    fac = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.877, 19.076]}, "properties": {"industrial": "refinery"}}]}
    enrich = FacilityEnricher.from_geojson(fac)
    # Event exactly at facility → 0
    info = enrich.enrich(19.076, 72.877)
    assert info["distance_to_industry"] == pytest.approx(0.0, abs=1e-6)
    # 0.001 deg lat ~111m → check haversine
    info2 = enrich.enrich(19.077, 72.877)
    assert 100 < info2["distance_to_industry"] < 130
    # Compare to direct haversine
    assert info2["distance_to_industry"] == pytest.approx(haversine_m(19.077, 72.877, 19.076, 72.877), rel=0.01)


def test_distance_polygon_boundary_and_inside():
    poly = {
        "type": "FeatureCollection",
        "features": [
            {
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
                "properties": {"industrial": "refinery"},
            }
        ],
    }
    enrich = FacilityEnricher.from_geojson(poly)
    # Inside → 0 and inside flag True
    inside = enrich.enrich(19.076, 72.877)
    assert inside["distance_to_industry"] == pytest.approx(0.0)
    assert inside["inside_industrial_area"] is True
    # Just outside east edge (~100m)
    # Polygon east edge at lon 72.879, point at 72.880 at same lat (~105m at this lat)
    outside = enrich.enrich(19.076, 72.88)
    assert 50 < outside["distance_to_industry"] < 250
    assert outside["inside_industrial_area"] is False
    # Verify not centroid distance: centroid approx 72.877,19.076 would give ~330m, but edge is ~100m
    centroid_dist = haversine_m(19.076, 72.88, 19.076, 72.877)
    # Edge distance should be less than centroid distance
    assert outside["distance_to_industry"] < centroid_dist


def test_distance_multipolygon():
    mp = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [[[72.86, 19.07], [72.87, 19.07], [72.87, 19.08], [72.86, 19.08], [72.86, 19.07]]],
                        [[[72.90, 19.10], [72.91, 19.10], [72.91, 19.11], [72.90, 19.11], [72.90, 19.10]]],
                    ],
                },
                "properties": {"industrial": "factory"},
            }
        ],
    }
    enrich = FacilityEnricher.from_geojson(mp)
    # Inside first polygon → 0
    assert enrich.enrich(19.075, 72.865)["distance_to_industry"] == pytest.approx(0.0)
    # Inside second
    assert enrich.enrich(19.105, 72.905)["distance_to_industry"] == pytest.approx(0.0)
    # Outside both → nearest edge
    outside = enrich.enrich(19.075, 72.875)
    assert 0 < outside["distance_to_industry"] < 5000
    # Direct helper also: distance_to_geometry_m should handle MultiPolygon 0 case
    geom = {"type": "MultiPolygon", "coordinates": mp["features"][0]["geometry"]["coordinates"]}
    assert distance_to_geometry_m(19.075, 72.865, geom) == pytest.approx(0.0)


def test_geometry_invalid_handling():
    # Unknown geometry type should be skipped, not crash
    gj = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}, "properties": {"industrial": "factory"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.877, 19.076]}, "properties": {"industrial": "refinery"}},
        ],
    }
    enrich = FacilityEnricher.from_geojson(gj)
    # Only Point should be kept
    assert len(enrich.facilities) == 1
    assert enrich.enrich(19.076, 72.877)["distance_to_industry"] == pytest.approx(0.0)

    # Missing geometry → skipped
    gj2 = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"industrial": "refinery"}}]}
    assert FacilityEnricher.from_geojson(gj2).facilities == []


# ---------------------------------------------------------------------------
# 5. Realistic OSM fixtures
# ---------------------------------------------------------------------------

def test_osm_realistic_fixtures_mapping():
    # Deterministic fixture resembling real OSM tagging
    osm_fixture = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.877, 19.076]}, "properties": {"industrial": "refinery", "name": "Refinery A"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.878, 19.077]}, "properties": {"industrial": "chemical", "name": "Chemical Plant"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.879, 19.078]}, "properties": {"industrial": "oil", "name": "Oil Field"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.880, 19.079]}, "properties": {"power": "plant", "name": "Power Plant"}},
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[72.875, 19.074], [72.879, 19.074], [72.879, 19.078], [72.875, 19.078], [72.875, 19.074]]]}, "properties": {"landuse": "industrial", "name": "Industrial Estate"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.881, 19.080]}, "properties": {"man_made": "works", "name": "Works"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.882, 19.081]}, "properties": {"facility_type": "refinery", "name": "Pre-normalized"}},
        ],
    }
    enrich = FacilityEnricher.from_geojson(osm_fixture)
    assert len(enrich.facilities) == 7

    # Check mappings preserve original
    mapping = {f["name"]: (f["canonical_type"], f["original_type"]) for f in enrich.facilities}
    assert mapping["Refinery A"] == ("refinery", "refinery")
    assert mapping["Chemical Plant"] == ("chemical", "chemical")
    assert mapping["Oil Field"] == ("oil_gas", "oil")
    assert mapping["Power Plant"] == ("power_plant", "plant")
    assert mapping["Industrial Estate"][0] == "industrial_area"
    assert mapping["Works"] == ("factory", "works")
    assert mapping["Pre-normalized"] == ("refinery", "refinery")

    # Enrich near each and verify type
    ev = _make_event(19.076, 72.877, "2026-09-06T12:00:00Z")
    info = enrich.enrich(ev["latitude"], ev["longitude"])
    assert info["facility_type"] == "refinery"

    # Landcover realistic also
    from ml.geospatial.landcover_enrichment import normalize_landcover_class

    assert normalize_landcover_class({"class": "forest"}) == "forest"
    assert normalize_landcover_class({"landuse": "farmland"}) == "agriculture"
    assert normalize_landcover_class({"natural": "wood"}) == "forest"


# ---------------------------------------------------------------------------
# 6. Missing-data behavior
# ---------------------------------------------------------------------------

def test_missing_individual_geometry_properties():
    # Feature with missing properties should not crash
    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.877, 19.076]}, "properties": {}}]}
    enrich = FacilityEnricher.from_geojson(gj)
    info = enrich.enrich(19.076, 72.877)
    assert info["facility_type"] == "other"
    assert info["distance_to_industry"] == pytest.approx(0.0)

    lc_empty = LandcoverEnricher.from_geojson({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}, "properties": {}}]})
    # Empty props → unknown class but still polygon works
    assert lc_empty.enrich(0.5, 0.5)["landcover_class"] in ("unknown", "other")


# ---------------------------------------------------------------------------
# 7. Determinism + lightweight performance
# ---------------------------------------------------------------------------

def test_enrichment_deterministic():
    fac = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.877, 19.076]}, "properties": {"industrial": "refinery"}}]}
    lc = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[72.86,19.07],[72.87,19.07],[72.87,19.08],[72.86,19.08],[72.86,19.07]]]}, "properties": {"class": "forest"}}]}
    ev = _make_event(19.076, 72.877, "2026-09-06T12:00:00Z", "EVT")
    history = [_make_event(19.076, 72.877, "2026-09-05T12:00:00Z", f"H{i}") for i in range(3)]

    r1 = enrich_events([ev], facilities=fac, landcover=lc, history=history, leakage_safe=True)[0]
    r2 = enrich_events([ev], facilities=fac, landcover=lc, history=list(reversed(history)), leakage_safe=True)[0]
    assert r1 == r2  # same regardless of facility/landcover order? Facilities order matters for tie but deterministic
    # Also direct enrich twice
    pipe = EnrichmentPipeline(facilities=fac, landcover=lc, history=history, leakage_safe=True)
    assert pipe.enrich_one(ev) == pipe.enrich_one(ev)


def test_performance_lightweight():
    # Thousands of events/facilities without being unusably slow (not timing assertion, just completes)
    facilities = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.87 + i*0.001, 19.076]}, "properties": {"industrial": "factory"}} for i in range(100)]}
    events = [_make_event(19.076 + (i%10)*0.0005, 72.877 + (i%10)*0.0005, "2026-09-06T12:00:00Z", f"EVT{i}") for i in range(500)]
    history = [_make_event(19.076, 72.877, "2026-09-05T12:00:00Z", f"H{i}") for i in range(200)]

    start = time.perf_counter()
    out = enrich_events(events, facilities=facilities, history=history)
    elapsed = time.perf_counter() - start
    assert len(out) == 500
    # Should be well under 10s on CI; not a brittle timing, just sanity that it completes
    assert elapsed < 10
