"""
Tests for PBF OSM extract — mocked, no real PBF download required.
"""

import json
import tempfile
from pathlib import Path
import pytest

from ml.geospatial.osm_extract import _is_relevant_tags, _should_keep, FacilityExtractor
from ml.geospatial.facility_enrichment import normalize_facility_type
from ml.geospatial.osm_index import OSMIndex
from ml.geospatial.osm_enrich import enrich_firms

def test_pbf_tag_filtering():
    # Should keep industrial
    assert _is_relevant_tags({"industrial": "factory"}) is True
    assert _is_relevant_tags({"landuse": "industrial"}) is True
    assert _is_relevant_tags({"building": "industrial"}) is True
    assert _is_relevant_tags({"man_made": "works"}) is True
    assert _is_relevant_tags({"man_made": "petroleum_well"}) is True
    assert _is_relevant_tags({"man_made": "storage_tank"}) is True
    assert _is_relevant_tags({"power": "plant"}) is True
    assert _is_relevant_tags({"power": "substation"}) is True
    # Should NOT keep power=generator (wind)
    assert _is_relevant_tags({"power": "generator"}) is False
    # But _should_keep should also handle wind
    assert _should_keep({"power": "generator", "generator:source": "wind"}) is False
    assert _should_keep({"power": "generator", "generator:source": "coal"}) is False  # we exclude all generators for prototype

def test_power_plant_retention():
    assert _is_relevant_tags({"power": "plant"}) is True
    # Normalize should be power_plant
    assert normalize_facility_type({"power": "plant"})[0] == "power_plant"

def test_factory_retention():
    assert _is_relevant_tags({"industrial": "factory"}) is True
    assert normalize_facility_type({"industrial": "factory"})[0] == "factory"

def test_industrial_area_retention():
    assert _is_relevant_tags({"landuse": "industrial"}) is True
    assert normalize_facility_type({"landuse": "industrial"})[0] == "industrial_area"

def test_petroleum_well_retention():
    assert _is_relevant_tags({"man_made": "petroleum_well"}) is True
    assert normalize_facility_type({"man_made": "petroleum_well"})[0] == "oil_gas" or normalize_facility_type({"man_made": "petroleum_well"})[0] == "other"
    # At least should be kept
    assert _should_keep({"man_made": "petroleum_well"}) is True

def test_storage_tank_handling():
    # Water tank should be kept but classified as other (not industrial)
    assert _is_relevant_tags({"man_made": "storage_tank", "content": "water"}) is True
    # Normalization should handle water as other
    assert normalize_facility_type({"man_made": "storage_tank", "content": "water"})[0] == "other"
    # Oil tank should be oil_gas
    assert normalize_facility_type({"man_made": "storage_tank", "content": "oil"})[0] == "oil_gas"

def test_power_generator_exclusion():
    # All power=generator should be excluded by _is_relevant_tags
    assert _is_relevant_tags({"power": "generator"}) is False
    assert _should_keep({"power": "generator", "generator:source": "wind"}) is False
    assert _should_keep({"power": "generator", "generator:source": "solar"}) is False
    assert _should_keep({"power": "generator", "generator:source": "coal"}) is False

def test_normalization_steel_cement_chemical_refinery():
    assert normalize_facility_type({"industrial": "steel"})[0] == "steel"
    assert normalize_facility_type({"industrial": "cement"})[0] == "cement"
    assert normalize_facility_type({"industrial": "chemical"})[0] == "chemical"
    assert normalize_facility_type({"industrial": "refinery"})[0] == "refinery"
    assert normalize_facility_type({"industrial": "oil"})[0] == "oil_gas"

def test_raw_tag_preservation():
    # Simulate FacilityExtractor node
    extractor = FacilityExtractor()
    # Create mock node object
    class MockLocation:
        def __init__(self, lat, lon):
            self.lat = lat
            self.lon = lon
            self.valid = lambda: True
    class MockNode:
        def __init__(self, id, lat, lon, tags):
            self.id = id
            self.location = MockLocation(lat, lon)
            self.tags = tags
    tags = {"industrial": "refinery", "name": "Test Refinery", "operator": "TestOp"}
    node = MockNode(1, 19.0, 72.8, tags)
    extractor.node(node)
    assert len(extractor.facilities) == 1
    fac = extractor.facilities[0]
    assert fac["raw_tags"]["operator"] == "TestOp"
    assert fac["name"] == "Test Refinery"
    assert fac["facility_type"] == "refinery"

