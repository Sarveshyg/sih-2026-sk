"""
Tests for ml/geospatial/boundary_filter.py — India boundary filtering.

All geometries synthetic except referencing saved india.geojson; no live downloads.
"""

from __future__ import annotations

import json
import csv
import tempfile
from pathlib import Path

import pytest

from ml.geospatial.boundary_filter import load_boundary, is_inside, filter_events, filter_csv
from ml.geospatial.geo_utils import point_in_polygon, point_in_multipolygon

# Reference boundary path
BOUNDARY_PATH = Path("data/geospatial/boundaries/india.geojson")


def test_known_point_inside_india():
    b = load_boundary(BOUNDARY_PATH)
    # New Delhi
    assert is_inside(28.6139, 77.2090, b) is True
    # Mumbai
    assert is_inside(19.076, 72.877, b) is True
    # Andaman Islands (part of India multipolygon)
    assert is_inside(11.7400, 92.6586, b) is True
    # Chennai
    assert is_inside(13.0827, 80.2707, b) is True


def test_known_point_outside_india():
    b = load_boundary(BOUNDARY_PATH)
    # Colombo, Sri Lanka
    assert is_inside(6.9271, 79.8612, b) is False
    # Karachi, Pakistan
    assert is_inside(24.8607, 67.0011, b) is False
    # Dhaka, Bangladesh
    assert is_inside(23.8103, 90.4125, b) is False
    # Indian Ocean far south
    assert is_inside(2.0, 80.0, b) is False
    # Tibet/China north
    assert is_inside(35.0, 85.0, b) is False


def test_boundary_multipolygon_handling():
    b = load_boundary(BOUNDARY_PATH)
    assert b["geometry_type"] == "MultiPolygon"
    # Multipolygon should contain both mainland and islands
    # Use point_in_multipolygon directly for synthetic sanity
    # Create simple multipolygon fixture
    multi = [
        [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
    ]
    assert point_in_multipolygon(0.5, 0.5, multi) is True
    assert point_in_multipolygon(2.5, 2.5, multi) is True
    assert point_in_multipolygon(1.5, 1.5, multi) is False
    # Synthetic through boundary_filter
    synth = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ADMIN": "TestMulti"},
                "geometry": {"type": "MultiPolygon", "coordinates": multi},
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False, encoding="utf-8") as tmp:
        json.dump(synth, tmp)
        tmp_path = Path(tmp.name)
    try:
        b2 = load_boundary(tmp_path)
        assert b2["geometry_type"] == "MultiPolygon"
        assert is_inside(0.5, 0.5, b2) is True
        assert is_inside(2.5, 2.5, b2) is True
        assert is_inside(1.5, 1.5, b2) is False
    finally:
        tmp_path.unlink()


def test_boundary_polygon_handling():
    poly = [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
    assert point_in_polygon(0.5, 0.5, [poly[0]]) is True if False else point_in_polygon(0.5, 0.5, [poly[0]]) is True  # dummy to avoid unused
    # Actual test via boundary_filter with Polygon
    synth = {
        "type": "Feature",
        "properties": {"ADMIN": "TestPoly"},
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False, encoding="utf-8") as tmp:
        json.dump(synth, tmp)
        tmp_path = Path(tmp.name)
    try:
        b = load_boundary(tmp_path)
        assert b["geometry_type"] == "Polygon"
        assert is_inside(1, 1, b) is True
        assert is_inside(3, 3, b) is False
    finally:
        tmp_path.unlink()


def test_malformed_geometry_error_handling():
    # Invalid type
    bad = {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False, encoding="utf-8") as tmp:
        json.dump({"type": "FeatureCollection", "features": [bad]}, tmp)
        p = Path(tmp.name)
    try:
        with pytest.raises(ValueError, match="Polygon/MultiPolygon"):
            load_boundary(p)
    finally:
        p.unlink()

    # Missing coordinates
    bad2 = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": []}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False, encoding="utf-8") as tmp:
        json.dump(bad2, tmp)
        p = Path(tmp.name)
    try:
        with pytest.raises(ValueError):
            load_boundary(p)
    finally:
        p.unlink()

    # Out-of-range coordinate
    bad3 = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [[[200, 0], [200, 1], [201, 1], [200, 0]]]},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False, encoding="utf-8") as tmp:
        json.dump(bad3, tmp)
        p = Path(tmp.name)
    try:
        with pytest.raises(ValueError, match="WGS84"):
            load_boundary(p)
    finally:
        p.unlink()

    # Nonexistent file
    with pytest.raises(FileNotFoundError):
        load_boundary("nonexistent.geojson")


