"""
Tests for OSM + Land-cover + Temporal enrichment pipeline.
All Overpass mocked, no internet.
"""

import json
import csv
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock

import pytest

from ml.geospatial.osm_enrichment import OSMEnricher, load_osm_facilities, overpass_to_geojson
from ml.geospatial.facility_enrichment import normalize_facility_type
from ml.geospatial.landcover_enrichment import LandcoverEnricher, normalize_landcover_class
from ml.geospatial.temporal_enrichment import TemporalEnricher
from ml.geospatial.enrichment_pipeline import enrich_dataset, load_daynight_map


# Helpers
def _make_firms_row(lat, lon, ts, sat="N20", frp=10, bt=320, conf=60, fid=None):
    # Use deterministic ID matching
    import hashlib
    fid = fid or f"FIRMS_{hashlib.sha1(f'{sat}|{ts}|{lat:.5f}|{lon:.5f}'.encode()).hexdigest()[:8].upper()}"
    return {"id": fid, "latitude": lat, "longitude": lon, "frp": frp, "brightness_temperature": bt, "confidence": conf, "timestamp": ts, "satellite": sat}


def _write_firms_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id","latitude","longitude","frp","brightness_temperature","confidence","timestamp","satellite"])
        w.writeheader()
        w.writerows(rows)


# OSM tests
def test_facility_normalization():
    assert normalize_facility_type({"industrial": "refinery"})[0] == "refinery"
    assert normalize_facility_type({"industrial": "oil"})[0] == "oil_gas"
    assert normalize_facility_type({"power": "plant"})[0] == "power_plant"
    assert normalize_facility_type({"landuse": "industrial"})[0] == "industrial_area"
    assert normalize_facility_type({"man_made": "works"})[0] == "factory"
    assert normalize_facility_type({"industrial": "steel"})[0] == "steel"
    assert normalize_facility_type({"industrial": "cement"})[0] == "cement"
    assert normalize_facility_type({"industrial": "chemical"})[0] == "chemical"


def test_tag_classification_preserves_raw():
    overpass_data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "refinery", "name": "Refinery A", "operator": "X"}},
        ]
    }
    gj = overpass_to_geojson(overpass_data)
    assert gj["features"][0]["properties"]["raw_tags"]["operator"] == "X"
    assert gj["features"][0]["properties"]["facility_type"] == "refinery"


def test_duplicate_handling():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}},
            {"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}},
            {"type": "node", "id": 2, "lat": 19.1, "lon": 72.9, "tags": {"industrial": "factory"}},
        ]
    }
    gj = overpass_to_geojson(data)
    assert len(gj["features"]) == 2  # duplicate removed
    facs = load_osm_facilities.__wrapped__ if hasattr(load_osm_facilities, "__wrapped__") else None
    # Test via OSMEnricher deduplication
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.geojson"
        p.write_text(json.dumps(gj))
        facs = load_osm_facilities(p)
        assert len(facs) == 2


def test_missing_name_handling():
    data = {"elements": [{"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}}]}
    gj = overpass_to_geojson(data)
    assert gj["features"][0]["properties"].get("name") is None
    enricher = OSMEnricher(load_osm_facilities(Path(tempfile.gettempdir()) / "dummy"))
    # Direct test with facility without name
    fac = [{"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "name": None, "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"}]
    enr = OSMEnricher(fac)
    info = enr.enrich(19.0, 72.8)
    assert info["nearest_facility_name"] is None
    assert info["nearest_facility_distance_m"] == 0.0


def test_node_geometry_handling():
    # Way with center
    data = {
        "elements": [
            {"type": "way", "id": 10, "center": {"lat": 19.5, "lon": 72.9}, "tags": {"industrial": "factory"}},
            {"type": "node", "id": 20, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}},
        ]
    }
    gj = overpass_to_geojson(data)
    assert len(gj["features"]) == 2
    assert gj["features"][0]["geometry"]["coordinates"] == [72.9, 19.5]


def test_invalid_geometry_skipped():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 1000, "lon": 2000, "tags": {"industrial": "factory"}},  # invalid
            {"type": "node", "id": 2, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}},
        ]
    }
    gj = overpass_to_geojson(data)
    assert len(gj["features"]) == 1


def test_distance_calculation():
    facs = [
        {"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "name": "A", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},
        {"osm_id": "node/2", "latitude": 19.1, "longitude": 72.9, "name": "B", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},
    ]
    enr = OSMEnricher(facs)
    # At 19.0,72.8 distance 0 to first
    info = enr.enrich(19.0, 72.8)
    assert info["nearest_facility_distance_m"] == 0.0
    assert info["nearest_facility_osm_id"] == "node/1"
    # Midpoint ~ 7km from both
    info2 = enr.enrich(19.05, 72.85)
    assert 5000 < info2["nearest_facility_distance_m"] < 10000


def test_nearest_facility_selection():
    facs = [
        {"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "name": "Near", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},
        {"osm_id": "node/2", "latitude": 20.0, "longitude": 73.8, "name": "Far", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},
    ]
    enr = OSMEnricher(facs)
    info = enr.enrich(19.001, 72.801)
    assert info["nearest_facility_osm_id"] == "node/1"


def test_facility_count_radius():
    facs = [
        {"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "name": "A", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},
        {"osm_id": "node/2", "latitude": 19.001, "longitude": 72.801, "name": "B", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},  # ~150m away
        {"osm_id": "node/3", "latitude": 20.0, "longitude": 73.8, "name": "C", "facility_type": "factory", "raw_tags": {}, "geometry_type": "Point"},  # far
    ]
    enr = OSMEnricher(facs)
    info = enr.enrich(19.0, 72.8)
    assert info["facility_count_500m"] == 2  # itself + 150m
    assert info["facility_count_1km"] == 2
    # Industrial counts should match
    assert info["industrial_facility_count_500m"] == 2


def test_landcover_mapping():
    assert normalize_landcover_class({"class": "forest"}) == "forest"
    assert normalize_landcover_class({"landuse": "farmland"}) == "agriculture"
    assert normalize_landcover_class({"class": "industrial"}) == "industrial"
    assert normalize_landcover_class({}) == "unknown"
    assert normalize_landcover_class({"class": "water"}) == "water"


def test_landcover_unknown_and_crs():
    enricher = LandcoverEnricher([])
    info = enricher.enrich(19.0, 72.8)
    assert info["landcover_class"] == "unknown"
    assert info["distance_to_forest"] is None
    # With synthetic polygon
    gj = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[72.8,19.0],[72.9,19.0],[72.9,19.1],[72.8,19.1],[72.8,19.0]]]}, "properties": {"class": "forest"}}
        ]
    }
    enr2 = LandcoverEnricher.from_geojson(gj)
    assert enr2.is_loaded()
    inside = enr2.enrich(19.05, 72.85)
    assert inside["landcover_class"] == "forest"