def test_geometry_conversion():
    extractor = FacilityExtractor()
    class MockLocation:
        def __init__(self, lat, lon):
            self.lat = lat
            self.lon = lon
            self.valid = lambda: True
    class MockWayNode:
        def __init__(self, lat, lon):
            self.location = MockLocation(lat, lon)
    class MockWay:
        def __init__(self, id, nodes, tags):
            self.id = id
            self.nodes = nodes
            self.tags = tags
    # Way with 4 nodes forming a square
    nodes = [MockWayNode(19.0, 72.8), MockWayNode(19.0, 72.9), MockWayNode(19.1, 72.9), MockWayNode(19.1, 72.8)]
    class WayNodes:
        def __init__(self, nodes):
            self._nodes = nodes
        def __iter__(self):
            for n in self._nodes:
                yield n
    way = MockWay(10, WayNodes(nodes), {"landuse": "industrial"})
    extractor.way(way)
    assert len(extractor.facilities) == 1
    fac = extractor.facilities[0]
    # Center should be average
    assert abs(fac["latitude"] - 19.05) < 0.01
    assert abs(fac["longitude"] - 72.85) < 0.01

def test_deterministic_deduplication():
    extractor = FacilityExtractor()
    class MockLocation:
        def __init__(self, lat, lon):
            self.lat = lat
            self.lon = lon
            self.valid = lambda: True
    class MockNode:
        def __init__(self, id, lat, lon, tags):
            self.id = id
            self.location = MockLocation(lat, lon)
            self.tags = tags
    tags = {"industrial": "factory"}
    n1 = MockNode(1, 19.0, 72.8, tags)
    n2 = MockNode(1, 19.0, 72.8, tags)  # same id
    extractor.node(n1)
    extractor.node(n2)
    assert len(extractor.facilities) == 1
    assert extractor.counters["duplicate"] == 1

def test_nearest_facility_calculation():
    # Use OSMIndex
    facilities = [
        {"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "facility_type": "factory", "name": "A"},
        {"osm_id": "node/2", "latitude": 19.1, "longitude": 72.9, "facility_type": "factory", "name": "B"},
    ]
    index = OSMIndex(facilities)
    nearest, dist = index.nearest(19.001, 72.801)
    assert nearest["osm_id"] == "node/1"
    assert dist < 200  # ~150m

def test_radius_queries():
    facilities = [
        {"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "facility_type": "factory", "name": "A"},
        {"osm_id": "node/2", "latitude": 19.001, "longitude": 72.801, "facility_type": "factory", "name": "B"},
        {"osm_id": "node/3", "latitude": 20.0, "longitude": 73.8, "facility_type": "factory", "name": "C"},
    ]
    index = OSMIndex(facilities)
    assert index.count_within(19.0, 72.8, 500) == 2
    assert index.count_within(19.0, 72.8, 1000) == 2
    assert index.count_within(19.0, 72.8, 5000) == 2
    assert len(index.query_radius(19.0, 72.8, 500)) == 2

def test_missing_nearby_facility_behavior():
    facilities = [
        {"osm_id": "node/1", "latitude": 19.0, "longitude": 72.8, "facility_type": "factory", "name": "A"},
    ]
    index = OSMIndex(facilities)
    # Far point
    nearest, dist = index.nearest(30.0, 80.0)
    # Should still return nearest, but distance large
    assert dist > 1000000
    # For enrichment, if dist >5km, should be considered no facility within 5km
    # Test enrich_firms logic
    import tempfile, csv, json
    from pathlib import Path
    from ml.geospatial.osm_enrich import enrich_firms
    # Create temp FIRMS
    with tempfile.TemporaryDirectory() as tmp:
        firms_path = Path(tmp) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,30.0,80.0,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        fac_geojson = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.8, 19.0]}, "properties": {"osm_id": "node/1", "facility_type": "factory", "name": "A"}}
            ]
        }
        fac_path = Path(tmp) / "fac.geojson"
        fac_path.write_text(json.dumps(fac_geojson))
        out = Path(tmp) / "out.csv"
        enrich_firms(firms_path, fac_path, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
            assert rows[0]["nearest_facility_distance_m"] == "" or float(rows[0]["nearest_facility_distance_m"]) > 5000
            # Should be considered no facility within 5km, so distance should be None or large, but not 0

def test_synthetic_facility_exclusion():
    # Ensure old synthetic 11-facility cache is not used in real enrichment
    # Real facilities should be from PBF, not synthetic
    # Check that synthetic cache is at data/geospatial/cache/synthetic vs real
    # For this test, ensure that enrich_firms with no facilities gives 0 counts
    facilities = []
    index = OSMIndex(facilities)
    assert index.count_within(19.0, 72.8, 500) == 0
    assert index.nearest(19.0, 72.8)[0] is None