def test_filter_events_preserves_columns():
    b = load_boundary(BOUNDARY_PATH)
    events = [
        {"id": "A", "latitude": 28.61, "longitude": 77.20, "frp": 10, "extra": "keep"},
        {"id": "B", "latitude": 6.92, "longitude": 79.86, "frp": 10, "extra": "keep"},
    ]
    inside, outside = filter_events(events, b)
    assert len(inside) == 1 and inside[0]["id"] == "A"
    assert len(outside) == 1 and outside[0]["id"] == "B"
    assert inside[0]["extra"] == "keep"


def test_filter_csv_preserves_and_reports():
    b_path = BOUNDARY_PATH
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as tmp_in:
        writer = csv.DictWriter(tmp_in, fieldnames=["id", "latitude", "longitude", "frp", "brightness_temperature", "confidence", "timestamp", "satellite"])
        writer.writeheader()
        writer.writerow({"id": "IN1", "latitude": 19.076, "longitude": 72.877, "frp": 10, "brightness_temperature": 320, "confidence": 60, "timestamp": "2026-08-01T00:00:00Z", "satellite": "VIIRS"})
        writer.writerow({"id": "OUT1", "latitude": 6.9271, "longitude": 79.8612, "frp": 10, "brightness_temperature": 320, "confidence": 60, "timestamp": "2026-08-01T00:00:00Z", "satellite": "VIIRS"})
        tmp_in_path = Path(tmp_in.name)

    out_path = Path(tempfile.gettempdir()) / "test_india_out.csv"
    report = filter_csv(tmp_in_path, out_path, boundary_path=b_path)

    assert report["original_records"] == 2
    assert report["records_inside_india"] == 1
    assert report["records_outside_india"] == 1
    assert report["boundary_type"] == "MultiPolygon"
    assert report["crs"] == "EPSG:4326"

    # Output preserves header order and columns
    with out_path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["id"] == "IN1"
        assert set(reader.fieldnames) == {"id", "latitude", "longitude", "frp", "brightness_temperature", "confidence", "timestamp", "satellite"}

    tmp_in_path.unlink()
    out_path.unlink()
    # cleanup reports
    for p in [out_path.with_name(out_path.stem + "_filter_report.json"), Path("data/firms/processed/india_filter_report.json")]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def test_sri_lanka_removed_from_real_dataset():
    # Verify the real filtered dataset has 0 Sri Lanka bbox points as in production run
    clean = Path("data/firms/processed/firms_clean.csv")
    india = Path("data/firms/processed/firms_india.csv")
    if not clean.exists() or not india.exists():
        pytest.skip("Real dataset not present")
    b = load_boundary(BOUNDARY_PATH)
    # Check known Colombo point not in india file via filter logic
    assert is_inside(6.9271, 79.8612, b) is False
    # Count Sri Lanka bbox in india file should be 0
    with india.open() as f:
        rows = list(csv.DictReader(f))
        sl = [r for r in rows if 5.5 <= float(r["latitude"]) <= 10 and 79.5 <= float(r["longitude"]) <= 82]
        assert len(sl) == 0, f"Expected 0 Sri Lanka detections inside India, got {len(sl)}"