def test_temporal_leakage_safe():
    base = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    def ts(hours_ago):
        return (base - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # History: one past, one future, one same time
    history = [
        _make_firms_row(19.0, 72.8, ts(2), fid="PAST"),
        _make_firms_row(19.0, 72.8, ts(-2), fid="FUTURE"),  # 2h in future
        _make_firms_row(19.0, 72.8, base.strftime("%Y-%m-%dT%H:%M:%SZ"), fid="SAME"),
    ]
    target = _make_firms_row(19.0, 72.8, base.strftime("%Y-%m-%dT%H:%M:%SZ"), fid="TARGET")
    enr_safe = TemporalEnricher(history, leakage_safe=True)
    info = enr_safe.enrich(target)
    # Only PAST should count
    assert info["detections_24h"] == 1
    assert info["detections_7d"] == 1
    # Non-safe should count all within window (including future and same)
    enr_nonsafe = TemporalEnricher(history, leakage_safe=False)
    info2 = enr_nonsafe.enrich(target)
    assert info2["detections_24h"] == 3


def test_pipeline_preserves_rows_and_deterministic(tmp_path):
    firms_csv = tmp_path / "firms.csv"
    rows = [_make_firms_row(19.0, 72.8, "2026-08-01T00:00:00Z", fid=f"ID{i}") for i in range(5)]
    _write_firms_csv(firms_csv, rows)
    # Create small OSM cache
    osm_geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.8, 19.0]}, "properties": {"osm_id": "node/1", "industrial": "factory", "name": "Factory"}}
        ]
    }
    osm_path = tmp_path / "osm.geojson"
    osm_path.write_text(json.dumps(osm_geojson))
    out = tmp_path / "enriched.csv"
    # Need raw for daynight
    raw_path = tmp_path / "raw.csv"
    raw_path.write_text("latitude,longitude,bright_ti4,acq_date,acq_time,satellite,confidence,frp,daynight\n19.0,72.8,320,2026-08-01,0000,VIIRS,60,10,D\n")
    # Run pipeline with mocked OSM
    report = enrich_dataset(input_path=firms_csv, output_path=out, raw_path=raw_path, osm_cache=osm_path, landcover_path=None, leakage_safe=True)
    assert report["input_records"] == 5
    assert report["output_records"] == 5
    # Check output has same IDs
    import csv
    with open(out) as f:
        out_rows = list(csv.DictReader(f))
        assert len(out_rows) == 5
        assert set(r["id"] for r in out_rows) == set(r["id"] for r in rows)
        # Check no duplicate IDs
        assert len(set(r["id"] for r in out_rows)) == 5
        # Check no labels
        assert "industrial_fire" not in str(out_rows)
        for r in out_rows:
            assert r["latitude"] is not None
            assert float(r["latitude"]) >= -90


def test_missing_enrichment_handled(tmp_path):
    firms_csv = tmp_path / "firms.csv"
    rows = [_make_firms_row(19.0, 72.8, "2026-08-01T00:00:00Z")]
    _write_firms_csv(firms_csv, rows)
    out = tmp_path / "out.csv"
    # No OSM, no landcover, no history beyond single
    report = enrich_dataset(input_path=firms_csv, output_path=out, osm_cache=None, landcover_path=None, leakage_safe=True)
    import csv
    with open(out) as f:
        out_rows = list(csv.DictReader(f))
        assert out_rows[0]["nearest_facility_distance_m"] in ("", None) or out_rows[0]["nearest_facility_distance_m"] == ""
        # Landcover unknown
        assert out_rows[0]["landcover_class"] == "unknown"
        # Fractions null
        assert out_rows[0]["forest_fraction"] == ""


def test_no_labels_generated(tmp_path):
    firms_csv = tmp_path / "firms.csv"
    rows = [_make_firms_row(19.0, 72.8, "2026-08-01T00:00:00Z")]
    _write_firms_csv(firms_csv, rows)
    out = tmp_path / "out.csv"
    enrich_dataset(input_path=firms_csv, output_path=out, osm_cache=None)
    import csv
    with open(out) as f:
        reader = csv.DictReader(f)
        assert "industrial_fire" not in reader.fieldnames
        assert "wildfire" not in reader.fieldnames
        for row in reader:
            for v in row.values():
                assert "industrial_fire" not in str(v)
